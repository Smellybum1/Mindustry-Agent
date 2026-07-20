package mindustry.rl;

import arc.util.serialization.*;
import mindustry.content.*;
import mindustry.game.*;
import mindustry.world.*;

import static mindustry.Vars.*;

/**
 * A tiny, fully in-code deterministic scenario for the M1 spike.
 *
 * <p>No map file is read: {@link mindustry.core.World#loadGenerator} is driven with a
 * procedural generator producing a flat {@code size x size} stone field, a rectangular
 * copper ore patch, and a single {@link mindustry.content.Blocks#coreShard} core for
 * {@link mindustry.game.Team#sharded}. No enemies, no waves — sandbox-minimal
 * (docs/ENGINE_NOTES.md §4.2).
 */
public final class Scenario{
    public static final String ID = "bootstrap-defense-v0";
    public static final int VERSION = 1;

    public final int size;
    public final int coreX;
    public final int coreY;

    public Scenario(int size){
        this.size = size;
        this.coreX = size / 2;
        this.coreY = size / 2;
    }

    /** Build the deterministic ruleset for this scenario. */
    public Rules buildRules(){
        Rules rules = new Rules();
        rules.waves = false;               //no wave schedule for M1
        rules.canGameOver = false;         //never auto-terminate; keeps runStateCheck off
        rules.fog = false;                 //no fog-of-war update path
        rules.pvp = false;
        rules.attackMode = false;
        rules.infiniteResources = false;
        rules.defaultTeam = Team.sharded;
        rules.waveTeam = Team.crux;
        rules.loadout = mindustry.type.ItemStack.list(Items.copper, 100);
        return rules;
    }

    /** Generate tiles in place: flat stone, a copper patch, one Sharded core. */
    public void generate(Tiles tiles){
        for(int x = 0; x < tiles.width; x++){
            for(int y = 0; y < tiles.height; y++){
                Block overlay = inCopperPatch(x, y) ? Blocks.oreCopper : Blocks.air;
                tiles.set(x, y, new Tile(x, y, Blocks.stone, overlay, Blocks.air));
            }
        }
        //core (multiblock; must be placed after tiles are populated, before endMapLoad)
        tiles.getn(coreX, coreY).setBlock(Blocks.coreShard, Team.sharded, 0);
    }

    private boolean inCopperPatch(int x, int y){
        //a fixed 6x6 copper patch offset from the core, well clear of the 3x3 core footprint
        int px = coreX + 6, py = coreY + 6;
        return x >= px && x < px + 6 && y >= py && y < py + 6;
    }

    /** Scenario metadata for the reset response. */
    public Jval metadata(){
        Jval m = Jval.newObject();
        m.put("scenario_id", ID);
        m.put("scenario_version", VERSION);
        m.put("size", size);
        m.put("core_x", coreX);
        m.put("core_y", coreY);
        return m;
    }

    /** Convenience: run the generator against the live world. */
    public void load(){
        world.loadGenerator(size, size, this::generate);
    }
}
