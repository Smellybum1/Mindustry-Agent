# Handoff

Codex-ready handoff per brief §27. Kept truthful; `TODO` marks pending info.

## Project state

- **What currently works** (M0–M6, M7.1–M7.6, and M8.1–M8.4 complete, verified
  2026-07-21): the
  fixed-step headless `rl-server` (reset/step/hash over loopback JSON, smoke +
  determinism + 1000-reset stress all green), the `agent-core` coordination
  board, deterministic candidate catalog, **and the M3/M4 `agentcore.skill` FSM
  layer** (108 JUnit tests), agent
  entities + skills in the exact engine (`RlAgentRegistry`, `SkillController`,
  `ActionDecoder`; agents mine copper and deliver it to the core with an exact
  balance ledger), the Python env/process layer (supervisor pool with
  crash-replacement, PettingZoo-shaped facade, vector collector; 92 pytest
  green), benchmarks recorded in `docs/BENCHMARKS.md`, and — new — the **full
  `bootstrap-defense-v0` world loaded from `scenario.json`** (48×48, ore patches,
  east spawn, 250-copper loadout, deterministic 3-wave dagger schedule at
  2700/4500/6300 with moving enemies, win/loss/truncate termination). Enemy pathing
  is deterministic via the one sanctioned upstream patch, `Pathfinder.syncUpdate()`
  (`docs/UPSTREAM_PATCHES.md`). The **seed lever is now real**: different seeds
  diverge once enemies spawn, same seed stays identical. M4.1 also neutralizes
  the tile-change `Time.millis()` refresh gate in thread-less mode; a wall placed
  after wave 1 produces identical re-pathing hashes across fresh JVMs. M4.2 adds
  legal `BUILD`: real `BuildPlan` execution, exact core resource consumption,
  and typed failure telemetry. M4.3 adds data-backed `SCHEMATIC`: the ordered
  `east_duo_v1` build completes through those legal plans for exactly 100 copper.
  M4.4 legally supplies both Duos for a balanced 30-copper core delta and 30 ammo
  units each; the full trace matches 79 boundaries. M4.5 rebuilds an engine-recorded
  wave-destroyed wall for an exact second six-copper charge. M4.6 adds deterministic
  alpha defense, agent-attributed damage events, and plan-cancelling core retreat
  (95 JUnit tests total); combat is present in the 79-boundary replay. M4.7 closes
  plan/progress/turret observations and hashes ordered build plans, broken queues,
  and turret ammo. M4.8 proves the one-agent defended wave-1 path with an untouched
  core and retains the matched omitted-defense loss regression.
  M5.1 parses the scored scenario objectives into a bounded, byte-stable per-agent
  candidate catalog; engine-backed utility features and aligned capability/range
  masks are live in reset/step observations. Smoke covers build/supply/defend
  candidate transitions.
  M5.2 hosts a reset-safe board on the sim thread, accepts typed task actions,
  maps claimed scenario tasks to legal skills, publishes bounded snapshots and
  drained structured events, and hashes non-empty board state. Its three-agent
  live check repeats byte-identically across two fresh JVMs through tick 280.
  M5.3 adds dependency-free greedy and fixed-role task policies plus deterministic
  helper coordination. Its live check records distinct miner/builder work, a
  real resources-short block, an accepted 20-copper helper contract fulfilled by
  21 legally mined/delivered copper, and one schematic completion; the full trace
  repeats byte-identically across fresh JVMs through tick 912.
  M5.4 acquires exact schematic-footprint and copper reservations before skill
  start, hashes and publishes them, cancels interrupted build queues, and releases
  on every lifecycle exit. Its live overlap trace gives the higher-utility second
  bidder the only build plan, emits `reservation_overlap` for the loser, proves
  abandon/reclaim/completion and supply budgets, and repeats byte-identically
  through tick 280.
  M5.5 adds a deterministic, validation-only failed-agent hook. The live chaos
  run freezes agent 0 mid-build, expires its lease and reservations at tick 627,
  lets agent 1 reclaim/complete at tick 893, reaches a normal terminal outcome,
  and repeats byte-identically through tick 3600.
  M5.6 renders human-readable announcements exclusively from structured events,
  exposes cumulative duplicate/completion/abandonment/idle/message metrics, and
  keeps routine traffic silent. Its live helper episode emits 112 structured
  events but only four announcements, suppresses the same-tick accept line, and
  repeats the entire event/metric transcript byte-identically across fresh JVMs.
  M6.1 adds the real two-drill copper line and a three-agent expert that wins
  all three waves on the five-seed set. Final core health is
  848/884/1001/920/983; the legal insufficient-copper variant emits a structured
  block, replans through mining, and also wins.
  M6.2 writes pinned JSONL episode summaries and aggregates the same five seeds:
  5/5 wins, minimum/mean core health 848/927.2, with full figures in BENCHMARKS.
  M6.3 checks in a complete two-episode/16,200-tick action+coordination golden;
  after the deliberate M7.1 regeneration, fresh-JVM replay matches 672
  checkpoints and the negative mutation test flips one.
  M6.4 builds a loadable stock-server plugin. Its isolated real-server probe
  legally completes the shared copper-line/east-Duo opening, expands it to 20
  fortifications/four supplied Duos, matches both build orders, enters reserve
  mining, and verifies pause/resume/emergency-stop without opening a port. The
  separate no-port survival probe adds two Duos/seven walls after waves 1–2,
  supplies all six/eight turrets, clears three waves, and reaches tick 8100 with
  1091 core health. A stock v159.7 client observed the full run and confirmed
  `/agents stop` halted all three active tasks. M7.1 resolves the independent
  review's mechanical findings: scenario-owned coordinates/timing feed both
  demos, candidate overflow is utility-ranked with a DEFEND reservation,
  transport episode IDs are deterministic, duplicated skill constants and dead
  demo branches are removed, supply stock telemetry has explicit consumers, and
  the upstream patch catalogue is exact. The current no-port survival probe
  reaches tick 8100 with 1100 core health after dynamic 9-block/2-turret
  expansions following waves 1 and 2. M7.2 replaces the two scripted policy
  implementations with one engine-neutral `ExpertCoordinationDriver` and
  scenario-derived plan. The fixed-step adapter and plugin now share staging,
  lifecycle, wave response, maintenance, expansion, and reserve-mining
  decisions; the plugin retains only real-time/engine/IO adaptation and
  controls. The recorded parity probe covers 366 decisions/89 selections and
  all six task types, while the two live openings both emit 33 selections with
  digest `f335f6b950ac1b58857ca84b40e7151f966d5d53408fd0e643fbc54a39671385`.
  The post-extraction survival run clears waves at ticks 3102/4865/6655 and
  reaches tick 8100 with 1091/1100 core health. M7.3 promotes the public
  candidate/utility seam to the primary expert: `GreedyUtilityPolicy` submits
  normal task actions over live candidates/masks, the former `ExpertEpisode`
  macro is frozen for the ladder, and structured resource blocks now trigger
  abandon/regenerate/reselection. Scenario-derived fortification/expansion
  candidates and the shared enriched plan produce 5/5 wins at tick 8100
  (minimum/mean core health 1082/1096.4); the legal pre-spend variant wins with
  209 health and seven replans. Genuine wave-clear/message/loss/health
  variation follows seeded enemy spread. `docs/CANDIDATE_GAPS.md` records the
  remaining rigidity. Updated shared fixed-step/plugin openings still match:
  43 selections and digest
  `157134ba5a4e3f39ccc3cf237093481dc8474b7edd1d20e16b274ec338b1a6c2`.
  The final stock-paced no-port probe reaches the six-turret opening at tick
  1814, completes eight-/ten-turret expansions, clears waves at ticks
  3015/4799/6606, and ends tick 8100 with 1100/1100 core health. Recurring task
  identity intentionally changes coordination hashes; the separately
  regenerated golden retains two wins, 16,200 ticks, and 672 checkpoints, with
  exact replay and a passing negative mutation check.
  M7.4 replaces the remaining fixed planning constants with authoritative
  economy/defense/spatial facts. The real line predicate requires directed
  drill-to-core connectivity and a full 600-tick window at 0.6 copper/s; wave
  HP/DPS and native Duo values derive readiness, ammo target, and defend lead.
  Opt-in event-driven steps wake on task/economy/wave/core-damage transitions,
  while default stepping remains exact. Typed BLOCKED replans are bounded and
  recent assignments feed switching cost. The delayed-loadout adaptive probe
  is won at tick 8100 (line 1794, defense-ready 1382), while the frozen macro
  cannot complete its opening and loses. Across fixed+probe, adaptive mean idle
  fraction is 0.125 vs 0.878 and censored defense-ready tick is 817 vs 5251.
  `make adaptive-planning-check`, fixed 5/5 evaluation, and the legal
  resource-pressure replan win are green. The M7.4 golden retains two wins and
  16,200 ticks across 670 checkpoints, with exact replay and a passing negative
  mutation. All REVIEW_M6 findings are resolved.
  M7.5 adds `bootstrap-defense-v1` / scenario version 2: bounded independently
  seeded ore positions, loadout, wave timing/composition, and an optional upper
  lane. Resolved contracts are validated, published, and hashed. ADR-0012
  freezes disjoint train/dev/held-out sets and development tools refuse held-out
  execution. Repeated/fresh-JVM reset and idle-through-wave traces match per
  seed; v2 waves receive deterministic disjoint entity-ID ranges so prior
  episode allocation history cannot leak through native spawning. Adaptive-v1 wins
  8/10 on the frozen dev set; seeds 2005/2007 expose the retained fixed-anchor
  upper-lane fortification gap. No held-out episode has been run.
  M7.6 adds the permanent five-policy evaluation ladder, a versioned fixed seed
  contract, deterministic 10,000-resample bootstrap intervals, and a per-episode
  teammate scorecard derived from structured events and existing metrics. The
  certified one-JVM Windows path writes byte-repeatable 65-episode JSONL plus
  aggregates in 39.6 seconds after the same per-seed idle trace used by M7.5.
  Adaptive-v1 is 5/5 fixed and 8/10 dev; pure
  greedy is 5/5 fixed and 9/10 dev. These are descriptive only: ADR-0012 now
  requires strict held-out win-rate CI separation, and held-out remains sealed.
  M8.1 is design-only and complete: `docs/M8_DESIGN.md` pins the one-seat
  selector tensors/masks/model/cadence/manifests/promotion protocol, while
  `docs/REWARD_AUDIT.md` drafts five hard-gated components with 15 exploit
  hypotheses and eight cross-component adversaries. M8.2 accepts ADR-0011 and
  pins the RL-only Linux CPU runtime to NumPy 2.4.2, PettingZoo 1.26.1, and
  PyTorch 2.12.1+cpu. Its 15-package hashed lock regenerates byte-identically;
  the WSL2 acceptance gate passed 33 `python -S` core tests and a temporary
  locked import/device probe on CPython 3.12.3. No reward or learned policy is
  implemented. M8.3 carries decision-event stepping through the supervised
  vector collector and adds a training-only shadow-inference gate. Its
  certified WSL2 result is 122.4×/212.7×/293.5× aggregate real-time at 1/2/4
  JVMs, with identical winning hashes. The same command passed 10,000 resets
  with zero drift, 338.3 MiB peak RSS, and no orphan.
