# Scenarios

This document specifies the loadable training/demo scenarios. Companion strategy
and balance reasoning lives in `docs/STRATEGY_NOTES.md`; the machine-readable
form of each scenario lives under `scenarios/<id>/scenario.json` (schema:
`scenarios/schemas/README.md`).

Coordinate convention (all scenarios): Mindustry **tile** coordinates, origin
`(0,0)` at the **south-west** corner, `x` increases **east**, `y` increases
**north**. `tilesize = 8` world units; simulation runs at **60 ticks/second**
(fixed `1/60` delta, `docs/ENGINE_NOTES.md` §2.4). Multiblock placement uses the
**center** tile for odd sizes (a 3×3 core placed "at (24,24)" occupies
`x∈[23,25], y∈[23,25]`), matching `Tile.setBlock` and the M1 loader
(`rl-server/.../Scenario.java:57`).

---

# bootstrap-defense-v0

A tiny custom Serpulo cooperative survival scenario for fast reset, obvious task
decomposition, and measurable teamwork (brief §12). **Not the campaign.** The M1
spike already loads a flat-stone/copper-patch/one-core world procedurally in code
(`rl-server/.../Scenario.java`); this spec is the full v0 that extends that
generator with a second/third ore patch, an east enemy spawn, a deterministic
3-wave schedule, and a scored objective decomposition. It stays fully
**procedural (no `.msav` on disk)** so it matches what the loader can build
(`docs/ENGINE_NOTES.md` §4.2, `World.loadGenerator`).

- `scenario_id`: `bootstrap-defense-v0`
- `scenario_version`: `1`
- Engine pin: `Anuken/Mindustry@v159.7` (`c9686eb`)

## World

- **Size:** 48 × 48 tiles (`x,y ∈ [0,47]`).
- **Floor:** flat `stone` everywhere → fully buildable, deterministic pathing
  (no ridges/water). Extends the M1 `generate()` loop directly.
- **Core:** one `coreShard` (Team `sharded`) at center **(24, 24)**, occupying
  `x∈[23,25], y∈[23,25]`. HP 1100, item capacity 4000 (`Blocks.java:3127`).
- **Enemy spawn:** one point on the **east** edge at **(46, 24)** (Team `crux`).
  Waves path west toward the core along the `y≈24` corridor.
- **Ore patches** (overlay = ore floor; drills go on top):

  | Patch | Ore | Rect (inclusive tiles) | Size | Purpose |
  |---|---|---|---|---|
  | A (main copper) | `oreCopper` | `x∈[27,32], y∈[27,32]` | 6×6 | primary economy; drills → trunk → core & turrets |
  | B (support copper) | `oreCopper` | `x∈[28,31], y∈[18,21]` | 4×4 | protected local ammo feed for the east Duos |
  | C (lead) | `oreLead` | `x∈[16,19], y∈[27,30]` | 4×4 | **optional in v0** (economy teaching / v1 variation) |

  All patches clear the 3×3 core footprint and each other. Lead is *not* consumed
  by any v0-allowed block (§Rules) — it is present so `HARVEST_RESOURCE` and the
  two-resource economy can be taught, and so v1 can require it. A v0 win never
  needs lead.
- **East approach lane (design region, not a wall):** the open stone corridor
  `x∈[26,46], y∈[21,27]` between the core area and the spawn. This is the
  `DEFEND_REGION` target and the intended firing kill-zone. The map itself does
  not wall it — funneling is the agents' job (the reference schematic below).
- **Buildable flat area:** the entire map except the core footprint and tiles
  currently carrying an agent/enemy unit. Ore tiles are buildable (drills sit on
  them). No weather, no fog.

### ASCII sketch (schematic — exact coords in the tables above)

Each cell ≈ a few tiles; `N` at top. Not to exact scale — the coordinate tables
are authoritative for the generator.

```
    x=0                      x=24                       x=47
y=47 +----------------------------------------------------------+
     |                                                          |
     |     [C:lead]        [A:copper]                           |
     |     16-19,27-30     27-32,27-32                          |
     |                                                          |
y=24 |                  ##### CORE #####        ...east lane... ►S   <- spawn (46,24)
     |                  # (23-25,23-25) #     Duos@32,{23,25}       daggers path west
     |                                        wall col @ x=33       along y≈24
     |                        [B:copper]                        |
     |                        28-31,18-21                       |
     |                                                          |
y=0  +----------------------------------------------------------+
```

The defensive line (built by agents, not part of the terrain):

