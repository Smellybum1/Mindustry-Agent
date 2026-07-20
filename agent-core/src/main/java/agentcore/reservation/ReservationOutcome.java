package agentcore.reservation;

import java.util.List;

/**
 * The result of attempting to acquire a reservation: whether it was granted, the
 * categorized {@link ReservationResult}, and any conflicts produced (agent
 * reservations that yielded to a human, or the collision that caused a rejection).
 *
 * @param result   categorized outcome
 * @param conflicts conflicts produced or encountered; never null, possibly empty
 */
public record ReservationOutcome(ReservationResult result, List<ReservationConflict> conflicts){
    public ReservationOutcome{
        conflicts = conflicts == null ? List.of() : List.copyOf(conflicts);
    }

    public boolean granted(){ return result.granted(); }

    static ReservationOutcome ofGranted(){
        return new ReservationOutcome(ReservationResult.GRANTED, List.of());
    }

    static ReservationOutcome ofHumanOverride(List<ReservationConflict> yielded){
        return new ReservationOutcome(ReservationResult.GRANTED_HUMAN_OVERRIDE, yielded);
    }

    static ReservationOutcome ofRejected(ReservationResult result, ReservationConflict conflict){
        return new ReservationOutcome(result, conflict == null ? List.of() : List.of(conflict));
    }
}
