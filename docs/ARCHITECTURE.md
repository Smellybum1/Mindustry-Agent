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

M7.2's `ExpertCoordinationDriver` remains the one in-process coordination
driver used by the real-time plugin and the fixed-step parity option. M7.3's
primary training expert instead selects the public candidate table through the
external task-action contract—the exact seam a learned selector will use. Both
paths share `ExpertCoordinationPlan`, `HandTunedUtility`, board semantics, and
skills. The remaining stage-local candidate construction in the in-process
driver is explicitly tracked in `docs/CANDIDATE_GAPS.md`; policy code has not
been copied back into `agent-plugin`.

## Module responsibilities

### Java (Gradle modules layered on pinned upstream engine)

| Module | Package | Depends on | Responsibility |
|---|---|---|---|
| `rl-server` | `mindustry.rl` | `:core`, `:server` | Headless externally-stepped launcher: init content once, fixed-step loop, load scenario, reset in-process, apply atomic action bundle at decision boundary, advance exact ticks, extract observations/rewards, return deterministic state hash, serve health/handshake/reset/step/close. Disables ordinary networking unless testing parity. |
| `agent-core` | `agentcore` | `:core` | Agent identity, task catalog + validation, shared scripted coordination driver and scenario plan, task board, intention/offer/claim/lease protocol, skill executors, candidate task generation, action masks, observation construction, reward accounting, metrics, announcement templates, structured event log. **No Python/RL dependency.** |
| `agent-plugin` | `mindustry.agentplugin` | `:core`, `:agent-core`, selected project-owned `:rl-server` adapters | Real-time dedicated-server adapter for demo mode. A loadable stock-server plugin that starts the exact scenario, spawns/rebinds three controlled Alphas, adapts the shared coordination driver to legal engine skills, renders approved announcements, and exposes status/pause/resume/emergency-stop controls. It owns pacing, engine/IO adaptation, controls, and telemetry—not a separate coordination policy. |

Upstream modules (`core`, `server`, `desktop`, `annotations`, `tools`, `tests`)
are unmodified except for the `settings.gradle` registration edit
(`docs/UPSTREAM_PATCHES.md`).

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

## Where the design is still open

The exact-engine stepping mechanism (how the wall-clock loop is replaced, which
`Logic`/`Application` hooks are used, stable-hash construction) is being designed
on a separate track and documented in `docs/ENGINE_NOTES.md` (owned by that
track; not edited here).
