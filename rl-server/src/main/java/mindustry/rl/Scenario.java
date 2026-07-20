package mindustry.rl;

import agentcore.skill.*;
import arc.struct.*;
import arc.util.serialization.*;
import mindustry.content.*;
import mindustry.ctype.*;
import mindustry.game.*;
import mindustry.type.*;
import mindustry.world.*;

import java.io.*;
import java.nio.charset.*;
import java.util.*;

import static mindustry.Vars.*;

/**
 * The full {@code bootstrap-defense-v0} scenario, driven entirely by the checked-in
 * machine-readable spec {@code scenarios/bootstrap-defense-v0/scenario.json}
 * (schema: {@code scenarios/schemas/README.md}; prose: {@code docs/SCENARIOS.md}).
 *
 * <p><b>Single source of truth.</b> The JSON is copied verbatim onto the rl-server
 * classpath at build time (see {@code rl-server/build.gradle} {@code processResources})
 * and parsed here at construction — no scenario constant is hardcoded, so the JSON and
 * the loaded world can never drift.
 *
 * <p>The world is built procedurally (no {@code .msav} on disk, docs/ENGINE_NOTES.md
 * §4.2) via {@link mindustry.core.World#loadGenerator}: a flat {@code stone} field with
 * ore-overlay patches, one {@code Blocks.spawn} overlay at the east enemy spawn, and one
 * {@code coreShard} for the {@code sharded} team. Enemy waves are configured on
 * {@code state.rules.spawns} and driven by the engine's native wave timer, which is
 * <b>tick-exact under the fixed {@code 1/60} step</b> ({@code state.wavetime} decrements by
 * {@code Time.delta == 1.0} each tick): waves fire at exactly the JSON ticks with no
 * wall-clock dependency (docs/UPSTREAM_PATCHES.md, docs/STATUS.md).
 */
public final class Scenario{
    /** Classpath location the JSON is copied to by {@code processResources}. */
    private static final String RESOURCE = "/scenarios/bootstrap-defense-v0/scenario.json";

    public final String id;
    public final int version;

    public final int width, height;
    public final Block floor;
    public final Block coreBlock;
    public final Team coreTeam;
    public final int coreX, coreY;

    /** Starting core loadout (zero-amount items dropped). */
    public final Seq<ItemStack> loadout = new Seq<>();

    /** Ore patches: overlay ore floors placed on top of {@link #floor}. */
    public final Seq<OrePatch> orePatches = new Seq<>();

    /** Enemy ground spawn tiles ({@code Blocks.spawn} overlays); v0 has one, east. */
    public final Seq<SpawnPoint> spawnPoints = new Seq<>();

    public final Team waveTeam;
    public final int unitCap;
    public final boolean canGameOver;

    /** Native-wave-timer parameters derived from the (uniform-spaced) wave schedule. */
    public final int initialWaveSpacing;   //ticks until wave 1
    public final int waveSpacing;          //ticks between subsequent waves
    public final Seq<SpawnGroup> spawnGroups = new Seq<>();
    public final int waveCount;

    /** Termination parameters (docs/SCENARIOS.md §Rules). */
    public final int winTick;              //core-alive-at-tick win predicate
    public final int tickCap;              //hard truncation tick

    /** Allowed content ids (whitelist); pre-unlocked so there is no tech tree. */
    public final Seq<UnlockableContent> allowedContent = new Seq<>();
    /** Data-backed schematic catalog, keyed by wire/action name. */
    public final ObjectMap<String, SchematicSpec> schematics = new ObjectMap<>();

    private final Jval raw;

