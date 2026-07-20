package agentcore.reservation;

import agentcore.AgentId;

import java.util.Objects;

/** A reservation of a quantity of a resource item against a notional budget. */
public record ResourceReservation(String taskId, AgentId agent, String item, int amount, boolean human) implements Reservation{
    public ResourceReservation{
        Objects.requireNonNull(taskId, "taskId");
        Objects.requireNonNull(agent, "agent");
        Objects.requireNonNull(item, "item");
        if(amount < 0) throw new IllegalArgumentException("reserved amount must be non-negative");
    }
}
