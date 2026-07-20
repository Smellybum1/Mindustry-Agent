package agentcore.candidates;

/** Stable live turret facts; generator sorts these by {@code entityId}. */
public record TurretSnapshot(long entityId, int tileX, int tileY, int totalAmmo){
    public TurretSnapshot{
        if(entityId < 0L) throw new IllegalArgumentException("entityId must be >= 0");
        if(totalAmmo < 0) throw new IllegalArgumentException("totalAmmo must be >= 0");
    }
}
