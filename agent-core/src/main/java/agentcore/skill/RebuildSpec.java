package agentcore.skill;

/** One immutable, engine-free view of a queued destroyed team block. */
public record RebuildSpec(String block, int tileX, int tileY, int rotation){
    public RebuildSpec{
        if(block == null || block.isBlank()) throw new IllegalArgumentException("block is blank");
        if(rotation < 0 || rotation > 3) throw new IllegalArgumentException("rotation must be 0..3");
    }
}
