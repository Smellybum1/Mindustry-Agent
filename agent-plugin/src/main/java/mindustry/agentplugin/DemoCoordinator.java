package mindustry.agentplugin;

import agentcore.announce.*;
import agentcore.coordination.*;
import agentcore.event.*;
import agentcore.skill.*;
import agentcore.task.*;
import arc.*;
import arc.struct.*;
import arc.util.*;
import arc.util.serialization.*;
import mindustry.content.*;
import mindustry.core.GameState.*;
import mindustry.entities.*;
import mindustry.gen.*;
import mindustry.rl.*;

import java.util.*;

import static mindustry.Vars.*;

/** Real-time pacing, I/O, and engine binding for the shared coordination driver. */
final class DemoCoordinator{
    private final Scenario scenario;
    private final boolean probe;
    private final boolean waitForPlayer;
    private final boolean survivalProbe;
    private final boolean publicPolicy;
    private final AnnouncementRenderer renderer = new AnnouncementRenderer();
    private final DemoAgentRegistry registry;
    private final ExpertCoordinationDriver driver;
    private final PublicCandidateDemo publicDemo;

    private boolean paused;
    private boolean stopped;
    private boolean probeReported;
    private boolean survivalReported;
    private int announcements;

    DemoCoordinator(Scenario scenario, boolean probe, boolean waitForPlayer){
        this.scenario = scenario;
        this.probe = probe;
        this.waitForPlayer = waitForPlayer;
        this.survivalProbe = System.getProperty(AgentPlugin.modeProperty, "")
            .equalsIgnoreCase("survival");
        this.publicPolicy = Boolean.getBoolean(AgentPlugin.publicPolicyProperty);
        this.registry = new DemoAgentRegistry(scenario);
        this.driver = new ExpertCoordinationDriver(
            ExpertCoordinationPlans.fromScenario(scenario), new DemoPort());
        this.publicDemo = new PublicCandidateDemo(scenario, registry);
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
            player.sendMessage("[accent]Cooperative agents active. /agents status|pause|resume|stop");
        }
    }

    void startOpening(){
        if(started() || stopped) return;
        if(publicPolicy){
            publicDemo.start();
            drainPublicAnnouncements();
        }else{
            driver.startOpening((long)state.tick);
            drainAnnouncements();
        }
    }

    void update(){
        if(!started() || paused || stopped || !state.isPlaying()) return;
        long tick = (long)state.tick;
        if(publicPolicy){
            publicDemo.update();
            drainPublicSignals();
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
            if(waitForPlayer && state.isPaused()) state.set(State.playing);
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
        return "agents: " + mode + " tick=" + (long)state.tick + " active=" + active
            + "/" + registry.size() + " tasks=" + taskCount()
            + " announcements=" + announcements + " phase=" + phase();
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
            if(!event.getBool("announce", false)) continue;
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

    private void finishProbeIfReady(){
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

    private static List<String> blockNames(Scenario.SchematicSpec spec){
        ArrayList<String> result = new ArrayList<>();
        for(BuildSpec block : spec.blocks()) result.add(block.block());
        return List.copyOf(result);
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
