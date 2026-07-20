package agentcore.board;

import agentcore.AgentId;
import agentcore.event.CoordinationEvent;

/**
 * The outcome of a claim attempt, including who owns the task after resolution
 * (brief §11.5). On a contested same-tick claim the {@link #owner()} is the
 * deterministic winner regardless of call order.
 *
 * @param result           categorized outcome
 * @param owner            the task owner after resolution (may differ from the claimant)
 * @param leaseExpiryTick  the winning lease's expiry, or -1 if none
 * @param event            the emitted event on a granted claim, else null
 */
public record ClaimOutcome(ClaimResult result, AgentId owner, long leaseExpiryTick, CoordinationEvent event){
    public boolean granted(){ return result.granted(); }
}
