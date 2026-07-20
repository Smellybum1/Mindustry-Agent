package agentcore.skill;

/**
 * Navigate into mine range of an ore tile and mine until a target cargo is reached
 * (docs/M3_DESIGN.md D4.2).
 *
 * <p>State machine:
 * <ol>
 *   <li>If the tile is not mineable for this unit's tier → {@code BLOCKED(INVALID_TARGET)}.</li>
 *   <li>Out of {@link AgentBody#mineRange()} → steer toward the tile (MOVING), mine target
 *       cleared.</li>
 *   <li>In range → set the mine tile and settle on it (MINING); the engine accrues cargo.</li>
 *   <li>Cargo reaches the target (or capacity) → clear the mine tile and DRAIN: hold until
 *       cargo has been stable for {@code drainTicks} ticks, so no engine-deferred mined
 *       items are still in flight (the mine→inventory transfer lands
 *       {@code Fx.itemTransfer.lifetime}=12 ticks late; see docs/ENGINE_NOTES.md and
 *       MinerComp). Then SUCCEED. This guarantees the carried amount equals the amount
 *       actually mined — the honesty ledger the smoke asserts on.</li>
 * </ol>
 *
 * <p>No free items: cargo only ever grows through the engine's own mining accrual.
 */
public final class MineResource implements Skill{
    /** Stable-cargo ticks required before success; must exceed the 12-tick deferred-add latency. */
    public static final int DEFAULT_DRAIN_TICKS = 14;
    public static final long DEFAULT_RETRY_DELAY = 120L;

    private final int tileX;
    private final int tileY;
    private final int targetAmount;
    private final int drainTicks;
    private final long retryDelay;

    private boolean draining = false;
    private int stableCargo = -1;
    private int stableTicks = 0;

    public MineResource(int tileX, int tileY, int targetAmount){
        this(tileX, tileY, targetAmount, DEFAULT_DRAIN_TICKS, DEFAULT_RETRY_DELAY);
    }

    public MineResource(int tileX, int tileY, int targetAmount, int drainTicks, long retryDelay){
        this.tileX = tileX;
        this.tileY = tileY;
        this.targetAmount = Math.max(1, targetAmount);
        this.drainTicks = Math.max(1, drainTicks);
        this.retryDelay = Math.max(0L, retryDelay);
    }

    @Override public String type(){ return "MINE"; }

    public int tileX(){ return tileX; }
    public int tileY(){ return tileY; }
    public int targetAmount(){ return targetAmount; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        if(!body.mineableAt(tileX, tileY)){
            body.clearMineTile();
            return SkillResult.blocked(SkillReason.INVALID_TARGET, tick + retryDelay);
        }

        int cargo = body.cargoAmount();
        int capacity = body.cargoCapacity();
        int target = Math.min(targetAmount, capacity);

        if(draining){
            if(cargo != stableCargo){
                stableCargo = cargo;
                stableTicks = 0;
            }else{
                stableTicks++;
            }
            body.halt();
            if(stableTicks >= drainTicks){
                SkillReason why = cargo >= capacity ? SkillReason.CARGO_FULL : SkillReason.TARGET_REACHED;
                return SkillResult.succeeded(why);
            }
            return SkillResult.running(SkillReason.MINING, 1f);
        }

        if(cargo >= target || cargo >= capacity){
            body.clearMineTile();
            body.halt();
            draining = true;
            stableCargo = cargo;
            stableTicks = 0;
            return SkillResult.running(SkillReason.MINING, 1f);
        }

        float cx = body.tileCenterX(tileX);
        float cy = body.tileCenterY(tileY);
        float progress = (float)cargo / target;

        if(body.dst(cx, cy) <= body.mineRange()){
            body.setMineTile(tileX, tileY);
            body.steerToward(cx, cy);
            return SkillResult.running(SkillReason.MINING, progress);
        }

        body.clearMineTile();
        body.steerToward(cx, cy);
        return SkillResult.running(SkillReason.MOVING, progress);
    }
}
