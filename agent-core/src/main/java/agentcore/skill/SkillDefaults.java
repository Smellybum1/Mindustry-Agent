package agentcore.skill;

/** Shared deterministic defaults used by skill state machines. */
public final class SkillDefaults{
    public static final float ARRIVAL_TOLERANCE = 8f;
    public static final long RETRY_DELAY_TICKS = 60L;

    private SkillDefaults(){ }
}
