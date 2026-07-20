package agentcore.utility;

/**
 * Weights for the additive task-selection utility (brief §11.1). Each weight is a
 * non-negative multiplier applied to the corresponding {@link UtilityFeatures}
 * term; the utility function applies the sign (positive terms add, cost terms
 * subtract), so weights themselves stay non-negative and readable.
 *
 * <p>The defaults are the transparent hand-tuned starting point of brief §11.1
 * ("Start with transparent hand-tuned terms"). {@code humanPriority} dominates so
 * human-created work outranks autonomous work (brief §20.2); {@code teamValue} and
 * {@code urgency} are the primary autonomous drivers; {@code duplicationRisk} and
 * {@code switchingCost} are penalized enough to discourage thrashing and duplicate
 * effort (brief §17.3). These are documented defaults, not tuned constants — the
 * learned policy will eventually subsume this scoring (brief §11.1, §16.6).
 *
 * <p>Immutable; use {@link #defaults()} or {@link #builder()}.
 */
public final class UtilityWeights{
    private final double teamValue;
    private final double urgency;
    private final double capabilityFit;
    private final double roleFit;
    private final double proximity;
    private final double helpSynergy;
    private final double humanPriority;
    private final double travelCost;
    private final double resourceCost;
    private final double duplicationRisk;
    private final double switchingCost;
    private final double danger;
    private final double uncertainty;

    private UtilityWeights(Builder b){
        this.teamValue = b.teamValue;
        this.urgency = b.urgency;
        this.capabilityFit = b.capabilityFit;
        this.roleFit = b.roleFit;
        this.proximity = b.proximity;
        this.helpSynergy = b.helpSynergy;
        this.humanPriority = b.humanPriority;
        this.travelCost = b.travelCost;
        this.resourceCost = b.resourceCost;
        this.duplicationRisk = b.duplicationRisk;
        this.switchingCost = b.switchingCost;
        this.danger = b.danger;
        this.uncertainty = b.uncertainty;
    }

    /** The documented hand-tuned defaults (brief §11.1). */
    public static UtilityWeights defaults(){
        return builder()
            .teamValue(1.0)
            .urgency(1.0)
            .capabilityFit(0.8)
            .roleFit(0.5)
            .proximity(0.3)
            .helpSynergy(0.4)
            .humanPriority(2.0)
            .travelCost(0.3)
            .resourceCost(0.2)
            .duplicationRisk(1.0)
            .switchingCost(0.5)
            .danger(0.6)
            .uncertainty(0.3)
            .build();
    }

    public double teamValue(){ return teamValue; }
    public double urgency(){ return urgency; }
    public double capabilityFit(){ return capabilityFit; }
    public double roleFit(){ return roleFit; }
    public double proximity(){ return proximity; }
    public double helpSynergy(){ return helpSynergy; }
    public double humanPriority(){ return humanPriority; }
    public double travelCost(){ return travelCost; }
    public double resourceCost(){ return resourceCost; }
    public double duplicationRisk(){ return duplicationRisk; }
    public double switchingCost(){ return switchingCost; }
    public double danger(){ return danger; }
    public double uncertainty(){ return uncertainty; }

    public static Builder builder(){ return new Builder(); }

    /** Fluent builder; every weight defaults to 0 (use {@link #defaults()} for the tuned set). */
    public static final class Builder{
        private double teamValue;
        private double urgency;
        private double capabilityFit;
        private double roleFit;
        private double proximity;
        private double helpSynergy;
        private double humanPriority;
        private double travelCost;
        private double resourceCost;
        private double duplicationRisk;
        private double switchingCost;
        private double danger;
        private double uncertainty;

        public Builder teamValue(double v){ this.teamValue = v; return this; }
        public Builder urgency(double v){ this.urgency = v; return this; }
        public Builder capabilityFit(double v){ this.capabilityFit = v; return this; }
        public Builder roleFit(double v){ this.roleFit = v; return this; }
        public Builder proximity(double v){ this.proximity = v; return this; }
        public Builder helpSynergy(double v){ this.helpSynergy = v; return this; }
        public Builder humanPriority(double v){ this.humanPriority = v; return this; }
        public Builder travelCost(double v){ this.travelCost = v; return this; }
        public Builder resourceCost(double v){ this.resourceCost = v; return this; }
        public Builder duplicationRisk(double v){ this.duplicationRisk = v; return this; }
        public Builder switchingCost(double v){ this.switchingCost = v; return this; }
        public Builder danger(double v){ this.danger = v; return this; }
        public Builder uncertainty(double v){ this.uncertainty = v; return this; }

        public UtilityWeights build(){ return new UtilityWeights(this); }
    }
}
