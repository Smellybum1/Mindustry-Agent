package agentcore.candidates;

import agentcore.AgentId;
import agentcore.TaskType;
import agentcore.task.TaskSpec;
import agentcore.utility.HandTunedUtility;
import agentcore.utility.UtilityFeatures;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class CandidateGeneratorTest{
    private static final Set<String> ALL_CAPABILITIES =
        Set.of("build", "carry", "combat", "mine", "wait");
    private static final AgentSnapshot AGENT =
        new AgentSnapshot(AgentId.of(0), 100f, 100f, 1000f, ALL_CAPABILITIES);
    private static final HandTunedUtility UTILITY = new HandTunedUtility((agent, task, tick) ->
        UtilityFeatures.builder().teamValue(task.priority()).urgency(tick / 1000.0).build());

    @Test void fixedSnapshotIsByteStableAndEntityExpansionIsSorted(){
        CandidateGenerator generator = new CandidateGenerator();
        CandidateWorldSnapshot world = activeWorld(List.of(
            new TurretSnapshot(19, 31, 24, 0),
            new TurretSnapshot(7, 30, 24, 2)
        ));

        byte[] expected = generator.generate(AGENT, world, UTILITY).canonicalBytes();
        for(int i = 0; i < 100; i++){
            assertArrayEquals(expected, generator.generate(AGENT, world, UTILITY).canonicalBytes());
        }

        List<String> taskIds = generator.generate(AGENT, world, UTILITY).candidates().stream()
            .map(candidate -> candidate.task().taskId()).toList();
        assertEquals(List.of(
            "T1:harvest:copper:at-50",
            "T2:build:copper_line_v1:at-50",
            "T3:build:east_duo_v1:at-50",
            "T4:supply:7:wave-1:at-50",
            "T4:supply:19:wave-1:at-50",
            "T6:rebuild:defense_block:wave-1:at-50",
            "T5:defend:east_lane:wave-1:agent-0:at-50",
            "runtime:wait"
        ), taskIds);
    }

    @Test void masksMissingCapabilitiesInStableCapabilityOrder(){
        AgentSnapshot waitOnly = new AgentSnapshot(AgentId.of(1), 100f, 100f, 1000f, Set.of("wait"));
        CandidateSet candidates = new CandidateGenerator().generate(waitOnly, activeWorld(List.of()), UTILITY);

        assertEquals("missing_capability:carry", candidates.candidates().get(0).invalidReason());
        assertEquals("missing_capability:build", candidates.candidates().get(1).invalidReason());
        assertEquals("missing_capability:build", candidates.candidates().get(2).invalidReason());
        assertEquals("missing_capability:build", candidates.candidates().get(3).invalidReason());
        assertEquals("missing_capability:combat", candidates.candidates().get(4).invalidReason());
        assertTrue(candidates.candidates().get(5).valid());
    }

    @Test void masksTargetsOutsideAssignmentRange(){
        AgentSnapshot local = new AgentSnapshot(AgentId.of(2), 0f, 0f, 8f, ALL_CAPABILITIES);
        CandidateSet candidates = new CandidateGenerator().generate(local, activeWorld(List.of()), UTILITY);

        assertEquals("out_of_range", candidates.candidates().get(0).invalidReason());
        assertEquals("out_of_range", candidates.candidates().get(1).invalidReason());
        assertEquals("out_of_range", candidates.candidates().get(2).invalidReason());
        assertEquals("out_of_range", candidates.candidates().get(3).invalidReason());
        assertEquals("out_of_range", candidates.candidates().get(4).invalidReason());
        assertTrue(candidates.candidates().get(5).valid(), "WAIT is always local to the agent");
    }

    @Test void boundedCatalogRanksByUtilityAndReservesDefend(){
        ArrayList<TurretSnapshot> turrets = new ArrayList<>();
        for(int i = 20; i >= 0; i--){
            turrets.add(new TurretSnapshot(i, 30 + i, 24, 0));
        }

        CandidateSet candidates = new CandidateGenerator(8).generate(AGENT, activeWorld(turrets),
            (agent, task, tick) -> task.taskId().equals("T4:supply:20:wave-1:at-50")
                ? 100.0 : task.type() == TaskType.DEFEND_REGION ? -100.0 : task.priority());
        List<String> ids = candidates.candidates().stream()
            .map(candidate -> candidate.task().taskId()).toList();
        assertEquals(8, candidates.candidates().size());
        assertEquals("runtime:wait", candidates.candidates().get(7).task().taskId());
        assertTrue(ids.contains("T4:supply:20:wave-1:at-50"),
            "late high-utility task must survive truncation");
        assertTrue(ids.contains("T5:defend:east_lane:wave-1:agent-0:at-50"),
            "DEFEND always retains an overflow slot");
        assertFalse(ids.contains("T1:harvest:copper:at-50"),
            "lower utility task should be truncated");
    }

    @Test void defendLeadBoundaryUsesOrdinaryDefenseInsteadOfStaging(){
        CandidateWorldSnapshot world = new CandidateWorldSnapshot(
            50, 8, "T1", "T2", "T3", "T4", "T6", "T5", 400, 300,
            true, economy(true), 31, true, 120,
            84f, 84f, 224f, 224f, "copper_line_v1",
            260f, 196f, "east_duo_v1",
            3, List.of(),
            List.of(new TurretSnapshot(7, 30, 24, 10)), 10,
            0, 260f, 196f, "defense_block",
            0, 600f, defense(1.0, 0.0), 300f, 196f, "east_lane"
        );

        CandidateSet candidates = new CandidateGenerator().generate(AGENT, world, UTILITY);
        assertEquals(2, candidates.candidates().size());
        assertEquals("T5:defend:east_lane:wave-3:agent-0:at-50",
            candidates.candidates().get(0).task().taskId());
        assertFalse(candidates.candidates().get(0).task().taskId().contains(":stage:"));
        assertTrue(candidates.candidates().get(0).valid());
        assertEquals("runtime:wait", candidates.candidates().get(1).task().taskId());
    }

    @Test void emptyQuietCatalogProducesExactDefenseStagingWindow(){
        CandidateWorldSnapshot world = satisfiedWorld(1200f);
        CandidateSet candidates = new CandidateGenerator().generate(AGENT, world, UTILITY);

        assertEquals(2, candidates.candidates().size());
        TaskSpec staging = candidates.candidates().get(0).task();
        assertEquals("T5:stage:east_lane:wave-3:agent-0:at-50", staging.taskId());
        assertEquals(TaskType.DEFEND_REGION, staging.type());
        assertEquals(1.0, staging.priority(), 1e-12);
        assertEquals(600, staging.estimatedTicks());
        assertFalse(staging.exclusive());
        assertTrue(candidates.candidates().get(0).valid());
        assertEquals(TaskType.WAIT, candidates.candidates().get(1).task().type());
    }

    @Test void ordinaryWorkPrecedesProactiveDefenseStaging(){
        CandidateSet candidates = new CandidateGenerator().generate(
            AGENT, activeWorld(List.of()), UTILITY);

        assertTrue(candidates.candidates().stream()
            .noneMatch(candidate -> candidate.task().taskId().contains(":stage:")));
    }

    @Test void partnerOwnedSchematicExposesLearnedSeatStagingBesideOrdinaryWork(){
        CandidateWorldSnapshot world = quietWorldWithOrdinaryWork(1200f, 0);
        CandidateSet candidates = new CandidateGenerator().generate(
            AGENT, world, UTILITY, true);

        assertTrue(candidates.candidates().stream()
            .anyMatch(candidate -> candidate.task().type() == TaskType.HARVEST_RESOURCE));
        TaskSpec staging = stagingCandidate(candidates).task();
        assertEquals("T5:stage:east_lane:wave-1:agent-0:at-50", staging.taskId());
        assertEquals(1.0, staging.priority(), 1e-12);
        assertFalse(staging.exclusive());
    }

    @Test void defaultGenerationRemainsUnchangedBesideOrdinaryWork(){
        CandidateWorldSnapshot world = quietWorldWithOrdinaryWork(1200f, 0);

        assertArrayEquals(
            new CandidateGenerator().generate(AGENT, world, UTILITY).canonicalBytes(),
            new CandidateGenerator().generate(AGENT, world, UTILITY, false).canonicalBytes());
        assertTrue(new CandidateGenerator().generate(AGENT, world, UTILITY).candidates().stream()
            .noneMatch(candidate -> candidate.task().taskId().contains(":stage:")));
    }

    @Test void partnerOwnedSchematicNeverExposesStagingToScriptedSeat(){
        AgentSnapshot partner = new AgentSnapshot(AgentId.of(1),
            100f, 100f, 1000f, ALL_CAPABILITIES);
        CandidateSet candidates = new CandidateGenerator().generate(
            partner, quietWorldWithOrdinaryWork(1200f, 0), UTILITY, true);

        assertTrue(candidates.candidates().stream()
            .noneMatch(candidate -> candidate.task().taskId().contains(":stage:")));
    }

    @Test void partnerOwnedSchematicDoesNotStageDuringCombatOrAtDefendLead(){
        CandidateGenerator generator = new CandidateGenerator();
        CandidateSet combat = generator.generate(
            AGENT, quietWorldWithOrdinaryWork(1200f, 1), UTILITY, true);
        CandidateSet defendLead = generator.generate(
            AGENT, quietWorldWithOrdinaryWork(600f, 0), UTILITY, true);

        assertTrue(combat.candidates().stream()
            .noneMatch(candidate -> candidate.task().taskId().contains(":stage:")));
        assertTrue(defendLead.candidates().stream()
            .noneMatch(candidate -> candidate.task().taskId().contains(":stage:")));
    }

    @Test void proactiveDefenseStagingIsScopedToTheLearnedSeat(){
        AgentSnapshot partner = new AgentSnapshot(AgentId.of(1),
            100f, 100f, 1000f, ALL_CAPABILITIES);
        CandidateSet candidates = new CandidateGenerator().generate(
            partner, satisfiedWorld(1200f), UTILITY);

        assertEquals(1, candidates.candidates().size());
        assertEquals(TaskType.WAIT, candidates.candidates().get(0).task().type());
    }

    @Test void supplyRequiresCurrentCoreOrCarriedCopper(){
        CandidateWorldSnapshot world = copyWithCore(activeWorld(List.of(
            new TurretSnapshot(7, 30, 24, 0)
        )), 0);
        TaskCandidate empty = supplyCandidate(new CandidateGenerator(16)
            .generate(AGENT, world, UTILITY));
        assertFalse(empty.valid());
        assertEquals("resources_unavailable:copper", empty.invalidReason());

        AgentSnapshot carryingCopper = new AgentSnapshot(AgentId.of(0),
            100f, 100f, 1000f, ALL_CAPABILITIES, "copper", 1);
        assertTrue(supplyCandidate(new CandidateGenerator(16)
            .generate(carryingCopper, world, UTILITY)).valid());

        AgentSnapshot carryingLead = new AgentSnapshot(AgentId.of(0),
            100f, 100f, 1000f, ALL_CAPABILITIES, "lead", 1);
        assertEquals("resources_unavailable:copper",
            supplyCandidate(new CandidateGenerator(16)
                .generate(carryingLead, world, UTILITY)).invalidReason());
    }

    @Test void completedBuildLineIsRemovedWhileOtherWorkRemains(){
        CandidateWorldSnapshot world = new CandidateWorldSnapshot(
            50, 8, "T1", "T2", "T3", "T4", "T6", "T5", 200, 300,
            true, economy(true), 31, false, 120,
            84f, 84f, 224f, 224f, "copper_line_v1",
            260f, 196f, "east_duo_v1", 2, List.of(), List.of(), 10,
            0, 260f, 196f, "defense_block",
            0, 1200f, defense(0.0, 0.0), 300f, 196f, "east_lane"
        );

        List<TaskType> types = new CandidateGenerator().generate(AGENT, world, UTILITY)
            .candidates().stream().map(candidate -> candidate.task().type()).toList();
        assertFalse(types.contains(TaskType.BUILD_LINE));
        assertTrue(types.contains(TaskType.BUILD_SCHEMATIC));
    }

    @Test void exposesWaveGatedScenarioPlannedSchematics(){
        PlannedSchematicSnapshot initial = new PlannedSchematicSnapshot(
            "expert:build:fortification", "fortification", 32, 24, 180,
            false, 1, 0.92, List.of("T2:build:copper_line_v1"));
        PlannedSchematicSnapshot expansion = new PlannedSchematicSnapshot(
            "expert:build:expansion-wave-1", "expansion-wave-1", 32, 24, 90,
            false, 2, 0.95, List.of("expert:build:fortification"));
        CandidateWorldSnapshot base = activeWorld(List.of());
        CandidateWorldSnapshot world = copyWithPlan(base, 2, List.of(initial, expansion));

        List<TaskSpec> planned = new CandidateGenerator(16).generate(AGENT, world, UTILITY)
            .candidates().stream().map(TaskCandidate::task)
            .filter(task -> task.taskId().startsWith("expert:build:"))
            .toList();

        assertEquals(List.of("expert:build:fortification", "expert:build:expansion-wave-1"),
            planned.stream().map(TaskSpec::taskId).toList());
        assertEquals(List.of("T2:build:copper_line_v1"),
            planned.get(0).dependencyTaskIds());
        assertEquals(List.of("expert:build:fortification"),
            planned.get(1).dependencyTaskIds());
    }

    @Test void economyRequiresConnectivityRateAndFullSampleWindow(){
        assertFalse(new EconomySnapshot(true, true, 0.7, 0.6, 599, 600).operational());
        assertFalse(new EconomySnapshot(true, false, 0.7, 0.6, 600, 600).operational());
        assertFalse(new EconomySnapshot(true, true, 0.5, 0.6, 600, 600).operational());
        assertTrue(new EconomySnapshot(true, true, 0.7, 0.6, 600, 600).operational());
    }

    @Test void prioritiesAndSupplyBatchAreDerivedFromLiveDeficits(){
        CandidateWorldSnapshot world = copyWithCore(activeWorld(List.of(
            new TurretSnapshot(7, 30, 24, 0)
        )), 2);
        List<TaskSpec> tasks = new CandidateGenerator(16).generate(AGENT, world, UTILITY)
            .candidates().stream().map(TaskCandidate::task).toList();

        TaskSpec harvest = tasks.stream().filter(task -> task.type() == TaskType.HARVEST_RESOURCE)
            .findFirst().orElseThrow();
        TaskSpec line = tasks.stream().filter(task -> task.type() == TaskType.BUILD_LINE)
            .findFirst().orElseThrow();
        TaskSpec supply = tasks.stream().filter(task -> task.type() == TaskType.SUPPLY_TURRET)
            .findFirst().orElseThrow();
        TaskSpec defend = tasks.stream().filter(task -> task.type() == TaskType.DEFEND_REGION)
            .findFirst().orElseThrow();

        assertEquals(298.0 / 300.0, harvest.priority(), 1e-12);
        assertEquals(1.0, line.priority(), 1e-12);
        assertEquals(2, supply.estimatedCost().amount("copper"));
        assertEquals(0.5, defend.priority(), 1e-12);
    }

    private static CandidateWorldSnapshot activeWorld(List<TurretSnapshot> turrets){
        return new CandidateWorldSnapshot(
            50, 8, "T1", "T2", "T3", "T4", "T6", "T5", 200, 300,
            false, economy(false), 31, false, 120,
            84f, 84f, 224f, 224f, "copper_line_v1",
            260f, 196f, "east_duo_v1",
            1, List.of(),
            turrets, 10,
            3, 260f, 196f, "defense_block",
            0, 400f, defense(0.0, 0.5), 300f, 196f, "east_lane"
        );
    }

    private static CandidateWorldSnapshot satisfiedWorld(float timeToNextWave){
        return new CandidateWorldSnapshot(
            50, 8, "T1", "T2", "T3", "T4", "T6", "T5", 400, 300,
            true, economy(true), 31, true, 120,
            84f, 84f, 224f, 224f, "copper_line_v1",
            260f, 196f, "east_duo_v1",
            3, List.of(),
            List.of(new TurretSnapshot(7, 30, 24, 10)), 10,
            0, 260f, 196f, "defense_block",
            0, timeToNextWave, defense(1.0, 0.0), 300f, 196f, "east_lane"
        );
    }

    private static CandidateWorldSnapshot quietWorldWithOrdinaryWork(
        float timeToNextWave,
        int enemyCount
    ){
        CandidateWorldSnapshot world = activeWorld(List.of());
        return new CandidateWorldSnapshot(
            world.tick(), world.tileSize(), world.harvestTaskId(), world.buildLineTaskId(),
            world.schematicTaskId(), world.supplyTaskId(), world.rebuildTaskId(),
            world.defendTaskId(), world.coreCopper(), world.harvestCopperThreshold(),
            world.buildLineComplete(), world.economy(), world.buildLineCopperCost(),
            world.schematicComplete(), world.schematicCopperCost(), world.harvestWorldX(),
            world.harvestWorldY(), world.buildLineWorldX(), world.buildLineWorldY(),
            world.buildLineId(), world.schematicWorldX(), world.schematicWorldY(),
            world.schematicId(), world.waveNumber(), world.plannedSchematics(), world.turrets(),
            world.turretTargetAmmo(), world.brokenBlockCount(), world.rebuildWorldX(),
            world.rebuildWorldY(), world.rebuildRegionId(), enemyCount, timeToNextWave,
            defense(0.0, 0.0), world.defendWorldX(), world.defendWorldY(),
            world.defendRegionId());
    }

    private static TaskCandidate stagingCandidate(CandidateSet set){
        return set.candidates().stream()
            .filter(candidate -> candidate.task().taskId().contains(":stage:"))
            .findFirst().orElseThrow();
    }

    private static TaskCandidate supplyCandidate(CandidateSet set){
        return set.candidates().stream()
            .filter(candidate -> candidate.task().type() == TaskType.SUPPLY_TURRET)
            .findFirst().orElseThrow();
    }

    private static CandidateWorldSnapshot copyWithPlan(
        CandidateWorldSnapshot world,
        int waveNumber,
        List<PlannedSchematicSnapshot> plan
    ){
        return new CandidateWorldSnapshot(
            world.tick(), world.tileSize(), world.harvestTaskId(), world.buildLineTaskId(),
            world.schematicTaskId(), world.supplyTaskId(), world.rebuildTaskId(),
            world.defendTaskId(), world.coreCopper(), world.harvestCopperThreshold(),
            world.buildLineComplete(), world.economy(), world.buildLineCopperCost(),
            world.schematicComplete(),
            world.schematicCopperCost(), world.harvestWorldX(), world.harvestWorldY(),
            world.buildLineWorldX(), world.buildLineWorldY(), world.buildLineId(),
            world.schematicWorldX(), world.schematicWorldY(), world.schematicId(),
            waveNumber, plan, world.turrets(), world.turretTargetAmmo(),
            world.brokenBlockCount(), world.rebuildWorldX(), world.rebuildWorldY(),
            world.rebuildRegionId(), 0, world.timeToNextWave(),
            world.defenseReadiness(), world.defendWorldX(), world.defendWorldY(),
            world.defendRegionId());
    }

    private static CandidateWorldSnapshot copyWithCore(
        CandidateWorldSnapshot world,
        int coreCopper
    ){
        return new CandidateWorldSnapshot(
            world.tick(), world.tileSize(), world.harvestTaskId(), world.buildLineTaskId(),
            world.schematicTaskId(), world.supplyTaskId(), world.rebuildTaskId(),
            world.defendTaskId(), coreCopper, world.harvestCopperThreshold(),
            world.buildLineComplete(), world.economy(), world.buildLineCopperCost(),
            world.schematicComplete(), world.schematicCopperCost(), world.harvestWorldX(),
            world.harvestWorldY(), world.buildLineWorldX(), world.buildLineWorldY(),
            world.buildLineId(), world.schematicWorldX(), world.schematicWorldY(),
            world.schematicId(), world.waveNumber(), world.plannedSchematics(), world.turrets(),
            world.turretTargetAmmo(), world.brokenBlockCount(), world.rebuildWorldX(),
            world.rebuildWorldY(), world.rebuildRegionId(), world.enemyCount(),
            world.timeToNextWave(), world.defenseReadiness(), world.defendWorldX(),
            world.defendWorldY(), world.defendRegionId());
    }

    private static EconomySnapshot economy(boolean operational){
        return new EconomySnapshot(operational, operational, operational ? 0.7 : 0.0,
            0.6, operational ? 600 : 0, 600);
    }

    private static DefenseReadinessSnapshot defense(double readiness, double imminence){
        return new DefenseReadinessSnapshot(1, 3, 450.0, 124.5, 51, 10,
            readiness >= 1.0 ? 2 : 0, 2, readiness >= 1.0 ? 51 : 0,
            readiness, readiness, readiness, readiness, 600, imminence);
    }
}
