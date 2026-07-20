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
        ExpertCoordinationPlan.Schematic fortification = fortification(scenario, referenceTurrets);
        List<ExpertCoordinationPlan.Schematic> expansions = expansions(
            scenario, rebuild, referenceTurrets);
        return new ExpertCoordinationPlan(
            scenario.coreX,
            scenario.coreY,
            tilesize,
            scenario.waveCount,
            scenario.winTick,
            schematic(line, scenario.buildLineAnchorX, scenario.buildLineAnchorY),
            schematic(defense, scenario.referenceAnchorX, scenario.referenceAnchorY),
            fortification,
            expansions,
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

    private static ExpertCoordinationPlan.Schematic fortification(
        Scenario scenario,
        List<TileTarget> referenceTurrets
    ){
        ArrayList<BuildSpec> blocks = new ArrayList<>();
        for(int y = scenario.coreY - 2; y <= scenario.coreY + 2; y++){
            add(blocks, "copper-wall", scenario.coreX - 2, y, 0, scenario);
        }
        for(int y = scenario.coreY - 2; y <= scenario.coreY; y++){
            add(blocks, "copper-wall", scenario.coreX + 2, y, 0, scenario);
        }
        for(int x = scenario.coreX - 1; x <= scenario.coreX + 1; x++){
            add(blocks, "copper-wall", x, scenario.coreY - 2, 0, scenario);
        }
        for(int x = scenario.coreX - 1; x <= scenario.coreX; x++){
            add(blocks, "copper-wall", x, scenario.coreY + 2, 0, scenario);
        }
        for(int y = scenario.coreY - 3; y <= scenario.coreY + 1; y++){
            add(blocks, "copper-wall", scenario.coreX + 3, y, 0, scenario);
        }
        for(TileTarget target : referenceTurrets){
            add(blocks, "duo", target.x() - 3, target.y(), 1, scenario);
            add(blocks, "duo", target.x() - 2, target.y(), 1, scenario);
        }
        return generated("expert_fortification_v1", scenario, blocks);
    }

    private static List<ExpertCoordinationPlan.Schematic> expansions(
        Scenario scenario,
        Scenario.RegionSpec rebuild,
        List<TileTarget> referenceTurrets
    ){
        ArrayList<ExpertCoordinationPlan.Schematic> result = new ArrayList<>();
        for(int index = 0; index < scenario.waveCount - 1; index++){
            ArrayList<BuildSpec> blocks = new ArrayList<>();
            int wallX = rebuild.x() + rebuild.w() + index * 3;
            int turretX = wallX - 1;
            for(int y = rebuild.y() + 1; y < rebuild.y() + rebuild.h() - 1; y++){
                add(blocks, "copper-wall", wallX, y, 0, scenario);
            }
            for(TileTarget reference : referenceTurrets){
                add(blocks, "duo", turretX, reference.y(), 1, scenario);
            }
            result.add(generated("expert_expansion_wave" + (index + 1) + "_v1",
                scenario, blocks));
        }
        return List.copyOf(result);
    }

    private static void add(
        List<BuildSpec> blocks,
        String block,
        int x,
        int y,
        int rotation,
        Scenario scenario
    ){
        blocks.add(new BuildSpec(block, x - scenario.coreX, y - scenario.coreY, rotation));
    }

    private static ExpertCoordinationPlan.Schematic generated(
        String name,
        Scenario scenario,
        List<BuildSpec> blocks
    ){
        int cost = 0;
        for(BuildSpec block : blocks) cost += copperCost(block.block());
        return new ExpertCoordinationPlan.Schematic(
            name, scenario.coreX, scenario.coreY, cost, blocks);
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
