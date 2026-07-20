package agentcore.board;

import agentcore.AgentId;
import agentcore.CoordinationAct;
import agentcore.event.CoordinationEvent;
import agentcore.event.EventLog;
import agentcore.event.RateLimiter;
import agentcore.reservation.Rect;
import agentcore.reservation.ReservationConflict;
import agentcore.reservation.ReservationOutcome;
import agentcore.reservation.ReservationRegistry;
import agentcore.task.HelperContract;
import agentcore.task.HelperOffer;
import agentcore.task.TaskSpec;
import agentcore.task.TaskStatus;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The shared, decentralized contract board (brief §11.1). It is a communication
 * and conflict-resolution medium, <em>not</em> a central planner: it stores open
 * proposals, intentions, claims, helper offers/contracts, reservations, progress,
 * and lifecycle transitions, and enforces valid commitments. Each agent decides
 * for itself what to do; the board only says whether a commitment is legal and
 * who wins a contest.
 *
 * <p>Every mutation emits exactly one {@link CoordinationEvent} into the
 * {@link EventLog}; the {@link RateLimiter} decides which events also surface as
 * human announcements. Reservations are delegated to a {@link ReservationRegistry}
 * and released automatically when a task terminates or reopens.
 *
 * <p><b>Threading:</b> single-threaded by contract (brief §23.6) — only the
 * simulation thread touches the board. It is deliberately not synchronized.
 *
 * <p><b>Determinism:</b> tasks iterate in insertion order (a {@link LinkedHashMap}),
 * claim contests resolve by an explicit total order, and no wall-clock or
 * unseeded randomness is used. See {@code docs/COORDINATION.md} for the state
 * machine and semantics.
 */
public final class TaskBoard{
    /** Default lease length: 600 ticks (~10 s at 60 tps). */
    public static final long DEFAULT_LEASE_TICKS = 600L;

    private final Map<String, TaskState> tasks = new LinkedHashMap<>();
    private final EventLog events;
    private final RateLimiter rateLimiter;
    private final ReservationRegistry reservations;
    private final long leaseDurationTicks;

    private long episodeId;

    public TaskBoard(){
        this(new EventLog(), new RateLimiter(), new ReservationRegistry(), DEFAULT_LEASE_TICKS, 0L);
    }

    public TaskBoard(EventLog events, RateLimiter rateLimiter, ReservationRegistry reservations,
                     long leaseDurationTicks, long episodeId){
        this.events = events;
        this.rateLimiter = rateLimiter;
        this.reservations = reservations;
        if(leaseDurationTicks <= 0) throw new IllegalArgumentException("leaseDurationTicks must be > 0");
        this.leaseDurationTicks = leaseDurationTicks;
        this.episodeId = episodeId;
    }

    // ---- accessors ----

    public EventLog events(){ return events; }
    public RateLimiter rateLimiter(){ return rateLimiter; }
    public ReservationRegistry reservations(){ return reservations; }
    public long episodeId(){ return episodeId; }
    public long leaseDurationTicks(){ return leaseDurationTicks; }

    /** The task state for {@code taskId}, or null if unknown. */
    public TaskState task(String taskId){ return tasks.get(taskId); }

    /** All task states in insertion order, unmodifiable. */
    public List<TaskState> tasks(){ return List.copyOf(tasks.values()); }

    /** Task states currently {@link TaskStatus#OPEN}, insertion order. */
    public List<TaskState> openTasks(){
        List<TaskState> out = new ArrayList<>();
        for(TaskState st : tasks.values()){
            if(st.status() == TaskStatus.OPEN) out.add(st);
        }
        return Collections.unmodifiableList(out);
    }

    // ---- lifecycle: propose ----

