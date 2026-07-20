# Strategy Notes — Early Serpulo Survival, distilled for agent design

**Purpose.** This is the strategy knowledge base that informs candidate-task
generation (brief §10.4), skill design (§10.3), and reward design (§17) for the
`bootstrap-defense-v0` scenario and the Stage A–C curriculum (§13). It distils
*early-game Serpulo survival* into concrete, sourced numbers and a partial order
of work that agents can be scored against.

**Scope.** Only the v0 allowed content is treated as load-bearing: Mechanical
Drill, Conveyor, Junction, Router, Duo, Copper Wall, and the Alpha core unit
(brief §12.2). Power, Menders, factories, and tech beyond copper are out of
scope until a later curriculum stage.

## Source conventions

- **Engine-verified** numbers are cited as `file:line` against this checkout
  (Anuken/Mindustry `v159.7`, commit `c9686eb`). Content paths are relative to
  `core/src/mindustry/content/` unless noted; block/turret mechanics are in
  `core/src/mindustry/world/blocks/...`; unit movement in
  `core/src/mindustry/entities/comp/...`. These are the authority.
- **Wiki/community** guidance is marked *(wiki)* and used only for qualitative
  advice (opening order, common mistakes), never for numbers that the engine
  source can provide.
- `tilesize = 8` world units. Simulation runs at **60 ticks/sec** with the fixed
  `1/60` delta (see `docs/ENGINE_NOTES.md` §2.4). "DPS" below means damage per
  simulated second; multiply per-tick figures by 60.

---

## 1. Economy fundamentals (verified throughput)

### 1.1 Mining — Mechanical Drill on copper

`mechanicalDrill` (`Blocks.java:2866`): `drillTime = 600`, `tier = 2`,
`size = 2`, cost **12 copper**. Effective drill time per item includes ore
hardness (`Drill.java:171`):

```
getDrillTime(item) = (drillTime + hardnessDrillMultiplier * item.hardness) / drillMultiplier
                   = (600 + 50 * 1) / 1 = 650 ticks per item, per drilled ore tile
```
`hardnessDrillMultiplier = 50` (`Drill.java:28`); copper `hardness = 1`
(`Items.java:17`), lead `hardness = 1` (`Items.java:23`), no multiplier for
either. Per-tick output scales with the number of ore tiles under the drill
footprint (`Drill.java:303,305` — `progress += delta * dominantItems / delay`):

| Ore tiles under a 2×2 Mechanical Drill | Copper output |
|---|---|
| 1 tile | 60 / 650 = **0.092 items/s** |
| 4 tiles (full patch) | 4 × 60 / 650 = **0.369 items/s** |

> The in-game *drillSpeed* stat (`Drill.java:181`, `60/drillTime * size²` = 0.40/s)
> **ignores hardness** and slightly overstates the real rate. Use **0.37 copper/s
> per fully-fed Mechanical Drill** for planning. Water boost (`liquidBoostIntensity
> = 1.6`, `Drill.java:38`) is not available in v0 (no water/pumps in the block set),
> so ignore it.

A drill must sit on ore; to maximise output, place the 2×2 footprint so all four
covered tiles are ore. On a 6×6 patch, up to nine 2×2 drills fit (with overlap
of coverage they contend for the same tiles, so plan for ~4–5 fully-fed drills
per 6×6 patch).

### 1.2 Transport — Conveyor / Junction / Router

- `conveyor` (`Blocks.java:2068`): `displayedSpeed = 6.5 items/s`, `speed =
  0.046`, `health = 45`, cost **1 copper**. One conveyor lane moves **6.5
  items/s** — vastly more than one drill produces (0.37/s), so a single lane
  trunks ~17 drills' worth of copper. Conveyors are the cheapest block; spam
  them *(wiki)*.
- `junction` (`Blocks.java:2097`): lets two conveyor lines cross without mixing;
  `speed = 26`, `capacity = 6`, `health = 30`, cost **3 copper**. Low HP — never
  put a junction where enemies can hit it.