```
        approach (east, +x) ─────────────►  enemies
                                   x=34   x=33   x=32
   y=26                            .      [W]     .
   y=25                            .      [W]    [Duo]
   y=24   ... core at x=24 ...     .      [W]     .      <- lane centerline
   y=23                            .      [W]    [Duo]
   y=22                            .      [W]     .
                              (2nd layer  (front  (turrets fire east,
                               optional)   wall)   protected behind wall)
```

## Rules

- **Allowed content (whitelist).** Placeable blocks: `mechanicalDrill`,
  `conveyor`, `junction`, `router`, `duo`, `copperWall`. Controllable unit:
  `alpha` (core builder). Nothing else may be placed or spawned by agents.
  (Mender, power, factories, other turrets/walls, other units → later stages,
  brief §12.2.)
- **No tech tree.** All allowed content is available from tick 0
  (`rules.researched` pre-populated / tech gating off). No launch/planet/sector
  metagame.
- **Teams:** player/agents = `sharded`; enemies = `crux` (`waveTeam`).
- **Ruleset flags** (extends `Scenario.buildRules`, `rl-server/.../Scenario.java:34`):
  `waves = true`, `canGameOver = true` (core loss ends episode), `fog = false`,
  `pvp = false`, `attackMode = false`, `infiniteResources = false`,
  `unitCap` small (e.g. 6 — enough for 2–4 builders + margin).
- **Starting loadout:** core seeded with **250 copper, 0 lead** (see the ammo
  arithmetic below — enough to build the reference defense and most ammo, but the
  team must still mine/supply the remainder, so `HARVEST`/`BUILD_LINE`/`SUPPLY`
  are all genuinely required).
- **Deterministic wave schedule** — 3 waves, fixed spawn ticks, Dagger-only
  (`dagger`, `UnitTypes.java:99`), spawned at (46,24):

  | Wave | Spawn tick | Sim time | Enemies |
  |---|---|---|---|
  | 1 | 2700 | 45 s | 3 × dagger |
  | 2 | 4500 | 75 s | 4 × dagger |
  | 3 | 6300 | 105 s | 5 × dagger |

  Total 12 daggers. No spawn-position jitter in v0 (see §Parameters/seeds); all
  spawn at the single point. Ground units, so `Pathfinder` seeds from
  `state.wave` deterministically (`docs/ENGINE_NOTES.md` §6).
- **Win condition:** the core is alive (`health > 0`) at **tick 8100** (30 s
  after wave-3 spawn — ample to clear 5 daggers, see arithmetic). Reaching that
  tick with the core intact = episode success.
- **Lose conditions:** core destroyed at any tick (`canGameOver` fires
  `Logic.gameOver`), **or** the episode tick cap is reached with an unmet win
  condition (treated as truncation/failure).
- **Episode tick cap:** **9000 ticks (150 s)**. The stepper truncates here
  regardless.

## Wave survivability arithmetic

All inputs are engine-verified (`docs/STRATEGY_NOTES.md` §1,2,5). Two Duos with
copper ammo = **54 DPS** combined; each Duo drains **1.5 copper/s** at full fire.
Dagger: 150 HP, 41.5 DPS, armor 0. Copper Wall: 320 HP. Core: 1100 HP.

**(a) Can 2 fed Duos clear wave 3 (the binding case, 5 daggers)?**
Turrets focus-fire the nearest dagger; kill time per dagger = `150 / 54 = 2.78 s`.
Sequential deaths at t = 2.78, 5.56, 8.33, 11.1, **13.9 s** → wave 3 fully cleared
in **13.9 s**, well inside the 30 s win window. ✅

**(b) Does the defensive line outlast the incoming damage?**
Each dagger fires 41.5 DPS until it dies. Summing damage dealt over each dagger's
lifetime (death times above): `41.5 × (2.78+5.56+8.33+11.1+13.9) = 41.5 × 41.67 ≈
1729 damage` delivered by the whole wave. Reference line HP = 5 walls × 320 + 2
Duos × 250 = **2100 HP > 1729**. Spread across the line, the wave cannot break
through to the core (1100 HP, never touched). ✅
*Concentration caveat (honest):* with a fully open front, focus fire on the
center wall tile (up to 5 × 41.5 = 207 DPS) breaks one 320-HP tile in ~1.5 s,
faster than the queue clears. Mitigations, both cheap: (1) the **2-tile funnel**
caps concurrent shooters to ~2 → ~83 DPS on the front, so a front tile lasts
~3.85 s; (2) a **2-deep wall** (front tile + backup) gives ~7.7 s of soak per
lane, outlasting the 13.9 s clear when combined with the funnel. The reference
schematic below uses a single wall column; agents are expected to thicken/funnel
it, and doing so is a scored `BUILD_SCHEMATIC`/`DEFEND` competency.

