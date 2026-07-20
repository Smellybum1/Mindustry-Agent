package agentcore.skill;

/**
 * Holds a world-space region for a fixed simulation-tick budget, selecting a target
 * deterministically while the engine owns weapon legality and projectile behavior.
 */
public final class DefendRegion implements Skill{
    private final float anchorX;
    private final float anchorY;
    private final float radius;
    private final long durationTicks;
    private long startTick = Long.MIN_VALUE;
    private int targetId = -1;
    private boolean complete;

    public DefendRegion(float anchorX, float anchorY, float radius, long durationTicks){
        this.anchorX = anchorX;
        this.anchorY = anchorY;
        this.radius = Math.max(0f, radius);
        this.durationTicks = Math.max(0L, durationTicks);
    }

    @Override public String type(){ return "DEFEND"; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        if(complete){
            body.halt();
            body.ceaseFire();
            return SkillResult.succeeded(SkillReason.DEFENDED);
        }
        if(startTick == Long.MIN_VALUE) startTick = tick;

        if(body.dst(anchorX, anchorY) > SkillDefaults.ARRIVAL_TOLERANCE){
            body.steerToward(anchorX, anchorY);
        }else{
            body.halt();
        }

        targetId = body.engageNearestEnemy(anchorX, anchorY, radius);
        long elapsed = Math.max(0L, tick - startTick);
        float progress = durationTicks == 0L ? 1f
            : Math.min(1f, (float)elapsed / durationTicks);
        if(elapsed >= durationTicks && targetId < 0){
            complete = true;
            body.ceaseFire();
            return SkillResult.succeeded(SkillReason.DEFENDED);
        }
        return SkillResult.running(SkillReason.DEFENDING, progress);
    }

    public int targetId(){ return targetId; }

    public long elapsed(long tick){
        return startTick == Long.MIN_VALUE ? 0L : Math.max(0L, tick - startTick);
    }

    public long durationTicks(){ return durationTicks; }
}