- **M8.4 evidence**: the exact one-seat selector seam is implemented with
  framework-neutral 8x37/56 features, five separately audited reward
  components, masked feed-forward PPO, chained checkpoints,
  training/replay JSONL, and complete run manifests. All 27 reward adversaries
  pass. Two independent pinned runs match checkpoint `0b2bd8ac904a9e21...`,
  complete replay `87ba273f376c47de...`, full-run digest
  `56cc7b54bc9b01b5...`, and dev action/state aggregate
  `52aecddf4c96bab6...`. The selected checkpoint is 0/10 on dev and is not
  promotable; held-out remains sealed. Current final capacity is 375.1x at four
  JVMs and 10,000 resets with zero drift/no leak/no orphan. The golden is 664
  checkpoints over 16,200 ticks and two wins.
- **M8.5 final**: base and auxiliary parent pairs reproduce exactly; two 75/25
  constructions match checkpoint `4fdad5cbd8476a8f...` and lineage
  `995cb7d71fa21e4e...`. Frozen dev preflight passed at 9/10. The exclusive
  held-out final then completed once and returned `not_promoted`: learned 4/10
  `[0.1,0.7]`, random-valid 6/10 `[0.3,0.9]`, greedy-utility 6/10 `[0.3,0.9]`,
  matched greedy 1/10 `[0.0,0.3]`. Permanent CI separation failed, and idle /
  abandonment regressed versus permanent greedy. The attempt marker forbids a
  rerun; held-out outcomes must not be used for policy revision.
