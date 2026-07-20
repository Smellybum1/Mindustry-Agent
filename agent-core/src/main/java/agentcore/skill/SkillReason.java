package agentcore.skill;

/**
 * Machine-readable reason code accompanying every {@link SkillResult} (docs/M3_DESIGN.md D3/D4).
 *
 * <p>Reasons are stable, ordinal-hashed identifiers: a higher-level policy or the
 * coordination board can branch on them without parsing prose. They are also part of
 * the per-agent observation ({@code skill.reason}) and the golden state hash (D7), so
 * their {@link #ordinal()} order must stay append-only.
 */
public enum SkillReason{
    /** No specific reason (freshly constructed / ready). */
    NONE,
    /** Steering toward a destination this tick. */
    MOVING,
    /** Arrived within tolerance of the navigation target. */
    ARRIVED,
    /** Actively mining (or draining pending mined items). */
    MINING,
    /** Requested cargo amount reached. */
    TARGET_REACHED,
    /** Unit cargo is at capacity. */
    CARGO_FULL,
    /** No measurable progress toward the target for the stuck window. */
    STUCK,
    /** Target tile/entity is not a legal target for this skill. */
    INVALID_TARGET,
    /** No core building is available to deliver to. */
    NO_CORE,
    /** Transferring cargo into the core this tick. */
    DELIVERING,
    /** Cargo delivered / nothing left to deliver. */
    DELIVERED,
    /** Cargo held but the core cannot accept more (at capacity). */
    CORE_FULL,
    /** Waiting out a fixed tick budget. */
    WAITING,
    /** The wait budget elapsed. */
    WAIT_ELAPSED,
    /** Skill was cancelled by a higher-level decision. */
    CANCELLED,
    /** Unit is executing an engine-owned build plan. */
    BUILDING,
    /** Requested block exists and construction is complete. */
    BUILT,
    /** Build progress stalled because the core lacks the recipe. */
    RESOURCES_SHORT,
    /** A conflicting building or invalid footprint occupies the target. */
    OCCUPIED,
    /** The unit could not enter engine build range. */
    OUT_OF_RANGE,
    /** An enqueued build plan disappeared before completion. */
    PLAN_REMOVED,
    /** Withdrawing requested items from the team core. */
    WITHDRAWING,
    /** Carrying/depositing requested items into a building. */
    SUPPLYING,
    /** Target received the request or refuses further stock. */
    SUPPLIED,
    /** The team core cannot provide more of the requested item. */
    CORE_SHORT,
    /** Existing unit cargo is a different item and cannot be mixed. */
    CARGO_MISMATCH,
    /** Reconstructing an engine-recorded destroyed team block. */
    REBUILDING,
    /** No destroyed blocks remain in the requested region. */
    REBUILT
}
