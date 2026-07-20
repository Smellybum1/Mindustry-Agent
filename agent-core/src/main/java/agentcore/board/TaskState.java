package agentcore.board;

import agentcore.AgentId;
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
 * The mutable, per-episode lifecycle record of one task on the board (brief §10.1
 * "TaskState"). Read freely by policies and telemetry through the getters; all
 * mutation is package-private and performed exclusively by {@link TaskBoard},
 * which is single-threaded by contract (brief §23.6). See {@code docs/COORDINATION.md}.
 */
public final class TaskState{
    private final TaskSpec spec;

    private TaskStatus status = TaskStatus.OPEN;
    private AgentId owner;                       // nullable
    private Claim activeClaim;                   // nullable; retained for tie-breaking
    private long leaseExpiryTick = -1;
    private double progress;
    private String reasonCode;                   // nullable

    private final List<HelperContract> helpers = new ArrayList<>();
    private final List<HelperOffer> pendingOffers = new ArrayList<>();
    // earliest ANNOUNCE_INTENT tick per agent, insertion-ordered for determinism
    private final Map<AgentId, Long> intentTicks = new LinkedHashMap<>();

    TaskState(TaskSpec spec){
        this.spec = spec;
    }

    // ---- read API (public) ----

    public TaskSpec spec(){ return spec; }
    public String taskId(){ return spec.taskId(); }
    public TaskStatus status(){ return status; }
    /** Current exclusive owner, or null when {@link TaskStatus#OPEN}. */
    public AgentId owner(){ return owner; }
    /** Tick at which the lease lapses; -1 when not leased. */
    public long leaseExpiryTick(){ return leaseExpiryTick; }
    /** Progress in [0,1]. */
    public double progress(){ return progress; }
    /** Machine-readable reason for the last BLOCKED/ABANDONED transition, or null. */
    public String reasonCode(){ return reasonCode; }
    /** Accepted helper contracts, unmodifiable. */
    public List<HelperContract> helpers(){ return Collections.unmodifiableList(helpers); }
    /** Outstanding, not-yet-accepted help offers, unmodifiable. */
    public List<HelperOffer> pendingOffers(){ return Collections.unmodifiableList(pendingOffers); }
    /** True when a lease exists and lapses at or before {@code tick}. */
    public boolean leaseExpired(long tick){
        return leaseExpiryTick >= 0 && tick >= leaseExpiryTick;
    }
    /** True when the status is terminal (COMPLETED or ABANDONED). */
    public boolean terminal(){
        return status == TaskStatus.COMPLETED || status == TaskStatus.ABANDONED;
    }

    // ---- mutation API (board-only) ----

    void setStatus(TaskStatus status){ this.status = status; }
    void setOwner(AgentId owner){ this.owner = owner; }
    void setActiveClaim(Claim claim){ this.activeClaim = claim; }
    Claim activeClaim(){ return activeClaim; }
    void setLeaseExpiryTick(long tick){ this.leaseExpiryTick = tick; }
    void setProgress(double progress){ this.progress = clamp01(progress); }
    void setReasonCode(String reasonCode){ this.reasonCode = reasonCode; }

    void recordIntent(AgentId agent, long tick){
        intentTicks.putIfAbsent(agent, tick);
    }

    long announceTickFor(AgentId agent, long fallback){
        return intentTicks.getOrDefault(agent, fallback);
    }

    void addOffer(HelperOffer offer){ pendingOffers.add(offer); }

    HelperOffer removeOffer(AgentId helper){
        for(int i = 0; i < pendingOffers.size(); i++){
            if(pendingOffers.get(i).helper().equals(helper)){
                return pendingOffers.remove(i);
            }
        }
        return null;
    }

    void addHelper(HelperContract contract){ helpers.add(contract); }

    HelperContract helperFor(AgentId helper){
        for(HelperContract c : helpers){
            if(c.helper().equals(helper)) return c;
        }
        return null;
    }

    /** Reset ownership/lease/claim/offers when the task reopens or terminates. */
    void clearOwnership(){
        this.owner = null;
        this.activeClaim = null;
        this.leaseExpiryTick = -1;
    }

    private static double clamp01(double v){
        if(v < 0) return 0;
        if(v > 1) return 1;
        return v;
    }
}
