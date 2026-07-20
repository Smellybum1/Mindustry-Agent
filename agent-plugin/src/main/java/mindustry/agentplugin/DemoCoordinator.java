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
import mindustry.core.GameState.*;
import mindustry.entities.*;
import mindustry.gen.*;
import mindustry.rl.*;

import java.util.*;

import static mindustry.Vars.*;

/** Simulation-thread board/policy adapter for the ordinary real-time server. */
final class DemoCoordinator{
    private enum Stage{
        IDLE, BUILD_LINE, BUILD_DEFENSE, MINE, DELIVER,
        ECONOMY_MINE, ECONOMY_DELIVER, FORTIFY, SUPPLY, DEFEND,
        REBUILD, MAINTENANCE_MINE, MAINTENANCE_DELIVER,
        RESERVE_MINE, RESERVE_DELIVER
    }

    private static final String[] names = {"agent-copper", "agent-shield", "agent-relay"};
    private static final int[][] mineTiles = {{28, 18}, {31, 18}, {28, 21}};

    private record BuildPlacement(String block, int x, int y, int rotation){}

    private static final class Agent{
        final int index;
        final AgentId id;
        Unit unit;
        final DemoAgentController controller;
        Stage stage = Stage.IDLE;
        String taskId;
        boolean blocked;
        int recordedBlocks;
        int economyRounds;
        int maintenanceRounds;
        boolean maintenanceDone;

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
    private final boolean survivalProbe;
    private final TaskBoard board = new TaskBoard();
    private final AnnouncementRenderer renderer = new AnnouncementRenderer();
    private final Seq<Agent> agents = new Seq<>();
    private final List<String> lineOrder = new ArrayList<>();
    private final List<String> defenseOrder = new ArrayList<>();
    private final ArrayDeque<BuildPlacement> fortifications = new ArrayDeque<>();
    private final ArrayDeque<TileTarget> supplyTargets = new ArrayDeque<>();
    private final List<TileTarget> activeTurrets = new ArrayList<>();
    private final List<BuildPlacement> expectedExpansions = new ArrayList<>();

    private boolean started;
    private boolean paused;
    private boolean stopped;
    private boolean probeReported;
    private boolean survivalReported;
    private boolean lineComplete;
    private boolean baseDefenseComplete;
    private boolean economyStarted;
    private boolean fortificationStarted;
    private boolean supplyStarted;
    private boolean preparationComplete;
    private boolean defenseStarted;
    private boolean maintenance;
    private boolean maintenanceSupplyStarted;
    private boolean maintenanceExpansionPrepared;
    private boolean maintenanceExpansionReported;
    private boolean rebuildDone;
    private long lastHeartbeat;
    private int announcements;
    private int buildsInFlight;
    private int suppliesInFlight;
    private int taskSequence;
    private int previousEnemies;
    private int waveClears;
    private long maintenanceStartTick;
    private long maintenanceSupplyStartTick;

    DemoCoordinator(Scenario scenario, boolean probe, boolean waitForPlayer){
        this.scenario = scenario;
        this.probe = probe;
        this.waitForPlayer = waitForPlayer;
        this.survivalProbe = System.getProperty(AgentPlugin.modeProperty, "")
            .equalsIgnoreCase("survival");
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
        if(waitForPlayer && !started && !stopped){
            player.sendMessage("[accent]Cooperative agents ready. Type /agents resume when you are ready to watch.");
        }else{
            player.sendMessage("[accent]Cooperative agents active. /agents status|pause|resume|stop");
        }
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
            new MineResource(mineTiles[2][0], mineTiles[2][1], 20), Stage.MINE);
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
        trackWaves(tick);
        if(tick - lastHeartbeat >= 120) lastHeartbeat = tick;
        board.expireStale(tick);
        dispatchPolicy(tick);
        drainAnnouncements();
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
    }

    String pause(){
        if(stopped) return "agents: stopped";
        paused = true;
        for(Agent agent : agents) agent.controller.pauseNow();
        return "agents: paused at tick " + (long)state.tick;
    }

