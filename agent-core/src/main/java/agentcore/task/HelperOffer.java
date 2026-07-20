package agentcore.task;

import agentcore.AgentId;

import java.util.Objects;

/**
 * A pending offer of help on a task, before the owner accepts or declines it
 * (brief §11.2 {@code OFFER_HELP}).
 *
 * <p>An offer becomes a binding {@link HelperContract} only when the task owner
 * accepts it. Offering help alone carries no reward or measured responsibility —
 * that is deliberate (brief §17.5: "Offer help without contributing" is a known
 * exploit; reward only accepted, measured contribution).
 *
 * @param helper       the agent offering to help
 * @param contribution short machine/human description, e.g. {@code "deliver copper"}
 * @param amount       quantitative contribution (e.g. item count); 0 if not quantified
 * @param offeredTick  tick at which the offer was made
 */
public record HelperOffer(AgentId helper, String contribution, int amount, long offeredTick){
    public HelperOffer{
        Objects.requireNonNull(helper, "helper");
        Objects.requireNonNull(contribution, "contribution");
        if(amount < 0) throw new IllegalArgumentException("amount must be >= 0");
    }
}
