package agentcore.event;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * An append-only, drainable log of {@link CoordinationEvent}s with a monotonic
 * {@code message_id} counter (brief §11.3 {@code message_id}, §21.2 event log).
 *
 * <p>The board appends here on every transition. Callers (telemetry, the protocol
 * serializer) periodically {@link #drain()} the accumulated events. Draining
 * returns everything logged since the last drain and clears the buffer; the
 * message-id counter is <em>not</em> reset by draining, only by {@link #reset()}
 * at episode boundaries, so ids stay unique within an episode.
 *
 * <p>Single-threaded by contract (brief §23.6); not synchronized.
 */
public final class EventLog{
    private final List<CoordinationEvent> pending = new ArrayList<>();
    private long nextMessageId;

    /** Allocate the next monotonic message id. */
    public long nextMessageId(){
        return nextMessageId++;
    }

    /** The id that will be returned by the next {@link #nextMessageId()} call. */
    public long peekNextMessageId(){
        return nextMessageId;
    }

    /** Append an event to the pending buffer. */
    public void append(CoordinationEvent event){
        pending.add(event);
    }

    /** Number of events waiting to be drained. */
    public int pendingCount(){
        return pending.size();
    }

    /** A read-only view of pending events without draining. */
    public List<CoordinationEvent> peek(){
        return Collections.unmodifiableList(pending);
    }

    /**
     * Return and remove all pending events in insertion order. The message-id
     * counter is preserved so ids remain unique across drains.
     */
    public List<CoordinationEvent> drain(){
        List<CoordinationEvent> out = new ArrayList<>(pending);
        pending.clear();
        return out;
    }

    /** Clear pending events and reset the message-id counter (episode reset). */
    public void reset(){
        pending.clear();
        nextMessageId = 0;
    }
}
