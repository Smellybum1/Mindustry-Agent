package agentcore.candidates;

/** Scenario- and engine-derived readiness for the current or next enemy wave. */
public record DefenseReadinessSnapshot(
    int waveNumber,
    int expectedEnemies,
    double expectedEnemyHealth,
    double incomingDps,
    int requiredAmmo,
    int targetAmmoPerTurret,
    int readyTurrets,
    int requiredTurrets,
    int totalAmmo,
    double ammoCoverage,
    double healthCoverage,
    double turretCoverage,
    double readiness,
    int defendLeadTicks,
    double waveImminence
){
    public DefenseReadinessSnapshot{
        if(waveNumber < 1 || expectedEnemies < 0 || expectedEnemyHealth < 0.0
            || incomingDps < 0.0 || requiredAmmo < 0 || targetAmmoPerTurret < 0
            || readyTurrets < 0 || requiredTurrets < 1 || totalAmmo < 0
            || defendLeadTicks < 0){
            throw new IllegalArgumentException("invalid defense readiness counts");
        }
        ammoCoverage = clamp(ammoCoverage);
        healthCoverage = clamp(healthCoverage);
        turretCoverage = clamp(turretCoverage);
        readiness = clamp(readiness);
        waveImminence = clamp(waveImminence);
    }

    private static double clamp(double value){
        if(!Double.isFinite(value)) throw new IllegalArgumentException("readiness must be finite");
        return Math.max(0.0, Math.min(1.0, value));
    }
}
