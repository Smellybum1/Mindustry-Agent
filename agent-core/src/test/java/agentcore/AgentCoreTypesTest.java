package agentcore;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Sanity tests locking the vocabulary sizes and identity semantics that the
 * protocol relies on. If any of these change, docs/PROTOCOL.md and the Python
 * mirrors must change in the same commit.
 */
class AgentCoreTypesTest{

    @Test void taskVocabularyHasSixteenTypes(){
        assertEquals(16, TaskType.values().length);
        assertEquals(TaskType.HARVEST_RESOURCE, TaskType.values()[0]);
        assertEquals(TaskType.REQUEST_HELP, TaskType.values()[TaskType.values().length - 1]);
    }

    @Test void coordinationVocabularyHasThirteenActs(){
        assertEquals(13, CoordinationAct.values().length);
        assertEquals(CoordinationAct.ANNOUNCE_INTENT, CoordinationAct.values()[0]);
    }

    @Test void skillStatusHasSixStates(){
        assertEquals(6, SkillStatus.values().length);
    }

    @Test void agentIdDefaultsDisplayNameFromIndex(){
        AgentId a = AgentId.of(3);
        assertEquals(3, a.index());
        assertEquals("agent-3", a.displayName());
    }

    @Test void agentIdEqualityIsByIndexOnly(){
        assertEquals(new AgentId(1, "copper"), new AgentId(1, "shield"));
        assertNotEquals(new AgentId(1, "copper"), new AgentId(2, "copper"));
    }

    @Test void agentIdRejectsNegativeIndex(){
        assertThrows(IllegalArgumentException.class, () -> new AgentId(-1, "x"));
    }
}
