package mindustry.agentplugin;

import agentcore.announce.*;
import agentcore.coordination.*;
import agentcore.event.*;
import agentcore.human.*;
import agentcore.human.HumanControl.*;
import agentcore.human.HumanPresence.*;
import agentcore.skill.*;
import agentcore.task.*;
import arc.*;
import arc.struct.*;
import arc.util.*;
import arc.util.serialization.*;
import mindustry.content.*;
import mindustry.core.GameState.*;
import mindustry.entities.*;
import mindustry.entities.units.*;
import mindustry.game.EventType.*;
import mindustry.gen.*;
import mindustry.rl.*;

import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

import static mindustry.Vars.*;

/** Real-time pacing, I/O, and engine binding for the shared coordination driver. */
final class DemoCoordinator{
    private final Scenario scenario;
    private final boolean probe;
    private final boolean waitForPlayer;
    private final boolean survivalProbe;
    private final boolean humanProbe;
    private final boolean publicPolicy;
    private final AnnouncementRenderer renderer = new AnnouncementRenderer();
    private final HumanControl.State humanControl = new HumanControl.State();
    private final HumanControl.CommandQueue humanCommands = new HumanControl.CommandQueue();
    private final HumanPresence.Tracker humanPresence = new HumanPresence.Tracker();
    private final Set<String> humanRegions;
    private final Object humanCommandLock = new Object();
    private final ConcurrentHashMap<Long, Consumer<String>> humanResponses =
        new ConcurrentHashMap<>();
    private volatile Snapshot publishedHumanControl = new Snapshot(List.of(), List.of(),
        AutonomyLevel.NORMAL, false, 0L);
    private final DemoAgentRegistry registry;
    private final ExpertCoordinationDriver driver;
    private final PublicCandidateDemo publicDemo;

    private boolean paused;
    private boolean stopped;
    private boolean probeReported;
    private boolean survivalReported;
    private int announcements;
    private int suppressedAnnouncements;
    private int humanProbePhase;
    private boolean lowAutonomyObserved;
    private boolean highAutonomyObserved;
    private int humanYieldNotices;
    private BuildPlan probeHumanPlan;
    private Plan probePresence;
    private long probeRecentExpiry = -1L;

    DemoCoordinator(Scenario scenario, boolean probe, boolean waitForPlayer){
        this.scenario = scenario;
        this.probe = probe;
        this.waitForPlayer = waitForPlayer;
        this.survivalProbe = System.getProperty(AgentPlugin.modeProperty, "")
            .equalsIgnoreCase("survival");
        this.humanProbe = System.getProperty(AgentPlugin.modeProperty, "")
            .equalsIgnoreCase("human");
        this.publicPolicy = publicPolicyEnabled();
        this.humanRegions = humanRegions(scenario);
        this.registry = new DemoAgentRegistry(scenario);
        this.driver = new ExpertCoordinationDriver(
            ExpertCoordinationPlans.fromScenario(scenario), new DemoPort());
        this.publicDemo = new PublicCandidateDemo(scenario, registry, humanControl,
            probe && !humanProbe);
        driver.reset(1L);
    }

    void spawn(){
        registry.spawn();
        Log.info("[agents] spawned @ controlled alpha units.", registry.size());
    }

    void playerJoined(Player player){
        if(player.team() != scenario.coreTeam) return;
        if(waitForPlayer && !driver.started() && !stopped){
            player.sendMessage("[accent]Cooperative agents ready. Type /agents resume when you are ready to watch.");
        }else{
            player.sendMessage("[accent]Cooperative agents active. /agents status|goal|cancel|assign|release|autonomy|quiet|pause|resume|stop");
        }
    }

    void startOpening(){
        if(started() || stopped) return;
        if(publicPolicy){
            publicDemo.start();
            drainPublicTraces();
            drainPublicAnnouncements();
        }else{
            driver.startOpening((long)state.tick);
            drainAnnouncements();
        }
    }

