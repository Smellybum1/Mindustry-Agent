package mindustry.rl;

import agentcore.*;
import agentcore.candidates.*;
import agentcore.task.*;
import agentcore.utility.*;

/** Engine-adapter feature values computed from one immutable observation boundary. */
public final class EngineFeatureSource implements FeatureSource{
    private final Scenario scenario;
    private final RlAgentRegistry registry;
    private final CandidateWorldSnapshot world;
    private final float assignmentRange;
    private final CoordinationAdapter coordination;

    public EngineFeatureSource(
        Scenario scenario,
        RlAgentRegistry registry,
        CandidateWorldSnapshot world,
        float assignmentRange,
        CoordinationAdapter coordination
    ){
        this.scenario = scenario;
        this.registry = registry;
        this.world = world;
        this.assignmentRange = Math.max(1f, assignmentRange);
        this.coordination = coordination;
    }

    @Override public UtilityFeatures featuresFor(AgentId agentId, TaskSpec task, long tick){
        RlAgentRegistry.Agent agent = registry.get(agentId.index());
        float[] target = targetPosition(task, agent);
        double travel = agent == null ? 1.0 : clamp(Math.hypot(
            target[0] - agent.unit.x, target[1] - agent.unit.y) / assignmentRange);

        return UtilityFeatures.builder()
            .teamValue(task.priority())
            .urgency(urgency(task))
            .capabilityFit(agent == null ? 0.0 : 1.0)
            .roleFit(agent == null ? 0.0 : roleFit(agentId.index(), task.type()))
            .proximity(1.0 - travel)
            .helpSynergy(task.helpersRequested() > 0 ? 1.0 : 0.0)
            .travelCost(travel)
            .resourceCost(clamp(task.estimatedCost().amount("copper")
                / (double)Math.max(1, world.coreCopper())))
            .switchingCost(coordination == null ? 0.0
                : coordination.switchingCost(agentId.index(), task, tick))
            .danger(task.type() == TaskType.DEFEND_REGION ? 0.0
                : clamp(world.enemyCount() / 5.0))
            .build();
    }

    private double urgency(TaskSpec task){
        return switch(task.type()){
            case HARVEST_RESOURCE -> clamp((world.harvestCopperThreshold() - world.coreCopper())
                / (double)Math.max(1, world.harvestCopperThreshold()));
            case BUILD_LINE -> 1.0 - world.economy().readiness();
            case BUILD_SCHEMATIC -> schematicUrgency(task);
            case SUPPLY_TURRET -> turretUrgency(task);
            case REPAIR_REGION -> clamp(world.brokenBlockCount() / 5.0);
            case DEFEND_REGION -> world.enemyCount() > 0 ? 1.0
                : world.defenseReadiness().waveImminence();
            default -> 0.0;
        };
    }

    private double turretUrgency(TaskSpec task){
        if(!(task.target() instanceof EntityTarget entity)) return 0.0;
        for(TurretSnapshot turret : world.turrets()){
            if(turret.entityId() == entity.entityId()){
                return clamp((world.turretTargetAmmo() - turret.totalAmmo())
                    / (double)Math.max(1, world.turretTargetAmmo()));
            }
        }
        return 0.0;
    }

    private double schematicUrgency(TaskSpec task){
        if(task.target() instanceof RegionTarget region
            && region.regionId().equals(world.schematicId())){
            return world.schematicComplete() ? 0.0 : 1.0;
        }
        return 1.0 - world.defenseReadiness().readiness();
    }

    private float[] targetPosition(TaskSpec task, RlAgentRegistry.Agent agent){
        if(task.target() instanceof EntityTarget entity){
            for(TurretSnapshot turret : world.turrets()){
                if(turret.entityId() == entity.entityId()){
                    return new float[]{turret.tileX() * world.tileSize(),
                        turret.tileY() * world.tileSize()};
                }
            }
        }else if(task.target() instanceof RegionTarget region){
            if(region.regionId().equals(world.buildLineId())){
                return new float[]{world.buildLineWorldX(), world.buildLineWorldY()};
            }
            if(region.regionId().equals(world.schematicId())){
                return new float[]{world.schematicWorldX(), world.schematicWorldY()};
            }
            for(PlannedSchematicSnapshot planned : world.plannedSchematics()){
                if(region.regionId().equals(planned.schematicId())){
                    return new float[]{planned.anchorX() * world.tileSize(),
                        planned.anchorY() * world.tileSize()};
                }
            }
            Scenario.RegionSpec spec = scenario.region(region.regionId());
            if(spec != null) return new float[]{center(spec.x(), spec.w()),
                center(spec.y(), spec.h())};
        }else if(task.target() instanceof ResourceTarget){
            return new float[]{world.harvestWorldX(), world.harvestWorldY()};
        }else if(task.target() instanceof TileTarget tile){
            return new float[]{tile.x() * world.tileSize(), tile.y() * world.tileSize()};
        }
        return agent == null ? new float[]{0f, 0f} : new float[]{agent.unit.x, agent.unit.y};
    }

    private float center(int start, int size){
        return (start + (size - 1) / 2f) * world.tileSize();
    }

    private static double clamp(double value){
        return Math.max(0.0, Math.min(1.0, value));
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

}
