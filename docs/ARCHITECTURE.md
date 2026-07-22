# Architecture

System overview for `mindustry-coop-agents`, adapted from the project brief §6
to our accepted decisions (`docs/decisions/ADR-0001..0010`).

## Two modes, one behaviour core

The same scenario-derived plan, task-board semantics, skills, action schema, and
announcement templates drive both modes. Only the *pacing and policy entry
point* differ (ADR-0006, brief §7.3).

```text
                        TRAINING MODE
                        (deterministic, headless, externally stepped)

   PyTorch / TorchRL trainer            [python/src/mindustry_agents/training]
              |
   PettingZoo ParallelEnv               [.../env]   <- no torch import (ADR-0007)
              |
   Process supervisor                   [.../process]  one JVM per world (ADR-0003)
              |
   length-prefixed JSON over            (ADR-0004; docs/PROTOCOL.md)
   loopback TCP  -> Protobuf later
              |
   +----------+----------+----------+
   |          |          |          |
   v          v          v          v
 +--------+ +--------+ +--------+ +--------+
 | JVM 0  | | JVM 1  | | JVM 2  | | JVM N  |   rl-server: mindustry.rl.RlServerMain
 | world  | | world  | | world  | | world  |   exact Mindustry rules, no rendering
 | 2-4 AI | | 2-4 AI | | 2-4 AI | | 2-4 AI |   fixed delta 1/60 s, external step
 +--------+ +--------+ +--------+ +--------+


                        HUMAN DEMONSTRATION MODE
                        (real-time, joinable private server)

   ordinary Mindustry client(s)
              |
      normal server network (private, loopback/LAN)
              |
   dedicated server + agent-plugin      [agent-plugin]  real-time pacing
   reuses agent-core coordination/tasks/skills/announcements
              |
   policy process OR in-process scripted fallback
```

The real-time plugin now defaults to `PublicCandidateDemo`: the engine-neutral
Java fallback selects the public candidate table through the same typed task-
action contract used by the externally stepped training expert. Both paths use
`EngineCandidates`, masks, `CoordinationAdapter`, board semantics, reservations,
and skills. M7.2's `ExpertCoordinationDriver` remains available only through
`DEMO_PUBLIC_POLICY=0` as the accepted legacy regression oracle.

ADR-0057 made elimination of that seam a prerequisite for M10 human commands;
the prerequisite is now met. Structured human goals may next overlay candidates.
Command callbacks will parse and enqueue immutable input, and the simulation
thread will validate and apply it. `docs/M10_DESIGN.md` pins that accepted
contract; the human-control implementation does not yet exist.
`AgentRuntimeRegistry` decouples candidates, adaptive facts, feature extraction,
action decoding, and coordination from the training registry while preserving
`RlAgentRegistry` as the existing runtime facade. `DemoAgentRegistry` now
implements that contract and owns deterministic demo spawn/rebind lifecycle;
the engine-neutral Java `GreedyUtilityPolicy` mirrors the accepted fallback's
candidate/mask decisions. `PublicCandidateDemo` wires the default real-time
plugin through public candidates, masks, typed actions, board, reservations,
and skills. The public path
derives survival telemetry from simulation-thread world state and has passed
the stock-clock three-wave acceptance at tick 8100 with core health 1100. Its
probe-only trace supplies the exact candidate/mask/action/result sequence to a
Python fallback replay; 390 boundaries and 1,170 actions match, and the pinned
225-selection digest reproduces across fresh JVMs. The logistics seat persists
for an undersupplied combat phase, leaving only two phase-entry rebalances and
seven unassigned combat waits in the golden. Probe mode alone fixes delta,
seeds engine/physics randomness, and synchronously owns pathfinding; join and
survival retain stock real-time engine behavior.

## Module responsibilities

### Java (Gradle modules layered on pinned upstream engine)

| Module | Package | Depends on | Responsibility |
|---|---|---|---|
| `rl-server` | `mindustry.rl` | `:core`, `:server` | Headless externally-stepped launcher: init content once, fixed-step loop, load scenario, reset in-process, apply atomic action bundle at decision boundary, advance exact ticks, extract observations/rewards, return deterministic state hash, serve health/handshake/reset/step/close. Disables ordinary networking unless testing parity. |
| `agent-core` | `agentcore` | `:core` | Agent identity, task catalog + validation, shared scripted coordination driver and scenario plan, task board, intention/offer/claim/lease protocol, skill executors, candidate task generation, action masks, observation construction, reward accounting, metrics, announcement templates, structured event log. **No Python/RL dependency.** |
| `agent-plugin` | `mindustry.agentplugin` | `:core`, `:agent-core`, selected project-owned `:rl-server` adapters | Real-time dedicated-server adapter for demo mode. A loadable stock-server plugin that starts the exact scenario, spawns/rebinds three controlled Alphas, adapts the shared coordination driver to legal engine skills, renders approved announcements, and exposes status/pause/resume/emergency-stop controls. It owns pacing, engine/IO adaptation, controls, and telemetry—not a separate coordination policy. |

