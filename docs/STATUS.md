# Status

**Date:** 2026-07-21
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
  client, parallel-env facade, vector collector) is stdlib-only too. **55 Python
  tests pass** via `python -m pytest python/tests -q` (verified 2026-07-21 with
  pytest 8.4.2 on Python 3.12.5).
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
- Server and client commands cover `agents status|pause|resume|stop`; stop clears
  velocity, mining, build plans, firing, and active skills on the simulation
  thread. Team chat receives only rate-limiter-approved structured events. Join
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
  set is frozen for one confirmation after dev-v1. V9 has not been constructed.

## What is stubbed (compiles/imports, no real behaviour)

- **`agent-core`**: real, compilable, unit-tested types — `TaskType` (16),
  `CoordinationAct` (13), `SkillStatus` (6), `AgentId` record, the coordination
  board (M2), the **`agentcore.skill`** FSM layer (M3/M4), and the engine-free
  deterministic M5.1 candidate catalog. Board-to-skill wiring and measurable
  helper fulfilment, live reservations, lease recovery, announcements, and
  metrics are wired through M5.6; the shared M7.2 expert uses that surface.
  M8.4 selector rewards/training and the complete M8.5 lineage/dev/one-way-final
  machinery are implemented. The v1 candidate failed promotion; the consumed
  held-out gate cannot be rerun.
- **`agent-plugin`** is no longer a stub. Its scripted M6 path is implemented;
  future M10 human goals/overrides and study instrumentation remain outside M6.
- **Python subpackages** `process`, `env`, `policies`, and `tools` now carry real M1/M2/M5 code
  (`process/{launcher,supervisor}.py`, `env/{client,parallel_env,vector}.py`,
  `tools/{smoke,determinism,stress_reset,benchmark,policy_check,
  shared_policy_check}.py` plus the reservation/chaos/announcement checks).
  `evaluation` now contains the real dependency-free M6 summaries and M7.6
  ladder/bootstrap machinery. `training` contains the M8.3 throughput gate and
  M8.4 feature/tensor adapter, audited reward, model, PPO optimizer,
  checkpoint/replay, manifest path, mixed-seat ablations, reproducible
  checkpoint interpolation, dev preflight, and one-way final gate; `telemetry`
  remains a documented
  skeleton.
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

## What is unverified

- **`rl-server` Java build/run is verified** (`./gradlew rl-server:dist` green;
  jar boots headlessly and passes smoke + determinism + stress-reset). **`agent-core`
  build + JUnit suite are now verified** (`./gradlew agent-core:test` → 108 tests
  green, including 31 M3/M4 skill tests). `agent-plugin:dist` and its isolated
  real-server acceptance probe are verified.
- **No CI** configured yet.
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
