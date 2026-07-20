package agentcore.utility;

import agentcore.AgentId;
import agentcore.task.TaskSpec;

import java.util.Objects;

/**
 * A transparent, hand-tuned implementation of the additive utility of brief §11.1:
 *
 * <pre>
 * utility = team_value + urgency + capability_fit + role_fit + proximity
 *         + help_synergy + human_priority
 *         - travel_cost - resource_cost - duplication_risk - switching_cost
 *         - danger - uncertainty
 * </pre>
 *
 * <p>Raw feature magnitudes come from a pluggable {@link FeatureSource} (filled in
 * by the engine adapter later); {@link UtilityWeights} scales each term. The class
 * is a deterministic pure function of its inputs — no randomness, no wall-clock —
 * and exposes a {@link #breakdown} so the score stays inspectable.
 */
public final class HandTunedUtility implements TaskUtility{
    private final FeatureSource features;
    private final UtilityWeights weights;

    /** Uses {@link UtilityWeights#defaults()}. */
    public HandTunedUtility(FeatureSource features){
        this(features, UtilityWeights.defaults());
    }

    public HandTunedUtility(FeatureSource features, UtilityWeights weights){
        this.features = Objects.requireNonNull(features, "features");
        this.weights = Objects.requireNonNull(weights, "weights");
    }

    @Override public double score(AgentId agent, TaskSpec task, long tick){
        return breakdown(agent, task, tick).total();
    }

    /** The full per-term breakdown of the score, for telemetry and testing. */
    public UtilityBreakdown breakdown(AgentId agent, TaskSpec task, long tick){
        UtilityFeatures f = features.featuresFor(agent, task, tick);
        return new UtilityBreakdown(
            weights.teamValue()       * f.teamValue(),
            weights.urgency()         * f.urgency(),
            weights.capabilityFit()   * f.capabilityFit(),
            weights.roleFit()         * f.roleFit(),
            weights.proximity()       * f.proximity(),
            weights.helpSynergy()     * f.helpSynergy(),
            weights.humanPriority()   * f.humanPriority(),
            -weights.travelCost()     * f.travelCost(),
            -weights.resourceCost()   * f.resourceCost(),
            -weights.duplicationRisk()* f.duplicationRisk(),
            -weights.switchingCost()  * f.switchingCost(),
            -weights.danger()         * f.danger(),
            -weights.uncertainty()    * f.uncertainty()
        );
    }
}