    void update(){
        driveHumanProbe();
        drainHumanCommands();
        if(publicPolicy && started()) syncHumanPresence();
        if(!started() || paused || stopped || !state.isPlaying()) return;
        long tick = (long)state.tick;
        if(publicPolicy){
            publicDemo.update();
            drainPublicSignals();
            drainPublicTraces();
            drainPublicAnnouncements();
            if(survivalProbe && !survivalReported && tick >= scenario.winTick){
                Building core = scenario.coreTeam.core();
                if(core == null || core.health <= 0f){
                    throw new IllegalStateException("demo core did not survive to win tick");
                }
                survivalReported = true;
                Log.info("AGENT-DEMO SURVIVAL OK tick=@ core_health=@", tick, Math.round(core.health));
                Core.app.exit();
                return;
            }
            finishProbeIfReady();
            return;
        }
        int enemies = 0;
        for(Unit unit : Groups.unit){
            if(unit.team == scenario.waveTeam && !unit.dead()) enemies++;
        }
        Building core = scenario.coreTeam.core();
        int coreHealth = core == null ? 0 : Math.round(core.health);
        driver.update(tick, enemies, coreHealth);
        drainSignals();
        drainAnnouncements();

        if(survivalProbe && !survivalReported && tick >= scenario.winTick){
            core = scenario.coreTeam.core();
            if(core == null || core.health <= 0f){
                throw new IllegalStateException("demo core did not survive to win tick");
            }
            survivalReported = true;
            Log.info("AGENT-DEMO SURVIVAL OK tick=@ core_health=@", tick, Math.round(core.health));
            Core.app.exit();
            return;
        }
        finishProbeIfReady();
    }

    String pause(){
        if(stopped) return "agents: stopped";
        paused = true;
        for(DemoAgentRegistry.Agent agent : registry.agents()) agent.controller().pauseNow();
        return "agents: paused at tick " + (long)state.tick;
    }

    String resume(){
        if(stopped) return "agents: stopped (start a new demo world to resume)";
        if(!started()){
            startOpening();
            if(waitForPlayer && state.isPaused()){
                state.set(mindustry.core.GameState.State.playing);
            }
        }
        paused = false;
        for(DemoAgentRegistry.Agent agent : registry.agents()) agent.controller().resumeNow();
        return "agents: running at tick " + (long)state.tick;
    }

    String stop(){
        if(stopped) return "agents: already stopped";
        stopped = true;
        paused = false;
        long tick = (long)state.tick;
        if(publicPolicy) publicDemo.stop("human_emergency_stop");
        else driver.stop(tick, "human_emergency_stop");
        for(DemoAgentRegistry.Agent agent : registry.agents()) agent.controller().stopNow();
        if(publicPolicy) drainPublicAnnouncements();
        else drainAnnouncements();
        return "agents: emergency stop complete at tick " + tick;
    }

