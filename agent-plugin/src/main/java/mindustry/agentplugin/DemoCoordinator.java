package mindustry.agentplugin;

import agentcore.announce.*;
import agentcore.coordination.*;
import agentcore.event.*;
import agentcore.skill.*;
import agentcore.task.*;
import arc.*;
import arc.struct.*;
import arc.util.*;
import mindustry.content.*;
import mindustry.core.GameState.*;
import mindustry.entities.*;
import mindustry.gen.*;
import mindustry.rl.*;

import java.util.*;

import static mindustry.Vars.*;

/** Real-time pacing, I/O, and engine binding for the shared coordination driver. */
final class DemoCoordinator{
    private static final String[] names = {"agent-copper", "agent-shield", "agent-relay"};

    private static final class Agent{
        final int index;
        Unit unit;
        final DemoAgentController controller;

        Agent(int index, Unit unit, DemoAgentController controller){
            this.index = index;
            this.unit = unit;
            this.controller = controller;
        }
    }

    private final Scenario scenario;
    private final boolean probe;
    private final boolean waitForPlayer;
    private final boolean survivalProbe;
    private final AnnouncementRenderer renderer = new AnnouncementRenderer();
    private final Seq<Agent> agents = new Seq<>();
    private final ExpertCoordinationDriver driver;

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
        this.driver = new ExpertCoordinationDriver(
            ExpertCoordinationPlans.fromScenario(scenario), new DemoPort());
        driver.reset(1L);
    }

    void spawn(){
        Building core = scenario.coreTeam.core();
        if(core == null) throw new IllegalStateException("demo scenario has no core");
        for(int i = 0; i < names.length; i++){
            Unit unit = UnitTypes.alpha.spawn(scenario.coreTeam,
                core.x + (3 + i) * tilesize, core.y);
            DemoAgentController controller = new DemoAgentController(i);
            unit.controller(controller);
            Units.notifyUnitSpawn(unit);
            agents.add(new Agent(i, unit, controller));
        }
        Log.info("[agents] spawned @ controlled alpha units.", agents.size);
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
        if(driver.started() || stopped) return;
        driver.startOpening((long)state.tick);
        drainAnnouncements();
    }

    void update(){
        if(!driver.started() || paused || stopped || !state.isPlaying()) return;
        long tick = (long)state.tick;
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
        for(Agent agent : agents) agent.controller.pauseNow();
        return "agents: paused at tick " + (long)state.tick;
    }

    String resume(){
        if(stopped) return "agents: stopped (start a new demo world to resume)";
        if(!driver.started()){
            startOpening();
            if(waitForPlayer && state.isPaused()) state.set(State.playing);
        }
        paused = false;
        for(Agent agent : agents) agent.controller.resumeNow();
        return "agents: running at tick " + (long)state.tick;
    }

    String stop(){
        if(stopped) return "agents: already stopped";
        stopped = true;
        paused = false;
        long tick = (long)state.tick;
        driver.stop(tick, "human_emergency_stop");
        for(Agent agent : agents) agent.controller.stopNow();
        drainAnnouncements();
        return "agents: emergency stop complete at tick " + tick;
    }

    String status(){
        String mode = stopped ? "stopped" : paused ? "paused"
            : driver.started() ? "running" : "waiting";
        int active = 0;
        for(Agent agent : agents) if(agent.controller.activeSkill() != null) active++;
        return "agents: " + mode + " tick=" + (long)state.tick + " active=" + active
            + "/" + agents.size + " tasks=" + driver.board().tasks().size()
            + " announcements=" + announcements + " phase=" + driver.phase();
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

    private void finishProbeIfReady(){
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
        for(Agent agent : agents){
            if(agent.controller.enabled() || !agent.unit.vel.isZero()){
                throw new IllegalStateException("pause did not halt agent " + agent.index);
            }
        }
        resume();
        for(Agent agent : agents){
            if(!agent.controller.enabled()){
                throw new IllegalStateException("resume did not enable agent " + agent.index);
            }
        }
        stop();
        for(Agent agent : agents){
            if(agent.controller.enabled() || agent.controller.activeSkill() != null){
                throw new IllegalStateException("stop did not cancel agent " + agent.index);
            }
        }
        Log.info("AGENT-DEMO CONTROLS OK pause/resume/stop halted all three agents");
        Log.info("AGENT-DEMO PROBE OK tick=@ announcements=@", (long)state.tick, announcements);
        Core.app.exit();
    }

    private static List<String> blockNames(Scenario.SchematicSpec spec){
        ArrayList<String> result = new ArrayList<>();
        for(BuildSpec block : spec.blocks()) result.add(block.block());
        return List.copyOf(result);
    }

    private final class DemoPort implements ExpertCoordinationDriver.Port{
        @Override
        public SkillResult lastResult(int agentIndex){
            Agent agent = agent(agentIndex);
            return agent == null ? SkillResult.ready() : agent.controller.lastResult();
        }

        @Override
        public Skill activeSkill(int agentIndex){
            Agent agent = agent(agentIndex);
            return agent == null ? null : agent.controller.activeSkill();
        }

        @Override
        public void setSkill(int agentIndex, Skill skill){
            Agent agent = agent(agentIndex);
            if(agent != null) agent.controller.setSkill(skill);
        }

        @Override
        public void cancelWork(int agentIndex){
            Agent agent = agent(agentIndex);
            if(agent == null) return;
            agent.controller.pauseNow();
            agent.controller.clearSkill();
            if(!stopped) agent.controller.resumeNow();
        }

        @Override
        public void ensureAgent(int agentIndex){
            Agent agent = agent(agentIndex);
            if(agent == null || (agent.unit != null && agent.unit.isValid() && !agent.unit.dead())) return;
            Building core = scenario.coreTeam.core();
            if(core == null) throw new IllegalStateException("cannot rebind agent without a core");
            Unit replacement = UnitTypes.alpha.spawn(scenario.coreTeam,
                core.x + (3 + agent.index) * tilesize, core.y);
            replacement.controller(agent.controller);
            Units.notifyUnitSpawn(replacement);
            agent.unit = replacement;
            agent.controller.resumeNow();
            Log.warn("AGENT-DEMO REBOUND agent=@ replacement_unit=@", agent.index, replacement.id);
        }

        @Override
        public boolean agentAvailable(int agentIndex){
            Agent agent = agent(agentIndex);
            return agent != null && agent.unit != null && agent.unit.isValid() && !agent.unit.dead();
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

        private Agent agent(int index){
            return index >= 0 && index < agents.size ? agents.get(index) : null;
        }
    }
}
