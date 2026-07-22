package agentcore.policy;

import agentcore.*;
import agentcore.candidates.*;
import agentcore.policy.GreedyUtilityPolicy.*;
import agentcore.skill.*;
import agentcore.task.*;
import org.junit.jupiter.api.*;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class GreedyUtilityPolicyTest{
    private final GreedyUtilityPolicy policy = new GreedyUtilityPolicy();

    @Test void selectsHighestUtilityWithStableIndexTieBreak(){
        AgentView agent = view(0, "", SkillStatus.READY, SkillReason.NONE,
            candidates(2.0, 4.0, 4.0), mask(true, true, true));

        assertEquals(Action.select(0, 1), policy.action(agent, team(0, 0, 1.0)));
    }

    @Test void continuesActiveWorkBeforeSelecting(){
        AgentView agent = new AgentView(0, "BUILD", SkillStatus.RUNNING, SkillReason.NONE,
            candidates(10.0), new ActionMask(List.of(true), true, true));

        assertEquals(Action.simple(0, ActionType.CONTINUE_CURRENT_TASK),
            policy.action(agent, team(10, 0, 1.0)));
    }

    @Test void wavePreemptsNonCombatWork(){
        AgentView agent = new AgentView(0, "BUILD", SkillStatus.RUNNING, SkillReason.NONE,
            candidates(10.0), new ActionMask(List.of(true), true, true));

        assertEquals(Action.abandon(0, "wave_preempt"),
            policy.action(agent, team(10, 1, 0.0)));
    }

    @Test void replanThrottleAllowsThreeAbandonsPerWindow(){
        AgentView blocked = new AgentView(0, "BUILD", SkillStatus.BLOCKED,
            SkillReason.RESOURCES_SHORT, candidates(1.0),
            new ActionMask(List.of(true), true, true));

        for(int tick : List.of(10, 20, 30)){
            assertEquals(Action.abandon(0, "resources_short_replan"),
                policy.action(blocked, team(tick, 0, 1.0)));
        }
        assertEquals(Action.simple(0, ActionType.CONTINUE_CURRENT_TASK),
            policy.action(blocked, team(40, 0, 1.0)));
        assertEquals(Action.abandon(0, "resources_short_replan"),
            policy.action(blocked, team(191, 0, 1.0)));
    }

    @Test void undersuppliedCombatKeepsOneLogisticsSeatThroughTheWave(){
        List<AgentView> defenders = List.of(
            defending(0), defending(1), defending(2));
        List<Action> actions = policy.actions(defenders, team(100, 3, 0.5));

        assertEquals(Action.abandon(2, "readiness_rebalance"), actions.get(2));

        AgentView idle = new AgentView(2, "", SkillStatus.READY, SkillReason.NONE,
            new CandidateSet(List.of(
                candidate("defend", TaskType.DEFEND_REGION, 5.0),
                candidate("supply", TaskType.SUPPLY_TURRET, 1.0)
            )), mask(true, true));
        assertEquals(Action.select(2, 1), policy.action(idle, team(101, 3, 0.5)));

        policy.observeActionResults(List.of(new ActionResult(2, true)));
        assertEquals(Action.select(2, 1), policy.action(idle, team(102, 3, 0.5)));

        AgentView supplied = new AgentView(2, "", SkillStatus.READY, SkillReason.NONE,
            idle.candidates(), mask(true, false));
        assertEquals(Action.simple(2, ActionType.WAIT),
            policy.action(supplied, team(103, 3, 1.0)));
        assertEquals(Action.select(2, 0), policy.action(supplied, team(104, 0, 1.0)));
    }

    private static AgentView defending(int index){
        return new AgentView(index, "DEFEND", SkillStatus.RUNNING, SkillReason.NONE,
            candidates(1.0), new ActionMask(List.of(true), true, true));
    }

    private static AgentView view(int index, String skill, SkillStatus status, SkillReason reason,
                                  CandidateSet candidates, ActionMask mask){
        return new AgentView(index, skill, status, reason, candidates, mask);
    }

    private static TeamView team(long tick, int enemies, double ammo){
        return new TeamView(tick, enemies, ammo);
    }

    private static ActionMask mask(boolean... values){
        ArrayList<Boolean> result = new ArrayList<>();
        for(boolean value : values) result.add(value);
        return new ActionMask(result, false, false);
    }

    private static CandidateSet candidates(double... utilities){
        ArrayList<TaskCandidate> result = new ArrayList<>();
        for(int i = 0; i < utilities.length; i++){
            result.add(candidate("task-" + i, TaskType.WAIT, utilities[i]));
        }
        return new CandidateSet(result);
    }

    private static TaskCandidate candidate(String id, TaskType type, double utility){
        return new TaskCandidate(TaskSpec.builder(id, type).build(), true, "", utility);
    }
}
