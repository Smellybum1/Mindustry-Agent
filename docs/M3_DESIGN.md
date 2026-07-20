# M3 Design — Agent Entities and First Skills

Status: approved design, not yet implemented. Author: Fable bootstrap pass, 2026-07-20.
Prereqs: M1 verified (fixed-step rl-server), M2 in progress (process pool/facade).
Related: docs/ENGINE_NOTES.md (engine facts), docs/COORDINATION.md (board), ADR-0006.

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

1. Exact core-unit spawn API and how respawn/despawn interacts with
   `Logic.reset()` (ENGINE_NOTES §reset).
2. Whether agent units need a `flag`/tag to be excluded from any vanilla
   auto-control (rally, formations) — verify none applies headlessly.
3. Legal unit->core transfer call that works without net (candidates above).
4. Mining range/speed constants for acceptance-test arithmetic (cite source).
