package mindustry.rl;

import agentcore.*;
import agentcore.coordination.*;
import agentcore.skill.*;
import agentcore.task.*;
import mindustry.content.*;

import java.util.*;

import static mindustry.Vars.*;

/** Maps authoritative scenario data onto the engine-neutral shared expert plan. */
public final class ExpertCoordinationPlans{
    private ExpertCoordinationPlans(){ }

    public static ExpertCoordinationPlan fromScenario(Scenario scenario){
        Scenario.SchematicSpec line = scenario.schematic(scenario.buildLineId);
        Scenario.SchematicSpec defense = scenario.schematic(scenario.referenceSchematicId);
        if(line == null || defense == null) throw new IllegalStateException("missing expert schematics");

        Scenario.OrePatch support = null;
        for(Scenario.OrePatch patch : scenario.orePatches){
            if(patch.role.equals("east_ammo_feed")){
                support = patch;
                break;
            }
        }
        if(support == null || support.w < 2 || support.h < 2){
            throw new IllegalStateException("scenario needs a 2x2 east_ammo_feed ore patch");
        }
        List<TileTarget> mineTiles = List.of(
            new TileTarget(support.x, support.y),
            new TileTarget(support.x + support.w - 1, support.y),
            new TileTarget(support.x, support.y + support.h - 1)
        );

        ArrayList<TileTarget> referenceTurrets = new ArrayList<>();
        for(BuildSpec block : defense.blocks()){
            if(block.block().equals("duo")){
                referenceTurrets.add(new TileTarget(
                    scenario.referenceAnchorX + block.offsetX(),
                    scenario.referenceAnchorY + block.offsetY()));
            }
        }

        Scenario.RegionSpec defend = objectiveRegion(scenario, TaskType.DEFEND_REGION);
        Scenario.RegionSpec rebuild = objectiveRegion(scenario, TaskType.REPAIR_REGION);
        return new ExpertCoordinationPlan(
            scenario.coreX,
            scenario.coreY,
            tilesize,
            scenario.waveCount,
            scenario.winTick,
            schematic(line, scenario.buildLineAnchorX, scenario.buildLineAnchorY),
            schematic(defense, scenario.referenceAnchorX, scenario.referenceAnchorY),
            mineTiles,
            referenceTurrets,
            region(defend),
            region(rebuild),
            Map.of(
                "copper-wall", copperCost("copper-wall"),
                "duo", copperCost("duo")
            )
        );
    }

    private static ExpertCoordinationPlan.Schematic schematic(
        Scenario.SchematicSpec spec,
        int anchorX,
        int anchorY
    ){
        return new ExpertCoordinationPlan.Schematic(
            spec.name(), anchorX, anchorY, spec.copperCost(), spec.blocks());
    }

    private static ExpertCoordinationPlan.Region region(Scenario.RegionSpec region){
        return new ExpertCoordinationPlan.Region(
            region.id(), region.x(), region.y(), region.w(), region.h());
    }

    private static Scenario.RegionSpec objectiveRegion(Scenario scenario, TaskType type){
        Scenario.ObjectiveSpec objective = scenario.objective(type);
        Scenario.RegionSpec region = objective == null ? null : scenario.region(objective.targetRef());
        if(region == null) throw new IllegalStateException("missing expert region for " + type);
        return region;
    }

    private static int copperCost(String blockName){
        int total = 0;
        var block = content.block(blockName);
        if(block == null) throw new IllegalStateException("unknown expert block: " + blockName);
        for(var requirement : block.requirements){
            if(requirement.item == Items.copper) total += requirement.amount;
        }
        return total;
    }
}
