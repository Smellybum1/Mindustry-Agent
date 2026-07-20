package agentcore.task;

/**
 * Lifecycle status of a task on the shared board (brief §10.1, §11).
 *
 * <p>The legal transitions form a small state machine enforced by
 * {@code agentcore.board.TaskBoard}; see {@code docs/COORDINATION.md} for the
 * full diagram. In summary:
 *
 * <pre>
 *   (none) --propose--&gt; OPEN
 *   OPEN --claim--&gt; CLAIMED
 *   CLAIMED --start--&gt; RUNNING
 *   RUNNING --reportBlocked--&gt; BLOCKED --renewLease/heartbeat--&gt; RUNNING
 *   CLAIMED|RUNNING|BLOCKED --complete--&gt; COMPLETED   (terminal)
 *   CLAIMED|RUNNING|BLOCKED --abandon--&gt; ABANDONED    (terminal)
 *   CLAIMED|RUNNING|BLOCKED --release--&gt; OPEN         (voluntary, keeps task alive)
 *   CLAIMED|RUNNING|BLOCKED --expireStale--&gt; EXPIRED  (lease lapsed) --&gt; reopened OPEN
 * </pre>
 *
 * <p>{@link #EXPIRED} is a transient marker emitted when a lease lapses; the
 * board immediately reopens the task to {@link #OPEN} so it can be reclaimed.
 */
public enum TaskStatus{
    /** Proposed and available; nobody owns it. */
    OPEN,
    /** Leased to an owner but not yet executing. */
    CLAIMED,
    /** Owner is actively executing; lease renewed by heartbeats. */
    RUNNING,
    /** Owner cannot currently progress but still holds the lease. */
    BLOCKED,
    /** Completion predicate satisfied. Terminal. */
    COMPLETED,
    /** Owner relinquished the task and its reservations. Terminal. */
    ABANDONED,
    /** Lease lapsed without renewal; the board reopens the task. */
    EXPIRED
}
