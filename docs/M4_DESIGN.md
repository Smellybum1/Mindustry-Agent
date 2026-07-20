# M4 Design — Build, Supply, Rebuild, Defend Skills

Status: approved design; implementation in progress (M4.1 completed 2026-07-20).
Author: Fable bootstrap pass, 2026-07-20.
Prereqs: M3 verified (skill layer + agent units); bootstrap-defense-v0 scenario
loader with waves (in progress) — Defend/Rebuild need live enemies to be testable.
Related: docs/M3_DESIGN.md (patterns to follow), docs/ENGINE_NOTES.md §8,
docs/STRATEGY_NOTES.md (verified numbers), docs/SCENARIOS.md (east_duo_v1 target).

## Principles carried over from M3

Engine-free FSMs in `agentcore.skill` driving an extended `AgentBody` port;
only `SkillController` touches the engine. Deterministic; typed reasons;
no free items or teleports; all mutations on the sim thread.

## Skills

### S1. BuildBlock(block, x, y, rotation)

- Enqueue a `BuildPlan` on the unit's queue (BuilderComp); navigate into build
  range; the ENGINE consumes core resources and constructs at `buildSpeed`
  (alpha 0.5) — we never place blocks directly.
- SUCCEEDED when the target tile holds the completed block (team ours, health
  full on completion); BLOCKED(RESOURCES_SHORT) when the core lacks the cost
  (verify exact engine behaviour: plans stall rather than fail — detect stall
  via no-progress ticks on `plan.progress`); BLOCKED(OCCUPIED) if the footprint
  has a conflicting building; FAILED if the plan is removed externally.
- Verify-first: does headless building consume core items with default rules
  (`state.rules.infiniteResources=false`)? Cite the consumption path.

### S2. ExecuteSchematic(name, anchorX, anchorY)

- A schematic = ordered list of BuildBlock specs, stored as data in
  `scenarios/schematics/<name>.json` (single source of truth; e.g.
  `east_duo_v1`: 2 Duos + copper walls per docs/SCENARIOS.md layout).
- Sequential S1 executions (order = list order — walls last so turrets fire
  early? No: spec order is authoritative; SCENARIOS.md says turrets first).
- Progress = completed blocks / total. BLOCKED propagates the inner reason.

### S3. SupplyBuilding(buildingPos, item, amount)

- Withdraw from core via the legal reverse-transfer path (verify candidates:
  `Call.requestItems`/`core.removeStack` + `unit.addItem` — must mirror what a
  real player/unit interaction does; cite it), navigate to the building,
  `Call.transferItemTo` (same call as M3 deliver, target = the building).
- Turrets accept copper as ammo through `ItemTurret.handleStack/acceptStack`
  (verify); SUCCEEDED when `amount` delivered or the building refuses further
  stock (report actual delivered in the result); BLOCKED(CORE_SHORT) if the
  core cannot supply.

### S4. RebuildRegion(rect)

- "Repair" for M4 is scoped to what alpha units actually support: re-building
  destroyed team blocks. Destroyed buildings are recorded in
  `team.data().plans` (broken-block queue — verify field name); the skill
  enqueues those within `rect` as build plans (engine rebuild semantics, cost
  paid from core again).
- True heal-repair of damaged-but-standing blocks is NOT a unit capability for
  alpha (no healing weapon); scenario v1 may add a Mender block instead.
  Document this honestly in observations (block health visible; agents cannot
  top it up in M4).
- SUCCEEDED when no broken blocks remain in rect; RUNNING otherwise; BLOCKED
  propagates S1 reasons.

### S5. DefendRegion(anchorX, anchorY, radius, durationTicks)

- Navigate to anchor; while enemies exist within `radius` of the anchor,
  target the nearest (deterministic tie-break: lowest unit id) and let the
  unit's own weapon fire (SkillController implements the AIController
  targeting hooks; the engine handles aim/shoot legality — alpha's small gun,
  ~9 dmg; agents are skirmish support, Duos do the real work per
  STRATEGY_NOTES).
- Kiting/retreat-on-low-health is NOT in M4 (EmergencyRetreat is separate and
  simple: navigate to core, cancel plans).
- Termination: SUCCEEDED at durationTicks elapsed with no enemies in region;
  RUNNING otherwise. Never BLOCKED by mere enemy presence.

### S6. EmergencyRetreat()

- Cancel build queue, drop nothing (cargo kept), navigate to core tile,
  SUCCEEDED on arrival.

## Action schema (additive, protocol v1)

New command types: `BUILD {block, x, y, rotation}`, `SCHEMATIC {name, x, y}`,
`SUPPLY {x, y, item, amount}`, `REBUILD {x1, y1, x2, y2}`,
`DEFEND {x, y, radius, ticks}`, `RETREAT {}`. Validation as in M3
(action_results[], typed reasons, never a crash). Observations gain, per agent:
build queue depth + current plan progress; team obs gains broken-block count.

## Hash

Build plans (ordered queue: block/pos/progress quantized), broken-block queue
size, and turret ammo counts join the canonical hash — schematic execution and
supply runs must perturb it deterministically.

## Testing

- FSM unit tests with stubbed `AgentBody` (mirror M3's 13).
- Integration (real engine, scripted): build a single Duo from core stock —
  assert core copper decreased by exactly the Duo cost (35 per STRATEGY_NOTES;
  cite Blocks.java) and the building exists; supply 30 copper to it — assert
  turret ammo increased accordingly and core decreased by exactly 30;
  schematic east_duo_v1 completes; determinism across two processes with the
  full build+supply trace; smoke ledger extended to cover build/supply flows.
- With waves live: defend integration — 2 supplied Duos + 1 defending agent
  survive wave 1 per SCENARIOS.md arithmetic; rebuild integration — destroy a
  wall via wave, rebuild it, assert costs.

## Non-goals

Mender/power (scenario v1+), CommandAI/pathfinder use for agent units (flat
map straight-line steering still sufficient; revisit with obstacles), task
board wiring (M5), rewards (M7), multi-unit squads.

## Open questions for the implementer (resolve against source, record here)

1. Core resource consumption path for unit build plans headlessly (file:line).
2. Legal core-withdrawal call for S3 and its constraints (amount caps, range).
3. Exact field for the broken-block/rebuild queue and its determinism
   (iteration order) for S4.
4. Turret ammo accounting for hash inclusion (ItemTurret ammo representation).
5. Duo build cost cited from Blocks.java at the pin (STRATEGY_NOTES says 35
   copper — confirm).
