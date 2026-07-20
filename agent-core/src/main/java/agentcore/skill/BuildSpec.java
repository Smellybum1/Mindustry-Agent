package agentcore.skill;

/** One ordered, anchor-relative block entry in a data-backed schematic. */
public record BuildSpec(String block, int offsetX, int offsetY, int rotation){
    public BuildSpec{
        if(block == null || block.isBlank()) throw new IllegalArgumentException("block is blank");
        if(rotation < 0 || rotation > 3) throw new IllegalArgumentException("rotation must be 0..3");
    }
}
