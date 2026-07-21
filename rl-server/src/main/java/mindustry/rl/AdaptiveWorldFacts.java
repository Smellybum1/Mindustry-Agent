package mindustry.rl;

import agentcore.candidates.*;
import agentcore.skill.*;
import arc.math.geom.*;
import mindustry.content.*;
import mindustry.entities.bullet.*;
import mindustry.gen.*;
import mindustry.type.*;
import mindustry.world.*;
import mindustry.world.blocks.defense.turrets.*;

import java.io.*;
import java.nio.charset.*;
import java.util.*;

import static mindustry.Vars.*;

/** Rolling, simulation-thread-only evidence used by M7.4 adaptive planning. */
public final class AdaptiveWorldFacts{
    private final Scenario scenario;
    private final RlAgentRegistry registry;
    private final int[] automatedCopperInflow;
    private final int[] previousAgentCopper;
    private final float assignmentRange;
    private int inflowIndex;
    private int inflowSamples;
    private int inflowTotal;
    private int previousCoreCopper;

    public AdaptiveWorldFacts(Scenario scenario, RlAgentRegistry registry){
        this.scenario = Objects.requireNonNull(scenario, "scenario");
        this.registry = Objects.requireNonNull(registry, "registry");
        automatedCopperInflow = new int[scenario.buildLineInflowSampleTicks];
        previousAgentCopper = new int[Math.max(1, scenario.unitCap)];
        assignmentRange = deriveAssignmentRange();
    }

    public void reset(){
        Arrays.fill(automatedCopperInflow, 0);
        Arrays.fill(previousAgentCopper, 0);
        inflowIndex = 0;
        inflowSamples = 0;
        inflowTotal = 0;
        previousCoreCopper = StateHasher.coreItem(Items.copper);
        captureAgentCopper(previousAgentCopper);
    }

    /** Record one authoritative engine tick, excluding explicit scenario grants and unit delivery. */
    public void recordTick(int scenarioGrant){
        int currentCore = StateHasher.coreItem(Items.copper);
        int positiveCoreDelta = Math.max(0, currentCore - previousCoreCopper);
        int[] currentAgentCopper = new int[previousAgentCopper.length];
        captureAgentCopper(currentAgentCopper);
        int unitDelivery = 0;
        for(int i = 0; i < previousAgentCopper.length; i++){
            unitDelivery += Math.max(0, previousAgentCopper[i] - currentAgentCopper[i]);
            previousAgentCopper[i] = currentAgentCopper[i];
        }
        int automated = Math.max(0, positiveCoreDelta - unitDelivery - Math.max(0, scenarioGrant));
        inflowTotal -= automatedCopperInflow[inflowIndex];
        automatedCopperInflow[inflowIndex] = automated;
        inflowTotal += automated;
        inflowIndex = (inflowIndex + 1) % automatedCopperInflow.length;
        inflowSamples = Math.min(automatedCopperInflow.length, inflowSamples + 1);
        previousCoreCopper = currentCore;
    }

    public EconomySnapshot economy(){
        boolean blocks = lineBlocksComplete();
        boolean connected = blocks && conveyorPathConnected();
        double rate = inflowTotal * 60.0 / automatedCopperInflow.length;
        return new EconomySnapshot(blocks, connected, rate, scenario.buildLineInflowRate,
            inflowSamples, automatedCopperInflow.length);
    }

