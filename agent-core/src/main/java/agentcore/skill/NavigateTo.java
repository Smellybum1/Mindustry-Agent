package agentcore.skill;

/**
 * Straight-line navigation to a world point (docs/M3_DESIGN.md D4.1).
 *
 * <p>Steers directly toward {@code (targetX, targetY)} each tick and SUCCEEDS once within
 * {@code tolerance}. Progress is {@code 1 - remaining/initial} distance. If the closest
 * approach does not improve by {@link #PROGRESS_EPSILON} for {@code stuckTicks} consecutive
 * ticks, the skill reports {@code BLOCKED(STUCK)} with a next-retry tick — the flat
 * bootstrap map has no obstacles, so this only fires on genuine wedging (D2: pathfinder
 * threads are stopped; flying units steer straight).
 */
public final class NavigateTo implements Skill{
    /** Distance (world units) the best approach must improve by to count as progress. */
    public static final float PROGRESS_EPSILON = 0.01f;
    public static final int DEFAULT_STUCK_TICKS = 180;
    public static final long DEFAULT_RETRY_DELAY = 60L;

    private final float targetX;
    private final float targetY;
    private final float tolerance;
    private final int stuckTicks;
    private final long retryDelay;

    private float initialDst = -1f;
    private float bestDst = Float.MAX_VALUE;
    private int sinceProgress = 0;

    public NavigateTo(float targetX, float targetY, float tolerance){
        this(targetX, targetY, tolerance, DEFAULT_STUCK_TICKS, DEFAULT_RETRY_DELAY);
    }

    public NavigateTo(float targetX, float targetY, float tolerance, int stuckTicks, long retryDelay){
        this.targetX = targetX;
        this.targetY = targetY;
        this.tolerance = Math.max(0f, tolerance);
        this.stuckTicks = Math.max(1, stuckTicks);
        this.retryDelay = Math.max(0L, retryDelay);
    }

    @Override public String type(){ return "NAVIGATE"; }

    public float targetX(){ return targetX; }
    public float targetY(){ return targetY; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        float d = body.dst(targetX, targetY);
        if(initialDst < 0f) initialDst = Math.max(d, 1e-3f);

        if(d <= tolerance){
            body.halt();
            return SkillResult.succeeded(SkillReason.ARRIVED);
        }

        if(d < bestDst - PROGRESS_EPSILON){
            bestDst = d;
            sinceProgress = 0;
        }else{
            sinceProgress++;
        }

        float progress = 1f - d / initialDst;
        if(sinceProgress >= stuckTicks){
            body.halt();
            return SkillResult.blocked(SkillReason.STUCK, tick + retryDelay, progress);
        }

        body.steerToward(targetX, targetY);
        return SkillResult.running(SkillReason.MOVING, progress);
    }
}
