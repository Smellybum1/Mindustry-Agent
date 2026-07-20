package agentcore.skill;

/**
 * Navigate to the core and hand the carried cargo over the legal transfer path
 * (docs/M3_DESIGN.md D4.3).
 *
 * <p>Out of {@link AgentBody#coreTransferRange()} → steer toward the core. In range →
 * {@link AgentBody#transferCargoToCore()} (clamped to core capacity; no free items).
 * SUCCEEDS once cargo is empty; reports {@code BLOCKED(CORE_FULL)} if the core cannot
 * accept and {@code BLOCKED(NO_CORE)} if no core exists.
 */
public final class DeliverToCore implements Skill{
    public static final long DEFAULT_RETRY_DELAY = 60L;

    private final long retryDelay;
    private int startCargo = -1;

    public DeliverToCore(){
        this(DEFAULT_RETRY_DELAY);
    }

    public DeliverToCore(long retryDelay){
        this.retryDelay = Math.max(0L, retryDelay);
    }

    @Override public String type(){ return "DELIVER_CORE"; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        if(!body.hasCore()){
            return SkillResult.blocked(SkillReason.NO_CORE, tick + retryDelay);
        }

        int cargo = body.cargoAmount();
        if(cargo <= 0){
            return SkillResult.succeeded(SkillReason.DELIVERED);
        }
        if(startCargo < 0) startCargo = cargo;

        float d = body.dst(body.coreX(), body.coreY());
        if(d > body.coreTransferRange()){
            body.steerToward(body.coreX(), body.coreY());
            float progress = 1f - (float)cargo / startCargo;
            return SkillResult.running(SkillReason.MOVING, progress);
        }

        int moved = body.transferCargoToCore();
        if(body.cargoAmount() <= 0){
            return SkillResult.succeeded(SkillReason.DELIVERED);
        }
        if(moved <= 0){
            return SkillResult.blocked(SkillReason.CORE_FULL, tick + retryDelay,
                1f - (float)body.cargoAmount() / startCargo);
        }
        return SkillResult.running(SkillReason.DELIVERING, 1f - (float)body.cargoAmount() / startCargo);
    }
}
