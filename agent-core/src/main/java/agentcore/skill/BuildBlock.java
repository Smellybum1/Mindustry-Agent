package agentcore.skill;

/**
 * Build one block through the engine's builder-plan queue (docs/M4_DESIGN.md S1).
 *
 * <p>The skill never places a block or edits resources itself. It navigates into the
 * body's build range, enqueues one legal build plan, and observes the engine-owned plan
 * progress. A plan that makes no progress while the core lacks the recipe reports
 * {@code BLOCKED(RESOURCES_SHORT)}; a conflicting footprint reports
 * {@code BLOCKED(OCCUPIED)}; an unreachable build radius reports
 * {@code BLOCKED(OUT_OF_RANGE)}.
 */
public final class BuildBlock implements Skill{
    public static final float PROGRESS_EPSILON = 1e-5f;
    public static final int DEFAULT_APPROACH_STUCK_TICKS = 180;
    public static final int DEFAULT_RESOURCE_STALL_TICKS = 120;
    public static final long DEFAULT_RETRY_DELAY = 60L;

    private final String block;
    private final int tileX, tileY, rotation;
    private final int approachStuckTicks, resourceStallTicks;
    private final long retryDelay;
    private final boolean rebuild;

    private float bestDistance = Float.MAX_VALUE;
    private float bestProgress = 0f;
    private int approachWithoutProgress;
    private int buildWithoutProgress;
    private boolean enqueued;

    public BuildBlock(String block, int tileX, int tileY, int rotation){
        this(block, tileX, tileY, rotation, DEFAULT_APPROACH_STUCK_TICKS,
            DEFAULT_RESOURCE_STALL_TICKS, DEFAULT_RETRY_DELAY, false);
    }

    BuildBlock(RebuildSpec spec){
        this(spec.block(), spec.tileX(), spec.tileY(), spec.rotation(),
            DEFAULT_APPROACH_STUCK_TICKS, DEFAULT_RESOURCE_STALL_TICKS,
            DEFAULT_RETRY_DELAY, true);
    }

    BuildBlock(String block, int tileX, int tileY, int rotation,
               int approachStuckTicks, int resourceStallTicks, long retryDelay){
        this(block, tileX, tileY, rotation, approachStuckTicks, resourceStallTicks,
            retryDelay, false);
    }

    private BuildBlock(String block, int tileX, int tileY, int rotation,
               int approachStuckTicks, int resourceStallTicks, long retryDelay,
               boolean rebuild){
        this.block = block;
        this.tileX = tileX;
        this.tileY = tileY;
        this.rotation = rotation;
        this.approachStuckTicks = Math.max(1, approachStuckTicks);
        this.resourceStallTicks = Math.max(1, resourceStallTicks);
        this.retryDelay = Math.max(0L, retryDelay);
        this.rebuild = rebuild;
    }

    @Override public String type(){ return "BUILD"; }

    public String block(){ return block; }
    public int tileX(){ return tileX; }
    public int tileY(){ return tileY; }
    public int rotation(){ return rotation; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        BuildTargetState state = body.buildTargetState(block, tileX, tileY, rotation);
        if(state == BuildTargetState.COMPLETE){
            body.halt();
            return SkillResult.succeeded(SkillReason.BUILT);
        }
        if(state == BuildTargetState.OCCUPIED){
            body.halt();
            return SkillResult.blocked(SkillReason.OCCUPIED, tick + retryDelay);
        }

        float range = body.buildRange();
        float targetX = body.buildTargetX(block, tileX);
        float targetY = body.buildTargetY(block, tileY);
        float distance = body.dst(targetX, targetY);
        if(range <= 0f || distance > range){
            if(distance < bestDistance - NavigateTo.PROGRESS_EPSILON){
                bestDistance = distance;
                approachWithoutProgress = 0;
            }else{
                approachWithoutProgress++;
            }
            if(range <= 0f || approachWithoutProgress >= approachStuckTicks){
                body.halt();
                return SkillResult.blocked(SkillReason.OUT_OF_RANGE, tick + retryDelay);
            }
            body.steerToward(targetX, targetY);
            return SkillResult.running(SkillReason.MOVING, 0f);
        }

        body.halt();
        if(!enqueued){
            if(rebuild){
                body.enqueueRebuild(block, tileX, tileY, rotation);
            }else{
                body.enqueueBuild(block, tileX, tileY, rotation);
            }
            enqueued = true;
            return SkillResult.running(SkillReason.BUILDING, 0f);
        }

        if(!body.hasBuildPlan(block, tileX, tileY, rotation)){
            //Completion was checked first; disappearance now means external removal or
            //engine validation failure, not success.
            return SkillResult.failed(SkillReason.PLAN_REMOVED);
        }

        float progress = body.buildProgress(block, tileX, tileY, rotation);
        if(progress > bestProgress + PROGRESS_EPSILON){
            bestProgress = progress;
            buildWithoutProgress = 0;
        }else{
            buildWithoutProgress++;
        }

        if(buildWithoutProgress >= resourceStallTicks && !body.hasBuildResources(block)){
            return SkillResult.blocked(
                SkillReason.RESOURCES_SHORT, tick + retryDelay, progress);
        }

        return SkillResult.running(SkillReason.BUILDING, progress);
    }
}
