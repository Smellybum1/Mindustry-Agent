package mindustry.agentplugin;

import agentcore.*;
import agentcore.announce.*;
import agentcore.board.*;
import agentcore.event.*;
import agentcore.skill.*;
import agentcore.task.*;
import arc.*;
import arc.struct.*;
import arc.util.*;
import mindustry.content.*;
import mindustry.entities.*;
import mindustry.gen.*;
import mindustry.rl.*;

import java.util.*;

import static mindustry.Vars.*;

/** Simulation-thread board/policy adapter for the ordinary real-time server. */
final class DemoCoordinator{
    private enum Stage{
        IDLE, BUILD_LINE, BUILD_DEFENSE, MINE, DELIVER, SUPPLY_A, SUPPLY_B, DEFEND
    }

    private static final String[] names = {"agent-copper", "agent-shield", "agent-relay"};
    private static final int mineX = 28, mineY = 18;

    private static final class Agent{
        final int index;
        final AgentId id;
        final Unit unit;
        final DemoAgentController controller;
        Stage stage = Stage.IDLE;
        String taskId;
        boolean blocked;
        int recordedBlocks;

        Agent(int index, Unit unit, DemoAgentController controller){
            this.index = index;
            this.id = new AgentId(index, names[index]);
            this.unit = unit;
            this.controller = controller;
        }
    }

    private final Scenario scenario;
    private final boolean probe;
    private final boolean waitForPlayer;
    private final TaskBoard board = new TaskBoard();
    private final AnnouncementRenderer renderer = new AnnouncementRenderer();
    private final Seq<Agent> agents = new Seq<>();
    private final List<String> lineOrder = new ArrayList<>();
    private final List<String> defenseOrder = new ArrayList<>();

    private boolean started;
    private boolean paused;
    private boolean stopped;
    private boolean probeReported;
    private long lastHeartbeat;
    private int announcements;

    DemoCoordinator(Scenario scenario, boolean probe, boolean waitForPlayer){
        this.scenario = scenario;
        this.probe = probe;
        this.waitForPlayer = waitForPlayer;
        board.reset(1L);
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
        player.sendMessage("[accent]Cooperative agents ready. /agents status|pause|resume|stop");
        if(waitForPlayer && !started && !stopped) startOpening();
    }

    void startOpening(){
        if(started || stopped) return;
        started = true;

        Scenario.SchematicSpec line = scenario.schematic(scenario.buildLineId);
        Scenario.SchematicSpec defense = scenario.schematic(scenario.referenceSchematicId);

        begin(agents.get(0), "demo-line", TaskType.BUILD_LINE,
            new TileTarget(scenario.buildLineAnchorX, scenario.buildLineAnchorY),
            ResourceCost.of("copper", line.copperCost()),
            new ExecuteSchematic(line.name(), scenario.buildLineAnchorX,
                scenario.buildLineAnchorY, line.blocks()), Stage.BUILD_LINE);
        begin(agents.get(1), "demo-defense", TaskType.BUILD_SCHEMATIC,
            new TileTarget(scenario.referenceAnchorX, scenario.referenceAnchorY),
            ResourceCost.of("copper", defense.copperCost()),
            new ExecuteSchematic(defense.name(), scenario.referenceAnchorX,
                scenario.referenceAnchorY, defense.blocks()), Stage.BUILD_DEFENSE);
        begin(agents.get(2), "demo-harvest", TaskType.HARVEST_RESOURCE,
            new ResourceTarget("copper", 300), ResourceCost.empty(),
            new MineResource(mineX, mineY, 20), Stage.MINE);
        drainAnnouncements();
    }

    void update(){
        if(!started || paused || stopped || !state.isPlaying()) return;
        long tick = (long)state.tick;

        for(Agent agent : agents){
            updateBuildOrder(agent);
            SkillResult result = agent.controller.lastResult();
            if(tick - lastHeartbeat >= 120 && agent.taskId != null){
                board.heartbeat(agent.taskId, agent.id, tick);
                board.reportProgress(agent.taskId, agent.id, result.progress(), tick);
            }
            if(result.status() == SkillStatus.BLOCKED && !agent.blocked && agent.taskId != null){
                agent.blocked = true;
                board.reportBlocked(agent.taskId, agent.id,
                    result.reason().name().toLowerCase(), tick);
            }else if(result.status() == SkillStatus.RUNNING && agent.blocked && agent.taskId != null){
                agent.blocked = false;
                board.reportProgress(agent.taskId, agent.id, result.progress(), tick);
            }
            if(result.status() == SkillStatus.SUCCEEDED){
                advance(agent, tick);
            }else if(result.status() == SkillStatus.FAILED || result.status() == SkillStatus.CANCELLED){
                abandon(agent, result.reason().name().toLowerCase(), tick);
            }
        }
        if(tick - lastHeartbeat >= 120) lastHeartbeat = tick;
        board.expireStale(tick);
        drainAnnouncements();
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
        if(!started) startOpening();
        paused = false;
        for(Agent agent : agents) agent.controller.resumeNow();
        return "agents: running at tick " + (long)state.tick;
    }

