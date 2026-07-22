package mindustry.rl;

import mindustry.gen.*;

/**
 * Runtime-neutral view of the controlled agent bindings consumed by candidate,
 * coordination, and feature adapters. Training and real-time demo registries
 * implement the same contract; neither adapter owns spawning or pacing.
 */
public interface AgentRuntimeRegistry{
    /**
     * One dense agent-index binding for the active world. Adapters consume the
     * accessors so a real-time registry can resolve a replacement unit after a
     * death/rebind without replacing its stable binding object.
     */
    class Agent{
        public final int index;
        public final Unit unit;
        public final SkillController controller;

        public Agent(int index, Unit unit, SkillController controller){
            this.index = index;
            this.unit = unit;
            this.controller = controller;
        }

        public int index(){ return index; }
        public Unit unit(){ return unit; }
        public SkillController controller(){ return controller; }
    }

    int size();

    /** Bindings in deterministic dense-index order. */
    Iterable<? extends Agent> agents();

    /** The binding at dense index {@code index}, or {@code null}. */
    Agent get(int index);
}
