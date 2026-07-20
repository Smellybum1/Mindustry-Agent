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
  client, parallel-env facade, vector collector) is stdlib-only too. **31 Python
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

## Milestone 3 — agent entities + first skills (DONE, verified 2026-07-20)

All M3 exit criteria met on this machine; **zero upstream engine edits**.

- **`agentcore.skill`** (agent-core): `Skill` contract returning `SkillResult`
  (status + machine-readable `SkillReason` + progress + next-retry), the FSMs
  `NavigateTo` / `MineResource` / `DeliverToCore` / `Wait`, and a thin engine-free
  `AgentBody` port. The FSMs import no mindustry — they are unit-tested against a
  fake body (**13 new JUnit tests; 77 total**), no content init needed.
- **`rl-server`**: `RlAgentRegistry` spawns `agent_count` `alpha` units per reset
  at deterministic index-ordered offsets and installs `SkillController` (extends
  `AIController`, implements `AgentBody`) which runs the active skill on the sim
  thread. Straight-line steering only (pathfinder threads stay stopped; no
  `CommandAI`). `ActionDecoder` turns `NAVIGATE/MINE/DELIVER_CORE/WAIT/CONTINUE`
  into skills with validated `action_results` (invalid ⇒ `accepted=false` + reason,
  never a crash). Per-agent observations `{agent_id, unit, skill, team}` (D6); the
  state hash gains unit cargo/velocity + registry + skill state (D7).
- **Protocol** (additive, still v1): `StepResponse.action_results`, `agent_actions`
  command objects — `docs/PROTOCOL.md`, `protocol.py` (+3 tests), Java side.
- **Honesty check**: the smoke's scripted phase mines copper with `agent_0`
  (target 20 → carried **21**, the extra from the 12-tick deferred mine transfer)
  and delivers it; the core copper delta equals **exactly** the delivered amount
  (100 → 121), read from real engine observations, with the full ledger printed.
  `agent_1` mining a non-ore tile reports `BLOCKED(INVALID_TARGET)`.
- **Determinism**: the determinism harness replays the same scripted trace — two
  fresh JVMs produce identical hashes at all **35** boundaries (reset + 10 plain +
  24 scripted), so the skill state machines are now covered. Reset purity holds
  (agent units respawned identically). Stress-reset (1000 in-JVM resets) stays
  green with the registry rebuild: 0 hash mismatches, no leak.
- **Verified**: `./gradlew agent-core:test` (77) + `rl-server:dist` green;
  `pytest python/tests -q` → 30 pass; `bash scripts/smoke.sh` → exit 0 (600-tick
  advance + balanced ledger); `bash scripts/determinism.sh` → exit 0;
  `bash scripts/stress-reset.sh` → exit 0.

## Scenario — full `bootstrap-defense-v0` world + deterministic waves (DONE, verified 2026-07-20)

The minimal M1 world is replaced by the full scenario, driven from
`scenarios/bootstrap-defense-v0/scenario.json` (bundled onto the classpath at
build time — the JSON is the single source of truth, nothing hardcoded).

- **World**: 48×48 flat stone; three ore patches (copper A `27..32,27..32`, copper
  B `28..31,18..21`, lead C `16..19,27..30`); one `coreShard` (sharded) at (24,24);
  one east enemy spawn (`Blocks.spawn` overlay) at (46,24); loadout **250 copper**.
- **Waves**: 3 / 4 / 5 daggers at ticks **2700 / 4500 / 6300**, from the east
  spawn, via the engine's **native** `WaveSpawner` — tick-exact under the fixed
  step (`state.wavetime` decrements by `Time.delta == 1.0`/tick; verified). Wave
  spawn spread is seeded from `root_seed`. `dropZoneRadius` shrunk to 24 u so the
  per-wave shockwave does not nuke the nearby core (`docs/SCENARIOS.md` impl notes).
