package agentcore.candidates;

import agentcore.*;
import agentcore.task.*;
import agentcore.utility.*;

import java.util.*;

/**
 * Deterministic M5.1 candidate rule catalog for bootstrap-defense-v0.
 *
 * <p>Rules run in a fixed semantic order. Repeated entities (turrets) are sorted by
 * stable engine id before expansion. The WAIT fallback always occupies the final slot
 * if truncation is required, keeping the action surface bounded and never empty.
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
            pending.add(new Pending(TaskSpec.builder(world.harvestTaskId() + ":harvest:copper", TaskType.HARVEST_RESOURCE)
                .target(new ResourceTarget("copper", deficit))
                .priority(0.70).estimatedTicks(300).requiredCapabilities(MINE_CAPS)
                .build(), world.harvestWorldX(), world.harvestWorldY()));
        }

        if(!world.schematicComplete()){
            pending.add(new Pending(TaskSpec.builder(world.schematicTaskId() + ":build:" + world.schematicId(), TaskType.BUILD_SCHEMATIC)
                .target(new RegionTarget(world.schematicId()))
                .priority(0.90).estimatedTicks(600)
                .estimatedCost(ResourceCost.of("copper", world.schematicCopperCost()))
                .requiredCapabilities(BUILD_CAPS).helpersRequested(1).build(),
                world.schematicWorldX(), world.schematicWorldY()));
        }

        ArrayList<TurretSnapshot> turrets = new ArrayList<>(world.turrets());
        turrets.sort(Comparator.comparingLong(TurretSnapshot::entityId));
        for(TurretSnapshot turret : turrets){
            if(turret.totalAmmo() >= world.turretTargetAmmo()) continue;
            int ammoDeficit = world.turretTargetAmmo() - turret.totalAmmo();
            int copper = (ammoDeficit + 1) / 2;
            pending.add(new Pending(TaskSpec.builder(world.supplyTaskId() + ":supply:" + turret.entityId(), TaskType.SUPPLY_TURRET)
                .target(new EntityTarget(turret.entityId()))
                .priority(0.85).estimatedTicks(180)
                .estimatedCost(ResourceCost.of("copper", copper))
                .requiredCapabilities(SUPPLY_CAPS)
                .dependencyTaskIds(List.of(world.schematicTaskId() + ":build:" + world.schematicId())).build(),
                tileWorld(turret.tileX(), world.tileSize()),
                tileWorld(turret.tileY(), world.tileSize())));
        }

        if(world.brokenBlockCount() > 0){
            pending.add(new Pending(TaskSpec.builder(world.rebuildTaskId() + ":rebuild:" + world.rebuildRegionId(), TaskType.REPAIR_REGION)
                .target(new RegionTarget(world.rebuildRegionId()))
                .priority(0.80).estimatedTicks(300).requiredCapabilities(BUILD_CAPS).build(),
                world.rebuildWorldX(), world.rebuildWorldY()));
        }

        if(world.enemyCount() > 0 || world.timeToNextWave() <= world.defendLeadTicks()){
            pending.add(new Pending(TaskSpec.builder(world.defendTaskId() + ":defend:" + world.defendRegionId(), TaskType.DEFEND_REGION)
                .target(new RegionTarget(world.defendRegionId()))
                .priority(1.0).estimatedTicks(900).requiredCapabilities(DEFEND_CAPS)
                .exclusive(false).build(), world.defendWorldX(), world.defendWorldY()));
        }

        Pending wait = new Pending(TaskSpec.builder("runtime:wait", TaskType.WAIT)
            .priority(0.05).estimatedTicks(60).requiredCapabilities(WAIT_CAPS)
            .exclusive(false).build(), agent.worldX(), agent.worldY());

        if(pending.size() >= maxCandidates){
            pending.subList(maxCandidates - 1, pending.size()).clear();
        }
        pending.add(wait);

        ArrayList<TaskCandidate> result = new ArrayList<>(pending.size());
        for(Pending item : pending){
            String invalid = invalidReason(agent, item);
            double score = utility.score(agent.id(), item.task(), world.tick());
            result.add(new TaskCandidate(item.task(), invalid.isEmpty(), invalid, score));
        }
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

    private record Pending(TaskSpec task, float worldX, float worldY){}
}
