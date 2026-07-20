package mindustry.rl;

import agentcore.skill.*;
import arc.math.geom.*;
import mindustry.entities.units.*;
import mindustry.game.Teams.*;
import mindustry.gen.*;
import mindustry.type.*;
import mindustry.world.*;
import mindustry.world.blocks.ConstructBlock.*;
import mindustry.world.blocks.defense.turrets.*;

import java.util.*;

import static mindustry.Vars.*;

/**
 * The per-agent unit controller (docs/M3_DESIGN.md D2). Extends the engine's
 * {@link AIController} so it is driven each tick by {@code Groups.unit.update()}
 * ({@code UnitComp.update():840}), and implements {@link AgentBody} so the engine-free
 * {@link Skill} state machines can steer the live unit.
 *
 * <p>{@link #updateUnit()} runs only the active skill — it deliberately does not call
 * {@code super.updateUnit()} (no vanilla targeting/weapons/pathfinding). Movement is
 * straight-line via {@link AIController#moveTo}; the async {@code ControlPathfinder} is
 * never consulted (its threads are stopped in deterministic mode), so a flying unit on the
 * flat bootstrap map moves deterministically (docs/ENGINE_NOTES.md §5.3).
 *
 * <p>All state reads/writes happen on the simulation thread. No teleports and no free
 * items: mining accrues through the engine's {@code MinerComp}; delivery/supply route
 * through {@code Call.transferItemTo}, and core withdrawal through {@code Call.takeItems}
 * (docs/M3_DESIGN.md D4; docs/M4_DESIGN.md S3).
 */
public final class SkillController extends AIController implements AgentBody{
    private static final Vec2 steer = new Vec2();

    private final int agentIndex;
    private Skill active;
    private SkillResult last = SkillResult.ready();

    public SkillController(int agentIndex){
        this.agentIndex = agentIndex;
    }

    /** Suppress the superclass RNG-seeded target timers (we never target). Keeps the
     * global {@code Mathf.rand} stream untouched by controller construction. */
    @Override protected void resetTimers(){ }

    public int agentIndex(){ return agentIndex; }

    public void setSkill(Skill skill){
        this.active = skill;
        this.last = SkillResult.running(SkillReason.NONE, 0f);
    }

    public void clearSkill(){
        this.active = null;
        this.last = SkillResult.ready();
    }

    public Skill activeSkill(){ return active; }

    public String activeType(){ return active == null ? "" : active.type(); }

    public SkillResult lastResult(){ return last; }

    @Override
    public void updateUnit(){
        if(unit == null || unit.dead()) return;
        if(active != null){
            last = active.tick(this, (long)state.tick);
        }
    }

    // ------------------------------------------------------------ AgentBody

    @Override public float x(){ return unit.x; }
    @Override public float y(){ return unit.y; }
    @Override public float speed(){ return prefSpeed(); }
    @Override public float dst(float wx, float wy){ return unit.dst(wx, wy); }

    @Override public void steerToward(float wx, float wy){
        //engine arrival steering (decelerates near target); no pathfinder consulted
        moveTo(steer.set(wx, wy), 0f, 30f, false, null, true);
    }

    @Override public void halt(){
        //issue no movement command; the unit coasts to rest via drag (deterministic)
    }

    @Override public float mineRange(){ return unit.type.mineRange; }

    @Override public boolean mineableAt(int tileX, int tileY){
        Tile t = world.tile(tileX, tileY);
        return t != null && ((Minerc)unit).validMine(t, false);
    }

    @Override public float tileCenterX(int tileX){ return tileX * tilesize + tilesize / 2f; }
    @Override public float tileCenterY(int tileY){ return tileY * tilesize + tilesize / 2f; }

    @Override public void setMineTile(int tileX, int tileY){
        ((Minerc)unit).mineTile(world.tile(tileX, tileY));
    }

    @Override public void clearMineTile(){ ((Minerc)unit).mineTile(null); }

    @Override public boolean isMining(){ return ((Minerc)unit).mining(); }

    @Override public int cargoAmount(){ return ((Itemsc)unit).stack().amount; }

    @Override public int cargoCapacity(){ return unit.type.itemCapacity; }

