package mindustry.rl;

import agentcore.*;
import agentcore.announce.*;
import agentcore.board.*;
import agentcore.candidates.*;
import agentcore.coordination.*;
import agentcore.event.*;
import agentcore.human.HumanPresence.*;
import agentcore.reservation.*;
import agentcore.skill.*;
import agentcore.task.*;
import arc.util.serialization.*;
import mindustry.content.*;
import mindustry.gen.*;

import java.io.*;
import java.nio.charset.*;
import java.util.*;

import static mindustry.Vars.*;

/** Sim-thread M5.2 adapter joining task actions, the board, and M3/M4 skills. */
public final class CoordinationAdapter{
    public static final int MAX_BOARD_TASKS = 32;
    private static final long HEARTBEAT_INTERVAL = 300L;

    private final Scenario scenario;
    private final AgentRuntimeRegistry registry;
    private final AdaptiveWorldFacts adaptiveFacts;
    private final ExpertCoordinationPlan expertPlan;
    private final TaskBoard board = new TaskBoard();
    private final AnnouncementRenderer announcementRenderer = new AnnouncementRenderer();
    private boolean sharedExpertEnabled;
    private boolean sharedExpertBlockedVariant;
    private ExpertCoordinationDriver sharedExpert;
    private Assignment[] assignments = new Assignment[0];
    private String[] helperDeliveryTasks = new String[0];
    private int[] helperDeliveryCargo = new int[0];
    private int failureAgent = -1;
    private long failureTick = -1L;
    private boolean failureApplied;
    private long agentTicks;
    private long idleAgentTicks;
    private long[] idleAgentTicksByAgent = new long[0];
    private long unavailableAgentTicks;
    private long[] unavailableAgentTicksByAgent = new long[0];
    private int duplicateWorkIncidents;
    private int tasksCompleted;
    private int tasksAbandoned;
    private int forcedTasksAbandoned;
    private int nonforcedTasksAbandoned;
    private int resourceReplans;
    private int adaptiveReplans;
    private int policySwitches;
    private int structuredMessages;
    private int announcedMessages;
    private int humanReservationYields;
    private TaskSpec[] previousTasks = new TaskSpec[0];
    private long[] previousTaskTicks = new long[0];
    private TaskSpec[] blockedTasks = new TaskSpec[0];
    private long[] blockedTaskTicks = new long[0];
    private final ArrayList<ArrayList<RetryHoldoff>> retryHoldoffs = new ArrayList<>();
    private long decisionRevision;
    private String lastDecisionReason = "";
    private int copperReservationCapacity;

    public CoordinationAdapter(
        Scenario scenario,
        AgentRuntimeRegistry registry,
        AdaptiveWorldFacts adaptiveFacts
    ){
        this.scenario = scenario;
        this.registry = registry;
        this.adaptiveFacts = adaptiveFacts;
        this.expertPlan = ExpertCoordinationPlans.fromScenario(scenario);
    }

    public TaskBoard board(){ return sharedExpert == null ? board : sharedExpert.board(); }

    /** Opt-in scripted policy used by the M7.2 fixed-step/demo parity acceptance path. */
    public void setSharedExpertEnabled(boolean enabled){
        sharedExpertEnabled = enabled;
    }

    /** Validation-only legal pre-spend that exercises utility-policy recovery. */
    public void setSharedExpertBlockedVariant(boolean enabled){
        sharedExpertBlockedVariant = enabled;
    }

    public void reset(long episodeId, int agentCount){
        board.reset(episodeId);
        copperReservationCapacity = initialCopperBudget();
        board.reservations().setCapacity("copper", copperReservationCapacity);
        assignments = new Assignment[agentCount];
        helperDeliveryTasks = new String[agentCount];
        helperDeliveryCargo = new int[agentCount];
        failureAgent = -1;
        failureTick = -1L;
        failureApplied = false;
        agentTicks = 0L;
        idleAgentTicks = 0L;
        idleAgentTicksByAgent = new long[agentCount];
        unavailableAgentTicks = 0L;
        unavailableAgentTicksByAgent = new long[agentCount];
        duplicateWorkIncidents = 0;
        tasksCompleted = 0;
        tasksAbandoned = 0;
        forcedTasksAbandoned = 0;
        nonforcedTasksAbandoned = 0;
        resourceReplans = 0;
        adaptiveReplans = 0;
        policySwitches = 0;
        structuredMessages = 0;
        announcedMessages = 0;
        humanReservationYields = 0;
        previousTasks = new TaskSpec[agentCount];
        previousTaskTicks = new long[agentCount];
        blockedTasks = new TaskSpec[agentCount];
        blockedTaskTicks = new long[agentCount];
        retryHoldoffs.clear();
        for(int i = 0; i < agentCount; i++) retryHoldoffs.add(new ArrayList<>());
        Arrays.fill(previousTaskTicks, Long.MIN_VALUE);
        Arrays.fill(blockedTaskTicks, Long.MIN_VALUE);
        decisionRevision = 0L;
        lastDecisionReason = "";
        if(sharedExpertEnabled){
            sharedExpert = new ExpertCoordinationDriver(
                ExpertCoordinationPlans.fromScenario(scenario), new SharedExpertPort(),
                sharedExpertBlockedVariant);
            sharedExpert.reset(episodeId);
            sharedExpert.startOpening((long)state.tick);
        }else{
            sharedExpert = null;
        }
    }

    /** Configure the deterministic M5.5 validation hook after an episode reset. */
    public void configureFailureInjection(int agentIndex, long tick){
        if(agentIndex < 0 || agentIndex >= assignments.length || tick < 0) return;
        failureAgent = agentIndex;
        failureTick = tick;
    }

