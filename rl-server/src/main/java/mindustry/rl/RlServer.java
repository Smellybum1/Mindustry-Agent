package mindustry.rl;

import arc.*;
import arc.math.*;
import arc.util.*;
import arc.util.serialization.*;
import mindustry.*;
import mindustry.content.*;
import mindustry.core.*;
import mindustry.ui.*;
import mindustry.core.GameState.*;
import mindustry.ctype.*;
import mindustry.game.*;
import mindustry.game.EventType.*;
import mindustry.gen.*;
import mindustry.mod.*;
import mindustry.mod.Mods.*;
import mindustry.net.Net;

import java.io.*;
import java.net.*;
import java.lang.reflect.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

import static mindustry.Vars.*;

/**
 * Externally-stepped headless RL server (roadmap M1).
 *
 * <p>Boots Mindustry content once (mirroring {@code ServerLauncher.init()} minus
 * {@code ServerControl}), then drives the real {@link Logic} at a fixed {@code 1/60f}
 * delta from an external client over a loopback length-prefixed JSON socket
 * (docs/PROTOCOL.md). All game-state access happens on the simulation thread (the
 * thread that calls {@link #serve()}); a separate reader thread only parses frames
 * and enqueues them (AGENTS.md §3 threading rule).
 */
public final class RlServer{
    public static final String ENGINE_TAG = "v159.7";
    public static final String ENGINE_COMMIT = "c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c";
    public static final String ARC_VERSION = "208a754044";
    public static final int PROTOCOL_VERSION = 1;
    public static final int MAX_MESSAGE_SIZE = 16 * 1024 * 1024;
    public static final int SCENARIO_SCHEMA_VERSION = 1;

    /** Sentinel enqueued by the reader thread when the peer closes. */
    private static final Jval EOF = Jval.newObject();

    private final int port;
    private final Scenario scenario = new Scenario(48);
    private final FixedStepApplication app;

    private final BlockingQueue<Jval> requests = new LinkedBlockingQueue<>();
    private ServerSocket serverSocket;
    private Socket client;
    private DataInputStream in;
    private DataOutputStream out;

    //episode state (simulation thread only)
    private String episodeId;
    private long rootSeed;
    private int agentCount = 1;
    private long uptimeTicks;
    private final AtomicBoolean stop = new AtomicBoolean(false);

    private Method pathfinderStop;
    private Method controlPathStop;
    private Field entityLastId;
    private Field timeGlobalRaw;
    private Field timeGlobal;

    public RlServer(int port){
        this.port = port;
        this.app = new FixedStepApplication();
    }

    // ------------------------------------------------------------------ boot

    /** One-time engine boot on the calling (simulation) thread. */
    public void boot(){
        app.setMainThread(Thread.currentThread());

        Vars.platform = new Platform(){};
        Vars.net = new Net(null);

        //keep runtime settings OUT of the repo (cwd is core/assets); one dir per port
        //so parallel JVMs (M2) never contend on the same settings file
        java.io.File dataDir = new java.io.File(
            System.getProperty("java.io.tmpdir"), "mindustry-rl-" + port);
        dataDir.mkdirs();
        Core.settings.setDataDirectory(Core.files.absolute(dataDir.getAbsolutePath()));
        loadLocales = false;
        headless = true;

        Vars.loadSettings();
        Vars.init();

        UI.loadColors();
        Fonts.loadContentIconsHeadless();

        content.createBaseContent();
        mods.loadScripts();
        content.createModContent();
        content.init();

        if(mods.hasContentErrors()){
            for(LoadedMod mod : mods.list()){
                if(mod.hasContentErrors()){
                    for(Content cont : mod.erroredContent){
                        Log.err("content error in @: @", cont.minfo.sourceFile.name(), cont.minfo.baseError);
                    }
                }
            }
            throw new RuntimeException("mod content errors; refusing to boot");
        }

        bases.load();

        //listener order mirrors ServerLauncher.java:74-78, minus ServerControl
        Core.app.addListener(new ApplicationListener(){ public void update(){ asyncCore.begin(); } });
        Core.app.addListener(logic = new Logic());
        Core.app.addListener(netServer = new mindustry.core.NetServer());
        Core.app.addListener(new ApplicationListener(){ public void update(){ asyncCore.end(); } });

        mods.eachClass(Mod::init);
        Events.fire(new ServerLoadEvent());

        app.initOnce();

        cacheReflection();
    }

