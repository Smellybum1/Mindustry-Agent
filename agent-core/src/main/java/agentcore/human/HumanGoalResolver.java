package agentcore.human;

import agentcore.AgentId;
import agentcore.candidates.*;
import agentcore.human.HumanControl.*;
import agentcore.task.*;
import agentcore.utility.TaskUtility;

import java.util.*;

/** Behavior-neutral overlay from structured human goals to safe ordinary candidates. */
public final class HumanGoalResolver{
    public static final int DEFAULT_MAX_CANDIDATES = 8;

    @FunctionalInterface
    public interface RegionMatcher{
        boolean matches(TaskSpec task, String regionId);
    }

    public record GoalResult(String goalId, boolean matched, String reason){}

    public record Resolution(CandidateSet candidates, List<GoalResult> goals){
        public Resolution{
            Objects.requireNonNull(candidates, "candidates");
            goals = List.copyOf(goals);
        }
    }

    private final int maxCandidates;

    public HumanGoalResolver(){
        this(DEFAULT_MAX_CANDIDATES);
    }

    public HumanGoalResolver(int maxCandidates){
        if(maxCandidates < 1) throw new IllegalArgumentException("maxCandidates must be >= 1");
        this.maxCandidates = maxCandidates;
    }

    public Resolution resolve(
        Snapshot controls,
        CandidateSet ordinary,
        TaskUtility utility,
        AgentId agentId,
        long tick
    ){
        return resolve(controls, ordinary, utility, agentId, tick,
            HumanGoalResolver::matchesRegionTarget);
    }

    public Resolution resolve(
        Snapshot controls,
        CandidateSet ordinary,
        TaskUtility utility,
        AgentId agentId,
        long tick,
        RegionMatcher regions
    ){
        Objects.requireNonNull(controls, "controls");
        Objects.requireNonNull(ordinary, "ordinary");
        Objects.requireNonNull(utility, "utility");
        Objects.requireNonNull(agentId, "agentId");
        Objects.requireNonNull(regions, "regions");
        if(controls.activeGoals().isEmpty()){
            return new Resolution(ordinary, List.of());
        }

        List<TaskCandidate> source = ordinary.candidates();
        int waitIndex = waitIndex(source);
        if(waitIndex < 0){
            throw new IllegalArgumentException("ordinary candidates must contain WAIT");
        }
        TaskCandidate wait = source.get(waitIndex);
        boolean[] consumed = new boolean[source.size()];
        ArrayList<TaskCandidate> human = new ArrayList<>();
        ArrayList<GoalResult> results = new ArrayList<>();

        for(Goal goal : controls.activeGoals()){
            int match = matchingCandidate(goal, source, consumed, waitIndex, regions);
            if(match < 0){
                results.add(new GoalResult(goal.id(), false, "no_valid_candidate"));
                continue;
            }
            consumed[match] = true;
            TaskSpec wrapped = humanTask(goal, source.get(match).task());
            human.add(new TaskCandidate(wrapped, true, "",
                utility.score(agentId, wrapped, tick)));
            results.add(new GoalResult(goal.id(), true, "candidate_available"));
        }

        if(human.isEmpty()) return new Resolution(ordinary, results);
        ArrayList<TaskCandidate> overlaid = new ArrayList<>();
        for(TaskCandidate candidate : human){
            if(overlaid.size() >= maxCandidates - 1) break;
            overlaid.add(candidate);
        }
        for(int i = 0; i < source.size() && overlaid.size() < maxCandidates - 1; i++){
            if(i != waitIndex && !consumed[i]) overlaid.add(source.get(i));
        }
        if(wait != null) overlaid.add(wait);
        return new Resolution(new CandidateSet(overlaid), results);
    }

    private static int matchingCandidate(
        Goal goal,
        List<TaskCandidate> candidates,
        boolean[] consumed,
        int waitIndex,
        RegionMatcher regions
    ){
        for(int i = 0; i < candidates.size(); i++){
            TaskCandidate candidate = candidates.get(i);
            if(i == waitIndex || consumed[i] || !candidate.valid()) continue;
            if(candidate.task().type() == goal.taskType()
                && regions.matches(candidate.task(), goal.regionId())) return i;
        }
        return -1;
    }

    private static TaskSpec humanTask(Goal goal, TaskSpec source){
        return TaskSpec.builder(goal.id(), source.type())
            .target(source.target())
            .priority(source.priority())
            .estimatedTicks(source.estimatedTicks())
            .estimatedCost(source.estimatedCost())
            .requiredCapabilities(source.requiredCapabilities())
            .helpersRequested(source.helpersRequested())
            .exclusive(source.exclusive())
            .parentTaskId(source.parentTaskId())
            .dependencyTaskIds(source.dependencyTaskIds())
            .humanOrigin(goal.id())
            .build();
    }

    private static int waitIndex(List<TaskCandidate> candidates){
        for(int i = candidates.size() - 1; i >= 0; i--){
            if(candidates.get(i).task().type() == agentcore.TaskType.WAIT) return i;
        }
        return -1;
    }

    private static boolean matchesRegionTarget(TaskSpec task, String regionId){
        return task.target() instanceof RegionTarget region
            && region.regionId().equals(regionId);
    }
}
