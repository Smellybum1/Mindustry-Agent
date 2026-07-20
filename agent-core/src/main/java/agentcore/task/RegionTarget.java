package agentcore.task;

import java.util.Objects;

/**
 * A named region of the map (brief §11.4 {@code {"region_id": "east-defense"}}).
 *
 * <p>Regions are opaque scenario-defined identifiers; the coordination layer does
 * not resolve them to geometry. The engine adapter owns the region-to-rect map.
 *
 * @param regionId scenario-defined region identifier, e.g. {@code "east-defense"}
 */
public record RegionTarget(String regionId) implements Target{
    public RegionTarget{
        Objects.requireNonNull(regionId, "regionId");
    }

    @Override public String describe(){
        return "region " + regionId;
    }
}
