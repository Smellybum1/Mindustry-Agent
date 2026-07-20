# Status

**Date:** 2026-07-20
**Branch:** `coop-agent/v159.7`
**Engine pin:** tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`, Arc `208a754044`

This file is kept truthful. It describes what actually exists, what is a stub,
and what is unverified.

## What exists and works

- **Repository scaffold**: top-level `AGENTS.md`, `CLAUDE.md`, `NOTICE.md`,
  `ENGINE_VERSION`, `Makefile`, `.gitignore` additions.
- **Docs**: `ARCHITECTURE.md`, `ROADMAP.md`, `STATUS.md`, `HANDOFF.md`,
  `UPSTREAM_PATCHES.md`, `PROTOCOL.md`, `REWARD_AUDIT.md`, `SCENARIOS.md`,
  `BENCHMARKS.md`, and ADR-0001..0010 under `docs/decisions/`.
- **Python core package** (`python/src/mindustry_agents/`): imports with zero
  third-party dependencies. `protocol.py` implements length-prefixed JSON framing
  and all v1 message dataclasses; the M2 process/env layer (supervisor, env
  client, parallel-env facade, vector collector) is stdlib-only too. **26 Python
  tests pass** via `python -m pytest python/tests -q` (verified 2026-07-20 with
  pytest 8.4.2 on Python 3.12.5).
- **`scripts/bootstrap.sh`**: verifies and prints the toolchain; exits 0 on this
  machine (JDK 21 Temurin, Python 3.12.5, Git 2.46). Verified working in Git Bash.
- **`smoke` / `determinism` scripts**: implemented (M1) and passing — see the
  Milestone 1 section above.
- **M2 scripts** (`stress-reset`, `benchmark`): implemented and passing — see the
  Milestone 2 section below.
- **Still not-implemented scripts** (`scripted-demo`, `demo-server`): exit 1 with
  a pointer to `docs/ROADMAP.md`, by design. (`test-java` is implemented.)

## Milestone 1 — external-step spike (DONE, verified 2026-07-20)

The highest-risk vertical slice is implemented and passing end to end on this
machine (AMD Ryzen 7 9800X3D, JDK 21.0.11, Windows 11).

- **`rl-server`** (`mindustry.rl`): a real headless launcher.
  - `FixedStepApplication implements arc.Application` + `FixedStepGraphics extends
    MockGraphics` drive the stock `Logic` at a fixed `1/60 s` delta with no
    background loop thread and no wall-clock read (`state.tick` advances exactly
    `+1.0` per update).
  - Boots content once, mirroring `ServerLauncher.init()` minus `ServerControl`
    (no stdin thread, no timers, no `net.host()`); depends on `:core` only.
  - Length-prefixed JSON control server on `127.0.0.1:<port>` (default 47810):
    handshake / reset / step / health / close / error, byte-compatible with
    `python/src/mindustry_agents/protocol.py`. A socket reader thread only parses
    and enqueues; all game-state access is on the simulation thread (AGENTS.md §3).
  - Reset loads a tiny in-code 48×48 scenario (flat stone, copper patch, one
    Sharded core, no waves/enemies), reseeds `Mathf.rand`, resets
    `EntityGroup.lastId` (reflection), zeros `Time`, and stops both pathfinder
    threads (reflection) — repeated resets work with no JVM restart.
  - Step advances exactly N ticks, captures the M1 observation (tick, wave,
    copper/lead, unit/building counts, core health, done) and a canonical
    SHA-256 state hash, with `{engine_ms, observation_ms, ...}` timing.
- **Python harness**: `process/launcher.py` (context-managed JVM supervisor,
  tracks the spawned PID, graceful `CloseRequest` + terminate — never kill by
  name), `tools/smoke.py`, `tools/determinism.py`. `scripts/smoke.sh` and
  `scripts/determinism.sh` build the jar if missing and run them.
- **Verified**: `./gradlew rl-server:dist` green; `bash scripts/smoke.sh` →
  exit 0, tick advances exactly 600; `bash scripts/determinism.sh` → exit 0
  (two fresh JVMs identical hash-for-hash; two resets identical initial hash);
  5× repeated in-JVM resets identical; reset latency ~3.8 ms median (Gate 2
  target <250 ms); ~32,700 engine-only ticks/sec (~545× real-time). See
  `docs/BENCHMARKS.md`.
- **Honest caveat**: the M1 scenario has **no RNG-driven or time-driven state**
  (no enemies, no weather, static core), so identical seeds trivially match
  *and different seeds also produce the same hash*. The `Mathf.rand` reseed is
  wired and correct; the seed lever simply has nothing stochastic to influence
  until enemies/weather exist (M3+). Determinism of the stepping/clock/reset
  machinery is genuinely proven; seed-sensitivity of state is deferred.
- **No upstream engine files were modified.** Pathfinder synchronization was
  achieved by stopping the threads via reflection (they idle with no flowfields
  in M1), avoiding the sanctioned-but-optional upstream patch.

## Milestone 2 — persistent process pool + env facade (DONE, verified 2026-07-20)

All M2 exit criteria met on this machine; no Java changes were needed.

- **Process supervisor** (`process/supervisor.py`): `ProcessSupervisor` manages a
  pool of ≤4 persistent JVMs (cap is deliberate — shared host). Unique port per
  child (probe upward from a base, EADDRINUSE handled by retrying the next port),
  explicit per-child seed + stderr log file under `runs/` (gitignored, last-N
  lines retrievable), handshake verification (`engine_commit` must equal the
  `ENGINE_VERSION` pin), startup-failure detection (no READY / bad commit →
  loud failure with stderr tail), reset/step socket timeouts, and **crash/hang
  detection with automatic replacement**: a dead or unresponsive child has its
  episode marked truncated, is terminated by the PID we spawned (never
  kill-by-name), and is transparently respawned + re-handshaked. Clean shutdown
  is wired to both `atexit` and the context-manager protocol; verified no
  orphaned JVMs after the full test run.
- **Env facade** (`env/`): `client.EnvClient` — synchronous, framework-neutral,
  per-connection episode/tick bookkeeping, returns Gym/PettingZoo-flavoured
  tuples. `parallel_env.MindustryParallelEnv` — the PettingZoo `ParallelEnv`
  method surface (possible_agents/agents/reset/step/close + space stubs)
  **without importing pettingzoo** (duck-typed; a trivial adapter is documented
  in the module for when the `[rl]` extra is installed). `vector.VectorCollector`
  — steps M worlds in lockstep, one thread per child, aggregates ticks/sec.
- **Honesty caveat (M1 engine, unchanged):** observations are still
  **world-level**; there are no per-agent entities yet (M3). `possible_agents =
  ["agent_0","agent_1"]` but every agent currently receives the *same* world
  observation and actions are accepted-but-**no-op** bundles. The per-agent dict
  plumbing (in/out, bundled into one `StepRequest`) is fully wired, so M3 changes
  only the payload contents, not the API shape. Nothing fakes per-agent state.
- **Tools**: `tools/stress_reset.py` (1000 in-JVM resets, same seed — all initial
  hashes identical, reset latency distribution, RSS leak check via psutil-or-
  `tasklist` fallback, `-Xmx` bounded so the working set is observable) and
  `tools/benchmark.py` (single-env engine ticks/sec + reset latency, protocol
  overhead, 1/2/4-JVM scaling; markdown report). Wired to `scripts/stress-reset.sh`
  and `scripts/benchmark.sh`.
- **Verified**: `python -m pytest python/tests -q` → 26 pass;
  `bash scripts/stress-reset.sh` → exit 0 (1000 resets, 0 hash mismatches, no
  leak); `bash scripts/benchmark.sh` → exit 0 (engine ~76k ticks/sec, reset
  median ~2 ms, scaling 1/2/4 JVMs); `bash scripts/smoke.sh` → exit 0 (no
  regression). Numbers in `docs/BENCHMARKS.md` (M2 measurements).
- **Memory note**: an uncapped JVM's RSS climbs for a few hundred resets then
  plateaus — this is lazy heap expansion toward the default max (~25% of RAM),
  **not** a leak. Even under a cap, *when* RSS plateaus varies run to run
  (observed +0.2% and +24% post-warmup growth for identical workloads), so a
  growth-trend leak check is flaky. The stress tool therefore caps the heap
  (`-Xmx350m` default) and fails only if peak RSS exceeds an absolute ceiling
  (`Xmx + 300 MiB` native/metaspace allowance); within-cap growth is reported
  as informational. A genuine native leak still fails the ceiling.

## What is stubbed (compiles/imports, no real behaviour)

- **`agent-core`**: real, compilable, unit-tested types — `TaskType` (16),
  `CoordinationAct` (13), `SkillStatus` (6), `AgentId` record — plus a JUnit
  test. No task board, skills, observations, or reward logic yet.
- **`agent-plugin`**: `mindustry.agentplugin.AgentPlugin` placeholder; not a
  loadable Mindustry plugin. See `agent-plugin/README.md`.
- **Python subpackages** `process`, `env`, and `tools` now carry real M1/M2 code
  (`process/{launcher,supervisor}.py`, `env/{client,parallel_env,vector}.py`,
  `tools/{smoke,determinism,stress_reset,benchmark}.py`). `policies`, `training`,
  `evaluation`, `telemetry`: still documented skeletons.
- **`scenarios/bootstrap-defense-v0/`**: spec stub only.
- **`configs/`**: example YAML stubs marked unused-yet.

## What is unverified

- **`rl-server` Java build/run is now verified** (`./gradlew rl-server:classes`
  and `:dist` green; jar boots headlessly and passes smoke + determinism).
  `agent-core` and `agent-plugin` builds are still unverified by this track.
- **Java unit tests** (`agent-core` `AgentCoreTypesTest`): written, not run.
- **No CI** configured yet.
- **No lockfile** for Python yet (pinned deps are trivial/none for the core).

## Known deviations from the brief

See the end of `HANDOFF.md`. In summary: `protocol/` is intentionally **not** a
Gradle module (JSON bootstrap lives in `docs/PROTOCOL.md` + `protocol.py`, per
ADR-0004); the Makefile carries the full brief §33 target surface, with unbuilt
targets failing loudly.
