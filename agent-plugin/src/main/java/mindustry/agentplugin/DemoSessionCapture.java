package mindustry.agentplugin;

import agentcore.human.HumanPresence.*;
import arc.util.serialization.*;
import mindustry.rl.*;

import java.io.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** Opt-in, simulation-thread-owned JSONL capture for human demo sessions. */
final class DemoSessionCapture{
    static final int schemaVersion = 3;
    static final String repositoryCommitProperty = "mindustry.agents.demo.repository-commit";
    static final String pluginContentSha256Property = "mindustry.agents.demo.plugin-content-sha256";
    static final String serverContentSha256Property = "mindustry.agents.demo.server-content-sha256";

    private final Path path;
    private final BufferedWriter writer;
    private final MessageDigest digest;
    private long records;
    private long lastTick;
    private boolean closed;
    private String closeReason = "";

    private DemoSessionCapture(Path path, Scenario scenario, long tick){
        String repositoryCommit = requireHexProperty(repositoryCommitProperty, 40);
        String pluginContentSha256 = requireHexProperty(pluginContentSha256Property, 64);
        String serverContentSha256 = requireHexProperty(serverContentSha256Property, 64);
        this.path = path;
        try{
            Path parent = path.getParent();
            if(parent == null || !Files.isDirectory(parent)){
                throw new IllegalArgumentException("demo capture parent directory does not exist: " + path);
            }
            writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            digest = MessageDigest.getInstance("SHA-256");
        }catch(IOException e){
            throw new IllegalArgumentException("cannot create demo capture: " + path, e);
        }catch(NoSuchAlgorithmException e){
            throw new IllegalStateException("SHA-256 unavailable", e);
        }

        Jval start = base("session_start", tick);
        start.put("engine_tag", RlServer.ENGINE_TAG);
        start.put("engine_commit", RlServer.ENGINE_COMMIT);
        start.put("arc_version", RlServer.ARC_VERSION);
        start.put("protocol_version", RlServer.PROTOCOL_VERSION);
        start.put("scenario_id", scenario.id);
        start.put("scenario_version", scenario.version);
        start.put("policy", "public-greedy-candidates-v1");
        start.put("repository_commit", repositoryCommit);
        start.put("agent_plugin_content_sha256", pluginContentSha256);
        start.put("server_content_sha256", serverContentSha256);
        start.put("python_lockfile", "not_applicable_demo_runtime");
        start.put("training_config", "not_applicable_demo_runtime");
        write(start, true);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            //Headless console EOF may request process exit while the simulation
            //thread is finishing its last update. Let that update own the normal
            //close; this hook is only the crash/abrupt-shutdown fallback.
            for(int i = 0; i < 200; i++){
                if(closed()) return;
                try{
                    Thread.sleep(50L);
                }catch(InterruptedException ignored){
                    Thread.currentThread().interrupt();
                    break;
                }
            }
            close(lastTick, "server_shutdown");
        }, "mindustry-demo-capture-close"));
    }

    static DemoSessionCapture open(String configured, Scenario scenario, long tick){
        if(configured == null || configured.isBlank()) return null;
        Path path = Path.of(configured.trim()).toAbsolutePath().normalize();
        return new DemoSessionCapture(path, scenario, tick);
    }

    private static String requireHexProperty(String name, int length){
        String value = System.getProperty(name, "").trim();
        if(value.length() != length){
            throw new IllegalArgumentException("demo capture requires " + name);
        }
        for(int i = 0; i < value.length(); i++){
            char character = value.charAt(i);
            if((character < '0' || character > '9') && (character < 'a' || character > 'f')){
                throw new IllegalArgumentException("demo capture requires lowercase hex " + name);
            }
        }
        return value;
    }

    Path path(){ return path; }

    private synchronized boolean closed(){ return closed; }

    void trajectory(Jval trace){
        Jval record = base("trajectory", trace.getLong("tick", -1L));
        record.add("trajectory", copy(trace));
        write(record, true);
    }

    void control(Jval control){
        Jval record = base("control", control.getLong("tick", -1L));
        record.add("control", copy(control));
        write(record, true);
    }

    void coordination(Jval event, String announcementStatus){
        Jval record = base("coordination", event.getLong("tick", -1L));
        record.put("announcement_status", Objects.requireNonNull(announcementStatus));
        record.add("event", copy(event));
        write(record, true);
    }

    void humanPresence(long tick, Change change){
        Jval record = base("human_presence", tick);
        Jval removed = Jval.newArray();
        for(String id : change.removed()) removed.add(id);
        record.add("removed", removed);
        Jval added = Jval.newArray();
        for(Plan plan : change.added()){
            Jval value = Jval.newObject();
            value.put("id", plan.id());
            Jval area = Jval.newObject();
            area.put("x", plan.area().x());
            area.put("y", plan.area().y());
            area.put("w", plan.area().w());
            area.put("h", plan.area().h());
            value.add("area", area);
            Jval resources = Jval.newObject();
            for(Map.Entry<String, Integer> entry : plan.resources().entrySet()){
                resources.put(entry.getKey(), entry.getValue());
            }
            value.add("resources", resources);
            added.add(value);
        }
        record.add("added", added);
        write(record, true);
    }

    synchronized void close(long tick, String reason){
        if(closed) return;
        closed = true;
        closeReason = reason;
        Jval end = base("session_end", tick);
        end.put("reason", reason == null || reason.isBlank() ? "closed" : reason);
        end.put("records", records);
        end.put("content_sha256", HexFormat.of().formatHex(digest.digest()));
        write(end, false);
        try{
            writer.close();
        }catch(IOException e){
            throw new IllegalStateException("cannot close demo capture: " + path, e);
        }
    }

    private static Jval base(String type, long tick){
        Jval record = Jval.newObject();
        record.put("capture_schema_version", schemaVersion);
        record.put("record_type", type);
        record.put("tick", tick);
        return record;
    }

    private static Jval copy(Jval value){
        return Jval.read(value.toString(Jval.Jformat.plain));
    }

    private synchronized void write(Jval record, boolean hash){
        if(closed && hash){
            throw new IllegalStateException("demo capture is closed (" + closeReason + "): " + path);
        }
        String line = record.toString(Jval.Jformat.plain);
        byte[] bytes = (line + "\n").getBytes(StandardCharsets.UTF_8);
        try{
            writer.write(line);
            writer.write('\n');
            writer.flush();
        }catch(IOException e){
            throw new IllegalStateException("cannot write demo capture: " + path, e);
        }
        if(hash){
            digest.update(bytes);
            records++;
            lastTick = Math.max(lastTick, record.getLong("tick", lastTick));
        }
    }
}
