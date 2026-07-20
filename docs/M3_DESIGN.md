# M3 Design — Agent Entities and First Skills

Status: **IMPLEMENTED and verified 2026-07-20** (all four open questions resolved
in place below). Author: Fable bootstrap pass, 2026-07-20.
Prereqs: M1 verified (fixed-step rl-server), M2 verified (process pool/facade).
Related: docs/ENGINE_NOTES.md (engine facts), docs/COORDINATION.md (board), ADR-0006.

Implementation refinement of D3: the skill FSMs (`agentcore.skill.{NavigateTo,
MineResource,DeliverToCore,Wait}`) are kept **engine-free**, steering through a thin
`agentcore.skill.AgentBody` port (primitives + world coords) rather than importing
mindustry directly. Only the body wrapper — `mindustry.rl.SkillController` (extends
`AIController`, implements `AgentBody`) — touches the engine. This keeps the FSMs
unit-testable without content init (13 JUnit tests) while still letting the
agent-plugin demo reuse identical skills via its own body impl.

## Goal

Scripted single agents that mine copper and deliver it to the core in the exact
engine, via a skill layer that the M5 task board and a later learned policy can
drive unchanged. Exit criteria per docs/ROADMAP.md M3.

## Decisions

### D1. Agent identity and unit ownership

- `AgentId` (agentcore) stays engine-free. Engine side keeps a registry
  `RlAgentRegistry: agent_id -> {team, unit id, controller}` living with the
  episode; reset rebuilds it from the ResetRequest's `agent_count`.
- One builder-capable core unit type per agent (Serpulo core unit — verify exact
  `UnitTypes` entry, expected `alpha`), spawned adjacent to the core at
  deterministic offsets ordered by agent index. No network `Player` objects
  (brief §9). Units are marked so waves/AI never reassign them.

### D2. Control path: custom AIController per agent unit

Each agent unit gets a dedicated `AIController` subclass (`SkillController`)
installed as its controller. The active skill is a deterministic state machine
executed inside the controller's update on the simulation thread. We do NOT use
`CommandAI`/`UnitCommand` for M3: commanded movement consults the async
`ControlPathfinder`, whose threads are deliberately stopped in deterministic
mode (see ENGINE_NOTES). Straight-line/local steering is sufficient on the flat
bootstrap map; a synchronous pathfinding patch is deferred until a scenario has
obstacles (that will be the sanctioned upstream `syncUpdate()` edit, M4+).

### D3. Where code lives

- `agent-core` (depends on :core): `agentcore.skill` — `Skill` contract
  (tick(unit, world-ctx) -> SkillStatus + reason code + progress), and the
  engine-facing skill implementations. Board packages remain engine-free;
  skills may import mindustry classes. Rationale: agent-plugin (demo server)
  must reuse identical skills (brief §7.3); rl-server stays transport+loop.
- `rl-server`: `RlAgentRegistry`, `SkillController`, action decoding,
  per-agent observation building.

### D4. M3 skill set (in order)

1. `NavigateTo(x, y, tolerance)` — straight-line steering, arrive test,
   BLOCKED(reason=stuck) if no progress for N ticks.
2. `MineResource(item, tile)` — navigate into mine range, set `unit.mineTile`,
   SUCCEEDED when cargo full or target amount reached; BLOCKED if tile invalid.
3. `DeliverToCore` — navigate to core, transfer inventory via the same code
   path the game uses for unit->core transfer (verify: `Call.transferItemTo` /
   `CoreBuild.handleStack` — must be legal-action equivalent, no free items).
4. `Wait(ticks)`.
No teleports, no free resources (brief §15.3).

### D5. Action schema (protocol-additive, stays protocol_version 1)

`StepRequest.agent_actions[i] = {agent_id, command: {type: "NAVIGATE"|"MINE"|
"DELIVER_CORE"|"WAIT"|"CONTINUE", params...}}`. `CONTINUE` (or absent entry) keeps
the current skill running — the common case between decision boundaries. Every
action is validated on the sim thread; invalid -> accepted=false + reason code in
the response (`action_results[]`), never a crash. Task-level actions
(SELECT_CANDIDATE_TASK etc.) arrive with M5 on top of this layer.

### D6. Observation v2 (additive)

`StepResponse.observations[]` becomes per-agent:
`{agent_id, unit: {x, y, vx, vy, health, item, item_amount, mining, flag},
skill: {type, status, progress, reason}, team: <M1 world obs unchanged>}`.
Positions quantized to 1e-3 in the hash as today; raw floats in observations.
Task-board snapshot joins in M5. Local spatial grids deferred to Stage D
(learned policy) — scripted skills read exact state engine-side and do not need
grids serialized (keeps protocol overhead within Gate 6).

### D7. State hash extension

Hash gains: per-agent unit (id, type, quantized pos/vel, health, cargo) — already
covered by generic unit hashing if agent units are ordinary group members
(verify) — plus registry (agent_id -> unit id) and each agent's
{skill type, status, progress-quantized}. Golden replays must break if a skill
state machine changes behavior.

### D8. Testing