    @Override public String cargoItem(){
        Item item = ((Itemsc)unit).item();
        return item == null ? "" : item.name;
    }

    @Override public boolean hasCore(){ return core() != null; }

    @Override public float coreX(){ Building c = core(); return c == null ? unit.x : c.x; }
    @Override public float coreY(){ Building c = core(); return c == null ? unit.y : c.y; }

    @Override public float coreTransferRange(){ return mineTransferRange; }

    @Override
    public int transferCargoToCore(){
        Building c = core();
        Itemsc it = (Itemsc)unit;
        mindustry.type.Item item = it.item();
        int amount = it.stack().amount;
        if(c == null || item == null || amount <= 0) return 0;
        int accepted = c.acceptStack(item, amount, unit);
        if(accepted > 0){
            //exact engine transfer path used by MinerComp: removes from unit, adds to core
            Call.transferItemTo(unit, item, accepted, unit.x, unit.y, c);
        }
        return accepted;
    }

    @Override public float buildRange(){ return unit.type.buildRange; }

    @Override public float buildTargetX(String block, int tileX){
        Block b = block(block);
        return tileX * tilesize + (b == null ? tilesize / 2f : b.offset);
    }

    @Override public float buildTargetY(String block, int tileY){
        Block b = block(block);
        return tileY * tilesize + (b == null ? tilesize / 2f : b.offset);
    }

    @Override
    public BuildTargetState buildTargetState(String block, int tileX, int tileY, int rotation){
        Block requested = block(block);
        Tile tile = world.tile(tileX, tileY);
        if(requested == null || tile == null) return BuildTargetState.OCCUPIED;

        if(tile.build instanceof ConstructBuild construct){
            return construct.team == unit.team && construct.current == requested
                ? BuildTargetState.CONSTRUCTING : BuildTargetState.OCCUPIED;
        }
        if(tile.block() == requested && tile.team() == unit.team){
            return BuildTargetState.COMPLETE;
        }
        return Build.validPlaceIgnoreUnits(
            requested, unit.team, tileX, tileY, rotation, true, true)
            ? BuildTargetState.PLACEABLE : BuildTargetState.OCCUPIED;
    }

    @Override
    public void enqueueBuild(String block, int tileX, int tileY, int rotation){
        Block requested = block(block);
        if(requested != null){
            unit.addBuild(new BuildPlan(tileX, tileY, rotation, requested));
        }
    }

    @Override
    public boolean hasBuildPlan(String block, int tileX, int tileY, int rotation){
        Block requested = block(block);
        if(requested == null) return false;
        for(BuildPlan plan : unit.plans()){
            if(!plan.breaking && plan.block == requested && plan.x == tileX && plan.y == tileY
                && plan.rotation == requested.planRotation(rotation)) return true;
        }
        return false;
    }

    @Override
    public float buildProgress(String block, int tileX, int tileY, int rotation){
        Block requested = block(block);
        if(requested == null) return 0f;
        for(BuildPlan plan : unit.plans()){
            if(!plan.breaking && plan.block == requested && plan.x == tileX && plan.y == tileY){
                return plan.progress;
            }
        }
        Tile tile = world.tile(tileX, tileY);
        if(tile != null && tile.build instanceof ConstructBuild construct
            && construct.current == requested && construct.team == unit.team){
            return construct.progress;
        }
        return 0f;
    }

    @Override
    public boolean hasBuildResources(String block){
        Block requested = block(block);
        Building c = core();
        if(requested == null || c == null || c.items == null) return false;
        for(ItemStack requirement : requested.requirements){
            int amount = Math.round(requirement.amount * state.rules.buildCostMultiplier);
            if(c.items.get(requirement.item) < amount) return false;
        }
        return true;
    }

    @Override public float supplyRange(){ return itemTransferRange; }

    @Override public float supplyTargetX(int tileX, int tileY){
        Building target = building(tileX, tileY);
        return target == null ? tileCenterX(tileX) : target.x;
    }

    @Override public float supplyTargetY(int tileX, int tileY){
        Building target = building(tileX, tileY);
        return target == null ? tileCenterY(tileY) : target.y;
    }

