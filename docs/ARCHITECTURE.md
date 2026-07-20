# Architecture

System overview for `mindustry-coop-agents`, adapted from the project brief §6
to our accepted decisions (`docs/decisions/ADR-0001..0010`).

## Two modes, one behaviour core

The same task board, skills, observations, action schema, and announcement
templates drive both modes. Only the *pacing and entry point* differ (ADR-0006,
brief §7.3).

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
   reuses agent-core tasks/skills/announcements
              |
   policy process OR in-process scripted fallback
```

## Module responsibilities

### Java (Gradle modules layered on pinned upstream engine)

| Module | Package | Depends on | Responsibility |
|---|---|---|---|
| `rl-server` | `mindustry.rl` | `:core`, `:server` | Headless externally-stepped launcher: init content once, fixed-step loop, load scenario, reset in-process, apply atomic action bundle at decision boundary, advance exact ticks, extract observations/rewards, return deterministic state hash, serve health/handshake/reset/step/close. Disables ordinary networking unless testing parity. |
| `agent-core` | `agentcore` | `:core` | Agent identity, task catalog + validation, shared task board, intention/offer/claim/lease protocol, skill executors, candidate task generation, action masks, observation construction, reward accounting, metrics, announcement templates, structured event log. **No Python/RL dependency.** |
| `agent-plugin` | `mindustry.agentplugin` | `:core`, `:agent-core`, selected project-owned `:rl-server` adapters | Real-time dedicated-server adapter for demo mode. A loadable stock-server plugin that starts the exact scenario, spawns three controlled Alphas, runs the scripted fallback through the shared task board/skills/announcement templates, and exposes status/pause/resume/emergency-stop controls. Its real-time policy builds/supplies the full expert defense, mines between waves, reacts to enemy presence, performs repair/resupply maintenance, and rebinds a lost stable agent slot to a replacement Alpha at the core with explicit telemetry. |

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
  atomic action-bundle applied → advance exactly `ticks_to_advance` updates at
  fixed delta → build observations → compute stable `state_hash` → response.
- **Reset path**: reset the world in-process without a JVM restart (ADR-0003);
  clear all entities, tasks, rewards, and policy-visible state; re-seed from
  `root_seed`; return initial observations + `state_hash`. JVM restart is a
  crash-recovery mechanism, not the normal reset path.
- Same seed + same action trace ⇒ identical `state_hash` (target: 10,000 ticks;
  brief §24 Gate 1).

## Where the design is still open

The exact-engine stepping mechanism (how the wall-clock loop is replaced, which
`Logic`/`Application` hooks are used, stable-hash construction) is being designed
on a separate track and documented in `docs/ENGINE_NOTES.md` (owned by that
track; not edited here).