    public Scenario(){
        this.raw = readSpec();

        this.id = raw.getString("scenario_id", "bootstrap-defense-v0");
        this.version = raw.getInt("scenario_version", 1);

        Jval world = raw.get("world");
        this.width = world.getInt("width", 48);
        this.height = world.getInt("height", 48);
        this.floor = block(world.getString("floor", "stone"));

        Jval core = raw.get("core");
        this.coreBlock = block(core.getString("block", "core-shard"));
        this.coreTeam = team(core.getString("team", "sharded"));
        Jval center = core.get("center");
        this.coreX = center.asArray().get(0).asInt();
        this.coreY = center.asArray().get(1).asInt();

        Jval load = raw.get("loadout");
        if(load != null){
            Jval.JsonMap map = load.asObject();
            for(int i = 0; i < map.size; i++){
                int amount = map.getValueAt(i).asInt();
                if(amount > 0) loadout.add(new ItemStack(item(map.getKeyAt(i)), amount));
            }
        }

        for(Jval patch : raw.get("ore_patches").asArray()){
            Jval rect = patch.get("rect");
            orePatches.add(new OrePatch(
                block(patch.getString("ore", "ore-copper")),
                rect.getInt("x", 0), rect.getInt("y", 0),
                rect.getInt("w", 0), rect.getInt("h", 0)));
        }

        for(Jval spawn : raw.get("enemy_spawns").asArray()){
            Jval tile = spawn.get("tile");
            spawnPoints.add(new SpawnPoint(
                tile.asArray().get(0).asInt(), tile.asArray().get(1).asInt()));
        }

        Jval rules = raw.get("rules");
        this.waveTeam = team(rules.getString("wave_team", "crux"));
        this.unitCap = rules.getInt("unit_cap", 6);
        this.canGameOver = rules.getBool("can_game_over", true);

        //allowed content whitelist -> pre-unlocked (no tech tree)
        Jval allowed = raw.get("allowed_content");
        if(allowed != null){
            Jval blocks = allowed.get("blocks");
            if(blocks != null) for(Jval b : blocks.asArray()) allowedContent.add(block(b.asString()));
            Jval units = allowed.get("units");
            if(units != null) for(Jval u : units.asArray()) allowedContent.add((UnlockableContent)content.unit(u.asString()));
        }

        Jval reference = raw.get("reference_schematic");
        if(reference != null){
            loadSchematic(reference.getString("path", ""), reference.getString("id", ""));
        }

        //--- wave schedule -> native wave timer + per-wave SpawnGroups -----------------
        Jval schedule = raw.get("wave_schedule");
        Seq<Jval> waves = new Seq<>();
        for(Jval w : schedule.asArray()) waves.add(w);
        this.waveCount = waves.size;
        if(waveCount == 0) throw new IllegalStateException("wave_schedule is empty");

        int firstTick = waves.get(0).getInt("tick", 0);
        int spacing = waveCount > 1 ? waves.get(1).getInt("tick", 0) - firstTick : 0;
        //the native timer is uniform-spaced; require the JSON schedule to match so ticks stay exact.
        for(int i = 1; i < waveCount; i++){
            int gap = waves.get(i).getInt("tick", 0) - waves.get(i - 1).getInt("tick", 0);
            if(gap != spacing){
                throw new IllegalStateException("wave_schedule is not uniformly spaced (gap " + gap
                    + " != " + spacing + " at wave " + i + "); drive spawns explicitly instead");
            }
        }
        this.initialWaveSpacing = firstTick;
        this.waveSpacing = spacing <= 0 ? Math.max(1, firstTick) : spacing;

        //one SpawnGroup per (wave, unit) — begin==end pins it to a single wave, so any
        //per-wave composition from the JSON is reproduced exactly (no arithmetic scaling).
        for(int i = 0; i < waveCount; i++){
            Jval w = waves.get(i);
            int waveIndex = i; //engine wave index consumed by getSpawned(state.wave - 1)
            for(Jval s : w.get("spawns").asArray()){
                UnitType type = content.unit(s.getString("unit", "dagger"));
                SpawnGroup group = new SpawnGroup(type);
                group.begin = waveIndex;
                group.end = waveIndex;
                group.unitAmount = s.getInt("count", 1);
                group.spacing = 1;
                group.spawn = -1; //all ground spawns (v0 has one)
                group.team = waveTeam;
                spawnGroups.add(group);
            }
        }

        Jval term = raw.get("termination");
        this.winTick = term.get("win").getInt("tick", 8100);
        this.tickCap = term.getInt("tick_cap", 9000);
    }

    /** Build the deterministic ruleset for this scenario (extends the M1 rules). */
    public Rules buildRules(){
        Rules rules = new Rules();
        Jval rj = raw.get("rules");
        rules.waves = rj.getBool("waves", true);
        rules.waveTimer = true;                 //native tick timer (tick-exact under fixed step)
        rules.waitEnemies = false;              //never pause the timer on live enemies
        rules.winWave = 0;                      //no engine "win"; the stepper owns termination
        rules.randomWaveAI = false;             //no hashCode()-seeded target RNG (docs/ENGINE_NOTES.md §6)
        rules.canGameOver = canGameOver;        //core loss ends the episode (runStateCheck on)
        rules.fog = rj.getBool("fog", false);
        rules.pvp = rj.getBool("pvp", false);
        rules.attackMode = rj.getBool("attack_mode", false);
        rules.infiniteResources = rj.getBool("infinite_resources", false);
        rules.defaultTeam = coreTeam;
        rules.waveTeam = waveTeam;
        rules.unitCap = unitCap;
        //Each wave fires a spawn-clearing shockwave of radius dropZoneRadius (default 300u).
        //Our east spawn (46,24) sits only ~172u from the core (24,24), so the default would
        //nuke the core on wave 1. Shrink it to a local radius that clears just the spawn tile
        //(and the ±2-tile spawn spread) without reaching the core. Documented in docs/SCENARIOS.md.
        rules.dropZoneRadius = tilesize * 3f;
        //rules.loadout is a Seq<ItemStack>; copy so a rules mutation can't touch our source
        rules.loadout = loadout.isEmpty() ? ItemStack.list(Items.copper, 0) : loadout.copy();
        rules.initialWaveSpacing = initialWaveSpacing;
        rules.waveSpacing = waveSpacing;
        rules.spawns = spawnGroups.copy();
        //no tech tree: every allowed block/unit is available from tick 0
        for(UnlockableContent c : allowedContent) rules.researched.add(c);
        return rules;
    }