    /** Apply one atomic bundle. SELECT claims finalize only after every bid is known. */
    public Jval applyActions(Jval actionsValue, CandidateSet[] candidates){
        Jval out = Jval.newArray();
        if(actionsValue == null || !actionsValue.isArray()) return out;

        if(sharedExpert != null){
            for(Jval action : actionsValue.asArray()){
                out.add(result(action.getInt("agent_id", -1), false,
                    "shared_policy_owned", ""));
            }
            return out;
        }

        var actions = actionsValue.asArray();
        Jval[] results = new Jval[actions.size];
        ArrayList<PendingSelection> pending = new ArrayList<>();
        HashSet<Integer> seenAgents = new HashSet<>();
        long tick = (long)state.tick;

        for(int i = 0; i < actions.size; i++){
            Jval action = actions.get(i);
            int agentIndex = action.getInt("agent_id", -1);
            AgentRuntimeRegistry.Agent agent = registry.get(agentIndex);
            if(agent == null){
                results[i] = result(agentIndex, false, "unknown_agent", "");
                continue;
            }
            if(!agentAvailable(agent)){
                Jval unavailableTask = action.get("task_action");
                boolean wait = action.get("command") == null && unavailableTask != null
                    && unavailableTask.isObject()
                    && unavailableTask.getString("type", "").equalsIgnoreCase("WAIT");
                results[i] = result(agentIndex, wait,
                    wait ? "accepted" : "agent_unavailable", wait ? "WAIT" : "");
                continue;
            }
            if(!seenAgents.add(agentIndex)){
                results[i] = result(agentIndex, false, "duplicate_agent_action", "");
                continue;
            }

            Jval taskAction = action.get("task_action");
            Jval command = action.get("command");
            if(taskAction != null && command != null){
                results[i] = result(agentIndex, false, "ambiguous_action", "");
            }else if(taskAction == null){
                if(current(agentIndex) != null){
                    results[i] = result(agentIndex, false, "task_active", "");
                }else{
                    captureHelperDelivery(agent, command);
                    results[i] = ActionDecoder.apply(registry, scenario, action);
                }
            }else if(!taskAction.isObject()){
                results[i] = result(agentIndex, false, "malformed_task_action", "");
            }else{
                String type = taskAction.getString("type", "").toUpperCase(Locale.ROOT);
                if(type.equals("SELECT_CANDIDATE_TASK")){
                    int candidateIndex = taskAction.getInt("candidate_index", -1);
                    prepareSelection(i, agent, candidateIndex, type,
                        candidatesFor(candidates, agentIndex), pending, results, tick);
                }else if(type.equals("WAIT")){
                    results[i] = current(agentIndex) == null
                        ? result(agentIndex, true, "accepted", type)
                        : result(agentIndex, false, "task_active", type);
                }else{
                    results[i] = applyImmediate(agent, taskAction, type, tick);
                }
            }
        }

        //The board resolves same-tick contests by a total order while tasks remain CLAIMED.
        //Only final owners receive skills and transition to RUNNING.
        pending.sort(Comparator
            .comparingDouble((PendingSelection selection) -> selection.candidate.utility()).reversed()
            .thenComparingInt(selection -> selection.agent.index())
            .thenComparing(selection -> selection.candidate.task().taskId()));
        for(PendingSelection selection : pending){
            TaskState state = board.task(selection.candidate.task().taskId());
            if(state == null || state.owner() == null
                || state.owner().index() != selection.agent.index()){
                results[selection.actionIndex] = result(selection.agent.index(), false,
                    "claim_lost", selection.actionType, selection.candidate.task().taskId());
                duplicateWorkIncidents++;
                if(selection.agent.index() == 1) markDecision("claim_lost");
                continue;
            }
            Skill skill = skillFor(selection.agent, selection.candidate.task());
            if(skill == null){
                board.release(state.taskId(), AgentId.of(selection.agent.index()), tick);
                results[selection.actionIndex] = result(selection.agent.index(), false,
                    "unsupported_or_missing_target", selection.actionType);
                continue;
            }
            String reservationFailure = acquireReservations(
                selection.candidate.task(), AgentId.of(selection.agent.index()), tick);
            if(reservationFailure != null){
                board.release(state.taskId(), AgentId.of(selection.agent.index()), tick);
                results[selection.actionIndex] = result(selection.agent.index(), false,
                    reservationFailure, selection.actionType, state.taskId());
                duplicateWorkIncidents++;
                continue;
            }
            OpResult started = board.start(state.taskId(), AgentId.of(selection.agent.index()), tick);
            if(!started.ok()){
                OpResult released = board.release(state.taskId(),
                    AgentId.of(selection.agent.index()), tick);
                if(!released.ok()) board.reservations().releaseAll(state.taskId());
                results[selection.actionIndex] = result(selection.agent.index(), false,
                    started.reason(), selection.actionType);
                continue;
            }
            selection.agent.controller().setSkill(skill);
            int startCoreCopper = StateHasher.coreItem(Items.copper);
            assignments[selection.agent.index()] = new Assignment(
                state.taskId(), selection.candidate.task(),
                stageFor(selection.candidate.task()), startCoreCopper,
                harvestTarget(selection.candidate.task(), startCoreCopper), tick);
            results[selection.actionIndex] = result(selection.agent.index(), true,
                "accepted", selection.actionType, state.taskId());
        }

        for(Jval result : results) out.add(result == null ? result(-1, false, "internal_error", "") : result);
        return out;
    }

    /** Advance lifecycle/leases after each engine tick. */
    public void tick(long tick){
        expireRetryHoldoffs(tick);
        if(sharedExpert != null){
            int enemies = 0;
            for(Unit unit : Groups.unit){
                if(unit.team == scenario.waveTeam && !unit.dead()) enemies++;
            }
            Building core = scenario.coreTeam.core();
            sharedExpert.update(tick, enemies, core == null ? 0 : Math.round(core.health));
            return;
        }
        // Preserve the episode's highest demonstrated copper budget. Spending
        // after a reservation must not retroactively invalidate that soft claim,
        // while renewable inflow and deterministic scenario grants can expand it.
        // Existing full estimates are added so incremental build spending is not
        // counted twice.
        int reservedCopper = board.reservations().reservedAmount("copper", false);
        copperReservationCapacity = Math.max(copperReservationCapacity,
            StateHasher.coreItem(Items.copper) + reservedCopper);
        board.reservations().setCapacity("copper", copperReservationCapacity);
        for(int i = 0; i < assignments.length; i++){
            AgentRuntimeRegistry.Agent agent = registry.get(i);
            syncHelperDelivery(i, agent, tick);
            Assignment assignment = assignments[i];
            if(assignment == null) continue;
            if(!agentAvailable(agent)){
                abandonUnavailable(i, assignment, agent, tick);
                continue;
            }
            if(reportsSuppressed(i, tick)){
                applyInjectedFailure(i, agent);
                continue;
            }
            TaskState task = board.task(assignment.taskId);
            if(agent == null || task == null || task.owner() == null
                || task.owner().index() != i){
                clearAssignment(i, agent);
                continue;
            }

            if(assignment.spec.type() == TaskType.DEFEND_REGION){
                int enemies = waveEnemyCount();
                if(enemies > 0) assignment.sawEnemy = true;
                if(assignment.sawEnemy && enemies == 0){
                    OpResult completed = board.complete(assignment.taskId,
                        AgentId.of(agent.index()), tick);
                    if(completed.ok()){
                        tasksCompleted++;
                        rememberTransition(i, assignment.spec, tick, false);
                        markDecision("task_terminal");
                    }
                    clearAssignment(i, agent);
                    continue;
                }
            }

            if(assignment.spec.type() == TaskType.BUILD_LINE
                && adaptiveFacts.economy().operational()){
                OpResult completed = board.complete(assignment.taskId,
                    AgentId.of(agent.index()), tick);
                if(completed.ok()){
                    tasksCompleted++;
                    rememberTransition(i, assignment.spec, tick, false);
                    markDecision("economy_operational");
                }
                clearAssignment(i, agent);
                continue;
            }

            SkillResult skill = agent.controller().lastResult();
            switch(skill.status()){
                case RUNNING -> reportRunning(assignment, agent, skill, tick);
                case SUCCEEDED -> skillSucceeded(assignment, agent, tick);
                case BLOCKED -> reportBlocked(assignment, agent, skill, tick);
                case FAILED, CANCELLED -> abandon(assignment, agent,
                    skill.reason().name().toLowerCase(Locale.ROOT), tick);
                default -> {
                    if(tick - assignment.lastHeartbeatTick >= HEARTBEAT_INTERVAL){
                        board.heartbeat(assignment.taskId, AgentId.of(i), tick);
                        assignment.lastHeartbeatTick = tick;
                    }
                }
            }
        }

        List<String> expired = board.expireStale(tick);
        if(!expired.isEmpty()){
            for(int i = 0; i < assignments.length; i++){
                if(assignments[i] != null && expired.contains(assignments[i].taskId)){
                    rememberTransition(i, assignments[i].spec, tick, true);
                    clearAssignment(i, registry.get(i));
                }
            }
            markDecision("task_expired");
        }
    }

    /** Record exactly one engine tick of assignment occupancy for episode metrics. */
    public void recordMetricsTick(){
        for(int i = 0; i < assignments.length; i++){
            if(!agentAvailable(registry.get(i))){
                unavailableAgentTicks++;
                unavailableAgentTicksByAgent[i]++;
                continue;
            }
            agentTicks++;
            if(assignments[i] == null){
                idleAgentTicks++;
                idleAgentTicksByAgent[i]++;
            }
        }
    }

    private boolean reportsSuppressed(int agentIndex, long tick){
        return agentIndex == failureAgent && failureTick >= 0 && tick >= failureTick;
    }

