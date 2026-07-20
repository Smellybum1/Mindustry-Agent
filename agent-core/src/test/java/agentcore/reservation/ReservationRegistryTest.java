package agentcore.reservation;

import agentcore.AgentId;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for soft reservations: incompatible overlap rejection, human override
 * priority, resource budgets, and the never-negative invariant (brief §11.6,
 * §23.5).
 */
class ReservationRegistryTest{

    private static final AgentId A = new AgentId(0, "agent-a");
    private static final AgentId B = new AgentId(1, "agent-b");
    private static final AgentId HUMAN = new AgentId(9, "human-1");

    @Test void tileRectOverlapDetection(){
        assertTrue(new Rect(0, 0, 3, 3).overlaps(new Rect(2, 2, 2, 2)));
        assertFalse(new Rect(0, 0, 2, 2).overlaps(new Rect(2, 2, 2, 2)));
        assertFalse(new Rect(0, 0, 2, 2).overlaps(new Rect(5, 5, 1, 1)));
    }

    @Test void incompatibleAgentOverlapRejected(){
        ReservationRegistry r = new ReservationRegistry();
        assertTrue(r.acquireTile("t1", A, new Rect(0, 0, 3, 3), false, 0).granted());
        ReservationOutcome out = r.acquireTile("t2", B, new Rect(1, 1, 3, 3), false, 1);
        assertFalse(out.granted());
        assertEquals(ReservationResult.REJECTED_OVERLAP, out.result());
        assertEquals(1, out.conflicts().size());
        // The rejected reservation was not added.
        assertEquals(1, r.size());
    }

    @Test void sameTaskOverlapIsCompatible(){
        ReservationRegistry r = new ReservationRegistry();
        assertTrue(r.acquireTile("t1", A, new Rect(0, 0, 3, 3), false, 0).granted());
        assertTrue(r.acquireTile("t1", A, new Rect(1, 1, 3, 3), false, 1).granted());
        assertEquals(2, r.size());
    }

    @Test void humanReservationForcesAgentToYield(){
        ReservationRegistry r = new ReservationRegistry();
        r.acquireTile("agentTask", A, new Rect(0, 0, 3, 3), false, 0);
        ReservationOutcome out = r.acquireTile("humanTask", HUMAN, new Rect(1, 1, 3, 3), true, 5);
        assertEquals(ReservationResult.GRANTED_HUMAN_OVERRIDE, out.result());
        assertEquals(1, out.conflicts().size());
        ReservationConflict c = out.conflicts().get(0);
        assertEquals("agentTask", c.yieldedTaskId());
        assertTrue(c.winnerHuman());
        // Agent reservation removed, only the human's remains.
        assertEquals(1, r.size());
        assertEquals(1, r.tileOverlaps(new Rect(1, 1, 1, 1)).size());
    }

    @Test void agentCannotOverrideHumanReservation(){
        ReservationRegistry r = new ReservationRegistry();
        r.acquireTile("humanTask", HUMAN, new Rect(0, 0, 3, 3), true, 0);
        ReservationOutcome out = r.acquireTile("agentTask", A, new Rect(1, 1, 3, 3), false, 5);
        assertEquals(ReservationResult.REJECTED_HUMAN_PRIORITY, out.result());
        assertEquals(1, r.size());
    }

    @Test void resourceBudgetRejectsOverReservationAndNeverGoesNegative(){
        ReservationRegistry r = new ReservationRegistry();
        r.setCapacity("copper", 100);
        assertTrue(r.acquireResource("t1", A, "copper", 60, false, 0).granted());
        ReservationOutcome out = r.acquireResource("t2", B, "copper", 60, false, 1);
        assertEquals(ReservationResult.REJECTED_CAPACITY, out.result());
        assertEquals(60, r.reservedAmount("copper"));

        // Releasing an unknown task cannot drive the counter negative.
        r.releaseAll("does-not-exist");
        assertEquals(60, r.reservedAmount("copper"));
        r.releaseAll("t1");
        assertEquals(0, r.reservedAmount("copper"));
        assertTrue(r.reservedAmount("copper") >= 0);
    }

    @Test void humanResourceReservationBypassesBudget(){
        ReservationRegistry r = new ReservationRegistry();
        r.setCapacity("copper", 100);
        assertTrue(r.acquireResource("human", HUMAN, "copper", 150, true, 0).granted());
        assertEquals(150, r.reservedAmount("copper"));
        // Now an agent cannot reserve because the human consumed the budget.
        assertFalse(r.acquireResource("t1", A, "copper", 10, false, 1).granted());
    }

    @Test void regionReservationOverlapAndRelease(){
        ReservationRegistry r = new ReservationRegistry();
        assertTrue(r.acquireRegion("t1", A, "east", false, 0).granted());
        assertTrue(r.isRegionReserved("east"));
        assertFalse(r.acquireRegion("t2", B, "east", false, 1).granted());
        r.releaseAll("t1");
        assertFalse(r.isRegionReserved("east"));
    }

    @Test void releaseAllReturnsRemovedCountAcrossKinds(){
        ReservationRegistry r = new ReservationRegistry();
        r.acquireTile("t", A, Rect.ofTile(0, 0), false, 0);
        r.acquireResource("t", A, "lead", 10, false, 0);
        r.acquireRegion("t", A, "north", false, 0);
        assertEquals(3, r.releaseAll("t"));
        assertEquals(0, r.size());
    }

    @Test void deterministicViewsAndPerTaskCountExposeActiveReservations(){
        ReservationRegistry r = new ReservationRegistry();
        r.acquireTile("a", A, Rect.ofTile(1, 1), false, 0);
        r.acquireResource("a", A, "copper", 20, false, 0);
        r.acquireRegion("b", B, "east", false, 0);

        assertEquals(2, r.countForTask("a"));
        assertEquals(1, r.countForTask("b"));
        assertEquals("a", r.tileReservations().get(0).taskId());
        assertEquals("a", r.resourceReservations().get(0).taskId());
        assertEquals("b", r.regionReservations().get(0).taskId());
        assertThrows(UnsupportedOperationException.class,
            () -> r.tileReservations().clear());
    }
}