- **What is stubbed**: the M10 human goal/override/study surface remains future
  work. M8.5 evaluation machinery is real, but the candidate did not promote.
- **What remains for M6**: nothing. The closure matrix and 15-item audit are
  recorded, and the closure commit is tagged `milestone-6`.
- **Post-failure governance**: ADR-0013 freezes the 40-root, globally disjoint
  `bootstrap-defense-v1-held-out-v2` contract before any successor model work.
  Development loaders refuse it and only one exclusive future final is
  permitted. `m8-selector-v3-diverse` tested 64 train roots at the unchanged
  512-episode budget and reproduced exactly, but selected update 1 at only 3/10
  dev wins (`e9e1ee37fbfef6ee...`). It stops before preflight and v2 remains
  unopened. M9.1 remains blocked by its explicit promotion prerequisite.
- **Teacher-regularized successor**: v4 reproduced exactly and improved the
  diverse-root dev result to 5/10, but remains ineligible. V5 changes only the
  teacher coefficient from 0.05 to 0.10 and is precommitted as the final test;
  it reproduced exactly but fell to 3/10, closing that line. V2 is unopened.
- **Long diverse successor**: v6 is precommitted as auxiliary-free v3 with only
  cycles raised from 8 to 32 (2,048 episodes/32 updates), restoring 32 visits
  per root. Two pinned runs reproduce exactly and select update 31 at 9/10 dev
  wins (`0dfdcf9b5273ae3f...`, full-run `54476ef63e31e06d...`). Direct-checkpoint
  lineage is implemented; full dev scorecard preflight is next. V2 is unopened.