    String stop(){
        if(stopped) return "agents: already stopped";
        stopped = true;
        paused = false;
        long tick = (long)state.tick;
        for(Agent agent : agents){
            agent.controller.stopNow();
            if(agent.taskId != null){
                board.abandon(agent.taskId, agent.id, "human_emergency_stop", tick);
                agent.taskId = null;
            }
        }
        drainAnnouncements();
        return "agents: emergency stop complete at tick " + tick;
    }

    String status(){
        String mode = stopped ? "stopped" : paused ? "paused" : started ? "running" : "waiting";
        int active = 0;
        for(Agent agent : agents) if(agent.controller.activeSkill() != null) active++;
        return "agents: " + mode + " tick=" + (long)state.tick + " active=" + active
            + "/" + agents.size + " tasks=" + board.tasks().size()
            + " announcements=" + announcements;
    }

    private void begin(Agent agent, String taskId, TaskType type, Target target,
                       ResourceCost cost, Skill skill, Stage stage){
        long tick = (long)state.tick;
        TaskSpec spec = TaskSpec.builder(taskId, type)
            .target(target)
            .priority(1.0)
            .estimatedTicks(900)
            .estimatedCost(cost)
            .requiredCapabilities(Set.of(skill.type().toLowerCase()))
            .build();
        board.propose(spec, tick);
        board.announceIntent(taskId, agent.id, 1.0, tick);
        board.claim(taskId, agent.id, 1.0, tick);
        board.start(taskId, agent.id, tick);
        agent.taskId = taskId;
        agent.stage = stage;
        agent.blocked = false;
        agent.recordedBlocks = 0;
        agent.controller.setSkill(skill);
    }

    private void advance(Agent agent, long tick){
        switch(agent.stage){
            case BUILD_LINE -> {
                complete(agent, tick);
                agent.stage = Stage.DEFEND;
                agent.controller.setSkill(new DefendRegion(244f, 196f, 220f, Long.MAX_VALUE));
            }
            case BUILD_DEFENSE -> {
                complete(agent, tick);
                begin(agent, "demo-supply-a", TaskType.SUPPLY_TURRET,
                    new TileTarget(32, 23), ResourceCost.of("copper", 15),
                    new SupplyBuilding("copper", 32, 23, 15), Stage.SUPPLY_A);
            }
            case SUPPLY_A -> {
                complete(agent, tick);
                begin(agent, "demo-supply-b", TaskType.SUPPLY_TURRET,
                    new TileTarget(32, 25), ResourceCost.of("copper", 15),
                    new SupplyBuilding("copper", 32, 25, 15), Stage.SUPPLY_B);
            }
            case SUPPLY_B -> {
                complete(agent, tick);
                agent.stage = Stage.DEFEND;
                agent.controller.setSkill(new DefendRegion(260f, 196f, 220f, Long.MAX_VALUE));
            }
            case MINE -> {
                agent.stage = Stage.DELIVER;
                agent.controller.setSkill(new DeliverToCore());
            }
            case DELIVER -> {
                if(agent.taskId != null) board.reportProgress(agent.taskId, agent.id, 0.5, tick);
                agent.stage = Stage.MINE;
                agent.controller.setSkill(new MineResource(mineX, mineY, 20));
            }
            case DEFEND -> agent.controller.setSkill(new DefendRegion(244f, 196f, 220f, Long.MAX_VALUE));
            case IDLE -> { }
        }
    }

    private void complete(Agent agent, long tick){
        if(agent.taskId != null) board.complete(agent.taskId, agent.id, tick);
        agent.taskId = null;
        agent.controller.clearSkill();
    }

    private void abandon(Agent agent, String reason, long tick){
        if(agent.taskId != null) board.abandon(agent.taskId, agent.id, reason, tick);
        agent.taskId = null;
        agent.stage = Stage.IDLE;
        agent.controller.stopNow();
    }

    private void updateBuildOrder(Agent agent){
        if(!(agent.controller.activeSkill() instanceof ExecuteSchematic active)) return;
        Scenario.SchematicSpec spec = agent.stage == Stage.BUILD_LINE
            ? scenario.schematic(scenario.buildLineId)
            : scenario.schematic(scenario.referenceSchematicId);
        List<String> output = agent.stage == Stage.BUILD_LINE ? lineOrder : defenseOrder;
        while(agent.recordedBlocks < active.completed()){
            output.add(spec.blocks().get(agent.recordedBlocks).block());
            agent.recordedBlocks++;
        }
    }

    private void drainAnnouncements(){
        for(CoordinationEvent event : board.events().drain()){
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
        if(!probe || probeReported) return;
        Agent shield = agents.get(1);
        if(shield.stage != Stage.DEFEND) return;

        List<String> expectedLine = blockNames(scenario.schematic(scenario.buildLineId));
        List<String> expectedDefense = blockNames(scenario.schematic(scenario.referenceSchematicId));
        if(!lineOrder.equals(expectedLine) || !defenseOrder.equals(expectedDefense)){
            throw new IllegalStateException("demo opening order drift: line=" + lineOrder
                + " defense=" + defenseOrder);
        }
        probeReported = true;
        Log.info("AGENT-DEMO PARITY OK line=@ defense=@", String.join(",", lineOrder),
            String.join(",", defenseOrder));
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
}
