package mindustry.agentplugin;

import mindustry.rl.SkillController;

/**
 * Real-time dedicated-server controller. The shared {@link SkillController}
 * supplies the exact training-mode {@code AgentBody} mapping; this subclass adds
 * immediate, human-facing pause and emergency-stop semantics for demo mode.
 */
public final class DemoAgentController extends SkillController{
    private boolean enabled = true;

    public DemoAgentController(int agentIndex){
        super(agentIndex);
    }

    @Override
    public void updateUnit(){
        if(enabled) super.updateUnit();
    }

    public boolean enabled(){ return enabled; }

    /** Suspend policy work without discarding the active deterministic skill. */
    public void pauseNow(){
        enabled = false;
        if(unit != null){
            unit.vel.setZero();
            clearMineTile();
            cancelBuildPlans();
            ceaseFire();
        }
    }

    public void resumeNow(){ enabled = true; }

    /** Cancel every engine-owned action immediately. */
    public void stopNow(){
        pauseNow();
        clearSkill();
    }
}