- **V6 dev preflight**: all four win-rate comparisons pass, but idle, recovery,
  and abandonment intervals are uncertain on ten dev-v1 pairs. ADR-0014 freezes
  a one-way 40-root dev-v2 confirmation with an exclusive attempt and refreshed
  permanent baselines. It must pass before held-out-v2 can be opened.
- **V6 confirmation result**: the exclusive marker was created, then the run
  aborted before result files on a matched-control catalog-WAIT indexing bug.
  ADR-0014 consumes any started attempt, so V6 is rejected and dev-v2 must not
  be rerun. The bug is fixed/regression-tested. Held-out-v2 remains unopened.
- **V7 precommit**: ADR-0015 freezes a 90/10 V6 update-31 / V4 update-5 blend,
  with explicit cross-commit parent validation. Dev-v3 is a new disjoint
  40-root, one-way confirmation set available only after V7 passes dev-v1. Its
  result follows; dev-v2 remains consumed and held-out-v2 sealed.
- **V7 result**: exact constructions; dev-v3 finishes 35/40 versus permanent
  greedy 30/40. Recovery, abandonment, announcements, and duplicates pass;
  idle remains favorable but uncertain. V7 is rejected and dev-v3 consumed.
- **V8 precommit**: ADR-0016 freezes a single `-0.25` WAIT-logit bias adjustment
  to V7, with masks/reward/lifecycle unchanged. Dev-v4 is a new disjoint
  40-root, one-way confirmation set. Its result follows.