    /** Generate tiles in place: flat floor, ore overlays, one enemy spawn overlay, one core. */
    public void generate(Tiles tiles){
        for(int x = 0; x < tiles.width; x++){
            for(int y = 0; y < tiles.height; y++){
                Block overlay = overlayAt(x, y);
                tiles.set(x, y, new Tile(x, y, floor, overlay, Blocks.air));
            }
        }
        //core is a multiblock; place after tiles are populated, before endMapLoad.
        tiles.getn(coreX, coreY).setBlock(coreBlock, coreTeam, 0);
    }

    /** The overlay ore/spawn floor at a tile, or {@code Blocks.air} for none. */
    private Block overlayAt(int x, int y){
        for(SpawnPoint sp : spawnPoints){
            if(sp.x == x && sp.y == y) return Blocks.spawn;
        }
        for(OrePatch p : orePatches){
            if(p.contains(x, y)) return p.ore;
        }
        return Blocks.air;
    }

    /** Scenario metadata for the reset response. */
    public Jval metadata(){
        Jval m = Jval.newObject();
        m.put("scenario_id", id);
        m.put("scenario_version", version);
        m.put("width", width);
        m.put("height", height);
        m.put("core_x", coreX);
        m.put("core_y", coreY);
        m.put("wave_count", waveCount);
        m.put("initial_wave_tick", initialWaveSpacing);
        m.put("wave_spacing", waveSpacing);
        m.put("win_tick", winTick);
        m.put("tick_cap", tickCap);
        return m;
    }

    /** Run the generator against the live world. */
    public void load(){
        world.loadGenerator(width, height, this::generate);
    }

    public SchematicSpec schematic(String name){
        return schematics.get(name);
    }

    // ---------------------------------------------------------------- helpers

    private void loadSchematic(String path, String expectedName){
        String resource = "/scenarios/" + path;
        Jval spec = readResource(resource);
        String name = spec.getString("name", "");
        if(name.isEmpty() || !name.equals(expectedName)){
            throw new IllegalStateException("schematic name " + name + " does not match reference " + expectedName);
        }

        ArrayList<BuildSpec> blocks = new ArrayList<>();
        int copperCost = 0;
        for(Jval entry : spec.get("blocks").asArray()){
            Block block = block(entry.getString("block", ""));
            if(!allowedContent.contains(block, true)){
                throw new IllegalStateException("schematic block is not scenario-whitelisted: " + block.name);
            }
            Jval offset = entry.get("offset");
            blocks.add(new BuildSpec(block.name, offset.asArray().get(0).asInt(),
                offset.asArray().get(1).asInt(), entry.getInt("rotation", 0)));
            for(ItemStack requirement : block.requirements){
                if(requirement.item != Items.copper){
                    throw new IllegalStateException("v0 schematic has non-copper cost: " + block.name);
                }
                copperCost += requirement.amount;
            }
        }
        int expectedCost = spec.getInt("expected_copper_cost", -1);
        if(copperCost != expectedCost){
            throw new IllegalStateException("schematic copper cost " + copperCost + " != expected " + expectedCost);
        }
        schematics.put(name, new SchematicSpec(name, List.copyOf(blocks), copperCost));
    }

    private static Jval readSpec(){
        return readResource(RESOURCE);
    }

    private static Jval readResource(String resource){
        try(InputStream in = Scenario.class.getResourceAsStream(resource)){
            if(in == null){
                throw new IllegalStateException("scenario resource not on classpath: " + resource
                    + " (rl-server processResources must copy scenarios/ JSON files)");
            }
            byte[] bytes = in.readAllBytes();
            return Jval.read(new String(bytes, StandardCharsets.UTF_8));
        }catch(IOException e){
            throw new RuntimeException("failed to read scenario resource " + resource, e);
        }
    }

    private static Block block(String name){
        Block b = content.block(name);
        if(b == null) throw new IllegalStateException("unknown block id in scenario spec: " + name);
        return b;
    }

    private static Item item(String name){
        Item it = content.item(name);
        if(it == null) throw new IllegalStateException("unknown item id in scenario spec: " + name);
        return it;
    }

    private static Team team(String name){
        switch(name){
            case "sharded": return Team.sharded;
            case "crux": return Team.crux;
            case "green": return Team.green;
            case "blue": return Team.blue;
            case "derelict": return Team.derelict;
            default: throw new IllegalStateException("unknown team id in scenario spec: " + name);
        }
    }

    /** An ore overlay rectangle (inclusive tiles), SW corner + extents. */
    public static final class OrePatch{
        public final Block ore;
        public final int x, y, w, h;
        OrePatch(Block ore, int x, int y, int w, int h){
            this.ore = ore; this.x = x; this.y = y; this.w = w; this.h = h;
        }
        boolean contains(int tx, int ty){
            return tx >= x && tx < x + w && ty >= y && ty < y + h;
        }
    }

    /** An enemy ground spawn tile. */
    public static final class SpawnPoint{
        public final int x, y;
        SpawnPoint(int x, int y){ this.x = x; this.y = y; }
    }

    public record SchematicSpec(String name, List<BuildSpec> blocks, int copperCost){}
}
