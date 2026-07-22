package agentcore.board;

import agentcore.AgentId;
import agentcore.TaskType;
import agentcore.reservation.Rect;
import agentcore.reservation.ReservationOutcome;
import agentcore.task.HelperContract;
import agentcore.task.RegionTarget;
import agentcore.task.TaskSpec;
import agentcore.task.TaskStatus;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Behavioural tests for the coordination board: claim tie-breaking, lease expiry,
 * heartbeats, the helper lifecycle, abandonment/reservation release, and the
 * exclusive-ownership safety property (brief §11.5, §23.1, §23.5).
 */
class TaskBoardTest{

    private static final AgentId COPPER = new AgentId(0, "agent-copper");
    private static final AgentId SHIELD = new AgentId(1, "agent-shield");
    private static final AgentId RELAY = new AgentId(2, "agent-relay");
    private static final AgentId ALPHA = new AgentId(3, "agent-alpha");
    private static final AgentId BETA = new AgentId(4, "agent-beta");

    private static TaskSpec spec(String id, TaskType type){
        return TaskSpec.builder(id, type).target(new RegionTarget("east")).priority(0.5).build();
    }

    private static TaskBoard board(){
        return new TaskBoard();
    }

    // ---- claim tie-breaking ----

    @Test void higherBidWinsRegardlessOfCallOrder(){
        // Order A: COPPER claims first, SHIELD (higher bid) second.
        TaskBoard b1 = board();
        b1.propose(spec("t", TaskType.BUILD_LINE), 0);
        assertTrue(b1.claim("t", COPPER, 1.0, 10).granted());
        ClaimOutcome contested1 = b1.claim("t", SHIELD, 2.0, 10);
        assertEquals(ClaimResult.WON_CONTEST, contested1.result());
        assertEquals(SHIELD, b1.task("t").owner());

        // Order B: SHIELD claims first, COPPER (lower bid) second — same winner.
        TaskBoard b2 = board();
        b2.propose(spec("t", TaskType.BUILD_LINE), 0);
        assertTrue(b2.claim("t", SHIELD, 2.0, 10).granted());
        ClaimOutcome contested2 = b2.claim("t", COPPER, 1.0, 10);
        assertEquals(ClaimResult.REJECTED_LOWER_BID, contested2.result());
        assertEquals(SHIELD, b2.task("t").owner());
    }

    @Test void equalBidBreaksToEarlierAnnouncementTick(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.announceIntent("t", COPPER, 0.5, 2);   // earlier
        b.announceIntent("t", SHIELD, 0.5, 5);   // later
        b.claim("t", SHIELD, 1.0, 10);
        ClaimOutcome c = b.claim("t", COPPER, 1.0, 10);
        assertEquals(ClaimResult.WON_CONTEST, c.result());
        assertEquals(COPPER, b.task("t").owner());
    }

    @Test void equalBidAndAnnounceBreaksLexicographicallyByAgentId(){
        // No prior intent: announce tick falls back to claim tick (equal), so the
        // lexicographically smaller display name wins: agent-alpha < agent-beta.
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", BETA, 1.0, 10);
        ClaimOutcome c = b.claim("t", ALPHA, 1.0, 10);
        assertEquals(ClaimResult.WON_CONTEST, c.result());
        assertEquals(ALPHA, b.task("t").owner());
    }

    @Test void claimOnEarlierTickIsNotStealable(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", COPPER, 1.0, 10);
        ClaimOutcome later = b.claim("t", SHIELD, 5.0, 20); // higher bid but different tick
        assertEquals(ClaimResult.REJECTED_ALREADY_LEASED, later.result());
        assertEquals(COPPER, b.task("t").owner());
    }

    // ---- leases ----

    @Test void expiredLeaseReopensTask(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", COPPER, 1.0, 0);
        assertEquals(TaskStatus.CLAIMED, b.task("t").status());

        var expired = b.expireStale(TaskBoard.DEFAULT_LEASE_TICKS + 1);
        assertEquals(1, expired.size());
        assertEquals(TaskStatus.OPEN, b.task("t").status());
        assertNull(b.task("t").owner());

        // Now reclaimable by anyone.
        assertTrue(b.claim("t", SHIELD, 1.0, TaskBoard.DEFAULT_LEASE_TICKS + 2).granted());
    }