    @Override
    public SupplyTargetState supplyTargetState(String item, int tileX, int tileY){
        Building target = building(tileX, tileY);
        Item requested = content.item(item);
        if(target == null || requested == null || target.team != unit.team
            || target.items == null || !target.interactable(unit.team())){
            return SupplyTargetState.INVALID;
        }
        if(target.block instanceof ItemTurret turret && !turret.ammoTypes.containsKey(requested)){
            return SupplyTargetState.INVALID;
        }
        return target.acceptStack(requested, 1, unit) > 0
            ? SupplyTargetState.ACCEPTING : SupplyTargetState.FULL;
    }

    @Override
    public int supplyTargetCapacity(String item, int tileX, int tileY){
        Building target = building(tileX, tileY);
        Item requested = content.item(item);
        if(target == null || requested == null || target.team != unit.team || target.items == null
            || !target.interactable(unit.team())){
            return 0;
        }
        if(target.block instanceof ItemTurret turret && !turret.ammoTypes.containsKey(requested)){
            return 0;
        }
        return target.acceptStack(requested, Integer.MAX_VALUE, unit);
    }

    @Override
    public int supplyTargetStock(String item, int tileX, int tileY){
        Building target = building(tileX, tileY);
        Item requested = content.item(item);
        if(target == null || requested == null || target.items == null) return 0;
        if(target instanceof Turret.TurretBuild turret) return turret.totalAmmo;
        return target.items.get(requested);
    }

    @Override
    public int coreItemAmount(String item){
        Building c = core();
        Item requested = content.item(item);
        return c == null || requested == null || c.items == null ? 0 : c.items.get(requested);
    }

    @Override
    public int withdrawFromCore(String item, int amount){
        Building c = core();
        Item requested = content.item(item);
        if(c == null || requested == null || amount <= 0 || c.team != unit.team
            || !c.interactable(unit.team()) || !unit.within(c, itemTransferRange)){
            return 0;
        }
        int before = ((Itemsc)unit).stack().amount;
        Call.takeItems(c, requested, amount, unit);
        return ((Itemsc)unit).stack().amount - before;
    }

    @Override
    public int transferCargoToBuilding(String item, int tileX, int tileY, int amount){
        Building target = building(tileX, tileY);
        Item requested = content.item(item);
        Itemsc items = (Itemsc)unit;
        if(target == null || requested == null || amount <= 0 || items.item() != requested
            || target.team != unit.team || target.items == null || !target.interactable(unit.team())
            || !unit.within(target, itemTransferRange)){
            return 0;
        }
        int accepted = target.acceptStack(requested, Math.min(amount, items.stack().amount), unit);
        if(accepted > 0){
            Call.transferItemTo(unit, requested, accepted, unit.x, unit.y, target);
        }
        return accepted;
    }

    @Override
    public List<RebuildSpec> brokenBlocksInRegion(int x1, int y1, int x2, int y2){
        ArrayList<RebuildSpec> result = new ArrayList<>();
        var plans = unit.team.data().plans;
        for(int i = 0; i < plans.size; i++){
            BlockPlan plan = plans.get(i);
            if(!plan.removed && plan.x >= x1 && plan.x <= x2 && plan.y >= y1 && plan.y <= y2){
                result.add(new RebuildSpec(plan.block.name, plan.x, plan.y, plan.rotation));
            }
        }
        return List.copyOf(result);
    }

    @Override
    public void enqueueRebuild(String block, int tileX, int tileY, int rotation){
        Block requested = block(block);
        if(requested == null) return;
        var plans = unit.team.data().plans;
        for(int i = 0; i < plans.size; i++){
            BlockPlan plan = plans.get(i);
            if(!plan.removed && plan.block == requested && plan.x == tileX && plan.y == tileY
                && plan.rotation == rotation){
                unit.addBuild(new BuildPlan(plan.x, plan.y, plan.rotation, plan.block, plan.config));
                return;
            }
        }
    }

    private Block block(String name){
        return content.block(name);
    }

    private Building core(){
        return unit.team().core();
    }

    private Building building(int tileX, int tileY){
        Tile tile = world.tile(tileX, tileY);
        return tile == null ? null : tile.build;
    }

}
