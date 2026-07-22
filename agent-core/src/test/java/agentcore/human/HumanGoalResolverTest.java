package agentcore.human;

import agentcore.*;
import agentcore.candidates.*;
import agentcore.human.HumanControl.*;
import agentcore.human.HumanGoalResolver.*;
import agentcore.task.*;
import agentcore.utility.TaskUtility;
import org.junit.jupiter.api.*;

import java.nio.charset.StandardCharsets;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class HumanGoalResolverTest{
    private static final AgentId AGENT = AgentId.of(0);
    private static final TaskUtility UTILITY = (agent, task, tick) ->
        task.origin() == TaskOrigin.HUMAN ? 9.0 : 1.0;
    private final HumanGoalResolver resolver = new HumanGoalResolver();

    @Test void emptyControlReturnsTheExactOrdinaryCandidateSet(){
        CandidateSet ordinary = ordinarySet();
        Resolution resolution = resolver.resolve(empty(), ordinary, UTILITY, AGENT, 10);
        assertSame(ordinary, resolution.candidates());
        assertArrayEquals(ordinary.canonicalBytes(), resolution.candidates().canonicalBytes());
        assertTrue(resolution.goals().isEmpty());
    }

    @Test void matchingGoalWrapsOnlyAnExistingValidCandidate(){
        Snapshot controls = snapshot(goal("human:goal:1", TaskType.DEFEND_REGION, "east"));
        Resolution resolution = resolver.resolve(controls, ordinarySet(), UTILITY, AGENT, 10);

        List<TaskCandidate> candidates = resolution.candidates().candidates();
        TaskSpec human = candidates.get(0).task();
        assertEquals("human:goal:1", human.taskId());
        assertEquals(TaskOrigin.HUMAN, human.origin());
        assertEquals("human:goal:1", human.sourceGoalId());
        assertEquals(new RegionTarget("east"), human.target());
        assertEquals(9.0, candidates.get(0).utility());
        assertEquals(List.of("ordinary:line", "runtime:wait"), candidates.subList(1, 3)
            .stream().map(candidate -> candidate.task().taskId()).toList());
        assertEquals(TaskType.WAIT, candidates.get(candidates.size() - 1).task().type());
        assertEquals(new GoalResult("human:goal:1", true, "candidate_available"),
            resolution.goals().get(0));
    }

    @Test void invalidOrStructurallyUnmatchedWorkIsNeverWrapped(){
        TaskCandidate invalid = candidate("ordinary:defend", TaskType.DEFEND_REGION,
            new RegionTarget("east"), false);
        CandidateSet ordinary = new CandidateSet(List.of(invalid, waitCandidate()));
        Snapshot controls = snapshot(goal("human:goal:1", TaskType.DEFEND_REGION, "east"));

        Resolution resolution = resolver.resolve(controls, ordinary, UTILITY, AGENT, 10);
        assertSame(ordinary, resolution.candidates());
        assertEquals("no_valid_candidate", resolution.goals().get(0).reason());

        TaskCandidate resource = candidate("ordinary:harvest", TaskType.HARVEST_RESOURCE,
            new ResourceTarget("copper", 10), true);
        CandidateSet resourceSet = new CandidateSet(List.of(resource, waitCandidate()));
        Snapshot resourceGoal = snapshot(goal("human:goal:2", TaskType.HARVEST_RESOURCE, "ore"));
        assertSame(resourceSet,
            resolver.resolve(resourceGoal, resourceSet, UTILITY, AGENT, 10).candidates());
    }

    @Test void AdapterMayMatchNonRegionTargetsWithoutUsingRenderedText(){
        TaskCandidate resource = candidate("ordinary:harvest", TaskType.HARVEST_RESOURCE,
            new ResourceTarget("copper", 10), true);
        CandidateSet ordinary = new CandidateSet(List.of(resource, waitCandidate()));
        Snapshot controls = snapshot(goal("human:goal:1", TaskType.HARVEST_RESOURCE, "ore"));

        Resolution resolution = resolver.resolve(controls, ordinary, UTILITY, AGENT, 10,
            (task, region) -> task.type() == TaskType.HARVEST_RESOURCE && region.equals("ore"));
        assertEquals(TaskOrigin.HUMAN,
            resolution.candidates().candidates().get(0).task().origin());
    }

    @Test void goalSequenceReservesBoundedSlotsAndWaitRemainsLast(){
        CandidateSet ordinary = new CandidateSet(List.of(
            candidate("ordinary:line", TaskType.BUILD_LINE, new RegionTarget("line"), true),
            candidate("ordinary:defend", TaskType.DEFEND_REGION, new RegionTarget("east"), true),
            candidate("ordinary:repair", TaskType.REPAIR_REGION, new RegionTarget("east"), true),
            waitCandidate()
        ));
        Snapshot controls = snapshot(
            goal("human:goal:1", TaskType.DEFEND_REGION, "east"),
            goal("human:goal:2", TaskType.BUILD_LINE, "line")
        );

        Resolution resolution = new HumanGoalResolver(3)
            .resolve(controls, ordinary, UTILITY, AGENT, 10);
        assertEquals(List.of("human:goal:1", "human:goal:2", "runtime:wait"),
            resolution.candidates().candidates().stream()
                .map(candidate -> candidate.task().taskId()).toList());
    }

    @Test void autonomousCanonicalBytesRetainTheirPreviousLayout(){
        TaskCandidate ordinary = new TaskCandidate(TaskSpec.builder("ordinary", TaskType.BUILD_LINE)
            .target(new RegionTarget("east"))
            .priority(0.5).estimatedTicks(10)
            .estimatedCost(ResourceCost.of("copper", 5))
            .requiredCapabilities(Set.of("build")).build(), true, "", 1.0);
        String expected = "ordinary|BUILD_LINE|region east|0x1.0p-1|10|copper=5|build|0|true|||"
            + "true||0x1.0p0";
        assertEquals(expected, new String(ordinary.canonicalBytes(), StandardCharsets.UTF_8));
    }

    private static CandidateSet ordinarySet(){
        return new CandidateSet(List.of(
            candidate("ordinary:line", TaskType.BUILD_LINE, new RegionTarget("line"), true),
            candidate("ordinary:defend", TaskType.DEFEND_REGION, new RegionTarget("east"), true),
            waitCandidate()
        ));
    }

    private static TaskCandidate candidate(String id, TaskType type, Target target, boolean valid){
        TaskSpec task = TaskSpec.builder(id, type).target(target).build();
        return new TaskCandidate(task, valid, valid ? "" : "out_of_range", 1.0);
    }

    private static TaskCandidate waitCandidate(){
        return new TaskCandidate(TaskSpec.builder("runtime:wait", TaskType.WAIT).build(),
            true, "", 0.0);
    }

    private static Goal goal(String id, TaskType type, String region){
        return new Goal(id, type, region, "player", 1, 1, GoalStatus.ACTIVE);
    }

    private static Snapshot snapshot(Goal... goals){
        return new Snapshot(List.of(goals), List.of(), AutonomyLevel.NORMAL, false, 1);
    }

    private static Snapshot empty(){
        return new Snapshot(List.of(), List.of(), AutonomyLevel.NORMAL, false, 0);
    }
}
