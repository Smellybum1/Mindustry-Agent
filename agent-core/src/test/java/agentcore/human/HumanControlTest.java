package agentcore.human;

import agentcore.*;
import agentcore.human.HumanControl.*;
import org.junit.jupiter.api.*;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class HumanControlTest{
    private final State state = new State();
    private final Context context = new Context(Set.of("east_lane", "copper_line_v1"), 3);

    @Test void parserCanonicalizesEveryCommand(){
        assertEquals(TaskType.DEFEND_REGION,
            parsed("goal", "defend-region", "EAST_LANE").taskType());
        assertEquals("human:goal:2", parsed("cancel", "HUMAN:GOAL:2").goalId());
        assertEquals(2, parsed("assign", "2", "human:goal:1").agentIndex());
        assertEquals(CommandType.RELEASE, parsed("release", "1").type());
        assertEquals(AutonomyLevel.LOW, parsed("autonomy", "low").autonomy());
        assertTrue(parsed("quiet", "ON").quiet());
    }

    @Test void parserRejectsUnknownMalformedAndExtraArguments(){
        assertEquals("missing_command", HumanControl.parse(new String[0], "player").reason());
        assertEquals("unknown_command", HumanControl.parse(new String[]{"wat"}, "player").reason());
        assertEquals("usage_goal", HumanControl.parse(new String[]{"goal"}, "player").reason());
        assertEquals("invalid_argument",
            HumanControl.parse(new String[]{"quiet", "maybe"}, "player").reason());
        assertEquals("usage_release",
            HumanControl.parse(new String[]{"release", "1", "extra"}, "player").reason());
        assertEquals("invalid_argument",
            HumanControl.parse(new String[]{"assign", "-1", "human:goal:1"}, "player").reason());
    }

    @Test void commandRecordRejectsIncompleteTypedPayloads(){
        assertThrows(NullPointerException.class, () -> new Command(CommandType.GOAL,
            null, "east_lane", "", -1, null, null, "player"));
        assertThrows(IllegalArgumentException.class, () -> new Command(CommandType.ASSIGN,
            null, "", "", 1, null, null, "player"));
        assertThrows(NullPointerException.class, () -> new Command(CommandType.QUIET,
            null, "", "", -1, null, null, "player"));
    }

    @Test void goalLifecycleIsBoundedOrderedAndRevisioned(){
        Event first = apply(parsed("goal", "defend-region", "east_lane"), 10);
        Event second = apply(parsed("goal", "build-line", "copper_line_v1"), 11);
        assertEquals("human:goal:1", first.goalId());
        assertEquals(2, second.revision());
        assertEquals(List.of("human:goal:1", "human:goal:2"), state.snapshot().activeGoals()
            .stream().map(Goal::id).toList());

        Event duplicate = apply(parsed("goal", "defend-region", "east_lane"), 12);
        assertFalse(duplicate.accepted());
        assertEquals("duplicate_goal", duplicate.reason());
        assertEquals(2, duplicate.revision());

        apply(parsed("goal", "harvest-resource", "east_lane"), 13);
        apply(parsed("goal", "repair-region", "east_lane"), 14);
        Event overflow = apply(parsed("goal", "wait", "east_lane"), 15);
        assertEquals("goal_limit", overflow.reason());
        assertEquals(4, state.snapshot().activeGoals().size());
    }

    @Test void assignmentReleaseAndCancelRejectWithoutMutation(){
        apply(parsed("goal", "defend-region", "east_lane"), 1);
        Event assigned = apply(parsed("assign", "2", "human:goal:1"), 2);
        assertTrue(assigned.accepted());
        assertEquals(List.of(new Assignment(2, "human:goal:1")), state.snapshot().assignments());

        Event duplicate = apply(parsed("assign", "2", "human:goal:1"), 3);
        assertEquals("agent_already_assigned", duplicate.reason());
        assertEquals(2, duplicate.revision());
        assertTrue(apply(parsed("release", "2"), 4).accepted());
        assertEquals("agent_not_assigned", apply(parsed("release", "2"), 5).reason());

        apply(parsed("assign", "1", "human:goal:1"), 6);
        assertTrue(apply(parsed("cancel", "human:goal:1"), 7).accepted());
        assertTrue(state.snapshot().activeGoals().isEmpty());
        assertTrue(state.snapshot().assignments().isEmpty());
        assertEquals("unknown_goal", apply(parsed("cancel", "human:goal:1"), 8).reason());
    }

    @Test void autonomyQuietAndResetAreBehaviorNeutralByDefault(){
        assertEquals(new Snapshot(List.of(), List.of(), AutonomyLevel.NORMAL, false, 0),
            state.snapshot());
        assertEquals("no_change", apply(parsed("autonomy", "normal"), 1).reason());
        assertTrue(apply(parsed("autonomy", "low"), 2).accepted());
        assertTrue(apply(parsed("quiet", "on"), 3).accepted());
        assertEquals(AutonomyLevel.LOW, state.snapshot().autonomy());
        assertTrue(state.snapshot().quiet());
        state.reset();
        assertEquals(new Snapshot(List.of(), List.of(), AutonomyLevel.NORMAL, false, 0),
            state.snapshot());
    }

    @Test void stateValidatesScenarioAndAgentBounds(){
        Event region = apply(parsed("goal", "defend-region", "missing"), 1);
        assertEquals("unknown_region", region.reason());
        apply(parsed("goal", "defend-region", "east_lane"), 2);
        Event agent = apply(parsed("assign", "3", "human:goal:1"), 3);
        assertEquals("unknown_agent", agent.reason());
        assertEquals(1, agent.revision());
    }

    @Test void contextCanonicalizesRegionsAndQuietPreservesUrgentMessages(){
        Context canonical = new Context(Set.of("EAST_LANE"), 1);
        assertTrue(new State().apply(parsed("goal", "defend-region", "east_lane"),
            1, canonical).accepted());
        assertFalse(HumanControl.shouldRenderCoordination(true, "START_TASK"));
        assertTrue(HumanControl.shouldRenderCoordination(true, "BLOCKED"));
        assertTrue(HumanControl.shouldRenderCoordination(true, "",
            "yield_to_human"));
        assertTrue(HumanControl.shouldRenderCoordination(false, "START_TASK"));
    }

    @Test void callbackQueueCannotMutateUntilSimulationThreadDrains() throws Exception{
        CommandQueue queue = new CommandQueue();
        EnqueueResult[] queued = new EnqueueResult[1];
        Thread callback = new Thread(() -> queued[0] = queue.enqueue(
            new String[]{"goal", "defend-region", "east_lane"}, "player"));
        callback.start();
        callback.join();

        assertTrue(queued[0].accepted());
        assertEquals(1, queued[0].sequence());
        assertEquals(1, queue.pending());
        assertEquals(0, state.snapshot().revision());
        assertTrue(state.snapshot().activeGoals().isEmpty());
        assertEquals("agents: command queued sequence=1 type=goal",
            HumanControl.renderQueued(queued[0]));

        List<AppliedCommand> applied = queue.drain(state, 20, context);
        assertEquals(1, applied.size());
        assertEquals("human:goal:1", applied.get(0).event().goalId());
        assertEquals(1, state.snapshot().revision());
        assertEquals("agents: command applied type=goal reason=applied revision=1"
            + " goal=human:goal:1", HumanControl.render(applied.get(0).event()));
        assertEquals(0, queue.pending());
    }

    @Test void queuePreservesAcceptedOrderAndDoesNotQueueParseFailures(){
        CommandQueue queue = new CommandQueue();
        assertFalse(queue.enqueue(new String[]{"quiet", "maybe"}, "player").accepted());
        assertEquals(0, queue.pending());
        assertEquals(1, queue.enqueue(new String[]{"quiet", "on"}, "player").sequence());
        assertEquals(2, queue.enqueue(new String[]{"autonomy", "low"}, "player").sequence());

        List<AppliedCommand> applied = queue.drain(state, 5, context);
        assertEquals(List.of(CommandType.QUIET, CommandType.AUTONOMY), applied.stream()
            .map(result -> result.event().command().type()).toList());
        assertEquals(2, state.snapshot().revision());
    }

    private Command parsed(String... tokens){
        ParseResult result = HumanControl.parse(tokens, "Player.One");
        assertTrue(result.accepted(), result.reason());
        return result.command();
    }

    private Event apply(Command command, long tick){
        return state.apply(command, tick, context);
    }
}