    public DefenseReadinessSnapshot defense(){
        int waveNumber = activeOrNextWave();
        Scenario.WaveSpec wave = scenario.waves.get(waveNumber - 1);
        ItemTurret duo = (ItemTurret)Blocks.duo;
        BulletType copperBullet = duo.ammoTypes.get(Items.copper);
        double duoDamage = Math.max(1.0, copperBullet.damage);
        double duoDps = duoDamage * 60.0 / Math.max(1.0, duo.reload);

        int enemies = 0;
        double health = 0.0;
        double incomingDps = 0.0;
        int requiredAmmo = 0;
        for(Scenario.WaveSpawn spawn : wave.spawns()){
            enemies += spawn.count();
            health += spawn.type().health * spawn.count();
            requiredAmmo += (int)Math.ceil(spawn.type().health / duoDamage) * spawn.count();
            double oneEnemyDps = 0.0;
            for(Weapon weapon : spawn.type().weapons){
                oneEnemyDps += weapon.bullet.damage * 60.0 / Math.max(1.0, weapon.reload);
            }
            incomingDps += oneEnemyDps * spawn.count();
        }

        int requiredTurrets = referenceTurretCount();
        int readyTurrets = 0;
        int totalAmmo = 0;
        for(Building building : StateHasher.worldBuildings()){
            if(building.team != scenario.coreTeam || building.block != Blocks.duo
                || !(building instanceof Turret.TurretBuild turret)) continue;
            totalAmmo += Math.max(0, Math.round(turret.totalAmmo));
            if(turret.totalAmmo > 0.0f) readyTurrets++;
        }
        int planningTurrets = Math.max(requiredTurrets, readyTurrets);
        // Straight HP / bullet-damage arithmetic is a lower bound: an unguided
        // Duo can miss within its configured inaccuracy cone. Reserve that same
        // engine-derived fraction before clamping to the physical magazine.
        double aimReserve = 1.0 + duo.inaccuracy / Math.max(1.0, duo.shootCone);
        int targetAmmo = Math.max(scenario.objective(agentcore.TaskType.SUPPLY_TURRET).threshold(),
            Math.min(Math.round(duo.maxAmmo),
                (int)Math.ceil(requiredAmmo * aimReserve / planningTurrets)));
        double ammoCoverage = coverage(totalAmmo, targetAmmo * planningTurrets);
        double turretCoverage = coverage(readyTurrets, requiredTurrets);

        double clearSeconds = health / Math.max(1.0, planningTurrets * duoDps);
        double liveRatio = enemies <= 0 ? 0.0 : (enemies + 1.0) / (2.0 * enemies);
        double expectedIncomingDamage = incomingDps * clearSeconds * liveRatio;
        double healthCoverage = coverage(defenseHealth(), expectedIncomingDamage);
        double readiness = Math.min(ammoCoverage, Math.min(turretCoverage, healthCoverage));

        Scenario.RegionSpec region = scenario.region(
            scenario.objective(agentcore.TaskType.DEFEND_REGION).targetRef());
        float defendX = center(region.x(), region.w());
        float defendY = center(region.y(), region.h());
        double travelTicks = Math.hypot(defendX - scenario.coreX * tilesize,
            defendY - scenario.coreY * tilesize) / Math.max(0.01, UnitTypes.alpha.speed);
        int clearTicks = (int)Math.ceil(clearSeconds * 60.0);
        int leadTicks = Math.max(1, (int)Math.ceil(travelTicks) + clearTicks);
        double imminence = state.enemies > 0 ? 1.0
            : clamp(1.0 - state.wavetime / Math.max(1.0, leadTicks));
        return new DefenseReadinessSnapshot(waveNumber, enemies, health, incomingDps,
            requiredAmmo, targetAmmo, readyTurrets, requiredTurrets, totalAmmo,
            ammoCoverage, healthCoverage, turretCoverage, readiness, leadTicks, imminence);
    }

    public float assignmentRange(){
        return assignmentRange;
    }

    public byte[] canonicalState(){
        try{
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            byte[] id = scenario.id.getBytes(StandardCharsets.UTF_8);
            out.writeInt(id.length);
            out.write(id);
            out.writeInt(inflowIndex);
            out.writeInt(inflowSamples);
            out.writeInt(inflowTotal);
            out.writeInt(previousCoreCopper);
            out.writeInt(automatedCopperInflow.length);
            for(int value : automatedCopperInflow) out.writeInt(value);
            out.writeInt(previousAgentCopper.length);
            for(int value : previousAgentCopper) out.writeInt(value);
            out.flush();
            return bytes.toByteArray();
        }catch(IOException impossible){
            throw new AssertionError(impossible);
        }
    }

    private void captureAgentCopper(int[] output){
        for(RlAgentRegistry.Agent agent : registry.agents()){
            if(agent.index < 0 || agent.index >= output.length) continue;
            output[agent.index] = agent.unit.stack().item == Items.copper
                ? agent.unit.stack().amount : 0;
        }
    }

