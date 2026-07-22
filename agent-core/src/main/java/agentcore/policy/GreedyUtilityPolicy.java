package agentcore.policy;

import agentcore.*;
import agentcore.candidates.*;
import agentcore.skill.*;

import java.util.*;

/** Deterministic Java fallback over the public candidate table and action mask. */
public final class GreedyUtilityPolicy{
    public static final long REPLAN_WINDOW_TICKS = 180L;
    public static final int MAX_REPLANS_PER_WINDOW = 3;

    private static final Set<SkillReason> replanableBlocks = EnumSet.of(
        SkillReason.RESOURCES_SHORT, SkillReason.CORE_SHORT, SkillReason.INVALID_TARGET,
        SkillReason.NO_CORE, SkillReason.CORE_FULL, SkillReason.STUCK, SkillReason.OCCUPIED,
        SkillReason.OUT_OF_RANGE, SkillReason.PLAN_REMOVED, SkillReason.CARGO_MISMATCH
    );

    public enum ActionType{
        SELECT_CANDIDATE_TASK, CONTINUE_CURRENT_TASK, ABANDON, WAIT
    }

    public record Action(int agentIndex, ActionType type, int candidateIndex, String reason){
        public Action{
            if(agentIndex < 0) throw new IllegalArgumentException("agentIndex must be non-negative");
            Objects.requireNonNull(type, "type");
            reason = reason == null ? "" : reason;
            if(type == ActionType.SELECT_CANDIDATE_TASK && candidateIndex < 0){
                throw new IllegalArgumentException("selection requires a candidate index");
            }
        }

        public static Action select(int agentIndex, int candidateIndex){
            return new Action(agentIndex, ActionType.SELECT_CANDIDATE_TASK, candidateIndex, "");
        }

        public static Action simple(int agentIndex, ActionType type){
            return new Action(agentIndex, type, -1, "");
        }

        public static Action abandon(int agentIndex, String reason){
            return new Action(agentIndex, ActionType.ABANDON, -1, reason);
        }
    }

    public record ActionMask(List<Boolean> candidateTask, boolean continueCurrentTask,
                             boolean abandon){
        public ActionMask{
            candidateTask = List.copyOf(candidateTask == null ? List.of() : candidateTask);
        }

        public boolean candidateAllowed(int index){
            return index >= 0 && index < candidateTask.size() && candidateTask.get(index);
        }
    }

    public record AgentView(int agentIndex, String activeSkill, SkillStatus skillStatus,
                            SkillReason skillReason, CandidateSet candidates, ActionMask mask){
        public AgentView{
            if(agentIndex < 0) throw new IllegalArgumentException("agentIndex must be non-negative");
            activeSkill = activeSkill == null ? "" : activeSkill;
            skillStatus = skillStatus == null ? SkillStatus.READY : skillStatus;
            skillReason = skillReason == null ? SkillReason.NONE : skillReason;
            candidates = candidates == null ? new CandidateSet(List.of()) : candidates;
            mask = mask == null ? new ActionMask(List.of(), false, false) : mask;
        }
    }

    public record TeamView(long tick, int enemyCount, double defenseAmmoCoverage){}

    public record ActionResult(int agentIndex, boolean accepted){}

    private final Map<Integer, ArrayDeque<Long>> replanTicks = new HashMap<>();
    private final Map<Integer, Long> lastTicks = new HashMap<>();
    private final Map<Integer, TaskType> preferredTypes = new HashMap<>();
    private final Map<Integer, TaskType> pendingPreferred = new HashMap<>();
    private final Set<Integer> returnToDefense = new HashSet<>();

    public void reset(){
        replanTicks.clear();
        lastTicks.clear();
        preferredTypes.clear();
        pendingPreferred.clear();
        returnToDefense.clear();
    }

    /** Advance preference state only after the authoritative adapter accepts a selection. */
    public void observeActionResults(List<ActionResult> results){
        for(ActionResult result : results == null ? List.<ActionResult>of() : results){
            TaskType preferred = pendingPreferred.remove(result.agentIndex());
            if(preferred == null || !result.accepted()) continue;
            preferredTypes.remove(result.agentIndex());
            if(preferred == TaskType.SUPPLY_TURRET) returnToDefense.add(result.agentIndex());
        }
    }

