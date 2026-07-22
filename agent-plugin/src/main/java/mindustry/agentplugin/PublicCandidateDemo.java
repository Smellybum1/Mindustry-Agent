package mindustry.agentplugin;

import agentcore.candidates.*;
import agentcore.board.*;
import agentcore.coordination.*;
import agentcore.human.*;
import agentcore.human.HumanActionPolicy.*;
import agentcore.human.HumanControl.*;
import agentcore.human.HumanPresence.*;
import agentcore.policy.*;
import agentcore.policy.GreedyUtilityPolicy.*;
import agentcore.skill.*;
import agentcore.task.*;
import arc.util.serialization.*;
import mindustry.gen.*;
import mindustry.entities.units.*;
import mindustry.rl.*;

import java.nio.charset.*;
import java.security.*;
import java.util.*;

import static mindustry.Vars.*;

/** Simulation-thread public-candidate policy runtime for the real-time demo. */
final class PublicCandidateDemo{
    private static final long decisionInterval = 30L;

    enum SignalType{ RESERVE_MINING, WAVE_START, WAVE_CLEAR, EXPANSION_COMPLETE, MAINTENANCE_COMPLETE }
    record Signal(SignalType type, long tick, int wave, int enemies, int coreHealth,
                  int blocks, int turrets){}
    record GoalAvailability(long tick, String goalId, String reason){}

    private final DemoAgentRegistry registry;
    private final AdaptiveWorldFacts facts;
    private final EngineCandidates candidates;
    private final CoordinationAdapter coordination;
    private final HumanControl.State humanControl;
    private final GreedyUtilityPolicy policy = new GreedyUtilityPolicy();
    private final HumanActionPolicy humanPolicy = new HumanActionPolicy();
    private final ArrayList<String> acceptedSelections = new ArrayList<>();
    private final ArrayDeque<Signal> signals = new ArrayDeque<>();
    private final ArrayDeque<Jval> traces = new ArrayDeque<>();
    private final ArrayDeque<GoalAvailability> goalAvailability = new ArrayDeque<>();
    private final HashSet<String> unavailableGoals = new HashSet<>();
    private final ExpertCoordinationPlan expertPlan;
    private final boolean traceEnabled;
    private CandidateSet[] boundaryCandidates = new CandidateSet[0];
    private long nextDecisionTick;
    private long decisionRevision;
    private int previousEnemies;
    private int previousCoreHealth;
    private int waveClears;
    private int reportedExpansions;
    private boolean reserveReported;
    private boolean started;

    PublicCandidateDemo(
        Scenario scenario,
        DemoAgentRegistry registry,
        HumanControl.State humanControl,
        boolean traceEnabled
    ){
        this.registry = registry;
        this.humanControl = humanControl;
        this.traceEnabled = traceEnabled;
        expertPlan = ExpertCoordinationPlans.fromScenario(scenario);
        facts = new AdaptiveWorldFacts(scenario, registry);
        candidates = new EngineCandidates(scenario, registry, facts);
        coordination = new CoordinationAdapter(scenario, registry, facts);
        candidates.setCoordination(coordination);
    }

    void start(){
        if(started) return;
        started = true;
        coordination.reset(1L, registry.size());
        facts.reset();
        policy.reset();
        acceptedSelections.clear();
        signals.clear();
        traces.clear();
        goalAvailability.clear();
        unavailableGoals.clear();
        nextDecisionTick = (long)state.tick;
        decisionRevision = coordination.decisionRevision();
        previousEnemies = enemyCount();
        previousCoreHealth = coreHealth();
        waveClears = 0;
        reportedExpansions = 0;
        reserveReported = false;
        decide((long)state.tick);
    }

