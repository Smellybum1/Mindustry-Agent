package agentcore.skill;

import agentcore.SkillStatus;

/**
 * Immutable outcome of one {@link Skill#tick} (docs/M3_DESIGN.md D3).
 *
 * <p>Carries the typed {@link SkillStatus}, a machine-readable {@link SkillReason}, a
 * {@code progress} estimate in {@code [0,1]}, and a {@code nextRetryTick} (the earliest
 * sim tick at which a {@code BLOCKED} skill is worth retrying, or {@code -1} when not
 * applicable). All fields are deterministic functions of engine state — no wall clock.
 *
 * @param status        typed lifecycle status
 * @param reason        machine-readable reason code
 * @param progress      completion estimate, clamped to {@code [0,1]}
 * @param nextRetryTick earliest retry tick for a {@code BLOCKED} result, else {@code -1}
 */
public record SkillResult(SkillStatus status, SkillReason reason, float progress, long nextRetryTick){

    public SkillResult{
        if(reason == null) reason = SkillReason.NONE;
        progress = progress < 0f ? 0f : (progress > 1f ? 1f : progress);
    }

    public static SkillResult ready(){
        return new SkillResult(SkillStatus.READY, SkillReason.NONE, 0f, -1L);
    }

    public static SkillResult running(SkillReason reason, float progress){
        return new SkillResult(SkillStatus.RUNNING, reason, progress, -1L);
    }

    public static SkillResult succeeded(SkillReason reason){
        return new SkillResult(SkillStatus.SUCCEEDED, reason, 1f, -1L);
    }

    public static SkillResult blocked(SkillReason reason, long nextRetryTick){
        return new SkillResult(SkillStatus.BLOCKED, reason, 0f, nextRetryTick);
    }

    public static SkillResult blocked(SkillReason reason, long nextRetryTick, float progress){
        return new SkillResult(SkillStatus.BLOCKED, reason, progress, nextRetryTick);
    }

    public static SkillResult failed(SkillReason reason){
        return new SkillResult(SkillStatus.FAILED, reason, 0f, -1L);
    }

    public static SkillResult cancelled(){
        return new SkillResult(SkillStatus.CANCELLED, SkillReason.CANCELLED, 0f, -1L);
    }

    public boolean terminal(){
        return status == SkillStatus.SUCCEEDED || status == SkillStatus.FAILED
            || status == SkillStatus.CANCELLED;
    }
}