    @Test void heartbeatRenewsLeaseAndPreventsExpiry(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", COPPER, 1.0, 0);
        long half = TaskBoard.DEFAULT_LEASE_TICKS / 2;
        assertTrue(b.heartbeat("t", COPPER, half).ok());
        // Original lease would have lapsed here, but the heartbeat pushed it out.
        assertTrue(b.expireStale(TaskBoard.DEFAULT_LEASE_TICKS + 1).isEmpty());
        assertEquals(TaskStatus.CLAIMED, b.task("t").status());
        assertEquals(COPPER, b.task("t").owner());
    }

    @Test void heartbeatFromNonOwnerRejected(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", COPPER, 1.0, 0);
        OpResult r = b.heartbeat("t", SHIELD, 10);
        assertFalse(r.ok());
        assertEquals("not_owner", r.reason());
    }

    // ---- helper lifecycle ----

    @Test void helperOfferAcceptFulfilLifecycle(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.SUPPLY_TURRET), 0);
        b.claim("t", SHIELD, 1.0, 0);
        assertTrue(b.offerHelp("t", RELAY, "deliver 120 copper", 120, 5).ok());
        assertEquals(1, b.task("t").pendingOffers().size());

        assertTrue(b.acceptHelp("t", SHIELD, RELAY, 6).ok());
        assertEquals(0, b.task("t").pendingOffers().size());
        assertEquals(1, b.task("t").helpers().size());
        HelperContract c = b.task("t").helpers().get(0);
        assertFalse(c.fulfilled());

        assertTrue(b.reportHelpFulfilled("t", RELAY, 50).ok());
        assertTrue(b.task("t").helpers().get(0).fulfilled());
        assertEquals(50, b.task("t").helpers().get(0).fulfilledTick());
    }

    @Test void declineHelpRemovesOfferAndCreatesNoContract(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.SUPPLY_TURRET), 0);
        b.claim("t", SHIELD, 1.0, 0);
        b.offerHelp("t", RELAY, "deliver copper", 0, 5);
        assertTrue(b.declineHelp("t", SHIELD, RELAY, 6).ok());
        assertEquals(0, b.task("t").pendingOffers().size());
        assertEquals(0, b.task("t").helpers().size());
    }

    @Test void ownerCannotOfferHelpToOwnTask(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.SUPPLY_TURRET), 0);
        b.claim("t", SHIELD, 1.0, 0);
        OpResult r = b.offerHelp("t", SHIELD, "self", 0, 5);
        assertFalse(r.ok());
    }

    // ---- terminal transitions & reservations ----

    @Test void abandonReleasesReservations(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_SCHEMATIC), 0);
        b.claim("t", COPPER, 1.0, 0);
        b.reserveTile("t", COPPER, new Rect(0, 0, 3, 3), false, 1);
        b.reserveResource("t", COPPER, "copper", 40, false, 1);
        assertEquals(2, b.reservations().size());

        assertTrue(b.abandon("t", COPPER, "gave_up", 10).ok());
        assertEquals(TaskStatus.ABANDONED, b.task("t").status());
        assertEquals(0, b.reservations().size());
        assertNull(b.task("t").owner());
    }

    @Test void completeMarksProgressFullReleasesReservationsAndIsTerminal(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", COPPER, 1.0, 0);
        b.reserveTile("t", COPPER, Rect.ofTile(4, 4), false, 1);
        assertTrue(b.complete("t", COPPER, 10).ok());
        assertEquals(TaskStatus.COMPLETED, b.task("t").status());
        assertEquals(1.0, b.task("t").progress());
        assertEquals(0, b.reservations().size());
        // Cannot complete twice.
        assertFalse(b.complete("t", COPPER, 11).ok());
    }

    @Test void releaseReopensTaskAndReleasesReservations(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.DEFEND_REGION), 0);
        b.claim("t", SHIELD, 1.0, 0);
        b.reserveRegion("t", SHIELD, "east", false, 1);
        assertTrue(b.release("t", SHIELD, 10).ok());
        assertEquals(TaskStatus.OPEN, b.task("t").status());
        assertNull(b.task("t").owner());
        assertEquals(0, b.reservations().size());
    }

    // ---- safety properties (brief §23.5) ----

    @Test void exclusiveTaskNeverHasTwoValidOwners(){
        // Property: after any sequence of claims, at most one agent owns the task.
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        AgentId[] agents = {COPPER, SHIELD, RELAY, ALPHA, BETA};
        // Many agents contend at the same tick with varying bids.
        for(int i = 0; i < agents.length; i++){
            b.claim("t", agents[i], i * 0.1, 100);
        }
        // Exactly one owner, and it is the top bidder (BETA, bid 0.4).
        assertEquals(BETA, b.task("t").owner());
        long owners = b.tasks().stream().filter(s -> s.owner() != null).count();
        assertEquals(1, owners);
    }

    @Test void completionCannotBeRewardedTwice(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", COPPER, 1.0, 0);
        assertTrue(b.complete("t", COPPER, 5).ok());
        // Second completion, abandon, or release all rejected on a terminal task.
        assertFalse(b.complete("t", COPPER, 6).ok());
        assertFalse(b.abandon("t", COPPER, "x", 6).ok());
        assertFalse(b.release("t", COPPER, 6).ok());
    }

    @Test void resetClearsAllEpisodeLocalState(){
        TaskBoard b = board();
        b.propose(spec("t", TaskType.BUILD_LINE), 0);
        b.claim("t", COPPER, 1.0, 0);
        b.reserveTile("t", COPPER, Rect.ofTile(1, 1), false, 1);
        b.reset(99);
        assertEquals(99, b.episodeId());
        assertTrue(b.tasks().isEmpty());
        assertEquals(0, b.reservations().size());
        assertEquals(0, b.events().pendingCount());
        assertEquals(0, b.events().peekNextMessageId());
    }

    @Test void invalidOpsAreRejectedNotThrown(){
        TaskBoard b = board();
        assertEquals("unknown_task", b.heartbeat("nope", COPPER, 0).reason());
        assertEquals(ClaimResult.REJECTED_UNKNOWN_TASK, b.claim("nope", COPPER, 1.0, 0).result());
    }

    @Test void reservationOutcomeReflectsHumanOverrideThroughBoard(){
        TaskBoard b = board();
        b.propose(spec("a", TaskType.BUILD_SCHEMATIC), 0);
        b.propose(spec("h", TaskType.BUILD_SCHEMATIC), 0);
        b.claim("a", COPPER, 1.0, 0);
        b.reserveTile("a", COPPER, new Rect(0, 0, 2, 2), false, 1);
        // Human reserves overlapping area: agent yields, board emits a conflict event.
        ReservationOutcome out = b.reserveTile("h", SHIELD, new Rect(1, 1, 2, 2), true, 2);
        assertTrue(out.granted());
        assertEquals(1, out.conflicts().size());
        assertTrue(b.events().peek().stream()
            .anyMatch(e -> "yield_to_human".equals(e.reasonCode()) && e.announce()));
    }

    @Test void humanYieldLifecycleDoesNotDuplicateRenderedConflict(){
        TaskBoard b = board();
        b.propose(spec("a", TaskType.BUILD_SCHEMATIC), 0);
        b.claim("a", COPPER, 1.0, 0);
        b.reserveTile("a", COPPER, new Rect(0, 0, 2, 2), false, 1);
        b.reserveTile("human", SHIELD, new Rect(1, 1, 2, 2), true, 2);

        assertTrue(b.yieldToHuman("a", COPPER, 2).ok());
        assertEquals(TaskStatus.ABANDONED, b.task("a").status());
        assertEquals(1, b.events().peek().stream()
            .filter(e -> "yield_to_human".equals(e.reasonCode()) && e.announce()).count());
    }
}
