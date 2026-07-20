package mindustry.rl;

import arc.*;
import arc.struct.*;
import arc.util.*;

/**
 * An {@link arc.Application} that replaces Arc's wall-clock background loop with an
 * externally driven, synchronous fixed-step loop (ADR-0002, docs/ENGINE_NOTES.md §2.6, §11.2).
 *
 * <p>The constructor mirrors {@code HeadlessApplication}'s {@code Core.*} assignment
 * block ({@code HeadlessApplication.java:35-41}) but substitutes {@link FixedStepGraphics}
 * and starts <b>no</b> background thread. {@link #stepOnce()} reproduces one iteration of
 * {@code HeadlessApplication.mainLoop()} minus the wall-clock sleep and minus
 * {@code graphics.updateTime()}, on the caller's (simulation) thread.
 */
public final class FixedStepApplication implements Application{
    private final Seq<ApplicationListener> listeners = new Seq<>();
    private final TaskQueue runnables = new TaskQueue();
    public final FixedStepGraphics graphics = new FixedStepGraphics();

    /** The single thread permitted to touch game state (AGENTS.md §3). */
    private Thread mainThread = Thread.currentThread();
    private volatile boolean running = true;

    public FixedStepApplication(){
        //mirror HeadlessApplication.java:35-41, but with our graphics and no loop thread
        Core.settings = new arc.Settings();
        Core.app = this;
        Core.files = new arc.mock.MockFiles();
        Core.audio = new arc.mock.MockAudio();
        Core.graphics = graphics;
        Core.input = new arc.mock.MockInput();
    }

    /** Bind the stepping thread; makes {@link #isOnMainThread()} true for it. */
    public void setMainThread(Thread thread){
        this.mainThread = thread;
    }

    /** Call each listener's {@code init()} once, on the current thread. */
    public void initOnce(){
        synchronized(listeners){
            for(ApplicationListener l : listeners){
                l.init();
            }
        }
    }

    /**
     * One synchronous engine update. Mirrors {@code HeadlessApplication.mainLoop()}
     * body ({@code :81-89}) minus the sleep and minus {@code graphics.updateTime()}
     * (the removed call is the only wall-clock read).
     */
    public void stepOnce(){
        runnables.run();                 //drain Core.app.post(...)
        graphics.incrementFrameId();
        defaultUpdate();                 //Core.settings.autosave() + Time.updateGlobal()
        synchronized(listeners){
            for(int i = 0; i < listeners.size; i++){
                listeners.get(i).update();
            }
        }
    }

    /** Drop callbacks posted by the episode being reset before IDs are reseeded. */
    public void clearPostedTasks(){
        runnables.clear();
    }

    @Override public Seq<ApplicationListener> getListeners(){ return listeners; }
    @Override public ApplicationType getType(){ return ApplicationType.headless; }
    @Override public Thread getMainThread(){ return mainThread; }
    @Override public void post(Runnable runnable){ runnables.post(runnable); }

    @Override public String getClipboardText(){ return ""; }
    @Override public void setClipboardText(String text){}

    @Override
    public void exit(){
        running = false;
    }

    public boolean isRunning(){
        return running;
    }
}
