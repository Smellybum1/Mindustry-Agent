package mindustry.agentplugin;

import arc.mock.*;

/** Fixed-delta headless graphics used only by the isolated decision-parity probe. */
final class FixedProbeGraphics extends MockGraphics{
    @Override
    public float getDeltaTime(){
        return 1f / 60f;
    }

    @Override
    public void updateTime(){
        //The probe must not derive engine time from the host wall clock.
    }
}