- `router` (`Blocks.java:2138`): 1→N split / N→1 merge, cost **3 copper**. Used
  to fan one copper trunk out to multiple Duos (turret ammo inputs).

### 1.3 Core sink & starting economy

- `coreShard` (`Blocks.java:3127`): `health = 1100`, `itemCapacity = 4000`,
  `size = 3`, spawns `alpha` builder units (`unitType = UnitTypes.alpha`). The
  core is both the item sink for mined ore and the object you must keep alive.
  The core does **not** shoot — it has no weapon. All defence is turrets/walls.
- Copper is the only resource the v0 build set consumes (drill 12, conveyor 1,
  junction 3, router 3, Duo 35, copper wall 6 — all copper). **Lead is not
  required to win v0**; the lead patch exists to teach the two-resource economy
  and for v1+ variation (see `docs/SCENARIOS.md`).

### 1.4 The Alpha builder unit (what an agent controls)

`alpha` (`UnitTypes.java:2480`): `flying = true`, `buildSpeed = 0.5`,
`mineSpeed = 6.5`, `mineTier = 1`, `itemCapacity = 30`, `health = 150`,
`speed = 3`. `mineTier = 1 ≥ hardness 1`, so Alpha can hand-mine **both copper
and lead**. Being flying, it ignores ground obstacles for navigation (relevant
to `docs/ENGINE_NOTES.md` §5.3: short/open moves are deterministic). It carries
only 30 items, so hand-mining is a bootstrap measure — sustained economy needs
drills + conveyors, not units ferrying ore.

---

## 2. Defense fundamentals

### 2.1 The Duo turret (verified)

`duo` (`Blocks.java:3258`), an `ItemTurret`, cost **35 copper**:

| Property | Value | Source |
|---|---|---|
| Health | 250 | `Blocks.java:3322` |
| Reload | 20 ticks → **3 shots/s** | `Blocks.java:3318` |
| Range | 160 units = **20 tiles** | `Blocks.java:3319` |
| Shot pattern | `ShootAlternate`, `shots = 1` (1 bullet/reload, alternating barrels) | `Blocks.java:3300`, `ShootPattern.java:9` |
| Max ammo | 30 (`ammoPerShot = 1`) | `Turret.java:47,49` |
| **Copper ammo** | `BasicBulletType(2.5, 9)` → speed 2.5, **9 dmg**, `ammoMultiplier = 2` | `Blocks.java:3261,3265` |

Derived (copper ammo, target with 0 armor such as a Dagger):

- **DPS = 3 shots/s × 9 = 27 DPS per Duo.**
- **Copper consumption at full fire** = 3 shots/s ÷ `ammoMultiplier 2` = **1.5
  copper/s per Duo**. A full magazine holds `maxAmmo 30 / ammoMultiplier 2 =
  15 copper` = 30 shots = **10 s of continuous fire** before it runs dry.
- Graphite ammo (18 dmg, `ammoMultiplier 4`, `Blocks.java:3271`) roughly doubles
  DPS and halves copper-equivalent consumption, but graphite is **out of scope**
  for v0 (no graphite production). Copper ammo only.

### 2.2 Copper Wall (verified)

`copperWall` (`Blocks.java:1706`): `health = 80 * wallHealthMultiplier`, and
`wallHealthMultiplier = 4` (`Blocks.java:1704`) → **320 HP**, cost **6 copper**,
`size = 1`. `copperWallLarge` is 2×2, 1280 HP. Walls have no regen; damaged walls
stay damaged until repaired/rebuilt. Their only job is to soak damage and block
the ground path so enemies bunch where turrets can focus them.

### 2.3 Placement doctrine (turrets + walls + choke)

Distilled from the community beginner guides *(wiki)* and constrained to the v0
set:

1. **Turrets behind a wall.** Bullets spawn above the turret and clear an
   adjacent same-height wall, so a wall directly in front of a Duo protects it
   while it keeps firing. Standard "wall-then-turret" line.