- **V8 final**: exact checkpoint `1f3c4525fb5fd10d...`; dev-v4 fully eligible
  at 37/40. Held-out-v2 completes once at V8 36/40, random 19/40, greedy 23/40,
  matched greedy 5/40. Win gates pass, but permanent-greedy idle/abandonment
  regress and other scorecards remain uncertain. V8 is not promoted; v2 is
  consumed and individual outcomes must not guide future policy changes.
- **Post-V8 governance**: ADR-0017 freezes 80 disjoint held-out-v3 roots before
  further model work. A successor must name v3 and use a new confirmation path.
- **V9 precommit**: ADR-0018 freezes one additional `-0.25` WAIT-bias child of
  V8 (`-0.50` total from V7), with all other behavior fixed. It names
  held-out-v3. Dev-v5 is a new disjoint 80-root, one-way confirmation set. V9
  has not yet been constructed.
- **What is broken**: nothing known.
- **Current branch**: `coop-agent/v159.7`
- **Current commit**: see `git rev-parse HEAD` (this scaffold is committed in
  several small commits; the pre-existing HEAD was `c9686eb5`).
- **Engine tag/commit**: `v159.7` / `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`;
  Arc `208a754044`.
- **Uncommitted changes intentionally preserved**: the user's modified
  `AGENTS.md` and generated
  `annotations/src/main/resources/classids.properties`. Neither belongs to the
  project commits; never stage the generated file.

## Exact commands

| Command | Expected output |
|---|---|
| `make bootstrap` | Prints ENGINE_VERSION, Java/Python/Git versions, Gradle wrapper presence, pytest presence; ends `bootstrap: OK`, exit 0. |
| `make build` | Builds `rl-server:dist` + the loadable `agent-plugin:dist`, then validates the Python package import; ends `build: OK`, exit 0. |
| `make test` | Runs the Python suite (92 pass). Use `make test-java` for the JUnit suite. Exit 0. |
| `make test-python` | `pytest python/tests -q` → all pass. |
| `make verify-rl-boundary` | On Linux/WSL2 with uv 0.11.16 and Python 3.12, runs 33 core tests under `python -S`, reconstructs the 15-package hashed CPU environment in a temporary directory, and ends `RL-BOUNDARY OK`. Verified 2026-07-21. |
| `make training-gate` | On WSL2 with pinned `UV`/`JAVA`, reconstructs the RL environment, runs the 1/2/4-JVM shadow-inference collector gate, then 10,000 resets. Current 4-JVM result 375.1x real-time; zero reset drift/leak/orphans; ends `TRAINING-GATE OK`. Verified 2026-07-21. |
| `bash scripts/train-selector.sh` | Runs 27 reward adversaries, two independent train/dev PPO runs, two complete fresh-checkpoint replays, and exact manifest comparison. Current checkpoint `0b2bd8ac...`, full digest `56cc7b54...`, dev 0/10; ends `TRAIN-SELECTOR OK`. Held-out is not read. |
| `make test-java` | Runs the `agent-core` (108 tests) and `rl-server` JUnit suites plus the `agent-plugin` compile check; ends `test-java: OK`, exit 0. Verified 2026-07-21. |
| `make smoke` | Runs exact stepping + M3/M4 ledgers/combat/acceptance and M5.2–5.6 coordination/policy/reservation/chaos/announcement checks twice across fresh JVMs, plus omitted-defense loss checks. Ends `SCENARIO OK`, exit 0. Verified 2026-07-21. |
| `make determinism` | Runs the legacy 79-boundary cross-process replay, reset purity with deterministic unique episode IDs, seed sensitivity, then the checked-in golden (664 checkpoints / 16,200 ticks / two wins). Exit 0. Verified 2026-07-21; `REPLAY_NEGATIVE=1` also passes. |
| `make candidate-policy-check` | Runs the pure public greedy selector over all five pinned seeds; requires 5/5 wins through the ordinary candidate/mask/task-action seam. Verified 2026-07-21. |
| `make coordination-parity` | Compares two complete recorded decision sequences, runs the fixed-step shared expert, then boots the no-port plugin and requires identical live-opening digest/count. Current result: 356 recorded decisions; live digest `1571…a6c2`, 43 selections. Verified 2026-07-21. |
| `make adaptive-planning-check` | Runs adaptive-v1 and frozen M6 on fixed+delayed-loadout scenarios. Requires adaptive 2/2 wins, fixed frozen win, probe frozen loss, all four decision-event reasons, lower mean idle fraction (0.125 < 0.878), and lower defense-ready tick (817 < 5251). Verified 2026-07-21. |
| `make scenario-variation-check` | Validates all scenario-v2 axes, disjoint seed governance, same-seed repeated/fresh-JVM reset and idle-through-wave hashes, frozen-dev adaptive survival, and an undefended v2 pathing/loss run. Current result: 8/10 wins (80%); held-out sets are refused. Verified 2026-07-21. |
| `make evaluate-ladder` | Runs 65 fixed/dev episodes across five versioned baselines, writes episode JSONL plus deterministic bootstrap aggregates, and leaves held-out sealed. Current adaptive-v1 result is 2/5 fixed and 9/10 dev. Verified 2026-07-21. |
| `make stress-reset` | Boots one persistent JVM, resets 1000× (same seed) with no restart; latest M7.1 run: zero hash mismatches, median 1.31 ms, p95 2.60 ms, peak 298.3 MiB, no leak; ends `STRESS-RESET OK`, exit 0. Verified 2026-07-20. |
| `make benchmark` | Measures single-env engine ticks/sec + reset latency, protocol overhead, and 1/2/4-JVM aggregate scaling; prints a markdown report; ends `BENCHMARK OK`, exit 0. ~5 s of stepping + JVM boots, well under 10 min. Verified 2026-07-20. |
| `make scripted-demo` | Runs adaptive-v1 and the legal post-reservation resource-pressure fixture; both end at tick 8100, and the fixture records a real `resources_short_replan`. Verified 2026-07-21. |
| `make evaluate-scripted` | Runs five pinned fixed seeds and writes `runs/scripted-evaluation.jsonl`; current M7.4 result is 5/5 wins, min/mean core health 200/572.6. Verified 2026-07-21. |
| `make demo-server` | Builds/boots the real server+plugin in an isolated no-port probe; verifies layout, full expert preparation, reserve mining, announcements, and controls; exits 0. `DEMO_SURVIVAL=1` clears three waves and reaches tick 8100 with 1100/1100 core health without opening a port. Use `DEMO_JOIN=1` only for an explicit private port-6567 human session. |