    private void applyInjectedFailure(int agentIndex, AgentRuntimeRegistry.Agent agent){
        if(failureApplied || agentIndex != failureAgent || agent == null) return;
        Assignment assignment = current(agentIndex);
        if(assignment != null && (assignment.spec.type() == TaskType.BUILD_SCHEMATIC
            || assignment.spec.type() == TaskType.REPAIR_REGION)){
            agent.controller().cancelBuildPlans();
        }
        agent.controller().clearSkill();
        failureApplied = true;
    }

    public Jval actionMask(int agentIndex, CandidateSet candidates){
        Jval out = Jval.newObject();
        Jval select = Jval.newArray();
        if(sharedExpert != null){
            for(int i = 0; i < candidates.candidates().size(); i++) select.add(false);
            out.add("candidate_task", select);
            out.put("continue_current_task", false);
            out.put("abandon", false);
            out.put("request_help", false);
            out.put("wait", false);
            out.add("offer_help", Jval.newArray());
            out.add("accept_help", Jval.newArray());
            out.add("decline_help", Jval.newArray());
            return out;
        }
        boolean available = agentAvailable(registry.get(agentIndex));
        boolean idle = available && current(agentIndex) == null;
        long tick = (long)state.tick;
        for(TaskCandidate candidate : candidates.candidates()){
            select.add(idle && candidate.valid() && taskAvailable(candidate.task())
                && humanReservationsAllow(candidate.task())
                && !retryNotDue(agentIndex, candidate.task(), tick));
        }
        out.add("candidate_task", select);
        out.put("continue_current_task", available && !idle);
        out.put("abandon", available && !idle);
        out.put("request_help", available && !idle);
        int waitIndex = waitIndex(candidates);
        out.put("wait", !available || idle && waitIndex >= 0
            && candidates.candidates().get(waitIndex).valid());

        Jval offers = Jval.newArray();
        AgentId agent = AgentId.of(agentIndex);
        List<TaskState> tasks = board.tasks();
        for(int i = 0; i < Math.min(MAX_BOARD_TASKS, tasks.size()); i++){
            TaskState task = tasks.get(i);
            boolean allowed = idle && !task.terminal() && task.owner() != null
                && !task.owner().equals(agent)
                && task.pendingOffers().stream().noneMatch(o -> o.helper().equals(agent))
                && task.helpers().stream().noneMatch(h -> h.helper().equals(agent));
            offers.add(allowed);
        }
        out.add("offer_help", offers);

        Jval accept = Jval.newArray();
        Assignment assignment = current(agentIndex);
        if(available && assignment != null){
            TaskState task = board.task(assignment.taskId);
            if(task != null) for(int i = 0; i < task.pendingOffers().size(); i++) accept.add(true);
        }
        out.add("accept_help", accept);
        out.add("decline_help", Jval.read(accept.toString(Jval.Jformat.plain)));
        return out;
    }

    public Jval boardSnapshot(){
        Jval out = Jval.newArray();
        TaskBoard activeBoard = board();
        List<TaskState> tasks = activeBoard.tasks();
        int count = Math.min(MAX_BOARD_TASKS, tasks.size());
        for(int i = 0; i < count; i++){
            TaskState task = tasks.get(i);
            Jval item = Jval.newObject();
            item.put("index", i);
            item.put("task_id", task.taskId());
            item.put("task_type", task.spec().type().name());
            item.put("target", task.spec().target() == null ? "" : task.spec().target().describe());
            item.put("status", task.status().name());
            item.put("owner_agent_id", task.owner() == null ? -1 : task.owner().index());
            item.put("lease_expiry_tick", task.leaseExpiryTick());
            item.put("progress", task.progress());
            item.put("reason", task.reasonCode() == null ? "" : task.reasonCode());
            item.put("pending_offer_count", task.pendingOffers().size());
            item.put("helper_count", task.helpers().size());
            item.put("reservation_count", activeBoard.reservations().countForTask(task.taskId()));
            int tileReservations = 0;
            for(TileReservation reservation : activeBoard.reservations().tileReservations()){
                if(reservation.taskId().equals(task.taskId())) tileReservations++;
            }
            item.put("tile_reservation_count", tileReservations);
            Jval resources = Jval.newObject();
            for(ResourceReservation reservation : activeBoard.reservations().resourceReservations()){
                if(!reservation.taskId().equals(task.taskId())) continue;
                resources.put(reservation.item(), resources.getInt(reservation.item(), 0)
                    + reservation.amount());
            }
            item.add("reserved_resources", resources);
            out.add(item);
        }
        return out;
    }

    /** Cumulative deterministic episode metrics for StepResponse infos. */
    public Jval metrics(){
        Jval out = Jval.newObject();
        out.put("duplicate_work_incidents", duplicateWorkIncidents);
        out.put("tasks_completed", tasksCompleted);
        out.put("tasks_abandoned", tasksAbandoned);
        out.put("forced_tasks_abandoned", forcedTasksAbandoned);
        out.put("nonforced_tasks_abandoned", nonforcedTasksAbandoned);
        out.put("resource_replans", resourceReplans);
        out.put("adaptive_replans", adaptiveReplans);
        out.put("policy_switches", policySwitches);
        out.put("decision_events", decisionRevision);
        out.put("agent_ticks", agentTicks);
        out.put("idle_agent_ticks", idleAgentTicks);
        Jval idleByAgent = Jval.newArray();
        for(long ticks : idleAgentTicksByAgent) idleByAgent.add(ticks);
        out.add("idle_agent_ticks_by_agent", idleByAgent);
        out.put("unavailable_agent_ticks", unavailableAgentTicks);
        Jval unavailableByAgent = Jval.newArray();
        for(long ticks : unavailableAgentTicksByAgent) unavailableByAgent.add(ticks);
        out.add("unavailable_agent_ticks_by_agent", unavailableByAgent);
        out.put("idle_fraction", agentTicks == 0L ? 0.0
            : idleAgentTicks / (double)agentTicks);
        out.put("structured_messages", structuredMessages);
        out.put("announced_messages", announcedMessages);
        long humanTiles = board.reservations().tileReservations().stream()
            .filter(TileReservation::human).count();
        long humanResources = board.reservations().resourceReservations().stream()
            .filter(ResourceReservation::human).count();
        if(humanReservationYields > 0 || humanTiles > 0 || humanResources > 0){
            out.put("human_reservation_yields", humanReservationYields);
            out.put("human_tile_reservations", humanTiles);
            out.put("human_resource_reservations", humanResources);
        }
        if(sharedExpert != null){
            out.put("shared_policy_name", sharedExpert.policyName());
            out.put("shared_decision_count", sharedExpert.selectionCount());
            out.put("shared_decision_digest", sharedExpert.selectionDigest());
            out.put("shared_policy_phase", sharedExpert.phase());
            out.put("shared_first_line_block_tick", sharedExpert.firstLineBlockTick());
            out.put("shared_resources_short_blocks", sharedExpert.resourcesShortBlocks());
            out.put("shared_resources_short_replans", sharedExpert.resourceReplans());
        }
        return out;
    }

    public Jval drainEvents(){
        Jval out = Jval.newArray();
        for(CoordinationEvent event : board().events().drain()){
            structuredMessages++;
            if(event.announce()) announcedMessages++;
            out.add(event(event));
        }
        return out;
    }