2. **Funnel into one lane.** Wall off secondary paths to force a single
   chokepoint; leave one gap so enemies must file through the turret kill-zone
   *(wiki: "close off secondary paths… create a chokepoint")*. A narrow lane
   caps how many enemies can shoot your front wall at once (their incoming DPS),
   while your turrets still hit the whole column.
3. **Duos forward, cheap and replaceable** *(wiki)* — Duo needs only copper, so
   losses are trivially rebuilt. Two forward Duos are the v0 defensive core.
4. **Range covers the lane.** A Duo's 20-tile range reaches far up the approach;
   place Duos so their range covers from the choke back past the enemy spawn, so
   enemies are under fire for the entire traversal, not just at the wall.

### 2.4 Ammo supply

A Duo is useless empty. The defensive line must be **fed copper** continuously —
this is the `SUPPLY_TURRET` task. Because a Duo drains 1.5 copper/s at full fire
and one drill makes only 0.37 copper/s, sustaining two Duos through a wave
requires **either a buffered stockpile in the magazine (30 shots) topped up
between waves, or ≥4 drills trunked to the turrets.** The intended v0 pattern is:
drills fill a conveyor trunk → router fans to both Duos → magazines stay near
full between waves and drain partially during each wave. Supply is a real,
scored task, not decoration.

---

## 3. The standard opening as a partial order

Tasks are a **partial order**: edges are hard prerequisites; siblings may run
concurrently (and across agents). Coordinates/predicates are made concrete in
`docs/SCENARIOS.md` §Objective decomposition.

```
                 ┌─────────────────────────────────────────────┐
                 │ (loadout: starting copper in core)           │
                 └───────────────┬─────────────────────────────┘
                                 │
        ┌────────────────────────┼───────────────────────────┐
        ▼                        ▼                            ▼
 [HARVEST copper]        [BUILD_LINE copper]          [BUILD_SCHEMATIC
  hand-mine to a          drills on patch →            east_duo_line]
  core threshold          conveyor trunk → core        2 Duos + wall choke
  (bootstraps if          (sustained economy)          (uses loadout copper)
   loadout is thin)                │                            │
        └──────────────┬──────────┘                            │
                       ▼                                        ▼
                [SUPPLY_TURRET east] ◄───────────── needs Duos to exist
                 route copper to both Duos                      │
                       │                                        │
                       └──────────────┬─────────────────────────┘
                                      ▼
                               [DEFEND_REGION east] (waves 1–3)
                                      │
                                      ▼
                               [REPAIR_REGION east]  (between/after waves)
```

Hard precedences:

- **Build the Duos before you can supply them.** `SUPPLY_TURRET` targets must
  exist (`BUILD_SCHEMATIC east_duo_line` completes first).
- **Have copper before you build.** Either the starting loadout or `HARVEST`
  must provide the ~160 copper the reference build costs before/while building.
- **Economy (BUILD_LINE) unblocks sustained supply.** Ammo for wave 3 exceeds
  what loadout + magazines hold, so the drill line must be feeding copper by
  ~wave 2 (arithmetic in `docs/SCENARIOS.md`).
- **Defend/repair are recurring**, triggered by wave ticks and by building
  damage, not one-shot.

Concurrency the coordination layer should exploit: while one agent lays the
copper line, another builds the east schematic; a third can hand-mine copper to
cover the shortfall or stage as the supply carrier (the brief's Copper / Shield /
Relay split, §1, §12.4).

---

## 4. Common failure modes (what beginners — and naive agents — get wrong)

Mix of *(wiki)* community observations and consequences that fall directly out of
the verified numbers:

1. **No defence / defence too late.** Undefended, a Dagger deals 41.5 DPS (§5);
   3 daggers on the 1100-HP core kill it in ~9 s once they arrive. An agent that
   only builds economy loses. (This is the intended "lose if you build nothing"
   property.)
2. **Empty turrets.** Building Duos but not supplying copper — the magazine
   drains in 10 s of fire and the turret goes silent mid-wave. Supply is not
   optional.