    /**
     * Register a new OPEN task (brief §11.1 "open task proposals"). The proposer is
     * usually the candidate generator, so no agent is attributed; the emitted event
     * is a board-internal transition (null act). Re-proposing an existing id is
     * rejected via {@link IllegalArgumentException} because ids must be unique.
     */
    public TaskState propose(TaskSpec spec, long tick){
        if(tasks.containsKey(spec.taskId())){
            throw new IllegalArgumentException("duplicate task id: " + spec.taskId());
        }
        TaskState st = new TaskState(spec);
        tasks.put(spec.taskId(), st);
        emit(st, null, null, null, tick, null, TaskStatus.OPEN, false);
        return st;
    }

    // ---- coordination acts ----

    /**
     * Announce intent to work a task (brief §11.2 {@code ANNOUNCE_INTENT}). Records
     * the announcement tick used to break claim ties (brief §11.5). The task must
     * exist and be OPEN.
     */
    public OpResult announceIntent(String taskId, AgentId agent, double confidence, long tick){
        TaskState st = tasks.get(taskId);
        if(st == null) return OpResult.rejected("unknown_task");
        if(st.status() != TaskStatus.OPEN) return OpResult.rejected("not_open");
        st.recordIntent(agent, tick);
        CoordinationEvent ev = emit(st, CoordinationAct.ANNOUNCE_INTENT, agent, null, tick, st.status(), st.status(),
            false, b -> b.confidence(confidence));
        return OpResult.ok(ev);
    }

    /**
     * Claim a task with a bid (brief §11.5). Claims are leases, not locks. If the
     * task is OPEN it is leased immediately. If it was claimed earlier this same
     * tick (a contested claim), the winner is decided deterministically by
     * (bid desc, announcement tick asc, agent id lexicographic) regardless of the
     * order the claims arrive. A task already validly leased on an earlier tick is
     * not stealable except through lease expiry.
     */
    public ClaimOutcome claim(String taskId, AgentId agent, double bid, long tick){
        TaskState st = tasks.get(taskId);
        if(st == null){
            return new ClaimOutcome(ClaimResult.REJECTED_UNKNOWN_TASK, null, -1, null);
        }
        long announceTick = st.announceTickFor(agent, tick);
        Claim incoming = new Claim(agent, bid, announceTick, tick);

        // Contested same-tick claim: a provisional owner was set this tick.
        if(st.status() == TaskStatus.CLAIMED && st.activeClaim() != null
            && st.activeClaim().claimTick() == tick && !st.leaseExpired(tick)){
            Claim current = st.activeClaim();
            if(current.agent().equals(agent)){
                // Same agent re-claiming this tick: keep current, no change.
                return new ClaimOutcome(ClaimResult.GRANTED, st.owner(), st.leaseExpiryTick(), null);
            }
            if(incoming.beats(current)){
                grantClaim(st, incoming, tick);
                CoordinationEvent ev = emit(st, CoordinationAct.CLAIM_TASK, agent, null, tick,
                    TaskStatus.CLAIMED, TaskStatus.CLAIMED, false, b -> b.confidence(bid));
                return new ClaimOutcome(ClaimResult.WON_CONTEST, agent, st.leaseExpiryTick(), ev);
            }
            return new ClaimOutcome(ClaimResult.REJECTED_LOWER_BID, st.owner(), st.leaseExpiryTick(), null);
        }

        // Already leased (earlier tick, not yet expired).
        if(st.owner() != null && !st.leaseExpired(tick)
            && st.status() != TaskStatus.OPEN){
            return new ClaimOutcome(ClaimResult.REJECTED_ALREADY_LEASED, st.owner(), st.leaseExpiryTick(), null);
        }

        // OPEN (or lease already lapsed but not yet swept): grant.
        if(st.status() == TaskStatus.OPEN || st.leaseExpired(tick)){
            TaskStatus from = st.status();
            if(st.owner() != null){
                // Taking over a lapsed lease: release the stale owner's reservations.
                reservations.releaseAll(taskId);
            }
            grantClaim(st, incoming, tick);
            CoordinationEvent ev = emit(st, CoordinationAct.CLAIM_TASK, agent, null, tick,
                from, TaskStatus.CLAIMED, false, b -> b.confidence(bid));
            return new ClaimOutcome(ClaimResult.GRANTED, agent, st.leaseExpiryTick(), ev);
        }

        return new ClaimOutcome(ClaimResult.REJECTED_NOT_OPEN, st.owner(), st.leaseExpiryTick(), null);
    }