    private boolean lineBlocksComplete(){
        Scenario.SchematicSpec line = scenario.schematic(scenario.buildLineId);
        for(BuildSpec block : line.blocks()){
            Tile tile = world.tile(scenario.buildLineAnchorX + block.offsetX(),
                scenario.buildLineAnchorY + block.offsetY());
            if(tile == null || tile.build == null || tile.build.team != scenario.coreTeam
                || !tile.block().name.equals(block.block())
                || tile.build.rotation != block.rotation()) return false;
        }
        return true;
    }

    private boolean conveyorPathConnected(){
        Scenario.SchematicSpec line = scenario.schematic(scenario.buildLineId);
        HashSet<Building> lineConveyors = new HashSet<>();
        ArrayList<Building> drills = new ArrayList<>();
        for(BuildSpec block : line.blocks()){
            Building building = world.build(scenario.buildLineAnchorX + block.offsetX(),
                scenario.buildLineAnchorY + block.offsetY());
            if(building == null || building.team != scenario.coreTeam) continue;
            if(building.block == Blocks.conveyor) lineConveyors.add(building);
            if(building.block == Blocks.mechanicalDrill) drills.add(building);
        }
        for(Building drill : drills){
            for(Building adjacent : drill.proximity){
                if(lineConveyors.contains(adjacent) && reachesCore(adjacent, lineConveyors)){
                    return true;
                }
            }
        }
        return false;
    }

    private boolean reachesCore(Building start, Set<Building> lineConveyors){
        HashSet<Building> visited = new HashSet<>();
        Building current = start;
        while(current != null && visited.add(current)){
            int direction = current.rotation & 3;
            Tile next = world.tile(current.tileX() + Geometry.d4x(direction),
                current.tileY() + Geometry.d4y(direction));
            Building target = next == null ? null : next.build;
            if(target == null || target.team != scenario.coreTeam) return false;
            if(target == scenario.coreTeam.core()) return true;
            if(!lineConveyors.contains(target)) return false;
            current = target;
        }
        return false;
    }

    private int activeOrNextWave(){
        int number = state.enemies > 0 ? state.wave - 1 : state.wave;
        return Math.max(1, Math.min(scenario.waveCount, number));
    }

    private int referenceTurretCount(){
        int count = 0;
        for(BuildSpec block : scenario.schematic(scenario.referenceSchematicId).blocks()){
            if(block.block().equals(Blocks.duo.name)) count++;
        }
        return Math.max(1, count);
    }

    private double defenseHealth(){
        Scenario.RegionSpec region = scenario.region(
            scenario.objective(agentcore.TaskType.REPAIR_REGION).targetRef());
        double health = 0.0;
        for(Building building : StateHasher.worldBuildings()){
            if(building.team == scenario.coreTeam && building.tileX() >= region.x()
                && building.tileX() < region.x() + region.w()
                && building.tileY() >= region.y()
                && building.tileY() < region.y() + region.h()){
                health += Math.max(0.0, building.health);
            }
        }
        return health;
    }

    private float deriveAssignmentRange(){
        float coreWorldX = scenario.coreX * tilesize;
        float coreWorldY = scenario.coreY * tilesize;
        double farthest = 0.0;
        for(Scenario.OrePatch patch : scenario.orePatches){
            farthest = Math.max(farthest, Math.hypot(center(patch.x, patch.w) - coreWorldX,
                center(patch.y, patch.h) - coreWorldY));
        }
        for(Scenario.RegionSpec region : scenario.regions.values()){
            farthest = Math.max(farthest, Math.hypot(center(region.x(), region.w()) - coreWorldX,
                center(region.y(), region.h()) - coreWorldY));
        }
        farthest = Math.max(farthest, Math.hypot(
            scenario.referenceAnchorX * tilesize - coreWorldX,
            scenario.referenceAnchorY * tilesize - coreWorldY));
        return (float)(farthest + tilesize * 2.0);
    }

    private static double coverage(double available, double required){
        return required <= 0.0 ? 1.0 : clamp(available / required);
    }

    private static float center(int start, int size){
        return (start + (size - 1) / 2f) * tilesize;
    }

    private static double clamp(double value){
        return Math.max(0.0, Math.min(1.0, value));
    }
}
