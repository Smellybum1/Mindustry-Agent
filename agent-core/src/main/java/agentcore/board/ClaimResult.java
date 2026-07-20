package agentcore.board;

/** Categorized outcome of a {@code claim} (see {@link ClaimOutcome}). */
public enum ClaimResult{
    /** The task was OPEN and is now leased to the claimant. */
    GRANTED,
    /** A contested same-tick claim: the claimant outbid the prior provisional owner. */
    WON_CONTEST,
    /** Rejected: another agent already holds a valid (unexpired) lease. */
    REJECTED_ALREADY_LEASED,
    /** Rejected: a contested same-tick claim the claimant lost on the tie-break. */
    REJECTED_LOWER_BID,
    /** Rejected: the task is not in a claimable state. */
    REJECTED_NOT_OPEN,
    /** Rejected: no such task on the board. */
    REJECTED_UNKNOWN_TASK;

    public boolean granted(){
        return this == GRANTED || this == WON_CONTEST;
    }
}
