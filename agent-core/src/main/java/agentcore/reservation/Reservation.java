package agentcore.reservation;

import agentcore.AgentId;

/**
 * A soft reservation held against the shared world (brief §11.6). Reservations
 * prevent agents from placing conflicting blocks or spending the same notional
 * resource budget; they are advisory ("soft") and tied to a task's lifecycle —
 * the board releases all of a task's reservations when it terminates.
 *
 * <p>The {@link #human()} flag encodes the override rule (brief §11.6, §20.2):
 * "Humans always have override priority." A human reservation always wins a
 * conflict; an overlapping agent reservation yields.
 */
public sealed interface Reservation permits TileReservation, ResourceReservation, RegionReservation{
    /** Owning task id; reservations are released together with this task. */
    String taskId();
    /** Agent (or human proxy) that holds the reservation. */
    AgentId agent();
    /** Whether this is a human reservation and therefore wins all conflicts. */
    boolean human();
}
