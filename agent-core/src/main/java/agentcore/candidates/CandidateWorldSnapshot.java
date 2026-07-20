package agentcore.candidates;

import java.util.List;

/**
 * Engine-free scenario/world facts consumed by the M5.1 rule catalog.
 * Coordinates are world units for distance masking and named regions remain opaque.
 */
public record CandidateWorldSnapshot(
    long tick,
    int tileSize,
    String harvestTaskId,
    String buildLineTaskId,
    String schematicTaskId,
    String supplyTaskId,
    String rebuildTaskId,
    String defendTaskId,
    int coreCopper,
    int harvestCopperThreshold,
    boolean buildLineComplete,
    int buildLineCopperCost,
    boolean schematicComplete,
    int schematicCopperCost,
    float harvestWorldX,
    float harvestWorldY,
    float buildLineWorldX,
    float buildLineWorldY,
    String buildLineId,
    float schematicWorldX,
    float schematicWorldY,
    String schematicId,
    List<TurretSnapshot> turrets,
    int turretTargetAmmo,
    int brokenBlockCount,
    float rebuildWorldX,
    float rebuildWorldY,
    String rebuildRegionId,
    int enemyCount,
    float timeToNextWave,
    int defendLeadTicks,
    float defendWorldX,
    float defendWorldY,
    String defendRegionId
){
    public CandidateWorldSnapshot{
        if(tileSize <= 0 || coreCopper < 0 || harvestCopperThreshold < 0
            || buildLineCopperCost < 0 || schematicCopperCost < 0
            || turretTargetAmmo < 0 || brokenBlockCount < 0 || enemyCount < 0
            || defendLeadTicks < 0){
            throw new IllegalArgumentException("candidate counts/costs must be non-negative");
        }
        schematicId = requireName(schematicId, "schematicId");
        harvestTaskId = requireName(harvestTaskId, "harvestTaskId");
        buildLineTaskId = requireName(buildLineTaskId, "buildLineTaskId");
        schematicTaskId = requireName(schematicTaskId, "schematicTaskId");
        supplyTaskId = requireName(supplyTaskId, "supplyTaskId");
        rebuildTaskId = requireName(rebuildTaskId, "rebuildTaskId");
        defendTaskId = requireName(defendTaskId, "defendTaskId");
        buildLineId = requireName(buildLineId, "buildLineId");
        rebuildRegionId = requireName(rebuildRegionId, "rebuildRegionId");
        defendRegionId = requireName(defendRegionId, "defendRegionId");
        turrets = List.copyOf(turrets == null ? List.of() : turrets);
    }

    private static String requireName(String value, String field){
        if(value == null || value.isBlank()) throw new IllegalArgumentException(field + " is required");
        return value;
    }
}
