package agentcore.event;

import agentcore.AgentId;
import agentcore.CoordinationAct;

import java.util.EnumSet;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * Decides whether a structured event should also surface as a human-facing
 * announcement (brief §11.7 communication rate limits). This gates
 * <em>rendering</em> only; the structured {@link CoordinationEvent} is always
 * logged so telemetry and the protocol never lose information.
 *
 * <p>Rules, per brief §11.7:
 * <ul>
 *   <li><b>Routine acts are never announced</b> — {@code HEARTBEAT} and
 *       {@code PROGRESS}, plus board-internal transitions (null act) such as
 *       proposal and expiry ("Do not print every heartbeat").</li>
 *   <li><b>Normal cooldown</b> — at most one normal announcement per agent every
 *       {@link #minTicksBetweenNormal()} ticks ("no more than one normal
 *       announcement per agent every few simulated seconds").</li>
 *   <li><b>Urgent bypass</b> — urgent events bypass the cooldown. An act is
 *       urgent if the caller flags it urgent, or it is inherently urgent
 *       ({@code BLOCKED}) ("urgent blocked/emergency messages may bypass").</li>
 *   <li><b>Duplicate suppression</b> — a repeated {@code (agent, act, task)}
 *       within {@link #duplicateWindowTicks()} is suppressed, urgent or not
 *       ("repeated identical messages are suppressed").</li>
 * </ul>
 *
 * <p>Deterministic and single-threaded by contract; no synchronization.
 */
public final class RateLimiter{
    /** Acts that are never rendered to humans (routine heartbeats/progress). */
    private static final Set<CoordinationAct> ROUTINE = EnumSet.of(CoordinationAct.HEARTBEAT, CoordinationAct.PROGRESS);
    /** Acts that are inherently urgent and bypass the normal cooldown. */
    private static final Set<CoordinationAct> URGENT = EnumSet.of(CoordinationAct.BLOCKED);

    private final long minTicksBetweenNormal;
    private final long duplicateWindowTicks;

    private final Map<AgentId, Long> lastNormalTick = new HashMap<>();
    private final Map<String, Long> lastDuplicateTick = new HashMap<>();

    /** Defaults: 180-tick (~3 s at 60 tps) cooldown, 300-tick (~5 s) duplicate window. */
    public RateLimiter(){
        this(180L, 300L);
    }

    public RateLimiter(long minTicksBetweenNormal, long duplicateWindowTicks){
        if(minTicksBetweenNormal < 0 || duplicateWindowTicks < 0){
            throw new IllegalArgumentException("rate-limit windows must be non-negative");
        }
        this.minTicksBetweenNormal = minTicksBetweenNormal;
        this.duplicateWindowTicks = duplicateWindowTicks;
    }

    public long minTicksBetweenNormal(){ return minTicksBetweenNormal; }
    public long duplicateWindowTicks(){ return duplicateWindowTicks; }

    /**
     * Decide whether {@code (agent, act, taskId)} at {@code tick} should be
     * announced, updating internal bookkeeping when it is allowed. Passing a null
     * {@code act} (board-internal transition) always returns false.
     *
     * @param urgent caller-supplied urgency (e.g. emergency replanning); combined
     *               with the inherently-urgent act set
     */
    public boolean shouldAnnounce(AgentId agent, CoordinationAct act, String taskId, long tick, boolean urgent){
        if(act == null || ROUTINE.contains(act)) return false;
        if(agent == null) return false;

        boolean effectiveUrgent = urgent || URGENT.contains(act);

        // Duplicate suppression applies regardless of urgency.
        String dupKey = agent.index() + "|" + act + "|" + taskId;
        Long lastDup = lastDuplicateTick.get(dupKey);
        if(lastDup != null && tick - lastDup < duplicateWindowTicks){
            return false;
        }

        // Normal cooldown applies only to non-urgent announcements.
        if(!effectiveUrgent){
            Long lastNormal = lastNormalTick.get(agent);
            if(lastNormal != null && tick - lastNormal < minTicksBetweenNormal){
                return false;
            }
        }

        // Allowed: record it. Urgent messages still reset the normal cooldown so a
        // burst of urgent+normal from one agent cannot flood the channel.
        lastNormalTick.put(agent, tick);
        lastDuplicateTick.put(dupKey, tick);
        return true;
    }

    /** Clear all bookkeeping (episode reset). */
    public void reset(){
        lastNormalTick.clear();
        lastDuplicateTick.clear();
    }
}