    private void prepareSelection(
        int actionIndex,
        AgentRuntimeRegistry.Agent agent,
        int candidateIndex,
        String actionType,
        CandidateSet candidates,
        List<PendingSelection> pending,
        Jval[] results,
        long tick
    ){
        if(current(agent.index()) != null){
            results[actionIndex] = result(agent.index(), false, "task_active", actionType);
            return;
        }
        if(candidateIndex < 0 || candidateIndex >= candidates.candidates().size()){
            results[actionIndex] = result(agent.index(), false, "candidate_index_out_of_range", actionType);
            return;
        }
        TaskCandidate candidate = candidates.candidates().get(candidateIndex);
        if(!candidate.valid()){
            results[actionIndex] = result(agent.index(), false, candidate.invalidReason(), actionType);
            return;
        }
        if(!dependenciesComplete(candidate.task())){
            results[actionIndex] = result(agent.index(), false, "dependency_incomplete", actionType);
            return;
        }
        if(retryNotDue(agent.index(), candidate.task(), tick)){
            results[actionIndex] = result(agent.index(), false, "retry_not_due", actionType);
            return;
        }
        TaskState existing = board.task(candidate.task().taskId());
        boolean sameTickContest = existing != null && existing.status() == TaskStatus.CLAIMED
            && existing.leaseExpiryTick() == tick + board.leaseDurationTicks();
        if(existing != null && existing.status() != TaskStatus.OPEN && !sameTickContest){
            results[actionIndex] = result(agent.index(), false, "task_not_open", actionType);
            return;
        }
        if(existing == null) board.propose(candidate.task(), tick);

        AgentId id = AgentId.of(agent.index());
        if(!sameTickContest){
            OpResult intent = board.announceIntent(candidate.task().taskId(), id,
                candidate.utility(), tick);
            if(!intent.ok()){
                results[actionIndex] = result(agent.index(), false, intent.reason(), actionType);
                return;
            }
        }
        ClaimOutcome claim = board.claim(candidate.task().taskId(), id, candidate.utility(), tick);
        if(!claim.granted()){
            results[actionIndex] = result(agent.index(), false,
                claim.result().name().toLowerCase(Locale.ROOT), actionType);
            return;
        }
        pending.add(new PendingSelection(actionIndex, agent, candidate, actionType));
    }

    private Jval applyImmediate(AgentRuntimeRegistry.Agent agent, Jval action, String type, long tick){
        Assignment assignment = current(agent.index());
        AgentId id = AgentId.of(agent.index());
        return switch(type){
            case "CONTINUE_CURRENT_TASK" -> {
                if(assignment == null) yield result(agent.index(), false, "no_current_task", type);
                OpResult op = board.heartbeat(assignment.taskId, id, tick);
                if(op.ok() && board.task(assignment.taskId).status() == TaskStatus.BLOCKED
                    && agent.controller().lastResult().status() != SkillStatus.BLOCKED){
                    board.reportProgress(assignment.taskId, id,
                        board.task(assignment.taskId).progress(), tick);
                    assignment.blockedReason = "";
                }
                yield result(agent.index(), op.ok(), op.reason(), type, assignment.taskId);
            }
            case "ABANDON" -> {
                if(assignment == null) yield result(agent.index(), false, "no_current_task", type);
                String reason = action.getString("reason", "policy_abandon");
                OpResult op = board.abandon(assignment.taskId, id, reason, tick);
                if(op.ok()){
                    tasksAbandoned++;
                    if(isForcedAbandonReason(reason)) forcedTasksAbandoned++;
                    else nonforcedTasksAbandoned++;
                    if(reason.equals("resources_short_replan")) resourceReplans++;
                    if(reason.equals("resources_short_replan")
                        || reason.startsWith("blocked_replan:")) adaptiveReplans++;
                    if(reason.equals("wave_preempt")
                        || reason.equals("readiness_rebalance")) policySwitches++;
                    rememberTransition(agent.index(), assignment.spec, tick,
                        reason.equals("resources_short_replan")
                            || reason.startsWith("blocked_replan:"));
                    clearAssignment(agent.index(), agent);
                    markDecision("task_terminal");
                }
                yield result(agent.index(), op.ok(), op.reason(), type, assignment.taskId);
            }
            case "REQUEST_HELP" -> {
                if(assignment == null) yield result(agent.index(), false, "no_current_task", type);
                OpResult op = board.requestHelp(assignment.taskId, id,
                    Math.max(1, action.getInt("helpers_requested", 1)), tick);
                yield result(agent.index(), op.ok(), op.reason(), type, assignment.taskId);
            }
            case "OFFER_HELP" -> offerHelp(agent, action, type, tick);
            case "ACCEPT_HELP" -> decideHelp(agent, action, type, true, tick);
            case "DECLINE_HELP" -> decideHelp(agent, action, type, false, tick);
            default -> result(agent.index(), false, "unknown_task_action", type);
        };
    }

    private static boolean isForcedAbandonReason(String reason){
        String normalized = reason == null ? "" : reason.toLowerCase(Locale.ROOT);
        return normalized.contains("wave")
            || normalized.contains("readiness")
            || normalized.contains("death")
            || normalized.contains("lease")
            || normalized.contains("human")
            || normalized.contains("terminal")
            || normalized.contains("cleanup");
    }

    private Jval offerHelp(AgentRuntimeRegistry.Agent agent, Jval action, String type, long tick){
        if(current(agent.index()) != null){
            return result(agent.index(), false, "task_active", type);
        }
        int taskIndex = action.getInt("task_index", -1);
        List<TaskState> tasks = board.tasks();
        if(taskIndex < 0 || taskIndex >= Math.min(MAX_BOARD_TASKS, tasks.size())){
            return result(agent.index(), false, "task_index_out_of_range", type);
        }
        TaskState task = tasks.get(taskIndex);
        OpResult op = board.offerHelp(task.taskId(), AgentId.of(agent.index()),
            action.getString("contribution", "assist"),
            Math.max(0, action.getInt("amount", 0)), tick);
        return result(agent.index(), op.ok(), op.reason(), type, task.taskId());
    }

    private Jval decideHelp(
        AgentRuntimeRegistry.Agent agent,
        Jval action,
        String type,
        boolean accept,
        long tick
    ){
        Assignment assignment = current(agent.index());
        if(assignment == null) return result(agent.index(), false, "no_current_task", type);
        TaskState task = board.task(assignment.taskId);
        int offerIndex = action.getInt("offer_index", -1);
        if(task == null || offerIndex < 0 || offerIndex >= task.pendingOffers().size()){
            return result(agent.index(), false, "offer_index_out_of_range", type);
        }
        AgentId helper = task.pendingOffers().get(offerIndex).helper();
        OpResult op = accept
            ? board.acceptHelp(task.taskId(), AgentId.of(agent.index()), helper, tick)
            : board.declineHelp(task.taskId(), AgentId.of(agent.index()), helper, tick);
        return result(agent.index(), op.ok(), op.reason(), type, task.taskId());
    }

    private void captureHelperDelivery(AgentRuntimeRegistry.Agent agent, Jval command){
        if(command == null || !command.isObject()
            || !command.getString("type", "").equalsIgnoreCase("DELIVER_CORE")) return;
        for(TaskState task : board.tasks()){
            for(HelperContract contract : task.helpers()){
                if(!contract.fulfilled() && contract.helper().index() == agent.index()
                    && contract.contribution().equalsIgnoreCase("deliver copper")
                    && agent.unit().item() == Items.copper){
                    helperDeliveryTasks[agent.index()] = task.taskId();
                    helperDeliveryCargo[agent.index()] = agent.unit().stack().amount;
                    return;
                }
            }
        }
    }

    private String acquireReservations(TaskSpec task, AgentId agent, long tick){
        if(task.type() == TaskType.BUILD_SCHEMATIC || task.type() == TaskType.BUILD_LINE){
            Rect footprint = schematicFootprint(task);
            ReservationOutcome tiles = board.reserveTile(task.taskId(), agent,
                footprint, false, tick);
            if(!tiles.granted()) return reservationReason(tiles);
        }
        if(task.type() == TaskType.BUILD_SCHEMATIC || task.type() == TaskType.BUILD_LINE
            || task.type() == TaskType.SUPPLY_TURRET){
            for(Map.Entry<String, Integer> cost : task.estimatedCost().asMap().entrySet()){
                ReservationOutcome resource = board.reserveResource(task.taskId(), agent,
                    cost.getKey(), cost.getValue(), false, tick);
                if(!resource.granted()){
                    board.reservations().releaseAll(task.taskId());
                    return reservationReason(resource);
                }
            }
        }
        return null;
    }