3. **Under-building drills.** One drill (0.37/s) cannot feed one Duo (1.5/s).
   Beginners place a single drill and starve both economy and ammo.
4. **Drill not fully on ore.** A 2×2 drill covering 1 ore tile makes a quarter of
   the output of one covering 4. Placement matters (§1.1).
5. **Spread-out, unwalled turrets.** Without a choke, enemies split across paths
   and hit turrets from angles; turrets can't focus. Wall the flanks *(wiki)*.
6. **Turrets in front of the wall** instead of behind it — the turret takes fire
   first and dies (250 HP vs a 320-HP wall that should be absorbing).
7. **Junctions/conveyors in the line of fire.** 30–45 HP transport blocks get
   destroyed, cutting supply mid-wave. Route logistics behind walls.
8. **No repair between waves.** Damaged walls carry into the next wave at reduced
   HP and collapse; `REPAIR_REGION` restores the soak before the next spawn.
9. **Duplicate work / thrashing** (coordination-specific): two agents both build
   the same Duo, or an agent abandons a half-built line to start another. The
   task board's leases and switching penalty exist to prevent this (brief §11.5).

---

## 5. Enemy reference — the Dagger (verified)

`dagger` (`UnitTypes.java:99`): the only enemy type in v0 (Crux team, T1 ground).

| Property | Value | Source |
|---|---|---|
| Health | 150 | `UnitTypes.java:103` |
| Armor | 0 (unset) | — |
| Move speed | `speed = 0.5` → `0.5 × 60 / 8 = 3.75 tiles/s` top | `UnitTypes.java:101`, `UnitComp.java:295` |
| Weapon | `reload = 13`, `BasicBulletType(2.5, 9)` | `UnitTypes.java:107,112` |
| **DPS** | `60/13 × 9 = 41.5 DPS` | derived |
| Weapon range | `2.5 × 60 = 150 units = 18.75 tiles` (speed × lifetime) | `UnitTypes.java:112,115` |

Notes for balance: daggers are *ranged* (18.75-tile bullet), so they can shoot
your front wall from just outside melee. But a Duo's 20-tile range slightly
out-ranges the Dagger's 18.75, so a Duo covering the lane gets first shots.
Armor 0 means the full 9 dmg/shot lands. A dagger decelerates to fire, so its
*effective* approach speed is well under 3.75 tiles/s — treat ~2–3 tiles/s as
the planning figure for lane-exposure time.

---

## 6. Strategy concept → TaskType → Skill mapping

The 16-type task catalog is brief §10.2; the skill set and its implementation
order is §10.3. This table is the bridge candidate-generation and reward code
build on. "v0" marks what `bootstrap-defense-v0` actually exercises; the rest are
catalog entries reserved for later stages.

