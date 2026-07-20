package agentcore.skill;

import java.util.HashSet;
import java.util.Set;

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
        buildPlan = true;
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
}
