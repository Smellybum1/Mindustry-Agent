package mindustry.rl;

import arc.struct.*;
import mindustry.content.*;
import mindustry.entities.*;
import mindustry.game.*;
import mindustry.gen.*;

import static mindustry.Vars.*;

/**
 * Maps dense agent indices to their controlled core units for one episode
 * (docs/M3_DESIGN.md D1). Rebuilt from scratch on every reset because
 * {@code Logic.reset()} calls {@code Groups.clear()} and removes all units
 * (docs/ENGINE_NOTES.md §3.4, resolved open question 1).
 *
 * <p>Agents are spawned <b>after</b> {@code logic.play()} at deterministic offsets ordered
 * by index, just east of the core and clear of its 3×3 footprint. Each unit is an
 * {@link UnitTypes#alpha} (the Serpulo core builder/miner: flying, {@code mineSpeed} 6.5,
 * {@code mineTier} 1, {@code itemCapacity} 30 — resolved open question 4) whose controller
 * is replaced by a {@link SkillController}. Under this scenario's ruleset
 * ({@code prebuildAi/buildAi/rtsAi} all off, sharded is the non-AI default team) nothing
 * vanilla ever reassigns the controller, so no tagging is required (resolved open
 * question 2).
 */
public final class RlAgentRegistry{

    /** One agent's episode binding. */
    public static final class Agent{
        public final int index;
        public final Unit unit;
        public final SkillController controller;

        Agent(int index, Unit unit, SkillController controller){
            this.index = index;
            this.unit = unit;
            this.controller = controller;
        }
    }

    private final Seq<Agent> agents = new Seq<>();

    /** Spawn {@code count} agent units for the active team and bind controllers. */
    public void rebuild(int count){
        agents.clear();

        Team team = state.rules.defaultTeam;
        Building core = team.core();
        float baseX = core != null ? core.x : world.width() * tilesize / 2f;
        float baseY = core != null ? core.y : world.height() * tilesize / 2f;

        for(int i = 0; i < count; i++){
            //deterministic, index-ordered offsets: (3+i) tiles east of the core center
            float sx = baseX + (3 + i) * tilesize;
            float sy = baseY;

            Unit unit = UnitTypes.alpha.spawn(team, sx, sy);
            SkillController controller = new SkillController(i);
            unit.controller(controller);
            Units.notifyUnitSpawn(unit);

            agents.add(new Agent(i, unit, controller));
        }
    }

    public void clear(){ agents.clear(); }

    public int size(){ return agents.size; }

    /** Agents in dense index order (0..size). */
    public Seq<Agent> agents(){ return agents; }

    /** The agent at dense index {@code i}, or {@code null} if out of range. */
    public Agent get(int i){
        return i >= 0 && i < agents.size ? agents.get(i) : null;
    }
}