- **Deterministic enemy pathing**: the flow-field `Pathfinder` thread stays stopped;
  the field is preloaded at world load and converged each tick on the sim thread via
  the new **`Pathfinder.syncUpdate()` upstream patch** (`docs/UPSTREAM_PATCHES.md`
  entry 2 — the one sanctioned engine edit, with a full determinism audit).
  `randomWaveAI = false` keeps the `hashCode()`-seeded RNG branch out of play.
  **M4.1 dynamic re-pathing is now verified:** when a tile change sets
  `needsRefresh`, the thread-less `syncUpdate()` path refreshes targets, marks flow
  fields dirty, and converges them immediately without consulting the normal
  `Time.millis()` throttle. Normal threaded play retains its original throttle.
- **Termination**: step response now carries honest `terminations`/`truncations`
  and an `outcome` field (`running`/`win`/`loss`/`truncated`): win = core alive at
  tick 8100, loss = core destroyed, truncate at the 9000-tick cap. Observations gain
  `time_to_next_wave`, `enemy_count`, and `enemy_nearest_core_dist`. State hash gains
  `state.wavetime` + `state.enemies`.
- **Seed lever is now real**: same seed → identical hashes across processes/resets;
  **different seeds diverge** once enemies spawn (spawn spread). Both asserted by
  `tools/determinism.py` (now steps past wave 1, places a copper wall in the lane,
  and follows the re-pathing enemies; the M4 trace also executes and supplies the
  ordered seven-block schematic; **79** hash boundaries) — this is the first
  genuine seed-sensitivity and dynamic-tile-change evidence.
- **Undefended loss**: `tools/scenario_check.py` (wired into `scripts/smoke.sh`)
  fast-forwards past wave 1, asserts daggers spawned (`enemy_count > 0`) and **move**
  toward the core (nearest-core distance strictly decreases), then runs on to the
  loss. Observed: core destroyed at tick **~3420–3450** (~12 s after wave 1),
  matching `docs/SCENARIOS.md` arithmetic (c) (travel + ~8.9 s contact kill), well
  under the cap.
- **Verified 2026-07-20**: `./gradlew rl-server:dist agent-core:test` green (91
  JUnit); `pytest python/tests -q` → 30 pass; `bash scripts/smoke.sh` → exit 0
  (mine/deliver ledger **and** scenario check); `bash scripts/determinism.sh` → exit
  0 (moving enemies + seed sensitivity); `bash scripts/stress-reset.sh` → exit 0
  (1000 resets, 0 mismatches, reset latency median **1.07 ms** / p95 2.11 ms /
  max 44.94 ms warmup — comfortably under the 250 ms gate even with the bigger world).

## Milestone 4 — build and defence skills (COMPLETE)

- **4.1 dynamic re-path determinism is done (verified 2026-07-20).** The minimal
  upstream amendment is catalogued in `docs/UPSTREAM_PATCHES.md`. Validation:
  `./gradlew agent-core:test rl-server:dist` green; 30 pytest green; smoke and
  scenario loss path green; determinism green at all 73 boundaries across two
  fresh JVMs, including a wall placed after wave 1 and live enemy re-pathing.
- **4.2 BuildBlock is done (verified 2026-07-20).** The engine-free FSM extends
  `AgentBody`; `SkillController` bridges to the unit's real ordered `BuildPlan`
  queue and `ConstructBuild` progress/resource path. `BUILD` accepts only
  scenario-whitelisted blocks. Five new FSM tests bring the Java total to 82.
  Live smoke proves a Duo costs exactly 35 core copper; after legal builds leave
  34 copper, a final Duo consumes only that stock and reports
  `BLOCKED(RESOURCES_SHORT)` at zero. The M4.1 direct-placement test hook is gone;
  determinism now builds its wall legally for six copper.
- **M4.3 — ExecuteSchematic is complete.** `east_duo_v1` is an ordered,
  anchor-relative JSON block list loaded and validated by the scenario. The
  engine-free `ExecuteSchematic` FSM sequences legal `BuildBlock` skills,
  reports monotone aggregate progress, and propagates inner typed failures.
  Live smoke completes two Duos plus five walls for exactly 100 core copper;
  two fresh JVMs reproduce the expanded trace.
