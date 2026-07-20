package agentcore.reservation;

import agentcore.AgentId;

import java.util.Objects;

/** A reservation over a rectangle of tiles (target tiles / schematic footprint). */
public record TileReservation(String taskId, AgentId agent, Rect area, boolean human) implements Reservation{
    public TileReservation{
        Objects.requireNonNull(taskId, "taskId");
        Objects.requireNonNull(agent, "agent");
        Objects.requireNonNull(area, "area");
    }
}