    String resume(){
        if(stopped) return "agents: stopped (start a new demo world to resume)";
        if(!started){
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
            + " announcements=" + announcements + " phase=" + phase();
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
                lineComplete = true;
                idle(agent);
            }
            case BUILD_DEFENSE -> {
                complete(agent, tick);
                baseDefenseComplete = true;
                idle(agent);
            }
            case MINE -> {
                agent.stage = Stage.DELIVER;
                agent.controller.setSkill(new DeliverToCore());
            }
            case DELIVER -> {
                if(agent.taskId != null) board.reportProgress(agent.taskId, agent.id, 0.5, tick);
                agent.stage = Stage.MINE;
                int[] tile = mineTiles[agent.index];
                agent.controller.setSkill(new MineResource(tile[0], tile[1], 20));
            }
            case ECONOMY_MINE -> {
                agent.stage = Stage.ECONOMY_DELIVER;
                agent.controller.setSkill(new DeliverToCore());
            }
            case ECONOMY_DELIVER -> {
                agent.economyRounds++;
                if(agent.economyRounds < 2){
                    agent.stage = Stage.ECONOMY_MINE;
                    int[] tile = mineTiles[agent.index];
                    agent.controller.setSkill(new MineResource(tile[0], tile[1], 20));
                }else{
                    complete(agent, tick);
                    idle(agent);
                }
            }
            case FORTIFY -> {
                complete(agent, tick);
                buildsInFlight--;
                idle(agent);
            }
            case SUPPLY -> {
                complete(agent, tick);
                suppliesInFlight--;
                idle(agent);
            }
            case REBUILD -> {
                complete(agent, tick);
                rebuildDone = true;
                agent.maintenanceDone = true;
                idle(agent);
            }
            case MAINTENANCE_MINE -> {
                agent.stage = Stage.MAINTENANCE_DELIVER;
                agent.controller.setSkill(new DeliverToCore());
            }
            case MAINTENANCE_DELIVER -> {
                agent.maintenanceRounds++;
                if(agent.maintenanceRounds < 1){
                    int[] tile = mineTiles[agent.index];
                    agent.stage = Stage.MAINTENANCE_MINE;
                    agent.controller.setSkill(new MineResource(tile[0], tile[1], 20));
                }else{
                    complete(agent, tick);
                    agent.maintenanceDone = true;
                    idle(agent);
                }
            }
            case RESERVE_MINE -> {
                agent.stage = Stage.RESERVE_DELIVER;
                agent.controller.setSkill(new DeliverToCore());
            }
            case RESERVE_DELIVER -> {
                if(agent.taskId != null) board.reportProgress(agent.taskId, agent.id, 0.05, tick);
                int[] tile = mineTiles[agent.index];
                agent.stage = Stage.RESERVE_MINE;
                agent.controller.setSkill(new MineResource(tile[0], tile[1], 20));
            }
            case DEFEND -> agent.controller.setSkill(new DefendRegion(244f, 196f, 220f, Long.MAX_VALUE));
            case IDLE -> { }
        }
    }

    private void dispatchPolicy(long tick){
        if(maintenance){
            dispatchMaintenance();
            return;
        }
        if(!economyStarted && lineComplete && baseDefenseComplete){
            startEconomy(tick);
            return;
        }
        if(economyStarted && !fortificationStarted && allEconomyReady()){
            prepareFortifications();
            fortificationStarted = true;
        }
        if(fortificationStarted && !supplyStarted){
            dispatchFortifications();
            if(fortifications.isEmpty() && buildsInFlight == 0){
                prepareSupply();
                supplyStarted = true;
            }
        }
        if(supplyStarted && !preparationComplete){
            dispatchSupply();
            if(supplyTargets.isEmpty() && suppliesInFlight == 0){
                preparationComplete = true;
                Log.info("AGENT-DEMO EXPERT READY tick=@ fortifications=20 turrets=4", (long)state.tick);
                startReserveMining(tick, "opening_complete");
            }
        }
    }

    private void startEconomy(long tick){
        economyStarted = true;
        for(Agent agent : agents){
            if(agent.taskId != null){
                board.abandon(agent.taskId, agent.id, "opening_economy_transition", tick);
            }
            cancelControllerWork(agent);
            agent.taskId = null;
            agent.economyRounds = 0;
            int[] tile = mineTiles[agent.index];
            begin(agent, "demo-economy-" + agent.index, TaskType.HARVEST_RESOURCE,
                new ResourceTarget("copper", 40), ResourceCost.empty(),
                new MineResource(tile[0], tile[1], 20), Stage.ECONOMY_MINE);
        }
    }

    private boolean allEconomyReady(){
        for(Agent agent : agents){
            if(agent.economyRounds < 2 || agent.stage != Stage.IDLE) return false;
        }
        return true;
    }

    private void prepareFortifications(){
        for(int y = 22; y <= 26; y++) fortifications.add(new BuildPlacement("copper-wall", 22, y, 0));
        for(int y = 22; y <= 24; y++) fortifications.add(new BuildPlacement("copper-wall", 26, y, 0));
        for(int x = 23; x <= 25; x++) fortifications.add(new BuildPlacement("copper-wall", x, 22, 0));
        for(int x = 23; x <= 24; x++) fortifications.add(new BuildPlacement("copper-wall", x, 26, 0));
        for(int y = 21; y <= 25; y++) fortifications.add(new BuildPlacement("copper-wall", 27, y, 0));
        fortifications.add(new BuildPlacement("duo", 29, 23, 1));
        fortifications.add(new BuildPlacement("duo", 29, 25, 1));
        trackTurret(29, 23);
        trackTurret(29, 25);
        trackTurret(32, 23);
        trackTurret(32, 25);
    }

    private void dispatchFortifications(){
        for(Agent agent : agents){
            if(agent.stage != Stage.IDLE || fortifications.isEmpty()) continue;
            BuildPlacement build = fortifications.removeFirst();
            buildsInFlight++;
            begin(agent, "demo-fortify-" + taskSequence++, TaskType.BUILD_SCHEMATIC,
                new TileTarget(build.x(), build.y()), ResourceCost.of("copper", copperCost(build.block())),
                new BuildBlock(build.block(), build.x(), build.y(), build.rotation()), Stage.FORTIFY);
        }
    }

    private void prepareSupply(){
        for(TileTarget target : activeTurrets) supplyTargets.add(target);
    }

    private void prepareMaintenanceExpansion(){
        int wallX = waveClears == 1 ? 36 : 39;
        int turretX = wallX - 1;
        for(int y = 21; y <= 27; y++) addExpansion("copper-wall", wallX, y, 0);
        addExpansion("duo", turretX, 23, 1);
        addExpansion("duo", turretX, 25, 1);
        trackTurret(turretX, 23);
        trackTurret(turretX, 25);
        Log.info("AGENT-DEMO EXPANSION START wave=@ planned_blocks=9 planned_turrets=2",
            waveClears);
    }

    private void addExpansion(String block, int x, int y, int rotation){
        BuildPlacement placement = new BuildPlacement(block, x, y, rotation);
        fortifications.add(placement);
        expectedExpansions.add(placement);
    }

    private void trackTurret(int x, int y){
        TileTarget candidate = new TileTarget(x, y);
        if(!activeTurrets.contains(candidate)) activeTurrets.add(candidate);
    }

    private void dispatchSupply(){
        for(Agent agent : agents){
            if(agent.stage != Stage.IDLE || supplyTargets.isEmpty()) continue;
            TileTarget target = supplyTargets.removeFirst();
            suppliesInFlight++;
            begin(agent, "demo-supply-" + taskSequence++, TaskType.SUPPLY_TURRET,
                target, ResourceCost.of("copper", 15),
                new SupplyBuilding("copper", target.x(), target.y(), 15), Stage.SUPPLY);
        }
    }

    private void startDefense(long tick){
        maintenance = false;
        maintenanceSupplyStarted = false;
        fortifications.clear();
        buildsInFlight = 0;
        supplyTargets.clear();
        suppliesInFlight = 0;
        defenseStarted = true;
        for(Agent agent : agents){
            if(agent.taskId != null){
                board.abandon(agent.taskId, agent.id, "enemy_wave", tick);
            }
            cancelControllerWork(agent);
            agent.taskId = null;
            ensureAgentBody(agent);
            begin(agent, "demo-defend-" + taskSequence++, TaskType.DEFEND_REGION,
                new RegionTarget("east_lane"), ResourceCost.empty(),
                new DefendRegion(244f + agent.index * 8f, 196f, 220f, Long.MAX_VALUE), Stage.DEFEND);
        }
    }

    private void startReserveMining(long tick, String reason){
        defenseStarted = false;
        for(Agent agent : agents){
            if(agent.taskId != null){
                board.abandon(agent.taskId, agent.id, reason, tick);
            }
            cancelControllerWork(agent);
            agent.taskId = null;
            ensureAgentBody(agent);
            int[] tile = mineTiles[agent.index];
            begin(agent, "demo-reserve-" + taskSequence++, TaskType.HARVEST_RESOURCE,
                new ResourceTarget("copper", 300), ResourceCost.empty(),
                new MineResource(tile[0], tile[1], 20), Stage.RESERVE_MINE);
        }
        Log.info("AGENT-DEMO RESERVE MINING tick=@ reason=@", tick, reason);
    }

    private int copperCost(String blockName){
        int total = 0;
        var block = content.block(blockName);
        if(block == null) throw new IllegalStateException("unknown demo block: " + blockName);
        for(var requirement : block.requirements){
            if(requirement.item == Items.copper) total += requirement.amount;
        }
        return total;
    }

    private void cancelControllerWork(Agent agent){
        agent.controller.pauseNow();
        agent.controller.clearSkill();
        agent.controller.resumeNow();
        agent.stage = Stage.IDLE;
    }

    private void trackWaves(long tick){
        int enemies = 0;
        for(Unit unit : Groups.unit){
            if(unit.team == scenario.waveTeam && !unit.dead()) enemies++;
        }
        if(previousEnemies == 0 && enemies > 0){
            Building core = scenario.coreTeam.core();
            Log.info("AGENT-DEMO WAVE START tick=@ enemies=@ core_health=@", tick, enemies,
                core == null ? 0 : Math.round(core.health));
            startDefense(tick);
        }else if(previousEnemies > 0 && enemies == 0 && defenseStarted && !maintenance){
            waveClears++;
            Building core = scenario.coreTeam.core();
            Log.info("AGENT-DEMO WAVE CLEAR tick=@ wave=@ core_health=@", tick, waveClears,
                core == null ? 0 : Math.round(core.health));
            if(waveClears < 3){
                startMaintenance(tick);
            }else{
                startReserveMining(tick, "wave_clear");
            }
        }
        previousEnemies = enemies;
    }

    private void startMaintenance(long tick){
        maintenance = true;
        maintenanceStartTick = tick;
        maintenanceSupplyStarted = false;
        maintenanceExpansionPrepared = false;
        maintenanceExpansionReported = false;
        rebuildDone = false;
        defenseStarted = false;
        supplyTargets.clear();
        suppliesInFlight = 0;

        for(Agent agent : agents){
            if(agent.taskId != null){
                board.abandon(agent.taskId, agent.id, "wave_clear_maintenance", tick);
            }
            cancelControllerWork(agent);
            agent.taskId = null;
            agent.maintenanceDone = false;
            agent.maintenanceRounds = 0;
            ensureAgentBody(agent);
        }

        Agent rebuilder = agents.get(0);
        begin(rebuilder, "demo-rebuild-" + taskSequence++, TaskType.REPAIR_REGION,
            new RegionTarget("defense_block"), ResourceCost.empty(),
            new RebuildRegion(20, 18, 40, 30), Stage.REBUILD);
        for(int i = 1; i < agents.size; i++){
            Agent miner = agents.get(i);
            int[] tile = mineTiles[miner.index];
            begin(miner, "demo-maintenance-mine-" + taskSequence++, TaskType.HARVEST_RESOURCE,
                new ResourceTarget("copper", 60), ResourceCost.empty(),
                new MineResource(tile[0], tile[1], 20), Stage.MAINTENANCE_MINE);
        }
        drainAnnouncements();
    }

    private void dispatchMaintenance(){
        long tick = (long)state.tick;
        boolean workReady = rebuildDone && agents.get(1).maintenanceDone && agents.get(2).maintenanceDone;
        if(!workReady && tick - maintenanceStartTick < 900) return;
        if(!workReady){
            Log.warn("AGENT-DEMO MAINTENANCE DEADLINE tick=@; resuming defense safely", tick);
            for(Agent agent : agents){
                if(agent.stage == Stage.IDLE) continue;
                if(agent.taskId != null){
                    board.abandon(agent.taskId, agent.id, "maintenance_deadline", tick);
                    agent.taskId = null;
                }
                cancelControllerWork(agent);
            }
        }
        if(!maintenanceExpansionPrepared){
            prepareMaintenanceExpansion();
            maintenanceExpansionPrepared = true;
        }
        dispatchFortifications();
        if(!fortifications.isEmpty() || buildsInFlight > 0){
            if(tick - maintenanceStartTick < 900) return;
            Log.warn("AGENT-DEMO EXPANSION DEADLINE tick=@ wave=@; supplying completed turrets",
                tick, waveClears);
            fortifications.clear();
            buildsInFlight = 0;
            for(Agent agent : agents){
                if(agent.stage != Stage.FORTIFY) continue;
                if(agent.taskId != null){
                    board.abandon(agent.taskId, agent.id, "expansion_deadline", tick);
                    agent.taskId = null;
                }
                cancelControllerWork(agent);
            }
        }
        if(!maintenanceExpansionReported){
            maintenanceExpansionReported = true;
            if(expansionReady()){
                Log.info("AGENT-DEMO EXPANSION COMPLETE wave=@ turrets=@ blocks=@",
                    waveClears, activeTurrets.size(), expectedExpansions.size());
            }else{
                Log.warn("AGENT-DEMO EXPANSION INCOMPLETE wave=@ turrets=@",
                    waveClears, activeTurrets.size());
            }
        }
        if(!maintenanceSupplyStarted){
            prepareSupply();
            maintenanceSupplyStarted = true;
            maintenanceSupplyStartTick = tick;
        }
        dispatchSupply();
        if(suppliesInFlight > 0 && tick - maintenanceSupplyStartTick >= 300){
            Log.warn("AGENT-DEMO SUPPLY DEADLINE tick=@; resuming defense safely", tick);
            supplyTargets.clear();
            suppliesInFlight = 0;
            for(Agent agent : agents){
                if(agent.stage != Stage.SUPPLY) continue;
                if(agent.taskId != null){
                    board.abandon(agent.taskId, agent.id, "supply_deadline", tick);
                    agent.taskId = null;
                }
                cancelControllerWork(agent);
            }
        }
        if(supplyTargets.isEmpty() && suppliesInFlight == 0){
            maintenance = false;
            maintenanceSupplyStarted = false;
            startReserveMining(tick, "maintenance_complete");
            Log.info("AGENT-DEMO MAINTENANCE COMPLETE tick=@ wave=@", (long)state.tick, waveClears);
        }
    }

    private void ensureAgentBody(Agent agent){
        if(agent.unit != null && agent.unit.isValid() && !agent.unit.dead()) return;
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

    private boolean expansionReady(){
        for(BuildPlacement placement : expectedExpansions){
            Building building = world.build(placement.x(), placement.y());
            if(building == null || !building.block.name.equals(placement.block())) return false;
        }
        return true;
    }

    private void idle(Agent agent){
        agent.stage = Stage.IDLE;
        agent.controller.clearSkill();
    }

    private void complete(Agent agent, long tick){
        if(agent.taskId != null) board.complete(agent.taskId, agent.id, tick);
        agent.taskId = null;
        agent.controller.clearSkill();
    }

    private void abandon(Agent agent, String reason, long tick){
        if(agent.stage == Stage.FORTIFY && buildsInFlight > 0) buildsInFlight--;
        if(agent.stage == Stage.SUPPLY && suppliesInFlight > 0) suppliesInFlight--;
        if(agent.taskId != null) board.abandon(agent.taskId, agent.id, reason, tick);
        agent.taskId = null;
        agent.stage = Stage.IDLE;
        agent.controller.stopNow();
        if(!stopped) agent.controller.resumeNow();
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
        if(!preparationComplete) return;

        List<String> expectedLine = blockNames(scenario.schematic(scenario.buildLineId));
        List<String> expectedDefense = blockNames(scenario.schematic(scenario.referenceSchematicId));
        if(!lineOrder.equals(expectedLine) || !defenseOrder.equals(expectedDefense)){
            throw new IllegalStateException("demo opening order drift: line=" + lineOrder
                + " defense=" + defenseOrder);
        }
        for(TileTarget target : List.of(new TileTarget(29, 23), new TileTarget(29, 25),
                                        new TileTarget(32, 23), new TileTarget(32, 25))){
            Building building = world.build(target.x(), target.y());
            if(building == null || building.block != Blocks.duo){
                throw new IllegalStateException("expert turret missing at " + target.describe());
            }
        }
        if(!status().contains("phase=reserve-mining")){
            throw new IllegalStateException("agents did not enter productive reserve mining");
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

    private String phase(){
        if(defenseStarted) return "defend";
        if(maintenance) return "maintenance";
        for(Agent agent : agents){
            if(agent.stage == Stage.RESERVE_MINE || agent.stage == Stage.RESERVE_DELIVER){
                return "reserve-mining";
            }
        }
        if(supplyStarted) return "supply";
        if(fortificationStarted) return "fortify";
        if(economyStarted) return "economy";
        return started ? "opening" : "waiting";
    }
}