    private Rect schematicFootprint(TaskSpec task){
        ExecutableSchematic spec = executableSchematic(task);
        if(spec == null) throw new IllegalArgumentException("unknown schematic task " + task.taskId());
        int minX = Integer.MAX_VALUE, minY = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE, maxY = Integer.MIN_VALUE;
        for(BuildSpec build : spec.blocks()){
            mindustry.world.Block block = content.block(build.block());
            int x = spec.anchorX() + build.offsetX() + block.sizeOffset;
            int y = spec.anchorY() + build.offsetY() + block.sizeOffset;
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + block.size);
            maxY = Math.max(maxY, y + block.size);
        }
        return new Rect(minX, minY, maxX - minX, maxY - minY);
    }

    private ExecutableSchematic executableSchematic(TaskSpec task){
        if(!(task.target() instanceof RegionTarget target)) return null;
        String id = target.regionId();
        if(task.type() == TaskType.BUILD_LINE && id.equals(scenario.buildLineId)){
            Scenario.SchematicSpec spec = scenario.schematic(id);
            return spec == null ? null : new ExecutableSchematic(spec.name(),
                scenario.buildLineAnchorX, scenario.buildLineAnchorY, spec.blocks());
        }
        if(task.type() != TaskType.BUILD_SCHEMATIC) return null;
        if(id.equals(scenario.referenceSchematicId)){
            Scenario.SchematicSpec spec = scenario.schematic(id);
            return spec == null ? null : new ExecutableSchematic(spec.name(),
                scenario.referenceAnchorX, scenario.referenceAnchorY, spec.blocks());
        }
        ExpertCoordinationPlan.Schematic planned = plannedSchematic(id);
        return planned == null ? null : new ExecutableSchematic(planned.name(),
            planned.anchorX(), planned.anchorY(), planned.blocks());
    }

    private ExpertCoordinationPlan.Schematic plannedSchematic(String id){
        if(expertPlan.fortification().name().equals(id)) return expertPlan.fortification();
        for(ExpertCoordinationPlan.Schematic expansion : expertPlan.expansions()){
            if(expansion.name().equals(id)) return expansion;
        }
        return null;
    }

    private int waveEnemyCount(){
        int enemies = 0;
        for(Unit unit : Groups.unit){
            if(unit.team == scenario.waveTeam && !unit.dead()) enemies++;
        }
        return enemies;
    }

    private int initialCopperBudget(){
        for(mindustry.type.ItemStack stack : scenario.loadout){
            if(stack.item == Items.copper) return stack.amount;
        }
        return 0;
    }

    private static String reservationReason(ReservationOutcome outcome){
        return switch(outcome.result()){
            case REJECTED_OVERLAP -> "reservation_overlap";
            case REJECTED_HUMAN_PRIORITY -> "reservation_human_priority";
            case REJECTED_CAPACITY -> "reservation_capacity";
            default -> "reservation_rejected";
        };
    }

    private void syncHelperDelivery(int agentIndex, AgentRuntimeRegistry.Agent agent, long tick){
        String taskId = helperDeliveryTasks[agentIndex];
        if(taskId == null || agent == null) return;
        SkillResult result = agent.controller().lastResult();
        if(!(agent.controller().activeSkill() instanceof DeliverToCore)
            || result.status() != SkillStatus.SUCCEEDED) return;

        TaskState task = board.task(taskId);
        if(task != null){
            for(HelperContract contract : task.helpers()){
                if(!contract.fulfilled() && contract.helper().index() == agentIndex){
                    int delivered = helperDeliveryCargo[agentIndex] - agent.unit().stack().amount;
                    if(delivered >= contract.amount()){
                        board.reportHelpFulfilled(taskId, AgentId.of(agentIndex), tick);
                    }
                    break;
                }
            }
        }
        helperDeliveryTasks[agentIndex] = null;
        helperDeliveryCargo[agentIndex] = 0;
    }

    private void reportRunning(
        Assignment assignment,
        AgentRuntimeRegistry.Agent agent,
        SkillResult skill,
        long tick
    ){
        double progress = taskProgress(assignment, skill.progress());
        int bucket = (int)Math.floor(progress * 100.0);
        if(bucket > assignment.lastProgressBucket){
            board.reportProgress(assignment.taskId, AgentId.of(agent.index()), progress, tick);
            assignment.lastProgressBucket = bucket;
            assignment.lastHeartbeatTick = tick;
        }else if(tick - assignment.lastHeartbeatTick >= HEARTBEAT_INTERVAL){
            board.heartbeat(assignment.taskId, AgentId.of(agent.index()), tick);
            assignment.lastHeartbeatTick = tick;
        }
        assignment.blockedReason = "";
    }

    private void reportBlocked(
        Assignment assignment,
        AgentRuntimeRegistry.Agent agent,
        SkillResult skill,
        long tick
    ){
        String reason = skill.reason().name().toLowerCase(Locale.ROOT);
        if(!reason.equals(assignment.blockedReason)){
            board.reportBlocked(assignment.taskId, AgentId.of(agent.index()), reason, tick);
            assignment.blockedReason = reason;
            blockedTasks[agent.index()] = assignment.spec;
            blockedTaskTicks[agent.index()] = tick;
            rememberRetryHoldoff(
                agent.index(), assignment.spec, tick, skill.nextRetryTick(),
                skill.reason() == SkillReason.RESOURCES_SHORT
                    || skill.reason() == SkillReason.CORE_SHORT);
            markDecision("task_blocked");
        }
        if(tick - assignment.lastHeartbeatTick >= HEARTBEAT_INTERVAL){
            board.heartbeat(assignment.taskId, AgentId.of(agent.index()), tick);
            assignment.lastHeartbeatTick = tick;
        }
    }

    private void skillSucceeded(Assignment assignment, AgentRuntimeRegistry.Agent agent, long tick){
        if(assignment.spec.type() == TaskType.HARVEST_RESOURCE){
            if(assignment.stage.equals("mine")){
                assignment.stage = "deliver";
                agent.controller().setSkill(new DeliverToCore());
                board.reportProgress(assignment.taskId, AgentId.of(agent.index()),
                    taskProgress(assignment, 0f), tick);
                return;
            }
            if(assignment.stage.equals("deliver")){
                assignment.stage = "settle";
                agent.controller().setSkill(new Wait(MineResource.DEFAULT_DRAIN_TICKS));
                board.heartbeat(assignment.taskId, AgentId.of(agent.index()), tick);
                assignment.lastHeartbeatTick = tick;
                return;
            }
            if(StateHasher.coreItem(Items.copper) < assignment.targetCoreCopper){
                assignment.stage = "mine";
                agent.controller().setSkill(mineSkill(agent, assignment.targetCoreCopper));
                board.reportProgress(assignment.taskId, AgentId.of(agent.index()),
                    taskProgress(assignment, 0f), tick);
                return;
            }
        }

        if(assignment.spec.type() == TaskType.BUILD_LINE
            && !adaptiveFacts.economy().operational()){
            assignment.stage = "verify_line";
            agent.controller().setSkill(new Wait(60));
            board.reportProgress(assignment.taskId, AgentId.of(agent.index()),
                adaptiveFacts.economy().readiness(), tick);
            assignment.lastHeartbeatTick = tick;
            return;
        }

        if(assignment.spec.type() == TaskType.WAIT){
            OpResult released = board.release(assignment.taskId,
                AgentId.of(agent.index()), tick);
            if(released.ok()) markDecision("task_terminal");
        }else{
            OpResult completed = board.complete(assignment.taskId,
                AgentId.of(agent.index()), tick);
            if(completed.ok()){
                tasksCompleted++;
                rememberTransition(agent.index(), assignment.spec, tick, false);
                markDecision("task_terminal");
            }
        }
        clearAssignment(agent.index(), agent);
    }

    private void abandon(
        Assignment assignment,
        AgentRuntimeRegistry.Agent agent,
        String reason,
        long tick
    ){
        OpResult abandoned = board.abandon(assignment.taskId,
            AgentId.of(agent.index()), reason, tick);
        if(abandoned.ok()){
            tasksAbandoned++;
            rememberTransition(agent.index(), assignment.spec, tick, true);
            markDecision("task_terminal");
        }
        clearAssignment(agent.index(), agent);
    }

    private void abandonUnavailable(
        int agentIndex,
        Assignment assignment,
        AgentRuntimeRegistry.Agent agent,
        long tick
    ){
        OpResult abandoned = board.abandon(assignment.taskId,
            AgentId.of(agentIndex), "agent_death", tick);
        if(abandoned.ok()){
            tasksAbandoned++;
            forcedTasksAbandoned++;
            rememberTransition(agentIndex, assignment.spec, tick, true);
            markDecision("task_terminal");
        }
        clearAssignment(agentIndex, agent);
    }

    private Skill skillFor(AgentRuntimeRegistry.Agent agent, TaskSpec task){
        return switch(task.type()){
            case HARVEST_RESOURCE -> mineSkill(agent,
                harvestTarget(task, StateHasher.coreItem(Items.copper)));
            case BUILD_LINE, BUILD_SCHEMATIC -> executeSchematic(task);
            case SUPPLY_TURRET -> supplySkill(task);
            case REPAIR_REGION -> regionSkill(task, true);
            case DEFEND_REGION -> regionSkill(task, false);
            case WAIT -> new Wait(task.estimatedTicks());
            default -> null;
        };
    }

    private Skill mineSkill(AgentRuntimeRegistry.Agent agent, int targetCoreCopper){
        Scenario.ObjectiveSpec objective = scenario.objective(TaskType.HARVEST_RESOURCE);
        Scenario.OrePatch patch = scenario.orePatch(objective.targetRef());
        if(patch == null) return null;
        int bestX = -1, bestY = -1;
        float bestDistance = -1f;
        for(int x = patch.x; x < patch.x + patch.w; x++){
            for(int y = patch.y; y < patch.y + patch.h; y++){
                float dx = x - scenario.coreX;
                float dy = y - scenario.coreY;
                float distance = dx * dx + dy * dy;
                if(distance > bestDistance){
                    bestDistance = distance;
                    bestX = x;
                    bestY = y;
                }
            }
        }
        int remaining = Math.max(1, targetCoreCopper - StateHasher.coreItem(Items.copper));
        return bestX < 0 ? null : new MineResource(bestX, bestY, Math.min(20, remaining));
    }

    private Skill executeSchematic(TaskSpec task){
        ExecutableSchematic schematic = executableSchematic(task);
        return schematic == null ? null : new ExecuteSchematic(schematic.name(),
            schematic.anchorX(), schematic.anchorY(), schematic.blocks());
    }

    private Skill supplySkill(TaskSpec task){
        if(!(task.target() instanceof EntityTarget target)) return null;
        for(Building building : StateHasher.worldBuildings()){
            if(building.id == target.entityId()){
                int amount = Math.max(1, task.estimatedCost().amount("copper"));
                return new SupplyBuilding("copper", building.tileX(), building.tileY(), amount);
            }
        }
        return null;
    }

    private Skill regionSkill(TaskSpec task, boolean rebuild){
        if(!(task.target() instanceof RegionTarget target)) return null;
        Scenario.RegionSpec region = scenario.region(target.regionId());
        if(region == null) return null;
        if(rebuild){
            return new RebuildRegion(region.x(), region.y(),
                region.x() + region.w() - 1, region.y() + region.h() - 1);
        }
        float x = center(region.x(), region.w());
        float y = center(region.y(), region.h());
        float radius = (float)Math.hypot(region.w() * tilesize, region.h() * tilesize) / 2f;
        return new DefendRegion(x, y, radius, task.estimatedTicks());
    }

    private double taskProgress(Assignment assignment, float skillProgress){
        if(assignment.spec.type() == TaskType.BUILD_LINE
            && assignment.stage.equals("verify_line")){
            return Math.min(0.99, adaptiveFacts.economy().readiness());
        }
        if(assignment.spec.type() != TaskType.HARVEST_RESOURCE) return skillProgress;
        int denominator = Math.max(1, assignment.targetCoreCopper - assignment.startCoreCopper);
        double delivered = Math.max(0, StateHasher.coreItem(Items.copper) - assignment.startCoreCopper);
        double base = Math.min(1.0, delivered / denominator);
        if(assignment.stage.equals("mine")) return Math.min(0.99, base + skillProgress * 0.1);
        return Math.min(0.99, base + skillProgress * 0.05);
    }

    private static int harvestTarget(TaskSpec task, int startCoreCopper){
        if(task.type() != TaskType.HARVEST_RESOURCE
            || !(task.target() instanceof ResourceTarget target)) return startCoreCopper;
        return startCoreCopper + target.amount();
    }

    private boolean taskAvailable(TaskSpec task){
        if(!dependenciesComplete(task)) return false;
        if(task.exclusive()){
            for(TaskState existing : board.tasks()){
                if(existing.terminal() || existing.status() == TaskStatus.OPEN
                    || existing.spec().type() != task.type()) continue;
                if(Objects.equals(existing.spec().target(), task.target())) return false;
            }
        }
        TaskState state = board.task(task.taskId());
        return state == null || state.status() == TaskStatus.OPEN;
    }

    private boolean humanReservationsAllow(TaskSpec task){
        if(task.type() == TaskType.BUILD_SCHEMATIC || task.type() == TaskType.BUILD_LINE){
            boolean hasHumanTiles = board.reservations().tileReservations().stream()
                .anyMatch(TileReservation::human);
            if(hasHumanTiles){
                Rect footprint = schematicFootprint(task);
                for(TileReservation reservation : board.reservations().tileOverlaps(footprint)){
                    if(reservation.human()) return false;
                }
            }
        }
        for(Map.Entry<String, Integer> cost : task.estimatedCost().asMap().entrySet()){
            int human = board.reservations().reservedAmount(cost.getKey(), true);
            if(human > 0){
                mindustry.type.Item item = content.item(cost.getKey());
                int stock = item == null ? 0 : StateHasher.coreItem(item);
                int agent = board.reservations().reservedAmount(cost.getKey(), false);
                if(!board.reservations().canAgentReserve(cost.getKey(), cost.getValue())
                    || stock < human + agent + cost.getValue()) return false;
            }
        }
        return true;
    }

    private boolean dependenciesComplete(TaskSpec task){
        for(String dependency : task.dependencyTaskIds()){
            TaskState state = board.task(dependency);
            if(state == null || state.status() != TaskStatus.COMPLETED) return false;
        }
        return true;
    }

    private Assignment current(int agentIndex){
        return agentIndex >= 0 && agentIndex < assignments.length ? assignments[agentIndex] : null;
    }

    private void clearAssignment(int agentIndex, AgentRuntimeRegistry.Agent agent){
        Assignment assignment = current(agentIndex);
        if(agent != null && assignment != null
            && (assignment.spec.type() == TaskType.BUILD_SCHEMATIC
                || assignment.spec.type() == TaskType.BUILD_LINE
                || assignment.spec.type() == TaskType.REPAIR_REGION)){
            agent.controller().cancelBuildPlans();
        }
        if(agent != null) agent.controller().clearSkill();
        if(agentIndex >= 0 && agentIndex < assignments.length) assignments[agentIndex] = null;
    }

    private static CandidateSet candidatesFor(CandidateSet[] sets, int agentIndex){
        return sets != null && agentIndex >= 0 && agentIndex < sets.length && sets[agentIndex] != null
            ? sets[agentIndex] : new CandidateSet(List.of());
    }

    private static int waitIndex(CandidateSet candidates){
        for(int i = 0; i < candidates.candidates().size(); i++){
            if(candidates.candidates().get(i).task().type() == TaskType.WAIT) return i;
        }
        return -1;
    }

    private static boolean agentAvailable(AgentRuntimeRegistry.Agent agent){
        return agent != null && agent.unit().isValid() && !agent.unit().dead();
    }

    private static String stageFor(TaskSpec task){
        return task.type() == TaskType.HARVEST_RESOURCE ? "mine" : "single";
    }

    public long decisionRevision(){ return decisionRevision; }
    public String currentTaskId(int agentIndex){
        Assignment assignment = current(agentIndex);
        return assignment == null ? "" : assignment.taskId;
    }

    public boolean currentTaskHumanOrigin(int agentIndex){
        Assignment assignment = current(agentIndex);
        return assignment != null && assignment.spec.origin() == TaskOrigin.HUMAN;
    }

    /** Release the current task back to OPEN without terminally consuming its stable id. */
    public boolean releaseCurrent(int agentIndex, long tick){
        Assignment assignment = current(agentIndex);
        AgentRuntimeRegistry.Agent agent = registry.get(agentIndex);
        if(assignment == null || agent == null) return false;
        OpResult released = board.release(assignment.taskId, AgentId.of(agentIndex), tick);
        if(!released.ok()) return false;
        rememberTransition(agentIndex, assignment.spec, tick, false);
        clearAssignment(agentIndex, agent);
        markDecision("task_released");
        return true;
    }

    /** Apply one sim-thread human plan/recent-construction reservation bundle. */
    public int reserveHumanPresence(Plan presence, long tick){
        Objects.requireNonNull(presence, "presence");
        AgentId human = new AgentId(assignments.length, "human");
        ReservationOutcome tiles = board.reserveTile(presence.id(), human,
            presence.area(), true, tick);
        int yielded = yieldToHuman(tiles.conflicts(), tick);
        for(Map.Entry<String, Integer> resource : presence.resources().entrySet()){
            ReservationOutcome outcome = board.reserveResource(presence.id(), human,
                resource.getKey(), resource.getValue(), true, tick);
            yielded += yieldToHuman(outcome.conflicts(), tick);
            mindustry.type.Item item = content.item(resource.getKey());
            int stock = item == null ? 0 : StateHasher.coreItem(item);
            ReservationOutcome floor = board.enforceHumanResourceFloor(presence.id(),
                human, resource.getKey(), stock, tick);
            yielded += yieldToHuman(floor.conflicts(), tick);
        }
        return yielded;
    }

    public void releaseHumanPresence(String presenceId){
        board.reservations().releaseAll(presenceId);
    }

    public int humanReservationYields(){ return humanReservationYields; }
    public int humanReservedAmount(String item){
        return board.reservations().reservedAmount(item, true);
    }

    public boolean hasHumanPresence(String presenceId){
        return board.reservations().tileReservations().stream()
            .anyMatch(reservation -> reservation.human()
                && reservation.taskId().equals(presenceId));
    }

    private int yieldToHuman(List<ReservationConflict> conflicts, long tick){
        TreeSet<String> yieldedTasks = new TreeSet<>();
        for(ReservationConflict conflict : conflicts){
            if(conflict.winnerHuman()) yieldedTasks.add(conflict.yieldedTaskId());
        }
        int yielded = 0;
        for(String taskId : yieldedTasks){
            for(int i = 0; i < assignments.length; i++){
                Assignment assignment = current(i);
                if(assignment == null || !assignment.taskId.equals(taskId)) continue;
                AgentRuntimeRegistry.Agent agent = registry.get(i);
                OpResult transition;
                if(assignment.spec.origin() == TaskOrigin.HUMAN){
                    transition = board.release(taskId, AgentId.of(i), tick);
                }else{
                    transition = board.yieldToHuman(taskId, AgentId.of(i), tick);
                }
                if(transition.ok()){
                    if(assignment.spec.origin() != TaskOrigin.HUMAN){
                        tasksAbandoned++;
                        forcedTasksAbandoned++;
                    }
                    rememberTransition(i, assignment.spec, tick, false);
                    clearAssignment(i, agent);
                    humanReservationYields++;
                    yielded++;
                    markDecision("human_reservation_yield");
                }
            }
        }
        return yielded;
    }

    public String lastDecisionReason(){ return lastDecisionReason; }

    public byte[] canonicalAdaptiveState(){
        try{
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            out.writeLong(decisionRevision);
            writeString(out, lastDecisionReason);
            out.writeInt(adaptiveReplans);
            out.writeInt(policySwitches);
            out.writeInt(copperReservationCapacity);
            out.writeInt(previousTasks.length);
            for(int i = 0; i < previousTasks.length; i++){
                writeTask(out, previousTasks[i]);
                out.writeLong(previousTaskTicks[i]);
                writeTask(out, blockedTasks[i]);
                out.writeLong(blockedTaskTicks[i]);
                ArrayList<RetryHoldoff> holdoffs = retryHoldoffs.get(i);
                out.writeInt(holdoffs.size());
                for(RetryHoldoff holdoff : holdoffs){
                    writeTask(out, holdoff.task());
                    out.writeLong(holdoff.blockedTick());
                    out.writeLong(holdoff.retryTick());
                    out.writeBoolean(holdoff.taskTypeScoped());
                }
            }
            out.flush();
            return bytes.toByteArray();
        }catch(IOException impossible){
            throw new AssertionError(impossible);
        }
    }

    public double switchingCost(int agentIndex, TaskSpec task, long tick){
        if(agentIndex < 0 || agentIndex >= previousTasks.length) return 0.0;
        TaskSpec blocked = blockedTasks[agentIndex];
        long sinceBlocked = tick - blockedTaskTicks[agentIndex];
        if(blocked != null && sinceBlocked >= 0 && sinceBlocked < 300
            && sameWork(blocked, task)){
            return 1.0 - sinceBlocked / 300.0;
        }
        TaskSpec previous = previousTasks[agentIndex];
        long elapsed = tick - previousTaskTicks[agentIndex];
        if(previous != null && elapsed >= 0 && elapsed < 120 && !sameWork(previous, task)){
            return 0.5 * (1.0 - elapsed / 120.0);
        }
        return 0.0;
    }

    private boolean retryNotDue(int agentIndex, TaskSpec task, long tick){
        if(agentIndex < 0 || agentIndex >= retryHoldoffs.size()) return false;
        for(RetryHoldoff holdoff : retryHoldoffs.get(agentIndex)){
            if(tick < holdoff.retryTick() && holdoff.task().type() == task.type()
                && (holdoff.taskTypeScoped() || sameWork(holdoff.task(), task))) return true;
        }
        return false;
    }

    /** Whether equivalent work already has a live board entry at this boundary. */
    public boolean semanticTaskActive(TaskSpec task){
        for(TaskState state : board().tasks()){
            if(!state.terminal() && sameWork(state.spec(), task)) return true;
        }
        return false;
    }

    /** Whether equivalent live work is owned by another seat at this boundary. */
    public boolean semanticTaskOwnedByOther(int agentIndex, TaskSpec task){
        AgentId self = AgentId.of(agentIndex);
        for(TaskState state : board().tasks()){
            if(!state.terminal() && state.owner() != null && !state.owner().equals(self)
                && sameWork(state.spec(), task)) return true;
        }
        return false;
    }

    /** Whether another seat owns any live schematic build at this boundary. */
    public boolean liveBuildSchematicOwnedByOther(int agentIndex){
        AgentId self = AgentId.of(agentIndex);
        for(TaskState state : board().tasks()){
            if(!state.terminal() && state.spec().type() == TaskType.BUILD_SCHEMATIC
                && state.owner() != null && !state.owner().equals(self)) return true;
        }
        return false;
    }

    private void rememberTransition(int agentIndex, TaskSpec task, long tick, boolean failed){
        if(agentIndex < 0 || agentIndex >= previousTasks.length) return;
        previousTasks[agentIndex] = task;
        previousTaskTicks[agentIndex] = tick;
        if(failed){
            blockedTasks[agentIndex] = task;
            blockedTaskTicks[agentIndex] = tick;
        }
    }

    private void rememberRetryHoldoff(
        int agentIndex,
        TaskSpec task,
        long blockedTick,
        long retryTick,
        boolean taskTypeScoped
    ){
        if(agentIndex < 0 || agentIndex >= retryHoldoffs.size()
            || task == null || retryTick < 0) return;
        ArrayList<RetryHoldoff> holdoffs = retryHoldoffs.get(agentIndex);
        if(taskTypeScoped){
            holdoffs.removeIf(holdoff -> holdoff.task().type() == task.type());
            holdoffs.add(new RetryHoldoff(task, blockedTick, retryTick, true));
            return;
        }
        for(int i = 0; i < holdoffs.size(); i++){
            if(sameWork(holdoffs.get(i).task(), task)){
                holdoffs.set(i, new RetryHoldoff(task, blockedTick, retryTick, false));
                return;
            }
        }
        holdoffs.add(new RetryHoldoff(task, blockedTick, retryTick, false));
    }

    private void expireRetryHoldoffs(long tick){
        for(ArrayList<RetryHoldoff> holdoffs : retryHoldoffs){
            holdoffs.removeIf(holdoff -> tick >= holdoff.retryTick());
        }
    }

    private void markDecision(String reason){
        decisionRevision++;
        lastDecisionReason = reason;
    }

    private static boolean sameWork(TaskSpec left, TaskSpec right){
        return left.type() == right.type() && Objects.equals(left.target(), right.target());
    }

    private static void writeTask(DataOutputStream out, TaskSpec task) throws IOException{
        if(task == null){
            out.writeBoolean(false);
            return;
        }
        out.writeBoolean(true);
        out.writeInt(task.type().ordinal());
        writeString(out, task.target() == null ? "" : task.target().describe());
    }

    private static void writeString(DataOutputStream out, String value) throws IOException{
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        out.writeInt(encoded.length);
        out.write(encoded);
    }

    private static float center(int start, int size){
        return (start + (size - 1) / 2f) * tilesize;
    }

    private static Jval result(int agentId, boolean accepted, String reason, String type){
        return result(agentId, accepted, reason, type, "");
    }

    private static Jval result(
        int agentId,
        boolean accepted,
        String reason,
        String type,
        String taskId
    ){
        Jval out = Jval.newObject();
        out.put("agent_id", agentId);
        out.put("accepted", accepted);
        out.put("reason", reason);
        out.put("task_action_type", type);
        out.put("task_id", taskId);
        return out;
    }

    private Jval event(CoordinationEvent event){
        Jval out = Jval.newObject();
        out.put("message_id", event.messageId());
        out.put("episode_id", event.episodeId());
        out.put("tick", event.tick());
        out.put("agent_id", event.agent() == null ? -1 : event.agent().index());
        out.put("act", event.act() == null ? "" : event.act().name());
        out.put("task_id", event.taskId());
        out.put("task_type", event.taskType() == null ? "" : event.taskType().name());
        out.put("target", event.targetDescription() == null ? "" : event.targetDescription());
        out.put("priority", event.priority());
        out.put("estimated_ticks", event.estimatedTicks());
        Jval cost = Jval.newObject();
        event.estimatedCost().asMap().forEach(cost::put);
        out.add("estimated_cost", cost);
        Jval capabilities = Jval.newArray();
        event.requiredCapabilities().stream().sorted().forEach(capabilities::add);
        out.add("required_capabilities", capabilities);
        out.put("helpers_requested", event.helpersRequested());
        out.put("offered_contribution", event.offeredContribution() == null
            ? "" : event.offeredContribution());
        out.put("confidence", event.confidence());
        out.put("lease_expiry_tick", event.leaseExpiryTick());
        out.put("parent_task_id", event.parentTaskId() == null ? "" : event.parentTaskId());
        Jval dependencies = Jval.newArray();
        event.dependencyTaskIds().forEach(dependencies::add);
        out.add("dependency_task_ids", dependencies);
        out.put("reason_code", event.reasonCode() == null ? "" : event.reasonCode());
        out.put("progress", event.progress());
        out.put("from_status", event.fromStatus() == null ? "" : event.fromStatus().name());
        out.put("to_status", event.toStatus() == null ? "" : event.toStatus().name());
        out.put("related_agent_id", event.relatedAgent() == null ? -1 : event.relatedAgent().index());
        out.put("announce", event.announce());
        out.put("announcement", event.announce() ? announcementRenderer.render(event) : "");
        return out;
    }

    private final class SharedExpertPort implements ExpertCoordinationDriver.Port{
        @Override
        public SkillResult lastResult(int agentIndex){
            AgentRuntimeRegistry.Agent agent = registry.get(agentIndex);
            return agent == null ? SkillResult.ready() : agent.controller().lastResult();
        }

        @Override
        public Skill activeSkill(int agentIndex){
            AgentRuntimeRegistry.Agent agent = registry.get(agentIndex);
            return agent == null ? null : agent.controller().activeSkill();
        }

        @Override
        public void setSkill(int agentIndex, Skill skill){
            AgentRuntimeRegistry.Agent agent = registry.get(agentIndex);
            if(agent != null) agent.controller().setSkill(skill);
        }

        @Override
        public void cancelWork(int agentIndex){
            AgentRuntimeRegistry.Agent agent = registry.get(agentIndex);
            if(agent == null) return;
            agent.controller().cancelBuildPlans();
            agent.controller().clearSkill();
        }

        @Override
        public void ensureAgent(int agentIndex){
            //The externally stepped registry remains fixed for an episode. The shared
            //policy can continue with surviving slots; demo mode owns explicit rebinding.
        }

        @Override
        public boolean agentAvailable(int agentIndex){
            return CoordinationAdapter.agentAvailable(registry.get(agentIndex));
        }

        @Override
        public int coreCopper(){
            return StateHasher.coreItem(Items.copper);
        }

        @Override
        public boolean buildingMatches(ExpertCoordinationDriver.BuildPlacement placement){
            Building building = world.build(placement.x(), placement.y());
            return building != null && building.block.name.equals(placement.block());
        }
    }

    private record PendingSelection(
        int actionIndex,
        AgentRuntimeRegistry.Agent agent,
        TaskCandidate candidate,
        String actionType
    ){}

    private record RetryHoldoff(
        TaskSpec task,
        long blockedTick,
        long retryTick,
        boolean taskTypeScoped
    ){}

    private record ExecutableSchematic(
        String name,
        int anchorX,
        int anchorY,
        List<BuildSpec> blocks
    ){}

    private static final class Assignment{
        final String taskId;
        final TaskSpec spec;
        final int startCoreCopper;
        final int targetCoreCopper;
        long lastHeartbeatTick;
        int lastProgressBucket = -1;
        String stage;
        String blockedReason = "";
        boolean sawEnemy;

        Assignment(
            String taskId,
            TaskSpec spec,
            String stage,
            int startCoreCopper,
            int targetCoreCopper,
            long tick
        ){
            this.taskId = taskId;
            this.spec = spec;
            this.stage = stage;
            this.startCoreCopper = startCoreCopper;
            this.targetCoreCopper = targetCoreCopper;
            this.lastHeartbeatTick = tick;
        }
    }
}
