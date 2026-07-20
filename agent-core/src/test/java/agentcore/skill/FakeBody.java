package agentcore.skill;

import java.util.*;

/**
 * A deterministic, engine-free {@link AgentBody} for skill state-machine tests.
 *
 * <p>Models a point mass that steps toward its steer target at a fixed speed, a set of
 * mineable tiles, an accrual model where mining a set tile adds cargo every
 * {@code ticksPerItem} advance calls (mirroring the engine cadence without content init),
 * and a core sink with finite capacity. Call {@link #advance()} between skill ticks to
 * move the world forward, exactly as the sim thread would between {@code updateUnit}s.
 */
final class FakeBody implements AgentBody{
    static final int TILESIZE = 8;

    float px, py;
    float steerX, steerY;
    boolean steering = false;
    float speed = 3f;

    float mineRange = 70f;
    float coreTransferRange = 220f;
    boolean hasCore = true;
    float coreX = 0f, coreY = 0f;
    int coreItems = 0;
    int coreCapacity = 4000;

    final Set<Long> mineable = new HashSet<>();
    Integer mineTileX = null, mineTileY = null;

    int cargo = 0;
    int capacity = 30;
    String cargoItem = "copper";

    float supplyRange = 220f;
    boolean supplyTargetValid = true;
    int supplyX = 8, supplyY = 8;
    int supplyCapacity = 30;
    int supplyStock = 0;
    int supplyMultiplier = 2;

    // accrual model
    int ticksPerItem = 10;
    int mineAccumulator = 0;

    float buildRange = 80f;
    BuildTargetState buildState = BuildTargetState.PLACEABLE;
    boolean buildPlan;
    boolean buildResources = true;
    boolean advanceBuild = true;
    float buildProgress;
    float buildRate = 0.02f;
    String buildBlock;
    int buildX, buildY, buildRotation;
    boolean rebuildPlan;
    final List<RebuildSpec> broken = new ArrayList<>();
    final List<FakeEnemy> enemies = new ArrayList<>();
    int targetId = -1;
    boolean firing;
    boolean buildPlansCancelled;

    FakeBody(float x, float y){ this.px = x; this.py = y; }

    static long key(int x, int y){ return (((long)x) << 32) ^ (y & 0xffffffffL); }

    void addMineable(int x, int y){ mineable.add(key(x, y)); }

    /** Advance the fake world one tick: apply steering and mining accrual. */
    void advance(){
        if(steering){
            float dx = steerX - px, dy = steerY - py;
            float d = (float)Math.sqrt(dx * dx + dy * dy);
            if(d <= speed){
                px = steerX;
                py = steerY;
            }else{
                px += dx / d * speed;
                py += dy / d * speed;
            }
        }
        if(mineTileX != null && cargo < capacity){
            mineAccumulator++;
            if(mineAccumulator >= ticksPerItem){
                mineAccumulator = 0;
                cargo++;
            }
        }
        if(buildPlan && advanceBuild && buildResources){
            buildState = BuildTargetState.CONSTRUCTING;
            buildProgress = Math.min(1f, buildProgress + buildRate);
            if(buildProgress >= 1f){
                buildPlan = false;
                buildState = BuildTargetState.COMPLETE;
                if(rebuildPlan){
                    broken.removeIf(spec -> spec.block().equals(buildBlock)
                        && spec.tileX() == buildX && spec.tileY() == buildY
                        && spec.rotation() == buildRotation);
                    rebuildPlan = false;
                }
            }
        }
        steering = false;
    }

    @Override public float x(){ return px; }
    @Override public float y(){ return py; }
    @Override public float speed(){ return speed; }

    @Override public float dst(float wx, float wy){
        float dx = wx - px, dy = wy - py;
        return (float)Math.sqrt(dx * dx + dy * dy);
    }

    @Override public void steerToward(float wx, float wy){
        steerX = wx; steerY = wy; steering = true;
    }

    @Override public void halt(){ steering = false; }

    @Override public float mineRange(){ return mineRange; }

    @Override public boolean mineableAt(int tileX, int tileY){
        return mineable.contains(key(tileX, tileY));
    }

    @Override public float tileCenterX(int tileX){ return tileX * TILESIZE + TILESIZE / 2f; }
    @Override public float tileCenterY(int tileY){ return tileY * TILESIZE + TILESIZE / 2f; }

    @Override public void setMineTile(int tileX, int tileY){
        if(mineTileX == null || mineTileX != tileX || mineTileY != tileY){
            mineAccumulator = 0;
        }
        mineTileX = tileX; mineTileY = tileY;
    }

    @Override public void clearMineTile(){ mineTileX = null; mineTileY = null; }

    @Override public boolean isMining(){ return mineTileX != null; }

    @Override public int cargoAmount(){ return cargo; }
    @Override public int cargoCapacity(){ return capacity; }
    @Override public String cargoItem(){ return cargo <= 0 ? "" : cargoItem; }

    @Override public boolean hasCore(){ return hasCore; }
    @Override public float coreX(){ return coreX; }
    @Override public float coreY(){ return coreY; }
    @Override public float coreTransferRange(){ return coreTransferRange; }

