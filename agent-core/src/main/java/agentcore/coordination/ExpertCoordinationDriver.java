package agentcore.coordination;

import agentcore.*;
import agentcore.board.*;
import agentcore.skill.*;
import agentcore.task.*;
import agentcore.utility.*;

import java.nio.charset.*;
import java.security.*;
import java.util.*;

/**
 * Shared deterministic expert policy and task lifecycle for fixed-step and demo modes.
 * The driver is engine-neutral; a simulation-thread {@link Port} executes its skills.
 */
public final class ExpertCoordinationDriver{
    public enum Stage{
        IDLE, BUILD_LINE, BUILD_DEFENSE, MINE, DELIVER,
        ECONOMY_MINE, ECONOMY_DELIVER, FORTIFY, SUPPLY, DEFEND,
        REBUILD, MAINTENANCE_MINE, MAINTENANCE_DELIVER,
        RECOVERY_MINE, RECOVERY_DELIVER,
        RESERVE_MINE, RESERVE_DELIVER
    }

    public enum SignalType{
        EXPERT_READY, RESERVE_MINING, WAVE_START, WAVE_CLEAR,
        EXPANSION_START, EXPANSION_COMPLETE, EXPANSION_INCOMPLETE,
        MAINTENANCE_DEADLINE, EXPANSION_DEADLINE, SUPPLY_DEADLINE,
        MAINTENANCE_COMPLETE
    }

    public interface Port{
        SkillResult lastResult(int agentIndex);
        Skill activeSkill(int agentIndex);
        void setSkill(int agentIndex, Skill skill);
        void cancelWork(int agentIndex);
        void ensureAgent(int agentIndex);
        boolean agentAvailable(int agentIndex);
        int coreCopper();
        boolean buildingMatches(BuildPlacement placement);
    }

    public record BuildPlacement(String block, int x, int y, int rotation){}

    private record WorkCandidate(
        TaskSpec spec,
        Skill skill,
        Stage stage,
        int semanticIndex
    ){}

    public record PolicyDecision(
        long sequence,
        long tick,
        int agentIndex,
        String kind,
        String taskId,
        TaskType taskType,
        Stage stage,
        String detail
    ){}

    public record Signal(
        SignalType type,
        long tick,
        int wave,
        int enemies,
        int coreHealth,
        int blocks,
        int turrets
    ){}

    private static final String[] names = {"agent-copper", "agent-shield", "agent-relay"};
    private static final long heartbeatInterval = 120L;

    private static final class Agent{
        final int index;
        final AgentId id;
        Stage stage = Stage.IDLE;
        String taskId;
        boolean blocked;
        int recordedBlocks;
        int economyRounds;
        boolean maintenanceDone;

        Agent(int index){
            this.index = index;
            this.id = new AgentId(index, names[index]);
        }
    }

    private final ExpertCoordinationPlan plan;
    private final Port port;
    private final HandTunedUtility utility;
    private final boolean blockedVariant;
    private final TaskBoard board = new TaskBoard();
    private final Agent[] agents = new Agent[names.length];
    private final List<String> lineOrder = new ArrayList<>();
    private final List<String> defenseOrder = new ArrayList<>();
    private final ArrayDeque<BuildPlacement> fortifications = new ArrayDeque<>();
    private final ArrayDeque<TileTarget> supplyTargets = new ArrayDeque<>();
    private final List<TileTarget> activeTurrets = new ArrayList<>();
    private final List<BuildPlacement> expectedExpansions = new ArrayList<>();
    private final List<PolicyDecision> decisions = new ArrayList<>();
    private final ArrayDeque<Signal> signals = new ArrayDeque<>();

    private boolean started;
    private boolean blockedSetup;
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
    private boolean recoveryActive;
    private long lastHeartbeat;
    private long decisionSequence;
    private int buildsInFlight;
    private int suppliesInFlight;
    private int taskSequence;
    private int previousEnemies;
    private int waveClears;
    private int openingFortificationCount;
    private long maintenanceStartTick;
    private long maintenanceSupplyStartTick;
    private long lastUpdateTick;
    private long firstLineBlockTick;
    private int resourcesShortBlocks;
    private int resourceReplans;

    public ExpertCoordinationDriver(ExpertCoordinationPlan plan, Port port){
        this(plan, port, false);
    }

    public ExpertCoordinationDriver(
        ExpertCoordinationPlan plan,
        Port port,
        boolean blockedVariant
    ){
        this.plan = Objects.requireNonNull(plan, "plan");
        this.port = Objects.requireNonNull(port, "port");
        this.blockedVariant = blockedVariant;
        this.utility = new HandTunedUtility(this::utilityFeatures);
        for(int i = 0; i < agents.length; i++) agents[i] = new Agent(i);
    }