- **M4.4 — SupplyBuilding is complete.** The engine-free FSM uses the live
  adapter's range-checked `Call.takeItems` withdrawal and `Call.transferItemTo`
  deposit, reports actual delivered/target stock, and has typed `CORE_SHORT` and
  `CARGO_MISMATCH` outcomes. Live smoke supplies 15 copper to each schematic Duo:
  both reach 30 native ammo units, the core loses exactly 30 copper, and both
  cargo stacks end empty. The full build+supply+re-path trace matches 79 hashes.
- **M4.5 — RebuildRegion is complete.** It consumes `TeamData.plans` in stable
  newest-first queue order and preserves the native plan config when adding the
  unit `BuildPlan`; completed engine placement clears the ghost plan. Live smoke
  proves wave 1 destroys a six-copper spawn-tile wall at tick 2700 and rebuilding
  it clears the queue while charging exactly six copper again. `broken_block_count`
  is now visible; true healing of standing damage remains unavailable to alpha.
- **M4.6 — DefendRegion + EmergencyRetreat is complete.** Target selection is
  stable nearest-distance/lowest-unit-id ordering, while the engine retains all
  aim, range, and weapon-fire legality. RETREAT clears `unit.clearBuilding()`,
  clears weapon targets, preserves cargo, and returns to the core. Step-scoped
  `unit_damage` events attribute source agent/unit and report post-hit HP/shield;
  observations add `enemy_total_health`, `build_queue_depth`, and DEFEND target/
  duration telemetry. Live acceptance observed dagger aggregate HP 450 -> 443.
  Four new FSM tests bring the Java total to 95; the combat-bearing 79-boundary
  replay matches across fresh JVMs.
- **M4.7 — protocol/observation/hash closure is complete.** Unit observations
  now include queue depth plus the current ordered plan and progress; team
  observations include ID-sorted turret ammo summaries. The canonical hash adds
  ordered unit build plans, ordered per-team broken-block plans (including
  removal markers), and native turret `totalAmmo`. Live checks observe plan
  progress 0.000 -> 0.056 and supplied Duo summaries `[30, 30]`; Python protocol
  records/round-trip coverage bring pytest to 30.
- **M4.8 — live acceptance is complete.** The script-wired single-agent run
  legally mines/delivers 21 copper, builds `east_duo_v1` plus 23 wall
  reinforcements, supplies both Duos to 30 ammo, and issues DEFEND. Wave 1 clears
  at tick 3271 with the core untouched at 1100 HP and copper ledger ending at 3.
  A matched omission reset still loses at tick 3450. The extra walls are an
  empirical requirement on the flat open map; the short reference column alone
  was not claimed sufficient after this live test. The post-M4 1000-reset run
  reports zero hash mismatches, median 0.94 ms / p95 1.87 ms, and no leak.

## Milestone 5.1 — candidate task generator (DONE, verified 2026-07-20)

- **Engine-free catalog:** `agentcore.candidates` produces at most eight
  fixed-order `TaskSpec` candidates per agent and boundary: low-core copper
  harvest, absent reference schematic, ID-sorted under-ammo turret supply,
  broken-block rebuild in `defense_block`, near/active-wave defense, and final
  `WAIT`. Required capabilities and assignment range produce typed masks.
- **Engine adapter:** `Scenario` exposes typed objective IDs/thresholds and named
  targets from the checked-in JSON. `EngineCandidates` captures all mutable game
  facts on the sim thread, while `EngineFeatureSource` turns the immutable
  boundary into distance, deficit, resource-cost, and danger features for
  `HandTunedUtility`.
- **Protocol:** each agent observation adds bounded `task_candidates`; aligned
  booleans are exposed at `action_masks[].candidate_task`. Selection/claiming is
  intentionally not accepted until the M5.2 board adapter.
- **Acceptance:** five synthetic JUnit tests repeat canonical bytes 100 times and
  cover stable entity expansion, bounds, capability masks, range masks, and the
  safe-only fallback. Live smoke verifies candidate transitions around schematic
  build, turret supply, and wave defense.
- **Verification:** `agent-core:test rl-server:dist` is green at **100 JUnit**;
  pytest remains **30 passed**; full smoke and the **79-boundary** determinism
  replay pass. The post-M5.1 1000-reset check has zero hash mismatches, median
  **1.00 ms**, p95 **1.88 ms**, peak **300.0 MiB**, and no leak.