| Strategy concept (this doc) | TaskType (§10.2) | Skill(s) (§10.3) | In v0? | Completion signal (see SCENARIOS.md) |
|---|---|---|---|---|
| Hand-mine copper to a core threshold | `HARVEST_RESOURCE` | `MineResource`, `DeliverToCore`, `NavigateTo` | ✅ | core copper ≥ threshold |
| Lay drills + conveyor trunk to core | `BUILD_LINE` | `ExecuteFixedSchematic`, `NavigateTo` | ✅ | line blocks placed & core copper rate ≥ target |
| Build the east Duo+wall defensive schematic | `BUILD_SCHEMATIC` | `ExecuteFixedSchematic` | ✅ | all footprint blocks complete |
| Keep the Duos fed with copper | `SUPPLY_TURRET` | `SupplyBuilding`, `NavigateTo`, `DeliverToCore`(variant) | ✅ | both Duos' ammo ≥ threshold sustained |
| Hold the east lane during waves | `DEFEND_REGION` | `DefendRegion`, `NavigateTo` | ✅ | region enemy count = 0 through wave |
| Repair damaged walls/turrets | `REPAIR_REGION` | `RepairTarget`, `NavigateTo` | ✅ | region block health fraction ≥ target |
| Help a stalled builder finish | `ASSIST_BUILD` | `AssistBuilder`, `NavigateTo` | ✅ (demo §12.4) | target plan completes |
| Ask for a carrier/helper | `REQUEST_HELP` | (coordination act, no skill) | ✅ | helper accepted |
| Route a generic item to a building | `SUPPLY_BUILDING` | `SupplyBuilding` | — | building inventory ≥ target |
| Deliver a resource batch to a sink | `DELIVER_RESOURCE` | `DeliverToCore`, `NavigateTo` | — | net delivered ≥ amount |
| Scout an approach/region | `SCOUT_REGION` | `NavigateTo` | — | region tiles observed |
| Kill a specific threat | `ATTACK_TARGET` | `DefendRegion`(variant), `NavigateTo` | — | target destroyed |
| Escort another agent | `ESCORT_AGENT` | `NavigateTo`, `DefendRegion` | — | escortee task done / safe |
| Clear a blocking obstacle | `CLEAR_OBSTACLE` | `ExecuteFixedSchematic`(break) | — | tile cleared |
| Stand power up | `GENERATE_POWER` | `ExecuteFixedSchematic` | — (later stage) | power balance ≥ 0 |
| Deliberate hold / no useful work | `WAIT` | (none) | ✅ (fallback) | interval elapsed |
| Retreat under threat | (no TaskType; skill-level) | `EmergencyRetreat` | ✅ (reactive) | unit out of danger |

Reward hooks (brief §17.4, high-water-mark / first-achievement): reward the
*first* completion of `BUILD_SCHEMATIC east_duo_line`, each *new* wave survived,
net copper delivered to the turret sink (not raw mined — anti-exploit §17.5), and
core/turret health preserved. Never reward raw mining, raw repair, or message
count (§17.5).

---

## 7. Numbers quick-reference (for task generators / reward code)

| Quantity | Value | Note |
|---|---|---|
| Ticks / second | 60 | fixed `1/60` delta |
| Mechanical Drill output (full 2×2 patch) | 0.37 copper/s | 0.092/s per single ore tile |
| Conveyor throughput | 6.5 items/s | one lane trunks ~17 drills |
| Duo DPS (copper) | 27 | 9 dmg × 3 shots/s |
| Duo range | 20 tiles (160 u) | out-ranges Dagger (18.75) |
| Duo copper burn (full fire) | 1.5 copper/s | magazine 15 copper = 30 shots = 10 s |
| Copper Wall HP | 320 | cost 6 copper |
| Duo HP | 250 | cost 35 copper |
| Dagger HP / DPS | 150 / 41.5 | armor 0, range 18.75 tiles |
| Core (Sharded) HP | 1100 | no weapon |
| Alpha build / mine | buildSpeed 0.5 / mineSpeed 6.5, tier 1 | flying, carries 30 |

**Could not verify / left as modelling assumptions:** the Dagger's *effective*
(decelerating) approach speed through the kill-zone — only the 3.75 tiles/s cap
is source-derived; the exposure-time estimate uses a conservative ~2–3 tiles/s.
Turret-vs-wall bullet clearance ("turrets fire over an adjacent wall") is
standard game behaviour, asserted from the geometry, not line-cited here.

## Sources

Engine source: this checkout, `Anuken/Mindustry@v159.7` (`c9686eb`), files cited
inline. Community strategy (qualitative only):

- [Guide: Simple strategies for beginners — Mindustry Unofficial Wiki](https://mindustry-unofficial.fandom.com/wiki/Guide:_Simple_strategies_for_beginners) (recovered via search; direct fetch returned HTTP 402)
- [Strategies — Mindustry Wiki (Fandom)](https://mindustry.fandom.com/wiki/Strategies)
- [Tips for Beginners — Steam Community Discussions](https://steamcommunity.com/app/1127400/discussions/0/3266809271724213356/)
- [A Comprehensive Guide for Mindustry Beginners (2024) — PaperNodes](https://papernodes.com/a-comprehensive-guide-for-mindustry-beginners-2024/)