    private void grantClaim(TaskState st, Claim claim, long tick){
        st.setOwner(claim.agent());
        st.setActiveClaim(claim);
        st.setStatus(TaskStatus.CLAIMED);
        st.setLeaseExpiryTick(tick + leaseDurationTicks);
    }

    /** Move a claimed task to RUNNING (brief §11.2 {@code START_TASK}); renews the lease. */
    public OpResult start(String taskId, AgentId agent, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.status() != TaskStatus.CLAIMED && st.status() != TaskStatus.BLOCKED){
            return OpResult.rejected("not_claimed");
        }
        TaskStatus from = st.status();
        st.setStatus(TaskStatus.RUNNING);
        renewLease(st, tick);
        return OpResult.ok(emit(st, CoordinationAct.START_TASK, agent, null, tick, from, TaskStatus.RUNNING, false));
    }

    /**
     * Renew the lease via a heartbeat (brief §11.5). Routine, never announced. A
     * running task that keeps heartbeating never expires; one that stops becomes
     * available to others.
     */
    public OpResult heartbeat(String taskId, AgentId agent, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.terminal()) return OpResult.rejected("terminal");
        renewLease(st, tick);
        return OpResult.ok(emit(st, CoordinationAct.HEARTBEAT, agent, null, tick, st.status(), st.status(), false));
    }

    /**
     * Report progress in [0,1] (brief §11.2 {@code PROGRESS}). Renews the lease and
     * resumes a BLOCKED task to RUNNING. Routine, never announced.
     */
    public OpResult reportProgress(String taskId, AgentId agent, double progress, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.terminal()) return OpResult.rejected("terminal");
        TaskStatus from = st.status();
        st.setProgress(progress);
        if(st.status() == TaskStatus.BLOCKED || st.status() == TaskStatus.CLAIMED){
            st.setStatus(TaskStatus.RUNNING);
        }
        st.setReasonCode(null);
        renewLease(st, tick);
        return OpResult.ok(emit(st, CoordinationAct.PROGRESS, agent, null, tick, from, st.status(), false,
            b -> b.progress(st.progress())));
    }

    /**
     * Report the task blocked with a reason code (brief §11.2 {@code BLOCKED}).
     * Urgent — bypasses the normal announcement cooldown. The owner keeps the lease
     * (it can recover), but stops making progress.
     */
    public OpResult reportBlocked(String taskId, AgentId agent, String reasonCode, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.terminal()) return OpResult.rejected("terminal");
        TaskStatus from = st.status();
        st.setStatus(TaskStatus.BLOCKED);
        st.setReasonCode(reasonCode);
        // keep lease so the owner can recover; heartbeats still required
        return OpResult.ok(emit(st, CoordinationAct.BLOCKED, agent, null, tick, from, TaskStatus.BLOCKED, true,
            b -> b.reasonCode(reasonCode)));
    }

    /** Offer help on a task (brief §11.2 {@code OFFER_HELP}); creates a pending offer. */
    public OpResult offerHelp(String taskId, AgentId helper, String contribution, int amount, long tick){
        TaskState st = tasks.get(taskId);
        if(st == null) return OpResult.rejected("unknown_task");
        if(st.terminal()) return OpResult.rejected("terminal");
        if(st.owner() != null && st.owner().equals(helper)) return OpResult.rejected("owner_cannot_help_self");
        if(st.helperFor(helper) != null) return OpResult.rejected("already_helping");
        st.removeOffer(helper);                                  // replace any prior offer
        st.addOffer(new HelperOffer(helper, contribution, amount, tick));
        return OpResult.ok(emit(st, CoordinationAct.OFFER_HELP, helper, st.owner(), tick, st.status(), st.status(),
            false, b -> b.offeredContribution(contribution)));
    }

    /**
     * Accept a pending help offer (brief §11.2 {@code ACCEPT_HELP}); converts it to
     * a binding {@link HelperContract}. Only the task owner may accept.
     */
    public OpResult acceptHelp(String taskId, AgentId owner, AgentId helper, long tick){
        TaskState st = requireOwner(taskId, owner);
        if(st == null) return OpResult.rejected(taskReason(taskId, owner));
        HelperOffer offer = st.removeOffer(helper);
        if(offer == null) return OpResult.rejected("no_such_offer");
        HelperContract contract = HelperContract.fromOffer(offer, tick);
        st.addHelper(contract);
        return OpResult.ok(emit(st, CoordinationAct.ACCEPT_HELP, helper, owner, tick, st.status(), st.status(),
            false, b -> b.offeredContribution(offer.contribution())));
    }

    /** Decline a pending help offer (brief §11.2 {@code DECLINE_HELP}). Only the owner may decline. */
    public OpResult declineHelp(String taskId, AgentId owner, AgentId helper, long tick){
        TaskState st = requireOwner(taskId, owner);
        if(st == null) return OpResult.rejected(taskReason(taskId, owner));
        HelperOffer offer = st.removeOffer(helper);
        if(offer == null) return OpResult.rejected("no_such_offer");
        return OpResult.ok(emit(st, CoordinationAct.DECLINE_HELP, owner, helper, tick, st.status(), st.status(),
            false, b -> b.offeredContribution(offer.contribution())));
    }

    /**
     * Mark a helper's accepted contract fulfilled (brief §11.5, §17.1 "accepted
     * helper contract successfully fulfilled"). Emitted as a {@code PROGRESS} act
     * with reason {@code "help_fulfilled"}; routine and not announced (brief §11.7
     * does not list helper fulfilment among announceable transitions).
     */
    public OpResult reportHelpFulfilled(String taskId, AgentId helper, long tick){
        TaskState st = tasks.get(taskId);
        if(st == null) return OpResult.rejected("unknown_task");
        HelperContract contract = st.helperFor(helper);
        if(contract == null) return OpResult.rejected("no_such_contract");
        if(contract.fulfilled()) return OpResult.rejected("already_fulfilled");
        contract.markFulfilled(tick);
        return OpResult.ok(emit(st, CoordinationAct.PROGRESS, helper, st.owner(), tick, st.status(), st.status(),
            false, b -> b.reasonCode("help_fulfilled").offeredContribution(contract.contribution())));
    }

    /**
     * Request help on the currently owned task (brief §11.2 {@code REQUEST_HELP}).
     * Only the owner may request. Announceable.
     */
    public OpResult requestHelp(String taskId, AgentId agent, int helpersWanted, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.terminal()) return OpResult.rejected("terminal");
        return OpResult.ok(emit(st, CoordinationAct.REQUEST_HELP, agent, null, tick, st.status(), st.status(),
            false, b -> b.helpersRequested(helpersWanted)));
    }

    // ---- lifecycle: terminal & reopen ----

    /** Complete the task (brief §11.2 {@code COMPLETE}). Terminal; releases reservations. Only the owner. */
    public OpResult complete(String taskId, AgentId agent, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.terminal()) return OpResult.rejected("terminal");
        TaskStatus from = st.status();
        st.setProgress(1.0);
        st.setStatus(TaskStatus.COMPLETED);
        reservations.releaseAll(taskId);
        CoordinationEvent ev = emit(st, CoordinationAct.COMPLETE, agent, null, tick, from, TaskStatus.COMPLETED,
            false, b -> b.progress(1.0));
        st.clearOwnership();
        return OpResult.ok(ev);
    }

    /**
     * Abandon the task (brief §11.2 {@code ABANDON}). Terminal; releases reservations
     * and drops pending offers (brief §11.5 "Abandonment must release tile and
     * resource reservations"). Only the owner. Announceable.
     */
    public OpResult abandon(String taskId, AgentId agent, String reasonCode, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.terminal()) return OpResult.rejected("terminal");
        TaskStatus from = st.status();
        st.setStatus(TaskStatus.ABANDONED);
        st.setReasonCode(reasonCode);
        reservations.releaseAll(taskId);
        CoordinationEvent ev = emit(st, CoordinationAct.ABANDON, agent, null, tick, from, TaskStatus.ABANDONED,
            true, b -> b.reasonCode(reasonCode));
        st.clearOwnership();
        return OpResult.ok(ev);
    }

    /**
     * Voluntarily release the task back to OPEN (brief §11.2 {@code RELEASE}).
     * Unlike {@link #abandon}, the task stays alive and reclaimable; reservations
     * are released. Only the owner. Announceable.
     */
    public OpResult release(String taskId, AgentId agent, long tick){
        TaskState st = requireOwner(taskId, agent);
        if(st == null) return OpResult.rejected(taskReason(taskId, agent));
        if(st.terminal()) return OpResult.rejected("terminal");
        TaskStatus from = st.status();
        reservations.releaseAll(taskId);
        st.setStatus(TaskStatus.OPEN);
        st.clearOwnership();
        return OpResult.ok(emit(st, CoordinationAct.RELEASE, agent, null, tick, from, TaskStatus.OPEN, false));
    }

    /**
     * Sweep every task whose lease has lapsed (brief §11.5 "If an agent crashes,
     * disconnects, or stops reporting, the task becomes available"). Each expired
     * task emits a board-internal EXPIRED event, releases its reservations, and is
     * reopened to OPEN. Returns the reopened task ids in deterministic order.
     */
    public List<String> expireStale(long tick){
        List<String> expired = new ArrayList<>();
        for(TaskState st : tasks.values()){
            boolean active = st.status() == TaskStatus.CLAIMED
                || st.status() == TaskStatus.RUNNING
                || st.status() == TaskStatus.BLOCKED;
            if(active && st.leaseExpired(tick)){
                TaskStatus from = st.status();
                AgentId previousOwner = st.owner();
                reservations.releaseAll(st.taskId());
                st.setStatus(TaskStatus.EXPIRED);
                emit(st, null, previousOwner, null, tick, from, TaskStatus.EXPIRED, false);
                // reopen immediately so it can be reclaimed
                st.setStatus(TaskStatus.OPEN);
                st.clearOwnership();
                expired.add(st.taskId());
            }
        }
        return expired;
    }

    // ---- reservations tied to task lifecycle ----

    /** Reserve a rectangle of tiles for a task; emits a conflict event if a reservation yields. */
    public ReservationOutcome reserveTile(String taskId, AgentId agent, Rect area, boolean human, long tick){
        ReservationOutcome outcome = reservations.acquireTile(taskId, agent, area, human, tick);
        emitConflicts(outcome.conflicts(), tick);
        return outcome;
    }

    /** Reserve a resource amount for a task. */
    public ReservationOutcome reserveResource(String taskId, AgentId agent, String item, int amount, boolean human, long tick){
        ReservationOutcome outcome = reservations.acquireResource(taskId, agent, item, amount, human, tick);
        emitConflicts(outcome.conflicts(), tick);
        return outcome;
    }

    /** Reserve a named region for a task. */
    public ReservationOutcome reserveRegion(String taskId, AgentId agent, String regionId, boolean human, long tick){
        ReservationOutcome outcome = reservations.acquireRegion(taskId, agent, regionId, human, tick);
        emitConflicts(outcome.conflicts(), tick);
        return outcome;
    }

    private void emitConflicts(List<ReservationConflict> conflicts, long tick){
        for(ReservationConflict c : conflicts){
            // Only human-override yields warrant a human announcement (brief §20.2:
            // "yield and announce the conflict once"). Agent-agent overlaps are logged
            // for telemetry but not announced.
            boolean announce = c.winnerHuman();
            TaskState st = tasks.get(c.yieldedTaskId());
            String targetDesc = c.detail();
            events.append(CoordinationEvent.builder()
                .messageId(events.nextMessageId())
                .episodeId(episodeId)
                .tick(tick)
                .agent(c.yieldedAgent())
                .act(null)
                .taskId(c.yieldedTaskId())
                .taskType(st == null ? null : st.spec().type())
                .targetDescription(targetDesc)
                .relatedAgent(c.winnerAgent())
                .reasonCode(c.winnerHuman() ? "yield_to_human" : "reservation_overlap")
                .announce(announce)
                .build());
        }
    }

    // ---- reset ----

    /** Clear all episode-local state (brief §7.4, §23.5 "reset clears all episode-local state"). */
    public void reset(long newEpisodeId){
        tasks.clear();
        events.reset();
        rateLimiter.reset();
        reservations.reset();
        this.episodeId = newEpisodeId;
    }

    // ---- internal helpers ----

    private void renewLease(TaskState st, long tick){
        st.setLeaseExpiryTick(tick + leaseDurationTicks);
    }

    /** Returns the task state if {@code agent} owns it, else null. */
    private TaskState requireOwner(String taskId, AgentId agent){
        TaskState st = tasks.get(taskId);
        if(st == null) return null;
        if(st.owner() == null || !st.owner().equals(agent)) return null;
        return st;
    }

    private String taskReason(String taskId, AgentId agent){
        TaskState st = tasks.get(taskId);
        if(st == null) return "unknown_task";
        if(st.owner() == null) return "unowned";
        return "not_owner";
    }

    // ---- event construction ----

    private CoordinationEvent emit(TaskState st, CoordinationAct act, AgentId agent, AgentId related,
                                   long tick, TaskStatus from, TaskStatus to, boolean urgent){
        return emit(st, act, agent, related, tick, from, to, urgent, null);
    }

    private CoordinationEvent emit(TaskState st, CoordinationAct act, AgentId agent, AgentId related,
                                   long tick, TaskStatus from, TaskStatus to, boolean urgent, EventCustomizer extra){
        TaskSpec spec = st.spec();
        boolean announce = rateLimiter.shouldAnnounce(agent, act, spec.taskId(), tick, urgent);
        CoordinationEvent.Builder b = CoordinationEvent.builder()
            .messageId(events.nextMessageId())
            .episodeId(episodeId)
            .tick(tick)
            .agent(agent)
            .act(act)
            .taskId(spec.taskId())
            .taskType(spec.type())
            .targetDescription(spec.target() == null ? null : spec.target().describe())
            .priority(spec.priority())
            .estimatedTicks(spec.estimatedTicks())
            .estimatedCost(spec.estimatedCost())
            .requiredCapabilities(spec.requiredCapabilities())
            .helpersRequested(spec.helpersRequested())
            .leaseExpiryTick(st.leaseExpiryTick())
            .parentTaskId(spec.parentTaskId())
            .dependencyTaskIds(spec.dependencyTaskIds())
            .progress(st.progress())
            .fromStatus(from)
            .toStatus(to)
            .relatedAgent(related)
            .announce(announce);
        if(extra != null) extra.apply(b);
        CoordinationEvent ev = b.build();
        events.append(ev);
        return ev;
    }

    /** Small functional seam so op-specific fields can be layered onto the base event. */
    @FunctionalInterface
    private interface EventCustomizer{
        void apply(CoordinationEvent.Builder b);
    }
}
