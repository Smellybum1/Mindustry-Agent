package agentcore.task;

/**
 * A single tile, addressed by integer grid coordinates (brief §10.2).
 *
 * @param x tile column (world tile units, not pixels)
 * @param y tile row
 */
public record TileTarget(int x, int y) implements Target{
    @Override public String describe(){
        return "tile (" + x + ", " + y + ")";
    }
}
