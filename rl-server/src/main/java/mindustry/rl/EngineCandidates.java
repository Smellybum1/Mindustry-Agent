package mindustry.rl;

import agentcore.*;
import agentcore.candidates.*;
import agentcore.coordination.*;
import agentcore.skill.*;
import agentcore.task.*;
import agentcore.utility.*;
import arc.util.serialization.*;
import mindustry.content.*;
import mindustry.game.Teams.*;
import mindustry.gen.*;
import mindustry.world.*;
import mindustry.world.blocks.defense.turrets.Turret.*;

import java.util.*;

import static mindustry.Vars.*;

/** Simulation-thread adapter from live Mindustry state to the engine-free M5 catalog. */
public final class EngineCandidates{
    private static final Set<String> ALPHA_CAPABILITIES =
        Set.of("build", "carry", "combat", "mine", "wait");

    private final Scenario scenario;
    private final RlAgentRegistry registry;
    private final AdaptiveWorldFacts facts;
    private final ExpertCoordinationPlan expertPlan;
    private final CandidateGenerator generator = new CandidateGenerator();
    private final Scenario.ObjectiveSpec harvest;
    private final Scenario.ObjectiveSpec buildLine;
    private final Scenario.ObjectiveSpec schematic;
    private final Scenario.ObjectiveSpec supply;
    private final Scenario.ObjectiveSpec rebuild;
    private final Scenario.ObjectiveSpec defend;
    private final Scenario.OrePatch harvestPatch;
    private final Scenario.RegionSpec rebuildRegion;
    private final Scenario.RegionSpec defendRegion;
    private boolean overlapProbe;
    private CoordinationAdapter coordination;

    public EngineCandidates(Scenario scenario, RlAgentRegistry registry){
        this(scenario, registry, new AdaptiveWorldFacts(scenario, registry));
    }

    public EngineCandidates(
        Scenario scenario,
        RlAgentRegistry registry,
        AdaptiveWorldFacts facts
    ){
        this.scenario = scenario;
        this.registry = registry;
        this.facts = facts;
        this.expertPlan = ExpertCoordinationPlans.fromScenario(scenario);
        harvest = requireObjective(TaskType.HARVEST_RESOURCE);
        buildLine = requireObjective(TaskType.BUILD_LINE);
        schematic = requireObjective(TaskType.BUILD_SCHEMATIC);
        supply = requireObjective(TaskType.SUPPLY_TURRET);
        rebuild = requireObjective(TaskType.REPAIR_REGION);
        defend = requireObjective(TaskType.DEFEND_REGION);
        if(harvest.threshold() <= 0){
            throw new IllegalStateException("harvest objective threshold must be positive");
        }
        if(supply.threshold() <= 0){
            throw new IllegalStateException("supply objective threshold must be positive");
        }
        if(scenario.referenceSchematicId.isBlank()
            || !scenario.referenceSchematicId.equals(schematic.targetRef())
            || scenario.schematic(scenario.referenceSchematicId) == null){
            throw new IllegalStateException("schematic objective/reference mismatch");
        }
        if(scenario.buildLineId.isBlank() || scenario.schematic(scenario.buildLineId) == null){
            throw new IllegalStateException("build-line reference mismatch");
        }
        harvestPatch = requirePatch(harvest.targetRef());
        rebuildRegion = requireRegion(rebuild.targetRef());
        defendRegion = requireRegion(defend.targetRef());
    }

