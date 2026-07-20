package agentcore.candidates;

import agentcore.*;
import agentcore.task.*;
import agentcore.utility.*;

import java.util.*;

/**
 * Deterministic M5.1 candidate rule catalog for bootstrap-defense-v0.
 *
 * <p>Rules run in a fixed semantic order. Repeated entities (turrets) are sorted by
 * stable engine id before expansion. On overflow, the highest-utility tasks are retained
 * with one slot reserved for DEFEND, then restored to semantic order. The WAIT fallback
 * always occupies the final slot, keeping the action surface bounded and never empty.
 */
public final class CandidateGenerator{
    public static final int DEFAULT_MAX_CANDIDATES = 8;

    private static final Set<String> MINE_CAPS = Set.of("carry", "mine");
    private static final Set<String> BUILD_CAPS = Set.of("build");
    private static final Set<String> SUPPLY_CAPS = Set.of("carry");
    private static final Set<String> DEFEND_CAPS = Set.of("combat");
    private static final Set<String> WAIT_CAPS = Set.of("wait");

    private final int maxCandidates;

    public CandidateGenerator(){
        this(DEFAULT_MAX_CANDIDATES);
    }

    public CandidateGenerator(int maxCandidates){
        if(maxCandidates < 1) throw new IllegalArgumentException("maxCandidates must be >= 1");
        this.maxCandidates = maxCandidates;
    }

