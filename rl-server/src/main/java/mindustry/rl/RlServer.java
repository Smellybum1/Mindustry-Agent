package mindustry.rl;

import agentcore.candidates.*;
import agentcore.skill.*;
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
import mindustry.entities.units.*;
import mindustry.world.blocks.defense.turrets.Turret.*;

import java.io.*;
import java.net.*;
import java.lang.reflect.*;
import java.util.*;
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
    //constructed in boot() after content.init() — the loader resolves Mindustry content ids.
    private Scenario scenario;
    private AdaptiveWorldFacts adaptiveFacts;
    private EngineCandidates engineCandidates;
    private CoordinationAdapter coordination;
    private final FixedStepApplication app;
    private final RlAgentRegistry registry = new RlAgentRegistry();

    private final BlockingQueue<Jval> requests = new LinkedBlockingQueue<>();
    private ServerSocket serverSocket;
    private Socket client;
    private DataInputStream in;
    private DataOutputStream out;

    //episode state (simulation thread only)
    private String episodeId;
    private long rootSeed;
    private long resetCounter;
    private int agentCount = 1;
    private long uptimeTicks;
    private int nextScenarioEvent;
    private final AtomicBoolean stop = new AtomicBoolean(false);
    private Jval stepGameEvents = Jval.newArray();
    private CandidateSet[] boundaryCandidates = new CandidateSet[0];

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

        //content is now loaded: parse the scenario spec (resolves block/unit/item ids)
        selectScenario("bootstrap-defense-v0");

        //Captured only while the simulation thread advances an external step.
        Events.on(UnitDamageEvent.class, this::recordUnitDamage);

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
        Jval features = Jval.newArray();
        features.add("task_candidates");
        features.add("task_actions");
        features.add("task_board");
        r.add("supported_features", features);
        r.put("process_id", ProcessHandle.current().pid());
        return r;
    }

    private Jval reset(Jval req){
        long requestId = req.getLong("request_id", 0);
        rootSeed = req.getLong("root_seed", 0);
        agentCount = Math.max(1, req.getInt("agent_count", 1));
        String requestedScenario = req.getString("scenario_id", "bootstrap-defense-v0");
        if(!Scenario.supports(requestedScenario)){
            throw new ProtocolReject("unknown_scenario", "unknown scenario_id: " + requestedScenario);
        }
        if(!scenario.id.equals(requestedScenario)) selectScenario(requestedScenario);
        Jval options = req.get("options");
        engineCandidates.setOverlapProbe(options != null && options.isObject()
            && options.getBool("reservation_overlap_probe", false));
        coordination.setSharedExpertEnabled(options != null && options.isObject()
            && options.getBool("shared_expert_policy", false));
        coordination.setSharedExpertBlockedVariant(options != null && options.isObject()
            && options.getBool("shared_expert_blocked_variant", false));

        doReset(rootSeed);
        if(options != null && options.isObject()){
            coordination.configureFailureInjection(
                options.getInt("lease_failure_agent_id", -1),
                options.getLong("lease_failure_tick", -1));
        }
        stepGameEvents = Jval.newArray();

        resetCounter++;
        episodeId = "ep-" + rootSeed + "-" + resetCounter;
        uptimeTicks = 0;

        Jval r = Jval.newObject();
        r.put("type", "reset_response");
        r.put("request_id", requestId);
        r.put("episode_id", episodeId);
        r.put("tick", (long)state.tick);
        r.add("initial_observations", agentObservations());
        r.add("action_masks", candidateMasks());
        r.put("state_hash", StateHasher.hash(registry, coordination.board(),
            adaptiveState()));
        r.put("outcome", "running");
        r.add("metadata", scenario.metadata());
        return r;
    }

    private Jval step(Jval req){
        long requestId = req.getLong("request_id", 0);
        String reqEpisode = req.getString("episode_id", "");
        int expectedTick = req.getInt("expected_tick", -1);
        int ticks = req.getInt("ticks_to_advance", 0);
        boolean stopOnDecisionEvent = req.getBool("stop_on_decision_event", false);

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
        stepGameEvents = Jval.newArray();

        //M3 (D5): decode + apply the per-agent action bundle on the sim thread BEFORE
        //advancing; invalid actions are rejected into action_results, never crash.
        coordination.tick((long)state.tick);
        Jval actionResults = applyActions(req);
        long decisionRevision = coordination.decisionRevision();
        int previousEnemies = waveEnemyCount();
        float previousCoreHealth = coreHealth();
        LinkedHashSet<String> decisionReasons = new LinkedHashSet<>();

        long t0 = System.nanoTime();
        app.graphics.setDeltaSeconds(1f / 60f);
        int advancedTicks = 0;
        for(int i = 0; i < ticks; i++){
            app.stepOnce();
            //deterministic enemy flowfield: converge on the sim thread each tick with the
            //background Pathfinder thread stopped (upstream syncUpdate patch, docs/UPSTREAM_PATCHES.md).
            pathfinder.syncUpdate();
            int scenarioGrant = applyScenarioEvents((int)state.tick);
            adaptiveFacts.recordTick(scenarioGrant);
            coordination.recordMetricsTick();
            coordination.tick((long)state.tick);
            advancedTicks++;

            if(coordination.decisionRevision() != decisionRevision){
                decisionReasons.add(coordination.lastDecisionReason());
                decisionRevision = coordination.decisionRevision();
            }
            int enemies = waveEnemyCount();
            if(previousEnemies == 0 && enemies > 0) decisionReasons.add("wave_spawn");
            if(previousEnemies > 0 && enemies == 0) decisionReasons.add("wave_clear");
            previousEnemies = enemies;
            float coreHealth = coreHealth();
            if(coreHealth + 1e-4f < previousCoreHealth) decisionReasons.add("core_damage");
            previousCoreHealth = coreHealth;
            if(stopOnDecisionEvent && !decisionReasons.isEmpty()) break;
        }
        long t1 = System.nanoTime();
        uptimeTicks += advancedTicks;

        long o0 = System.nanoTime();
        Jval obs = agentObservations();
        String hash = StateHasher.hash(registry, coordination.board(), adaptiveState());
        long o1 = System.nanoTime();

        //termination: win = core alive at winTick; loss = core destroyed; truncate at tick cap.
        Building core = scenario.coreTeam.core();
        boolean coreAlive = core != null && core.health > 0f && !state.gameOver;
        int nowTick = (int)state.tick;
        boolean terminated = false, truncated = false;
        String outcome = "running";
        if(!coreAlive){
            outcome = "loss";
            terminated = true;
        }else if(nowTick >= scenario.winTick){
            outcome = "win";
            terminated = true;
        }else if(nowTick >= scenario.tickCap){
            outcome = "truncated";
            truncated = true;
        }

        Jval timing = Jval.newObject();
        timing.put("engine_ms", (t1 - t0) / 1e6);
        timing.put("observation_ms", (o1 - o0) / 1e6);
        timing.put("serialization_ms", 0.0);
        timing.put("io_ms", 0.0);
        Jval taskEvents = coordination.drainEvents();

        Jval r = Jval.newObject();
        r.put("type", "step_response");
        r.put("request_id", requestId);
        r.put("episode_id", episodeId);
        r.put("previous_tick", previousTick);
        r.put("tick", (long)state.tick);
        r.add("observations", obs);
        r.add("action_masks", candidateMasks());
        r.add("action_results", actionResults);
        r.add("team_state", teamState());
        r.add("reward_breakdowns", replicate(Jval.newObject(), agentCount));
        r.add("terminations", boolArray(agentCount, terminated));
        r.add("truncations", boolArray(agentCount, truncated));
        r.put("outcome", outcome);
        r.add("task_events", taskEvents);
        r.add("task_board", coordination.boardSnapshot());
        r.add("coordination_metrics", coordination.metrics());
        r.add("game_events", stepGameEvents);
        Jval boundary = Jval.newObject();
        boundary.put("requested_ticks", ticks);
        boundary.put("advanced_ticks", advancedTicks);
        boundary.put("triggered", !decisionReasons.isEmpty());
        Jval reasons = Jval.newArray();
        for(String reason : decisionReasons) reasons.add(reason);
        boundary.add("reasons", reasons);
        r.add("decision_boundary", boundary);
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

        //deterministic mode: stop the free-running wall-clock pathfinder threads. Our agent
        //units steer straight (SkillController, no ControlPathfinder); enemy ground units use
        //the flow-field Pathfinder, which is preloaded synchronously at world load and then
        //driven per tick via pathfinder.syncUpdate() (§5.5, §11.6, D2, docs/UPSTREAM_PATCHES.md).
        stopPathfinders();

        //M3 (D1): rebuild the agent registry after play() so the core exists; spawns
        //agent_count alpha units at deterministic offsets and installs SkillControllers
        registry.rebuild(agentCount);
        coordination.reset(rootSeed, agentCount);
        adaptiveFacts.reset();
        nextScenarioEvent = 0;

        //converge the preloaded enemy flow field once so the first observation is settled
        pathfinder.syncUpdate();
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

    // ------------------------------------------------------------ actions

    /** Decode + apply the {@code agent_actions} bundle, returning {@code action_results[]}. */
    private Jval applyActions(Jval req){
        return coordination.applyActions(req.get("agent_actions"), boundaryCandidates);
    }

    // ------------------------------------------------------------ observation

    /** Per-agent observations in dense index order (docs/M3_DESIGN.md D6). */
    private Jval agentObservations(){
        Jval arr = Jval.newArray();
        Jval world = worldObs();
        CandidateWorldSnapshot candidateWorld = engineCandidates.snapshot();
        boundaryCandidates = new CandidateSet[agentCount];
        for(RlAgentRegistry.Agent agent : registry.agents()){
            CandidateSet candidates = engineCandidates.generate(agent, candidateWorld);
            boundaryCandidates[agent.index] = candidates;
            Jval o = Jval.newObject();
            o.put("agent_id", agent.index);
            o.add("unit", unitObs(agent));
            o.add("skill", skillObs(agent));
            o.add("team", Jval.read(world.toString(Jval.Jformat.plain)));
            o.add("task_candidates", engineCandidates.observation(candidates));
            arr.add(o);
        }
        //fallback: if there are no agents (agent_count 0), still emit the world view
        if(arr.asArray().isEmpty()){
            for(int i = 0; i < agentCount; i++){
                arr.add(Jval.read(world.toString(Jval.Jformat.plain)));
            }
        }
        return arr;
    }

    private Jval candidateMasks(){
        Jval out = Jval.newArray();
        for(int i = 0; i < agentCount; i++){
            Jval agentMask = Jval.newObject();
            CandidateSet candidates = i < boundaryCandidates.length ? boundaryCandidates[i] : null;
            if(candidates == null){
                agentMask.add("candidate_task", Jval.newArray());
                out.add(agentMask);
            }else{
                out.add(coordination.actionMask(i, candidates));
            }
        }
        return out;
    }

    private Jval unitObs(RlAgentRegistry.Agent agent){
        Unit u = agent.unit;
        Itemsc it = (Itemsc)u;
        Minerc mn = (Minerc)u;
        Jval o = Jval.newObject();
        o.put("x", u.x);
        o.put("y", u.y);
        o.put("vx", u.vel().x);
        o.put("vy", u.vel().y);
        o.put("health", u.health);
        o.put("item", it.item() == null ? "" : it.item().name);
        o.put("item_amount", it.stack().amount);
        o.put("mining", mn.mining());
        o.put("flag", u.flag);
        o.put("dead", u.dead());
        o.put("build_queue_depth", u.plans().size);
        BuildPlan plan = u.plans().isEmpty() ? null : u.plans().first();
        o.put("build_plan_progress", plan == null ? 0f : plan.progress);
        if(plan != null){
            Jval current = Jval.newObject();
            current.put("breaking", plan.breaking);
            current.put("block", plan.block == null ? "" : plan.block.name);
            current.put("tile_x", plan.x);
            current.put("tile_y", plan.y);
            current.put("rotation", plan.rotation);
            current.put("progress", plan.progress);
            o.add("build_plan", current);
        }
        return o;
    }

    private Jval skillObs(RlAgentRegistry.Agent agent){
        SkillController sc = agent.controller;
        SkillResult r = sc.lastResult();
        Jval o = Jval.newObject();
        o.put("type", sc.activeType());
        o.put("status", r.status().name());
        o.put("reason", r.reason().name());
        o.put("progress", r.progress());
        o.put("next_retry_tick", r.nextRetryTick());
        if(sc.activeSkill() instanceof SupplyBuilding supply){
            o.put("requested", supply.requested());
            o.put("delivered", supply.delivered());
            o.put("target_stock_before", supply.targetStockBefore());
            o.put("target_stock", supply.targetStock());
        }
        if(sc.activeSkill() instanceof RebuildRegion rebuild){
            o.put("initial_broken", rebuild.initialCount());
            o.put("completed", rebuild.completed());
        }
        if(sc.activeSkill() instanceof DefendRegion defend){
            o.put("target_id", defend.targetId());
            o.put("duration_ticks", defend.durationTicks());
            o.put("elapsed_ticks", defend.elapsed((long)state.tick));
        }
        return o;
    }

    private Jval worldObs(){
        Building core = scenario.coreTeam.core();
        EconomySnapshot economy = adaptiveFacts.economy();
        DefenseReadinessSnapshot defense = adaptiveFacts.defense();
        Jval o = Jval.newObject();
        o.put("tick", (long)state.tick);
        o.put("wave", state.wave);
        o.put("copper", StateHasher.coreItem(Items.copper));
        o.put("lead", StateHasher.coreItem(Items.lead));
        o.put("unit_count", Groups.unit.size());
        o.put("building_count", Groups.build.size());
        o.put("broken_block_count", brokenBlockCount());
        o.put("core_health", core == null ? 0.0 : core.health);
        //wave/enemy telemetry (scenario phase): time to the next spawn and live enemy summary.
        o.put("time_to_next_wave", state.wavetime);
        o.put("enemy_count", state.enemies);
        o.put("enemy_total_health", enemyTotalHealth());
        o.put("enemy_nearest_core_dist", enemyNearestCoreDist(core));
        o.put("line_blocks_complete", economy.blocksComplete());
        o.put("line_conveyor_connected", economy.conveyorConnected());
        o.put("core_copper_inflow_per_s", economy.coreInflowPerSecond());
        o.put("core_copper_inflow_target_per_s", economy.requiredInflowPerSecond());
        o.put("line_operational", economy.operational());
        o.put("next_wave_expected_enemies", defense.expectedEnemies());
        o.put("next_wave_required_ammo", defense.requiredAmmo());
        o.put("target_ammo_per_turret", defense.targetAmmoPerTurret());
        o.put("defense_ammo_coverage", defense.ammoCoverage());
        o.put("defense_health_coverage", defense.healthCoverage());
        o.put("defense_turret_coverage", defense.turretCoverage());
        o.put("defense_readiness", defense.readiness());
        o.put("defend_lead_ticks", defense.defendLeadTicks());
        o.put("wave_imminence", defense.waveImminence());
        o.add("turrets", turretSummary());
        o.put("done", state.gameOver);
        return o;
    }

    private int brokenBlockCount(){
        int count = 0;
        var plans = scenario.coreTeam.data().plans;
        for(int i = 0; i < plans.size; i++){
            if(!plans.get(i).removed) count++;
        }
        return count;
    }

    /** Smallest distance (world units) from any wave-team unit to the core, or -1 if none. */
    private double enemyNearestCoreDist(Building core){
        if(core == null) return -1.0;
        float best = Float.MAX_VALUE;
        for(Unit u : Groups.unit){
            if(u.team() == scenario.waveTeam){
                float d = u.dst(core.x, core.y);
                if(d < best) best = d;
            }
        }
        return best == Float.MAX_VALUE ? -1.0 : best;
    }

    private double enemyTotalHealth(){
        double total = 0.0;
        for(Unit u : Groups.unit){
            if(u.team() == scenario.waveTeam && !u.dead()) total += u.health;
        }
        return total;
    }

    private Jval turretSummary(){
        arc.struct.Seq<Building> turrets = new arc.struct.Seq<>();
        for(Building building : Groups.build){
            if(building.team == scenario.coreTeam && building instanceof TurretBuild){
                turrets.add(building);
            }
        }
        turrets.sort(java.util.Comparator.comparingInt(Building::id));

        Jval out = Jval.newArray();
        for(Building building : turrets){
            TurretBuild turret = (TurretBuild)building;
            Jval item = Jval.newObject();
            item.put("id", building.id);
            item.put("block", building.block.name);
            item.put("tile_x", building.tileX());
            item.put("tile_y", building.tileY());
            item.put("total_ammo", turret.totalAmmo);
            out.add(item);
        }
        return out;
    }

    private void recordUnitDamage(UnitDamageEvent event){
        if(event.unit == null || event.bullet == null) return;
        Jval out = Jval.newObject();
        out.put("type", "unit_damage");
        out.put("tick", (long)state.tick);
        out.put("target_unit_id", event.unit.id);
        out.put("target_health", event.unit.health);
        out.put("target_shield", event.unit.shield);
        out.put("target_team", event.unit.team.name);
        out.put("nominal_damage", event.bullet.damage);

        int sourceUnitId = -1;
        int sourceAgentId = -1;
        if(event.bullet.owner instanceof Unit source){
            sourceUnitId = source.id;
            for(RlAgentRegistry.Agent agent : registry.agents()){
                if(agent.unit == source){
                    sourceAgentId = agent.index;
                    break;
                }
            }
        }
        out.put("source_unit_id", sourceUnitId);
        out.put("agent_id", sourceAgentId);
        stepGameEvents.add(out);
    }

    private Jval teamState(){
        Jval t = Jval.newObject();
        t.put("team", "sharded");
        t.put("cores", Team.sharded.cores().size);
        t.put("copper", StateHasher.coreItem(Items.copper));
        t.put("lead", StateHasher.coreItem(Items.lead));
        return t;
    }

    private void selectScenario(String id){
        scenario = new Scenario(id);
        adaptiveFacts = new AdaptiveWorldFacts(scenario, registry);
        engineCandidates = new EngineCandidates(scenario, registry, adaptiveFacts);
        coordination = new CoordinationAdapter(scenario, registry, adaptiveFacts);
        engineCandidates.setCoordination(coordination);
    }

    private int applyScenarioEvents(int tick){
        int grantedCopper = 0;
        while(nextScenarioEvent < scenario.scheduledEvents.size()
            && scenario.scheduledEvents.get(nextScenarioEvent).tick() <= tick){
            Scenario.ScheduledEvent event = scenario.scheduledEvents.get(nextScenarioEvent++);
            Building core = scenario.coreTeam.core();
            if(core != null){
                core.items.add(event.item(), event.amount());
                if(event.item() == Items.copper) grantedCopper += event.amount();
            }
            Jval out = Jval.newObject();
            out.put("type", "scenario_event");
            out.put("event_type", event.type());
            out.put("tick", tick);
            out.put("item", event.item().name);
            out.put("amount", event.amount());
            out.put("reason", event.reason());
            stepGameEvents.add(out);
        }
        return grantedCopper;
    }

    private int waveEnemyCount(){
        int count = 0;
        for(Unit unit : Groups.unit){
            if(unit.team == scenario.waveTeam && !unit.dead()) count++;
        }
        return count;
    }

    private float coreHealth(){
        Building core = scenario.coreTeam.core();
        return core == null ? 0f : core.health;
    }

    private byte[] adaptiveState(){
        try{
            byte[] facts = adaptiveFacts.canonicalState();
            byte[] coordinationState = coordination.canonicalAdaptiveState();
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            out.writeInt(facts.length);
            out.write(facts);
            out.writeInt(coordinationState.length);
            out.write(coordinationState);
            out.writeInt(nextScenarioEvent);
            out.flush();
            return bytes.toByteArray();
        }catch(IOException impossible){
            throw new AssertionError(impossible);
        }
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