    @Override public int transferCargoToCore(){
        if(cargo <= 0) return 0;
        int accepted = Math.min(cargo, coreCapacity - coreItems);
        cargo -= accepted;
        coreItems += accepted;
        return accepted;
    }

    @Override public float buildRange(){ return buildRange; }
    @Override public float buildTargetX(String block, int tileX){ return tileCenterX(tileX); }
    @Override public float buildTargetY(String block, int tileY){ return tileCenterY(tileY); }
    @Override public BuildTargetState buildTargetState(String block, int tileX, int tileY, int rotation){
        if(buildState == BuildTargetState.OCCUPIED) return buildState;
        if(buildBlock != null && block.equals(buildBlock) && tileX == buildX && tileY == buildY
            && rotation == buildRotation) return buildState;
        return BuildTargetState.PLACEABLE;
    }
    @Override public void enqueueBuild(String block, int tileX, int tileY, int rotation){
        startBuild(block, tileX, tileY, rotation, false);
    }
    private void startBuild(String block, int tileX, int tileY, int rotation, boolean rebuild){
        buildPlan = true;
        rebuildPlan = rebuild;
        buildProgress = 0f;
        buildBlock = block;
        buildX = tileX;
        buildY = tileY;
        buildRotation = rotation;
    }
    @Override public boolean hasBuildPlan(String block, int tileX, int tileY, int rotation){
        return buildPlan && block.equals(buildBlock) && tileX == buildX && tileY == buildY
            && rotation == buildRotation;
    }
    @Override public float buildProgress(String block, int tileX, int tileY, int rotation){
        return buildProgress;
    }
    @Override public boolean hasBuildResources(String block){ return buildResources; }

    @Override public float supplyRange(){ return supplyRange; }
    @Override public float supplyTargetX(int tileX, int tileY){ return tileCenterX(tileX); }
    @Override public float supplyTargetY(int tileX, int tileY){ return tileCenterY(tileY); }
    @Override public SupplyTargetState supplyTargetState(String item, int tileX, int tileY){
        if(!supplyTargetValid || tileX != supplyX || tileY != supplyY){
            return SupplyTargetState.INVALID;
        }
        return supplyCapacity > 0 ? SupplyTargetState.ACCEPTING : SupplyTargetState.FULL;
    }
    @Override public int supplyTargetCapacity(String item, int tileX, int tileY){
        return supplyTargetState(item, tileX, tileY) == SupplyTargetState.ACCEPTING
            ? supplyCapacity : 0;
    }
    @Override public int supplyTargetStock(String item, int tileX, int tileY){
        return supplyStock;
    }
    @Override public int coreItemAmount(String item){ return coreItems; }
    @Override public int withdrawFromCore(String item, int amount){
        int moved = Math.min(Math.min(coreItems, amount), capacity - cargo);
        if(moved > 0){
            coreItems -= moved;
            cargo += moved;
            cargoItem = item;
        }
        return moved;
    }
    @Override public int transferCargoToBuilding(String item, int tileX, int tileY, int amount){
        if(!item.equals(cargoItem)) return 0;
        int moved = Math.min(Math.min(cargo, amount), supplyTargetCapacity(item, tileX, tileY));
        cargo -= moved;
        supplyCapacity -= moved;
        supplyStock += moved * supplyMultiplier;
        return moved;
    }

    @Override public List<RebuildSpec> brokenBlocksInRegion(int x1, int y1, int x2, int y2){
        List<RebuildSpec> result = new ArrayList<>();
        for(RebuildSpec spec : broken){
            if(spec.tileX() >= x1 && spec.tileX() <= x2
                && spec.tileY() >= y1 && spec.tileY() <= y2){
                result.add(spec);
            }
        }
        return List.copyOf(result);
    }
    @Override public void enqueueRebuild(String block, int tileX, int tileY, int rotation){
        for(RebuildSpec spec : broken){
            if(spec.block().equals(block) && spec.tileX() == tileX && spec.tileY() == tileY
                && spec.rotation() == rotation){
                startBuild(block, tileX, tileY, rotation, true);
                return;
            }
        }
    }

    @Override public int engageNearestEnemy(float anchorX, float anchorY, float radius){
        FakeEnemy best = null;
        float bestDst2 = Float.MAX_VALUE;
        float radius2 = radius * radius;
        for(FakeEnemy enemy : enemies){
            float dx = enemy.x - anchorX, dy = enemy.y - anchorY;
            float dst2 = dx * dx + dy * dy;
            if(dst2 > radius2) continue;
            if(best == null || Float.compare(dst2, bestDst2) < 0
                || (Float.compare(dst2, bestDst2) == 0 && enemy.id < best.id)){
                best = enemy;
                bestDst2 = dst2;
            }
        }
        targetId = best == null ? -1 : best.id;
        firing = best != null;
        return targetId;
    }

    @Override public void ceaseFire(){ targetId = -1; firing = false; }

    @Override public void cancelBuildPlans(){
        buildPlan = false;
        rebuildPlan = false;
        buildPlansCancelled = true;
    }

    static final class FakeEnemy{
        final int id;
        final float x, y;

        FakeEnemy(int id, float x, float y){ this.id = id; this.x = x; this.y = y; }
    }
}