## Milestone 5.2 — board/engine/protocol adapter (DONE, verified 2026-07-20)

- **Episode board:** `CoordinationAdapter` owns and resets the `TaskBoard` on the
  simulation thread. Candidate selections are proposed, announced, claimed, and
  started; two-phase bundle handling preserves the board's deterministic
  same-tick bid/tie-break semantics before any skill is assigned.
- **Execution/lifecycle:** selected harvest tasks repeat legal 20-item
  mine/deliver/settle batches until core copper reaches the scenario threshold.
  Build, supply, rebuild, defend, and wait candidates map to the existing M3/M4
  skills. Progress/blockage/completion/abandonment and 300-tick heartbeats update
  board state during the fixed-step loop, including long externally chunked steps.
- **Protocol/hash:** additive v1 `task_action` supports selection, continue,
  offer/accept/decline help, abandon, request-help, and wait with typed rejection
  results. Steps publish structured drained `task_events[]`, a stable maximum-32
  `task_board[]`, and board-aware action masks. Non-empty board state is now part
  of the canonical hash; empty-board hashes remain byte-compatible with M4.
- **Acceptance:** `tools.coordination_check` uses three live agents to prove an
  invalid index rejection, contested build ownership, help actions, legal
  schematic completion at tick 250, disjoint turret supply to `[10, 10]`, and
  wait/abandon. A second fresh JVM produces a byte-identical hash/result/board/
  event/mask transcript through tick 280. Full smoke includes this check.
- **Verification:** **100 JUnit**, **31 pytest**, full smoke, and the legacy
  **79-boundary** determinism replay are green. The post-M5.2 1000-reset run has
  zero hash mismatches, median **1.00 ms**, p95 **1.97 ms**, peak **298.9 MiB**,
  and no leak.

## What is stubbed (compiles/imports, no real behaviour)

- **`agent-core`**: real, compilable, unit-tested types — `TaskType` (16),
  `CoordinationAct` (13), `SkillStatus` (6), `AgentId` record, the coordination
  board (M2), the **`agentcore.skill`** FSM layer (M3/M4), and the engine-free
  deterministic M5.1 candidate catalog. Board-to-skill wiring is live in M5.2;
  scripted policies (M5.3), real reservations (M5.4), and reward logic (M7) remain.
- **`agent-plugin`**: `mindustry.agentplugin.AgentPlugin` placeholder; not a
  loadable Mindustry plugin. See `agent-plugin/README.md`.
- **Python subpackages** `process`, `env`, and `tools` now carry real M1/M2 code
  (`process/{launcher,supervisor}.py`, `env/{client,parallel_env,vector}.py`,
  `tools/{smoke,determinism,stress_reset,benchmark}.py`). `policies`, `training`,
  `evaluation`, `telemetry`: still documented skeletons.
- **`scenarios/bootstrap-defense-v0/`**: **fully loaded** by `rl-server` (world,
  ore, waves, termination, objective IDs/targets/thresholds, named regions, and
  reference schematic). M5.1 turns those objectives plus live world state into
  scored candidates; M5.2 claims and executes them, while autonomous policy is
  M5.3/M6.
- **`configs/`**: example YAML stubs marked unused-yet.

## What is unverified

- **`rl-server` Java build/run is verified** (`./gradlew rl-server:dist` green;
  jar boots headlessly and passes smoke + determinism + stress-reset). **`agent-core`
  build + JUnit suite are now verified** (`./gradlew agent-core:test` → 100 tests
  green, including 31 M3/M4 skill tests). `agent-plugin` build still unverified.
- **No CI** configured yet.
- **No lockfile** for Python yet (pinned deps are trivial/none for the core).

## Known deviations from the brief

See the end of `HANDOFF.md`. In summary: `protocol/` is intentionally **not** a
Gradle module (JSON bootstrap lives in `docs/PROTOCOL.md` + `protocol.py`, per
ADR-0004); the Makefile carries the full brief §33 target surface, with unbuilt
targets failing loudly.
