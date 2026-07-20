package agentcore.skill;

/** Cancel active construction and weapon fire, then return to the team core. */
public final class EmergencyRetreat implements Skill{
    private static final float ARRIVAL_TOLERANCE = 8f;
    private boolean cancelled;
    private boolean complete;

    @Override public String type(){ return "RETREAT"; }

    @Override
    public SkillResult tick(AgentBody body, long tick){
        if(!cancelled){
            body.cancelBuildPlans();
            cancelled = true;
        }
        body.ceaseFire();

        if(complete){
            body.halt();
            return SkillResult.succeeded(SkillReason.RETREATED);
        }

        if(!body.hasCore()){
            body.halt();
            return SkillResult.blocked(SkillReason.NO_CORE, tick + 60L);
        }
        if(body.dst(body.coreX(), body.coreY()) <= ARRIVAL_TOLERANCE){
            complete = true;
            body.halt();
            return SkillResult.succeeded(SkillReason.RETREATED);
        }
        body.steerToward(body.coreX(), body.coreY());
        return SkillResult.running(SkillReason.RETREATING, 0f);
    }
}
