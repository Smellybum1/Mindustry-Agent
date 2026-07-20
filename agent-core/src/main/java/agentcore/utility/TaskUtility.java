package agentcore.utility;

import agentcore.AgentId;
import agentcore.task.TaskSpec;

/**
 * Computes an agent's utility (bid) for a candidate task (brief §11.1). Each agent
 * independently scores candidate tasks; the board consumes the resulting bid to
 * resolve simultaneous claims (brief §11.5). This interface is the seam a learned
 * policy replaces later — the board enforces valid commitments regardless of how
 * the score is produced (brief §11.1, §16.6).
 *
 * <p>Implementations must be deterministic.
 */
public interface TaskUtility{
    /** The scalar utility/bid of {@code task} for {@code agent} at {@code tick}. */
    double score(AgentId agent, TaskSpec task, long tick);
}
