package agentcore.human;

import agentcore.human.HumanPresence.*;
import agentcore.reservation.*;
import org.junit.jupiter.api.*;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class HumanPresenceTest{
    private final Tracker tracker = new Tracker();
    private final Plan plan = new Plan("human:presence:1", new Rect(3, 4, 2, 2),
        Map.of("copper", 12));

    @Test void activePlanDiffIsStableAndRemovalIsOrdered(){
        Change first = tracker.update(List.of(plan), 10);
        assertEquals(List.of(plan), first.added());
        assertTrue(first.removed().isEmpty());
        assertTrue(tracker.update(List.of(plan), 11).empty());
        assertEquals(List.of("human:presence:1"), tracker.update(List.of(), 12).removed());
    }

    @Test void completedPlanDropsResourceFloorButRetainsTileForPinnedTicks(){
        tracker.update(List.of(plan), 10);
        tracker.constructionCompleted(plan, 20);
        Change stillActive = tracker.update(List.of(plan), 20);
        assertTrue(stillActive.empty());

        Change completed = tracker.update(List.of(), 21);
        assertEquals(List.of(plan.id()), completed.removed());
        assertEquals(List.of(plan.completed()), completed.added());
        assertTrue(tracker.update(List.of(), 619).empty());
        assertEquals(List.of(plan.id()), tracker.update(List.of(), 620).removed());
    }

    @Test void resetClearsAppliedAndRecentState(){
        tracker.update(List.of(plan), 1);
        tracker.constructionCompleted(plan, 2);
        tracker.reset();
        assertTrue(tracker.current().isEmpty());
        assertTrue(tracker.update(List.of(), 3).empty());
    }
}