    private void cacheReflection(){
        try{
            pathfinderStop = pathfinder.getClass().getDeclaredMethod("stop");
            pathfinderStop.setAccessible(true);
            controlPathStop = controlPath.getClass().getDeclaredMethod("stop");
            controlPathStop.setAccessible(true);
            entityLastId = mindustry.entities.EntityGroup.class.getDeclaredField("lastId");
            entityLastId.setAccessible(true);
            //globalTimeRaw has no public setter (docs/ENGINE_NOTES.md §12.3)
            timeGlobalRaw = Time.class.getDeclaredField("globalTimeRaw");
            timeGlobalRaw.setAccessible(true);
            timeGlobal = Time.class.getDeclaredField("globalTime");
            timeGlobal.setAccessible(true);
        }catch(Exception e){
            throw new RuntimeException("reflection setup failed (engine layout changed?)", e);
        }
    }

    // ------------------------------------------------------------------ serve

    /** Bind, accept one client, and run the request loop on this thread. */
    public void serve() throws IOException{
        serverSocket = new ServerSocket();
        serverSocket.setReuseAddress(true);
        try{
            serverSocket.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), port));
        }catch(IOException e){
            Log.err("failed to bind 127.0.0.1:@ (port busy?): @", port, e.getMessage());
            throw e;
        }

        //single READY line on stdout for launcher readiness detection; logs go to stderr
        System.out.println("READY " + port);
        System.out.flush();

        client = serverSocket.accept();
        client.setTcpNoDelay(true);
        in = new DataInputStream(new BufferedInputStream(client.getInputStream()));
        out = new DataOutputStream(new BufferedOutputStream(client.getOutputStream()));

        Thread reader = new Thread(this::readLoop, "rl-io-reader");
        reader.setDaemon(true);
        reader.start();

        try{
            mainLoop();
        }finally{
            cleanup();
        }
    }

    /** I/O thread: parse frames, enqueue. Never touches game state. */
    private void readLoop(){
        try{
            while(!stop.get()){
                int len = in.readInt();
                if(len < 0 || len > MAX_MESSAGE_SIZE){
                    Log.err("oversized/invalid frame length @; closing", len);
                    break;
                }
                byte[] body = new byte[len];
                in.readFully(body);
                Jval msg = Jval.read(new String(body, java.nio.charset.StandardCharsets.UTF_8));
                requests.put(msg);
            }
        }catch(EOFException | SocketException e){
            //peer closed
        }catch(Exception e){
            Log.err("reader error: @", e.getMessage());
        }finally{
            requests.offer(EOF);
        }
    }

    /** Simulation thread: dispatch requests, write responses. */
    private void mainLoop() throws IOException{
        while(app.isRunning() && !stop.get()){
            Jval req;
            try{
                req = requests.take();
            }catch(InterruptedException e){
                break;
            }
            if(req == EOF) break;

            String type = req.getString("type", "");
            if("close_request".equals(type)){
                sendClose(req);
                break;
            }

            Jval resp = dispatch(req, type);
            if(resp != null){
                writeFrame(resp);
            }
        }
    }

    private Jval dispatch(Jval req, String type){
        try{
            switch(type){
                case "handshake_request": return handshake(req);
                case "reset_request": return reset(req);
                case "step_request": return step(req);
                case "health_request": return health(req);
                default: return error(req, "unknown_type", "unknown message type: " + type);
            }
        }catch(ProtocolReject r){
            return error(req, r.code, r.getMessage());
        }catch(Exception e){
            Log.err("dispatch error on @: @", type, e);
            return error(req, "internal_error", String.valueOf(e.getMessage()));
        }
    }

    // ------------------------------------------------------------ handlers

    private Jval handshake(Jval req){
        Jval r = Jval.newObject();
        r.put("type", "handshake_response");
        r.put("protocol_version", PROTOCOL_VERSION);
        r.put("engine_version", ENGINE_TAG);
        r.put("engine_commit", ENGINE_COMMIT);
        r.put("arc_version", ARC_VERSION);
        r.put("scenario_schema_version", SCENARIO_SCHEMA_VERSION);
        r.add("supported_features", Jval.newArray());
        r.put("process_id", ProcessHandle.current().pid());
        return r;
    }

    private Jval reset(Jval req){
        long requestId = req.getLong("request_id", 0);
        rootSeed = req.getLong("root_seed", 0);
        agentCount = Math.max(1, req.getInt("agent_count", 1));

        doReset(rootSeed);

        episodeId = "ep-" + rootSeed + "-" + System.nanoTime();
        uptimeTicks = 0;

        Jval obs = observation();
        Jval r = Jval.newObject();
        r.put("type", "reset_response");
        r.put("request_id", requestId);
        r.put("episode_id", episodeId);
        r.put("tick", (long)state.tick);
        r.add("initial_observations", replicate(obs, agentCount));
        r.add("action_masks", replicate(Jval.newObject(), agentCount));
        r.put("state_hash", StateHasher.hash());
        r.add("metadata", scenario.metadata());
        return r;
    }

    private Jval step(Jval req){
        long requestId = req.getLong("request_id", 0);
        String reqEpisode = req.getString("episode_id", "");
        int expectedTick = req.getInt("expected_tick", -1);
        int ticks = req.getInt("ticks_to_advance", 0);

        if(episodeId == null || !episodeId.equals(reqEpisode)){
            throw new ProtocolReject("unknown_episode", "no such active episode: " + reqEpisode);
        }
        int current = (int)state.tick;
        if(expectedTick != current){
            throw new ProtocolReject("stale_tick", "expected_tick " + expectedTick + " != current " + current);
        }
        if(ticks < 0 || ticks > 1_000_000){
            throw new ProtocolReject("bad_request", "ticks_to_advance out of range: " + ticks);
        }

        int previousTick = current;

        //action application for M1 is a no-op (validated but not yet applied)
        long t0 = System.nanoTime();
        app.graphics.setDeltaSeconds(1f / 60f);
        for(int i = 0; i < ticks; i++){
            app.stepOnce();
        }
        long t1 = System.nanoTime();
        uptimeTicks += ticks;

        long o0 = System.nanoTime();
        Jval obs = observation();
        String hash = StateHasher.hash();
        long o1 = System.nanoTime();

        Jval timing = Jval.newObject();
        timing.put("engine_ms", (t1 - t0) / 1e6);
        timing.put("observation_ms", (o1 - o0) / 1e6);
        timing.put("serialization_ms", 0.0);
        timing.put("io_ms", 0.0);

        Jval r = Jval.newObject();
        r.put("type", "step_response");
        r.put("request_id", requestId);
        r.put("episode_id", episodeId);
        r.put("previous_tick", previousTick);
        r.put("tick", (long)state.tick);
        r.add("observations", replicate(obs, agentCount));
        r.add("action_masks", replicate(Jval.newObject(), agentCount));
        r.add("team_state", teamState());
        r.add("reward_breakdowns", replicate(Jval.newObject(), agentCount));
        r.add("terminations", boolArray(agentCount, false));
        r.add("truncations", boolArray(agentCount, false));
        r.add("task_events", Jval.newArray());
        r.add("game_events", Jval.newArray());
        r.put("state_hash", hash);
        r.add("timing", timing);
        return r;
    }

    private Jval health(Jval req){
        Jval r = Jval.newObject();
        r.put("type", "health_response");
        r.put("request_id", req.getLong("request_id", 0));
        r.put("ok", true);
        r.put("uptime_ticks", uptimeTicks);
        r.put("episode_id", episodeId == null ? "" : episodeId);
        r.put("detail", "engine=" + ENGINE_TAG + " tick=" + (episodeId == null ? -1 : (long)state.tick));
        return r;
    }

    private void sendClose(Jval req){
        try{
            Jval r = Jval.newObject();
            r.put("type", "health_response");
            r.put("request_id", req.getLong("request_id", 0));
            r.put("ok", true);
            r.put("uptime_ticks", uptimeTicks);
            r.put("episode_id", episodeId == null ? "" : episodeId);
            r.put("detail", "closing");
            writeFrame(r);
        }catch(IOException ignored){
        }
    }

    // ------------------------------------------------------------- reset core

    /**
     * Episode reset without JVM restart (docs/ENGINE_NOTES.md §3.4, §11.4). Handles the
     * gaps {@code Logic.reset()} leaves: reseed {@code Mathf.rand}, reset the static
     * {@code EntityGroup.lastId}, zero {@code Time}, then load the scenario and play.
     */
    private void doReset(long seed){
        logic.reset();

        //RNG: dominant lever — reseed the global generator (never reseeded by reset())
        Mathf.rand.setSeed(seed);

        //entity id counter is static and NOT reset by Logic.reset(); reset for cross-episode hash equality
        try{
            entityLastId.setInt(null, 0);
        }catch(Exception e){
            throw new RuntimeException("failed to reset EntityGroup.lastId", e);
        }

        //zero Time accumulators (Logic.reset() clears only the delayed-task list)
        Time.setInternalTime(0);
        try{
            timeGlobalRaw.setDouble(null, 0.0);
            timeGlobal.setFloat(null, 0f);
        }catch(Exception e){
            throw new RuntimeException("failed to zero Time.globalTime", e);
        }

        //rules must be set before world load (pathfinder/async read state.rules)
        state.rules = scenario.buildRules();

        scenario.load();   //fires WorldLoad* -> starts pathfinder threads
        logic.play();      //State.playing, loadout, PlayEvent (zeroes state.tick)

        stopPathfinders(); //deterministic mode: no units need pathing in M1 (§5.5, §11.6)
    }

    /** Stop the two free-running pathfinder threads via their private stop() (no upstream edit). */
    private void stopPathfinders(){
        try{
            pathfinderStop.invoke(pathfinder);
            controlPathStop.invoke(controlPath);
        }catch(Exception e){
            Log.err("failed to stop pathfinder threads: @", e.getMessage());
        }
    }

    // ------------------------------------------------------------ observation

    private Jval observation(){
        Building core = Team.sharded.core();
        Jval o = Jval.newObject();
        o.put("tick", (long)state.tick);
        o.put("wave", state.wave);
        o.put("copper", StateHasher.coreItem(Items.copper));
        o.put("lead", StateHasher.coreItem(Items.lead));
        o.put("unit_count", Groups.unit.size());
        o.put("building_count", Groups.build.size());
        o.put("core_health", core == null ? 0.0 : core.health);
        o.put("done", state.gameOver);
        return o;
    }

    private Jval teamState(){
        Jval t = Jval.newObject();
        t.put("team", "sharded");
        t.put("cores", Team.sharded.cores().size);
        t.put("copper", StateHasher.coreItem(Items.copper));
        t.put("lead", StateHasher.coreItem(Items.lead));
        return t;
    }

    // ------------------------------------------------------------- utilities

    private Jval error(Jval req, String code, String message){
        Jval r = Jval.newObject();
        r.put("type", "error_response");
        r.put("request_id", req == null ? 0 : req.getLong("request_id", 0));
        r.put("code", code);
        r.put("message", message == null ? "" : message);
        r.add("detail", Jval.newObject());
        return r;
    }

    private static Jval replicate(Jval value, int count){
        Jval arr = Jval.newArray();
        for(int i = 0; i < count; i++){
            arr.add(Jval.read(value.toString(Jval.Jformat.plain)));
        }
        return arr;
    }

    private static Jval boolArray(int count, boolean value){
        Jval arr = Jval.newArray();
        for(int i = 0; i < count; i++){
            arr.add(value);
        }
        return arr;
    }

    private void writeFrame(Jval msg) throws IOException{
        byte[] body = msg.toString(Jval.Jformat.plain).getBytes(java.nio.charset.StandardCharsets.UTF_8);
        if(body.length > MAX_MESSAGE_SIZE){
            throw new IOException("outbound frame exceeds max size: " + body.length);
        }
        out.writeInt(body.length);
        out.write(body);
        out.flush();
    }

    private void cleanup(){
        stop.set(true);
        stopPathfinders();
        closeQuietly(in);
        closeQuietly(out);
        closeQuietly(client);
        closeQuietly(serverSocket);
    }

    private static void closeQuietly(Closeable c){
        if(c != null){
            try{ c.close(); }catch(IOException ignored){}
        }
    }

    /** Rejection with a protocol error code, mapped to an ErrorResponse. */
    private static final class ProtocolReject extends RuntimeException{
        final String code;
        ProtocolReject(String code, String message){
            super(message);
            this.code = code;
        }
    }
}
