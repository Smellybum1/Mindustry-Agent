package agentcore.skill;

/**
 * Hold position for a fixed number of ticks (docs/M3_DESIGN.md D4.4).
 *
 * <p>The deadline is captured on the first tick relative to the current simulation tick,
 * so the skill is position- and history-independent. SUCCEEDS once the budget elapses.
 */
public final class Wait implements Skill{
    private final long ticks;
    private long endTick = -1L;

    public Wait(long ticks){
        this.ticks = Math.max(0L, ticks);
    }

    @Override public String type(){ return "WAIT"; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        if(endTick < 0L) endTick = tick + ticks;
        body.halt();
        if(tick >= endTick){
            return SkillResult.succeeded(SkillReason.WAIT_ELAPSED);
        }
        long remaining = endTick - tick;
        float progress = ticks == 0 ? 1f : 1f - (float)remaining / ticks;
        return SkillResult.running(SkillReason.WAITING, progress);
    }
}
