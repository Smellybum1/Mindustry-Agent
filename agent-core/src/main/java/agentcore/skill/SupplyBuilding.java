package agentcore.skill;

/**
 * Withdraw an item from the team core and carry it to a team building.
 *
 * <p>Both item movements are delegated to {@link AgentBody}; the live adapter uses
 * the engine's {@code Call.takeItems} and {@code Call.transferItemTo} paths. Requested
 * amounts larger than the target's capacity succeed when the target refuses further
 * stock, while {@link #delivered()} reports the actual item count transferred.
 */
public final class SupplyBuilding implements Skill{
    public static final long DEFAULT_RETRY_DELAY = 60L;

    private final String item;
    private final int tileX, tileY, amount;
    private final long retryDelay;

    private int delivered;
    private int targetStockBefore = -1;
    private int targetStock;

    public SupplyBuilding(String item, int tileX, int tileY, int amount){
        this(item, tileX, tileY, amount, DEFAULT_RETRY_DELAY);
    }

    SupplyBuilding(String item, int tileX, int tileY, int amount, long retryDelay){
        if(item == null || item.isBlank()) throw new IllegalArgumentException("item is blank");
        if(amount <= 0) throw new IllegalArgumentException("amount must be positive");
        this.item = item;
        this.tileX = tileX;
        this.tileY = tileY;
        this.amount = amount;
        this.retryDelay = Math.max(0L, retryDelay);
    }

    @Override public String type(){ return "SUPPLY"; }

    public String item(){ return item; }
    public int tileX(){ return tileX; }
    public int tileY(){ return tileY; }
    public int requested(){ return amount; }
    public int delivered(){ return delivered; }
    /** Initial native target stock, emitted in observations for the supply ledger. */
    public int targetStockBefore(){ return Math.max(0, targetStockBefore); }
    /** Current native target stock, consumed by validation and core-short recovery policy. */
    public int targetStock(){ return targetStock; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        SupplyTargetState state = body.supplyTargetState(item, tileX, tileY);
        if(state == SupplyTargetState.INVALID){
            body.halt();
            return SkillResult.blocked(SkillReason.INVALID_TARGET, tick + retryDelay,
                progress());
        }
        updateTargetStock(body);
        if(delivered >= amount || state == SupplyTargetState.FULL){
            body.halt();
            return SkillResult.succeeded(SkillReason.SUPPLIED, progress());
        }

        int cargo = body.cargoAmount();
        if(cargo > 0 && !item.equals(body.cargoItem())){
            body.halt();
            return SkillResult.blocked(SkillReason.CARGO_MISMATCH, tick + retryDelay,
                progress());
        }

        if(cargo > 0){
            float tx = body.supplyTargetX(tileX, tileY), ty = body.supplyTargetY(tileX, tileY);
            if(body.dst(tx, ty) > body.supplyRange()){
                body.steerToward(tx, ty);
                return SkillResult.running(SkillReason.MOVING, progress());
            }
            body.halt();
            int moved = body.transferCargoToBuilding(
                item, tileX, tileY, Math.min(cargo, amount - delivered));
            delivered += moved;
            updateTargetStock(body);
            if(delivered >= amount){
                return SkillResult.succeeded(SkillReason.SUPPLIED);
            }
            if(moved <= 0 || body.supplyTargetState(item, tileX, tileY) == SupplyTargetState.FULL){
                return SkillResult.succeeded(SkillReason.SUPPLIED, progress());
            }
            return SkillResult.running(SkillReason.SUPPLYING, progress());
        }

        if(!body.hasCore()){
            body.halt();
            return SkillResult.blocked(SkillReason.NO_CORE, tick + retryDelay, progress());
        }
        if(body.coreItemAmount(item) <= 0){
            body.halt();
            return SkillResult.blocked(SkillReason.CORE_SHORT, tick + retryDelay, progress());
        }

        float cx = body.coreX(), cy = body.coreY();
        if(body.dst(cx, cy) > body.supplyRange()){
            body.steerToward(cx, cy);
            return SkillResult.running(SkillReason.MOVING, progress());
        }
        body.halt();
        int wanted = Math.min(amount - delivered, body.cargoCapacity());
        wanted = Math.min(wanted, body.supplyTargetCapacity(item, tileX, tileY));
        int moved = body.withdrawFromCore(item, wanted);
        if(moved <= 0){
            return SkillResult.blocked(SkillReason.CORE_SHORT, tick + retryDelay, progress());
        }
        return SkillResult.running(SkillReason.WITHDRAWING, progress());
    }

    private void updateTargetStock(AgentBody body){
        targetStock = body.supplyTargetStock(item, tileX, tileY);
        if(targetStockBefore < 0) targetStockBefore = targetStock;
    }

    private float progress(){
        return delivered / (float)amount;
    }
}
