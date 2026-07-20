package agentcore.event;

import agentcore.AgentId;
import agentcore.CoordinationAct;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for the announcement rate limiter (brief §11.7): normal cooldown, urgent
 * bypass, duplicate suppression, and never announcing routine acts.
 */
class RateLimiterTest{

    private static final AgentId A = new AgentId(0, "agent-a");
    private static final AgentId B = new AgentId(1, "agent-b");

    @Test void firstNormalAnnouncementAllowed(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.ANNOUNCE_INTENT, "t1", 0, false));
    }

    @Test void normalCooldownSuppressesWithinWindow(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.ANNOUNCE_INTENT, "t1", 0, false));
        // Different task, but same agent within the cooldown window -> suppressed.
        assertFalse(rl.shouldAnnounce(A, CoordinationAct.CLAIM_TASK, "t2", 50, false));
        // After the cooldown elapses -> allowed again.
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.CLAIM_TASK, "t2", 100, false));
    }

    @Test void cooldownIsPerAgent(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.ANNOUNCE_INTENT, "t1", 0, false));
        // A different agent is not affected by A's cooldown.
        assertTrue(rl.shouldAnnounce(B, CoordinationAct.ANNOUNCE_INTENT, "t1", 1, false));
    }

    @Test void urgentBlockedBypassesCooldown(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.START_TASK, "t1", 0, false));
        // BLOCKED is inherently urgent -> bypasses the still-active cooldown.
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.BLOCKED, "t1", 10, false));
    }

    @Test void callerUrgentFlagBypassesCooldown(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.ANNOUNCE_INTENT, "t1", 0, false));
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.ABANDON, "t2", 10, true));
    }

    @Test void duplicateSuppressionAppliesEvenToUrgent(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.BLOCKED, "t1", 0, false));
        // Identical (agent, act, task) within the duplicate window -> suppressed,
        // even though BLOCKED is urgent.
        assertFalse(rl.shouldAnnounce(A, CoordinationAct.BLOCKED, "t1", 20, false));
        // Outside the duplicate window -> allowed again.
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.BLOCKED, "t1", 60, false));
    }

    @Test void routineActsNeverAnnounced(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertFalse(rl.shouldAnnounce(A, CoordinationAct.HEARTBEAT, "t1", 0, false));
        assertFalse(rl.shouldAnnounce(A, CoordinationAct.PROGRESS, "t1", 0, false));
        assertFalse(rl.shouldAnnounce(A, null, "t1", 0, false));
    }

    @Test void resetClearsBookkeeping(){
        RateLimiter rl = new RateLimiter(100, 50);
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.ANNOUNCE_INTENT, "t1", 0, false));
        rl.reset();
        // After reset the cooldown no longer applies.
        assertTrue(rl.shouldAnnounce(A, CoordinationAct.ANNOUNCE_INTENT, "t2", 1, false));
    }
}
