package agentcore.candidates;

import agentcore.AgentId;
import agentcore.TaskType;
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
            "T1:harvest:copper",
            "T2:build:copper_line_v1",
            "T3:build:east_duo_v1",
            "T4:supply:7",
            "T4:supply:19",
            "T6:rebuild:defense_block",
            "T5:defend:east_lane",
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
            (agent, task, tick) -> task.taskId().equals("T4:supply:20")
                ? 100.0 : task.type() == TaskType.DEFEND_REGION ? -100.0 : task.priority());
        List<String> ids = candidates.candidates().stream()
            .map(candidate -> candidate.task().taskId()).toList();
        assertEquals(8, candidates.candidates().size());
        assertEquals("runtime:wait", candidates.candidates().get(7).task().taskId());
        assertTrue(ids.contains("T4:supply:20"), "late high-utility task must survive truncation");
        assertTrue(ids.contains("T5:defend:east_lane"), "DEFEND always retains an overflow slot");
        assertFalse(ids.contains("T1:harvest:copper"), "lower utility task should be truncated");
    }

    @Test void satisfiedAndSafeWorldProducesOnlyWait(){
        CandidateWorldSnapshot world = new CandidateWorldSnapshot(
            50, 8, "T1", "T2", "T3", "T4", "T6", "T5", 400, 300,
            true, 31, true, 120,
            84f, 84f, 224f, 224f, "copper_line_v1",
            260f, 196f, "east_duo_v1",
            List.of(new TurretSnapshot(7, 30, 24, 10)), 10,
            0, 260f, 196f, "defense_block",
            0, 1200f, 600, 300f, 196f, "east_lane"
        );

        CandidateSet candidates = new CandidateGenerator().generate(AGENT, world, UTILITY);
        assertEquals(1, candidates.candidates().size());
        assertEquals("runtime:wait", candidates.candidates().get(0).task().taskId());
        assertTrue(candidates.candidates().get(0).valid());
    }

    @Test void completedBuildLineIsRemovedWhileOtherWorkRemains(){
        CandidateWorldSnapshot world = new CandidateWorldSnapshot(
            50, 8, "T1", "T2", "T3", "T4", "T6", "T5", 200, 300,
            true, 31, false, 120,
            84f, 84f, 224f, 224f, "copper_line_v1",
            260f, 196f, "east_duo_v1", List.of(), 10,
            0, 260f, 196f, "defense_block",
            0, 1200f, 600, 300f, 196f, "east_lane"
        );

        List<TaskType> types = new CandidateGenerator().generate(AGENT, world, UTILITY)
            .candidates().stream().map(candidate -> candidate.task().type()).toList();
        assertFalse(types.contains(TaskType.BUILD_LINE));
        assertTrue(types.contains(TaskType.BUILD_SCHEMATIC));
    }

    private static CandidateWorldSnapshot activeWorld(List<TurretSnapshot> turrets){
        return new CandidateWorldSnapshot(
            50, 8, "T1", "T2", "T3", "T4", "T6", "T5", 200, 300,
            false, 31, false, 120,
            84f, 84f, 224f, 224f, "copper_line_v1",
            260f, 196f, "east_duo_v1",
            turrets, 10,
            3, 260f, 196f, "defense_block",
            2, 400f, 600, 300f, 196f, "east_lane"
        );
    }
}
