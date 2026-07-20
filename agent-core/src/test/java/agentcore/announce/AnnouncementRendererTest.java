package agentcore.announce;

import agentcore.AgentId;
import agentcore.CoordinationAct;
import agentcore.TaskType;
import agentcore.event.CoordinationEvent;
import agentcore.task.TaskStatus;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Snapshot tests locking the deterministic announcement strings (brief §20.3).
 * If a template changes, these must change in the same commit.
 */
class AnnouncementRendererTest{

    private static final AgentId COPPER = new AgentId(0, "agent-copper");
    private static final AgentId SHIELD = new AgentId(1, "agent-shield");
    private static final AgentId RELAY = new AgentId(2, "agent-relay");

    private final AnnouncementRenderer renderer = new AnnouncementRenderer();

    private static CoordinationEvent.Builder base(){
        return CoordinationEvent.builder().messageId(0).tick(100).taskId("task");
    }

    @Test void startTaskBuildLine(){
        CoordinationEvent ev = base()
            .agent(COPPER).act(CoordinationAct.START_TASK).taskType(TaskType.BUILD_LINE)
            .targetDescription("region core").announce(true).build();
        assertEquals("[Agent Copper] Starting: establish production line at region core.", renderer.render(ev));
    }

    @Test void startTaskWithHelperRequest(){
        CoordinationEvent ev = base()
            .agent(SHIELD).act(CoordinationAct.START_TASK).taskType(TaskType.DEFEND_REGION)
            .targetDescription("region east-defense").helpersRequested(1).announce(true).build();
        assertEquals("[Agent Shield] Starting: defend region east-defense. Requesting 1 helper.", renderer.render(ev));
    }

    @Test void acceptHelpRendersHelperHelpingLead(){
        CoordinationEvent ev = base()
            .agent(RELAY).relatedAgent(SHIELD).act(CoordinationAct.ACCEPT_HELP)
            .taskType(TaskType.SUPPLY_TURRET).offeredContribution("deliver 120 copper").announce(true).build();
        assertEquals("[Agent Relay] Helping Shield: deliver 120 copper.", renderer.render(ev));
    }

    @Test void offerHelpRendersOfferingToLead(){
        CoordinationEvent ev = base()
            .agent(RELAY).relatedAgent(SHIELD).act(CoordinationAct.OFFER_HELP)
            .taskType(TaskType.SUPPLY_TURRET).offeredContribution("deliver copper").announce(true).build();
        assertEquals("[Agent Relay] Offering to help Shield: deliver copper.", renderer.render(ev));
    }

    @Test void blockedRendersReason(){
        CoordinationEvent ev = base()
            .agent(SHIELD).act(CoordinationAct.BLOCKED).taskType(TaskType.SUPPLY_TURRET)
            .reasonCode("18 copper short. Waiting up to 20 seconds.").announce(true).build();
        assertEquals("[Agent Shield] Blocked: 18 copper short. Waiting up to 20 seconds.", renderer.render(ev));
    }

    @Test void completeRendersPhrase(){
        CoordinationEvent ev = base()
            .agent(COPPER).act(CoordinationAct.COMPLETE).taskType(TaskType.BUILD_LINE)
            .targetDescription("region core").progress(1.0).announce(true).build();
        assertEquals("[Agent Copper] Complete: establish production line at region core.", renderer.render(ev));
    }

    @Test void abandonRendersReason(){
        CoordinationEvent ev = base()
            .agent(SHIELD).act(CoordinationAct.ABANDON).taskType(TaskType.DEFEND_REGION)
            .targetDescription("region east").reasonCode("overrun").announce(true).build();
        assertEquals("[Agent Shield] Abandoning: defend region east (overrun).", renderer.render(ev));
    }

    @Test void proposeRendersBoardLine(){
        CoordinationEvent ev = base()
            .act(null).taskType(TaskType.HARVEST_RESOURCE).targetDescription("120 copper")
            .fromStatus(null).toStatus(TaskStatus.OPEN).build();
        assertEquals("[Board] Proposed: harvest 120 copper.", renderer.render(ev));
    }

    @Test void yieldToHumanRendersConflictLine(){
        CoordinationEvent ev = base()
            .agent(COPPER).act(null).reasonCode("yield_to_human")
            .targetDescription("agent reservation yielded to human on tile Rect[x=1, y=1, w=2, h=2]")
            .announce(true).build();
        assertEquals("[Agent Copper] Yielding to human: agent reservation yielded to human on tile "
            + "Rect[x=1, y=1, w=2, h=2].", renderer.render(ev));
    }

    @Test void renderAnnouncementsFiltersByAnnounceFlag(){
        CoordinationEvent announced = base().agent(COPPER).act(CoordinationAct.START_TASK)
            .taskType(TaskType.BUILD_LINE).announce(true).build();
        CoordinationEvent routine = base().agent(COPPER).act(CoordinationAct.HEARTBEAT)
            .taskType(TaskType.BUILD_LINE).announce(false).build();
        List<String> out = renderer.renderAnnouncements(List.of(announced, routine));
        assertEquals(1, out.size());
        assertEquals("[Agent Copper] Starting: establish production line.", out.get(0));
    }
}
