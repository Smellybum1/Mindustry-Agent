package agentcore.event;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/** Tests the drainable event log and its monotonic message-id counter (brief §11.3, §21.2). */
class EventLogTest{

    private static CoordinationEvent ev(long id){
        return CoordinationEvent.builder().messageId(id).tick(id).taskId("t").build();
    }

    @Test void messageIdsAreMonotonicAndSurviveDrain(){
        EventLog log = new EventLog();
        assertEquals(0, log.nextMessageId());
        assertEquals(1, log.nextMessageId());
        log.append(ev(2));
        assertEquals(1, log.pendingCount());
        List<CoordinationEvent> drained = log.drain();
        assertEquals(1, drained.size());
        assertEquals(0, log.pendingCount());
        // Counter is not reset by draining.
        assertEquals(2, log.nextMessageId());
    }

    @Test void drainReturnsEventsInOrderThenClears(){
        EventLog log = new EventLog();
        log.append(ev(0));
        log.append(ev(1));
        List<CoordinationEvent> first = log.drain();
        assertEquals(2, first.size());
        assertEquals(0, first.get(0).messageId());
        assertEquals(1, first.get(1).messageId());
        assertTrue(log.drain().isEmpty());
    }

    @Test void resetClearsCounterAndPending(){
        EventLog log = new EventLog();
        log.nextMessageId();
        log.append(ev(9));
        log.reset();
        assertEquals(0, log.peekNextMessageId());
        assertEquals(0, log.pendingCount());
    }
}
