package agentcore.task;

import agentcore.AgentId;

import java.util.Objects;

/**
 * An accepted, explicit contribution contract between a task owner and a helper
 * (brief §11.5: "Helpers own explicit subtasks or contribution contracts; they
 * should not merely follow the lead agent without measurable responsibility").
 *
 * <p>Created when an owner accepts a {@link HelperOffer}. The {@link #fulfilled}
 * flag is the single point of mutation and is flipped exactly once, by the board,
 * when the helper reports the contribution delivered. This is what makes
 * "accepted helper contract successfully fulfilled" a rewardable, measurable
 * event (brief §17.1) rather than mere help-offer volume.
 */
public final class HelperContract{
    private final AgentId helper;
    private final String contribution;
    private final int amount;
    private final long acceptedTick;
    private boolean fulfilled;
    private long fulfilledTick = -1;

    public HelperContract(AgentId helper, String contribution, int amount, long acceptedTick){
        this.helper = Objects.requireNonNull(helper, "helper");
        this.contribution = Objects.requireNonNull(contribution, "contribution");
        if(amount < 0) throw new IllegalArgumentException("amount must be >= 0");
        this.amount = amount;
        this.acceptedTick = acceptedTick;
    }

    /** Build a contract from an accepted offer. */
    public static HelperContract fromOffer(HelperOffer offer, long acceptedTick){
        return new HelperContract(offer.helper(), offer.contribution(), offer.amount(), acceptedTick);
    }

    public AgentId helper(){ return helper; }
    public String contribution(){ return contribution; }
    public int amount(){ return amount; }
    public long acceptedTick(){ return acceptedTick; }
    public boolean fulfilled(){ return fulfilled; }
    /** Tick the contract was fulfilled, or -1 if not yet fulfilled. */
    public long fulfilledTick(){ return fulfilledTick; }

    /**
     * Mark the contract fulfilled (called by the board, the single writer).
     * Throws if already fulfilled so double-fulfilment is caught rather than
     * silently re-rewarded (brief §17.5).
     */
    public void markFulfilled(long tick){
        if(fulfilled) throw new IllegalStateException("helper contract already fulfilled");
        this.fulfilled = true;
        this.fulfilledTick = tick;
    }

    @Override public String toString(){
        return "HelperContract[" + helper.displayName() + " " + contribution
            + (amount > 0 ? " x" + amount : "") + (fulfilled ? " (fulfilled)" : " (pending)") + "]";
    }
}
