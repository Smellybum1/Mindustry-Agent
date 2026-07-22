package mindustry.agentplugin;

import arc.*;
import arc.math.*;
import arc.struct.*;
import arc.util.*;
import mindustry.async.*;
import mindustry.core.GameState.*;
import mindustry.game.EventType.*;
import mindustry.gen.*;
import mindustry.maps.*;
import mindustry.mod.*;
import mindustry.net.Administration.*;
import mindustry.rl.*;

import static mindustry.Vars.*;

/** Stock dedicated-server entry point for the private M6 cooperative-agent demo. */
public final class AgentPlugin extends Plugin{
    public static final String modeProperty = "mindustry.agents.demo.mode";
    public static final String portProperty = "mindustry.agents.demo.port";
    public static final String publicPolicyProperty = "mindustry.agents.demo.public-policy";

    private DemoCoordinator coordinator;
    private boolean deterministicProbe;

    @Override
    public void init(){
        Events.on(ServerLoadEvent.class, event -> {
            String mode = System.getProperty(modeProperty, "manual").trim().toLowerCase();
            if(mode.equals("probe") || mode.equals("join") || mode.equals("survival")){
                Core.app.post(() -> startDemo(mode.equals("join"), mode.equals("probe")));
            }else{
                Log.info("[agents] plugin loaded; run 'agents start' or use DEMO_JOIN=1.");
            }
        });
        Events.on(PlayerConnect.class, event -> {
            if(coordinator != null) coordinator.playerJoined(event.player);
        });
        Events.on(GameOverEvent.class, event -> {
            if(System.getProperty(modeProperty, "").equalsIgnoreCase("survival")){
                Log.err("AGENT-DEMO SURVIVAL FAIL core destroyed before tick @", (long)state.tick);
                Core.app.exit();
            }
        });
        Events.run(Trigger.update, () -> {
            if(deterministicProbe && state.isPlaying()) pathfinder.syncUpdate();
            if(coordinator != null) coordinator.update();
        });
    }

    @Override
    public void registerServerCommands(CommandHandler handler){
        handler.register("agents", "<status|start|pause|resume|stop>",
            "Control the cooperative demo agents.", args -> {
                String result = command(args[0]);
                Log.info("@", result);
            });
    }

    @Override
    public void registerClientCommands(CommandHandler handler){
        handler.<mindustry.gen.Player>register("agents", "<status|pause|resume|stop>",
            "Control the cooperative demo agents.", (args, player) -> {
                String result = command(args[0]);
                player.sendMessage("[accent]" + result);
            });
    }

    private String command(String action){
        return switch(action.toLowerCase()){
            case "start" -> {
                if(coordinator == null) startDemo(false, false);
                yield coordinator == null ? "agents failed to start" : coordinator.status();
            }
            case "status" -> coordinator == null ? "agents: no demo world" : coordinator.status();
            case "pause" -> coordinator == null ? "agents: no demo world" : coordinator.pause();
            case "resume" -> coordinator == null ? "agents: no demo world" : coordinator.resume();
            case "stop" -> coordinator == null ? "agents: no demo world" : coordinator.stop();
            default -> "agents: expected status, start, pause, resume, or stop";
        };
    }

    private void startDemo(boolean openServer, boolean probe){
        if(coordinator != null){
            Log.warn("[agents] demo world already active.");
            return;
        }

        if(probe){
            //The parity probe compares exact policy selections with the externally
            //stepped runtime. Pin engine time here so server frame jitter cannot
            //change resource-recovery decisions. Stop wall-clock pathfinder workers
            //before world load and converge the enemy flow field on this simulation
            //thread each tick. Join and survival remain stock real-time.
            Core.graphics = new FixedProbeGraphics();
            deterministicProbe = true;
            mindustry.entities.EntityGroup.enableDeterministicOrder();
            Groups.build.enableDeterministicOrder(building -> -building.pos());
            pathfinder.disableBackgroundThread();
            controlPath.disableBackgroundThread();
            Mathf.rand.setSeed(0L);
        }

        Scenario scenario = new Scenario();
        logic.reset();
        state.rules = scenario.buildRules();
        state.map = demoMap(scenario);
        scenario.load();
        if(deterministicProbe) seedProbePhysics(0L);
        logic.play();
        if(deterministicProbe) pathfinder.syncUpdate();

        coordinator = new DemoCoordinator(scenario, probe, openServer);
        coordinator.spawn();

        if(openServer){
            //Hold the scenario clock as well as the controllers. Otherwise the
            //unattended wave timer can destroy the core while the client loads.
            state.set(State.paused);
            int port = parsePort(System.getProperty(portProperty, "6567"));
            Config.port.set(port);
            netServer.openServer();
            Log.info("[agents] private demo listening on port @; policy waits for the first player.", port);
        }else{
            coordinator.startOpening();
            Log.info("[agents] demo probe started without opening a network port.");
        }
    }

    private static Map demoMap(Scenario scenario){
        StringMap tags = StringMap.of(
            "name", "Bootstrap Defense v0",
            "author", "mindustry-coop-agents",
            "description", "Private cooperative-agent demonstration"
        );
        return new Map(customMapDirectory.child("bootstrap-defense-v0.msav"),
            scenario.width, scenario.height, tags, true);
    }

    private static void seedProbePhysics(long seed){
        try{
            var physicsField = PhysicsProcess.class.getDeclaredField("physics");
            physicsField.setAccessible(true);
            var randomField = PhysicsProcess.PhysicsWorld.class.getDeclaredField("rand");
            randomField.setAccessible(true);
            for(AsyncProcess process : asyncCore.processes){
                if(!(process instanceof PhysicsProcess physics)) continue;
                Object physicsWorld = physicsField.get(physics);
                if(physicsWorld == null){
                    throw new IllegalStateException("probe physics world is absent");
                }
                ((Rand)randomField.get(physicsWorld)).setSeed(seed ^ 0x4d38504859534cL);
                return;
            }
            throw new IllegalStateException("probe async physics process is absent");
        }catch(ReflectiveOperationException e){
            throw new IllegalStateException("probe physics layout changed", e);
        }
    }

    private static int parsePort(String value){
        try{
            int parsed = Integer.parseInt(value);
            if(parsed < 1 || parsed > 65535) throw new NumberFormatException();
            return parsed;
        }catch(NumberFormatException e){
            throw new IllegalArgumentException("invalid demo port: " + value);
        }
    }
}
