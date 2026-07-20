package agentcore.reservation;

/** Outcome category for a reservation acquisition (see {@link ReservationOutcome}). */
public enum ReservationResult{
    /** Reservation granted with no conflict. */
    GRANTED,
    /** Granted for a human, forcing one or more overlapping agent reservations to yield. */
    GRANTED_HUMAN_OVERRIDE,
    /** Rejected: overlaps an incompatible reservation held by another agent. */
    REJECTED_OVERLAP,
    /** Rejected: overlaps a human reservation, which has priority. */
    REJECTED_HUMAN_PRIORITY,
    /** Rejected: would exceed the configured resource budget for the item. */
    REJECTED_CAPACITY;

    /** Whether the reservation was actually acquired. */
    public boolean granted(){
        return this == GRANTED || this == GRANTED_HUMAN_OVERRIDE;
    }
}