Upstream modules are preserved except for the narrowly catalogued deterministic
external-mode patches and `settings.gradle` registration edit in
`docs/UPSTREAM_PATCHES.md`.

### Python package (`python/src/mindustry_agents/`)

| Subpackage | Responsibility |
|---|---|
| `protocol` | Length-prefixed JSON framing + message dataclasses (mirrors `docs/PROTOCOL.md`). Stdlib only. |
| `env` | PettingZoo `ParallelEnv` facade; batches all agents in a world into one atomic step. Framework-neutral. |
| `process` | Launch/supervise JVM environments, timeouts, crash detection + restart. |
| `policies` | Scripted, heuristic, random-valid, IPPO, MAPPO policies (scripted before learned; IPPO before MAPPO). |
| `training` | IPPO/MAPPO training, checkpointing, export. Only layer that imports the RL stack. |
| `evaluation` | Seed-set eval, metrics/matrix, baseline comparisons, ablations. |
| `telemetry` | Run manifests, event logs, plots/tables/replay summaries; per-component reward breakdowns. |
| `tools` | CLI utilities: transcript inspectors, replay players, benchmark front-ends. |

## Threading rule (hard invariant)

> **I/O threads may parse and queue requests. Only the simulation/main thread
> may read mutable game state for an observation boundary or apply a game
> action.** (brief §23.6)

Mindustry global state (`Vars.state`, `Vars.world`, `Vars.logic`, pathfinders,
content, entity groups) is not thread-safe. Requests arrive on I/O threads, are
validated and queued, and are drained by the single simulation thread at a
decision boundary. Every deviation must be documented here.

_No documented exceptions._ The plugin registers callbacks and commands from
the server lifecycle, but every game-state read/mutation and board transition is
executed by the stock simulation thread. Client/network threads only enqueue
their command callbacks through Mindustry's existing command path.

## Determinism and reset paths

- **Step path**: request (I/O) → validated + queued → drained on sim thread →
  atomic action bundle applied → advance exactly `ticks_to_advance` updates at
  fixed delta (or, only when `stop_on_decision_event=true`, stop after the first
  authoritative decision event) → build observations → compute stable
  `state_hash` → response. The response always reports actual advanced ticks.
- **Reset path**: reset the world in-process without a JVM restart (ADR-0003);
  resolve an immutable scenario descriptor from id/version/`root_seed`; validate
  its bounded geometry/timing; clear all entities, tasks, rewards, and
  policy-visible state; re-seed and load on the simulation thread; return
  initial observations + `state_hash`. JVM restart is a crash-recovery
  mechanism, not the normal reset path.
- Reset drops callbacks posted by the outgoing episode before resetting the
  engine entity counter. Scenario v2 additionally reserves a disjoint
  deterministic entity-ID range immediately before each native wave, preventing
  lazy transient allocations from making wave identity depend on episode history.
- Adaptive rolling inflow evidence, scenario-event cursor, and recent
  coordination switching history are canonical hash inputs. Scenario version 2
  also hashes its fully resolved variation contract. These inputs are updated
  and read only on the simulation thread.
- Same seed + same action trace ⇒ identical `state_hash` (target: 10,000 ticks;
  brief §24 Gate 1).

### M8.4 deterministic runtime boundary

Both pathfinder workers are disabled before world load and stopped/joined on
reset. Every upstream async-process begin/process/end phase runs synchronously
on the simulation thread; the physics RNG is seeded from the episode root seed.
Building proximity callbacks are tile-ordered, sleeping building insertion is
canonical by reverse tile position, and removals preserve order with generated
indices repaired. Authoritative observations and hashes enumerate unique
tile-backed buildings rather than the sleeping `Groups.build` update subset.
Headless placement effects consume no audio RNG. Training JVMs use `-Xbatch`.

## Where the design is still open

The exact-engine stepping mechanism (how the wall-clock loop is replaced, which
`Logic`/`Application` hooks are used, stable-hash construction) is being designed
on a separate track and documented in `docs/ENGINE_NOTES.md` (owned by that
track; not edited here).
