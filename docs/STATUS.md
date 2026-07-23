# Status

**Date:** 2026-07-23
**Branch:** `coop-agent/v159.7`
**Engine pin:** tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`, Arc `208a754044`

This file is kept truthful. It describes what actually exists, what is a stub,
and what is unverified.

## What exists and works

- **Repository scaffold**: top-level `AGENTS.md`, `CLAUDE.md`, `NOTICE.md`,
  `ENGINE_VERSION`, `Makefile`, `.gitignore` additions.
- **Docs**: `ARCHITECTURE.md`, `ROADMAP.md`, `STATUS.md`, `HANDOFF.md`,
  `UPSTREAM_PATCHES.md`, `PROTOCOL.md`, `REWARD_AUDIT.md`, `SCENARIOS.md`,
  `BENCHMARKS.md` and ADR-0001..0012 under `docs/decisions/`.
- **Python core package** (`python/src/mindustry_agents/`): imports with zero
  third-party dependencies. `protocol.py` implements length-prefixed JSON framing
  and all v1 message dataclasses; the M2 process/env layer (supervisor, env
  client, parallel-env facade, vector collector) is stdlib-only too. The
  governed **33-test core boundary passes under `python -S`** with no third-party
  packages; the complete dev/RL suite passes all **287 tests** (verified
  2026-07-23).
- **`scripts/bootstrap.sh`**: verifies and prints the toolchain; exits 0 on this
  machine (JDK 21 Temurin, Python 3.12.5, Git 2.46). Verified working in Git Bash.
- **`smoke` / `determinism` scripts**: implemented (M1) and passing — see the
  Milestone 1 section above.
- **M2 scripts** (`stress-reset`, `benchmark`): implemented and passing — see the
  Milestone 2 section below.
- **M6/M7 entry points are implemented:** `scripted-demo` and
  `evaluate-scripted` now use the M7.3 public greedy candidate policy;
  `candidate-policy-check` isolates that seam. Frozen M6 golden replay through
  `determinism` and the real-server `demo-server` probe remain available.
  Human join mode remains deliberately opt-in (`DEMO_JOIN=1`) so no game port is
  grabbed silently.
  `evaluate-ladder` supplies the permanent M7.6 baseline/scorecard gate;
  held-out execution is explicit and remains unused.

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

## Milestone 5.3 — scripted multi-agent policies (DONE, verified 2026-07-20)

- **Policies:** the dependency-free Python package now exports greedy-utility
  and fixed-role baselines. Both continue active work, honor candidate masks,
  select deterministically by utility then stable candidate index, and fall
  back to `WAIT`. Fixed roles map agent indices to miner, builder, supplier, or
  defender task families. `HelperCoordinator` produces the explicit typed
  request/offer/accept/decline flow and selects the nearest idle agent with an
  agent-index distance tie-break.
- **Measurable helper fulfilment:** the sim-thread adapter associates an
  accepted `deliver copper` contract with a helper's legal `DELIVER_CORE`
  command. Only an observed copper cargo decrease meeting the contracted amount
  calls `reportHelpFulfilled`; reset clears the pending measurement state.
- **Acceptance:** `tools.policy_check` first proves simultaneous miner/builder
  intent, then spends the live core to 98 copper, blocks the builder on the
  100-copper schematic, records request/offer/accept, and has the nearest idle
  helper mine and deliver 21 copper against a 20-copper contract. The fulfilment
  event occurs at tick 901 and the single schematic completes at tick 912. A
  second fresh JVM produces a byte-identical full transcript. Full smoke runs
  this acceptance check.
- **Verification:** **100 JUnit**, **35 pytest**, full smoke, and the
  **79-boundary** determinism replay are green. The post-M5.3 1000-reset check
  reports zero hash mismatches, median **1.07 ms**, p95 **2.24 ms**, peak
  **300.3 MiB**, and no leak.

## Milestone 5.4 — live target/resource reservations (DONE, verified 2026-07-20)

- **Acquisition:** after all candidate claims in an atomic bundle are known,
  pending starts are sorted by utility descending, then agent index and task ID.
  Before a skill is assigned, schematic tasks reserve the exact bounding tile
  rectangle derived from live block sizes plus their estimated copper; turret
  supply tasks reserve estimated copper against the scenario's declared
  250-copper soft budget. Rejection reopens the task and returns a typed reason.
- **Lifecycle/telemetry:** completion, abandonment, release, expiry, and failed
  starts release reservations. Clearing an interrupted build assignment also
  cancels its engine build queue. Board snapshots expose reservation counts and
  per-item amounts; ordered tile/resource/region reservations are included in
  the canonical state hash. Engine-free registry views remain read-only and a
  new test covers their deterministic order and per-task counts.
- **Acceptance:** validation-only reset option `reservation_overlap_probe`
  exposes two distinct candidates for the same real schematic. In the live
  two-agent trace, agent 1's higher utility wins despite appearing second in the
  action bundle; agent 0 receives `reservation_overlap`, a structured conflict
  event names both agents, and only the winner gets an engine build plan.
  Abandonment clears two reservations and the queued plan; the released builder
  subsequently completes at tick 243. Both turret supply tasks then hold and
  release five-copper reservations. A second JVM repeats the transcript
  byte-identically through tick 280. Full smoke includes the check.
- **Verification:** **101 JUnit**, **35 pytest**, full smoke, and the
  **79-boundary** determinism replay are green. The post-M5.4 1000-reset check
  reports zero hash mismatches, median **1.20 ms**, p95 **3.80 ms**, peak
  **312.1 MiB**, and no leak.

## Milestone 5.5 — lease expiry and failure recovery (DONE, verified 2026-07-20)

- **Deterministic failure hook:** validation-only reset options name an agent and
  fixed failure tick. At that tick, on the simulation thread, the adapter clears
  its active skill, cancels any queued build plan, and suppresses subsequent
  progress/heartbeat/completion reports while deliberately retaining the board
  assignment. The hook resets completely between episodes and is disabled by
  default; no wall-clock or background thread participates.
- **Acceptance:** `tools.chaos_check` assigns the reference schematic to agent 0,
  sends it no further actions, and freezes it at tick 30 after measurable partial
  progress. Its last progress-renewed lease expires at tick 627, reopening the
  task and releasing both footprint/resource reservations. Agent 1 reclaims the
  same task, completes it at tick 893, and the otherwise unattended scenario
  reaches a normal loss outcome at tick 3600. Structured events preserve the
  `RUNNING → EXPIRED` transition and later claim/completion; the entire trace is
  byte-identical in a second JVM. Full smoke includes this check.
- **Verification:** **101 JUnit**, **35 pytest**, full smoke, and the
  **79-boundary** determinism replay are green. The post-M5.5 1000-reset check
  reports zero hash mismatches, median **1.15 ms**, p95 **2.46 ms**, peak
  **298.4 MiB**, and no leak.

## Milestone 5.6 — announcements and coordination metrics (DONE, verified 2026-07-20)

- **Structured-first announcements:** each `task_events[]` entry now carries an
  `announcement` rendered only from its structured `CoordinationEvent` fields.
  It is non-empty exactly when the deterministic board rate limiter sets
  `announce=true`; progress, heartbeats, and internal transitions remain silent.
- **Episode metrics:** every step reports cumulative duplicate-work incidents,
  completed/abandoned tasks, agent/idle ticks, idle fraction, and structured/
  announced message counts. Python copies the object into each step `info` and
  no metric contributes to reward or simulation state.
- **Acceptance:** `tools.announcement_check` isolates the live M5.3 helper run,
  verifies intent/progress/block/request/offer/accept/fulfil/complete ordering,
  same-tick accept suppression, silent routine traffic, and bounds of 112
  structured/four announced messages. It prints four coherent lines (intent,
  resources-short block, helper offer, completion); the complete event/metric
  transcript is byte-identical across two fresh JVMs.
- **Verification:** **101 JUnit**, **35 pytest**, full smoke, and the
  **79-boundary** determinism replay are green. The post-M5.6 1000-reset check
  reports zero hash mismatches, median **1.08 ms**, p95 **2.35 ms**, peak
  **300.1 MiB**, and no leak.

## Milestone 6.1 — scripted expert team (DONE, verified 2026-07-20)

- The live catalog now includes the scenario's `BUILD_LINE` objective, executed
  through the same `TaskBoard`, reservations, `ExecuteSchematic`, build plans,
  and structured announcements as the existing schematic task. Its data-backed
  `copper_line_v1` plan builds two drills and a real conveyor-to-core trunk.
- A three-agent fixed expert performs the complete economy/build/supply/defend/
  rebuild loop. The five-seed set 12345/23456/34567/45678/987666666 wins at the
  exact tick-8100 boundary with final core health 848/884/1001/920/983.
- The constrained variant legally spends the loadout before committing work,
  records one `resources_short` block, mines/delivers to recover, and wins with
  992 core health. No reset hook, free items, teleport, or state poke is used.
- `make scripted-demo` runs both transcripts noninteractively. **102 JUnit**,
  **36 pytest**, and the full legacy smoke suite are green after the change.

## Milestone 6.2 — evaluation summaries (DONE, verified 2026-07-20)

- `make evaluate-scripted` runs the fixed five-seed set in one persistent JVM,
  writes canonical JSONL to `runs/scripted-evaluation.jsonl`, and prints a
  Markdown table. Each row embeds the engine/Arc/protocol/scenario/policy/Python
  manifest plus outcome, milestone ticks, core damage, units lost, boundary
  copper totals, task counts, idle fraction, and structured/rendered messages.
- The verified aggregate is 5/5 wins, minimum/mean final core health 848/927.2,
  two agent losses, and 790/25 structured/rendered messages. Full numbers and
  the boundary-accounting caveat are recorded in `docs/BENCHMARKS.md`.
- The dependency-free summarizer/aggregator has unit coverage; pytest is now
  **36 passed**.

## Milestone 6.3 — checked-in deterministic replay (DONE, verified 2026-07-20)

- The expert runner records reset seeds, every external step/action bundle,
  every structured coordination event, outcome, and response hash. The pinned
  JSONL manifest includes engine/Arc/protocol/scenario/policy versions.
- `tests/golden/bootstrap-defense-v0-scripted-v1.jsonl` contains seeds 12345 and
  23456: two complete wins and **16,200 ticks**. M7.1 deliberately regenerated
  the behavior-adjacent trace from 678 to **672 checkpoints**. Fresh-JVM
  replay matches every hash and event; `make determinism` now runs this after
  the unchanged 79-boundary legacy replay.
- `--negative-check` changes the first MINE tile in memory and requires a
  mismatch. It passed; no mutated trace is written. Parser/mutation unit tests
  bring pytest to **38 passed**. Format and commands are in `docs/REPLAY.md`.

## Milestone 6.4 — real-time dedicated-server plugin (DONE, verified 2026-07-20)

- `agent-plugin:dist` builds `mindustry-coop-agents-plugin.jar` with a real
  `plugin.json`/`Plugin` entry point, shared `agentcore` classes, exact scenario
  resources, and no bundled upstream engine classes.
- The stock `server:dist` path creates Bootstrap Defense v0, spawns three
  controlled Alphas, and runs the scripted opening through the same `TaskBoard`,
  skill FSMs, live engine mapping, and `AnnouncementRenderer` used by training
  mode. It then constructs the initial 20-piece/four-Duo expert defense.
  Available agents continuously mine and deliver between waves, switch to
  defense on contact, then repair and add two Duos/seven walls after each of
  waves 1–2. All six/eight active turrets are supplied before mining resumes.
  If an Alpha is lost, its stable agent slot is visibly rebound to a replacement
  at the core.
  A demo-specific controller subclass adds immediate pause and emergency-stop
  semantics.
- Server and client commands cover `agents status|goal|cancel|assign|release|autonomy|quiet|pause|resume|stop`;
  human control is queued for simulation-thread application, while stop clears
  velocity, mining, build plans, firing, and active skills immediately. Team
  chat receives only rate-limiter-approved structured events, further filtered
  by quiet mode without suppressing urgent or structured records. Join
  mode pauses both agents and the scenario clock until the human's `/agents
  resume`, so client map loading cannot hide the opening or advance waves
  unattended.
- `make demo-server` is a non-networked isolated acceptance probe. Verified:
  plugin load, three spawns, both shared plans, 20 fortifications, four supplied
  Duos, exact per-plan block-order parity, reserve mining, and pause/resume/stop
  by approximately tick 1060. `DEMO_SURVIVAL=1 make demo-server` verified both
  nine-block expansions, six then eight supplied turrets, all three wave clears,
  and tick 8100 with **1091/1100** core health. Both automated paths open no
  port.
- A human joined locally with a stock v159.7 client as `Smellybum`, used
  `/agents resume`, saw mining/building/supplying and concise chat through all
  three waves, then typed `/agents stop`. The server log recorded all three
  active harvest tasks abandoned immediately. Human feedback produced both the
  continuous reserve-mining loop and the between-wave defensive expansions.

## Milestone 6.5 — closure validation (DONE, verified 2026-07-20)

The 2026-07-20 non-networked closure matrix is green: **102 JUnit**, **38
pytest**, full smoke, 79-boundary cross-process determinism, 678-checkpoint /
16,200-tick golden replay, both scripted expert variants, 5/5 evaluation wins,
the isolated plugin probe, and the three-wave real-time survival probe. The
1,000-reset run had zero hash mismatches, 1.15 ms median / 2.59 ms p95 latency,
298.7 MiB peak RSS, and no leak. The contention-sensitive benchmark reported
27,341 engine-only and 20,456 wrapper ticks/sec; 1/2/4-JVM aggregate throughput
was 13,613/21,076/21,671 ticks/sec. These are validation measurements, not a
replacement for the less-contended historical M2 baseline in `BENCHMARKS.md`.
The closure commit is tagged `milestone-6`.

The original brief §32 text is not checked into this repository; only the
roadmap's requirement to record items 1–15 is available. The honest
repository-evidence mapping used for the M6 audit is:

1. **PASS — scenario:** the checked-in Bootstrap Defense v0 data loads and its
   three waves/termination boundaries execute.
2. **PASS — cooperative bodies:** three controlled agents are present in both
   training and demo paths.
3. **PASS — fixed expert:** the scripted team wins at tick 8100.
4. **PASS — mining/delivery:** legal cargo and core ledgers are exercised.
5. **PASS — construction:** the copper line and defensive schematics use real
   build plans and exact resource costs.
6. **PASS — supply/maintenance:** the initial four Duos expand to six/eight
   supplied turrets and damaged defenses are rebuilt between waves.
7. **PASS — combat:** agents switch from reserve mining to defense on contact
   and the core survives wave 3.
8. **PASS — blocked replan:** the insufficient-copper variant reports
   `resources_short`, mines, replans, and wins.
9. **PASS — coordination:** the shared board, claims, helpers, leases, and
   reservations are exercised by deterministic checks.
10. **PASS — structured communication:** human text is rendered only from
    rate-limited structured events.
11. **PASS — evaluation:** the defined five-seed set is 5/5 wins with recorded
    per-episode metrics.
12. **PASS — replay:** the checked-in complete trace matches fresh-JVM training
    results and the negative mutation changes a hash.
13. **PASS — real server:** the stock dedicated server loads the plugin; a stock
    v159.7 client joined privately and observed/resumed the agents.
14. **PASS — manual emergency stop:** the human typed `/agents stop` after wave
    3; all three active harvest tasks were abandoned immediately.
15. **PASS — closure record/tag:** status, benchmarks, roadmap, handoff, and the
    takeover prompt are refreshed; the closure commit is tagged `milestone-6`.

## Milestone 7.1 — review-findings consolidation (DONE, verified 2026-07-20)

- Resolved independent-review findings 1/3/4/6/8/9/10/11/12. The expert and
  real-time plugin derive scenario-owned mining/turret/region coordinates and
  timing from one JSON-backed `Scenario` payload; probe counts come from the
  actual placement queues. Dead demo transitions are gone.
- Candidate overflow now retains highest deterministic utility while reserving
  a DEFEND slot. Reset transport IDs are wall-clock-free
  (`ep-<root_seed>-<reset_counter>`). Shared skill arrival/retry defaults,
  type-safe reservation yielding, and explicit supply-stock telemetry consumers
  close the remaining mechanical findings. `UPSTREAM_PATCHES.md` now matches the
  actual 48-line `Pathfinder.syncUpdate()` addition.
- Golden regeneration is isolated in commit `00421cf76`: both seeds remain wins
  at tick 8100, total ticks remain 16,200, replay matches all 672 checkpoints,
  and the negative MINE mutation diverges. Smoke confirms every resource ledger
  remains balanced.
- Closure validation: **103 JUnit**, **40 pytest**, full smoke, legacy
  79-boundary determinism, the 672-checkpoint golden, 1,000 resets with zero
  mismatches (1.31/2.60 ms median/p95, 298.3 MiB peak, no leak), scripted normal
  and blocked wins, and 5/5 evaluation wins (core health min/mean 749/840.8,
  two unit losses). The plugin probe and real-time three-wave survival probe are
  green; the latter reaches tick 8100 with 1100 core health.
- At the M7.1 checkpoint, findings 2/5/7 remained deliberately open for
  M7.2–M7.4; M7.2 resolves finding 5 below.

## Milestone 7.2 — one coordination brain (DONE, verified 2026-07-21)

- `agentcore.coordination.ExpertCoordinationDriver` is now the single scripted
  coordination policy for fixed-step validation and the real-time demo. It owns
  stage transitions, board/task lifecycle, opening economy and fortification,
  supply, wave response, repair/rebuild, post-wave expansion, and reserve
  mining. Immutable `ExpertCoordinationPlan` data is derived from the
  authoritative scenario by `ExpertCoordinationPlans`.
- `CoordinationAdapter` can enable that driver with the validation-only reset
  option `shared_expert_policy=true`; the normal externally supplied action
  path is unchanged. `DemoCoordinator` is reduced from 848 to 312 lines and now
  owns only pacing, engine/IO adaptation, agent rebinding, controls, chat, and
  telemetry.
- `make coordination-parity` proves decision-level parity twice: a recorded
  90-snapshot trace produces 366 decisions and 89 selections spanning harvest,
  schematic, line, supply, repair, and defend; the actual fixed-step and no-port
  plugin openings both produce 33 selections with normalized digest
  `f335f6b950ac1b58857ca84b40e7151f966d5d53408fd0e643fbc54a39671385`.
- The no-port demo survival acceptance remains green after extraction: both
  nine-block/two-turret expansions complete, waves clear at ticks
  3102/4865/6655, and tick 8100 is reached with **1091/1100** core health.
- Closure validation: **104 JUnit**, **40 pytest**, `agent-core:test`,
  `rl-server:dist`, `agent-plugin:dist`, full smoke, legacy 79-boundary replay,
  and the 672-checkpoint/16,200-tick golden replay are green. No reward component,
  engine pin, accepted ADR, or upstream file changed.
- Next: M7.3, make the utility layer the primary expert. REVIEW_M6 finding 5 is
  resolved; findings 2 and 7 remain assigned to M7.3/M7.4.

## Milestone 7.3 — the utility layer is the expert (DONE, verified 2026-07-21)

- The primary `run_episode` no longer calls the hand-authored `ExpertEpisode`
  macro or enables the validation-only shared driver. `UtilityExpertEpisode`
  applies dependency-free `GreedyUtilityPolicy` to live candidates and masks;
  every task enters through `SELECT_CANDIDATE_TASK`, deterministic board claim
  resolution, reservations, and the existing skill adapter. `ExpertEpisode` is
  retained as `run_frozen_episode` for the future ladder and golden replay.
- The scenario-derived shared plan now supplies a 22-block/six-turret opening
  fortification and two nine-block/two-turret expansions to both runtime modes.
  The public catalog gained planned schematics, deterministic recurring task
  identity, physical prerequisite gates, a 30-ammo turret reserve, accurate
  planned-target urgency/distance, and per-agent non-exclusive defense tasks.
- `BLOCKED(RESOURCES_SHORT|CORE_SHORT)` causes a structured
  `ABANDON(resources_short_replan)` followed by candidate regeneration and
  reselection; cumulative `resource_replans` is exposed in coordination
  metrics. A legal 18-wall pre-spend variant wins at tick 8100 with 209 core
  health and seven replans.
- The five pinned evaluation seeds all win at tick 8100 with final core health
  **1082 minimum / 1096.4 mean**. Static pre-wave milestones remain truthful and
  identical; native seeded spawn spread produces different wave-clear ticks,
  structured-message counts, unit losses, and final health. No random policy
  branch or cosmetic timing jitter was added.
- The enriched M7.2 parity gate remains green: 90 recorded snapshots, 356
  decisions/42 selections across all six task types, and 43 live opening
  selections with fixed-step/plugin digest
  `157134ba5a4e3f39ccc3cf237093481dc8474b7edd1d20e16b274ec338b1a6c2`.
  `docs/CANDIDATE_GAPS.md` records every fixed gap and the remaining M7.4 work.
- The stock-paced no-port survival probe reaches the six-turret opening at tick
  1814, completes the eight-/ten-turret expansions, clears waves at ticks
  3015/4799/6606, and finishes tick 8100 with **1100/1100** core health.
- Recurring and retry task IDs now encode current board state, intentionally
  changing coordination hashes without changing the frozen macro's outcome or
  length. The checked-in golden was regenerated separately: two wins, 16,200
  ticks, 672 checkpoints, exact fresh-JVM replay, and a passing negative MINE
  mutation check.
- REVIEW_M6 finding 2 is resolved. Finding 7 remains assigned to M7.4. No
  reward component, engine pin, accepted ADR, or upstream file changed.

## Milestone 7.4 — adaptive planning v1 (DONE, verified 2026-07-21)

- The public catalog now derives economy, wave, defense, ammo, and spatial
  urgency from authoritative scenario/engine state. Fixed 600-tick anticipation,
  magic priority bands, map-diagonal range, and the fixed ammo reserve are gone.
- `AdaptiveWorldFacts` verifies the actual line footprint and conveyor direction,
  then requires a grant/delivery-excluded 600-tick core inflow window at
  **0.6 copper/s**. Defense readiness uses loaded wave composition and native
  Duo damage/reload/inaccuracy/magazine values. Finding 7 is resolved.
- The additive `stop_on_decision_event` request option wakes on task terminal or
  block, economy readiness, wave spawn/clear, and core damage. Callers that omit
  it retain exact requested advancement. Adaptive rolling state and recent
  switching history are included in `state_hash`.
- Recoverable BLOCKED reasons abandon/regenerate/reselect with a bound of three
  replans per 180 ticks. The legal pressure fixture overcommits only after both
  reservations, emits real resource blocks, performs five structured replans,
  and wins at tick 8100 with 992 core health.
- `bootstrap-defense-adaptive-probe` starts with 70 copper and grants 450 at tick
  1100. Adaptive-v1 builds a working line at 1794, is defense-ready at 1382, and
  wins at 8100; the frozen macro cannot finish its opening by 2401 and loses.
  Across fixed+probe, adaptive mean idle fraction is **0.125 vs 0.878** and mean
  censored defense-ready tick is **817 vs 5251**.
- Closure validation: **108 JUnit**, **45 pytest**, Java/plugin compile, fixed
  5/5 evaluation, normal+blocked scripted wins, `make adaptive-planning-check`,
  and the full determinism gate. The regenerated trace retains two wins and
  16,200 ticks across **670 checkpoints**; exact replay and the negative action
  mutation check are green with adaptive rolling state included in the hash.
- All REVIEW_M6 findings are resolved. No reward component, engine pin, accepted
  ADR, upstream file, or `docs/ENGINE_NOTES.md` changed. Next: M7.5 and ADR-0012.

## Milestone 7.5 — scenario variation v1 + seed governance (DONE, verified 2026-07-21)

- `bootstrap-defense-v1` is scenario version 2. Stable named derivations from
  `root_seed` independently resolve bounded copper/lead patch jitter, a
  220–280 copper loadout, uniform wave timing jitter, per-wave Dagger count
  deltas, and an optional upper-east lane on wave 2 or 3.
- The loader rebuilds the immutable scenario on every reset, pins native wave
  groups to named spawn tiles, validates resolved geometry/timing/counts, emits
  the resolved contract in metadata, and includes it in `state_hash`. Nonzero
  requested scenario-version mismatches are rejected.
- ADR-0012 freezes pairwise-disjoint train/dev/held-out v1 seed sets. The dev
  harness refuses held-out input and records engine/Arc/protocol/scenario/
  seed-set/policy provenance.
- `make scenario-variation-check` exercises every axis, proves same-seed reset
  metadata plus idle-through-wave hashes across repeated resets and fresh JVMs,
  and runs the normal
  undefended scenario/pathing/loss check on v2. Adaptive-v1 wins **8/10 (80%)**
  on the frozen dev set; winning core health is 191–1100 (mean 854.8).
- Seeds 2005 and 2007 lose on the larger upper-lane wave 3. The fixed lower-east
  build anchor cannot express lane-specific fortification; this remains visible
  in `docs/CANDIDATE_GAPS.md` for M7.6 instead of rotating seeds.
- The stronger trace caught stale engine entity-allocation history: callbacks
  posted by the prior episode are cleared at reset, and each v2 native wave gets
  a disjoint deterministic entity-ID range before spawning. The same post-wave
  trace now hashes identically regardless of the preceding episode.
- No held-out episode was run. No reward, dependency, engine pin, upstream file,
  previously accepted ADR, or `docs/ENGINE_NOTES.md` changed.

## Milestone 7.6 â€” evaluation ladder + teammate scorecard (DONE, verified 2026-07-21)

- `make evaluate-ladder` evaluates versioned random-valid, pure greedy,
  three-seat role, frozen M6 (fixed only), and adaptive-v1 baselines over the
  frozen fixed/dev contracts. Each policy/seed-set cell starts a fresh JVM and
  keeps seed order fixed; every score follows the same same-seed idle trace used
  by M7.5.
- The certified Windows path uses one JVM at a time (within the four-JVM cap).
  Simultaneous JVM trials changed live policy traces under host contention, so
  the tool rejects that non-reproducible mode. Two certified executions emitted
  byte-identical 65-line episode JSONL; the full run took 39.6 seconds.
- Every episode contains the six scorecard metrics plus coverage counts. Help
  and recovery values are nullable when the relevant event was not observed;
  no value is imputed. Aggregates use 10,000 deterministic bootstrap resamples.
- Fixed/dev results are descriptive: adaptive-v1 is 5/5 fixed and 8/10 dev;
  pure greedy is 5/5 fixed and 9/10 dev. No intervals or dev outcomes authorize
  promotion. ADR-0012 now requires strict held-out win-rate CI separation.
- No held-out episode was run. No reward, dependency, engine pin, upstream
  file, or `docs/ENGINE_NOTES.md` changed. M8.1 then completed the design and
  reward exploit audit before any learned-policy code.

## Milestone 8.1 â€” learned-selector design + reward audit (DONE, verified 2026-07-21)

- `docs/M8_DESIGN.md` fixes the scope at one learned selector seat over the
  existing typed board protocol. It specifies the 10-way action/mask contract,
  `8×37` candidate tensor, 56 scalar/context features, forced lifecycle action
  handling, event-driven cadence, feed-forward model, manifest, matched
  ablation, and held-out promotion rules.
- `selector_reward_v1-draft` contains only milestone high-water, terminal,
  unresolved-tick, invalid-action, and abandonment-liability components.
  `docs/REWARD_AUDIT.md` gives each component three exploit hypotheses and
  concrete adversarial cases, plus an eight-case cross-component matrix.
- All reward rows remain `drafted-not-implemented`. No component influences an
  environment or policy, and no torch/model/trainer/lockfile, spatial grid,
  engine change, or held-out run was added. Next: M8.2 ADR-0011, exact RL
  dependency boundary, lockfile, and WSL2 bring-up/reverification.

## Milestone 8.2 — RL dependency boundary (DONE, verified 2026-07-21)

- ADR-0011 keeps core `dependencies = []` and confines NumPy, PettingZoo, and
  PyTorch imports to `mindustry_agents.training`. An AST regression rejects
  those imports anywhere else in the package.
- The `rl` extra pins NumPy 2.4.2, PettingZoo 1.26.1, and PyTorch 2.12.1.
  `python/requirements-rl-linux-py312.lock` pins all 15 Linux CPU packages and
  hashes; uv 0.11.16 regenerated it byte-identically at SHA-256
  `8d865c8c710a61d7e37b8896b38166a1dcf121e40d17fbb1a47e948b4861bf6c`.
- `make verify-rl-boundary` is the reproducible Linux/WSL2 gate. On Ubuntu
  24.04, kernel 6.6.114.1-microsoft-standard-WSL2, it ran 33 core tests under
  Python `-S`, constructed a temporary environment, and reported CPython
  3.12.3, NumPy 2.4.2, PettingZoo 1.26.1, and PyTorch 2.12.1+cpu with CUDA
  unavailable. No package was installed machine-globally.
- Windows remains the dev/demo reference. The full 54-test Python suite,
  smoke, 670-checkpoint/16,200-tick golden replay, and 65-episode evaluation
  ladder are green after the metadata change. No model, reward emission,
  collector optimization, engine/upstream change, or held-out run entered
  M8.2. Next: M8.3 throughput bring-up on WSL2.

## Milestone 8.3 — WSL2 training throughput (DONE, verified 2026-07-21)

- `EnvClient`, `ProcessSupervisor`, and `VectorCollector` now carry the opt-in
  decision-event stop flag end to end. Vector timing sums actual per-child
  advances, so early asynchronous boundaries cannot inflate throughput.
- The training-only `throughput` probe runs a frozen M8-shape CPU graph in
  shadow mode at reset and real decision events. Scripted adaptive actions
  remain authoritative; logits never affect an action and no reward exists.
- On the exact ADR-0011 lock and project-local Temurin 21.0.11+10, WSL2
  1/2/4-JVM cells delivered 122.4×/212.7×/293.5× aggregate real-time. All
  episodes won at tick 8100 and shared final hash
  `9f244b8741f7948220d57cc143796568bbf42d725c1e285ff628ca30cf9e0042`.
  The ≥50× four-JVM prerequisite passes by 5.87×.
- The same noninteractive gate completed 10,000 in-JVM resets: zero hash
  mismatches; median/p95 0.93/1.27 ms; 338.3 MiB peak RSS below the 650 MiB
  ceiling; exact child PID absent after close. Gate 5 is complete.
- `runs/m8-throughput.json` and `runs/m8-stress-reset.json` hold the current
  machine-readable evidence. They are intentionally gitignored run outputs;
  methodology and certified figures are recorded in `docs/BENCHMARKS.md`.
  Next: M8.4 feature adapter, audited reward implementation, PPO selector, and
  exact run/checkpoint manifests. Held-out remains sealed.

## Milestone 8.4 — one-seat PPO selector (DONE, verified 2026-07-21)

- `selector_features_v1` exposes the pinned 8x37 candidate table, 56 scalar
  context values, masks, forced-action attribution, and exact boundary history
  without importing torch outside `mindustry_agents.training`.
- `selector_reward_v1` implements all five audited components separately. The
  noninteractive gate passes 27 adversarial cases before training.
- The trainer runs one learned selector seat with two adaptive scripted seats,
  writes chained checkpoints, per-transition training JSONL, complete fresh
  replay JSONL, reward totals, scorecard, seeds/lock/runtime evidence, and exact
  path-independent manifests.
- Two independent pinned WSL2 runs selected update 3 with identical checkpoint
  SHA `0b2bd8ac904a9e21...`, complete replay digest `87ba273f376c47de...`,
  full-run reproducibility digest `56cc7b54bc9b01b5...`, and dev action/state
  aggregate `52aecddf4c96bab6...`.
- The selected checkpoint won **0/10 dev episodes**. M8.4 proves the learning
  and reproducibility path; it does not meet M8.5 quality/promotion criteria.
  Held-out has not been opened.
- Determinism hardening keeps async phases on the simulation thread, seeds
  physics, disables/joins pathfinder workers, canonicalizes building
  proximity/sleep ordering, enumerates authoritative tile-backed buildings,
  and removes headless placement RNG. All upstream edits are catalogued.
- Final gates: 92 Python tests; Java/JUnit plus plugin compile green; smoke
  green; 79-boundary cross-JVM determinism; 664-checkpoint/16,200-tick golden
  and negative mutation green; 65-episode fixed/dev ladder green; 27 reward
  adversaries; paired PPO reproducibility; 10,000 reset hashes with no drift,
  0.85/1.20 ms median/p95, 335.8 MiB peak, no leak/orphan; 4-JVM throughput
  375.1x real-time. Adaptive-v1 is 2/5 fixed and 9/10 dev in the current
  descriptive ladder; held-out remains sealed.

## Milestone 8.5 — one-way promotion result (NOT PROMOTED, 2026-07-21)

- PPO credit assignment now decays both gamma and GAE lambda by elapsed engine
  seconds, so terminal credit is invariant to extra decision-event boundaries.
  The trainer also records a deterministic repeated train-seed schedule and
  canonicalizes the catalog WAIT row to the single WAIT action.
- The final candidate is a governed 75/25 interpolation of aligned update-2
  parents: base PPO (8/10 dev, checkpoint `e9d83831b9cb5ca2...`, full-run digest
  `39b465f5ad910807...`) and auxiliary successful-trajectory imitation (6/10,
  `7aa12b17600cbe27...`, `bd6e52311a09adec...`). Two independent pinned runs
  reproduce each parent exactly.
- Two independent constructions produce identical derived checkpoint
  `4fdad5cbd8476a8f...`, model-state digest `266c4acc5504dcda...`, and lineage
  digest `995cb7d71fa21e4e...`. The constructor verifies parent configs, updates,
  manifests, initial state, commit/status, schemas, and architecture.
- The M8.5 preflight runner now evaluates the learned seat against refreshed
  permanent random-valid/greedy-utility aggregates and matched random/greedy
  seat-0 controls while keeping the same adaptive teammates and lifecycle. It
  archives decision traces and applies paired bootstrap scorecard checks.
- Frozen-commit dev preflight at `7494396ce2` is eligible: learned 9/10 beats
  permanent random-valid 3/10, permanent greedy-utility 8/10, matched random
  2/10, and matched greedy 1/10; reward adversaries and paired scorecards pass.
- The one-way runner created the exclusive attempt marker before first reading
  held-out membership, then archived 40 episodes and refused future attempts.
  Final held-out results are learned 4/10 (95% CI `[0.1,0.7]`), permanent
  random-valid 6/10 (`[0.3,0.9]`), permanent greedy-utility 6/10
  (`[0.3,0.9]`), and matched greedy 1/10 (`[0.0,0.3]`). There is no permanent
  comparator CI separation. Idle fraction and abandonment regress versus
  permanent greedy; recovery is uncertain. Status: **not promoted**.
- Final evidence is local under `runs/m8-promotion-held-out-final*`: records
  SHA `e8beeda83880cd4b...`, aggregate `c245c46227047600...`, report
  `02d05e925cecf964...`. The completed attempt marker permanently forbids a
  rerun. Individual held-out outcomes must not be used to revise behavior.
- ADR-0013 now governs any post-failure continuation. The sealed
  `bootstrap-defense-v1-held-out-v2` contract freezes 40 globally disjoint root
  seeds before another candidate is designed or trained. Development loaders
  refuse the split, its one future final attempt is exclusive, and M9 remains
  gated. The precommitted `m8-selector-v3-diverse` recipe isolates broader
  train-root coverage at the same 512-episode budget and names v2. Two pinned
  runs reproduced exactly but selected update 1 at 3/10 dev wins (checkpoint
  `174c71d6b44819d4...`, replay `9d156396fc6ee71a...`, full-run
  `e9e1ee37fbfef6ee...`). It is rejected before preflight; v2 remains unopened.
- `m8-selector-v4-teacher-regularized` is precommitted as the next train/dev
  hypothesis. It adds a 0.05 successful-episode adaptive-teacher auxiliary to
  the otherwise unchanged v3 recipe, with explicit loss/sample telemetry and a
  zero-default compatibility path. Two pinned runs reproduce exactly and select
  update 5 at 5/10 dev wins (`da777520e27ee20c...`, full-run
  `fc23c1ed82a546d3...`), so v4 stops before preflight.
- V5 is frozen as the final coefficient-only follow-up at 0.10. It changes no
  other recipe field, names held-out-v2, and must reach at least 9/10 dev wins
  or the teacher-regularization line ends. Two pinned runs reproduce exactly
  but select update 8 at 3/10 dev wins (`6e488b4d2f21f0f6...`, full-run
  `4d55b193cede563b...`), so the line is closed and v2 remains unopened.
- V6 is precommitted as an auxiliary-free data-budget test. It changes only v3
  training cycles from 8 to 32 (2,048 episodes/32 updates), restoring 32 visits
  per each of 64 train roots. Two pinned runs reproduce exactly and select
  update 31 at 9/10 dev wins: checkpoint `0dfdcf9b5273ae3f...`, replay
  `c3f6e5bb720ad95d...`, full-run `54476ef63e31e06d...`. This authorizes full
  dev preflight only; v2 remains unopened.
- `checkpoint_lineage.py` now governs direct selected checkpoints from two exact
  training replicas and shares validation with the legacy interpolation path.
  It rejects manifest, checkpoint, config, update, model-state, commit, or dirt
  mismatches before promotion evaluation.
- V6's full dev-v1 preflight beats permanent random/greedy and matched
  random/greedy by observed win rate, with reward/lineage/repository gates
  passing. It is still ineligible because idle, recovery, and abandonment
  scorecard intervals cross zero. ADR-0014 freezes a 40-root, globally disjoint
  dev-v2 one-way confirmation with an exclusive attempt. Its consumed attempt
  status is recorded below; held-out-v2 remains unopened.
- The exclusive dev-v2 attempt was created on commit `888095a664` and aborted
  before result artifacts on a matched-control catalog-WAIT indexing bug. Its
  `status: started` marker consumes dev-v2 under ADR-0014, so V6 is rejected and
  the attempt will not be rerun. The control path now canonicalizes WAIT before
  indexing and rejects genuine out-of-range SELECT actions explicitly.
  Held-out-v2 remains unopened.
- ADR-0015 freezes V7 before construction as a 90/10 V6-update-31 / V4-update-5
  interpolation. Cross-commit parent lineage now requires each full training
  commit. A new disjoint 40-root dev-v3 set is frozen for one confirmation only
  after dev-v1 qualification. Its result is recorded below; v2 remains sealed.
- V7 constructions match checkpoint `40478db69dd700b7...` and lineage
  `955960199cb90b18...`. Its exclusive dev-v3 confirmation completes at 35/40
  wins versus permanent greedy 30/40. All scorecards except idle pass; idle is
  favorable on average but uncertain, so V7 is rejected and dev-v3 consumed.
- ADR-0016 freezes V8 as exactly one `-0.25` WAIT-logit bias adjustment to V7.
  Masks remain authoritative and no reward or lifecycle behavior changes. A
  new disjoint 40-root dev-v4 set is frozen for one confirmation after dev-v1.
  Its construction and final result are recorded below.
- V8 constructions match checkpoint `1f3c4525fb5fd10d...` and lineage
  `8bc6ee1a9719e78d...`. Dev-v4 is fully eligible at 37/40 wins with every
  paired scorecard passing. The exclusive held-out-v2 final completes once:
  V8 36/40, permanent random 19/40, permanent greedy 23/40, matched greedy
  5/40. Win-rate CI gates pass, but permanent-greedy idle and abandonment
  regress, announcements/recovery are uncertain, and matched-greedy idle is
  uncertain. Status: **not promoted**. Held-out-v2 is consumed.
- Final v2 artifacts: records SHA `c291e704b2a93a65...`, aggregate
  `fd2acc01813ea147...`, report `71e83f38562ec889...`. Individual outcomes and
  traces must not inform policy revision.
- ADR-0017 freezes an 80-root, globally disjoint held-out-v3 contract before
  further model work. Development loaders refuse it and it permits one future
  exclusive final after a newly governed candidate/confirmation path.
- ADR-0018 freezes V9 before construction as one additional `-0.25` WAIT-bias
  child of V8 (`-0.50` total from V7). All other tensors and behavior remain
  fixed, and its config names held-out-v3. A globally disjoint 80-root dev-v5
  set is frozen for one confirmation after dev-v1.
- V9 constructions match checkpoint `3ae49108c913b078...`, model state
  `a62210ed1716cba6...`, and lineage `c329bfc096122a13...`. V9 beats every
  dev-v1 win comparator and completes exclusive dev-v5 at 65/80 wins. The
  then-implemented matched-only development scorecard passes.
- Held-out-v3 completes once: V9 70/80 (95% CI `[0.8,0.9375]`), permanent
  random 33/80 (`[0.3,0.525]`), permanent greedy 49/80 (`[0.5,0.7125]`), and
  matched greedy 5/80. Win gates pass, but permanent-greedy announcements,
  idle, and abandonment regress; permanent recovery and matched idle are
  uncertain. V9 is **not promoted**, held-out-v3 is consumed, and its
  individual outcomes/traces remain quarantined.
- Final v3 records, aggregate, and report SHA-256 values are
  `20d77ea9dc980570...`, `4f3ad4372798656e...`, and `eff86e5d718addc96...`.
- ADR-0019 fixes development/final parity. Preflight now loads exact seed-level
  permanent records, requires scorecards against both permanent and matched
  greedy, hashes the permanent record source, and has the final revalidate it.
  Held-out-v4 is frozen before future model work as 160 globally disjoint roots
  refused by development tools and available for at most one exclusive final.
- ADR-0020 precommits V10 as V6's 64-root/32-cycle PPO recipe plus coefficient
  `1.0` adaptive-teacher cross-entropy on every unforced transition. Reusable
  dev-v5 evidence found only 5.3% V9/teacher agreement; adaptive-v1 sharply
  reduced idle/abandonment, whereas role assignment lost win capacity and
  increased duplicates. Reward and inference behavior remain unchanged. The
  config names held-out-v4 and a disjoint 160-root dev-v6 one-way confirmation
  is frozen for the corrected dual-scorecard gate.
- Two pinned V10 runs reproduce exactly and select update 6 at only 1/10
  dev-v1 wins: checkpoint `a20f44d6ec093076...`, model state
  `5d5cd3bd8395855f...`, replay `045854f0a9e58712...`, and full-run digest
  `787b5d4bd6548eea...`. Mean dev idle is about 0.361. V10 is rejected before
  dev-v6; dev-v6 and held-out-v4 remain unopened.
- ADR-0021 precommits V11 as a fixed 90/10 V6-update-31/V10-update-6 blend,
  using V7's established weight. Its config names held-out-v4 and requires at
  least 9/10 dev-v1 wins. Dev-v6 is retired unopened; a globally disjoint
  160-root dev-v7 set is frozen for one corrected dual-scorecard confirmation.
  V11 constructions match checkpoint `0a8fa8b4ba98581d...`, model state
  `eefe623958d9456d...`, and lineage `845282326c58308c...`. Dev-v1 is 9/10 and
  beats all win comparators. Permanent idle/abandonment regress while matched
  idle/abandonment are favorable but uncertain. V11 qualifies for dev-v7 only;
  held-out-v4 remains sealed.
- Exclusive dev-v7 completes once at V11 137/160, permanent random 69/160,
  permanent greedy 100/160, matched random 19/160, and matched greedy 12/160.
  All win and matched-greedy scorecard gates pass. Permanent duplicates pass,
  but announcements, idle, recovery, and abandonment fail. V11 is rejected;
  dev-v7 is consumed and held-out-v4 remains sealed. Records/aggregate/report
  hashes are `ebc2362db79af180...`, `a605ec43468f9f89...`, and
  `bdf411b0fb386e7c...`.
- ADR-0022 precommits V12 under `selector_reward_v2`: v1 plus bounded penalties
  for idle ticks, duplicate work, announcements, and non-forced team
  abandonment. Production delta accounting, caps, rollback failures, rollout
  telemetry, and schema plumbing are implemented. All 37 reward adversaries
  and the 121-test Python suite pass, so the reward gate authorizes training.
  V12 otherwise uses V6's long recipe, names held-out-v4, and must reach 9/10
  dev-v1 with idle below 0.25. Two exact 2,048-episode runs reproduce at update
  28 with 10/10 dev wins, but mean idle is 0.26628148, so V12 is rejected before
  confirmation. Checkpoint/model-state/replay/full-run hashes are
  `a10752ccf12b513c...`, `64846932b7e2d948...`, `6f99df0a3243de3f...`,
  and `6d8912cbc00766c6...`. Dev-v8 remains unopened and held-out-v4 remains
  sealed.
- ADR-0023 precommits V13 as an exact V12 rerun with a quality-gated checkpoint
  selector. Each dev checkpoint must record mean idle; eligibility requires at
  least 9/10 wins and idle strictly below 0.25 before the existing
  wins/return/core-health/earlier-update ranking applies. The permitted dev-v1
  frontier motivates the rule, but V12 remains rejected and its update 24 is
  not relabeled. Dev-v8 is retired unopened; dev-v9 freezes 160 globally
  disjoint roots `91001..91160`. The strict selector, per-checkpoint idle
  evidence, manifest compatibility, and failure path are implemented. Two
  exact 2,048-episode runs reproduce and select eligible update 24 at 10/10
  dev-v1 wins and mean idle 0.24980951. Checkpoint/model-state/replay/full-run
  hashes are `ff5c21bc6644d903...`, `6695f8ffb690f635...`,
  `c556d3ec24f06c8a...`, and `842ac034e91e84ae...`; lineage is
  `8aff4629be3090b3...`. V13 is authorized for dev-v9 only.
- Exclusive dev-v9 completes once: V13 152/160, permanent random 62/160,
  permanent greedy 92/160, matched random 13/160, and matched greedy 15/160.
  Every win gate and matched-greedy scorecard passes. Versus permanent greedy,
  duplicates pass, while announcements, idle, recovery, and abandonment fail.
  V13 is rejected, dev-v9 is consumed, and held-out-v4 remains sealed.
  Records/aggregate/report hashes are `b4caeaba900f047a...`,
  `46f940a8361b4dad...`, and `a4dd2ecad7c485de...`.
- Reusable dev-v1 analysis, never dev-v9 episode inspection, attributes all 23
  non-forced V13 abandons to learned seat 0's `resources_short_replan`. Of
  those, 21 are `SUPPLY_TURRET` selections with authoritative resource cost
  1.0; successful supplies average 0.144 resource cost. Behavior-neutral
  selected-candidate diagnostics now record the bounded evidence needed to
  audit a successor without entering the action/state replay digest.
- ADR-0024 precommits scorecard v2 after reusable dev-v1 evidence proves that
  v1 counts forced wave/lifecycle preemption as policy abandonment despite
  reward v2's accepted exclusions. Future records will separate forced from
  non-forced abandonment and expose per-agent idle ticks. Consumed records and
  V13's rejection remain immutable. Schema v2, shared reason semantics,
  simulation-thread counters, protocol docs, and live reconciliation checks are
  implemented; 128 Python tests, build, smoke, and determinism pass.
- The same reusable V13 dev-v1 traces exposed a fixed-step scheduling defect:
  30 learned-seat `ABANDON` decisions advanced 23,371 ticks because the server
  captured the decision revision after applying the action bundle. Successful
  abandonment now marks `task_terminal`, the step captures the pre-action
  revision, and stop-on-event returns after exactly one fixed engine tick. The
  live reservation check asserts that boundary. The regenerated 664-checkpoint
  golden is semantically identical to the prior two-win/16,200-tick trace apart
  from the corrected decision-revision state hashes; two independent recordings
  match at SHA-256 `f386e056e3b21cbf...`. The 128-test suite, build, smoke,
  determinism, and deliberate replay-mutation check pass.
- Replaying rejected V13 update 24 on reusable dev-v1 under the corrected
  boundary remains 10/10 wins and improves mean team idle from 0.24980951 to
  0.20217810. All 110 learned-seat abandon decisions advance one tick, but
  immediate replanning exposes 105 non-forced `resources_short_replan` events;
  permanent/matched dual scorecards remain ineligible. Records, aggregate, and
  preflight hashes are `373d47db23646daa...`, `c03ce068da2a1203...`, and
  `5b161a1baee74d5e...`. V13 remains rejected.
- ADR-0025 precommits V14 as a from-scratch retrain of V13's otherwise exact
  reward/optimizer/architecture/RNG/root/schedule/selection recipe under the
  corrected one-tick abandonment boundary. Two exact 2,048-episode replicas
  are required. A 9/10, idle `<0.25` reusable dev-v1 result must then pass both
  permanent and matched greedy scorecards before one exclusive dev-v10
  confirmation. Dev-v10 freezes 160 disjoint roots `101001..101160`; held-out-v4
  remains sealed. The precommit governance test brings the Python suite to 129
  passing tests.
- Two pinned V14 2,048-episode replicas reproduce exactly and select update 32
  at 10/10 dev-v1 wins, mean idle 0.15861366, and mean core health 1034.3.
  Checkpoint/model-state/replay/full-run/lineage hashes are
  `d403044cc5adec74...`, `d2d60661ad2a5b90...`, `c6647a44b09ce7eb...`,
  `ecd8776cda1430d5...`, and `52f6138246423c54...`. Fresh scorecard-v2
  permanent baselines and the corrected reusable dev-v1 dual preflight then
  reject V14: versus permanent greedy, idle difference is +0.11430187 (95% CI
  +0.08198337..+0.14898070) and non-forced abandonment difference is
  +0.04469033 (+0.01168093..+0.09201991); recovery is uncertain. Baseline,
  candidate, aggregate, and preflight artifacts are hashed. Dev-v10 remains
  unopened, held-out-v4 remains sealed, and M8.5 remains unmet.
- Permitted V14 dev-v1 analysis attributes 34,993 of 81,000 engine ticks to
  only 59 learned `WAIT` choices; update 32 is already the lowest-idle 10/10
  frontier point. ADR-0026 therefore precommits V15 with V14 held fixed except
  for reward-v2 idle cost `0.0001 -> 0.0003` and non-forced team-abandon cost
  `0.1 -> 0.25` (the `2.0` abandonment cap is unchanged). The adversary runner
  now loads and hashes the exact candidate config. All 37 V15-config cases and
  the 131-test Python suite pass. Dev-v10 is retired unopened; dev-v11 freezes
  160 disjoint roots `111001..111160`. Held-out-v4 remains sealed.
- Two pinned V15 2,048-episode replicas reproduce exactly and select update 25
  at 10/10 dev-v1 wins, mean idle 0.21873675, and mean core health 1088.3.
  Checkpoint/model-state/replay/full-run/lineage hashes are
  `a328550d36448897...`, `823336f58798a487...`, `32735e17026b8903...`,
  `22792939f896fbd0...`, and `0db57e0879cca7df...`. The reusable dual
  preflight rejects V15 before dev-v11. Non-forced abandonment improves to
  0.01673964, but permanent-greedy idle is definitively worse by 0.17442496
  (95% CI +0.14772493..+0.20024502); recovery and matched idle are uncertain.
  Dev-v11 remains unopened, held-out-v4 remains sealed, and M8.5 remains unmet.
- V16's two pinned 2,048-episode replicas reproduce exactly and select update
  23 at 9/10 construction wins with mean idle 0.10050130. Checkpoint
  `6db48a03427edfa2...`, model state `91c3364b793d7091...`, replay
  `4862b1a8a319d8bf...`, full run `65bebd16464f95a1...`, and direct lineage
  `a172fad58f842f6e...` all reproduce. The stronger capped slope eliminates
  non-forced abandonment and improves matched-greedy idle by 0.12929577, but
  reusable dev-v1 rejects V16: permanent-greedy idle is still definitively
  worse by 0.05618951 (95% CI +0.03029619..+0.08042806), and recovery remains
  uncertain against both scorecards. Dev-v12 remains unopened, held-out-v4
  remains sealed, and M8.5 remains unmet.
- V17's two pinned 2,048-episode replicas reproduce exactly and select update
  17 at 9/10 construction wins with mean idle 0.08594077. Checkpoint
  `6dbde34e0b745b55...`, model state `701bff0e24bfae60...`, replay
  `ab01623eda4d40ea...`, full run `8b210937805c23f3...`, and direct lineage
  `233282b7fc536cb3...` all reproduce. Reusable dev-v1 still rejects V17:
  permanent-greedy idle is definitively worse by 0.04162898 (95% CI
  +0.01733907..+0.06734018), while announcements and recovery remain uncertain
  against permanent greedy and recovery remains uncertain against matched
  greedy. Non-forced abandonment remains zero and matched idle improves by
  0.14385630. Dev-v13 remains unopened, held-out-v4 remains sealed, and M8.5
  remains unmet.
- V17's idle and recovery gaps are empirically independent (paired-root
  correlation about -0.08), so ADR-0029 precommits V18 against all remaining
  blockers. V18 uses idle cost `0.004` capped at `5.0`, announcement cost
  `0.01` capped at `1.0`, and an optional backward-compatible recovery-delay
  penalty `0.001` per tick capped at `3.0`; duplicate cap rises to `4.0` solely
  to preserve the exact busywork ordering. Recovery mirrors the governed
  structured-event definition and charges unrecovered roles, so neither loss
  nor non-recovery can farm reward. All 43 exact-config adversaries and 138
  Python tests pass. Dev-v13 is retired unopened; dev-v14 freezes 160 disjoint
  roots `141001..141160`. Held-out-v4 remains sealed.
- V18's two pinned 2,048-episode replicas reproduce exactly and select update
  22 at 9/10 construction wins with mean idle 0.10978972. Checkpoint
  `0984700a681bfdc5...`, model state `2fd25b37851c1d97...`, replay
  `d098fba29b3de64f...`, full run `127410b515f6917e...`, and direct lineage
  `b226742761e58852...` all reproduce. Reusable dev-v1 still rejects V18:
  permanent-greedy idle is definitively worse by 0.06547793 (95% CI
  +0.03188818..+0.09708444), while recovery remains uncertain against both
  permanent greedy (-6.85 ticks, 95% CI -93.62..+114.80) and matched greedy
  (-42.52 ticks, 95% CI -214.79..+118.93). Announcements, duplicate work, and
  abandonment non-regress; matched idle improves by 0.12000735. Dev-v14
  remains unopened, held-out-v4 remains sealed, and M8.5 remains unmet.
- ADR-0030 precommits V19 after reusable per-agent diagnostics identify reward
  saturation as the causal gap: V18 reaches its idle cap in 8/10 dev episodes,
  and excess idle is dominated by downstream seat 1 (`0.174262` versus
  permanent greedy `0.031523`), not explicit learned-seat WAIT. V19 restores
  idle cost `0.002`, raises its cap to `8.0` (4,000 differentiating idle-agent
  ticks), and raises duplicate cap to `7.0` so duplicate plus abandonment churn
  remains worse at the full horizon. All other V18 fields remain exact. The new
  full-horizon adversary and all 44 exact cases pass, as do 140 Python tests,
  smoke, and determinism. Dev-v14 is retired unopened; dev-v15 freezes disjoint
  roots `151001..151160`. Held-out-v4 remains sealed.
- V19's two pinned 2,048-episode replicas reproduce exactly and select update
  24 at 9/10 construction wins with mean idle 0.09911830. Checkpoint
  `1a9376a331b3aadc...`, model state `510e07d964c84de0...`, replay
  `75bf5fb9cc34d5a6...`, full run `4d15c3a728f33d4c...`, and direct lineage
  `121a7400b241ce77...` all reproduce. The extended cap reduces selected-dev
  saturation from V18's 8/10 episodes to 2/10 and improves the reusable
  permanent-idle gap from 0.06547793 to 0.05480651, but the latter remains
  definitively worse (95% CI +0.02786525..+0.08510262). Recovery remains
  uncertain against both scorecards and non-forced abandonment regresses
  slightly by 0.00131579. Dev-v15 remains unopened, held-out-v4 remains sealed,
  and M8.5 remains unmet.
- ADR-0031 closes the idle-cap line and precommits V20 from reusable evidence.
  The all-adaptive teacher wins 9/10 with permanent-idle gap 0.01737902 and zero
  abandonment difference, while V19 disagrees with it on 529/607 unforced
  decisions. V20 keeps V19 exact except a low full-boundary teacher coefficient
  `0.05`; unlike V10's failed `1.0`, this is bounded at the V4-proven scale.
  Behavior-neutral teacher candidate diagnostics are archived without entering
  action/state digests. All 44 exact adversaries, 141 Python tests, smoke, and
  determinism pass. Dev-v15 is retired unopened; dev-v16 freezes disjoint roots
  `161001..161160`. Held-out-v4 remains sealed.
- V20's two pinned 2,048-episode replicas reproduce exactly and select update
  32 at 9/10 construction wins with mean idle 0.09850656. Checkpoint
  `6209f46876db0778...`, model state `1ba534267c67ff54...`, replay
  `a1bc0eec0c7f0002...`, full run `a407aa303e839844...`, and direct lineage
  `564f7fdca22f0ba9...` all reproduce. Teacher disagreements fall from V19's
  529/607 to 170/362 unforced decisions and abandonment returns to zero, but
  permanent idle is essentially unchanged at +0.05419477 (95% CI
  +0.02812093..+0.08298135). Permanent announcements/duplicates and both
  recovery comparisons are uncertain. Dev-v16 remains unopened, held-out-v4
  remains sealed, and M8.5 remains unmet.
- Reconstructing assignment occupancy exactly from V20's reusable structured
  `START_TASK`/terminal events exposed a runtime boundary defect rather than a
  reward gap: successful `WAIT` elapsed into `RELEASE`, cleared the assignment,
  but did not increment the decision revision. Individual gaps reached 2,086
  idle ticks while stop-on-event waited for an unrelated boundary. Successful
  automatic wait release now marks assignment `task_terminal`; the board task
  remains correctly `OPEN`. The live check proves the deterministic 60-tick
  wait lifecycle returns on its release tick (61 advanced engine ticks including
  initialization) and matches byte-for-byte across fresh JVMs. The pinned build,
  141 Python tests, smoke, determinism, and unchanged 664-checkpoint golden pass.
  Existing checkpoints were trained on the old decision sequence, so M8.5 still
  requires a governed from-scratch successor.
- ADR-0032 precommits V21 as an exact V20 retrain under runtime contract
  `successful_abandon_one_tick_wait_release_same_tick_v2`. Keeping V20's
  teacher coefficient `0.05` fixed isolates the runtime correction and closes,
  rather than reopens, teacher tuning. Dev-v16 is retired unopened; dev-v17
  freezes globally disjoint roots `171001..171160` for one confirmation only
  after reusable construction and both scorecards pass. Held-out-v4 remains
  sealed. All 44 exact reward adversaries, 142 Python tests, pinned build,
  smoke, and determinism pass. Config and adversary report SHA-256 are
  `5567e1c1d79cae0...` and `732536ffcd358d25...`.
- V21's two pinned 2,048-episode replicas reproduce exactly and select update 29
  at 9/10 construction wins with mean idle 0.04383598. Checkpoint/model/replay/
  full-run/lineage hashes are `68c3dfba722e0b75...`, `5c09bf859571ac2c...`,
  `81ca21dfe5d634b4...`, `5d5831a59032c57e...`, and
  `df5af947a70f6a8c...`. The corrected boundary removes the definitive
  permanent-idle regression (mean -0.00047581, CI crosses zero) and decisively
  improves matched idle/recovery, but reusable preflight still rejects V21.
  Task abandonment is definitively worse by 0.04347388 against both scorecards:
  six episodes repeat a resource-short supply target three times before a fourth
  selection succeeds, producing 18 avoidable non-forced replans. Announcements,
  duplicates, and permanent recovery remain uncertain. Dev-v17 is unopened,
  held-out-v4 is sealed, and M8.5 remains unmet.
- V21's reusable failure has now been corrected at its authoritative source.
  `CoordinationAdapter` retains each blocked skill's `nextRetryTick`, hashes it,
  masks only equivalent type/target work until due, and rejects a mask bypass as
  `retry_not_due`. The live fixture blocks agent 1's `BUILD_SCHEMATIC` at tick
  607, keeps alternative non-WAIT work legal, and reopens the same candidate at
  tick 667. The wider gate also exposed that dead fixed-step seats kept stale
  assignments alive: loss now emits `ABANDON(agent_death)`, releases
  reservations, wakes `task_terminal`, and restricts that seat to no-op WAIT.
  All five public greedy seeds win and expose 12 loss releases. Two independent
  golden recordings match at SHA-256 `f08c5af6b6ea4e25908da8b59e10ba7f4d10afdef7306529859ef726023dccd2`;
  all 664 state hashes change because retry eligibility joined canonical state,
  while every non-hash record remains identical. The negative replay still
  diverges. Previously trained checkpoints remain historical evidence; a V22
  precommit and from-scratch retrain are still required.
- ADR-0033 now precommits V22 as the exact V21 training packet under runtime
  contract `abandon_wait_retry_and_agent_death_boundaries_v3`. Candidate ID,
  runtime contract, and confirmation path are the only config differences;
  reward, teacher coefficient `0.05`, train/dev roots, model, optimizer, RNGs,
  schedule, and checkpoint selection stay frozen. Dev-v17 is retired unopened.
  Dev-v18 freezes 160 globally disjoint roots `181001..181160` and remains
  unopened; held-out-v4 remains sealed. All 44 exact reward adversaries, 143
  Python tests, pinned build, five-seed candidate policy, smoke, determinism,
  and negative replay pass. Config/adversary SHA-256 are
  `95bc200596718170...` and `18f337ac3ca54700...`. No V22 model work preceded
  this precommit.
- V22 replica A completed 2,048 episodes/32 updates and stopped at the
  precommitted dev quality gate; replica B was not started. Frontier idle means
  were `0.43868123..0.54747927`; update 17 reached 10/10 wins but reported
  `0.48320387` idle. The reconstructed rejection frontier hashes to
  `17d8afa6e7fb2f33...`. Agent-death cleanup had exposed that permanently dead
  seats still accumulated available and idle ticks, contaminating both the gate
  and training reward. Metrics now partition seat-ticks into available or
  unavailable and charge idle only while a seat can act. Diagnostic update-17
  evaluation becomes 10/10 at `0.13474577` idle, but cannot rehabilitate a model
  trained under the faulty reward. V22 is rejected, dev-v18 is retired unopened,
  held-out-v4 remains sealed, and a newly precommitted retrain is required.
- ADR-0034 precommits V23 as an exact V22 retrain under corrected runtime
  contract `abandon_wait_retry_agent_death_available_idle_v4`. Only candidate
  ID, runtime contract, and confirmation path differ; all reward, teacher,
  train/dev, model, optimizer, RNG, schedule, and selection fields remain exact.
  Dev-v18 is retired unopened; dev-v19 freezes globally disjoint roots
  `191001..191160` and remains unopened; held-out-v4 stays sealed. The 44 exact
  reward adversaries, 145 Python tests, pinned build, five-seed availability
  ledger, smoke, determinism, and negative replay pass. Config/adversary hashes
  are `17e741e63f9862bc...` and `e2043acefb24a016...`. No V23 model work preceded
  the precommit.
- V23's two admissible pinned replicas reproduce update 5 exactly at 10/10
  construction wins and `0.09043677` idle (checkpoint `2ae62cc31c86731a...`,
  full run `85dfb4e2596cd653...`, direct lineage `b532f8cb8df8e3c...`). Reusable
  preflight nevertheless rejects it: abandonment is definitively
  `+0.04490747` worse than both permanent and matched greedy, and permanent
  idle is definitively `+0.03999701` worse. Report hash is
  `4237a8503bb4bff4...`; dev-v19 remains unopened and is retired, while
  held-out-v4 remains sealed.
- Trace review identified 31/32 non-forced abandons as two-tick alternation
  among resource-short supply targets. Retry holdoffs are now an ordered,
  canonical-hashed set: `CORE_SHORT`/`RESOURCES_SHORT` apply across the task
  type, other failures remain target-local, direct bypass returns
  `retry_not_due`, unrelated task types remain legal, and every entry expires
  exactly when due. The live two-turret fixture proves tick 432 -> 492 behavior;
  the pinned build, 145 Python tests, 5/5 candidate gate, smoke, determinism,
  and negative replay pass. The regenerated golden is byte-identical twice at
  `8fee3db9b5cf01f2...`; all 664 hashes differ from the prior runtime with zero
  non-hash changes. An old-checkpoint diagnostic cannot promote; V24 requires a
  governed from-scratch retrain under the corrected decision sequence.
- ADR-0035 precommits V24 as an exact V23 retrain under runtime contract
  `abandon_wait_resource_scoped_retry_agent_death_available_idle_v5`. Only
  candidate ID, runtime contract, and confirmation path differ. Dev-v19 is
  retired unopened; dev-v20 freezes globally disjoint roots `201001..201160`
  and remains unopened; held-out-v4 stays sealed. No V24 model work preceded
  this packet. The 44 exact-config reward adversaries, 146 Python tests, pinned
  build, 5/5 candidate gate, smoke, determinism, and negative replay pass.
  Config/adversary hashes are `94a7ae8cf57cb1ce...` and
  `4cd7f5096bbd0ebc...`; exact twin replicas are next.
- V24 replica A completed 2,048 episodes/32 updates but failed construction:
  no checkpoint reached 9/10. Best-ranked update 19 is 8/10 with mean idle
  `0.06516475`; the retained frontier hash is `90ead621f808c53f...`. Replica B
  did not start, dev-v20 remained unopened and is retired, and held-out-v4 stays
  sealed. On current-runtime reusable dev-v1, adaptive-v1 is 10/10 with idle
  `0.07308979` and zero abandonment, while update 19 disagrees on 73/427
  unforced decisions and loses seeds 2004/2005. V24 is rejected.
- ADR-0036 precommits V25 as the unchanged resource-scoped runtime with one
  training-loss coordinate: full-boundary teacher coefficient `0.05 -> 0.10`.
  Candidate/label/confirmation metadata also change; every reward, root, model,
  optimizer, RNG, schedule, and selection field remains exact. The current-
  runtime teacher's 10/10 result and V24's 73/427 disagreement motivate the
  bounded step, which is still tenfold below V10's failed `1.0`. Dev-v20 is
  retired unopened; dev-v21 freezes roots `211001..211160` and remains unopened;
  held-out-v4 stays sealed. No V25 model work preceded the packet. All 44 exact-
  config reward adversaries, 147 Python tests, pinned build, 5/5 candidate gate,
  smoke, determinism, and negative replay pass. Config/adversary hashes are
  `90b50d1b7add7fd0...` and `8faa7834e426678e...`.
- V25 replica A completed 2,048 episodes/32 updates but no checkpoint reached
  9/10. Best update 16 is 8/10 with idle `0.06516475`; retained frontier hash is
  `0ad699ece62ab94b...`. Replica B did not start, dev-v21 remained unopened and
  is retired, and held-out-v4 stays sealed. The coefficient accelerated early
  learning (update 1: 1/10 -> 7/10) and reduced mean disagreement logit gap
  `1.49301094 -> 1.07148486`, but the best policy still has 73 disagreements and
  the same losses on seeds 2004/2005. V25 is rejected.
- ADR-0037 precommits V26 as the final fixed full-boundary teacher step:
  coefficient `0.10 -> 0.20`, still fivefold below V10's failed `1.0`. The V25
  logit trend authorizes this bounded test; a construction failure closes the
  coefficient line. All runtime/reward/data/model/optimizer/RNG/schedule/
  selection fields remain exact apart from the mirrored coefficient and
  candidate/label/confirmation metadata. Dev-v21 is retired unopened; dev-v22
  freezes roots `221001..221160` and remains unopened; held-out-v4 stays sealed.
  No V26 model work preceded the packet. All 44 exact-config adversaries, 148
  Python tests, pinned build, 5/5 candidate gate, smoke, determinism, and
  negative replay pass. Config/adversary hashes are `b5e3bf17a1dc1ace...` and
  `202e71a48bf8a05f...`.
- V26 replica A completed 2,048 episodes/32 updates but peaked at only 5/10.
  Best update 10 has idle `0.06423822`; retained frontier hash is
  `0f67cf4484c09ad7...`. Replica B did not start, dev-v22 remained unopened and
  is retired, and held-out-v4 stays sealed. The `0.20` coefficient reversed
  V25's early gain, so the fixed full-boundary teacher-strength line is closed
  and no further coefficient-only successor is authorized.
- ADR-0038 precommits V27 as a non-coefficient successor based exactly on V24.
  It keeps the low online teacher coefficient `0.05`, reward, runtime, roots,
  model, PPO budget, ordinary RNGs, and selection fixed. Before PPO, adaptive-v1
  controls one separately seeded train-v2 cycle; only the 121 unforced labels
  from its five winning episodes enter eight deterministic CE epochs. All 64
  episode summaries remain evidence. Warmup RNGs are `8605`/`8606`, and the
  report plus pre/post model hashes join full-run reproducibility. Dev-v22 is
  retired unopened; dev-v23 freezes disjoint roots `231001..231160` and remains
  unopened; held-out-v4 stays sealed. No V27 model work preceded the precommit.
  All 44 exact-config adversaries, 152 Python tests, pinned build, 5/5 candidate
  gate, smoke, determinism, and negative replay pass. Config/adversary hashes
  are `189ef43857452494...` and `d1c1da02ed7d3a4e...`.
- V27 replica A completed its 64-episode warmup and all 2,048 PPO episodes/32
  updates but failed construction. Warmup evidence matches the precommit: 5/64
  wins, 121 eligible transitions, and 968 presentations; model state changes
  `dbae4c605e52b962... -> ce95e9b0aa8ab34a...`, and the report hashes to
  `b4ca44db858a84a8...`. Eighteen updates reach 8/10 but none reaches 9/10.
  Best-ranked update 20 has idle `0.07044212`; complete frontier hash is
  `d23df387d15966f17...`. Replica B did not start, dev-v23 remains unopened and
  is retired, held-out-v4 stays sealed, and V27 is rejected before preflight.
- ADR-0039 precommits V28 as the exact V27 construction plus one success-only
  teacher-trajectory rehearsal epoch after each PPO update. Reusable diagnosis
  shows V27's disagreement margin grew from `0.02482445` at update 1 to
  `2.24436055` at update 20, so distributed rehearsal targets forgetting rather
  than reopening initial strength or the closed online-coefficient line. Order
  is `PPO -> rehearsal -> checkpoint -> dev`; seed `8607` is separate, the same
  Adam state continues, and an atomic report preserves all 32 rehearsal updates.
  Dev-v23 is retired unopened; dev-v24 freezes roots `241001..241160` and remains
  unopened; held-out-v4 stays sealed. No V28 model work preceded the packet. All
  44 exact-config adversaries, 153 Python tests, pinned build, 5/5 candidate
  gate, smoke, determinism, and negative replay pass. Config/adversary hashes
  are `ef58055e7da5566d...` and `2d672a7f0e816a41...`.
- V28 replica A completed all 32 rehearsal-bearing updates but failed
  construction. Rehearsal CE falls `1.39527905 -> 1.31666994`; its 32-update
  report hashes to `2bd187fea8635206...`. Ten updates reach 8/10 but none reaches
  9/10. Best-ranked update 27 has idle `0.07046312`; its 134/401 teacher
  disagreements match V27, although mean margin improves
  `2.24436055 -> 1.81065121`. Losses remain 2004/2009 and frontier hash is
  `ba963bea1d0d303b...`. Replica B did not start, dev-v24 is retired unopened,
  held-out-v4 stays sealed, and V28 is rejected before preflight.
- ADR-0040 precommits V29 as a corpus-diversity test, not another strength step.
  It freezes 256 globally disjoint train-only teacher roots `291001..291256`
  before observing any outcomes. Teacher warmup/rehearsal uses that auxiliary
  set, while V28's 64-root/2,048-episode PPO construction, reward, runtime,
  model, optimizer values, RNG values, online teacher coefficient, selection,
  and inference remain exact. All 256 outcomes are archived; only successful
  trajectories enter CE. Dev-v24 is retired unopened; dev-v25 freezes roots
  `251001..251160` and remains unopened; held-out-v4 stays sealed. V29
  teacher outcomes/model work were unobserved at precommit. All 44 exact-config
  adversaries, 154 Python tests, pinned build, 5/5 candidate gate, smoke,
  determinism, and negative replay pass. Config/adversary hashes are
  `a40a8772ef5392fb...` and `cac12af7f0861dea...`.
- V29 replica A completed all 256 teacher episodes and 32 rehearsal-bearing
  updates but failed construction. The frozen teacher set yields 37 wins and
  860 eligible transitions; warmup report hash is `582f362322e4aa43...`.
  Rehearsal CE falls `1.32362124 -> 0.46930411`, with report hash
  `b5c089bf4d85acd2...`, but no checkpoint exceeds 4/10. Best-ranked update 5
  has mean return `-10.68702`, core health `182.6`, and idle `0.21429663`;
  frontier hash is `26c6270efca0c852...`. Replica B did not start, dev-v25 is
  retired unopened, held-out-v4 stays sealed, and V29 is rejected before
  reusable preflight.
- ADR-0041 precommits V30 to isolate V29's corpus diversity from its roughly
  sevenfold CE-budget increase. V30 holds V29 exact but caps every warmup and
  rehearsal epoch at 121 deterministically shuffled transitions, restoring
  V28's 968 total warmup presentations and one rehearsal batch per PPO update.
  Exact sampled indices, unique coverage, and schedule hashes join the reports;
  cap-free historical configs retain full-corpus behavior. Dev-v25 is retired
  unopened; dev-v26 freezes roots `261001..261160` and remains unopened;
  held-out-v4 stays sealed. No V30 model work preceded the packet. All 44 exact-
  config adversaries, 155 Python tests, pinned build, 5/5 candidate gate, smoke,
  determinism, and negative replay pass. Config/adversary hashes are
  `c57556695157dcd4...` and `a3bcf116478e1be0...`.
- V30 replica A completed all construction work but peaked at 8/10, so it is
  rejected. Warmup restores exactly 968 presentations/eight batches and samples
  603/860 unique transitions; report hash is `7f92ee1bdaa59d8f...`. Rehearsal
  restores 3,872 total presentations, covers 855/860 transitions across 32
  updates, and lowers CE `1.41403544 -> 1.05248463`; report hash is
  `a2559f5651cc0d54...`. Twenty-one checkpoints reach 8/10. Best-ranked update
  11 has mean return `1.18132`, core health `686.5`, and idle `0.06573742`;
  frontier hash is `e841b620424e0299...`. Replica B did not start, dev-v26 is
  retired unopened, held-out-v4 stays sealed, and reusable preflight did not
  begin.
- ADR-0042 precommits V31 from the stable V24/V30 failure pair. V30 update 11
  loses seeds 2004/2005; seed 2004 has only six policy decisions and two teacher
  disagreements. Every reusable seed begins `BUILD_LINE` while the 10/10
  teacher begins `BUILD_SCHEMATIC`, with learned margins
  `0.83764815..0.85484707`. V31 holds V30 exact and adds `+1.0` only to a valid
  tick-0 `BUILD_SCHEMATIC` logit. The prior is included consistently in rollout,
  PPO, teacher CE, preflight, and final evaluation; all later logits remain
  unchanged and historical configs remain exact. Dev-v26 is retired unopened;
  dev-v27 freezes roots `271001..271160` and remains unopened; held-out-v4 stays
  sealed. No V31 model work preceded the packet. All 44 exact-config
  adversaries, 156 Python tests, pinned build, 5/5 candidate gate, smoke,
  determinism, and negative replay pass. Config/adversary hashes are
  `861f34bd07db43a5...` and `e7eb2f8826db4617...`.
- V31 replicas reproduce selected update 16 exactly at 9/10 wins, return
  `3.11808`, core health `891.0`, and idle `0.07742222`. Checkpoint/model/replay
  hashes are `6961656faaee8d93...`, `d87d193cb36e6604...`, and
  `b9f7e84c938a0bd3...`. Commit `d62fc09872` removes the replica-local warmup
  artifact path from canonical v1 evidence while still validating legacy run
  digests; canonical full-run digest is `b2dacf42484258fb...` and direct lineage
  is `78e923796393ca58...`. Reusable preflight wins 9/10 and beats all four
  observed-rate comparators, but rejects V31: permanent-greedy idle regresses
  `+0.02698246` and abandonment `+0.03137446` with intervals wholly above zero;
  matched-greedy abandonment also regresses, while recovery and permanent
  announcements remain uncertain. Dev-v27 is retired unopened and held-out-v4
  remains sealed. M8.5 is unmet.
- ADR-0043 precommits V32 from reusable V31 traces. All 13 non-forced abandons
  are one-copper `SUPPLY_TURRET` selections that block at zero current copper;
  every available idle run has only WAIT in its catalog during a quiet pre-wave
  gap. V32 keeps V31 exact but masks supply unless the core or selecting unit
  has copper and, for learned seat 0 only, adds a priority-1.0 nonexclusive
  defense-staging task when no ordinary work exists, ending at the existing
  defend-lead boundary. The first all-seat implementation failed public seed
  23456 (4/5); scoping the evidence-backed change to the learned seat restored
  the gate to 5/5 before any model work. Engine-free/live actionability and
  staging checks, the pinned 112-test Java build, candidate gate, smoke,
  determinism, negative replay, 157-test Python suite, and all 44 exact-config reward
  adversaries pass. Dev-v27 is retired unopened; dev-v28 freezes disjoint roots
  `281001..281160`; held-out-v4 stays sealed. This packet was committed before
  V32 model work.
- V32's two pinned replicas reproduce selected update 28 exactly at 10/10,
  return `5.58316`, core health `639.2`, and idle `0.06066571`. Checkpoint,
  model-state, replay, canonical full-run, and direct-lineage hashes are
  `72e10ec9dcf9b30c...`, `dae302b62259866f...`, `837102913ff2596d...`,
  `f4495f671fd72430...`, and `3744c81c88dd435f...`. Fresh V32-runtime
  baselines give learned 10/10, permanent random 5/10, permanent greedy 8/10,
  matched random 4/10, and matched greedy 0/10. Abandonment is now exact zero,
  but corrected reusable preflight rejects V32: permanent-greedy idle regresses
  `+0.02116306` (95% CI `[+0.00659211,+0.03839977]`), while permanent
  announcements/recovery and matched recovery are uncertain. Dev-v28 is
  retired unopened, held-out-v4 remains sealed, and M8.5 is unmet.
- ADR-0044 precommits V33 from reusable V32 evidence only. Mean idle ticks by
  seat are `[4.2, 408.8, 487.4]` for V32 versus `[274.8, 51.5, 298.8]` for
  permanent greedy; scripted seat 1 is the dominant `+357.3`-tick gap while
  learned seat 0 is already `-270.6` better. V33 therefore extends the exact
  V32 proactive-staging rule to fixed seat 1 while preserving seat 2. Every
  model/reward/training field remains exact. Dev-v28 is retired unopened;
  dev-v29 freezes disjoint roots `282001..282160` and remains unopened;
  held-out-v4 stays sealed. Config/seed governance, 158 Python tests, and all 44
  exact-config reward adversaries pass. Runtime implementation and the remaining
  pretraining gates are next; no V33 model work has begun.
- V33 is rejected at its hard public pretraining boundary. Extending defense
  staging to seat 1 changed seed 23456 from a V32 win to a loss at tick 7593,
  so the gate fell to 4/5 even with seat 2 preserved. The experimental runtime
  edit was removed and V32 restored; no replica or model work began. Dev-v29 is
  retired unopened, held-out-v4 remains sealed, and M8.5 is unmet.
- ADR-0045 precommits V34 from a fresh reusable-only V32 trace. Every dev-v1
  win repeats the same seat-1 mask-valid supply and harvest claim losses; the
  latter returns `claim_lost` at tick 254 without advancing the decision
  revision, leaving the unassigned seat idle until tick 660. V34 preserves V32's
  task catalog, partner/learned policies, reward, teacher/training construction,
  and scorecards exactly. It only exposes final atomic loss as structured
  decision boundary `claim_lost`, without assigning or penalizing the loser or
  synthesizing a board event. Dev-v29 is retired unopened; dev-v30 freezes
  disjoint roots `283001..283160` and remains unopened; held-out-v4 stays sealed.
  Config/seed governance, 159 Python tests, and all 44 exact-config reward
  adversaries pass. Runtime implementation and pretraining gates are next; no
  V34 model work has begun.
- V34 is rejected at the complete public pretraining boundary. The all-seat
  wake preserved 5/5 survival but reduced required proactive-staging starts
  from five to zero. A temporary diagnostic found every public claim loss on
  learned seat 0 (`[9,14,10,10,9]` by seed) while the reusable 406-tick defect
  is on scripted seat 1. The experiment was removed and V32 rebuilt; its gate
  again passes 5/5 with five staging starts. Replica A never began, dev-v30 is
  retired unopened, held-out-v4 stays sealed, and M8.5 is unmet.
- ADR-0046 precommits V35 from those disjoint public/reusable traces. Only final
  atomic loss from fixed scripted seat 1 wakes structured `claim_lost`; losses
  from learned seat 0 and scripted seat 2 preserve V32 scheduling. The loser
  still receives no assignment, fake board event, or invalid penalty. All other
  V32 policy/reward/teacher/training fields remain exact. Dev-v30 is retired
  unopened; dev-v31 freezes disjoint roots `284001..284160` and remains unopened;
  held-out-v4 stays sealed. Config/seed governance, 160 Python tests, and all 44
  exact-config reward adversaries pass. Implementation and pretraining gates are
  next; no V35 model work has begun.
- V35's implementation checkpoint passes the focused fixed-seat live check,
  pinned Java build, and complete public candidate gate. Seat 1 wakes after one
  tick on a real harvest `claim_lost`; seat 0 loses the same task without a
  boundary. Winner ownership remains authoritative and no fake board event is
  emitted. The public gate is 5/5 with all five proactive-staging starts
  restored. From implementation commit `673042bfd0`, smoke, cross-process/reset/
  seed determinism, the 16,200-tick golden replay, and negative replay all pass.
  Replica A is authorized; dev-v31 and held-out-v4 remain unopened.
- V35's exact replicas select update 8 at 9/10, return `3.85778`, core health
  `721.8`, and idle `0.05600096`; checkpoint/model/replay/full-run/direct-lineage
  digests all reproduce. Fresh baselines are random 4/10 and greedy 8/10.
  Reusable preflight beats every win comparator and strongly improves matched
  idle/recovery, but rejects permanent-greedy idle by `+0.01815752` (95% CI
  `[+0.00077632,+0.04116776]`) with other uncertain intervals. Per-seat idle is
  `[390.1,8.1,380.0]`: learned seat 0 loses the biased tick-0 schematic claim
  and idles 250 ticks in every episode. Removing the prior chooses `BUILD_LINE`
  but the off-contract checkpoint wins only 6/10, so a successor must retrain.
  V35 is rejected, dev-v31 is retired unopened, held-out-v4 remains sealed, and
  M8.5 is unmet.
- ADR-0047 precommits V36 from the exact learned-seat collision trace. It changes
  only the tick-0 `+1.0` training prior from `BUILD_SCHEMATIC` to `BUILD_LINE`,
  the rejected checkpoint's unadjusted first choice on all ten reusable seeds.
  V35 runtime, rewards, teachers, budgets, model, RNGs, roots, and gates remain
  exact. Dev-v31 is retired unopened; dev-v32 freezes disjoint roots
  `285001..285160` and remains unopened; held-out-v4 stays sealed. Config/seed
  governance, 161 Python tests, and all 44 exact-config reward adversaries pass.
  No V36 model work has begun.
- From committed V36 packet `f8b191c582`, the focused seat-1 positive/seat-0
  negative wake check, pinned Java build, and complete public candidate gate
  pass. Public survival is 5/5 and proactive staging starts in all five seeds.
  Smoke, cross-process/reset/seed determinism, the 16,200-tick golden replay,
  and negative replay pass. Replica A is authorized; dev-v32 and held-out-v4
  remain unopened.
- V36 replica A completes all 32 updates but no checkpoint clears the 9/10
  construction floor. Rank-best update 5 is 7/10 with return `-0.17522`, core
  health `488.3`, and idle `0.05917146`; replica B is prohibited. Build-line
  removes learned-seat idle but loses seeds 2001/2003/2004. Reusable-only
  harvest and one-tick-replan diagnostics each win 6/10; forced WAIT preserves
  V35's 9/10 but reproduces its exact rejected idle profile. The public policy
  also loses the schematic claim at tick 0 on all five seeds, so a runtime
  tick-0 wake is not isolated from V34's staging failure. V36 is rejected,
  dev-v32 is retired unopened, held-out-v4 stays sealed, and M8.5 remains unmet.
- ADR-0048 precommits V37 from accepted-task timelines. V37 returns to the
  complete V35 construction and changes only fixed scripted seat 2's tick-0
  opening from its colliding schematic choice to valid `HARVEST_RESOURCE`;
  learned seat 0 retains the V35 schematic prior and timing. The unchanged V35
  checkpoint is 9/10 off-contract with idle ticks `[267.0,0.7,308.2]`, versus
  V35 `[390.1,8.1,380.0]`; seat-2 build-line and other simple alternatives fail
  at 6/10. Dev-v32 is retired unopened, dev-v33 freezes disjoint roots
  `286001..286160`, and held-out-v4 stays sealed. Config/seed governance and all
  44 exact-config reward adversaries pass, and the precommit Python suite was
  162/162. No implementation or V37 model work preceded the precommit.
- V37's fail-closed scripted-partner opening is implemented across teacher/PPO
  collection, reusable evaluation, checkpoint replay, matched controls,
  confirmation, and final evaluation. It emits an ordinary structured
  candidate selection, archives the full action in decision traces, leaves
  legacy configs and permanent public baselines unchanged, and rejects missing,
  duplicate, invalid, or masked candidates before stepping. The complete Python
  suite is 165/165. From implementation commit `0c4a09659f`, the pinned Java
  build/tests, focused seat-1 wake check, and complete public gate pass; public
  survival is 5/5 with all five proactive-staging starts. Smoke, cross-process/
  reset/seed determinism, the 664-checkpoint/16,200-tick golden replay, negative
  replay, and all 44 exact-config reward adversaries pass. Replica A is
  authorized; dev-v33 and held-out-v4 remain unopened, no V37 model work has
  begun, and M8.5 remains unmet.
- V37 replica A selects update 16 at the exact precommitted floor: 9/10 reusable
  wins, mean return `4.18676`, core health `805.5`, and idle `0.05108287`.
  Checkpoint/model/replay/full-run digests are `a9a55110fe2266b8...`,
  `21b665232664f79e...`, `9b67d5d468f86a55...`, and
  `614c071b7f3003b0...`; the two fresh checkpoint replays are bit-exact. Replica
  B is authorized from the same frozen commit/config/toolchain. Dev-v33 and
  held-out-v4 remain unopened; no scorecard or confirmation work has begun.
- V37 replica B reproduces A exactly: update 16, 9/10 wins, return `4.18676`,
  core health `805.5`, idle `0.05108287`, checkpoint/model/replay/full-run
  digests, teacher evidence, and canonical frontier evidence all match. The
  repository comparator reports bit-exact full-run digest
  `614c071b7f3003b0...`; direct lineage passes with digest
  `fd69503ae40e977b...` and artifact SHA-256 `3c17cfdf02a43fcb...` from training
  commit `8d323a3c72`. Reusable permanent-greedy and matched-greedy scorecards
  are next. Dev-v33 and held-out-v4 remain unopened.
- V37's reusable preflight is ineligible despite 9/10 candidate wins versus
  permanent random 4/10, permanent greedy 8/10, matched random 5/10, and matched
  greedy 3/10. The matched-greedy scorecard passes every observed metric, with
  idle improved by `-0.13391229` and recovery by `-88.95` ticks. The required
  permanent-greedy scorecard fails uncertainty: announcements are
  `-0.00364304` (95% CI `[-0.01624392,+0.01056959]`), idle is `+0.01323943`
  (`[-0.00258843,+0.03051348]`), and recovery is `-12.9` ticks
  (`[-94.5525,+51.5525]`). V37 is rejected under the frozen non-regression rule;
  dev-v33 is retired without execution, and M8.5 is unmet.
  The preflight report SHA-256 is `faac2dc071489f25...`.
- ADR-0049 records a post-rejection governance incident: a delegated read-only
  review opened the dev-v33 and held-out-v4 seed manifests despite an explicit
  prohibition. No episode or outcome was produced, but membership exposure
  retires both sets unexecuted. Neither may ever be used. The next successor
  must precommit globally disjoint dev-v34 and held-out-v5 sets plus an umbrella
  one-way marker created before any membership read or baseline episode.
- Two reusable-only off-contract V38 diagnostics are rejected. Collision
  redirect (`097d8f5c95b0bbd6a40d3f8fbca0ca6e86d527d4bbf1c8a1f3a01ebc52ff2490`)
  falls from V37's 9/10 to 6/10 and increases idle `7,840 -> 11,609`
  (`+48.07%`): learned seat 0 saves 3,053 ticks while seat 2 gains 6,988. Of 37
  rewrites, 34 target seat 2 and 13 become `WAIT`; seeds 2002/2003/2006 flip to
  losses. Partner-intent masking
  (`83a4242b6b7df288ec20976029356637de61a3e2adf9736b1a3cff41e5006319`) is
  evidence-bound to V37's exact config/checkpoint/lineage and public reusable
  set, but reaches only 7/10 and mean core health `500.0`. Idle changes
  `7,840 -> 7,182`, by seat `[4,658,342,2,840] -> [4,619,338,2,225]`; only 39
  learned-seat ticks are saved and seed 2002 seat 2 supplies 617/658 of the
  reduction. Mean authoritative idle is `0.05223`; 48 masks produce clean
  traces with no invalid or unaccepted learned action, but seeds 2005/2010 flip
  to losses. Announcement/recovery parity is not measurable from this
  diagnostic. Both coordinates are rejected; the subsequent V38 precommit is
  described below. M8.5 remains unmet.
- The read-only actionability artifact
  `0500a74377b740556e3012635491318acbde3939c7f179bd24e79aa46ebf2099` preserves
  V37 exactly across all 1,128 action/tick/state-hash boundaries: 9/10 wins,
  mean core health `805.5`, and idle `[4,658,342,2,840]`. All 4,658 learned-seat
  idle ticks overlap the fortification board task, including 4,611 while its
  `BUILD_SCHEMATIC` is `RUNNING` under seat 1. There are 1,607 learned-idle ticks
  with no valid non-WAIT action and no exposed staging candidate; six harvest
  claim losses contribute 3,011 ticks. No learned-idle interval exposes a valid
  proactive staging action.
- ADR-0050 precommits V38 as V37 plus one learned-seat-only catalog exposure:
  the existing nonexclusive proactive `DEFEND_REGION` candidate may be present
  while another seat owns a live `BUILD_SCHEMATIC` in the quiet pre-defend-lead
  window. There is no force, mask, redirect, or scripted-seat change; retraining
  and fresh baselines are required. Config SHA-256 is
  `d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`.
  Umbrella reservation SHA-256
  `a2e2389925797a5f5a8c93224561f68f36fd443afbebdc07f888aaf6bef6f27a` is part
  of the governance/config/umbrella/test packet committed at `de597c8462`
  before membership access. The primary-only freezer commit is `a7504a4781`;
  freeze commit `9c8f7f3d32` records `values_emitted=false`, 41 pre-existing
  membership documents, and 5,321 unique prior roots. Dev-v34 and held-out-v5
  are now frozen at 160 unique, globally disjoint roots each, with hashes
  `bef6bb17c7759530dc216961733839808dbff228bb96a09232dced89a7ca5ac7` and
  `1118ef59b0953aacd86176737777013bb2c6498e128f28bcbb7850e6ad586910`.
  The value-free freeze record hash is
  `7282a3cd405f2d6b00dd3942fb8da2b2f62eb3a8f567dc067edc07756787018e`.
  Both sets remain unconsumed. V38's runtime implementation is committed at
  `8b3f9cc749`, with the complete pretraining boundary green. On public seed
  12345, the focused live probe observes seat 1 running `BUILD_SCHEMATIC`, one
  valid learned-seat `DEFEND_REGION` stage beside ordinary `BUILD_LINE`, no
  scripted-seat stage, and no synthetic claim/helper/event. Focused
  `CandidateGenerator` tests and Gradle `agent-core:test rl-server:test
  agent-plugin:classes` pass; Python is 166/166. The public candidate-policy
  gate is 5/5 with 10 proactive staging starts; smoke is 9/9. Determinism ends
  at cross-process `20a97f36407167597981e77c`, reset
  `a2cf4a73ee901c844f30f486`, and alternate seed
  `495ba05fa71697bdc8ff2951`. Golden replay covers 664 checkpoints, 16,200
  ticks, and two episodes, and negative replay detects a one-line `MINE`
  change. All 44 exact-config reward adversaries pass for config
  `d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`; the
  temporary, uncommitted report SHA-256 is
  `e44865297a31ab1625bf4a43116cf1ff712b96657043c200c0af629ddd4f59bf`.
  At that implementation checkpoint, no baseline episode or model work had
  begun; replica B was allowed only after at least 9/10 wins with mean idle
  below `0.25`.
- V38 replica A completed from committed repository
  `3effefed781b88c2e71354d784db58eb787ed7e6` under exact config
  `d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf` and lock
  `8d865c8c710a61d7e37b8896b38166a1dcf121e40d17fbb1a47e948b4861bf6c`.
  It completed 256 warmup episodes, 2,048 training episodes, and 32 updates;
  update 20 was selected at 9/10 wins, return `4.859680000000006`, core health
  `565.2`, and idle `0.021071738935729764`. Checkpoint/model-state hashes are
  `3bc4a3a1cc9c2ef4450e20c689c3909a8bf9ae8ba35b194e8710df1acf737b5e` and
  `b9f592ffe58d1b866f200cd3544a2ecfd48f6d662f517aece3dffa745fa66540`.
  Both replay passes are bit-exact at
  `272dfb7a5793c1b79be95ce9b7e2407c3752cb6ee183cf9440dbe388ee4553af`;
  action-state is
  `5ba7991a0dd10f0d857c5fcbf75ccbbb573eb7a7c59b975967c3432463f3c68c`,
  canonical full-run is
  `356a2065c8c2001ba6e9b2b480949e0c4ff3fdfd39b88ac8747c49e2838f57a2`,
  frontier is
  `9955422e926e955700370f6dcf792c1c1054e6501e8b5b46afb151911ea78c7b`,
  and manifest is
  `e61516546eabb0cf35d53f699c1e24fa20f214f9a534678cf69ff5361ecd63ad`.
  The gate passes exactly (`>=9/10`, idle `<0.25`), so exact replica B is
  authorized from the same commit/config/toolchain in an independent output.
  Dev-v34 and held-out-v5 remain unconsumed; no scorecard, confirmation, or
  final episode has run. M8.5 remains unmet.
- V38 replica B completed independently from the same exact training/repository
  commit, config, and lock, selecting update 20 with the identical 9/10 wins,
  return `4.859680000000006`, core health `565.2`, and idle
  `0.021071738935729764`. All 32 checkpoints are byte-identical; selected
  checkpoint/model, replay, action-state, and canonical full-run reproduce at
  `3bc4a3a1cc9c2ef...`, `b9f592ffe58d1b86...`, `272dfb7a5793c1b79...`,
  `5ba7991a0dd10f0d...`, and `356a2065c8c2001b...`. Warmup raw hash is exact at
  `d1dab1c2d438ba95...`; path-bearing rehearsal/frontier/manifest raw hashes
  differ as expected while governed canonical validation passes. Direct lineage
  passes `selector_checkpoint_direct_lineage_v1` with exact selected update 20,
  commit, checkpoint, model, and config; digest is `ada0bcca1d60b25b...` and
  artifact SHA-256 is `9a608dc354ff06ba3...`. Exact replicas are complete.
  Fresh permanent random/greedy and matched V38 baselines, followed by reusable
  scorecard preflight, are next. Dev-v34 and held-out-v5 remain unconsumed;
  confirmation/final remain prohibited and M8.5 remains unmet.
- ADR-0051 accepts the selected-only reusable-evaluation contract implemented
  by guard commit `9bc96f91c7219ad9e9656f99b29f15331b78b399`. Governed runs require an
  explicit `--seed-set-file`, declared split, pre-read held-out gate, caller-
  supplied runtime, and config/repository/JAR provenance; they reject stale
  promotion provenance and never invoke Gradle implicitly. Legacy registry
  loading remains diagnostic-only compatibility and cannot be a promotion
  fallback. Python passes 176/176; the exact-config reward report remains
  44/44 at `e44865297a31ab1625bf4a43116cf1ff712b96657043c200c0af629ddd4f59bf`.
- Fresh selected-only permanent baselines bind config
  `d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`,
  repository `9bc96f91c7219ad9e9656f99b29f15331b78b399`, and JAR `5d4fc89f...`.
  Records/aggregate hashes are `aaf28dd1...`/`4bbc3aa3...`. Permanent random
  is 4/10 with idle `0.0153280914` and core health `217.7`; permanent greedy is
  8/10 with idle `0.0157205468` and core health `707.2`. V38 selected update 20
  reproduces on reusable dev-v1 at 9/10, return `4.85968`, core health `565.2`,
  and idle `0.0210717389`. Matched random is 5/10 with idle `0.1635828272`;
  matched greedy is 6/10 with idle `0.0888449994`. All four observed win
  comparisons pass.
- V38 is rejected by the frozen dual scorecards. Against permanent greedy,
  announcements (`-0.00307796475`, CI `[-0.0150290537,0.0074881288]`),
  duplicates (`-0.6`, CI `[-1.9,0.6]`), and idle (`+0.00535119211`, CI
  `[-0.0112619599,0.0266615919]`) are uncertain; recovery (`-108.4`, CI
  `[-168.10125,-46.15]`) and abandonment pass. Against matched greedy,
  announcements (`-0.0187138416`, CI `[-0.0269992949,-0.0108248022]`) and idle
  (`-0.0677732604`, CI `[-0.0946828840,-0.0412051517]`) pass; duplicates
  (`-1.0`, CI `[-3.4,0.8]`) and recovery (`-20.85`, CI
  `[-100.3025,61.4025]`) are uncertain; abandonment passes. Preflight is false;
  records/aggregate/report hashes are `99575abd...`/`aa3fa1fe...`/`e6c9cf27...`.
  ADR-0050 makes uncertainty a failure, so rejection occurs before confirmation.
  Dev-v34 is retired unopened and unconsumed without any membership read;
  held-out-v5 remains sealed and unconsumed. M8.5 remains unmet. Next diagnose
  one coordinate using reusable evidence only, precommit it, and freeze a new
  dev confirmation identity before model work.
- Four reusable-only V39 diagnostics completed with byte-exact twins and full
  candidate/matched/permanent parity, and all are rejected. The WAIT
  communication artifact
  `014085de7007e4d6227e6c5ae89ee1cd636b60f036c6b1db23a8acdd41908ad6`
  records structured/suppressed counts of candidate `17641/74`, matched
  `16161/69`, and permanent `17252/74`; candidate-minus-permanent is uncertain
  before filtering (`-0.00307796`, CI `[-0.01502905,0.00748813]`) and after
  (`+0.00176772`, CI `[-0.00574127,0.00877167]`), while matched stays pass.
  The claim-loss artifact
  `e3c726380516e9762566ab5b98dc3312758f52d2c943b979e49263cefbb9f794`
  has 10/10 canonical parity and finds 19 learned-seat-0 losses: 18 supply, one
  harvest, zero staged/live partner schematics, 19/19 valid ordinary non-WAIT
  choices, and zero extra boundary reconvergences. Seed 2005's tick-2053,
  gap-695 harvest could expose `BUILD_LINE` one tick earlier at 694 only by
  changing the trajectory and recreating V34 staging-disappearance risk.
- The recovery catalog
  `727e62145895a5a9435a6c62372156a7887c5dd12d2d5d204d8d7b89bc5d298e`
  finds 30 deaths and zero same-type valid choices at the exact death boundary.
  Seeds 2004/2006 first permit `HARVEST` on the next tick but require
  bias-to-tie above `3.822402`/`3.973103` against defense, so this is not a
  narrow coordinate. The supply-collision artifact
  `9b9905b208dceb95b9ddbf240a4050d63a85779b321eec7b6fc35bdfb1e26870`
  records 18 collisions/seven bursts, alternate supply in 11/18, and 18 mask
  changes (11 supply, six schematic, one harvest), but only 6/18 have an
  alternate-supply prior within `+1`. This repeats the 18/37 rejected redirect
  rewrites and 18/48 rejected masks and changes duplicates only, not recovery
  or idle.
- ADR-0052 precommits V39's single selector-input coordinate. Exact same-boundary
  fixed-partner `task_id` intent raises only the matching learned candidate's
  existing `duplication_risk` input to `1.0`; it does not mask, redirect, force,
  reorder, suppress, or apply an action. Runtime, feature dimensions, action
  vocabulary, model, reward, optimizer, roots, teacher, budget, RNGs, and
  checkpoint ranking remain V38-exact. ADR-0053 supersedes only its final-set
  metadata after a legacy full-suite
  test read retired held-out-v5. The behavior-identical live config hashes to
  `54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924`.
  A value-free umbrella reserves dev-v35 for primary-only construction after
  this precommit. Dev-v35 is now frozen value-free with zero membership reads
  and remains unconsumed. Held-out-v5 is retired without outcomes; a committed
  replacement umbrella now freezes held-out-v6 in a disjoint no-read namespace.
  Its value-free receipt hashes to `4f31a7078e5cd45628c4c8e25843b7baac4c598c40782870942ec9559d3b9d3e`;
  membership SHA is `2bf4aa04ef54d873e961ff367db849c14c72b83bb4d280c4e31ba75bdeefa51c`.
  Confirmation consumption and final access remain prohibited.
  M8.5 remains unmet. The implementation passes 198 Python tests, pinned Java,
  public 5/5 survival/staging, smoke, determinism/replay controls, and 44/44
  exact-config reward adversaries for the revised hash. The ignored revised
  reward report hashes to
  `f3365c5abdd30fb8f1f7731c245c4b00b15870f5f22839f65aab4a9ebdc5173e`.
- V39 replica A completed all 32 updates but failed the frozen construction
  floor. No checkpoint reached 9/10; rank-best update 25 is 8/10 with return
  `3.3231000000000073`, core health `448.0`, and idle
  `0.01845563475648595`. Checkpoint/frontier hashes are
  `1af02875472f54a6...` / `181ed3e7069b429b...`. No selected manifest or
  replica B exists. V39 is rejected; dev-v35 is retired unopened/unconsumed,
  held-out-v6 remains sealed/unconsumed, and M8.5 remains unmet.
- ADR-0054 precommits one training-only V40 coordinate from reusable/train-only
  evidence. V39's partner-intent feature flips every reusable opening in the
  same narrow risk interval, so a scalar change is rejected. Instead V40
  excludes from teacher imitation only the exact labels whose action index is
  simultaneously marked as partner-intent duplicate risk. The fixed warmup
  schedule contains 752 such conflicts among 3,956 teacher-eligible
  transitions; V39 presented 177 in warmup and 734 in rehearsal. PPO
  policy/value learning, runtime, reward, model, roots, budget, and RNGs remain
  exact. Config SHA is `230759e7e02dcca9...`; a committed value-free umbrella
  reserves primary-only dev-v36 in `[4B,5B)`. The filter implementation is
  committed at `c9459c58f4`; 208 Python tests pass. The bound train-only
  diagnostic reproduces all counts, including the corrected 189 successful-
  corpus conflicts, and hashes to `4fe2960225d659cb...`. No dev-v36 membership
  construction, baseline episode, or model work has begun.
- V40's complete pretraining boundary is green: 208 Python tests, pinned Java,
  public survival 5/5 with 10 staging starts, focused wake/staging, smoke,
  accepted cross-process/reset/alternate-seed determinism, the 664-checkpoint
  16,200-tick golden plus negative control, and 44/44 exact-config reward
  adversaries. The reward report hashes to `9677e5caed4d891...`. Primary-only
  dev-v36 freezer code and pure tests now pass within the 211-test suite. The
  freezer uses only `[4B,5B)`, hashes in-memory bytes, and reads no membership.
  It was committed at `54db674e2e` before execution. Dev-v36 is now frozen
  value-free and unconsumed: membership/receipt hashes are
  `d4bfbcf88d99f4f...` / `fce63a49f80d165...`, with no membership reads or
  emitted values. Held-out-v6 remains sealed; baselines and model work remain
  absent. The receipt-aware Python suite passes 212 tests without opening
  membership.
- V40 replica A completed the exact 256-warmup/2,048-PPO/32-update construction
  from committed repository `c288483436`. The frozen rule selects update 28 at
  10/10 reusable wins, mean return `7.77414`, core health `656.3`, and idle
  `0.008388499062201467`; checkpoint SHA is `9ff618797d8ae593...`. Fresh
  checkpoint replays are bit-exact at `5af990a3ec8ff7fb...`; the action-state
  and full-run digests are `4f0726c7dc8f127...` and `b6dd3c958762c082...`.
  Replica B is authorized. Dev-v36 and held-out-v6 remain unopened/unconsumed;
  no reusable scorecard, confirmation, or final episode has run.
- V40 replica B reproduces Replica A exactly: update 28, 10/10 wins, every
  scorecard mean, all 32 checkpoint files, warmup, checkpoint/model, replay,
  action-state, and full-run evidence match. Canonical manifest comparison
  passes. Direct lineage validates with digest `cfb0ec1b21fd49fb...` and
  artifact SHA `5fdc3bdabf24ee5e...`. Fresh selected-only permanent baselines
  and reusable dual scorecards are authorized next. Dev-v36 and held-out-v6
  remain unopened/unconsumed.
- V40 is rejected at the reusable dual-scorecard gate. Fresh selected-only
  permanent random/greedy are 4/10 and 8/10; candidate is 10/10, matched random
  5/10, and matched greedy 6/10, so all observed win gates pass. Permanent-
  greedy announcements and idle remain uncertain, while matched-greedy
  recovery remains uncertain. Records/aggregate/report hashes are
  `3fe4454202460b4...` / `eafe2ce3faf8baba...` / `8453b0c4b75cd681...`.
  Dev-v36 is retired unopened/unconsumed; held-out-v6 remains sealed and
  unconsumed. No confirmation or final episode ran.
- ADR-0055 precommits V41's single 50/50 adjacent-frontier midpoint. A canonical
  reusable-only diagnostic proves V40 updates 25, 26, and 28 are all 10/10 and
  all fail the same announcement/idle/recovery rows; updates 25 and 26 have
  complementary idle outliers. V41 derives one checkpoint from exact update-26
  and update-25 parents without changing runtime, reward, features, roots, or
  action authority. Config/umbrella hashes are `c4705974f18512a...` /
  `7ce8f5cf640978ef...`. The 44/44 exact-config reward gate passes at report
  SHA `995d9db2f866d5f2...`. Dev-v37 is frozen value-free and unopened in
  `[5B,6B)`; its membership/receipt hashes are `7874f5abaf230665...` /
  `277264b80c6456f7...`. The constructor now preserves config-selected reward
  schema while retaining legacy v1 behavior (224 Python tests pass). Under the
  pinned WSL Torch 2.12.1 toolchain, independent A/B constructions are exact:
  checkpoint `b6b5e98ddee56740...`, model state `93594bd64193740a...`, and
  canonical lineage `37c4b1e571fca96c...`. Fresh permanent random/greedy
  baselines are 4/10 and 8/10; the midpoint is 10/10 versus matched random /
  greedy 5/10 and 6/10, so all observed win comparisons pass. V41 is rejected
  because permanent-greedy idle remains uncertain (mean `-0.00739956`, 95% CI
  `[-0.02001559,+0.01067689]`) and matched-greedy recovery remains uncertain
  (mean `-19.85`, 95% CI `[-81.80125,+29.65]`). Records/aggregate/report hashes
  are `543e50b729097326...` / `056b356de88704f0...` /
  `ca7b39c84a9f51d1...`. Dev-v37 is retired unopened/unconsumed; held-out-v6
  remains sealed/unconsumed. No confirmation or final episode ran.
- Public-only V42 diagnosis closes learned WAIT-logit and danger-label fixes:
  seed 2006's adverse idle follows learned-seat death and forced WAIT while both
  surviving scripted seats have only structured `runtime:wait` candidates, and
  teacher/learned danger is zero before every public learned-seat death. The
  exact teacher train schedule instead exposes one untried label coordinate.
  An optimizer-free diagnostic reproduces V40's 94/256 wins and 752 exact
  partner-intent conflicts, finding valid deterministic nonconflicting labels
  for 682 conflicts and 174/189 successful-corpus conflicts; 70 retain filter
  fallback. ADR-0056 precommits V42 to that pure adaptive-preference-preserving
  relabel only. Config/umbrella hashes are `3fcb0c8800c638a3...` /
  `c1644d2dd6dde231...`. Dev-v38 is primary-only in `[6B,7B)` and is now frozen
  value-free and unopened; held-out-v6 remains sealed/unconsumed. The implementation
  separates original/effective labels, applies the shared V42 rule to all three
  generic teacher paths, and records deterministic relabel/fallback/schedule
  telemetry. The production diagnostic reproduces the exact 752/682/70 split
  over 34,898 transitions and 3,956 eligible labels; its report/payload/action-
  state hashes are `83f8dd6904e5356d...` / `e92436ffb3773b80...` /
  `0e609742ba171c60...`. The 2026-07-23 pretraining boundary is green: 243
  Python tests and the Java gate pass; public policy is 5/5 with 10 proactive
  staging starts; secondary-claim and owned-schematic checks pass; smoke passes;
  cross-process/reset/alternate-seed determinism hashes are
  `20a97f3640716759...` / `a2cf4a73ee901c84...` /
  `495ba05fa71697bd...`; golden replay is 664 checkpoints / 16,200 ticks / two
  wins and negative replay detects the mutation. All 44 reward adversaries pass
  under the exact config; report SHA is `272ac291ef143fa6...`. The freezer was
  committed at `3e328ce91e`, then dev-v38 and its value-free receipt were
  committed at `949b73f987`. Membership/receipt hashes are
  `3f4b0d012cf87303...` / `fea431ae993d1072...`; zero membership documents were
  read and no values were emitted. The freezer packet lifts the full suite to
  248 Python tests. Independent pinned-toolchain replicas from training commit
  `12980ee2b9` are exact across all 32 checkpoint files. Both select update 2 at
  9/10 reusable wins, mean return `4.73976`, core health `568.8`, and idle
  `0.03455784384563236`. Checkpoint/model/replay/action-state/full-run hashes are
  `65f8e3dc3a41bf89...` / `4363617f8535bc8b...` /
  `d01d0dfe425d1b0d...` / `52751513f785c196...` /
  `cb719361da11ab6c...`. Direct lineage digest/artifact hashes are
  `b1dbf1abc6a7dacd...` / `100945a4820b2039...`. Fresh permanent random/greedy
  are 4/10 and 8/10; candidate is 9/10 and matched random/greedy are 5/10 and
  6/10, so all four win comparisons pass. V42 nevertheless fails both frozen
  scorecards: permanent-greedy announcements and idle are uncertain, and
  matched-greedy recovery is uncertain. Records/aggregate/report hashes are
  `e0a78468268bc021...` / `dae12fbf3868c6cc...` /
  `01bf941060bc7e6f...`. V42 is rejected before confirmation. A non-promotable
  public diagnostic retargets only the existing tick-zero prior to `BUILD_LINE`:
  all ten openings become nonconflicting and idle passes decisively, but the
  result remains 9/10 and still fails permanent announcements and matched
  recovery. Records/report hashes are `6ccd6ac543d43891...` /
  `41e3b71b133f4c63...`. This closes the runtime-prior reopening; no V43 is
  authorized. Dev-v38 is retired unopened/unconsumed and held-out-v6 remains
  sealed/unconsumed.
- ADR-0060 precommits V43 as a model-only architecture successor. The v1 actor
  cannot compare SELECT candidates and its CONTINUE/WAIT logits cannot see the
  candidate catalog. V43 adds deterministic masked candidate-set context while
  preserving V42 runtime authority, features, reward, teacher trajectory and
  relabeling, roots, budgets, optimizer, RNG values, scripted seats, and engine
  pins. Config/umbrella hashes are `29b4430839451f13...` /
  `99851aa2cdbfb469...`. Dev-v39 is reserved primary-only in `[7B,8B)` and is not
  constructed; dev-v38 remains retired without a read and held-out-v6 remains
  sealed. Implementation and the full pretraining boundary are pending; no V43
  model work or restricted membership access has occurred.
- The V43 implementation boundary is green. Config-selected v1/v2 construction,
  masked set pooling, dynamic checkpoint schema, and training/replay/lineage/
  preflight/final compatibility are implemented. The boundary passes 293 Python
  tests, pinned Java, public 5/5 survival with 10 staging starts, both focused
  coordination checks, smoke, deterministic golden and negative replay, and all
  44 exact-config reward adversaries (report SHA `3e3210447ff4f428...`). Dev-v39
  remains unconstructed, dev-v38 remains retired without a membership read,
  held-out-v6 remains sealed, and no V43 training episode has run.
- The primary-only dev-v39 freezer is implemented and tests exact config/
  umbrella hashes, paths, identity, count, namespace, and sealed-final binding.
  It atomically creates membership plus a value-free zero-read receipt. All 298
  Python tests pass. The freezer has not executed and dev-v39 is unconstructed;
  it must first be committed.
- Committed freezer `5007a7b9f3` created dev-v39 value-free in `[7B,8B)`.
  Membership SHA is `0b88fda1b37647aa...`; its receipt records no emitted values
  and zero membership-document reads. The membership/receipt packet was
  committed at `df7723c6cb` before replica A; dev-v39 remained unconsumed.
- The V43 membership packet was committed at `df7723c6cb`; two pinned replicas
  then reproduce exactly at update 27 with 10/10 wins, mean idle `0.00874233`,
  checkpoint `b4cc691ad0c08d67...`, and full-run digest
  `66385a8f85ec7db7...`. All win comparisons and permanent recovery pass, but
  permanent announcements/idle and matched recovery remain uncertain. Report
  SHA is `10f829a54a110507...`. V43 is rejected before confirmation; dev-v39 is
  retired unopened/unconsumed and held-out-v6 remains sealed. M8.5 is unmet.
- ADR-0061 precommits V44 as a bounded temporal successor. The remaining V43
  misses are sequence-defined, but v2 sees only the current boundary; reusable
  root 2004 pairs 65 WAIT decisions with the sole high-idle candidate trace.
  V44 appends the previous boundary's 56 base scalars, masked 37-value candidate
  mean, candidate-count fraction, and submitted ten-way action one-hot. The V43
  set actor is retained with a 160-input scalar encoder. Config/umbrella hashes
  are `9a23c90567754eb8...` / `4a526274d9568726...`. Dev-v40 is reserved in
  `[8B,9B)` but remains unconstructed; dev-v39 remains retired without a read,
  held-out-v6 remains sealed, and no V44 model work has occurred.
- The V44 implementation boundary is green. Config-selected v1/v2/v3 feature
  and model construction, immutable/reset-local lag snapshots, dynamic feature+
  model checkpoint identity, and training/replay/lineage/preflight/final
  compatibility are implemented. The boundary passes 305 Python tests, pinned
  Java, public 5/5 survival with ten staging starts, both focused checks, smoke,
  deterministic golden/negative replay, and all 44 exact-config reward
  adversaries (report SHA `740aba578809911...`). Dev-v40 remains unconstructed,
  dev-v39 remains retired without a membership read, held-out-v6 remains
  sealed, and no V44 training episode has run.
- The primary-only dev-v40 freezer is implemented and tests exact config/
  umbrella hashes, paths, identity, count, `[8B,9B)` namespace, and the sealed-
  final binding. It atomically creates membership plus a value-free zero-read
  receipt. All 310 Python tests pass. The freezer has not executed and dev-v40
  remains unconstructed; it must first be committed.
- Committed freezer `6b7a6c5dca` created dev-v40 value-free in `[8B,9B)`.
  Membership/receipt hashes are `05ca1f48227581fc...` /
  `acffc919ab1c40e2...`; the receipt records no emitted values, zero membership
  reads, and no retired or sealed-set access. Dev-v40 remains unconsumed. The
  membership/receipt packet must be committed before replica A.
- The V44 membership packet was committed at `b510cc48a1`; two pinned replicas
  then reproduce exactly at update 1 with 9/10 wins, mean idle `0.07252724`,
  checkpoint `4e51d31bd4f33a67...`, and full-run digest
  `029e77830406127a...`. All observed win comparisons, matched announcements,
  and permanent recovery pass. The frozen scorecards reject V44 because
  permanent idle decisively regresses and five other quality rows remain
  uncertain. Report SHA is `260625f302f3e268...`. Update 1 is the only 9-win
  frontier checkpoint and later updates collapse. V44 is rejected before
  confirmation; dev-v40 is retired unopened/unconsumed and held-out-v6 remains
  sealed. M8.5 is unmet.
- ADR-0062 precommits V45's residual-temporal actor. It preserves V43's exact
  current-state set path, separately encodes V44's 104 lag values, and adds
  zero-initialized temporal residual logits while leaving the critic unchanged.
  Config/umbrella hashes are `a7d0c8029acebe79...` /
  `e4fe0b56a95fa64c...`. Dev-v41 is reserved in `[9B,10B)` but unconstructed;
  dev-v40 remains retired without a read, held-out-v6 remains sealed, and no
  V45 model work has occurred.
- The V45 residual actor and pretraining boundary are green. Tests prove exact
  V43 base-path initialization, zero temporal outputs, controlled lag
  sensitivity, masks, shapes, and compatibility. The embargo-safe 273-test
  suite, pinned Java, public 5/5 with ten staging starts, both focused checks,
  smoke, deterministic golden/negative replay, and all 44 reward adversaries
  pass (SHA `84cd359cf9cbd401...`). The 43 legacy scenario-variation tests remain
  last green before dev-v40 freeze and are not rerun because they glob-read
  retired membership. Dev-v41 is unconstructed and no V45 training has run.
- The primary-only dev-v41 freezer is implemented using commit-bound reviewed
  atomic/no-read primitives plus exact V45 validation and namespace proof. The
  embargo-safe suite passes 277 tests. It has not executed and dev-v41 remains
  unconstructed; the freezer must first be committed.
- The committed freezer constructed dev-v41 without emitting or reading seed
  values. Membership/receipt hashes are `591513526bdd0bce...` /
  `d2d14a281d37a046...`; the receipt records zero membership-document reads.
  Dev-v41 is frozen and unconsumed.
- Two exact V45 replicas select update 32 at 10/10 reusable wins, mean return
  `7.67784`, core `730.1`, and idle `0.00873637`. Checkpoint/full-run/lineage
  prefixes are `cdc526403cd1fe27...` / `f253cd6dbb1c0f5c...` /
  `5c1ca3fc7ab9c49f...`. Fresh permanent random/greedy are 4/10 and 8/10;
  matched random/greedy are 5/10 and 6/10. Every observed win gate passes.
- Both reusable scorecards reject V45 on uncertainty: permanent announcements
  mean `-0.00986813`, CI `[-0.02822874,+0.00206376]`; permanent idle mean
  `-0.00698418`, CI `[-0.02004098,+0.01159603]`; matched recovery mean `-31.9`,
  CI `[-89.70125,+18.10125]`. Report SHA is `ea7466a45d91d415...`.
  Root 2004's 65 WAIT actions are all forced after the only legal defense
  action, which agrees with the teacher; the selector cannot act at those
  boundaries. V45 is rejected before confirmation. Dev-v41 is retired
  unopened/unconsumed without a read; held-out-v6 remains sealed/unconsumed.
  No evidence-backed V46 coordinate is authorized.
- Scenario-variation governance no longer glob-reads every seed membership.
  Its disjointness loops enumerate only explicit legacy/public memberships
  (fixed/train, dev-v1..v33, held-out-v1..v4); governed replacement sets are
  checked through value-free receipts and existence only. All 44 focused tests
  and the complete embargo-safe Python suite pass (322 tests) without reading
  dev-v34..v41 or held-out-v5/v6 membership.
- With explicit owner authorization to expand learned control, ADR-0063
  precommits V46's bounded `DEFER_TO_SCRIPTED_EXPERT` policy action. It
  translates to the already-computed canonical adaptive-v1 seat-0 action,
  cannot override forced safety/lifecycle decisions, and is unavailable for
  expert WAIT. V45's ten ordinary logits/critic stay exact; a same-boundary
  expert-action input and zero-initialized DEFER head are appended. Teacher
  losses stay on actions 0..9 and promotion caps mean DEFER at 25%.
- V46 config/umbrella hashes are `b588ee43e66bd9d...` /
  `a78631d7ba9f1cd2...`. Dev-v42 is reserved value-free in `[10B,11B)` but
  unconstructed. Implementation and the full public/pretraining boundary must
  be committed before membership construction or training. Dev-v41 remains
  retired unopened; held-out-v6 remains sealed.
- The V46 implementation and full pretraining boundary are green. Feature v3,
  control v2, and model v5 preserve V45's ten ordinary actor logits, masked
  logits, and critic bit-exactly at initialization while adding a separately
  encoded zero-output DEFER head. Translation stays policy-side and submits the
  already-computed canonical structured expert action; forced, single-action,
  and expert-WAIT boundaries cannot defer. History records the effective
  ordinary action, teacher CE remains actions 0..9, and validated telemetry
  enforces the inclusive 25% cap at checkpoint, reusable, confirmation, and
  final gates.
- Thirteen focused V46 tests and all 335 embargo-safe Python tests pass. Pinned
  Java/custom modules, public 5/5 survival with ten staging starts, secondary
  claim wake, owned-schematic staging, smoke, the 79-boundary deterministic
  replay, 664-checkpoint/16,200-tick golden plus negative mutation check, and
  all 44 exact-config reward adversaries pass. The adversary report SHA-256 is
  `ec3acb4c1056207a1f83729cb62e5c38042164c5688e67c18c6d842d96a54b9e`.
  Dev-v42 remains unconstructed; no V46 training/checkpoint or restricted
  membership read has occurred.
- The primary-only dev-v42 freezer is implemented and unexecuted. It pins the
  V46 implementation/config/umbrella commits, validates the exclusive
  `[10B,11B)` namespace without reading prior membership, and records a
  value-free receipt. The embargo-safe suite now passes 339 tests. The freezer
  must be committed before it may construct membership.
- The committed freezer constructed dev-v42 without displaying or reading its
  membership. The value-free receipt binds membership
  `8f518384f19c193f...`, generator `e9a828a7d01ed7e9...`, and implementation
  `173cd5c2a11f3237...`, and records zero membership-document reads. Dev-v42 is
  frozen and unconsumed pending both exact replicas and all reusable
  scorecard/control gates. The receipt-aware embargo-safe suite passes 340
  tests.
- Two pinned V46 replicas reproduce update 32 exactly at 10/10 public-dev wins,
  mean return `7.22016`, core `639.2`, idle `0.01033305`, and mean DEFER
  `0.18420177`. Checkpoint/model/replay/full-run prefixes are
  `93694e4d70ec56e4...` / `70c762f358ae8cce...` /
  `493ab925a384ccec...` / `8d61abfa4ce4fe10...`.
- Direct-lineage construction failed closed before output because its expected
  schema omitted the new control coordinate. The validator now explicitly
  binds control v2; focused and full suites pass 341 tests. No reusable,
  confirmation, or held-out episode has run.
- Direct lineage is canonical at `b6322349e4d14b31...`. Fresh reusable
  permanent random/greedy baselines are 4/10 and 8/10, matched random/greedy
  are 5/10 and 6/10, and V46 wins 10/10. Its mean DEFER `0.18420177` passes the
  25% cap.
- Both reusable scorecards reject V46 on uncertainty. Permanent announcements
  mean `-0.00135566`, CI `[-0.00779035,+0.00535807]`; permanent idle mean
  `-0.00538749`, CI `[-0.01753561,+0.01213167]`; matched recovery mean `-18.0`,
  CI `[-82.11,+39.75125]`. Report SHA is `2af00337138b9939...`. V46 is rejected
  before confirmation; dev-v42 is retired unopened/unconsumed and held-out-v6
  remains sealed.
- A reusable-only V46 no-DEFER ablation remains 10/10 and produces essentially
  the same three uncertain rows (report `109d0bd5ef8ca177...`), so another
  small control-head change is not evidence-backed. With explicit owner
  authorization, ADR-0064 precommits a statistical-power correction: the exact
  confidence rule stays frozen, while one canonical reusable screen uses 160
  public roots in `[11B,12B)`. The V46 checkpoint is frozen; no retraining or
  reselection is allowed. Replacement confirmation dev-v43 is reserved in
  `[12B,13B)` but cannot be constructed unless all reusable-v2 gates pass.
  Dev-v42 stays retired unopened and held-out-v6 stays sealed.
- The ADR-0064 packet was committed at `26d25acd64` before construction. The
  deterministic generator then froze 160 public reusable-v2 roots with
  membership SHA `c529951782ec0426...`; its receipt records zero restricted
  membership reads and zero evaluation episodes. The set is frozen and
  unevaluated pending this data/evidence commit.
- Reusable-v2 rejects V46 with substantially higher power. Permanent
  random/greedy win 62/160 and 84/160; V46 wins 96/160 and matched
  random/greedy win 69/160 and 67/160. V46's mean DEFER `0.22788814` passes,
  and every matched scorecard passes. Permanent announcements remain
  indistinguishable (`-0.00016845`, CI
  `[-0.00413065,+0.00377476]`) while idle is unfavorable
  (`+0.00391218`, CI `[-0.00166438,+0.00971554]`). Report SHA is
  `d272edd51197166b...`. Dev-v43 is not constructed; dev-v42 stays retired and
  held-out-v6 stays sealed.

## What is stubbed (compiles/imports, no real behaviour)

- **`agent-core`**: real, compilable, unit-tested types — `TaskType` (16),
  `CoordinationAct` (13), `SkillStatus` (6), `AgentId` record, the coordination
  board (M2), the **`agentcore.skill`** FSM layer (M3/M4), and the engine-free
  deterministic M5.1 candidate catalog. Board-to-skill wiring and measurable
  helper fulfilment, live reservations, lease recovery, announcements, and
  metrics are wired through M5.6; the shared M7.2 expert uses that surface.
  M8.4 selector rewards/training and the complete M8.5 lineage/dev/one-way-final
  machinery are implemented. V1, V8, and V9 failed promotion; their consumed
  held-out gates cannot be rerun. Held-out-v6 remains sealed and unconsumed.
- **`agent-plugin`** is no longer a stub. Its scripted M6 path and queued M10
  human goal/assignment/autonomy/quiet surface plus human build-plan and recent-
  construction reservation/yield are implemented; study instrumentation remains
  unimplemented.
  `docs/M10_DESIGN.md` and ADR-0057 accept the structured command contract and
  make demo adoption of the public candidate/typed-action path a prerequisite.
  `AgentRuntimeRegistry` now removes the candidate/coordination adapters'
  concrete dependency on `RlAgentRegistry`. `DemoAgentRegistry` implements the
  seam and owns real-time spawn/rebind. The engine-neutral Java
  `GreedyUtilityPolicy` fallback is implemented and tested over public
  candidates/masks, including deterministic ties, replan throttling, wave
  preemption, and combat supply/defense preference. The default real-time
  runtime now uses `EngineCandidates`, masks,
  typed actions, `CoordinationAdapter`, board, reservations, and skills end to
  end; an earlier stock-clock probe reached readiness at tick 5664 after
  wave-damage recovery and one rebind (89 accepted selections). These real-time
  counts are diagnostic, not a deterministic parity baseline. The public-path
  stock-clock survival gate is now green through tick 8100 with core health
  1100; structured world-state telemetry records three wave clears, both
  expansion schematics at 8/10 turrets, both maintenance completions, and
  reserve mining. Exact public-path parity is also green: a probe-only JSON trace
  replays 390 real candidate/mask boundaries and 1,170 Java actions through the
  Python fallback without drift; two fresh JVMs reproduce 225 accepted
  selections and digest `aaf2e734ea384fe4b537cbdf3bd5342fb5e954f3432a91470ebce311fa503714`.
  A persistent combat logistics seat reduces seven repeated abandon/reclaim
  cycles to two phase-entry rebalances plus seven unassigned waits.
  Probe engine delta, pathfinding, entity iteration, and physics/global RNG are
  deterministic; stock survival remains real-time. All public-path prerequisite
  gates and the default promotion are green. `DEMO_PUBLIC_POLICY=0` keeps the
  shared driver as an explicit regression oracle. The engine-free M10.1
  `HumanControl` parser/state packet is implemented and focused-tested: strict
  commands produce canonical structured intent, while ordered bounded goals,
  assignments, autonomy/quiet settings, deterministic ids/revisions, stable
  rejection reasons, and reset are simulation-thread state. Candidate overlay
  core is now implemented with explicit task provenance: the engine-free
  resolver wraps only already-valid structured ordinary candidates, reserves
  bounded slots in goal order, preserves WAIT, and returns the exact original
  candidate set for empty control. Autonomous canonical bytes, observation
  fields, and hashes omit provenance and remain unchanged. Engine matching,
  assignment masks, and queued plugin application are now live on the public
  path. Callbacks enqueue only and simulation-thread application emits stable
  structured results. `DEMO_HUMAN_CONTROL=1` passes at tick 2189 after
  completing assigned `human:goal:1` BUILD_LINE, observing assigned LOW and
  stable-id-reassigned LOW plus advisory HIGH defense tasks, applying 16/16
  commands, cancelling all goals, restoring NORMAL, and suppressing four
  nonurgent messages. The probe also converts an engine build plan into exact
  tile and rules-scaled resource reservations, yields/clears the overlapping
  agent once, protects completed construction for 600 ticks, and resumes the
  stable goal after expiry. M10.1 and M10.2 are complete. Exact no-command
  parity remains 390/1,170/225 with digest `aaf2e734...714`; stock survival
  remains tick 8100 at 1100 health. M10.3's local opt-in capture substrate is
  now implemented: `CREATE_NEW` UTF-8 JSONL includes pinned session metadata,
  the same public candidate/mask/action/result trajectories, applied human
  controls with queued/applied ticks, authoritative coordination events plus
  render status, and human presence changes. A terminal count/SHA-256 is
  validated by a dependency-free loader that deterministically replays control
  state and derives pace/role/plan-change statistics. The no-port capture gate
  produced 504 records (84 trajectory boundaries, 16/16 controls, four presence
  changes, and one human-yield event). Its historical v1 content SHA-256 is
  `3e864f35ffc3cf3c...`; the control-schedule SHA-256 remains
  `d30d529355b07ce1...`. Capture v3 added project-commit and canonical plugin/
  server runtime-content hashes; current v4 retains them and adds authoritative
  agent/experiment condition metadata, with legacy-v1/v2/v3 loader
  compatibility. V2's
  whole-server-JAR hashes changed across committed builds (`7cee94a1...` /
  `489bbb68...`); per-entry diagnosis found only volatile generated
  `version.properties`. V3 normalizes only its comment/`buildDate` while hashing
  stable version fields and every other entry byte. Two fresh JVMs at committed
  implementation `c19e652324` reproduce
  session content `7a2c68e638e9fff3...`, plugin content `faca436f81b865bd...`,
  server content `e02c4208749ee2ed...`, and the unchanged control schedule
  exactly. Five executable scripted
  partner profiles are versioned in
  `configs/partners/human-scripted-v1.json`; they remain staged, not active in
  training, because M8 has not authorized M9.
  M10.4's objective scorecard substrate is also implemented. It derives human
  intervention rate, plan conflicts, yield latency, goal compliance,
  time-to-help, and announcement counts from authoritative capture records.
  An opted-in private join now checks both create-new artifact targets before
  opening the server, then validates the completed capture and writes a sibling
  `.scorecard.unrated.json` after a normal exit. The same postprocessor is used
  by the deterministic no-port gate.
  Optional usefulness/preference/comparison/serious-session judgments require a
  separate human-entered schema-v1 rating whose session digest must match; the
  dependency-free rating command now obtains that digest from a validated
  capture and writes only the exact four-answer schema with create-new
  semantics. Unknown/free-text/identity fields are rejected. The no-port gate
  deliberately reports
  `rating_status=not_provided`, with 5/83 intervention ticks, one conflict at
  zero-tick yield latency, 1/1 eligible goal compliance, and 10 rendered/four
  suppressed announcements. No human preference result is claimed.
  ADR-0058 and the dependency-free evidence report now govern exploratory multi-session
  aggregation: duplicate digests fail, exact engine/Arc/protocol/scenario/policy
  pins define comparable groups, and only serious ratings count toward the
  minimum-three-session floor. That report deliberately keeps acceptance
  `not_evaluated` because rating v1 does not measure paired agents-present
  versus agents-absent preference. Legacy v1/v2
  sessions are excluded from the provenance-complete floor; v3 groups require
  exact project-commit and canonical runtime-content identity. ADR-0059 now
  separately freezes final acceptance before any result exists: three
  Latin-square blocks each pair absent, scripted, and learned conditions on one
  trial seed; capture v4 binds condition/order/seed at session start; every
  objective scorecard mean must non-regress against scripted; and direct owner
  preference must favor learned over absent. `bash
  scripts/human-absent-check.sh` passes through the real server/plugin with zero
  controlled units, five trajectory boundaries, a valid capture, and no
  network port. The learned condition remains unavailable until M8 promotion
  and M10.5, so no final block has begun and no M10 exit checkbox is closed.
- **Python subpackages** `process`, `env`, `policies`, and `tools` now carry real M1/M2/M5 code
  (`process/{launcher,supervisor}.py`, `env/{client,parallel_env,vector}.py`,
  `tools/{smoke,determinism,stress_reset,benchmark,policy_check,
  shared_policy_check}.py` plus the reservation/chaos/announcement checks).
  `evaluation` now contains the real dependency-free M6 summaries and M7.6
  ladder/bootstrap machinery. `training` contains the M8.3 throughput gate and
  M8.4 feature/tensor adapter, audited reward, model, PPO optimizer,
  checkpoint/replay, manifest path, mixed-seat ablations, reproducible
  checkpoint interpolation, dev preflight, and one-way final gate; `telemetry`
  now contains the M10.3 human-session validator, replay, summaries, and staged
  scripted partner-model contract.
- **`scenarios/bootstrap-defense-v0/`**: **fully loaded** by `rl-server` (world,
  ore, waves, termination, objective IDs/targets/thresholds, named regions, and
  reference schematic), plus the delayed-loadout adaptive probe. M5.1 turns
  those objectives plus live world state into
  scored candidates; M5.2 claims and executes them; M5.3 supplies deterministic
  task-level policy baselines. The winning primary expert is now the M7.3
  greedy candidate policy; the M6 macro remains a frozen baseline. Scenario v2
  adds bounded seed-resolved variation and the M7.4 probe remains explicit.
- **`configs/`**: the M7.5 train/dev/held-out-v1 seed sets, M7.6 fixed seed set,
  and ADR-0013 held-out-v2 successor are active governance artifacts; unrelated
  example training YAML remains unused.
- **Project CI is hosted-run verified.** The SHA-pinned Ubuntu 24.04 workflow
  installs both hash-locked Python environments, runs `make test`, and builds
  the custom distributions. The first complete green hosted run is
  [29972868046](https://github.com/Smellybum1/Mindustry-Agent/actions/runs/29972868046)
  at commit `6b4afc4d3f`; bootstrap, dependency installation, all 287 Python
  tests, Java suites/custom-module compilation, and distribution builds passed
  in 2m37s. The first attempted run correctly exposed and led to repair of a
  clean-checkout test that had required ignored local V41 diagnostics.

## What is unverified

- **`rl-server` Java build/run is verified** (`./gradlew rl-server:dist` green;
  jar boots headlessly and passes smoke + determinism + stress-reset). **`agent-core`
  build + JUnit suite are now verified** (`./gradlew agent-core:test` → 108 tests
  green, including 31 M3/M4 skill tests). `agent-plugin:dist` and its isolated
  real-server acceptance probe are verified.
- **RL lock is verified** for Linux CPython 3.12 CPU; core remains dependency
  free. Native Windows training, CUDA, and other Python/platform locks are not
  certified and require an explicit later decision.
- **Human demo acceptance:** stock v159.7 join, visual/chat observation, all
  three waves, and in-client emergency stop are verified.

## Known deviations from the brief

See the end of `HANDOFF.md`. In summary: `protocol/` is intentionally **not** a
Gradle module (JSON bootstrap lives in `docs/PROTOCOL.md` + `protocol.py`, per
ADR-0004); the Makefile carries the full brief §33 target surface, with unbuilt
targets failing loudly.