    String status(){
        String mode = stopped ? "stopped" : paused ? "paused"
            : started() ? "running" : "waiting";
        int active = 0;
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            if(agent.controller().activeSkill() != null) active++;
        }
        Snapshot controls = publishedHumanControl;
        return "agents: " + mode + " tick=" + (long)state.tick + " active=" + active
            + "/" + registry.size() + " tasks=" + taskCount()
            + " announcements=" + announcements + " suppressed=" + suppressedAnnouncements
            + " phase=" + phase()
            + " human_goals=" + controls.activeGoals().size()
            + " autonomy=" + controls.autonomy().name().toLowerCase(Locale.ROOT)
            + " quiet=" + controls.quiet();
    }

    String queueHumanCommand(String[] tokens, String authorId, Consumer<String> response){
        if(!publicPolicy) return "agents: command rejected reason=public_policy_required";
        if(stopped) return "agents: command rejected reason=stopped";
        EnqueueResult queued;
        synchronized(humanCommandLock){
            queued = humanCommands.enqueue(tokens, authorId);
            if(queued.accepted() && response != null){
                humanResponses.put(queued.sequence(), response);
            }
        }
        return HumanControl.renderQueued(queued);
    }

    private void drainHumanCommands(){
        List<AppliedCommand> applied;
        synchronized(humanCommandLock){
            applied = humanCommands.drain(humanControl, (long)state.tick,
                new Context(humanRegions, registry.size()));
        }
        if(!applied.isEmpty()) publishedHumanControl = humanControl.snapshot();
        for(AppliedCommand result : applied){
            Event event = result.event();
            if(publicPolicy) publicDemo.controlApplied(event);
            Jval structured = controlEvent(result.sequence(), event);
            Log.info("AGENT-DEMO HUMAN CONTROL @", structured.toString(Jval.Jformat.plain));
            Consumer<String> response = humanResponses.remove(result.sequence());
            if(response != null){
                try{
                    response.accept(HumanControl.render(event));
                }catch(RuntimeException e){
                    Log.warn("[agents] command response delivery failed: @", e.getMessage());
                }
            }
        }
    }

    private static Jval controlEvent(long sequence, Event event){
        Jval out = Jval.newObject();
        out.put("sequence", sequence);
        out.put("tick", event.tick());
        out.put("author_id", event.command().authorId());
        out.put("command", event.command().type().name());
        out.put("accepted", event.accepted());
        out.put("reason", event.reason());
        out.put("revision", event.revision());
        out.put("goal_id", event.goalId());
        out.put("agent_index", event.agentIndex());
        return out;
    }

    private void drainSignals(){
        for(ExpertCoordinationDriver.Signal signal : driver.drainSignals()){
            switch(signal.type()){
                case EXPERT_READY -> Log.info(
                    "AGENT-DEMO EXPERT READY tick=@ fortifications=@ turrets=@",
                    signal.tick(), signal.blocks(), signal.turrets());
                case RESERVE_MINING -> Log.info(
                    "AGENT-DEMO RESERVE MINING tick=@ reason=shared_policy", signal.tick());
                case WAVE_START -> Log.info(
                    "AGENT-DEMO WAVE START tick=@ enemies=@ core_health=@",
                    signal.tick(), signal.enemies(), signal.coreHealth());
                case WAVE_CLEAR -> Log.info(
                    "AGENT-DEMO WAVE CLEAR tick=@ wave=@ core_health=@",
                    signal.tick(), signal.wave(), signal.coreHealth());
                case EXPANSION_START -> Log.info(
                    "AGENT-DEMO EXPANSION START wave=@ planned_blocks=@ planned_turrets=@",
                    signal.wave(), signal.blocks(), signal.turrets());
                case EXPANSION_COMPLETE -> Log.info(
                    "AGENT-DEMO EXPANSION COMPLETE wave=@ turrets=@ blocks=@",
                    signal.wave(), signal.turrets(), signal.blocks());
                case EXPANSION_INCOMPLETE -> Log.warn(
                    "AGENT-DEMO EXPANSION INCOMPLETE wave=@ turrets=@",
                    signal.wave(), signal.turrets());
                case MAINTENANCE_DEADLINE -> Log.warn(
                    "AGENT-DEMO MAINTENANCE DEADLINE tick=@; resuming defense safely",
                    signal.tick());
                case EXPANSION_DEADLINE -> Log.warn(
                    "AGENT-DEMO EXPANSION DEADLINE tick=@ wave=@; supplying completed turrets",
                    signal.tick(), signal.wave());
                case SUPPLY_DEADLINE -> Log.warn(
                    "AGENT-DEMO SUPPLY DEADLINE tick=@; resuming defense safely", signal.tick());
                case MAINTENANCE_COMPLETE -> Log.info(
                    "AGENT-DEMO MAINTENANCE COMPLETE tick=@ wave=@",
                    signal.tick(), signal.wave());
            }
        }
    }

    private void drainAnnouncements(){
        for(CoordinationEvent event : driver.board().events().drain()){
            if(!event.announce()) continue;
            String line = renderer.render(event);
            announcements++;
            Log.info("AGENT-DEMO CHAT @", line);
            for(Player player : Groups.player){
                if(player.team() == scenario.coreTeam) player.sendMessage("[accent]" + line);
            }
        }
    }

    private void drainPublicAnnouncements(){
        for(Jval event : publicDemo.drainEvents().asArray()){
            if(event.getBool("announce", false)
                || event.getString("task_id", "").startsWith("human:goal:")){
                Log.info("AGENT-DEMO COORDINATION @", event.toString(Jval.Jformat.plain));
            }
            if(!event.getBool("announce", false)) continue;
            if(event.getString("reason_code", "").equals("yield_to_human")){
                humanYieldNotices++;
            }
            if(!HumanControl.shouldRenderCoordination(humanControl.snapshot().quiet(),
                event.getString("act", ""), event.getString("reason_code", ""))){
                suppressedAnnouncements++;
                Log.info("AGENT-DEMO CHAT SUPPRESSED message_id=@ reason=quiet",
                    event.getString("message_id", ""));
                continue;
            }
            String line = event.getString("announcement", "");
            if(line.isBlank()) continue;
            announcements++;
            Log.info("AGENT-DEMO CHAT @", line);
            for(Player player : Groups.player){
                if(player.team() == scenario.coreTeam) player.sendMessage("[accent]" + line);
            }
        }
    }

    private void drainPublicSignals(){
        for(PublicCandidateDemo.GoalAvailability availability
            : publicDemo.drainGoalAvailability()){
            Log.info("AGENT-DEMO HUMAN GOAL tick=@ goal=@ reason=@",
                availability.tick(), availability.goalId(), availability.reason());
        }
        for(PublicCandidateDemo.Signal signal : publicDemo.drainSignals()){
            switch(signal.type()){
                case RESERVE_MINING -> Log.info(
                    "AGENT-DEMO RESERVE MINING tick=@ reason=public_policy", signal.tick());
                case WAVE_START -> Log.info(
                    "AGENT-DEMO WAVE START tick=@ enemies=@ core_health=@",
                    signal.tick(), signal.enemies(), signal.coreHealth());
                case WAVE_CLEAR -> Log.info(
                    "AGENT-DEMO WAVE CLEAR tick=@ wave=@ core_health=@",
                    signal.tick(), signal.wave(), signal.coreHealth());
                case EXPANSION_COMPLETE -> Log.info(
                    "AGENT-DEMO EXPANSION COMPLETE wave=@ turrets=@ blocks=@",
                    signal.wave(), signal.turrets(), signal.blocks());
                case MAINTENANCE_COMPLETE -> Log.info(
                    "AGENT-DEMO MAINTENANCE COMPLETE tick=@ wave=@",
                    signal.tick(), signal.wave());
            }
        }
    }

    private void drainPublicTraces(){
        for(Jval trace : publicDemo.drainTraces()){
            Log.info("AGENT-DEMO PUBLIC TRACE @", trace.toString(Jval.Jformat.plain));
        }
    }

    private void finishProbeIfReady(){
        if(humanProbe) return;
        if(publicPolicy){
            finishPublicProbeIfReady();
            return;
        }
        if(!probe || probeReported || !driver.preparationComplete()) return;

        List<String> expectedLine = blockNames(scenario.schematic(scenario.buildLineId));
        List<String> expectedDefense = blockNames(scenario.schematic(scenario.referenceSchematicId));
        if(!driver.lineOrder().equals(expectedLine) || !driver.defenseOrder().equals(expectedDefense)){
            throw new IllegalStateException("demo opening order drift: line=" + driver.lineOrder()
                + " defense=" + driver.defenseOrder());
        }
        for(TileTarget target : driver.activeTurrets()){
            Building building = world.build(target.x(), target.y());
            if(building == null || building.block != Blocks.duo){
                throw new IllegalStateException("expert turret missing at " + target.describe());
            }
        }
        if(!status().contains("phase=reserve-mining")){
            throw new IllegalStateException("agents did not enter productive reserve mining");
        }
        probeReported = true;
        Log.info("AGENT-DEMO DECISION DIGEST digest=@ selections=@",
            driver.selectionDigest(), driver.selectionCount());
        Log.info("AGENT-DEMO PARITY OK decisions=@ line=@ defense=@",
            driver.decisions().size(), String.join(",", driver.lineOrder()),
            String.join(",", driver.defenseOrder()));
        pause();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            if(agent.controller().enabled() || !agent.unit().vel.isZero()){
                throw new IllegalStateException("pause did not halt agent " + agent.index());
            }
        }
        resume();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            if(!agent.controller().enabled()){
                throw new IllegalStateException("resume did not enable agent " + agent.index());
            }
        }
        stop();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            if(agent.controller().enabled() || agent.controller().activeSkill() != null){
                throw new IllegalStateException("stop did not cancel agent " + agent.index());
            }
        }
        Log.info("AGENT-DEMO CONTROLS OK pause/resume/stop halted all three agents");
        Log.info("AGENT-DEMO PROBE OK tick=@ announcements=@", (long)state.tick, announcements);
        Core.app.exit();
    }

    private void finishPublicProbeIfReady(){
        if(!probe || probeReported || !publicDemo.preparationComplete()) return;
        requireSchematic(scenario.schematic(scenario.buildLineId),
            scenario.buildLineAnchorX, scenario.buildLineAnchorY);
        requireSchematic(scenario.schematic(scenario.referenceSchematicId),
            scenario.referenceAnchorX, scenario.referenceAnchorY);

        probeReported = true;
        Log.info("AGENT-DEMO EXPERT READY tick=@ public_candidates=true", (long)state.tick);
        Log.info("AGENT-DEMO DECISION DIGEST digest=@ selections=@",
            publicDemo.selectionDigest(), publicDemo.selectionCount());
        Log.info("AGENT-DEMO PARITY OK decisions=@ path=public-candidates",
            publicDemo.selectionCount());
        verifyControlsAndExit();
    }

    private void requireSchematic(Scenario.SchematicSpec spec, int anchorX, int anchorY){
        for(BuildSpec block : spec.blocks()){
            Building building = world.build(anchorX + block.offsetX(), anchorY + block.offsetY());
            if(building == null || !building.block.name.equals(block.block())
                || building.rotation != block.rotation()){
                throw new IllegalStateException("public policy schematic incomplete: " + spec.name());
            }
        }
    }

    private void verifyControlsAndExit(){
        pause();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            if(agent.controller().enabled() || !agent.unit().vel.isZero()){
                throw new IllegalStateException("pause did not halt agent " + agent.index());
            }
        }
        resume();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            if(!agent.controller().enabled()){
                throw new IllegalStateException("resume did not enable agent " + agent.index());
            }
        }
        stop();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            if(agent.controller().enabled() || agent.controller().activeSkill() != null){
                throw new IllegalStateException("stop did not cancel agent " + agent.index());
            }
        }
        Log.info("AGENT-DEMO CONTROLS OK pause/resume/stop halted all three agents");
        Log.info("AGENT-DEMO PROBE OK tick=@ announcements=public:@",
            (long)state.tick, announcements);
        Core.app.exit();
    }

    private boolean started(){ return publicPolicy ? publicDemo.started() : driver.started(); }
    private int taskCount(){
        return publicPolicy ? publicDemo.taskCount() : driver.board().tasks().size();
    }
    private String phase(){ return publicPolicy ? publicDemo.phase() : driver.phase(); }

    private static boolean publicPolicyEnabled(){
        String configured = System.getProperty(AgentPlugin.publicPolicyProperty, "true").trim();
        if(configured.equalsIgnoreCase("true")) return true;
        if(configured.equalsIgnoreCase("false")) return false;
        throw new IllegalArgumentException(AgentPlugin.publicPolicyProperty
            + " must be true or false, got: " + configured);
    }

    private static List<String> blockNames(Scenario.SchematicSpec spec){
        ArrayList<String> result = new ArrayList<>();
        for(BuildSpec block : spec.blocks()) result.add(block.block());
        return List.copyOf(result);
    }

    private static Set<String> humanRegions(Scenario scenario){
        TreeSet<String> result = new TreeSet<>();
        for(String id : scenario.regions.keys()) result.add(id.toLowerCase(Locale.ROOT));
        for(String id : scenario.schematics.keys()) result.add(id.toLowerCase(Locale.ROOT));
        for(Scenario.OrePatch patch : scenario.orePatches){
            result.add(patch.id.toLowerCase(Locale.ROOT));
        }
        for(Scenario.ObjectiveSpec objective : scenario.objectives.values()){
            if(!objective.targetRef().isBlank()){
                result.add(objective.targetRef().toLowerCase(Locale.ROOT));
            }
        }
        return Set.copyOf(result);
    }

    void humanBuildCompleted(BlockBuildEndEvent event){
        if(!publicPolicy || event == null || event.breaking || event.unit == null
            || !event.unit.isPlayer() || event.team != scenario.coreTeam
            || event.tile == null || event.tile.block() == Blocks.air) return;
        int rotation = event.tile.build == null ? 0 : event.tile.build.rotation;
        BuildPlan completed = new BuildPlan(event.tile.x, event.tile.y, rotation,
            event.tile.block());
        humanPresence.constructionCompleted(presence(completed), (long)state.tick);
    }

    private void syncHumanPresence(){
        TreeMap<String, Plan> plans = new TreeMap<>();
        for(Player player : Groups.player){
            if(player.team() != scenario.coreTeam || !player.isBuilder()) continue;
            for(BuildPlan plan : player.unit().plans()){
                Plan presence = presence(plan);
                if(presence != null) plans.put(presence.id(), presence);
            }
        }
        if(probeHumanPlan != null){
            Plan presence = presence(probeHumanPlan);
            if(presence != null) plans.put(presence.id(), presence);
        }
        publicDemo.applyHumanPresence(humanPresence.update(plans.values(), (long)state.tick),
            (long)state.tick);
    }

    private static Plan presence(BuildPlan plan){
        if(plan == null || plan.block == null) return null;
        int x = plan.x + plan.block.sizeOffset;
        int y = plan.y + plan.block.sizeOffset;
        TreeMap<String, Integer> resources = new TreeMap<>();
        if(!plan.breaking){
            for(mindustry.type.ItemStack requirement : plan.block.requirements){
                int amount = Math.round(requirement.amount * state.rules.buildCostMultiplier);
                if(amount > 0) resources.merge(requirement.item.name, amount, Integer::sum);
            }
        }
        String id = "human:presence:" + plan.x + ":" + plan.y + ":"
            + plan.block.name + ":" + plan.rotation + ":"
            + (plan.breaking ? "break" : "build");
        return new Plan(id, new agentcore.reservation.Rect(x, y,
            plan.block.size, plan.block.size), resources);
    }

    private void driveHumanProbe(){
        if(!humanProbe || !publicPolicy || !started()) return;
        switch(humanProbePhase){
            case 0 -> {
                probeCommand("goal", "build-line", scenario.buildLineId);
                probeCommand("assign", "0", "human:goal:1");
                humanProbePhase = 1;
            }
            case 1 -> {
                if(publicDemo.taskOwner("human:goal:1") != 0) return;
                startProbeHumanPresence();
                humanProbePhase = 2;
            }
            case 2 -> {
                if(publicDemo.humanReservationYields() != 1 || humanYieldNotices != 1
                    || publicDemo.taskOwner("human:goal:1") >= 0) return;
                if(publicDemo.agentBuildPlanOverlaps(probePresence.area())){
                    throw new IllegalStateException("agent retained a plan inside human reservation");
                }
                int copper = probePresence.resources().getOrDefault("copper", 0);
                if(copper <= 0 || publicDemo.humanReservedAmount("copper") != copper){
                    throw new IllegalStateException("human resource floor was not reserved");
                }
                probeHumanPlan = null;
                humanPresence.constructionCompleted(probePresence, (long)state.tick);
                probeRecentExpiry = (long)state.tick + HumanPresence.RECENT_CONSTRUCTION_TICKS;
                humanProbePhase = 3;
            }
            case 3 -> {
                if(!publicDemo.hasHumanPresence(probePresence.id())) return;
                if(publicDemo.humanReservedAmount("copper") != 0){
                    throw new IllegalStateException("completed human plan retained resource floor");
                }
                if(publicDemo.taskOwner("human:goal:1") >= 0
                    || publicDemo.agentBuildPlanOverlaps(probePresence.area())){
                    throw new IllegalStateException("agent entered recent human construction zone");
                }
                if((long)state.tick < probeRecentExpiry) return;
                humanProbePhase = 4;
            }
            case 4 -> {
                if(publicDemo.hasHumanPresence(probePresence.id())
                    || !publicDemo.taskCompleted("human:goal:1")) return;
                probeCommand("release", "0");
                probeCommand("cancel", "human:goal:1");
                probeCommand("autonomy", "low");
                probeCommand("goal", "defend-region", "east_lane");
                probeCommand("assign", "1", "human:goal:2");
                probeCommand("quiet", "on");
                humanProbePhase = 5;
            }
            case 5 -> {
                if(publicDemo.taskOwner("human:goal:2") != 1
                    || !publicDemo.lowIsolation("human:goal:2", 1)) return;
                lowAutonomyObserved = true;
                probeCommand("release", "1");
                probeCommand("assign", "2", "human:goal:2");
                humanProbePhase = 6;
            }
            case 6 -> {
                if(publicDemo.taskOwner("human:goal:2") != 2
                    || !publicDemo.lowIsolation("human:goal:2", 2)) return;
                probeCommand("cancel", "human:goal:2");
                probeCommand("autonomy", "high");
                probeCommand("goal", "defend-region", "east_lane");
                probeCommand("quiet", "off");
                humanProbePhase = 7;
            }
            case 7 -> {
                if(publicDemo.taskOwner("human:goal:3") < 0) return;
                highAutonomyObserved = true;
                probeCommand("cancel", "human:goal:3");
                probeCommand("autonomy", "normal");
                humanProbePhase = 8;
            }
            case 8 -> finishHumanProbe();
            case 9 -> { }
            default -> throw new IllegalStateException("invalid human probe phase");
        }
    }

    private void startProbeHumanPresence(){
        Scenario.SchematicSpec line = scenario.schematic(scenario.buildLineId);
        if(line == null || line.blocks().isEmpty()){
            throw new IllegalStateException("human probe requires build-line schematic");
        }
        BuildSpec block = line.blocks().get(0);
        probeHumanPlan = new BuildPlan(scenario.buildLineAnchorX + block.offsetX(),
            scenario.buildLineAnchorY + block.offsetY(), block.rotation(),
            content.block(block.block()));
        probePresence = presence(probeHumanPlan);
        if(probePresence == null) throw new IllegalStateException("invalid human probe plan");
    }

    private void probeCommand(String... tokens){
        String queued = queueHumanCommand(tokens, "probe", message ->
            Log.info("AGENT-DEMO HUMAN RESPONSE @", message));
        Log.info("AGENT-DEMO HUMAN QUEUED @", queued);
    }

    private void finishHumanProbe(){
        Snapshot controls = humanControl.snapshot();
        if(!controls.activeGoals().isEmpty() || !controls.assignments().isEmpty()
            || controls.autonomy() != AutonomyLevel.NORMAL || controls.quiet()) return;
        if(!lowAutonomyObserved || !highAutonomyObserved){
            throw new IllegalStateException("human autonomy modes were not observed");
        }
        if(suppressedAnnouncements == 0){
            throw new IllegalStateException("quiet mode suppressed no rendered announcement");
        }
        if(publicDemo.humanReservationYields() != 1 || humanYieldNotices != 1){
            throw new IllegalStateException("human conflict notification was not exactly once");
        }
        Log.info("AGENT-DEMO HUMAN CONTROL OK tick=@ low=true high=true suppressed=@ yields=1",
            (long)state.tick, suppressedAnnouncements);
        Core.app.exit();
        humanProbePhase = 9;
    }

    private final class DemoPort implements ExpertCoordinationDriver.Port{
        @Override
        public SkillResult lastResult(int agentIndex){
            DemoAgentRegistry.Agent agent = registry.get(agentIndex);
            return agent == null ? SkillResult.ready() : agent.controller().lastResult();
        }

        @Override
        public Skill activeSkill(int agentIndex){
            DemoAgentRegistry.Agent agent = registry.get(agentIndex);
            return agent == null ? null : agent.controller().activeSkill();
        }

        @Override
        public void setSkill(int agentIndex, Skill skill){
            DemoAgentRegistry.Agent agent = registry.get(agentIndex);
            if(agent != null) agent.controller().setSkill(skill);
        }

        @Override
        public void cancelWork(int agentIndex){
            DemoAgentRegistry.Agent agent = registry.get(agentIndex);
            if(agent == null) return;
            agent.controller().pauseNow();
            agent.controller().clearSkill();
            if(!stopped) agent.controller().resumeNow();
        }

        @Override
        public void ensureAgent(int agentIndex){
            registry.ensureAgent(agentIndex);
        }

        @Override
        public boolean agentAvailable(int agentIndex){
            return registry.available(agentIndex);
        }

        @Override
        public int coreCopper(){
            Building core = scenario.coreTeam.core();
            return core == null ? 0 : core.items.get(Items.copper);
        }

        @Override
        public boolean buildingMatches(ExpertCoordinationDriver.BuildPlacement placement){
            Building building = world.build(placement.x(), placement.y());
            return building != null && building.block.name.equals(placement.block());
        }
    }
}