    /** Capture all mutable state once at the observation boundary. */
    public CandidateWorldSnapshot snapshot(){
        Scenario.SchematicSpec schematicSpec = scenario.schematic(scenario.referenceSchematicId);
        Scenario.SchematicSpec lineSpec = scenario.schematic(scenario.buildLineId);
        ArrayList<TurretSnapshot> turrets = new ArrayList<>();
        for(Building building : Groups.build){
            if(building.team == scenario.coreTeam && building instanceof TurretBuild turret){
                turrets.add(new TurretSnapshot(building.id, building.tileX(), building.tileY(),
                    turret.totalAmmo));
            }
        }

        EconomySnapshot economy = facts.economy();
        DefenseReadinessSnapshot defense = facts.defense();
        return new CandidateWorldSnapshot(
            (long)state.tick, tilesize,
            harvest.id(), buildLine.id(), schematic.id(), supply.id(), rebuild.id(), defend.id(),
            StateHasher.coreItem(Items.copper), harvest.threshold(),
            economy.operational(), economy,
            lineSpec.copperCost(),
            schematicComplete(schematicSpec), schematicSpec.copperCost(),
            center(harvestPatch.x, harvestPatch.w), center(harvestPatch.y, harvestPatch.h),
            scenario.buildLineAnchorX * tilesize, scenario.buildLineAnchorY * tilesize,
            scenario.buildLineId,
            scenario.referenceAnchorX * tilesize, scenario.referenceAnchorY * tilesize,
            scenario.referenceSchematicId,
            Math.max(1, state.wave), plannedSchematics(defense),
            turrets, defense.targetAmmoPerTurret(),
            brokenBlocksIn(rebuildRegion),
            center(rebuildRegion.x(), rebuildRegion.w()), center(rebuildRegion.y(), rebuildRegion.h()),
            rebuildRegion.id(),
            state.enemies, state.wavetime, defense,
            center(defendRegion.x(), defendRegion.w()), center(defendRegion.y(), defendRegion.h()),
            defendRegion.id()
        );
    }

    private List<PlannedSchematicSnapshot> plannedSchematics(
        DefenseReadinessSnapshot defense
    ){
        ArrayList<PlannedSchematicSnapshot> result = new ArrayList<>();
        ExpertCoordinationPlan.Schematic fortification = expertPlan.fortification();
        if(!schematicComplete(fortification)){
            if(schematicComplete(scenario.schematic(scenario.buildLineId),
                scenario.buildLineAnchorX, scenario.buildLineAnchorY)
                && schematicComplete(scenario.schematic(scenario.referenceSchematicId))){
                result.add(planned(fortification, 1, 1.0 - defense.readiness()));
            }
            return List.copyOf(result);
        }
        for(int i = 0; i < expertPlan.expansions().size(); i++){
            ExpertCoordinationPlan.Schematic expansion = expertPlan.expansions().get(i);
            if(schematicComplete(expansion)) continue;
            result.add(planned(expansion, i + 2, 1.0 - defense.readiness()));
            break;
        }
        return List.copyOf(result);
    }

    private PlannedSchematicSnapshot planned(
        ExpertCoordinationPlan.Schematic schematic,
        int minimumWave,
        double priority
    ){
        String taskId = "expert:build:" + schematic.name() + ":at-" + (long)state.tick;
        return new PlannedSchematicSnapshot(taskId, schematic.name(),
            schematic.anchorX(), schematic.anchorY(), schematic.copperCost(),
            false, minimumWave, priority, List.of());
    }

    public CandidateSet generate(RlAgentRegistry.Agent agent, CandidateWorldSnapshot world){
        float assignmentRange = facts.assignmentRange();
        AgentSnapshot snapshot = new AgentSnapshot(AgentId.of(agent.index), agent.unit.x,
            agent.unit.y, assignmentRange, ALPHA_CAPABILITIES);
        HandTunedUtility utility = new HandTunedUtility(
            new EngineFeatureSource(scenario, registry, world, assignmentRange, coordination));
        CandidateSet generated = generator.generate(snapshot, world, utility);
        return overlapProbe ? withOverlapProbe(generated) : generated;
    }

    /** Validation-only scenario option: expose a second task over the same footprint. */
    public void setOverlapProbe(boolean enabled){
        overlapProbe = enabled;
    }

    public void setCoordination(CoordinationAdapter coordination){
        this.coordination = coordination;
    }

