package agentcore.reservation;

/**
 * An axis-aligned rectangle of tiles, used for tile/schematic footprint
 * reservations (brief §11.6). Half-open in the usual grid sense: it covers
 * columns {@code [x, x+w)} and rows {@code [y, y+h)}.
 *
 * @param x left tile column
 * @param y bottom tile row
 * @param w width in tiles, &gt; 0
 * @param h height in tiles, &gt; 0
 */
public record Rect(int x, int y, int w, int h){
    public Rect{
        if(w <= 0 || h <= 0) throw new IllegalArgumentException("rect must have positive extent");
    }

    /** A 1x1 rectangle covering a single tile. */
    public static Rect ofTile(int x, int y){
        return new Rect(x, y, 1, 1);
    }

    /** True if this rectangle shares at least one tile with {@code other}. */
    public boolean overlaps(Rect other){
        return x < other.x + other.w
            && other.x < x + w
            && y < other.y + other.h
            && other.y < y + h;
    }
}
