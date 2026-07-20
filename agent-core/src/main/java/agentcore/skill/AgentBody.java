package agentcore.skill;

/**
 * The thin engine port a {@link Skill} steers through (docs/M3_DESIGN.md D2/D3).
 *
 * <p>Every method is expressed in primitives and world/tile coordinates so the skill
 * state machines stay engine-free and unit-testable against a fake body, while the real
 * implementation ({@code mindustry.rl.SkillController}) wraps a live {@code Unit} and
 * core building. This is the small refinement over D3's "skills import mindustry": the
 * FSMs import nothing engine-specific; only the body wrapper does. The same skills can
 * therefore back the rl-server controller and the agent-plugin demo unchanged.
 *
 * <p>Contract: all reads reflect current engine state on the simulation thread; all
 * movement/mining calls take effect on the tick they are issued. No teleports and no
 * free items — {@link #transferCargoToCore()} routes through the game's legal transfer
 * path (docs/M3_DESIGN.md D4, open question 3).
 */
public interface AgentBody{

    // -- pose / steering ---------------------------------------------------

    float x();

    float y();

    /** Preferred speed magnitude in world units per tick (for progress estimates). */
    float speed();

    /** Straight-line distance from the unit to a world point. */
    float dst(float worldX, float worldY);

    /** Steer straight toward a world point this tick, with arrival deceleration. */
    void steerToward(float worldX, float worldY);

    /** Request no directed movement this tick (unit coasts to rest via drag). */
    void halt();

    // -- mining ------------------------------------------------------------

    /** Mining reach in world units. */
    float mineRange();

    /** Whether the tile carries ore this unit's mine tier can extract (distance ignored). */
    boolean mineableAt(int tileX, int tileY);

    /** World-space center X of a tile column. */
    float tileCenterX(int tileX);

    /** World-space center Y of a tile row. */
    float tileCenterY(int tileY);

    /** Begin mining the given tile (sets the engine mine target). */
    void setMineTile(int tileX, int tileY);

    /** Clear any active mine target. */
    void clearMineTile();

    boolean isMining();

    int cargoAmount();

    int cargoCapacity();

    // -- core delivery -----------------------------------------------------

    boolean hasCore();

    float coreX();

    float coreY();

    /** Range within which cargo may be transferred to the core, in world units. */
    float coreTransferRange();

    /**
     * Transfer the whole carried stack into the core via the game's legal transfer
     * path, clamped to core capacity. Returns the amount actually accepted (0 if the
     * core is full or nothing is carried). No items are created or destroyed.
     */
    int transferCargoToCore();

    // -- building ---------------------------------------------------------

    /** Builder reach in world units. */
    float buildRange();

    /** World-space center of a requested block plan. */
    float buildTargetX(String block, int tileX);

    /** World-space center of a requested block plan. */
    float buildTargetY(String block, int tileY);

    /** Classify the live footprint without changing it. */
    BuildTargetState buildTargetState(String block, int tileX, int tileY, int rotation);

    /** Enqueue one engine-owned build plan. Never places a block directly. */
    void enqueueBuild(String block, int tileX, int tileY, int rotation);

    /** Whether the matching plan still exists in the unit's ordered queue. */
    boolean hasBuildPlan(String block, int tileX, int tileY, int rotation);

    /** Current engine plan/construct progress in {@code [0,1]}. */
    float buildProgress(String block, int tileX, int tileY, int rotation);

    /** Whether the team core currently holds the full recipe for this block. */
    boolean hasBuildResources(String block);
}