    public Jval observation(CandidateSet set){
        Jval out = Jval.newArray();
        int index = 0;
        for(TaskCandidate candidate : set.candidates()){
            Jval item = Jval.newObject();
            item.put("index", index++);
            item.put("task_id", candidate.task().taskId());
            item.put("task_type", candidate.task().type().name());
            item.put("target", candidate.task().target() == null ? ""
                : candidate.task().target().describe());
            item.put("priority", candidate.task().priority());
            item.put("estimated_ticks", candidate.task().estimatedTicks());
            Jval cost = Jval.newObject();
            candidate.task().estimatedCost().asMap().forEach(cost::put);
            item.add("estimated_cost", cost);
            Jval capabilities = Jval.newArray();
            candidate.task().requiredCapabilities().forEach(capabilities::add);
            item.add("required_capabilities", capabilities);
            item.put("valid", candidate.valid());
            item.put("invalid_reason", candidate.invalidReason());
            item.put("utility", candidate.utility());
            out.add(item);
        }
        return out;
    }

    public Jval mask(CandidateSet set){
        Jval mask = Jval.newArray();
        for(TaskCandidate candidate : set.candidates()) mask.add(candidate.valid());
        return mask;
    }

    private boolean schematicComplete(Scenario.SchematicSpec spec){
        return schematicComplete(spec, scenario.referenceAnchorX, scenario.referenceAnchorY);
    }

    private boolean schematicComplete(ExpertCoordinationPlan.Schematic spec){
        return schematicComplete(spec.blocks(), spec.anchorX(), spec.anchorY());
    }

    private boolean schematicComplete(Scenario.SchematicSpec spec, int anchorX, int anchorY){
        return schematicComplete(spec.blocks(), anchorX, anchorY);
    }

    private boolean schematicComplete(List<BuildSpec> blocks, int anchorX, int anchorY){
        for(BuildSpec block : blocks){
            Tile tile = world.tile(anchorX + block.offsetX(), anchorY + block.offsetY());
            if(tile == null || tile.build == null || !tile.block().name.equals(block.block())
                || tile.build.rotation != block.rotation()) return false;
        }
        return true;
    }

    private CandidateSet withOverlapProbe(CandidateSet generated){
        if(generated.candidates().size() >= CandidateGenerator.DEFAULT_MAX_CANDIDATES){
            return generated;
        }
        ArrayList<TaskCandidate> candidates = new ArrayList<>(generated.candidates());
        for(int i = 0; i < candidates.size(); i++){
            TaskCandidate original = candidates.get(i);
            TaskSpec task = original.task();
            if(task.type() != TaskType.BUILD_SCHEMATIC) continue;
            TaskSpec probe = TaskSpec.builder(task.taskId() + ":overlap-probe", task.type())
                .target(task.target())
                .priority(task.priority())
                .estimatedTicks(task.estimatedTicks())
                .estimatedCost(task.estimatedCost())
                .requiredCapabilities(task.requiredCapabilities())
                .helpersRequested(task.helpersRequested())
                .exclusive(task.exclusive())
                .parentTaskId(task.parentTaskId())
                .dependencyTaskIds(task.dependencyTaskIds())
                .build();
            candidates.add(i + 1, new TaskCandidate(probe, original.valid(),
                original.invalidReason(), original.utility()));
            break;
        }
        return new CandidateSet(candidates);
    }

    private int brokenBlocksIn(Scenario.RegionSpec region){
        int count = 0;
        var plans = scenario.coreTeam.data().plans;
        for(int i = 0; i < plans.size; i++){
            BlockPlan plan = plans.get(i);
            if(!plan.removed && plan.x >= region.x() && plan.x < region.x() + region.w()
                && plan.y >= region.y() && plan.y < region.y() + region.h()) count++;
        }
        return count;
    }

    private Scenario.ObjectiveSpec requireObjective(TaskType type){
        Scenario.ObjectiveSpec objective = scenario.objective(type);
        if(objective == null) throw new IllegalStateException("missing scenario objective " + type);
        return objective;
    }

    private Scenario.OrePatch requirePatch(String id){
        Scenario.OrePatch patch = scenario.orePatch(id);
        if(patch == null) throw new IllegalStateException("unknown objective ore patch " + id);
        return patch;
    }

    private Scenario.RegionSpec requireRegion(String id){
        Scenario.RegionSpec region = scenario.region(id);
        if(region == null) throw new IllegalStateException("unknown objective region " + id);
        return region;
    }

    private static float center(int start, int size){
        return (start + (size - 1) / 2f) * tilesize;
    }
}