**(c) Lose if the team builds nothing.** With no turrets, daggers path unopposed
to the core: wave 1's 3 daggers deal `3 × 41.5 = 124 DPS`; core 1100 HP → dead in
**8.9 s** of contact. An undefended core cannot survive even wave 1 to
completion, and certainly not wave 3. ✅ (Genuine "must build to win.")

**(d) Ammo / supply budget (whole episode).**
Shots to clear 12 daggers = `12 × 150 / 9 = 200 shots` (perfect hits) → 200 ammo
units → **100 copper minimum**, budget **~140 copper** with overkill/misses. A
Duo magazine holds `30 / 2 = 15 copper` (30 shots, 10 s of fire), so magazines
alone (2 × 15 = 30 copper) cover only part of wave 3 — **the drill line must be
feeding the turrets by wave 2** or they run dry. Reference build cost ≈ 2 Duos
(70) + 2 drills (24) + ~14 conveyor (14) + junction (3) + router (3) + 5 walls
(30) = **~144 copper**. Total demand ≈ 144 build + 140 ammo ≈ **~284 copper**.
Loadout 250 → the team must mine ≥ ~35 copper and route ammo forward; two drills
at 0.37 copper/s over 105 s produce ~78 copper, covering the gap with margin. ✅

## Objective decomposition

Team objective (brief §12.3): *establish a copper supply line, construct and
supply two east-facing Duo turrets, repair damage, and survive three waves.*
Concrete task instances (TaskTypes per brief §10.2; predicate variables are the
canonical hash inputs of `docs/ENGINE_NOTES.md` §10). Coordinates are tile
coords.

| # | Task | TaskType | Target | Completion predicate | Precedes |
|---|---|---|---|---|---|
| T1 | Hand-mine copper to bootstrap | `HARVEST_RESOURCE` | patch A `(27..32,27..32)` | `core.items[copper]` reaches ≥ 300 cumulative delivered (net, source=ore) | T4 (softly), T5 |
| T2 | Lay drill+conveyor copper line | `BUILD_LINE` | drills on patch A → conveyor trunk → core `(24,24)` | ≥ 2 `mechanicalDrill` complete on ore **and** ≥ 1 conveyor path connects a drill to the core; sustained core copper inflow ≥ 0.6/s | T5 |
| T3 | Build east defensive schematic | `BUILD_SCHEMATIC` (`east_duo_line`) | Duos @ `(32,23)`,`(32,25)`; walls @ `x=33, y∈{22..26}` | all 7 footprint blocks (2 Duo + 5 wall) `state == ready` (built) | T5, T6 |
| T4 | Supply the east Duos | `SUPPLY_TURRET` | Duos @ `(32,23)`,`(32,25)` | both Duos `totalAmmo ≥ 10` (≥5 copper) held, refreshed each wave | T6 |
| T5 | Hold the east lane | `DEFEND_REGION` | region `x∈[26,46], y∈[21,27]` | region enemy (`crux` unit) count returns to 0 after each wave | win |
| T6 | Repair the line between waves | `REPAIR_REGION` | region `x∈[30,35], y∈[20,28]` | all owned blocks in region health fraction ≥ 0.9 before next spawn tick | (recurring) |
| T7 | Assist a stalled builder | `ASSIST_BUILD` | any agent's incomplete `BuildPlan` | target plan reaches `ready` | (opportunistic) |

**Reference schematic `east_duo_line` (`scenarios/bootstrap-defense-v0/schematics/east-duo-v1`, planned):**
`copperWall` at `(33,22),(33,23),(33,24),(33,25),(33,26)`; `duo` at `(32,23)` and
`(32,25)`, both facing **east (rotation 1 / +x)**. Cost 5×6 + 2×35 = **100
copper**. Agents may extend with a second wall column at `x=34` and a supply
router at, e.g., `(30,24)`.

**Expected precedence graph** (mirrors `docs/STRATEGY_NOTES.md` §3):

