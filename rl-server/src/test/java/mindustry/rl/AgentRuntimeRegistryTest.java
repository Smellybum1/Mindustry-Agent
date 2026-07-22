package mindustry.rl;

import org.junit.jupiter.api.*;

import static org.junit.jupiter.api.Assertions.*;

class AgentRuntimeRegistryTest{
    @Test void rlRegistryPreservesItsFacadeThroughSharedContract(){
        RlAgentRegistry concrete = new RlAgentRegistry();
        AgentRuntimeRegistry shared = concrete;

        assertEquals(0, shared.size());
        assertNull(shared.get(0));
        assertFalse(shared.agents().iterator().hasNext());
    }

    @Test void legacyAgentFieldsRemainAvailableOnSharedBinding(){
        SkillController controller = new SkillController(2);
        RlAgentRegistry.Agent agent = new RlAgentRegistry.Agent(2, null, controller);
        AgentRuntimeRegistry.Agent shared = agent;

        assertEquals(2, agent.index);
        assertNull(agent.unit);
        assertSame(controller, agent.controller);
        assertEquals(agent.index, shared.index());
        assertSame(agent.unit, shared.unit());
        assertSame(agent.controller, shared.controller());
    }

    @Test void sharedBindingAccessorsCanResolveRuntimeStateDynamically(){
        SkillController first = new SkillController(0);
        SkillController replacement = new SkillController(0);
        SkillController[] current = {first};
        AgentRuntimeRegistry.Agent binding = new AgentRuntimeRegistry.Agent(
            0, null, first
        ){
            @Override public SkillController controller(){ return current[0]; }
        };

        assertSame(first, binding.controller());
        current[0] = replacement;
        assertSame(replacement, binding.controller());
    }
}
