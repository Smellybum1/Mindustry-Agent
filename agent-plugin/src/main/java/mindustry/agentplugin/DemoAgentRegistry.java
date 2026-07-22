package mindustry.agentplugin;

import arc.struct.*;
import arc.util.*;
import mindustry.content.*;
import mindustry.entities.*;
import mindustry.gen.*;
import mindustry.rl.*;

import static mindustry.Vars.*;

/** Real-time controlled-agent bindings with deterministic spawn and rebind ownership. */
final class DemoAgentRegistry implements AgentRuntimeRegistry{
    private static final String[] names = {"agent-copper", "agent-shield", "agent-relay"};

    static final class Agent extends AgentRuntimeRegistry.Agent{
        private Unit currentUnit;
        private final DemoAgentController demoController;

        Agent(int index, Unit unit, DemoAgentController controller){
            super(index, unit, controller);
            currentUnit = unit;
            demoController = controller;
        }

        @Override public Unit unit(){ return currentUnit; }
        @Override public DemoAgentController controller(){ return demoController; }

        void rebind(Unit replacement){
            currentUnit = replacement;
        }
    }

    private final Scenario scenario;
    private final Seq<Agent> agents = new Seq<>();

    DemoAgentRegistry(Scenario scenario){
        this.scenario = scenario;
    }

    void spawn(){
        Building core = scenario.coreTeam.core();
        if(core == null) throw new IllegalStateException("demo scenario has no core");
        agents.clear();
        for(int i = 0; i < names.length; i++){
            DemoAgentController controller = new DemoAgentController(i);
            Unit unit = spawnUnit(i, controller, core);
            agents.add(new Agent(i, unit, controller));
        }
    }

    void ensureAgent(int agentIndex){
        Agent agent = get(agentIndex);
        if(agent == null || available(agent)) return;
        Building core = scenario.coreTeam.core();
        if(core == null) throw new IllegalStateException("cannot rebind agent without a core");
        Unit replacement = spawnUnit(agent.index(), agent.controller(), core);
        agent.rebind(replacement);
        agent.controller().resumeNow();
        Log.warn("AGENT-DEMO REBOUND agent=@ replacement_unit=@", agent.index(), replacement.id);
    }

    boolean available(int agentIndex){
        return available(get(agentIndex));
    }

    @Override public int size(){ return agents.size; }
    @Override public Seq<Agent> agents(){ return agents; }

    @Override
    public Agent get(int index){
        return index >= 0 && index < agents.size ? agents.get(index) : null;
    }

    private Unit spawnUnit(int index, DemoAgentController controller, Building core){
        Unit unit = UnitTypes.alpha.spawn(scenario.coreTeam,
            core.x + (3 + index) * tilesize, core.y);
        unit.controller(controller);
        Units.notifyUnitSpawn(unit);
        return unit;
    }

    private static boolean available(Agent agent){
        return agent != null && agent.unit() != null && agent.unit().isValid() && !agent.unit().dead();
    }
}