- Java: `agent-core` unit tests for skill state machines against fake
  minimal contexts where feasible; integration tests behind a Gradle task
  (`rl-server:integrationTest`) that boots headless content once per JVM and
  runs mine/deliver scenarios — kept out of the default `test` task (slow).
- Python: extend smoke to issue NAVIGATE/MINE/DELIVER and assert core copper
  increases by the mined amount exactly; determinism harness gains a scripted
  action trace (same trace, same hashes — this finally exercises seeds once
  scenario v1 adds jitter).
- Acceptance (ROADMAP M3): scripted agent mines and delivers copper from
  multiple seeded starts; failure reasons observable in responses.

## Non-goals for M3

Building/schematics (M4), repair/defend (M4), task board wiring and candidate
generation (M5), any reward emission (M7 — REWARD_AUDIT.md gates it), pathfinder
patch, Erekir content, multi-world-per-JVM.

## Open questions for the implementer (resolve against source, record here)

**All four resolved during M3 implementation (2026-07-20). Answers below, cited
against this checkout (v159.7).**

1. **Exact core-unit spawn API and reset interaction. RESOLVED.**
   Spawn via `UnitTypes.alpha.spawn(Team, worldX, worldY)`
   (`core/src/mindustry/type/UnitType.java:611` → `:573`, which does
   `create(team)` → set pos → `unit.add()`); then replace the controller with
   `unit.controller(new SkillController(i))`
   (`UnitComp.controller(UnitController)` at `core/src/mindustry/entities/comp/UnitComp.java:455`).
   `Units.notifyUnitSpawn(unit)` mirrors the engine's own spawn idiom
   (`Logic.java:573`). No despawn handling is needed: `Logic.reset()` →
   `Groups.clear()` (`Logic.java:300`) removes **all** units, so the registry is
   rebuilt from scratch each episode after `logic.play()`. Agent units are **not**
   `spawnedByCore`, so the core-unit auto-removal at `UnitComp.java:848-849` never
   fires. Implemented in `RlAgentRegistry.rebuild()`; verified leak-free and
   hash-stable over 1000 stress resets.

2. **Flag/tag to exclude from vanilla auto-control. RESOLVED: none needed.**
   The three per-team AI paths in `Logic.update()` — `buildAi` (`:555`), `rtsAi`
   (`:560`), and `prebuildAi` core-unit spawn (`:566-577`) — are all gated on
   `Rules` flags that default `false` and stay `false` in this scenario
   (`core/src/mindustry/game/Rules.java:357,360,365`). `Team.sharded` is
   `state.rules.defaultTeam`, so `Team.isAI()` is `false`
   (`core/src/mindustry/game/Team.java:112-114`) → no wave/flowfield control.
   `AIController.isValidController()` defaults `true`
   (`core/src/mindustry/entities/units/UnitController.java:14`), so the engine
   never resets our controller (`UnitComp.java:844`). Therefore no flag/tag is
   required headlessly under this ruleset.

3. **Legal unit->core transfer call. RESOLVED:** `Call.transferItemTo(unit, item,
   amount, x, y, core)` (`core/src/mindustry/input/InputHandler.java:247`) — the
   exact path `MinerComp` uses (`MinerComp.java:81,106`). It removes `amount` from
   `unit.stack` (`:250`) and calls `core.handleStack(item, amount, unit)` (`:256`),
   which adds to `core.items` clamped to capacity
   (`CoreBlock.java:738-741`, `BuildingComp.java:801-803`). Gate the amount with
   `core.acceptStack(item, unit.stack.amount, unit)` (`BuildingComp.java:779-784`,
   returns `min(headroom, requested)`) so no free items and no overflow. Net-safe
   headlessly (`net.active()==false`, ENGINE_NOTES §8.3). Implemented in
   `SkillController.transferCargoToCore()`.

4. **Mining range/speed constants. RESOLVED.**
   - `mineRange = 70f` world units (`UnitType.java:94` default; `alpha` does not
     override) = 8.75 tiles.
   - `mineTransferRange = 220f` world units (`core/src/mindustry/Vars.java:105`) =
     27.5 tiles (the copper patch sits ~8 tiles from the core, so a miner is always
     within transfer range — capacity-triggered auto-dump is avoided by keeping the
     mine target below `itemCapacity`).
   - `alpha`: `mineSpeed = 6.5`, `mineTier = 1`, `itemCapacity = 30`
     (`core/src/mindustry/content/UnitTypes.java` alpha block).
   - `mineHardnessScaling = true` (`UnitType.java:390` default) → per-item threshold
     `50 + hardness*15`; copper `hardness = 1` (`Items.java:17`) → **65**. Accrual
     `mineTimer += 1.0*6.5*1.0` per tick → **1 copper / 10 ticks**. The
     mine→inventory transfer is deferred by `Fx.itemTransfer.lifetime = 12` ticks
     (`InputHandler.createItemTransfer` → `transferItemToUnit`, `Fx.java:138`), which
     is why `MineResource` drains to cargo-stability before succeeding. Verified in
     the smoke: target 20 → carried 21 (one deferred item lands after the observed
     cargo crossed the target), delivered exactly 21, core delta exactly 21.
