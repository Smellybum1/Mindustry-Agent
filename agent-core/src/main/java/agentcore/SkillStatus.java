package agentcore;

/**
 * Typed result status returned by every low-level skill executor (brief §10.3).
 *
 * <p>Alongside this status a skill also returns a machine-readable reason code,
 * a progress estimate, and a next-retry tick (not modeled by this enum).
 */
public enum SkillStatus{
    /** Skill is constructed and ready to run but has not started. */
    READY,
    /** Skill is actively executing this tick. */
    RUNNING,
    /** Skill reached its completion predicate successfully. */
    SUCCEEDED,
    /** Skill cannot currently make progress but may retry later. */
    BLOCKED,
    /** Skill hit an unrecoverable failure condition. */
    FAILED,
    /** Skill was cancelled by a higher-level decision. */
    CANCELLED
}
