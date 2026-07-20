# Handoff

Codex-ready handoff per brief §27. Kept truthful; `TODO` marks pending info.

## Project state

- **What currently works** (M0–M5 and M6.1–6.3 complete, verified 2026-07-20): the
  fixed-step headless `rl-server` (reset/step/hash over loopback JSON, smoke +
  determinism + 1000-reset stress all green), the `agent-core` coordination
  board, deterministic candidate catalog, **and the M3/M4 `agentcore.skill` FSM
  layer** (101 JUnit tests), agent
  entities + skills in the exact engine (`RlAgentRegistry`, `SkillController`,
  `ActionDecoder`; agents mine copper and deliver it to the core with an exact
  balance ledger), the Python env/process layer (supervisor pool with
  crash-replacement, PettingZoo-shaped facade, vector collector; 36 pytest
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
  fresh-JVM replay matches 678 checkpoints and the negative mutation test flips one.
- **What is stubbed**: `agent-plugin` (placeholder for the M6/M10 demo server);
  a scripted full three-wave *win* path and evaluation/golden replay work remain
  in M6; rewards are empty until M7;
  training/evaluation Python subpackages. See `docs/STATUS.md`.
- **What is broken**: nothing known.
- **Current branch**: `coop-agent/v159.7`
- **Current commit**: see `git rev-parse HEAD` (this scaffold is committed in
  several small commits; the pre-existing HEAD was `c9686eb5`).
- **Engine tag/commit**: `v159.7` / `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`;
  Arc `208a754044`.
- **Uncommitted changes**: aim for none. Note: the background Gradle build
  touched `annotations/src/main/resources/classids.properties` (a generated
  file); that change is **not** part of this scaffold and was left unstaged.

## Exact commands

| Command | Expected output |
|---|---|
| `make bootstrap` | Prints ENGINE_VERSION, Java/Python/Git versions, Gradle wrapper presence, pytest presence; ends `bootstrap: OK`, exit 0. |
| `make build` | Builds `rl-server:dist` + `agent-core`/`agent-plugin` classes, then validates the Python package import; ends `build: OK`, exit 0. |
| `make test` | Runs the Python suite (38 pass). Use `make test-java` for the JUnit suite. Exit 0. |
| `make test-python` | `pytest python/tests -q` → all pass. |
| `make test-java` | `gradlew agent-core:test` (101 tests) + compile checks for `rl-server`/`agent-plugin`; ends `test-java: OK`, exit 0. Verified 2026-07-20. |
| `make smoke` | Runs exact stepping + M3/M4 ledgers/combat/acceptance and M5.2–5.6 coordination/policy/reservation/chaos/announcement checks twice across fresh JVMs, plus omitted-defense loss checks. Ends `SCENARIO OK`, exit 0. Verified 2026-07-20. |
| `make determinism` | Runs the legacy 79-boundary cross-process replay, reset purity, seed sensitivity, then the checked-in M6 golden (678 checkpoints / 16,200 ticks / two wins). Exit 0. Verified 2026-07-20. |
| `make stress-reset` | Boots one persistent JVM, resets 1000× (same seed) with no restart; all 1000 initial hashes identical, reset latency median/p95/max reported, leak check = peak RSS under `Xmx(350m) + 300 MiB` ceiling. Latest post-M5.6 run: median 1.08 ms, p95 2.35 ms, peak 300.1 MiB, no leak; ends `STRESS-RESET OK`, exit 0. Verified 2026-07-20. |
| `make benchmark` | Measures single-env engine ticks/sec + reset latency, protocol overhead, and 1/2/4-JVM aggregate scaling; prints a markdown report; ends `BENCHMARK OK`, exit 0. ~5 s of stepping + JVM boots, well under 10 min. Verified 2026-07-20. |
| `make scripted-demo` | Runs the primary three-wave expert and the legal insufficient-copper replan variant; both end at tick 8100 with `outcome=win`. Verified 2026-07-20. |
| `make evaluate-scripted` | Runs five pinned seeds, writes `runs/scripted-evaluation.jsonl`, and prints the M6 aggregate table; 5/5 wins. Verified 2026-07-20. |
| `make demo-server` | **Exits 1** — not implemented (M6/M10). |

(If `make` is unavailable on Windows, run `bash scripts/<name>.sh` directly.)

## Architecture map

- **Key modules**: `rl-server` (headless fixed-step launcher, `mindustry.rl`),
  `agent-core` (`agentcore`), `agent-plugin` (`mindustry.agentplugin`); Python
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
  `mindustry.rl.CoordinationAdapter` owns the per-episode board, validates task
  actions, resolves bundle-wide claims, maps task types to M3/M4 skills, and
  reports lifecycle/events/snapshots. `SkillController` and `RlAgentRegistry`
  remain the engine ports; `ActionDecoder` retains the legacy direct-command path.

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

- **Passing**: 35 Python tests (`test_import.py`, `test_protocol.py` incl. M3–M5
  action/board/event roundtrips, `test_supervisor.py`, `test_env.py`; fake-server
  subprocess, no JVM, fast) and 101 Java JUnit tests (`agent-core`, incl.
  31 M3/M4 `agentcore.skill` FSM tests, via `make test-java`). Real-JVM coverage is
  the shell scripts (smoke/determinism/stress-reset/benchmark) — smoke includes
  the M5.2–M5.6 live coordination checks and determinism the scripted skill
  trace; all verified green 2026-07-20.
- **Skipped**: none.
- **Flaky**: the stress-reset *leak* check was flaky under the original
  growth-trend methodology (passed for the author, failed on re-verification);
  fixed by switching to a capped-heap absolute-ceiling check. Hash stability was
  never flaky.
- **Failing**: none.
- **Golden hashes**: determinism harness compares live runs; checked-in golden
  trace files are still TODO (see next issues).

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

**Authoritative work queue: `docs/ROADMAP.md` M6 item 6.4, then M6 closure.
Handoff prompt for the next agent:
`docs/CODEX_HANDOFF_PROMPT.md`.** The summary below mirrors the head of that
queue.

1. **M6.4: agent-plugin demo server.** Run the same board/skills/policy in an
   ordinary human-joinable v159.7 dedicated server with emergency-stop commands.
2. **M6.5: milestone closure.** Run the full acceptance matrix, update truthful
   docs/benchmarks, and close M6 only when every exit criterion passes.
3. **M7.1: learned selector baseline contract.** Begin only after M6 closure.
4. **M7.2: PPO selector implementation.** Remains unauthorized until M7 begins.
5. **M7.3: checkpoint/evaluation pipeline.** Remains unauthorized until M7.

## Decisions

See `docs/decisions/ADR-0001..0010` (do not relitigate).

## Deviations from the brief in this scaffold

- `protocol/` is **not** a Gradle module. Per ADR-0004 the bootstrap transport is
  JSON; the schema lives in `docs/PROTOCOL.md` and `protocol.py`. Protobuf +
  generated bindings are deferred to Stage D. This avoids dead scaffolding.
- `tests/{determinism,integration,golden}/` from the brief tree are not created
  yet; golden trace files are next-issue 2.
