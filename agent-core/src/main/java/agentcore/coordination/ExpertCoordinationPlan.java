package agentcore.coordination;

import agentcore.skill.*;
import agentcore.task.*;

import java.util.*;

/** Immutable, engine-neutral scenario inputs for the shared scripted coordinator. */
public record ExpertCoordinationPlan(
    int coreX,
    int coreY,
    int tileSize,
    int waveCount,
    long winTick,
    Schematic line,
    Schematic defense,
    Schematic fortification,
    List<Schematic> expansions,
    List<TileTarget> mineTiles,
    List<TileTarget> referenceTurrets,
    Region defendRegion,
    Region rebuildRegion,
    Map<String, Integer> copperCosts
){
    public ExpertCoordinationPlan{
        if(tileSize <= 0) throw new IllegalArgumentException("tileSize must be positive");
        if(waveCount <= 0) throw new IllegalArgumentException("waveCount must be positive");
        Objects.requireNonNull(line, "line");
        Objects.requireNonNull(defense, "defense");
        Objects.requireNonNull(fortification, "fortification");
        expansions = List.copyOf(expansions);
        mineTiles = List.copyOf(mineTiles);
        referenceTurrets = List.copyOf(referenceTurrets);
        Objects.requireNonNull(defendRegion, "defendRegion");
        Objects.requireNonNull(rebuildRegion, "rebuildRegion");
        copperCosts = Collections.unmodifiableMap(new TreeMap<>(copperCosts));
        if(mineTiles.size() != 3) throw new IllegalArgumentException("exactly three mine tiles required");
        if(referenceTurrets.size() != 2){
            throw new IllegalArgumentException("exactly two reference turrets required");
        }
        if(expansions.size() != Math.max(0, waveCount - 1)){
            throw new IllegalArgumentException("one expansion per non-final wave required");
        }
    }

    public int copperCost(String block){
        Integer cost = copperCosts.get(block);
        if(cost == null) throw new IllegalArgumentException("missing copper cost for " + block);
        return cost;
    }

    public record Schematic(
        String name,
        int anchorX,
        int anchorY,
        int copperCost,
        List<BuildSpec> blocks
    ){
        public Schematic{
            if(name == null || name.isBlank()) throw new IllegalArgumentException("schematic name required");
            blocks = List.copyOf(blocks);
            if(blocks.isEmpty()) throw new IllegalArgumentException("schematic blocks required");
        }
    }

    public record Region(String id, int x, int y, int w, int h){
        public Region{
            if(id == null || id.isBlank()) throw new IllegalArgumentException("region id required");
            if(w <= 0 || h <= 0) throw new IllegalArgumentException("region dimensions must be positive");
        }
    }
}