(If `make` is unavailable on Windows, run `bash scripts/<name>.sh` directly.)

## Architecture map

- **Key modules**: `rl-server` (headless fixed-step launcher, `mindustry.rl`),
  `agent-core` (`agentcore`), `agent-plugin` (loadable real-time server adapter,
  `mindustry.agentplugin`); Python
  `mindustry_agents` package. See `docs/ARCHITECTURE.md`.
- **Python env/process layer (M2)** — the request path top to bottom:
  `env.parallel_env.MindustryParallelEnv` (per-agent dict PettingZoo surface,
  duck-typed, no pettingzoo import) → `env.client.EnvClient` (one connection,
  episode/tick bookkeeping, tuple returns) → `process.launcher.Connection`
  (length-prefixed JSON socket) → one JVM. `process.supervisor.ProcessSupervisor`
  owns a pool of these (ports, seeds, per-child `runs/` stderr logs, handshake
  verification, crash/hang detection + auto-replacement, atexit/context-manager
  shutdown); `env.vector.VectorCollector` steps the whole pool in lockstep. All
  stdlib-only (ADR-0007). The JVM is mocked in unit tests by
  `python/tests/fake_server.py` (a subprocess speaking the real protocol).
- **Important classes/functions**: `mindustry.rl.RlServer` (fixed-step launcher +
  control loop; see `FixedStepApplication`, `FixedStepGraphics`, `StateHasher`,
  and `Scenario` — the JSON-driven world/waves/termination loader — in
  `rl-server/src/main/java/mindustry/rl/`);
  `agentcore.board.TaskBoard` + `agentcore.{task,reservation,event,announce,utility}`
  (see `docs/COORDINATION.md`);
  `mindustry_agents.protocol.{encode,decode,decode_stream,read_message}`;
  `mindustry_agents.process.launcher` (JVM supervisor, tracks spawned PID only).