    /** Select one atomic team bundle, retaining one logistics seat during undersupplied combat. */
    public List<Action> actions(List<AgentView> agents, TeamView team){
        Objects.requireNonNull(team, "team");
        List<AgentView> views = agents == null ? List.of() : agents;
        ArrayList<Action> actions = new ArrayList<>();
        for(AgentView agent : views){
            actions.add(action(agent, team));
        }
        if(team.enemyCount() <= 0 || team.defenseAmmoCoverage() >= 1.0) return List.copyOf(actions);

        boolean supplierActive = views.stream().anyMatch(
            agent -> agent.activeSkill().equals("SUPPLY"));
        ArrayList<AgentView> defenders = new ArrayList<>();
        for(AgentView agent : views){
            if(agent.activeSkill().equals("DEFEND") && agent.mask().abandon()) defenders.add(agent);
        }
        if(!supplierActive && defenders.size() > 2){
            AgentView selected = defenders.stream().max(Comparator.comparingInt(AgentView::agentIndex))
                .orElseThrow();
            preferredTypes.put(selected.agentIndex(), TaskType.SUPPLY_TURRET);
            replace(actions, Action.abandon(selected.agentIndex(), "readiness_rebalance"));
        }
        return List.copyOf(actions);
    }

    public Action action(AgentView agent, TeamView team){
        long previousTick = lastTicks.getOrDefault(agent.agentIndex(), team.tick());
        if(team.tick() < previousTick){
            replanTicks.remove(agent.agentIndex());
            preferredTypes.remove(agent.agentIndex());
            pendingPreferred.remove(agent.agentIndex());
            returnToDefense.remove(agent.agentIndex());
        }
        lastTicks.put(agent.agentIndex(), team.tick());

        TaskType preferred = preferredTypes.get(agent.agentIndex());
        if(agent.activeSkill().equals("DEFEND")) returnToDefense.remove(agent.agentIndex());

        if(agent.mask().abandon() && team.enemyCount() > 0
            && !agent.activeSkill().isEmpty()
            && !agent.activeSkill().equals("DEFEND")
            && !agent.activeSkill().equals("SUPPLY")){
            return Action.abandon(agent.agentIndex(), "wave_preempt");
        }

        if(agent.mask().abandon() && agent.skillStatus() == SkillStatus.BLOCKED
            && replanableBlocks.contains(agent.skillReason())){
            ArrayDeque<Long> history = replanTicks.computeIfAbsent(
                agent.agentIndex(), ignored -> new ArrayDeque<>());
            long cutoff = team.tick() - REPLAN_WINDOW_TICKS;
            while(!history.isEmpty() && history.peekFirst() <= cutoff) history.removeFirst();
            if(history.size() < MAX_REPLANS_PER_WINDOW){
                history.addLast(team.tick());
                String reason = agent.skillReason() == SkillReason.RESOURCES_SHORT
                    || agent.skillReason() == SkillReason.CORE_SHORT
                    ? "resources_short_replan"
                    : "blocked_replan:" + agent.skillReason().name().toLowerCase(Locale.ROOT);
                return Action.abandon(agent.agentIndex(), reason);
            }
        }

        if(agent.mask().continueCurrentTask()){
            return Action.simple(agent.agentIndex(), ActionType.CONTINUE_CURRENT_TASK);
        }

        if(returnToDefense.contains(agent.agentIndex())) preferred = TaskType.DEFEND_REGION;
        int selected = select(agent, preferred);
        if(selected < 0 && preferred != null){
            preferredTypes.remove(agent.agentIndex());
            selected = select(agent, null);
        }
        if(selected < 0) return Action.simple(agent.agentIndex(), ActionType.WAIT);
        if(preferred != null) pendingPreferred.put(agent.agentIndex(), preferred);
        return Action.select(agent.agentIndex(), selected);
    }

    private static int select(AgentView agent, TaskType preferred){
        int selected = -1;
        double best = Double.NEGATIVE_INFINITY;
        List<TaskCandidate> candidates = agent.candidates().candidates();
        for(int i = 0; i < candidates.size(); i++){
            TaskCandidate candidate = candidates.get(i);
            if(!agent.mask().candidateAllowed(i) || !candidate.valid()) continue;
            if(preferred != null && candidate.task().type() != preferred) continue;
            if(selected < 0 || Double.compare(candidate.utility(), best) > 0){
                selected = i;
                best = candidate.utility();
            }
        }
        return selected;
    }

    private static void replace(List<Action> actions, Action replacement){
        for(int i = 0; i < actions.size(); i++){
            if(actions.get(i).agentIndex() == replacement.agentIndex()){
                actions.set(i, replacement);
                return;
            }
        }
    }
}
