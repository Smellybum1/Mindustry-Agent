package agentcore.reservation;

import agentcore.AgentId;

import java.util.Objects;

/** A reservation of a named region of responsibility (brief §11.6). */
public record RegionReservation(String taskId, AgentId agent, String regionId, boolean human) implements Reservation{
    public RegionReservation{
        Objects.requireNonNull(taskId, "taskId");
        Objects.requireNonNull(agent, "agent");
        Objects.requireNonNull(regionId, "regionId");
    }
}