    public TaskBoard board(){ return board; }
    public boolean started(){ return started; }
    public boolean preparationComplete(){ return preparationComplete; }
    public boolean defenseStarted(){ return defenseStarted; }
    public boolean maintenance(){ return maintenance; }
    public int waveClears(){ return waveClears; }
    public int openingFortificationCount(){ return openingFortificationCount; }
    public String policyName(){ return "greedy-utility-expert-v1"; }
    public int resourcesShortBlocks(){ return resourcesShortBlocks; }
    public int resourceReplans(){ return resourceReplans; }
    public long firstLineBlockTick(){ return firstLineBlockTick; }
    public List<String> lineOrder(){ return List.copyOf(lineOrder); }
    public List<String> defenseOrder(){ return List.copyOf(defenseOrder); }
    public List<TileTarget> activeTurrets(){ return List.copyOf(activeTurrets); }
    public List<BuildPlacement> expectedExpansions(){ return List.copyOf(expectedExpansions); }
    public List<PolicyDecision> decisions(){ return List.copyOf(decisions); }
    public long selectionCount(){
        return decisions.stream().filter(decision -> decision.kind().equals("SELECT_TASK")).count();
    }

    /** Stable digest of task selections, intentionally independent of runtime pacing/ticks. */
    public String selectionDigest(){
        try{
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for(PolicyDecision decision : decisions){
                if(!decision.kind().equals("SELECT_TASK")) continue;
                String row = decision.agentIndex() + "\u001f" + decision.taskId() + "\u001f"
                    + (decision.taskType() == null ? "" : decision.taskType().name()) + "\u001f"
                    + decision.stage().name() + "\u001f" + decision.detail() + "\n";
                digest.update(row.getBytes(StandardCharsets.UTF_8));
            }
            return HexFormat.of().formatHex(digest.digest());
        }catch(NoSuchAlgorithmException e){
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    public void reset(long episodeId){
        board.reset(episodeId);
        for(Agent agent : agents){
            agent.stage = Stage.IDLE;
            agent.taskId = null;
            agent.blocked = false;
            agent.recordedBlocks = 0;
            agent.economyRounds = 0;
            agent.maintenanceDone = false;
        }
        lineOrder.clear();
        defenseOrder.clear();
        fortifications.clear();
        supplyTargets.clear();
        activeTurrets.clear();
        expectedExpansions.clear();
        decisions.clear();
        signals.clear();
        started = false;
        blockedSetup = false;
        lineComplete = false;
        baseDefenseComplete = false;
        economyStarted = false;
        fortificationStarted = false;
        supplyStarted = false;
        preparationComplete = false;
        defenseStarted = false;
        maintenance = false;
        maintenanceSupplyStarted = false;
        maintenanceExpansionPrepared = false;
        maintenanceExpansionReported = false;
        rebuildDone = false;
        recoveryActive = false;
        lastHeartbeat = 0L;
        decisionSequence = 0L;
        buildsInFlight = 0;
        suppliesInFlight = 0;
        taskSequence = 0;
        previousEnemies = 0;
        waveClears = 0;
        openingFortificationCount = 0;
        maintenanceStartTick = 0L;
        maintenanceSupplyStartTick = 0L;
        lastUpdateTick = Long.MIN_VALUE;
        firstLineBlockTick = -1L;
        resourcesShortBlocks = 0;
        resourceReplans = 0;
    }

    public void startOpening(long tick){
        if(started) return;
        started = true;
        if(blockedVariant){
            blockedSetup = true;
            for(int y = 4; y < 29; y++){
                fortifications.add(new BuildPlacement("copper-wall", 10, y, 0));
            }
            record(tick, null, "PLAN_BLOCKED_VARIANT", "", null,
                "legal_prespent_walls=" + fortifications.size());
            return;
        }
        beginOpening(tick);
    }

    private void beginOpening(long tick){
        ArrayList<WorkCandidate> candidates = new ArrayList<>();
        candidates.add(work("demo-line", TaskType.BUILD_LINE,
            new TileTarget(plan.line().anchorX(), plan.line().anchorY()),
            ResourceCost.of("copper", plan.line().copperCost()),
            new ExecuteSchematic(plan.line().name(), plan.line().anchorX(),
                plan.line().anchorY(), plan.line().blocks()), Stage.BUILD_LINE, 0.88, 0));
        candidates.add(work("demo-defense", TaskType.BUILD_SCHEMATIC,
            new TileTarget(plan.defense().anchorX(), plan.defense().anchorY()),
            ResourceCost.of("copper", plan.defense().copperCost()),
            new ExecuteSchematic(plan.defense().name(), plan.defense().anchorX(),
                plan.defense().anchorY(), plan.defense().blocks()), Stage.BUILD_DEFENSE, 0.90, 1));
        TileTarget mine = plan.mineTiles().get(2);
        candidates.add(work("demo-harvest", TaskType.HARVEST_RESOURCE,
            new ResourceTarget("copper", 300), ResourceCost.empty(),
            new MineResource(mine.x(), mine.y(), 20), Stage.MINE, 0.70, 2));
        for(Agent agent : agents){
            WorkCandidate selected = select(agent, candidates, tick);
            if(selected == null) continue;
            candidates.remove(selected);
            begin(agent, selected.spec(), selected.skill(), selected.stage(), tick);
        }
    }

    /** Advance lifecycle and policy once for an authoritative simulation snapshot. */
    public void update(long tick, int enemies, int coreHealth){
        if(!started) return;
        if(tick <= lastUpdateTick) return;
        lastUpdateTick = tick;
        for(Agent agent : agents){
            updateBuildOrder(agent, tick);
            SkillResult result = port.lastResult(agent.index);
            if(result == null) result = SkillResult.ready();
            if(tick - lastHeartbeat >= heartbeatInterval && agent.taskId != null){
                board.heartbeat(agent.taskId, agent.id, tick);
                board.reportProgress(agent.taskId, agent.id, result.progress(), tick);
            }
            if(result.status() == SkillStatus.BLOCKED && !agent.blocked && agent.taskId != null){
                agent.blocked = true;
                if(result.reason() == SkillReason.RESOURCES_SHORT) resourcesShortBlocks++;
                board.reportBlocked(agent.taskId, agent.id,
                    result.reason().name().toLowerCase(Locale.ROOT), tick);
                if((result.reason() == SkillReason.RESOURCES_SHORT
                    || result.reason() == SkillReason.CORE_SHORT)
                    && startResourceRecovery(agent, tick)) continue;
            }else if(result.status() == SkillStatus.RUNNING && agent.blocked && agent.taskId != null){
                agent.blocked = false;
                board.reportProgress(agent.taskId, agent.id, result.progress(), tick);
            }
            if(result.status() == SkillStatus.SUCCEEDED){
                advance(agent, tick);
            }else if(result.status() == SkillStatus.FAILED || result.status() == SkillStatus.CANCELLED){
                abandon(agent, result.reason().name().toLowerCase(Locale.ROOT), tick);
            }
        }
        trackWaves(tick, enemies, coreHealth);
        if(tick - lastHeartbeat >= heartbeatInterval) lastHeartbeat = tick;
        board.expireStale(tick);
        dispatchPolicy(tick);
    }

    public void stop(long tick, String reason){
        for(Agent agent : agents){
            port.cancelWork(agent.index);
            if(agent.taskId != null){
                board.abandon(agent.taskId, agent.id, reason, tick);
                record(tick, agent, "ABANDON_TASK", agent.taskId, null, reason);
                agent.taskId = null;
            }
            agent.stage = Stage.IDLE;
        }
    }

    public List<Signal> drainSignals(){
        ArrayList<Signal> result = new ArrayList<>(signals);
        signals.clear();
        return List.copyOf(result);
    }

    public String phase(){
        if(blockedSetup) return "blocked-setup";
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

    private void begin(Agent agent, String taskId, TaskType type, Target target,
                       ResourceCost cost, Skill skill, Stage stage, long tick){
        TaskSpec spec = TaskSpec.builder(taskId, type)
            .target(target)
            .priority(1.0)
            .estimatedTicks(900)
            .estimatedCost(cost)
            .requiredCapabilities(Set.of(skill.type().toLowerCase(Locale.ROOT)))
            .build();
        begin(agent, spec, skill, stage, tick);
    }

    private void begin(Agent agent, TaskSpec spec, Skill skill, Stage stage, long tick){
        double score = utility.score(agent.id, spec, tick);
        String taskId = spec.taskId();
        board.propose(spec, tick);
        board.announceIntent(taskId, agent.id, score, tick);
        board.claim(taskId, agent.id, score, tick);
        board.start(taskId, agent.id, tick);
        agent.taskId = taskId;
        agent.stage = stage;
        agent.blocked = false;
        agent.recordedBlocks = 0;
        port.setSkill(agent.index, skill);
        record(tick, agent, "UTILITY_SCORE", taskId, spec.type(),
            String.format(Locale.ROOT, "%.6f", score));
        record(tick, agent, "SELECT_TASK", taskId, spec.type(), skill.type());
    }

    private WorkCandidate work(
        String taskId,
        TaskType type,
        Target target,
        ResourceCost cost,
        Skill skill,
        Stage stage,
        double priority,
        int semanticIndex
    ){
        TaskSpec spec = TaskSpec.builder(taskId, type)
            .target(target)
            .priority(priority)
            .estimatedTicks(900)
            .estimatedCost(cost)
            .requiredCapabilities(Set.of(skill.type().toLowerCase(Locale.ROOT)))
            .build();
        return new WorkCandidate(spec, skill, stage, semanticIndex);
    }

    private WorkCandidate select(Agent agent, List<WorkCandidate> candidates, long tick){
        WorkCandidate best = null;
        double bestScore = Double.NEGATIVE_INFINITY;
        for(WorkCandidate candidate : candidates){
            double score = utility.score(agent.id, candidate.spec(), tick);
            if(best == null || score > bestScore
                || (Double.compare(score, bestScore) == 0
                    && candidate.semanticIndex() < best.semanticIndex())){
                best = candidate;
                bestScore = score;
            }
        }
        return best;
    }

    private UtilityFeatures utilityFeatures(AgentId agentId, TaskSpec task, long tick){
        Agent agent = agentId.index() >= 0 && agentId.index() < agents.length
            ? agents[agentId.index()] : null;
        int copper = Math.max(1, port.coreCopper());
        double resourceCost = clamp(task.estimatedCost().amount("copper") / (double)copper);
        double danger = task.type() == TaskType.DEFEND_REGION ? 0.0
            : clamp(previousEnemies / 5.0);
        return UtilityFeatures.builder()
            .teamValue(task.priority())
            .urgency(taskUrgency(task.type()))
            .capabilityFit(agent != null && port.agentAvailable(agent.index) ? 1.0 : 0.0)
            .roleFit(agent == null ? 0.0 : roleFit(agent.index, task.type()))
            .helpSynergy(task.helpersRequested() > 0 ? 1.0 : 0.0)
            .resourceCost(resourceCost)
            .danger(danger)
            .build();
    }

    private double taskUrgency(TaskType type){
        return switch(type){
            case DEFEND_REGION -> previousEnemies > 0 ? 1.0 : 0.85;
            case REPAIR_REGION -> maintenance ? 1.0 : 0.4;
            case SUPPLY_TURRET -> supplyStarted || maintenanceSupplyStarted ? 0.9 : 0.5;
            case BUILD_LINE, BUILD_SCHEMATIC -> preparationComplete ? 0.6 : 1.0;
            case HARVEST_RESOURCE -> preparationComplete ? 0.65 : 0.8;
            default -> 0.2;
        };
    }

    private static double roleFit(int agentIndex, TaskType type){
        return switch(agentIndex){
            case 0 -> switch(type){
                case BUILD_LINE, BUILD_SCHEMATIC, REPAIR_REGION -> 1.0;
                case SUPPLY_TURRET -> 0.6;
                default -> 0.35;
            };
            case 1 -> switch(type){
                case BUILD_SCHEMATIC, SUPPLY_TURRET, DEFEND_REGION -> 1.0;
                case REPAIR_REGION -> 0.6;
                default -> 0.4;
            };
            default -> switch(type){
                case HARVEST_RESOURCE, DEFEND_REGION -> 1.0;
                case SUPPLY_TURRET -> 0.7;
                default -> 0.35;
            };
        };
    }

    private static double clamp(double value){
        return Math.max(0.0, Math.min(1.0, value));
    }

    private void replaceSkill(Agent agent, Skill skill, Stage stage, long tick){
        agent.stage = stage;
        port.setSkill(agent.index, skill);
        record(tick, agent, "CONTINUE_TASK", agent.taskId, null, skill.type());
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
            case MINE -> replaceSkill(agent, new DeliverToCore(), Stage.DELIVER, tick);
            case DELIVER -> {
                if(agent.taskId != null) board.reportProgress(agent.taskId, agent.id, 0.5, tick);
                TileTarget tile = plan.mineTiles().get(agent.index);
                replaceSkill(agent, new MineResource(tile.x(), tile.y(), 20), Stage.MINE, tick);
            }
            case ECONOMY_MINE -> replaceSkill(agent, new DeliverToCore(), Stage.ECONOMY_DELIVER, tick);
            case ECONOMY_DELIVER -> {
                agent.economyRounds++;
                if(agent.economyRounds < 2){
                    TileTarget tile = plan.mineTiles().get(agent.index);
                    replaceSkill(agent, new MineResource(tile.x(), tile.y(), 20),
                        Stage.ECONOMY_MINE, tick);
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
            case MAINTENANCE_MINE -> replaceSkill(agent, new DeliverToCore(),
                Stage.MAINTENANCE_DELIVER, tick);
            case MAINTENANCE_DELIVER -> {
                complete(agent, tick);
                agent.maintenanceDone = true;
                idle(agent);
            }
            case RECOVERY_MINE -> replaceSkill(agent, new DeliverToCore(),
                Stage.RECOVERY_DELIVER, tick);
            case RECOVERY_DELIVER -> {
                complete(agent, tick);
                recoveryActive = false;
                idle(agent);
            }
            case RESERVE_MINE -> replaceSkill(agent, new DeliverToCore(), Stage.RESERVE_DELIVER, tick);
            case RESERVE_DELIVER -> {
                if(agent.taskId != null) board.reportProgress(agent.taskId, agent.id, 0.05, tick);
                TileTarget tile = plan.mineTiles().get(agent.index);
                replaceSkill(agent, new MineResource(tile.x(), tile.y(), 20), Stage.RESERVE_MINE, tick);
            }
            case DEFEND, IDLE -> { }
        }
    }

    private void dispatchPolicy(long tick){
        if(blockedSetup){
            dispatchFortifications(tick);
            if(fortifications.isEmpty() && buildsInFlight == 0){
                blockedSetup = false;
                beginOpening(tick);
            }
            return;
        }
        if(maintenance){
            dispatchMaintenance(tick);
            return;
        }
        if(defenseStarted) return;
        if(!economyStarted && lineComplete && baseDefenseComplete){
            startEconomy(tick);
            return;
        }
        if(economyStarted && !fortificationStarted && allEconomyReady()){
            prepareFortifications(tick);
            fortificationStarted = true;
        }
        if(fortificationStarted && !supplyStarted){
            dispatchFortifications(tick);
            if(fortifications.isEmpty() && buildsInFlight == 0){
                prepareSupply();
                supplyStarted = true;
            }
        }
        if(supplyStarted && !preparationComplete){
            dispatchSupply(tick);
            if(supplyTargets.isEmpty() && suppliesInFlight == 0){
                preparationComplete = true;
                signal(SignalType.EXPERT_READY, tick, 0, 0, 0,
                    openingFortificationCount, activeTurrets.size());
                startReserveMining(tick, "opening_complete");
            }
        }
    }

    private void startEconomy(long tick){
        economyStarted = true;
        for(Agent agent : agents){
            transitionAway(agent, "opening_economy_transition", tick);
            agent.economyRounds = 0;
            TileTarget tile = plan.mineTiles().get(agent.index);
            begin(agent, "demo-economy-" + agent.index, TaskType.HARVEST_RESOURCE,
                new ResourceTarget("copper", 40), ResourceCost.empty(),
                new MineResource(tile.x(), tile.y(), 20), Stage.ECONOMY_MINE, tick);
        }
    }

    private boolean allEconomyReady(){
        for(Agent agent : agents){
            if(agent.economyRounds < 2 || agent.stage != Stage.IDLE) return false;
        }
        return true;
    }

    private void prepareFortifications(long tick){
        ExpertCoordinationPlan.Schematic schematic = plan.fortification();
        for(BuildSpec block : schematic.blocks()){
            int x = schematic.anchorX() + block.offsetX();
            int y = schematic.anchorY() + block.offsetY();
            fortifications.add(new BuildPlacement(block.block(), x, y, block.rotation()));
            if(block.block().equals("duo")) trackTurret(x, y);
        }
        for(TileTarget target : plan.referenceTurrets()) trackTurret(target.x(), target.y());
        openingFortificationCount = fortifications.size();
        record(tick, null, "PLAN_OPENING", "", null,
            "blocks=" + openingFortificationCount + ",turrets=" + activeTurrets.size());
    }

    private void dispatchFortifications(long tick){
        for(Agent agent : agents){
            if(agent.stage != Stage.IDLE || !port.agentAvailable(agent.index)
                || fortifications.isEmpty()) continue;
            LinkedHashMap<WorkCandidate, BuildPlacement> options = new LinkedHashMap<>();
            int semantic = 0;
            for(BuildPlacement build : fortifications){
                WorkCandidate candidate = work(
                    "demo-fortify-" + taskSequence + "-" + semantic,
                    TaskType.BUILD_SCHEMATIC, new TileTarget(build.x(), build.y()),
                    ResourceCost.of("copper", plan.copperCost(build.block())),
                    new BuildBlock(build.block(), build.x(), build.y(), build.rotation()),
                    Stage.FORTIFY, 0.92, semantic++);
                options.put(candidate, build);
            }
            WorkCandidate selected = select(agent, new ArrayList<>(options.keySet()), tick);
            if(selected == null) continue;
            BuildPlacement build = options.get(selected);
            fortifications.remove(build);
            buildsInFlight++;
            taskSequence++;
            begin(agent, selected.spec(), selected.skill(), selected.stage(), tick);
        }
    }

    private void prepareSupply(){
        supplyTargets.addAll(activeTurrets);
    }

    private void prepareMaintenanceExpansion(long tick){
        int blocksBefore = expectedExpansions.size();
        int turretsBefore = activeTurrets.size();
        ExpertCoordinationPlan.Schematic schematic = plan.expansions().get(waveClears - 1);
        for(BuildSpec block : schematic.blocks()){
            int x = schematic.anchorX() + block.offsetX();
            int y = schematic.anchorY() + block.offsetY();
            addExpansion(block.block(), x, y, block.rotation());
            if(block.block().equals("duo")) trackTurret(x, y);
        }
        int blocks = expectedExpansions.size() - blocksBefore;
        int turrets = activeTurrets.size() - turretsBefore;
        signal(SignalType.EXPANSION_START, tick, waveClears, 0, 0, blocks, turrets);
        record(tick, null, "PLAN_EXPANSION", "", null,
            "wave=" + waveClears + ",blocks=" + blocks + ",turrets=" + turrets);
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

    private void dispatchSupply(long tick){
        for(Agent agent : agents){
            if(agent.stage != Stage.IDLE || !port.agentAvailable(agent.index)
                || supplyTargets.isEmpty()) continue;
            LinkedHashMap<WorkCandidate, TileTarget> options = new LinkedHashMap<>();
            int semantic = 0;
            for(TileTarget target : supplyTargets){
                WorkCandidate candidate = work(
                    "demo-supply-" + taskSequence + "-" + semantic,
                    TaskType.SUPPLY_TURRET, target, ResourceCost.of("copper", 15),
                    new SupplyBuilding("copper", target.x(), target.y(), 15),
                    Stage.SUPPLY, 0.85, semantic++);
                options.put(candidate, target);
            }
            WorkCandidate selected = select(agent, new ArrayList<>(options.keySet()), tick);
            if(selected == null) continue;
            TileTarget target = options.get(selected);
            supplyTargets.remove(target);
            suppliesInFlight++;
            taskSequence++;
            begin(agent, selected.spec(), selected.skill(), selected.stage(), tick);
        }
    }

    private void startDefense(long tick){
        maintenance = false;
        recoveryActive = false;
        maintenanceSupplyStarted = false;
        fortifications.clear();
        buildsInFlight = 0;
        supplyTargets.clear();
        suppliesInFlight = 0;
        defenseStarted = true;
        ExpertCoordinationPlan.Region region = plan.defendRegion();
        for(Agent agent : agents){
            transitionAway(agent, "enemy_wave", tick);
            port.ensureAgent(agent.index);
            if(!port.agentAvailable(agent.index)) continue;
            begin(agent, "demo-defend-" + taskSequence++, TaskType.DEFEND_REGION,
                new RegionTarget(region.id()), ResourceCost.empty(),
                new DefendRegion(regionHoldX(region) + agent.index * plan.tileSize(),
                    regionCenterY(region), regionRadius(region), Long.MAX_VALUE),
                Stage.DEFEND, tick);
        }
    }

    private void startReserveMining(long tick, String reason){
        defenseStarted = false;
        for(Agent agent : agents){
            transitionAway(agent, reason, tick);
            port.ensureAgent(agent.index);
            if(!port.agentAvailable(agent.index)) continue;
            TileTarget tile = plan.mineTiles().get(agent.index);
            begin(agent, "demo-reserve-" + taskSequence++, TaskType.HARVEST_RESOURCE,
                new ResourceTarget("copper", 300), ResourceCost.empty(),
                new MineResource(tile.x(), tile.y(), 20), Stage.RESERVE_MINE, tick);
        }
        signal(SignalType.RESERVE_MINING, tick, waveClears, 0, 0, 0, activeTurrets.size());
    }

    private void trackWaves(long tick, int enemies, int coreHealth){
        if(previousEnemies == 0 && enemies > 0){
            signal(SignalType.WAVE_START, tick, waveClears + 1, enemies, coreHealth, 0,
                activeTurrets.size());
            startDefense(tick);
        }else if(previousEnemies > 0 && enemies == 0 && defenseStarted && !maintenance){
            waveClears++;
            signal(SignalType.WAVE_CLEAR, tick, waveClears, 0, coreHealth, 0,
                activeTurrets.size());
            if(waveClears < plan.waveCount()){
                startMaintenance(tick);
            }else{
                startReserveMining(tick, "wave_clear");
            }
        }
        previousEnemies = enemies;
    }

    private void startMaintenance(long tick){
        maintenance = true;
        recoveryActive = false;
        maintenanceStartTick = tick;
        maintenanceSupplyStarted = false;
        maintenanceExpansionPrepared = false;
        maintenanceExpansionReported = false;
        rebuildDone = false;
        defenseStarted = false;
        supplyTargets.clear();
        suppliesInFlight = 0;

        for(Agent agent : agents){
            transitionAway(agent, "wave_clear_maintenance", tick);
            port.ensureAgent(agent.index);
            agent.maintenanceDone = !port.agentAvailable(agent.index);
        }

        ExpertCoordinationPlan.Region region = plan.rebuildRegion();
        if(port.agentAvailable(agents[0].index)){
            begin(agents[0], "demo-rebuild-" + taskSequence++, TaskType.REPAIR_REGION,
                new RegionTarget(region.id()), ResourceCost.empty(),
                new RebuildRegion(region.x(), region.y(), region.x() + region.w() - 1,
                    region.y() + region.h() - 1), Stage.REBUILD, tick);
        }else{
            rebuildDone = true;
        }
        for(int i = 1; i < agents.length; i++){
            Agent miner = agents[i];
            if(!port.agentAvailable(miner.index)) continue;
            TileTarget tile = plan.mineTiles().get(miner.index);
            begin(miner, "demo-maintenance-mine-" + taskSequence++,
                TaskType.HARVEST_RESOURCE, new ResourceTarget("copper", 60),
                ResourceCost.empty(), new MineResource(tile.x(), tile.y(), 20),
                Stage.MAINTENANCE_MINE, tick);
        }
    }

    private void dispatchMaintenance(long tick){
        boolean workReady = rebuildDone && agents[1].maintenanceDone && agents[2].maintenanceDone;
        if(!workReady && tick - maintenanceStartTick < 900) return;
        if(!workReady){
            signal(SignalType.MAINTENANCE_DEADLINE, tick, waveClears, 0, 0, 0,
                activeTurrets.size());
            for(Agent agent : agents){
                if(agent.stage != Stage.IDLE) transitionAway(agent, "maintenance_deadline", tick);
            }
        }
        if(!maintenanceExpansionPrepared){
            prepareMaintenanceExpansion(tick);
            maintenanceExpansionPrepared = true;
        }
        dispatchFortifications(tick);
        if(!fortifications.isEmpty() || buildsInFlight > 0){
            if(tick - maintenanceStartTick < 900) return;
            signal(SignalType.EXPANSION_DEADLINE, tick, waveClears, 0, 0,
                expectedExpansions.size(), activeTurrets.size());
            fortifications.clear();
            buildsInFlight = 0;
            for(Agent agent : agents){
                if(agent.stage == Stage.FORTIFY) transitionAway(agent, "expansion_deadline", tick);
            }
        }
        if(!maintenanceExpansionReported){
            maintenanceExpansionReported = true;
            signal(expansionReady() ? SignalType.EXPANSION_COMPLETE : SignalType.EXPANSION_INCOMPLETE,
                tick, waveClears, 0, 0, expectedExpansions.size(), activeTurrets.size());
        }
        if(!maintenanceSupplyStarted){
            prepareSupply();
            maintenanceSupplyStarted = true;
            maintenanceSupplyStartTick = tick;
        }
        dispatchSupply(tick);
        if(suppliesInFlight > 0 && tick - maintenanceSupplyStartTick >= 300){
            signal(SignalType.SUPPLY_DEADLINE, tick, waveClears, 0, 0, 0,
                activeTurrets.size());
            supplyTargets.clear();
            suppliesInFlight = 0;
            for(Agent agent : agents){
                if(agent.stage == Stage.SUPPLY) transitionAway(agent, "supply_deadline", tick);
            }
        }
        if(supplyTargets.isEmpty() && suppliesInFlight == 0){
            maintenance = false;
            maintenanceSupplyStarted = false;
            startReserveMining(tick, "maintenance_complete");
            signal(SignalType.MAINTENANCE_COMPLETE, tick, waveClears, 0, 0,
                expectedExpansions.size(), activeTurrets.size());
        }
    }

    private boolean expansionReady(){
        for(BuildPlacement placement : expectedExpansions){
            if(!port.buildingMatches(placement)) return false;
        }
        return true;
    }

    private boolean startResourceRecovery(Agent agent, long tick){
        if(recoveryActive) return false;
        Skill active = port.activeSkill(agent.index);
        if(agent.stage == Stage.FORTIFY && active instanceof BuildBlock build){
            fortifications.addFirst(new BuildPlacement(build.block(), build.tileX(),
                build.tileY(), build.rotation()));
            if(buildsInFlight > 0) buildsInFlight--;
        }else if(agent.stage == Stage.SUPPLY && active instanceof SupplyBuilding supply){
            supplyTargets.addFirst(new TileTarget(supply.tileX(), supply.tileY()));
            if(suppliesInFlight > 0) suppliesInFlight--;
        }else{
            return false;
        }

        transitionAway(agent, "resources_short_replan", tick);
        recoveryActive = true;
        resourceReplans++;
        TileTarget tile = plan.mineTiles().get(agent.index);
        begin(agent, "demo-recovery-" + taskSequence++, TaskType.HARVEST_RESOURCE,
            new ResourceTarget("copper", 20), ResourceCost.empty(),
            new MineResource(tile.x(), tile.y(), 20), Stage.RECOVERY_MINE, tick);
        return true;
    }

    private void transitionAway(Agent agent, String reason, long tick){
        if(agent.taskId != null){
            board.abandon(agent.taskId, agent.id, reason, tick);
            record(tick, agent, "ABANDON_TASK", agent.taskId, null, reason);
        }
        port.cancelWork(agent.index);
        agent.taskId = null;
        agent.stage = Stage.IDLE;
    }

    private void idle(Agent agent){
        agent.stage = Stage.IDLE;
        port.cancelWork(agent.index);
    }

    private void complete(Agent agent, long tick){
        if(agent.taskId != null){
            board.complete(agent.taskId, agent.id, tick);
            record(tick, agent, "COMPLETE_TASK", agent.taskId, null, "");
        }
        agent.taskId = null;
        port.cancelWork(agent.index);
    }

    private void abandon(Agent agent, String reason, long tick){
        if(agent.stage == Stage.FORTIFY && buildsInFlight > 0) buildsInFlight--;
        if(agent.stage == Stage.SUPPLY && suppliesInFlight > 0) suppliesInFlight--;
        if(agent.taskId != null){
            board.abandon(agent.taskId, agent.id, reason, tick);
            record(tick, agent, "ABANDON_TASK", agent.taskId, null, reason);
        }
        agent.taskId = null;
        agent.stage = Stage.IDLE;
        port.cancelWork(agent.index);
    }

    private void updateBuildOrder(Agent agent, long tick){
        if(!(port.activeSkill(agent.index) instanceof ExecuteSchematic active)) return;
        ExpertCoordinationPlan.Schematic spec = agent.stage == Stage.BUILD_LINE
            ? plan.line() : plan.defense();
        List<String> output = agent.stage == Stage.BUILD_LINE ? lineOrder : defenseOrder;
        while(agent.recordedBlocks < active.completed()){
            if(agent.stage == Stage.BUILD_LINE && agent.recordedBlocks == 0
                && firstLineBlockTick < 0) firstLineBlockTick = tick;
            output.add(spec.blocks().get(agent.recordedBlocks).block());
            agent.recordedBlocks++;
        }
    }

    private float regionHoldX(ExpertCoordinationPlan.Region region){
        return (region.x() + (region.w() - 1) / 4f) * plan.tileSize();
    }

    private float regionCenterY(ExpertCoordinationPlan.Region region){
        return (region.y() + (region.h() - 1) / 2f) * plan.tileSize();
    }

    private float regionRadius(ExpertCoordinationPlan.Region region){
        return (float)Math.hypot(region.w() * plan.tileSize(), region.h() * plan.tileSize());
    }

    private void record(long tick, Agent agent, String kind, String taskId,
                        TaskType taskType, String detail){
        decisions.add(new PolicyDecision(decisionSequence++, tick,
            agent == null ? -1 : agent.index, kind, taskId == null ? "" : taskId,
            taskType, agent == null ? Stage.IDLE : agent.stage, detail == null ? "" : detail));
    }

    private void signal(SignalType type, long tick, int wave, int enemies,
                        int coreHealth, int blocks, int turrets){
        signals.add(new Signal(type, tick, wave, enemies, coreHealth, blocks, turrets));
    }
}