```
 loadout(250 copper) ──┬──► T2 BUILD_LINE ──┐
                       │                     ├──► T4 SUPPLY_TURRET ──┐
 T1 HARVEST (bootstrap)┘   T3 BUILD_SCHEMATIC┘  (needs T3 to exist)   ├──► T5 DEFEND ──► win
                                    │                                 │
                                    └───────────────► T6 REPAIR ◄─────┘  (recurring, wave-gated)
                                    T7 ASSIST_BUILD: opportunistic, unblocks T2/T3
```
Hard edges: T3 → T4 (can't supply turrets that don't exist); T2 → T4 (sustained
ammo for wave 3 needs the line, per arithmetic (d)); {T2,T3,T4} → T5 (defence
needs fed turrets); loadout **or** T1 → building tasks (need copper in hand).
Siblings T1/T2/T3 run concurrently across the 2–4 agents (the Copper/Shield/Relay
split, brief §1).

## Scenario parameters and seeds

- **`root_seed` derivation** feeds `Mathf.rand` at reset (`docs/ENGINE_NOTES.md`
  §6); with `rules.waves = true`, pathfinding/targeting RNG seed from
  `state.wave` and are deterministic regardless of `root_seed`.
- **v0: nothing varies with `root_seed`.** Ore patches, spawn point, wave ticks,
  wave composition, and loadout are all fixed constants of `scenario_version = 1`.
  `root_seed` still flows through for replay-manifest completeness and to exercise
  the seeding path, but two different seeds produce identical maps in v0. This is
  intentional (brief §12: prove the stack before adding variation).
- **Planned variation axes (v1+, each bumps `scenario_version`; brief §13 Stage G):**
  1. Ore patch positions jitter (patch A/B/C origin offset within bounded boxes,
     seeded from `root_seed`).
  2. Approach lane / spawn side (east vs a second north or south approach).
  3. Wall/obstacle scatter in the buildable area (forces re-pathing → tests
     deterministic `ControlPathfinder`, `docs/ENGINE_NOTES.md` §5.3).
  4. Wave timing and composition jitter (±ticks, occasional extra dagger).
  5. Starting loadout amount (tighter copper → harder economy).
  6. Agent count (1 / 2 / 4) and a delayed/missing teammate.
  7. Allowed-block subset (e.g., withhold `router`).
  Held-out seeds/families are reserved for evaluation (brief §3.9, §22.2).

## Acceptance demonstration script (brief §12.4)

The scripted v0 demo (deterministic task selection is acceptable) must produce
this announcement sequence — rendered from real structured commitments, not
post-hoc narration (brief §1, §11.7):

1. **[Agent Copper] Starting: establish copper line to the core.** — claims T2
   (`BUILD_LINE`), begins placing drills on patch A + conveyor trunk.
2. **[Agent Shield] Starting: build east defence. Requesting 1 helper.** — claims
   T3 (`BUILD_SCHEMATIC east_duo_line`), emits `REQUEST_HELP`.
3. **[Agent Relay] Helping Shield: deliver copper to the east Duos.** — `OFFER_HELP`
   accepted; claims T4 (`SUPPLY_TURRET`) as Shield's helper contract.
4. The task board records Shield's claim + Relay's accepted helper contract
   (leases visible, brief §11.5).
5. Agents execute real Mindustry actions (build plans, mining, item transfer) —
   no teleport/free resources (brief §15.3).
6. A deliberately blocked task (e.g., a wall tile of the schematic is occupied /
   copper short) triggers **[Agent Shield] Blocked: 18 copper short. Waiting up
   to 20 seconds.** → `BLOCKED` announcement and replanning (helper re-routes).
7. The team survives waves 1–3 with the core alive at tick 8100 →
   **[Team] Survived wave 3. Core intact.**
8. Same `root_seed` + scripted action/coordination trace reproduces identical
   state hashes at checkpoint ticks (brief §7.6, Gate 1).
9. The demo server lets a human join and observe the same announcements in real
   time (human-demonstration mode, brief §1).

## Versioning

`scenario_version` is an integer that pins the **observable scenario contract**:
world size, floor, core position, ore-patch rects, spawn point(s), wave schedule
(ticks + composition), allowed-content whitelist, starting loadout, win/lose
conditions, and tick cap. **Any change to those bumps `scenario_version`** and
invalidates prior golden hashes/checkpoints for this scenario (brief §12,
determinism §7.5). `scenario_version = 1` is the spec above. Cosmetic doc edits
that do not change loaded state do **not** bump it. The pair
`(scenario_id, scenario_version)` plus `root_seed` fully identifies a v0 episode
map; it is recorded in every run manifest (brief §21.1) and in the reset
response metadata.
