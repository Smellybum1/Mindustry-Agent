package agentcore;

/**
 * Coordination acts for the decentralized contract-board protocol (brief §11.2).
 *
 * <p>These are the authoritative, structured messages agents exchange on the
 * shared task board. Human-readable announcements are <em>rendered from</em>
 * these acts, never the other way around (ADR-0005). A {@link #CLAIM_TASK} is a
 * lease, not a permanent lock.
 */
public enum CoordinationAct{
    ANNOUNCE_INTENT,
    CLAIM_TASK,
    OFFER_HELP,
    ACCEPT_HELP,
    DECLINE_HELP,
    START_TASK,
    PROGRESS,
    BLOCKED,
    COMPLETE,
    ABANDON,
    RELEASE,
    REQUEST_HELP,
    HEARTBEAT
}