- **Protocol entry points**: `docs/PROTOCOL.md` (spec v1);
  `python/src/mindustry_agents/protocol.py` (reference impl); Java side in
  `mindustry.rl` (length-prefixed JSON, byte-compatible — verified by smoke).
- **Simulation thread rules**: only the sim thread reads/mutates game state; I/O
  threads parse+queue (`docs/ARCHITECTURE.md` threading rule).
- **Reset path**: `RlServer` reset handler — `Logic.reset()` plus the gaps it
  leaves (reseed `Mathf.rand`, reset `EntityGroup.lastId`, zero `Time` incl.
  `globalTimeRaw`, pathfinder threads stopped); in-process, no JVM restart,
  ~4 ms median. See `docs/ENGINE_NOTES.md`.
- **Step path**: queued request → sim thread applies action bundle → exactly N
  fixed-delta engine updates → observation + SHA-256 canonical hash.
- **Observation path**: built on the sim thread at the step boundary (M1 minimal:
  tick/wave/core items/counts/health; per-agent observations are M3).
- **Task/skill path**: `agentcore` owns the board and engine-free skills;
  `agentcore.coordination.ExpertCoordinationDriver` owns the shared scripted
  policy and lifecycle. `mindustry.rl.CoordinationAdapter` owns the per-episode
  board, validates external task actions, optionally adapts that driver for
  parity evaluation, maps task types to M3/M4 skills, and reports lifecycle/
  events/snapshots. `SkillController` and `RlAgentRegistry` remain the engine
  ports; `ActionDecoder` retains the legacy direct-command path.

## Current performance

- **Machine information**: AMD Ryzen 7 9800X3D (8C/16T), 61.6 GB RAM, Windows 11,
  Temurin 21.0.11, Python 3.12.5.
- **Single-environment ticks/sec**: ~76,000 engine-only (~1,270× real-time);
  ~54,000 end-to-end through the Python client.
- **Reset latency**: median ~0.8 ms over 1000 resets (p95 ~1.5 ms) for the M1/M2
  minimal world; **~1.07 ms median (p95 2.11 ms, max 44.94 ms warmup) for the full
  bootstrap-defense-v0 world** (bigger map + wave/flowfield preload) — Gate 2
  (<250 ms) still passes with a huge margin; no JVM restart, no stale state.
- **Memory per JVM**: peak working set ~285 MiB over 1000 resets with `-Xmx350m`
  (well under the 650 MiB leak ceiling); no per-reset leak. Within-cap RSS growth
  is lazy heap sizing, not a leak — run-to-run growth varies (+0.2% to +24%),
  which is why the leak check uses an absolute ceiling, not a growth trend.
- **Scaling table**: 1 JVM ~42k, 2 JVMs ~66k (~79%), 4 JVMs ~89k (~53%) aggregate
  ticks/sec. Near-linear to 2; capped at 4 on this shared host. Full table +
  caveats in `docs/BENCHMARKS.md` (M2 measurements).
- **Known bottleneck**: at 4 JVMs the per-step engine time (<1 ms for a 60-tick
  chunk) is smaller than the `VectorCollector`'s GIL-bound JSON encode/decode, so
  the Python side — not the engine — limits aggregate throughput. Larger step
  chunks or a process-based collector would scale further (future work).

## Tests

