package agentcore.human;

import agentcore.TaskType;
import agentcore.candidates.*;
import agentcore.human.HumanControl.*;
import agentcore.task.*;

import java.util.*;

/** Deterministic human assignment/autonomy constraints over ordinary action masks. */
public final class HumanActionPolicy{
    public record BaseMask(List<Boolean> candidateTask, boolean continueCurrentTask,
                           boolean abandon){
        public BaseMask{
            candidateTask = List.copyOf(candidateTask == null ? List.of() : candidateTask);
        }

        public boolean candidateAllowed(int index){
            return index >= 0 && index < candidateTask.size() && candidateTask.get(index);
        }
    }

    public record AgentBoundary(int agentIndex, String currentTaskId, CandidateSet candidates,
                                BaseMask mask){
        public AgentBoundary{
            currentTaskId = currentTaskId == null ? "" : currentTaskId;
            Objects.requireNonNull(candidates, "candidates");
            Objects.requireNonNull(mask, "mask");
        }
    }

    public Map<Integer, String> bindings(Snapshot controls, List<AgentBoundary> agents){
        Objects.requireNonNull(controls, "controls");
        List<AgentBoundary> boundaries = agents == null ? List.of() : agents;
        TreeMap<Integer, String> bindings = new TreeMap<>();
        HashSet<String> explicitlyAssigned = new HashSet<>();
        for(Assignment assignment : controls.assignments()){
            bindings.put(assignment.agentIndex(), assignment.goalId());
            explicitlyAssigned.add(assignment.goalId());
        }
        if(controls.autonomy() != AutonomyLevel.NORMAL) return Map.copyOf(bindings);

        for(Goal goal : controls.activeGoals()){
            if(explicitlyAssigned.contains(goal.id())) continue;
            AgentBoundary best = null;
            double bestUtility = Double.NEGATIVE_INFINITY;
            for(AgentBoundary agent : boundaries){
                if(bindings.containsKey(agent.agentIndex()) || !agent.currentTaskId().isEmpty()) continue;
                int candidate = humanCandidateIndex(agent.candidates(), goal.id());
                if(candidate < 0 || !agent.mask().candidateAllowed(candidate)) continue;
                double utility = agent.candidates().candidates().get(candidate).utility();
                if(best == null || Double.compare(utility, bestUtility) > 0
                    || Double.compare(utility, bestUtility) == 0
                    && agent.agentIndex() < best.agentIndex()){
                    best = agent;
                    bestUtility = utility;
                }
            }
            if(best != null) bindings.put(best.agentIndex(), goal.id());
        }
        return Map.copyOf(bindings);
    }

    public BaseMask constrain(
        AgentBoundary agent,
        Snapshot controls,
        Map<Integer, String> bindings
    ){
        Objects.requireNonNull(agent, "agent");
        Objects.requireNonNull(controls, "controls");
        Map<Integer, String> resolved = bindings == null ? Map.of() : bindings;
        String boundGoal = resolved.get(agent.agentIndex());
        Map<String, Integer> explicitOwners = explicitOwners(controls);
        ArrayList<Boolean> candidateMask = new ArrayList<>();
        List<TaskCandidate> candidates = agent.candidates().candidates();
        for(int i = 0; i < candidates.size(); i++){
            TaskSpec task = candidates.get(i).task();
            boolean allowed = agent.mask().candidateAllowed(i);
            if(task.origin() == TaskOrigin.HUMAN){
                Integer owner = explicitOwners.get(task.sourceGoalId());
                if(boundGoal != null){
                    allowed &= task.sourceGoalId().equals(boundGoal);
                }else if(controls.autonomy() == AutonomyLevel.HIGH){
                    allowed &= owner == null || owner == agent.agentIndex();
                }else{
                    allowed = false;
                }
            }else if(task.type() != TaskType.WAIT
                && (boundGoal != null || controls.autonomy() == AutonomyLevel.LOW)){
                allowed = false;
            }else if(task.type() == TaskType.WAIT
                && (boundGoal != null || controls.autonomy() == AutonomyLevel.LOW)){
                allowed = false;
            }
            candidateMask.add(allowed);
        }
        boolean continueCurrent = agent.mask().continueCurrentTask();
        if(boundGoal != null) continueCurrent &= agent.currentTaskId().equals(boundGoal);
        else if(controls.autonomy() == AutonomyLevel.LOW) continueCurrent = false;
        return new BaseMask(candidateMask, continueCurrent, agent.mask().abandon());
    }

    private static Map<String, Integer> explicitOwners(Snapshot controls){
        HashMap<String, Integer> owners = new HashMap<>();
        for(Assignment assignment : controls.assignments()){
            owners.put(assignment.goalId(), assignment.agentIndex());
        }
        return owners;
    }

    private static int humanCandidateIndex(CandidateSet set, String goalId){
        for(int i = 0; i < set.candidates().size(); i++){
            TaskSpec task = set.candidates().get(i).task();
            if(task.origin() == TaskOrigin.HUMAN && task.sourceGoalId().equals(goalId)) return i;
        }
        return -1;
    }
}