    void update(){
        long tick = (long)state.tick;
        facts.recordTick(0);
        coordination.recordMetricsTick();
        coordination.tick(tick);

        int enemies = enemyCount();
        int health = coreHealth();
        if(previousEnemies == 0 && enemies > 0){
            signals.add(new Signal(SignalType.WAVE_START, tick, waveClears + 1,
                enemies, health, 0, candidates.snapshot().turrets().size()));
        }else if(previousEnemies > 0 && enemies == 0){
            waveClears++;
            signals.add(new Signal(SignalType.WAVE_CLEAR, tick, waveClears,
                0, health, 0, candidates.snapshot().turrets().size()));
        }
        boolean worldBoundary = (previousEnemies == 0) != (enemies == 0)
            || health < previousCoreHealth;
        if(tick >= nextDecisionTick || coordination.decisionRevision() != decisionRevision
            || worldBoundary){
            decide(tick);
        }
        previousEnemies = enemies;
        previousCoreHealth = health;
        recordReadinessSignals(tick);
    }

    void stop(String reason){
        Jval actions = Jval.newArray();
        for(int i = 0; i < registry.size(); i++){
            Jval action = Jval.newObject();
            action.put("agent_id", i);
            Jval task = Jval.newObject();
            task.put("type", "ABANDON");
            task.put("reason", reason);
            action.add("task_action", task);
            actions.add(action);
        }
        coordination.applyActions(actions, boundaryCandidates);
    }

