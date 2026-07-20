package agentcore.skill;

/**
 * A deterministic low-level behaviour executed one tick at a time (docs/M3_DESIGN.md D3/D4).
 *
 * <p>A skill is a pure state machine over an {@link AgentBody}: given the body and the
 * current simulation tick it advances its internal state and returns a {@link SkillResult}.
 * Skills never read wall-clock time and never iterate unordered collections, so a fixed
 * body trajectory yields a fixed result sequence (determinism, docs/ENGINE_NOTES.md §6).
 *
 * <p>The M3/M4 set includes {@link NavigateTo}, {@link MineResource},
 * {@link DeliverToCore}, {@link Wait}, {@link BuildBlock}, and
 * {@link ExecuteSchematic}, {@link SupplyBuilding}, {@link RebuildRegion},
 * {@link DefendRegion}, and {@link EmergencyRetreat}.
 * Higher-level task actions (M5) compose these unchanged.
 */
public interface Skill{

    /** Stable action type tag, e.g. {@code "NAVIGATE"}, {@code "MINE"}. */
    String type();

    /**
     * Advance the skill one tick.
     *
     * @param body the unit port to observe and steer
     * @param tick the current simulation tick (used only for {@code nextRetryTick})
     * @return the outcome this tick
     */
    SkillResult tick(AgentBody body, long tick);
}
