package mindustry.rl;

import agentcore.TaskType;
import agentcore.skill.*;
import arc.math.geom.*;
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
 * A supported bootstrap-defense scenario, driven entirely by its checked-in
 * machine-readable spec under {@code scenarios/}
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
    private static final Map<String, String> RESOURCES = Map.of(
        "bootstrap-defense-v0", "/scenarios/bootstrap-defense-v0/scenario.json",
        "bootstrap-defense-v1", "/scenarios/bootstrap-defense-v1/scenario.json",
        "bootstrap-defense-adaptive-probe",
        "/scenarios/bootstrap-defense-adaptive-probe/scenario.json"
    );

    public final String id;
    public final int version;
    public final long rootSeed;

    public final int width, height;
    public final Block floor;
    public final Block coreBlock;
    public final Team coreTeam;
    public final int coreX, coreY;

    /** Starting core loadout (zero-amount items dropped). */
    public final Seq<ItemStack> loadout = new Seq<>();

    /** Ore patches: overlay ore floors placed on top of {@link #floor}. */
    public final Seq<OrePatch> orePatches = new Seq<>();
    public final ObjectMap<String, OrePatch> orePatchesById = new ObjectMap<>();

    /** Named objective regions and typed scenario objectives used by M5 candidates. */
    public final ObjectMap<String, RegionSpec> regions = new ObjectMap<>();
    public final ObjectMap<TaskType, ObjectiveSpec> objectives = new ObjectMap<>();

    /** Enemy ground spawn tiles ({@code Blocks.spawn} overlays); v0 has one, east. */
    public final Seq<SpawnPoint> spawnPoints = new Seq<>();

    public final Team waveTeam;
    public final int unitCap;
    public final boolean canGameOver;

    /** Native-wave-timer parameters derived from the (uniform-spaced) wave schedule. */
    public final int initialWaveSpacing;   //ticks until wave 1
    public final int waveSpacing;          //ticks between subsequent waves
    public final Seq<SpawnGroup> spawnGroups = new Seq<>();
    public final Seq<Integer> waveTicks = new Seq<>();
    public final int waveCount;

    /** Termination parameters (docs/SCENARIOS.md §Rules). */
    public final int winTick;              //core-alive-at-tick win predicate
    public final int tickCap;              //hard truncation tick

    /** Allowed content ids (whitelist); pre-unlocked so there is no tech tree. */
    public final Seq<UnlockableContent> allowedContent = new Seq<>();
    /** Data-backed schematic catalog, keyed by wire/action name. */
    public final ObjectMap<String, SchematicSpec> schematics = new ObjectMap<>();
    public final String referenceSchematicId;
    public final int referenceAnchorX, referenceAnchorY;
    public final String buildLineId;
    public final int buildLineAnchorX, buildLineAnchorY;
    public final double buildLineInflowRate;
    public final int buildLineInflowSampleTicks;
    public final List<WaveSpec> waves;
    public final List<ScheduledEvent> scheduledEvents;

    private final Jval variation;
    private final ObjectMap<String, Point2> oreJitter = new ObjectMap<>();
    private final int[] waveCountDeltas;
    private final int waveInitialOffset;
    private final int waveSpacingOffset;
    private final boolean secondLaneEnabled;
    private final int secondLaneWave;

    private final Jval raw;

    public Scenario(){
        this("bootstrap-defense-v0", 0L);
    }

    public Scenario(String requestedId){
        this(requestedId, 0L);
    }

    public Scenario(String requestedId, long rootSeed){
        this.raw = readSpec(requestedId);
        this.rootSeed = rootSeed;
        Jval configuredVariation = raw.get("variation");
        this.variation = configuredVariation != null
            && configuredVariation.getBool("enabled", false) ? configuredVariation : null;

        this.id = raw.getString("scenario_id", "bootstrap-defense-v0");
        if(!id.equals(requestedId)){
            throw new IllegalStateException("scenario resource id " + id
                + " does not match requested id " + requestedId);
        }
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
                if(map.getKeyAt(i).equals("copper") && variation != null){
                    amount = variationRange("loadout_copper", variation.get("loadout_copper"), amount);
                }
                if(amount > 0) loadout.add(new ItemStack(item(map.getKeyAt(i)), amount));
            }
        }

        for(Jval patch : raw.get("ore_patches").asArray()){
            Jval rect = patch.get("rect");
            String patchId = patch.getString("id", "");
            Point2 jitter = oreVariation(patchId);
            OrePatch spec = new OrePatch(patchId,
                block(patch.getString("ore", "ore-copper")),
                rect.getInt("x", 0) + jitter.x, rect.getInt("y", 0) + jitter.y,
                rect.getInt("w", 0), rect.getInt("h", 0),
                patch.getString("role", ""));
            orePatches.add(spec);
            orePatchesById.put(spec.id, spec);
        }

        Jval.JsonMap regionMap = raw.get("regions").asObject();
        for(int i = 0; i < regionMap.size; i++){
            Jval rect = regionMap.getValueAt(i).get("rect");
            regions.put(regionMap.getKeyAt(i), new RegionSpec(regionMap.getKeyAt(i),
                rect.getInt("x", 0), rect.getInt("y", 0),
                rect.getInt("w", 0), rect.getInt("h", 0)));
        }

        ObjectMap<String, SpawnPoint> spawnById = new ObjectMap<>();
        for(Jval spawn : raw.get("enemy_spawns").asArray()){
            Jval tile = spawn.get("tile");
            SpawnPoint point = new SpawnPoint(spawn.getString("id", ""),
                tile.asArray().get(0).asInt(), tile.asArray().get(1).asInt());
            spawnPoints.add(point);
            spawnById.put(point.id, point);
        }
        Jval secondLane = variation == null ? null : variation.get("second_lane");
        secondLaneEnabled = secondLane != null && variationChoice("second_lane_enabled",
            secondLane.getInt("enabled_numerator", 0), secondLane.getInt("enabled_denominator", 1));
        int parsedSecondLaneWave = 0;
        if(secondLaneEnabled){
            Jval spawn = secondLane.get("spawn");
            Jval tile = spawn.get("tile");
            SpawnPoint point = new SpawnPoint(spawn.getString("id", "second_lane"),
                tile.asArray().get(0).asInt(), tile.asArray().get(1).asInt());
            spawnPoints.add(point);
            spawnById.put(point.id, point);
            parsedSecondLaneWave = variationRange("second_lane_wave", secondLane.get("wave_range"), 2);
        }
        secondLaneWave = parsedSecondLaneWave;

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
            referenceSchematicId = reference.getString("id", "");
            Jval anchor = reference.get("anchor");
            referenceAnchorX = anchor.asArray().get(0).asInt();
            referenceAnchorY = anchor.asArray().get(1).asInt();
            loadSchematic(reference.getString("path", ""), referenceSchematicId);
        }else{
            referenceSchematicId = "";
            referenceAnchorX = referenceAnchorY = 0;
        }

        Jval line = raw.get("build_line");
        if(line != null){
            buildLineId = line.getString("id", "");
            Jval anchor = line.get("anchor");
            buildLineAnchorX = anchor.asArray().get(0).asInt();
            buildLineAnchorY = anchor.asArray().get(1).asInt();
            loadSchematic(line.getString("path", ""), buildLineId);
        }else{
            buildLineId = "";
            buildLineAnchorX = buildLineAnchorY = 0;
        }

        double parsedInflowRate = 0.0;
        int parsedInflowSampleTicks = 600;
        for(Jval objective : raw.get("objectives").asArray()){
            TaskType type = TaskType.valueOf(objective.getString("task_type", ""));
            Jval target = objective.get("target");
            Jval predicate = objective.get("predicate");
            String targetRef = target == null ? "" : target.getString("ref", "");
            int threshold = switch(type){
                case HARVEST_RESOURCE -> predicate.getInt("amount", 0);
                case SUPPLY_TURRET -> predicate.getInt("total_ammo", 0);
                default -> 0;
            };
            ObjectiveSpec spec = new ObjectiveSpec(objective.getString("id", ""), type,
                targetRef, threshold);
            if(objectives.put(type, spec) != null){
                throw new IllegalStateException("duplicate scenario objective type: " + type);
            }
            if(type == TaskType.BUILD_LINE){
                Jval inflow = findPredicate(predicate, "core_item_inflow_ge");
                if(inflow == null){
                    throw new IllegalStateException("BUILD_LINE requires core_item_inflow_ge");
                }
                parsedInflowRate = inflow.getDouble("rate_per_s", 0.0);
                parsedInflowSampleTicks = inflow.getInt("sample_ticks", 600);
            }
        }
        if(parsedInflowRate <= 0.0 || parsedInflowSampleTicks <= 0){
            throw new IllegalStateException("invalid BUILD_LINE inflow predicate");
        }
        buildLineInflowRate = parsedInflowRate;
        buildLineInflowSampleTicks = parsedInflowSampleTicks;

        //--- wave schedule -> native wave timer + per-wave SpawnGroups -----------------
        Jval schedule = raw.get("wave_schedule");
        Seq<Jval> waves = new Seq<>();
        for(Jval w : schedule.asArray()) waves.add(w);
        this.waveCount = waves.size;
        if(waveCount == 0) throw new IllegalStateException("wave_schedule is empty");

        Jval timingVariation = variation == null ? null : variation.get("wave_timing");
        waveInitialOffset = timingVariation == null ? 0 : variationRange(
            "wave_initial_offset", timingVariation.get("initial_offset_ticks"), 0);
        waveSpacingOffset = timingVariation == null ? 0 : variationRange(
            "wave_spacing_offset", timingVariation.get("spacing_offset_ticks"), 0);
        int baseFirstTick = waves.get(0).getInt("tick", 0);
        int baseSpacing = waveCount > 1
            ? waves.get(1).getInt("tick", 0) - baseFirstTick : 0;
        int firstTick = baseFirstTick + waveInitialOffset;
        int spacing = baseSpacing + waveSpacingOffset;
        //the native timer is uniform-spaced; require the JSON schedule to match so ticks stay exact.
        for(int i = 1; i < waveCount; i++){
            int gap = waves.get(i).getInt("tick", 0) - waves.get(i - 1).getInt("tick", 0);
            if(gap != baseSpacing){
                throw new IllegalStateException("wave_schedule is not uniformly spaced (gap " + gap
                    + " != " + baseSpacing + " at wave " + i + "); drive spawns explicitly instead");
            }
        }
        if(firstTick <= 0 || spacing <= 0){
            throw new IllegalStateException("varied wave timing must remain positive");
        }
        this.initialWaveSpacing = firstTick;
        this.waveSpacing = spacing;

        //one SpawnGroup per (wave, unit) — begin==end pins it to a single wave, so any
        //per-wave composition from the JSON is reproduced exactly (no arithmetic scaling).
        ArrayList<WaveSpec> parsedWaves = new ArrayList<>();
        waveCountDeltas = new int[waveCount];
        Jval countVariation = variation == null ? null : variation.get("wave_count_delta");
        for(int i = 0; i < waveCount; i++){
            Jval w = waves.get(i);
            int resolvedTick = firstTick + i * spacing;
            waveTicks.add(resolvedTick);
            int waveIndex = i; //engine wave index consumed by getSpawned(state.wave - 1)
            ArrayList<WaveSpawn> parsedSpawns = new ArrayList<>();
            int countDelta = countVariation == null ? 0 : variationRange(
                "wave_count_delta_" + (i + 1), countVariation, 0);
            waveCountDeltas[i] = countDelta;
            String spawnId = w.getString("spawn", "");
            if(secondLaneEnabled && secondLaneWave == i + 1){
                spawnId = secondLane.get("spawn").getString("id", "second_lane");
            }
            SpawnPoint spawnPoint = spawnById.get(spawnId);
            if(spawnPoint == null){
                throw new IllegalStateException("wave references unknown spawn: " + spawnId);
            }
            for(Jval s : w.get("spawns").asArray()){
                UnitType type = content.unit(s.getString("unit", "dagger"));
                int count = s.getInt("count", 1) + countDelta;
                if(count <= 0) throw new IllegalStateException("varied wave count must be positive");
                SpawnGroup group = new SpawnGroup(type);
                group.begin = waveIndex;
                group.end = waveIndex;
                group.unitAmount = count;
                group.spacing = 1;
                // Preserve v0's historical all-ground-spawns sentinel exactly;
                // scenario v2 needs an explicit packed tile to route its named
                // optional lane without changing the fixed golden behavior.
                group.spawn = variation == null && spawnPoints.size == 1
                    ? -1 : Point2.pack(spawnPoint.x, spawnPoint.y);
                group.team = waveTeam;
                spawnGroups.add(group);
                parsedSpawns.add(new WaveSpawn(type, count));
            }
            parsedWaves.add(new WaveSpec(i + 1, resolvedTick, spawnId, parsedSpawns));
        }
        this.waves = List.copyOf(parsedWaves);

        ArrayList<ScheduledEvent> parsedEvents = new ArrayList<>();
        Jval eventData = raw.get("scheduled_events");
        if(eventData != null){
            for(Jval event : eventData.asArray()){
                String type = event.getString("type", "");
                if(!type.equals("core_item_grant")){
                    throw new IllegalStateException("unsupported scheduled event " + type);
                }
                parsedEvents.add(new ScheduledEvent(type, event.getInt("tick", -1),
                    item(event.getString("item", "copper")), event.getInt("amount", 0),
                    event.getString("reason", "scenario_event")));
            }
        }
        parsedEvents.sort(Comparator.comparingInt(ScheduledEvent::tick));
        this.scheduledEvents = List.copyOf(parsedEvents);

        Jval term = raw.get("termination");
        this.winTick = term.get("win").getInt("tick", 8100);
        this.tickCap = term.getInt("tick_cap", 9000);
        if(waveTicks.peek() >= winTick || winTick >= tickCap){
            throw new IllegalStateException("wave/win/tick-cap ordering is invalid");
        }
        validateGeometry();
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
        if(variation != null) m.put("root_seed", rootSeed);
        m.put("width", width);
        m.put("height", height);
        m.put("tile_size", tilesize);
        m.put("core_x", coreX);
        m.put("core_y", coreY);
        m.put("core_health_max", coreBlock.health);
        m.put("copper_budget", coreBlock.itemCapacity);
        m.put("wave_count", waveCount);
        m.put("initial_wave_tick", initialWaveSpacing);
        m.put("wave_spacing", waveSpacing);
        m.put("win_tick", winTick);
        m.put("tick_cap", tickCap);
        Jval ticks = Jval.newArray();
        for(int tick : waveTicks) ticks.add(tick);
        m.add("wave_ticks", ticks);

        Jval patches = Jval.newArray();
        for(OrePatch patch : orePatches){
            Jval entry = Jval.newObject();
            entry.put("id", patch.id);
            entry.put("ore", patch.ore.name);
            entry.put("role", patch.role);
            entry.add("rect", rectMetadata(patch.x, patch.y, patch.w, patch.h));
            patches.add(entry);
        }
        m.add("ore_patches", patches);

        Jval regionData = Jval.newObject();
        for(ObjectMap.Entry<String, RegionSpec> entry : regions){
            RegionSpec region = entry.value;
            Jval value = Jval.newObject();
            value.add("rect", rectMetadata(region.x(), region.y(), region.w(), region.h()));
            regionData.add(entry.key, value);
        }
        m.add("regions", regionData);
        Jval objectiveData = Jval.newObject();
        for(ObjectMap.Entry<TaskType, ObjectiveSpec> entry : objectives){
            ObjectiveSpec objective = entry.value;
            Jval value = Jval.newObject();
            value.put("id", objective.id());
            value.put("target_ref", objective.targetRef());
            value.put("threshold", objective.threshold());
            objectiveData.add(entry.key.name(), value);
        }
        m.add("objectives", objectiveData);
        m.add("reference_schematic", schematicMetadata(referenceSchematicId,
            referenceAnchorX, referenceAnchorY));
        m.add("build_line", schematicMetadata(buildLineId, buildLineAnchorX,
            buildLineAnchorY));
        Jval economy = Jval.newObject();
        economy.put("core_inflow_rate_per_s", buildLineInflowRate);
        economy.put("sample_ticks", buildLineInflowSampleTicks);
        m.add("build_line_predicate", economy);
        m.add("variation", variationMetadata());
        return m;
    }

    /** Canonical seed-resolved scenario state included in every observation hash. */
    public byte[] canonicalState(){
        try{
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            writeString(out, id);
            out.writeInt(version);
            out.writeLong(rootSeed);
            out.writeInt(loadout.size);
            for(ItemStack stack : loadout){
                writeString(out, stack.item.name);
                out.writeInt(stack.amount);
            }
            out.writeInt(orePatches.size);
            for(OrePatch patch : orePatches){
                writeString(out, patch.id);
                out.writeInt(patch.x);
                out.writeInt(patch.y);
                out.writeInt(patch.w);
                out.writeInt(patch.h);
            }
            out.writeInt(spawnPoints.size);
            for(SpawnPoint spawn : spawnPoints){
                writeString(out, spawn.id);
                out.writeInt(spawn.x);
                out.writeInt(spawn.y);
            }
            out.writeInt(waves.size());
            for(WaveSpec wave : waves){
                out.writeInt(wave.tick());
                writeString(out, wave.spawnId());
                out.writeInt(wave.spawns().size());
                for(WaveSpawn spawn : wave.spawns()){
                    writeString(out, spawn.type().name);
                    out.writeInt(spawn.count());
                }
            }
            out.flush();
            return bytes.toByteArray();
        }catch(IOException impossible){
            throw new AssertionError(impossible);
        }
    }

    /** Run the generator against the live world. */
    public void load(){
        world.loadGenerator(width, height, this::generate);
    }

    public SchematicSpec schematic(String name){
        return schematics.get(name);
    }

    public ObjectiveSpec objective(TaskType type){
        return objectives.get(type);
    }

    public RegionSpec region(String id){
        return regions.get(id);
    }

    public OrePatch orePatch(String id){
        return orePatchesById.get(id);
    }

    // ---------------------------------------------------------------- helpers

    private Point2 oreVariation(String patchId){
        if(variation == null) return new Point2();
        Jval patches = variation.get("ore_patch_jitter");
        Jval patch = patches == null ? null : patches.get(patchId);
        if(patch == null) return new Point2();
        Point2 jitter = new Point2(
            variationRange("ore_" + patchId + "_x", patch.get("x"), 0),
            variationRange("ore_" + patchId + "_y", patch.get("y"), 0));
        oreJitter.put(patchId, jitter);
        return jitter;
    }

    private int variationRange(String axis, Jval range, int fallback){
        if(range == null || !range.isArray() || range.asArray().size < 2) return fallback;
        int min = range.asArray().get(0).asInt();
        int max = range.asArray().get(1).asInt();
        if(max < min) throw new IllegalStateException("invalid variation range for " + axis);
        long mixed = mix64(rootSeed ^ stableHash(axis));
        return min + (int)Math.floorMod(mixed, (long)max - min + 1L);
    }

    private boolean variationChoice(String axis, int numerator, int denominator){
        if(denominator <= 0 || numerator < 0 || numerator > denominator){
            throw new IllegalStateException("invalid variation probability for " + axis);
        }
        return Math.floorMod(mix64(rootSeed ^ stableHash(axis)), denominator) < numerator;
    }

    private Jval variationMetadata(){
        Jval out = Jval.newObject();
        out.put("enabled", variation != null);
        if(variation == null) return out;
        Jval jitter = Jval.newObject();
        for(ObjectMap.Entry<String, Point2> entry : oreJitter){
            Jval offset = Jval.newArray();
            offset.add(entry.value.x);
            offset.add(entry.value.y);
            jitter.add(entry.key, offset);
        }
        out.add("ore_patch_jitter", jitter);
        out.put("wave_initial_offset_ticks", waveInitialOffset);
        out.put("wave_spacing_offset_ticks", waveSpacingOffset);
        Jval deltas = Jval.newArray();
        for(int delta : waveCountDeltas) deltas.add(delta);
        out.add("wave_count_deltas", deltas);
        out.put("second_lane_enabled", secondLaneEnabled);
        out.put("second_lane_wave", secondLaneWave);
        out.put("resolved_copper_loadout", loadoutAmount(Items.copper));
        return out;
    }

    private int loadoutAmount(Item item){
        for(ItemStack stack : loadout){
            if(stack.item == item) return stack.amount;
        }
        return 0;
    }

    private void validateGeometry(){
        int coreMinX = coreX - coreBlock.size / 2;
        int coreMinY = coreY - coreBlock.size / 2;
        for(int i = 0; i < orePatches.size; i++){
            OrePatch patch = orePatches.get(i);
            if(patch.x < 0 || patch.y < 0 || patch.x + patch.w > width
                || patch.y + patch.h > height){
                throw new IllegalStateException("ore patch outside world: " + patch.id);
            }
            if(rectsOverlap(patch.x, patch.y, patch.w, patch.h,
                coreMinX, coreMinY, coreBlock.size, coreBlock.size)){
                throw new IllegalStateException("ore patch overlaps core: " + patch.id);
            }
            for(int j = 0; j < i; j++){
                OrePatch other = orePatches.get(j);
                if(rectsOverlap(patch.x, patch.y, patch.w, patch.h,
                    other.x, other.y, other.w, other.h)){
                    throw new IllegalStateException("ore patches overlap: "
                        + other.id + " and " + patch.id);
                }
            }
        }
        for(SpawnPoint spawn : spawnPoints){
            if(spawn.x < 0 || spawn.y < 0 || spawn.x >= width || spawn.y >= height){
                throw new IllegalStateException("spawn outside world: " + spawn.id);
            }
        }
    }

    private static boolean rectsOverlap(
        int ax, int ay, int aw, int ah, int bx, int by, int bw, int bh
    ){
        return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
    }

    private static long stableHash(String value){
        long hash = 0xcbf29ce484222325L;
        for(int i = 0; i < value.length(); i++){
            hash ^= value.charAt(i);
            hash *= 0x100000001b3L;
        }
        return hash;
    }

    private static long mix64(long value){
        value = (value ^ (value >>> 30)) * 0xbf58476d1ce4e5b9L;
        value = (value ^ (value >>> 27)) * 0x94d049bb133111ebL;
        return value ^ (value >>> 31);
    }

    private static void writeString(DataOutputStream out, String value) throws IOException{
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        out.writeInt(encoded.length);
        out.write(encoded);
    }

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

    public static boolean supports(String id){
        return RESOURCES.containsKey(id);
    }

    private static Jval readSpec(String id){
        String resource = RESOURCES.get(id);
        if(resource == null) throw new IllegalArgumentException("unknown scenario_id: " + id);
        return readResource(resource);
    }

    private static Jval findPredicate(Jval predicate, String type){
        if(predicate == null) return null;
        if(type.equals(predicate.getString("type", ""))) return predicate;
        Jval children = predicate.get("of");
        if(children != null){
            for(Jval child : children.asArray()){
                Jval found = findPredicate(child, type);
                if(found != null) return found;
            }
        }
        return null;
    }

    private Jval schematicMetadata(String id, int anchorX, int anchorY){
        SchematicSpec spec = schematic(id);
        Jval result = Jval.newObject();
        result.put("id", id);
        Jval anchor = Jval.newArray();
        anchor.add(anchorX);
        anchor.add(anchorY);
        result.add("anchor", anchor);
        Jval blocks = Jval.newArray();
        if(spec != null){
            for(BuildSpec block : spec.blocks()){
                Jval entry = Jval.newObject();
                entry.put("block", block.block());
                Jval offset = Jval.newArray();
                offset.add(block.offsetX());
                offset.add(block.offsetY());
                entry.add("offset", offset);
                entry.put("rotation", block.rotation());
                blocks.add(entry);
            }
        }
        result.add("blocks", blocks);
        return result;
    }

    private static Jval rectMetadata(int x, int y, int w, int h){
        Jval rect = Jval.newObject();
        rect.put("x", x);
        rect.put("y", y);
        rect.put("w", w);
        rect.put("h", h);
        return rect;
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
        public final String id;
        public final Block ore;
        public final int x, y, w, h;
        public final String role;
        OrePatch(String id, Block ore, int x, int y, int w, int h, String role){
            this.id = id; this.ore = ore; this.x = x; this.y = y; this.w = w; this.h = h;
            this.role = role;
        }
        boolean contains(int tx, int ty){
            return tx >= x && tx < x + w && ty >= y && ty < y + h;
        }
    }

    /** An enemy ground spawn tile. */
    public static final class SpawnPoint{
        public final String id;
        public final int x, y;
        SpawnPoint(String id, int x, int y){ this.id = id; this.x = x; this.y = y; }
    }

    public record SchematicSpec(String name, List<BuildSpec> blocks, int copperCost){}
    public record RegionSpec(String id, int x, int y, int w, int h){}
    public record ObjectiveSpec(String id, TaskType taskType, String targetRef, int threshold){}
    public record WaveSpawn(UnitType type, int count){
        public WaveSpawn{
            Objects.requireNonNull(type, "type");
            if(count <= 0) throw new IllegalArgumentException("wave spawn count must be positive");
        }
    }
    public record WaveSpec(int number, int tick, String spawnId, List<WaveSpawn> spawns){
        public WaveSpec{ spawns = List.copyOf(spawns); }
    }
    public record ScheduledEvent(String type, int tick, Item item, int amount, String reason){
        public ScheduledEvent{
            if(tick < 0 || amount <= 0) throw new IllegalArgumentException("invalid scheduled event");
            Objects.requireNonNull(item, "item");
            reason = reason == null ? "" : reason;
        }
    }
}