    Jval drainEvents(){ return coordination.drainEvents(); }
    List<Signal> drainSignals(){
        ArrayList<Signal> out = new ArrayList<>(signals);
        signals.clear();
        return List.copyOf(out);
    }
    List<Jval> drainTraces(){
        ArrayList<Jval> out = new ArrayList<>(traces);
        traces.clear();
        return List.copyOf(out);
    }
    List<GoalAvailability> drainGoalAvailability(){
        ArrayList<GoalAvailability> out = new ArrayList<>(goalAvailability);
        goalAvailability.clear();
        return List.copyOf(out);
    }
    Jval metrics(){ return coordination.metrics(); }
    boolean started(){ return started; }
    int taskCount(){ return coordination.board().tasks().size(); }
    boolean preparationComplete(){
        CandidateWorldSnapshot world = candidates.snapshot();
        return facts.economy().operational() && world.buildLineComplete()
            && world.schematicComplete() && world.plannedSchematics().isEmpty()
            && facts.defense().readiness() >= 1.0;
    }
    String phase(){
        if(enemyCount() > 0) return "defend";
        return preparationComplete() ? "reserve-mining" : "opening";
    }
    int selectionCount(){ return acceptedSelections.size(); }
    void applyHumanPresence(Change change, long tick){
        for(String presenceId : change.removed()) coordination.releaseHumanPresence(presenceId);
        for(Plan presence : change.added()) coordination.reserveHumanPresence(presence, tick);
        if(!change.empty()) nextDecisionTick = Math.min(nextDecisionTick, tick);
    }
    int humanReservationYields(){ return coordination.humanReservationYields(); }
    int humanReservedAmount(String item){ return coordination.humanReservedAmount(item); }
    boolean hasHumanPresence(String presenceId){ return coordination.hasHumanPresence(presenceId); }
    boolean agentBuildPlanOverlaps(agentcore.reservation.Rect area){
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            for(BuildPlan plan : agent.unit().plans()){
                if(plan.breaking || plan.block == null) continue;
                agentcore.reservation.Rect footprint = new agentcore.reservation.Rect(
                    plan.x + plan.block.sizeOffset, plan.y + plan.block.sizeOffset,
                    plan.block.size, plan.block.size);
                if(footprint.overlaps(area)) return true;
            }
        }
        return false;
    }
    boolean taskCompleted(String taskId){
        TaskState task = coordination.board().task(taskId);
        return task != null && task.status() == TaskStatus.COMPLETED;
    }
    int taskOwner(String taskId){
        TaskState task = coordination.board().task(taskId);
        return task == null || task.owner() == null ? -1 : task.owner().index();
    }
    boolean lowIsolation(String goalId, int assignedAgent){
        for(int i = 0; i < registry.size(); i++){
            String current = coordination.currentTaskId(i);
            if(i == assignedAgent){
                if(!current.equals(goalId)) return false;
            }else if(!current.isEmpty() && !current.equals("runtime:wait")){
                return false;
            }
        }
        return true;
    }

    void controlApplied(Event event){
        if(!event.accepted()) return;
        if(started){
            switch(event.command().type()){
                case CANCEL -> abandonGoal(event.goalId(), "human_goal_cancelled");
                case ASSIGN -> enforceExplicitAssignment(event.agentIndex(), event.goalId());
                case RELEASE -> {
                    if(humanControl.snapshot().autonomy() == AutonomyLevel.LOW){
                        releaseAgentIfTask(event.agentIndex(), event.goalId());
                    }
                }
                case AUTONOMY -> {
                    if(event.command().autonomy() == AutonomyLevel.LOW) enforceLowAutonomy();
                }
                case GOAL, QUIET -> { }
            }
        }
        nextDecisionTick = Math.min(nextDecisionTick, event.tick());
    }

    String selectionDigest(){
        try{
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for(String row : acceptedSelections){
                digest.update(row.getBytes(StandardCharsets.UTF_8));
                digest.update((byte)'\n');
            }
            return HexFormat.of().formatHex(digest.digest());
        }catch(NoSuchAlgorithmException e){
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    private void decide(long tick){
        for(int i = 0; i < registry.size(); i++){
            if(!registry.available(i)) registry.ensureAgent(i);
        }

        CandidateWorldSnapshot world = candidates.snapshot();
        Snapshot controls = humanControl.snapshot();
        boundaryCandidates = new CandidateSet[registry.size()];
        ArrayList<AgentView> views = new ArrayList<>();
        Jval[] masks = new Jval[registry.size()];
        Jval[] rawMasks = new Jval[registry.size()];
        HashSet<String> matchedGoals = new HashSet<>();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            HumanGoalResolver.Resolution resolution = candidates.generate(agent, world, controls);
            CandidateSet set = resolution.candidates();
            for(HumanGoalResolver.GoalResult result : resolution.goals()){
                if(result.matched()) matchedGoals.add(result.goalId());
            }
            boundaryCandidates[agent.index()] = set;
            rawMasks[agent.index()] = coordination.actionMask(agent.index(), set);
        }
        recordGoalAvailability(tick, controls, matchedGoals);
        ArrayList<AgentBoundary> humanBoundaries = new ArrayList<>();
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            int index = agent.index();
            humanBoundaries.add(new AgentBoundary(index, coordination.currentTaskId(index),
                boundaryCandidates[index], baseMask(rawMasks[index], boundaryCandidates[index])));
        }
        Map<Integer, String> bindings = humanPolicy.bindings(controls, humanBoundaries);
        for(DemoAgentRegistry.Agent agent : registry.agents()){
            int index = agent.index();
            CandidateSet set = boundaryCandidates[index];
            AgentBoundary boundary = humanBoundaries.get(index);
            BaseMask constrained = humanPolicy.constrain(boundary, controls, bindings);
            Jval rawMask = applyConstraints(rawMasks[index], constrained,
                bindings.containsKey(index) || controls.autonomy() == AutonomyLevel.LOW);
            masks[agent.index()] = rawMask;
            SkillResult result = agent.controller().lastResult();
            views.add(new AgentView(agent.index(), agent.controller().activeType(),
                result.status(), result.reason(), set, mask(rawMask)));
        }

        List<Action> selected = policy.actions(views,
            new TeamView(tick, world.enemyCount(), world.defenseReadiness().ammoCoverage()));
        Jval payload = Jval.newArray();
        for(Action action : selected) payload.add(action(action));
        Jval results = coordination.applyActions(payload, boundaryCandidates);

        ArrayList<ActionResult> accepted = new ArrayList<>();
        for(int i = 0; i < selected.size(); i++){
            Action action = selected.get(i);
            Jval result = results.asArray().get(i);
            boolean ok = result.getBool("accepted", false);
            accepted.add(new ActionResult(action.agentIndex(), ok));
            if(ok && action.type() == ActionType.SELECT_CANDIDATE_TASK){
                TaskCandidate candidate = boundaryCandidates[action.agentIndex()]
                    .candidates().get(action.candidateIndex());
                acceptedSelections.add(action.agentIndex() + "\u001f"
                    + normalizeTaskId(candidate.task().taskId()) + "\u001f"
                    + candidate.task().type().name());
            }
        }
        policy.observeActionResults(accepted);
        if(traceEnabled){
            traces.add(trace(tick, world, views, masks, payload, results));
        }
        decisionRevision = coordination.decisionRevision();
        nextDecisionTick = tick + decisionInterval;
    }

    private static Jval applyConstraints(Jval raw, BaseMask constrained, boolean restricted){
        Jval out = Jval.read(raw.toString(Jval.Jformat.plain));
        Jval select = Jval.newArray();
        for(boolean allowed : constrained.candidateTask()) select.add(allowed);
        out.add("candidate_task", select);
        out.put("continue_current_task", constrained.continueCurrentTask());
        boolean anyCandidate = constrained.candidateTask().stream().anyMatch(Boolean::booleanValue);
        out.put("wait", raw.getBool("wait", false) || restricted && !anyCandidate);
        if(restricted){
            out.put("request_help", false);
            out.add("offer_help", falseArray(raw.get("offer_help")));
            out.add("accept_help", falseArray(raw.get("accept_help")));
            out.add("decline_help", falseArray(raw.get("decline_help")));
        }
        return out;
    }

    private static BaseMask baseMask(Jval raw, CandidateSet candidates){
        ArrayList<Boolean> select = new ArrayList<>();
        for(int i = 0; i < candidates.candidates().size(); i++){
            select.add(maskValue(raw, i));
        }
        return new BaseMask(select, raw.getBool("continue_current_task", false),
            raw.getBool("abandon", false));
    }

    private void recordGoalAvailability(long tick, Snapshot controls, Set<String> matched){
        HashSet<String> active = new HashSet<>();
        for(Goal goal : controls.activeGoals()){
            active.add(goal.id());
            if(matched.contains(goal.id()) || coordination.board().task(goal.id()) != null){
                unavailableGoals.remove(goal.id());
            }else if(unavailableGoals.add(goal.id())){
                goalAvailability.add(new GoalAvailability(tick, goal.id(), "no_valid_candidate"));
            }
        }
        unavailableGoals.retainAll(active);
    }

    private void enforceExplicitAssignment(int agentIndex, String goalId){
        for(int i = 0; i < registry.size(); i++){
            String current = coordination.currentTaskId(i);
            if(i == agentIndex){
                if(!current.isEmpty() && !current.equals(goalId)){
                    displace(i, "human_assignment");
                }
            }else if(current.equals(goalId)){
                release(i);
            }
        }
    }

    private void enforceLowAutonomy(){
        Map<Integer, String> assigned = new TreeMap<>();
        for(Assignment assignment : humanControl.snapshot().assignments()){
            assigned.put(assignment.agentIndex(), assignment.goalId());
        }
        for(int i = 0; i < registry.size(); i++){
            String current = coordination.currentTaskId(i);
            if(current.isEmpty()) continue;
            if(!current.equals(assigned.get(i))) displace(i, "autonomy_low");
        }
    }

    private void abandonGoal(String goalId, String reason){
        for(int i = 0; i < registry.size(); i++){
            if(coordination.currentTaskId(i).equals(goalId)) abandon(i, reason);
        }
    }

    private void releaseAgentIfTask(int agentIndex, String goalId){
        if(coordination.currentTaskId(agentIndex).equals(goalId)) release(agentIndex);
    }

    private void displace(int agentIndex, String reason){
        if(coordination.currentTaskHumanOrigin(agentIndex)) release(agentIndex);
        else abandon(agentIndex, reason);
    }

    private void release(int agentIndex){
        coordination.releaseCurrent(agentIndex, (long)state.tick);
        policy.resetAgent(agentIndex);
    }

    private void abandon(int agentIndex, String reason){
        Jval payload = Jval.newArray();
        payload.add(action(Action.abandon(agentIndex, reason)));
        coordination.applyActions(payload, boundaryCandidates);
        policy.resetAgent(agentIndex);
    }

    private static boolean maskValue(Jval mask, int index){
        if(mask == null) return false;
        Jval values = mask.get("candidate_task");
        return values != null && values.isArray() && index >= 0 && index < values.asArray().size
            && values.asArray().get(index).asBool();
    }

    private static Jval falseArray(Jval source){
        Jval result = Jval.newArray();
        if(source != null && source.isArray()){
            for(int i = 0; i < source.asArray().size; i++) result.add(false);
        }
        return result;
    }

    private Jval trace(long tick, CandidateWorldSnapshot world, List<AgentView> views,
                       Jval[] masks, Jval actions, Jval results){
        Jval record = Jval.newObject();
        record.put("tick", tick);
        Jval team = Jval.newObject();
        team.put("tick", tick);
        team.put("enemy_count", world.enemyCount());
        team.put("defense_ammo_coverage", world.defenseReadiness().ammoCoverage());
        record.add("team", team);

        Jval observations = Jval.newArray();
        Jval actionMasks = Jval.newArray();
        for(AgentView view : views){
            Jval observation = Jval.newObject();
            observation.put("agent_id", view.agentIndex());
            Jval skill = Jval.newObject();
            skill.put("type", view.activeSkill());
            skill.put("status", view.skillStatus().name());
            skill.put("reason", view.skillReason().name());
            observation.add("skill", skill);
            observation.add("team", Jval.read(team.toString(Jval.Jformat.plain)));
            observation.add("task_candidates", candidates.observation(
                registry.get(view.agentIndex()), world, view.candidates()));
            observations.add(observation);
            actionMasks.add(Jval.read(masks[view.agentIndex()].toString(Jval.Jformat.plain)));
        }
        record.add("observations", observations);
        record.add("action_masks", actionMasks);
        record.add("actions", Jval.read(actions.toString(Jval.Jformat.plain)));
        record.add("action_results", Jval.read(results.toString(Jval.Jformat.plain)));
        return record;
    }

    private void recordReadinessSignals(long tick){
        if(!reserveReported && preparationComplete()){
            reserveReported = true;
            signals.add(new Signal(SignalType.RESERVE_MINING, tick, waveClears, 0,
                coreHealth(), 0, candidates.snapshot().turrets().size()));
        }
        while(reportedExpansions < Math.min(waveClears, expertPlan.expansions().size())){
            ExpertCoordinationPlan.Schematic expansion = expertPlan.expansions().get(reportedExpansions);
            if(!schematicComplete(expansion)) break;
            reportedExpansions++;
            int turrets = candidates.snapshot().turrets().size();
            signals.add(new Signal(SignalType.EXPANSION_COMPLETE, tick, reportedExpansions,
                0, coreHealth(), expansion.blocks().size(), turrets));
            signals.add(new Signal(SignalType.MAINTENANCE_COMPLETE, tick, reportedExpansions,
                0, coreHealth(), expansion.blocks().size(), turrets));
        }
    }

    private static boolean schematicComplete(ExpertCoordinationPlan.Schematic schematic){
        for(BuildSpec block : schematic.blocks()){
            Building building = world.build(schematic.anchorX() + block.offsetX(),
                schematic.anchorY() + block.offsetY());
            if(building == null || !building.block.name.equals(block.block())
                || building.rotation != block.rotation()) return false;
        }
        return true;
    }

    private static ActionMask mask(Jval raw){
        ArrayList<Boolean> candidateMask = new ArrayList<>();
        Jval values = raw.get("candidate_task");
        if(values != null && values.isArray()){
            for(Jval value : values.asArray()) candidateMask.add(value.asBool());
        }
        return new ActionMask(candidateMask,
            raw.getBool("continue_current_task", false), raw.getBool("abandon", false));
    }

    private static Jval action(Action selected){
        Jval out = Jval.newObject();
        out.put("agent_id", selected.agentIndex());
        Jval task = Jval.newObject();
        task.put("type", selected.type().name());
        if(selected.type() == ActionType.SELECT_CANDIDATE_TASK){
            task.put("candidate_index", selected.candidateIndex());
        }else if(selected.type() == ActionType.ABANDON){
            task.put("reason", selected.reason());
        }
        out.add("task_action", task);
        return out;
    }

    private static String normalizeTaskId(String taskId){
        return taskId.replaceFirst(":at-[0-9]+$", ":at-*");
    }

    private static int enemyCount(){
        int count = 0;
        for(Unit unit : Groups.unit) if(unit.team == state.rules.waveTeam && !unit.dead()) count++;
        return count;
    }

    private static int coreHealth(){
        Building core = state.rules.defaultTeam.core();
        return core == null ? 0 : Math.round(core.health);
    }
}
