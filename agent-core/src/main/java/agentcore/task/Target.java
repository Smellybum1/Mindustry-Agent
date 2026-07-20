package agentcore.task;

/**
 * A typed, immutable reference to the thing a task acts upon (brief §11.3
 * {@code target} field).
 *
 * <p>Kept engine-independent on purpose: the board and coordination layer never
 * touch mindustry {@code :core} classes. Coordinates are raw tile indices and
 * ids are plain strings/longs; the engine adapter (later, in the skill/plugin
 * layer) maps these onto real {@code Tile}, {@code Building}, and {@code Unit}
 * references. See {@code docs/COORDINATION.md}.
 */
public sealed interface Target permits TileTarget, RegionTarget, EntityTarget, ResourceTarget{

    /**
     * A short, deterministic human-readable rendering of this target, used by the
     * announcement renderer. Never localized, never randomized.
     */
    String describe();
}
