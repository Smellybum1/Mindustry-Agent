package agentcore.human;

import agentcore.*;
import agentcore.candidates.*;
import agentcore.human.HumanActionPolicy.*;
import agentcore.human.HumanControl.*;
import agentcore.task.*;
import org.junit.jupiter.api.*;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class HumanActionPolicyTest{
    private final HumanActionPolicy policy = new HumanActionPolicy();

    @Test void normalBindsEachGoalToHighestUtilityIdleSeat(){
        Snapshot controls = snapshot(AutonomyLevel.NORMAL, List.of(
            goal("human:goal:1"), goal("human:goal:2")), List.of());
        List<AgentBoundary> agents = List.of(
            boundary(0, "", candidates(Map.of("human:goal:1", 3.0, "human:goal:2", 8.0))),
            boundary(1, "", candidates(Map.of("human:goal:1", 5.0, "human:goal:2", 7.0))),
            boundary(2, "busy", candidates(Map.of("human:goal:1", 9.0, "human:goal:2", 9.0)))
        );
        assertEquals(Map.of(0, "human:goal:2", 1, "human:goal:1"),
            policy.bindings(controls, agents));
    }

    @Test void lowAllowsOnlyExplicitGoalAndForcesOtherSeatToWait(){
        Snapshot controls = snapshot(AutonomyLevel.LOW, List.of(goal("human:goal:1")),
            List.of(new Assignment(1, "human:goal:1")));
        AgentBoundary assigned = boundary(1, "", candidates(Map.of("human:goal:1", 5.0)));
        BaseMask assignedMask = policy.constrain(assigned, controls,
            policy.bindings(controls, List.of(assigned)));
        assertEquals(List.of(false, true, false), assignedMask.candidateTask());

        AgentBoundary unassigned = boundary(0, "", candidates(Map.of("human:goal:1", 5.0)));
        BaseMask waiting = policy.constrain(unassigned, controls,
            policy.bindings(controls, List.of(unassigned, assigned)));
        assertEquals(List.of(false, false, false), waiting.candidateTask());
        assertFalse(waiting.continueCurrentTask());
    }

    @Test void highLeavesUnassignedHumanGoalAdvisoryButHonorsExplicitOwner(){
        Snapshot advisory = snapshot(AutonomyLevel.HIGH, List.of(goal("human:goal:1")),
            List.of());
        AgentBoundary agent = boundary(0, "", candidates(Map.of("human:goal:1", 5.0)));
        assertEquals(List.of(true, true, true),
            policy.constrain(agent, advisory, policy.bindings(advisory, List.of(agent)))
                .candidateTask());

        Snapshot assigned = snapshot(AutonomyLevel.HIGH, List.of(goal("human:goal:1")),
            List.of(new Assignment(1, "human:goal:1")));
        assertEquals(List.of(true, false, true),
            policy.constrain(agent, assigned, policy.bindings(assigned, List.of(agent)))
                .candidateTask());
    }

    @Test void boundGoalMayContinueOnlyItsOwnCurrentTask(){
        Snapshot controls = snapshot(AutonomyLevel.NORMAL, List.of(goal("human:goal:1")),
            List.of(new Assignment(0, "human:goal:1")));
        BaseMask own = policy.constrain(boundary(0, "human:goal:1",
                candidates(Map.of("human:goal:1", 1.0))),
            controls, Map.of(0, "human:goal:1"));
        BaseMask other = policy.constrain(boundary(0, "ordinary",
                candidates(Map.of("human:goal:1", 1.0))),
            controls, Map.of(0, "human:goal:1"));
        assertTrue(own.continueCurrentTask());
        assertFalse(other.continueCurrentTask());
        assertTrue(other.abandon());
    }

    private static AgentBoundary boundary(int index, String current, CandidateSet candidates){
        ArrayList<Boolean> allowed = new ArrayList<>();
        for(int i = 0; i < candidates.candidates().size(); i++) allowed.add(true);
        return new AgentBoundary(index, current, candidates,
            new BaseMask(allowed, true, true));
    }

    private static CandidateSet candidates(Map<String, Double> human){
        ArrayList<TaskCandidate> result = new ArrayList<>();
        result.add(candidate("ordinary", TaskType.BUILD_LINE, 1.0, false));
        human.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry ->
            result.add(candidate(entry.getKey(), TaskType.DEFEND_REGION,
                entry.getValue(), true)));
        result.add(new TaskCandidate(TaskSpec.builder("runtime:wait", TaskType.WAIT).build(),
            true, "", 0.0));
        return new CandidateSet(result);
    }

    private static TaskCandidate candidate(String id, TaskType type, double utility,
                                           boolean human){
        TaskSpec.Builder builder = TaskSpec.builder(id, type).target(new RegionTarget("east"));
        if(human) builder.humanOrigin(id);
        return new TaskCandidate(builder.build(), true, "", utility);
    }

    private static Goal goal(String id){
        return new Goal(id, TaskType.DEFEND_REGION, "east", "player", 0, 1,
            GoalStatus.ACTIVE);
    }

    private static Snapshot snapshot(AutonomyLevel autonomy, List<Goal> goals,
                                     List<Assignment> assignments){
        return new Snapshot(goals, assignments, autonomy, false, 1);
    }
}
