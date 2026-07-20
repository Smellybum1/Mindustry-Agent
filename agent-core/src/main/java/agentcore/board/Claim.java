package agentcore.board;

import agentcore.AgentId;

/**
 * An agent's bid for a task, retained so simultaneous claims can be resolved
 * deterministically (brief §11.5: "Simultaneous claims are resolved
 * deterministically by bid, then announcement tick, then agent ID").
 *
 * @param agent       the bidding agent
 * @param bid         the agent's computed utility/bid; higher wins
 * @param announceTick earliest tick the agent announced intent for this task
 *                     (falls back to the claim tick if no prior intent)
 * @param claimTick   tick the claim was submitted
 */
record Claim(AgentId agent, double bid, long announceTick, long claimTick){

    /**
     * Deterministic total order for contested claims made on the same tick.
     * Returns true if {@code this} should win over {@code other}: higher bid wins;
     * ties break to the earlier announcement tick; further ties break to the
     * lexicographically smaller {@code agent_id} (the display-name string).
     */
    boolean beats(Claim other){
        if(bid != other.bid) return bid > other.bid;
        if(announceTick != other.announceTick) return announceTick < other.announceTick;
        return agent.displayName().compareTo(other.agent.displayName()) < 0;
    }
}
