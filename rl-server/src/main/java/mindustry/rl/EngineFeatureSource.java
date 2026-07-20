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
    private final float mapDiagonal;

    public EngineFeatureSource(
        Scenario scenario,
        RlAgentRegistry registry,
        CandidateWorldSnapshot world
    ){
        this.scenario = scenario;
        this.registry = registry;
        this.world = world;
        this.mapDiagonal = (float)Math.hypot(scenario.width * world.tileSize(),
            scenario.height * world.tileSize());
    }

    @Override public UtilityFeatures featuresFor(AgentId agentId, TaskSpec task, long tick){
        RlAgentRegistry.Agent agent = registry.get(agentId.index());
        float[] target = targetPosition(task, agent);
        double travel = agent == null ? 1.0 : clamp(Math.hypot(
            target[0] - agent.unit.x, target[1] - agent.unit.y) / mapDiagonal);

        return UtilityFeatures.builder()
            .teamValue(task.priority())
            .urgency(urgency(task))
            .capabilityFit(agent == null ? 0.0 : 1.0)
            .roleFit(agent == null ? 0.0 : 1.0)
            .proximity(1.0 - travel)
            .helpSynergy(task.helpersRequested() > 0 ? 1.0 : 0.0)
            .travelCost(travel)
            .resourceCost(clamp(task.estimatedCost().amount("copper")
                / (double)Math.max(1, world.coreCopper())))
            .danger(task.type() == TaskType.DEFEND_REGION ? 0.0
                : clamp(world.enemyCount() / 5.0))
            .build();
    }

    private double urgency(TaskSpec task){
        return switch(task.type()){
            case HARVEST_RESOURCE -> clamp((world.harvestCopperThreshold() - world.coreCopper())
                / (double)Math.max(1, world.harvestCopperThreshold()));
            case BUILD_SCHEMATIC -> world.schematicComplete() ? 0.0 : 1.0;
            case SUPPLY_TURRET -> turretUrgency(task);
            case REPAIR_REGION -> clamp(world.brokenBlockCount() / 5.0);
            case DEFEND_REGION -> world.enemyCount() > 0 ? 1.0 : clamp(1.0
                - world.timeToNextWave() / Math.max(1.0, world.defendLeadTicks()));
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

    private float[] targetPosition(TaskSpec task, RlAgentRegistry.Agent agent){
        if(task.target() instanceof EntityTarget entity){
            for(TurretSnapshot turret : world.turrets()){
                if(turret.entityId() == entity.entityId()){
                    return new float[]{turret.tileX() * world.tileSize(),
                        turret.tileY() * world.tileSize()};
                }
            }
        }else if(task.target() instanceof RegionTarget region){
            if(region.regionId().equals(world.schematicId())){
                return new float[]{world.schematicWorldX(), world.schematicWorldY()};
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
}
