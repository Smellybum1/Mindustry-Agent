package agentcore.utility;

/**
 * The raw, unweighted feature terms feeding the task-selection utility (brief
 * §11.1). Positive terms increase desirability; the "cost" terms are stored as
 * non-negative magnitudes and subtracted by the utility function. All terms
 * default to 0, so a {@link agentcore.utility.FeatureSource} need only populate
 * the ones it can compute; the rest contribute nothing.
 *
 * <p>These values are engine-derived and therefore filled in later by the engine
 * adapter (proximity, travel cost, danger, etc. need real world state). The board
 * and utility scaffold stay headless; see {@code docs/COORDINATION.md}.
 *
 * <p>Immutable; construct via {@link #builder()}.
 */
public final class UtilityFeatures{
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

    private UtilityFeatures(Builder b){
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

    /** Fluent builder; every term defaults to 0. */
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

        public UtilityFeatures build(){ return new UtilityFeatures(this); }
    }
}
