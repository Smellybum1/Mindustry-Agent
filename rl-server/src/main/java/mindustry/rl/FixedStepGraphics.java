package mindustry.rl;

import arc.mock.*;

/**
 * Deterministic, wall-clock-free graphics stub for the externally-stepped loop.
 *
 * <p>Overriding {@link #getDeltaTime()} is the single lever that pins every engine
 * clock to a fixed step (see docs/ENGINE_NOTES.md §2.4-2.5): {@code Logic.update()}
 * reads {@code Core.graphics.getDeltaTime()} directly for {@code state.tick +=
 * delta*60f}, and {@code Time.updateGlobal()} reads it directly for
 * {@code globalTimeRaw}. With a fixed {@code 1/60f} delta, {@code state.tick},
 * {@code Time.delta}, {@code Time.time} and {@code Time.globalTime} all advance
 * exactly {@code +1.0} per update, with no {@code System.nanoTime()} read.
 *
 * <p>{@code deltaTime} is package-private in {@link MockGraphics} so an out-of-package
 * subclass cannot write the field; overriding the two accessors is sufficient.
 */
public final class FixedStepGraphics extends MockGraphics{
    /** Seconds per engine update. 1/60 gives exactly +1.0 game tick per update. */
    private float deltaSeconds = 1f / 60f;

    public void setDeltaSeconds(float seconds){
        this.deltaSeconds = seconds;
    }

    @Override
    public float getDeltaTime(){
        return deltaSeconds;
    }

    /** No-op: this is the only wall-clock coupling in the whole simulation. */
    @Override
    public void updateTime(){
        //intentionally empty — never read System.nanoTime()
    }
}