    public CandidateSet generate(
        AgentSnapshot agent,
        CandidateWorldSnapshot world,
        TaskUtility utility
    ){
        Objects.requireNonNull(agent, "agent");
        Objects.requireNonNull(world, "world");
        Objects.requireNonNull(utility, "utility");

        ArrayList<Pending> pending = new ArrayList<>();
        if(world.coreCopper() < world.harvestCopperThreshold()){
            int deficit = world.harvestCopperThreshold() - world.coreCopper();
            double priority = ratio(deficit, world.harvestCopperThreshold());
            pending.add(new Pending(TaskSpec.builder(world.harvestTaskId() + ":harvest:copper:at-"
                + world.tick(), TaskType.HARVEST_RESOURCE)
                .target(new ResourceTarget("copper", deficit))
                .priority(priority).estimatedTicks(300).requiredCapabilities(MINE_CAPS)
                .build(), world.harvestWorldX(), world.harvestWorldY()));
        }

        if(!world.buildLineComplete()){
            double priority = 1.0 - world.economy().readiness();
            pending.add(new Pending(TaskSpec.builder(world.buildLineTaskId()
                + ":build:" + world.buildLineId() + ":at-" + world.tick(),
                TaskType.BUILD_LINE)
                .target(new RegionTarget(world.buildLineId()))
                .priority(priority).estimatedTicks(600)
                .estimatedCost(ResourceCost.of("copper", world.buildLineCopperCost()))
                .requiredCapabilities(BUILD_CAPS).build(),
                world.buildLineWorldX(), world.buildLineWorldY()));
        }

        if(!world.schematicComplete()){
            double priority = 1.0 - world.defenseReadiness().readiness();
            pending.add(new Pending(TaskSpec.builder(world.schematicTaskId() + ":build:"
                + world.schematicId() + ":at-" + world.tick(), TaskType.BUILD_SCHEMATIC)
                .target(new RegionTarget(world.schematicId()))
                .priority(priority).estimatedTicks(600)
                .estimatedCost(ResourceCost.of("copper", world.schematicCopperCost()))
                .requiredCapabilities(BUILD_CAPS).helpersRequested(1).build(),
                world.schematicWorldX(), world.schematicWorldY()));
        }

        for(PlannedSchematicSnapshot schematic : world.plannedSchematics()){
            if(schematic.complete() || world.waveNumber() < schematic.minimumWave()) continue;
            if(schematic.minimumWave() > 1 && world.enemyCount() > 0) continue;
            pending.add(new Pending(TaskSpec.builder(schematic.taskId(), TaskType.BUILD_SCHEMATIC)
                .target(new RegionTarget(schematic.schematicId()))
                .priority(schematic.priority()).estimatedTicks(900)
                .estimatedCost(ResourceCost.of("copper", schematic.copperCost()))
                .requiredCapabilities(BUILD_CAPS)
                .dependencyTaskIds(schematic.dependencyTaskIds()).build(),
                tileWorld(schematic.anchorX(), world.tileSize()),
                tileWorld(schematic.anchorY(), world.tileSize())));
        }

        ArrayList<TurretSnapshot> turrets = new ArrayList<>(world.turrets());
        turrets.sort(Comparator.comparingLong(TurretSnapshot::entityId));
        for(TurretSnapshot turret : turrets){
            if(turret.totalAmmo() >= world.turretTargetAmmo()) continue;
            int ammoDeficit = world.turretTargetAmmo() - turret.totalAmmo();
            int copper = Math.min((ammoDeficit + 1) / 2,
                Math.max(1, world.coreCopper()));
            double priority = ratio(ammoDeficit, world.turretTargetAmmo());
            pending.add(new Pending(TaskSpec.builder(world.supplyTaskId() + ":supply:"
                + turret.entityId() + ":wave-" + world.waveNumber() + ":at-" + world.tick(),
                TaskType.SUPPLY_TURRET)
                .target(new EntityTarget(turret.entityId()))
                .priority(priority).estimatedTicks(180)
                .estimatedCost(ResourceCost.of("copper", copper))
                .requiredCapabilities(SUPPLY_CAPS).build(),
                tileWorld(turret.tileX(), world.tileSize()),
                tileWorld(turret.tileY(), world.tileSize())));
        }

        if(world.brokenBlockCount() > 0){
            double priority = Math.max(1.0 - world.defenseReadiness().healthCoverage(),
                ratio(world.brokenBlockCount(), 5));
            pending.add(new Pending(TaskSpec.builder(world.rebuildTaskId() + ":rebuild:"
                + world.rebuildRegionId() + ":wave-" + world.waveNumber() + ":at-"
                + world.tick(), TaskType.REPAIR_REGION)
                .target(new RegionTarget(world.rebuildRegionId()))
                .priority(priority).estimatedTicks(300).requiredCapabilities(BUILD_CAPS).build(),
                world.rebuildWorldX(), world.rebuildWorldY()));
        }

        DefenseReadinessSnapshot defense = world.defenseReadiness();
        if(world.enemyCount() > 0 || world.timeToNextWave() <= defense.defendLeadTicks()){
            pending.add(new Pending(TaskSpec.builder(world.defendTaskId() + ":defend:"
                + world.defendRegionId() + ":wave-" + world.waveNumber() + ":agent-"
                + agent.id().index() + ":at-" + world.tick(), TaskType.DEFEND_REGION)
                .target(new RegionTarget(world.defendRegionId()))
                .priority(world.enemyCount() > 0 ? 1.0 : defense.waveImminence())
                .estimatedTicks(Math.max(1, defense.defendLeadTicks()))
                .requiredCapabilities(DEFEND_CAPS)
                .exclusive(false).build(), world.defendWorldX(), world.defendWorldY()));
        }

        Pending wait = new Pending(TaskSpec.builder("runtime:wait", TaskType.WAIT)
            .priority(0.0).estimatedTicks(60).requiredCapabilities(WAIT_CAPS)
            .exclusive(false).build(), agent.worldX(), agent.worldY());

        ArrayList<ScoredPending> scored = new ArrayList<>(pending.size());
        for(int i = 0; i < pending.size(); i++){
            Pending item = pending.get(i);
            String invalid = invalidReason(agent, item);
            scored.add(new ScoredPending(item, invalid,
                utility.score(agent.id(), item.task(), world.tick()), i));
        }

        int taskSlots = maxCandidates - 1;
        if(scored.size() > taskSlots){
            ScoredPending defend = taskSlots == 0 ? null : scored.stream()
                .filter(item -> item.pending().task().type() == TaskType.DEFEND_REGION)
                .findFirst().orElse(null);
            ArrayList<ScoredPending> ranked = new ArrayList<>(scored);
            if(defend != null) ranked.remove(defend);
            ranked.sort(Comparator.comparingDouble(ScoredPending::utility).reversed()
                .thenComparingInt(ScoredPending::semanticIndex));
            int ordinarySlots = taskSlots - (defend == null ? 0 : 1);
            scored = new ArrayList<>(ranked.subList(0, ordinarySlots));
            if(defend != null) scored.add(defend);
            scored.sort(Comparator.comparingInt(ScoredPending::semanticIndex));
        }

        ArrayList<TaskCandidate> result = new ArrayList<>(scored.size() + 1);
        for(ScoredPending item : scored){
            result.add(new TaskCandidate(item.pending().task(), item.invalidReason().isEmpty(),
                item.invalidReason(), item.utility()));
        }
        String waitInvalid = invalidReason(agent, wait);
        result.add(new TaskCandidate(wait.task(), waitInvalid.isEmpty(), waitInvalid,
            utility.score(agent.id(), wait.task(), world.tick())));
        return new CandidateSet(result);
    }

    private static String invalidReason(AgentSnapshot agent, Pending candidate){
        for(String required : candidate.task().requiredCapabilities()){
            if(!agent.capabilities().contains(required)) return "missing_capability:" + required;
        }
        float dx = candidate.worldX() - agent.worldX();
        float dy = candidate.worldY() - agent.worldY();
        if(dx * dx + dy * dy > agent.assignmentRange() * agent.assignmentRange()){
            return "out_of_range";
        }
        return "";
    }

    private static float tileWorld(int tile, int tileSize){
        return tile * (float)tileSize;
    }

    private static double ratio(int numerator, int denominator){
        if(denominator <= 0) return numerator > 0 ? 1.0 : 0.0;
        return Math.max(0.0, Math.min(1.0, numerator / (double)denominator));
    }

    private record Pending(TaskSpec task, float worldX, float worldY){}
    private record ScoredPending(Pending pending, String invalidReason, double utility,
                                 int semanticIndex){}
}
