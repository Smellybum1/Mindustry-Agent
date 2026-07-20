# Scenario schemas

Home for the schema that validates scenario definitions under
`scenarios/<id>/scenario.json`. The first concrete scenario,
`bootstrap-defense-v0`, ships a machine-readable `scenario.json`; this file
documents its schema **inline** (a formal `scenario.schema.json` JSON-Schema file
lands with the loader in roadmap M6 — until then this doc is the contract, and
`docs/SCENARIOS.md` is the human-readable source of truth).

Compatibility: `scenario_version` (in each `scenario.json`) pins the observable
scenario contract and maps to the protocol `scenario_schema_version` field
(`docs/PROTOCOL.md`). Bump it whenever any loaded value below changes.

## Conventions

- **Coordinates** are Mindustry **tile** coords: origin south-west, `x` east,
  `y` north, `tilesize = 8`. Simulation is **60 ticks/second**. Multiblocks are
  placed by their **center** tile for odd sizes (see `coords` in the file).
- **Rects** are `{ "x", "y", "w", "h" }` with `(x,y)` the **south-west** corner
  and `w`/`h` the tile extents; the rect covers `x..x+w-1, y..y+h-1` inclusive.
- **Tiles** are `[x, y]` pairs. **Rotations** follow Mindustry: `0=+x (east)`,
  `1=+y (north)`, `2=-x (west)`, `3=-y (south)`. (In `scenario.json` the Duos use
  `rotation: 1`; the loader should orient turret facing toward the enemy lane —
  east — per `docs/SCENARIOS.md`; treat `rotation` as "facing" and reconcile with
  engine rotation enum at load time.)
- **Block/unit/item names** are Mindustry content string ids (e.g.
  `mechanical-drill`, `copper-wall`, `duo`, `dagger`, `ore-copper`, `core-shard`)
  — the `name` passed to each content constructor in
  `core/src/mindustry/content/*.java`.

## Top-level fields

| Field | Type | Meaning |
|---|---|---|
| `scenario_id` | string | stable id; matches the directory name |
| `scenario_version` | int | observable-contract version (see above) |
| `engine` | `{tag, commit}` | pinned engine the balance was verified against |
| `coords` | object | coordinate/tick conventions (documentation of the invariants above) |
| `world` | object | `width`, `height`, `floor`, `generator`, `weather`, `fog` |
| `core` | object | `block`, `team`, `center [x,y]`, `footprint_rect`, `health`, `item_capacity` |
| `loadout` | `{item: amount}` | items seeded into the core at play start |
| `ore_patches` | array | each `{id, ore, rect, role, required_to_win?}` |
| `enemy_spawns` | array | each `{id, team, tile [x,y]}` |
| `regions` | object | named `{rect}` regions used as objective targets |
| `allowed_content` | object | `blocks[]`, `units[]` whitelist; `tech_tree` bool |
| `rules` | object | ruleset flags applied to `state.rules` (mirrors `Scenario.buildRules`) |
| `wave_schedule` | array | deterministic waves (see below) |
| `termination` | object | `win`, `lose[]`, `tick_cap` |
| `reference_schematic` | object | the `east_duo_line` build: `blocks[]`, `copper_cost`, `path` |
| `objectives` | array | scored task instances (see below) |
| `seed_policy` | object | what varies with `root_seed` now vs planned |
| `balance_check` | object | engine-verified numbers + derived survivability results |

## `wave_schedule[]`

Each entry: `{ "wave": int, "tick": int, "spawn": <enemy_spawn id>, "spawns":
[ { "unit": <id>, "count": int } ] }`. Ticks are absolute simulation ticks from
play start (tick 0). Waves are Dagger-only in v0. The stepper spawns `count`
units of `unit` at the referenced spawn tile when `state.tick == tick`. Because
`rules.waves = true`, ground-unit pathfinding/targeting RNG seed deterministically
from `state.wave` (`docs/ENGINE_NOTES.md` §6).

## `objectives[]`

Each entry is a scored task instance:

| Field | Meaning |
|---|---|
| `id` | task instance id (`T1`..`Tn`) |
| `task_type` | one of the brief §10.2 catalog (`HARVEST_RESOURCE`, `BUILD_LINE`, `BUILD_SCHEMATIC`, `SUPPLY_TURRET`, `DEFEND_REGION`, `REPAIR_REGION`, `ASSIST_BUILD`, …) |
| `target` | `{kind, …}` — `ore_patch`/`path`/`schematic`/`buildings`/`region`/`any_incomplete_build_plan` |
| `predicate` | structured completion condition (see predicate vocabulary) |
| `precedes` | ids this task is a hard prerequisite for |
| `recurring` / `opportunistic` | booleans for non-one-shot tasks |

### Predicate vocabulary (v0)

Predicates are structured so completion is computable from the canonical state
(`docs/ENGINE_NOTES.md` §10) with no natural-language parsing:

- `cumulative_delivered_ge` `{item, amount, source}` — net items of `item` reaching
  the core from `source` (e.g. `ore`) ≥ `amount` (anti-exploit: net, not raw mined).
- `block_count_ge` `{block, on_ore?, count}` — ≥ `count` completed `block`s (optionally on ore).
- `conveyor_path_connects` `{from_block, to}` — a conveyor chain links `from_block` to `to`.
- `core_item_inflow_ge` `{item, rate_per_s}` — measured core inflow ≥ rate.
- `all_footprint_blocks_ready` `{schematic}` — every block of the schematic is built.
- `all_turrets_ammo_ge` `{tiles, total_ammo, sustained_each_wave?}` — each turret's `totalAmmo` ≥ threshold.
- `region_enemy_count_zero_after_each_wave` `{region}` — enemy units in region return to 0 post-wave.
- `region_block_health_fraction_ge` `{region, fraction, by?}` — owned-block health fraction ≥ target.
- `target_plan_ready` — the referenced `BuildPlan` reached `ready` (built).
- `all` `{of: [...]}` — conjunction of sub-predicates.

These are a pragmatic starting set; new predicate types are additive and do not
bump `scenario_version` unless they change what an existing scenario requires.

## `termination`

- `win`: `{ predicate: "core_alive_at_tick", core, tick }`.
- `lose[]`: `core_destroyed` and `tick_cap_reached_without_win`.
- `tick_cap`: hard truncation tick for the episode.

## Validation notes for the loader (M6)

- Reject any `blocks`/`units` not in `allowed_content`.
- Assert ore-patch rects and the core footprint do not overlap.
- Assert every `wave_schedule[].spawn` and `objectives[].target.ref` resolves to a
  declared `enemy_spawns`/`regions`/`ore_patches` id.
- Assert `wave` ticks are strictly increasing and `< tick_cap`; `win.tick <
  tick_cap`.
- Assert the reference schematic's block tiles lie inside the map and outside the
  core footprint.