- **Passing**: 92 Python tests (`test_import.py`, `test_protocol.py` incl. M3–M7.6
  action/board/event roundtrips, `test_supervisor.py`, `test_env.py`; fake-server
  subprocess, no JVM, fast) and 108 Java JUnit tests (`agent-core`, incl.
  31 M3/M4 `agentcore.skill` FSM tests, via `make test-java`). Real-JVM coverage is
  the shell scripts (smoke/determinism/stress-reset/benchmark) — smoke includes
  the M5.2–M5.6 live coordination checks and determinism the scripted skill
  trace; all verified green 2026-07-21. M7.2 additionally has the recorded and
  live-runtime `coordination-parity` gate. M7.3 adds five-seed public
  `candidate-policy-check`; M7.4 adds real predicate, event-boundary,
  generalized blocked-replan, and adaptive-vs-frozen probe coverage. M7.5 adds
  cross-JVM variant-reset, sealed-set refusal, and frozen-dev survival coverage.
  M7.6 adds deterministic policy/scorecard/bootstrap unit coverage and the live
  65-episode ladder. M8 adds deterministic PPO/replay coverage plus the dev-only
  promotion comparator and paired-scorecard gates.
- **Skipped**: none.
- **Flaky**: the stress-reset *leak* check was flaky under the original
  growth-trend methodology (passed for the author, failed on re-verification);
  fixed by switching to a capped-heap absolute-ceiling check. Hash stability was
  never flaky.
- **Failing**: none.
- **Golden hashes**: the live harness and checked-in two-episode golden both
  pass; 670 checkpoints cover 16,200 ticks and two wins. M7.4 regenerated the
  trace because the hash now includes adaptive rolling facts and switching
  history; frozen macro outcomes and length did not change, and the negative
  mutation still diverges.

## Known risks and bugs

- **The seed lever is now exercised (resolved)**: with enemy waves live, different
  `root_seed`s diverge once wave 1 spawns (the native `WaveSpawner` spread is seeded
  from `root_seed`), while the same seed stays bit-identical across processes and
  resets. Proven by `tools/determinism.py` check 4. Pre-wave state is still
  seed-independent (nothing consumes `root_seed` before tick 2700) — expected.
- **Dynamic re-path determinism is resolved (M4.1)**: the thread-less
  `Pathfinder.syncUpdate()` path consumes pending tile changes immediately without
  the normal-mode wall-clock gate. `tools/determinism.py` places a copper wall at
  tick 2760 and matches all 79 hashes across fresh JVMs while daggers continue
  around it. M4.2 removed the temporary hook; the trace now uses legal `BUILD`
  and verifies the six-copper wall ledger.
- **4-JVM scaling is Python-bound** (~53% efficiency): GIL-bound JSON in the
  collector, not the engine. Fine for now; revisit before large-scale training
  (larger tick chunks or process-based collection).
- **Protocol overhead** is ~22% of a 60-tick step wall-time (engine is just
  <1 ms/chunk); Gate 6 (<10%) passes only at larger action-repeat. Honest
  status in `docs/BENCHMARKS.md`; revisit alongside ADR-0004's Protobuf trigger.
- See `docs/decisions/` and brief §29 for the standing risk register.

## Next five issues

**Authoritative work queue: `docs/ROADMAP.md` M8 item 8.5.
Handoff prompt for the next agent:
`docs/CODEX_HANDOFF_PROMPT.md`.** The summary below mirrors the head of that
queue.

1. **Choose the next M8 candidate from train/dev evidence only.** ADR-0013 and
   held-out-v2 are frozen; the candidate config must name v2 before training.
   Never inspect or tune against individual held-out-v1 outcomes.
2. **M8.5 remains unmet.** The v1 one-seat selector was not promoted and its
   held-out attempt cannot be rerun.
3. **M9.1 remains gated.** The roadmap says to begin only after the single
   learned seat promotes; do not silently bypass that prerequisite.
4. **M9.2 partner population** remains behind M9.1.
5. **M9.3 communication ablation** remains behind M9.2.

## Decisions

See `docs/decisions/ADR-0001..0018` (do not relitigate).

## Deviations from the brief in this scaffold

- `protocol/` is **not** a Gradle module. Per ADR-0004 the bootstrap transport is
  JSON; the schema lives in `docs/PROTOCOL.md` and `protocol.py`. Protobuf +
  generated bindings are deferred to Stage D. This avoids dead scaffolding.
- The brief's separate `tests/{determinism,integration}/` directory split is not
  used; real-JVM checks live behind `scripts/*.sh`. `tests/golden/` now contains
  the checked-in complete M6 replay trace.
