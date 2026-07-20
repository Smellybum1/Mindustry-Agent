package agentcore.reservation;

import agentcore.AgentId;

/**
 * A record that an agent reservation yielded to a human reservation, or that two
 * agent reservations collided (brief §11.6, §20.2). Emitted so the agent can
 * "yield and announce the conflict once rather than fighting the player".
 *
 * @param tick          tick the conflict was detected
 * @param yieldedTaskId task whose reservation was rejected or removed
 * @param yieldedAgent  agent that yielded
 * @param winnerTaskId  task whose reservation prevailed
 * @param winnerAgent   agent (or human proxy) that prevailed
 * @param winnerHuman   whether the winner is a human reservation
 * @param detail        short human-readable description
 */
public record ReservationConflict(
    long tick,
    String yieldedTaskId,
    AgentId yieldedAgent,
    String winnerTaskId,
    AgentId winnerAgent,
    boolean winnerHuman,
    String detail
){}
