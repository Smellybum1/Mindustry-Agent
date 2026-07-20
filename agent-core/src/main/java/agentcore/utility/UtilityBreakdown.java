package agentcore.utility;

/**
 * The per-term weighted contributions to a task's utility, plus the {@link #total()}
 * (brief §11.1). Returned by {@link HandTunedUtility#breakdown} so the scoring
 * stays transparent and inspectable in telemetry — every additive term is
 * separately visible, mirroring the "record every reward component separately"
 * discipline of brief §3/§17.6.
 *
 * <p>Cost terms are stored as their signed contribution (negative), so
 * {@link #total()} is a plain sum of every field.
 */
public record UtilityBreakdown(
    double teamValue,
    double urgency,
    double capabilityFit,
    double roleFit,
    double proximity,
    double helpSynergy,
    double humanPriority,
    double travelCost,
    double resourceCost,
    double duplicationRisk,
    double switchingCost,
    double danger,
    double uncertainty
){
    /** Sum of all weighted term contributions. */
    public double total(){
        return teamValue + urgency + capabilityFit + roleFit + proximity + helpSynergy + humanPriority
            + travelCost + resourceCost + duplicationRisk + switchingCost + danger + uncertainty;
    }
}
