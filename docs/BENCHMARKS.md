# Benchmarks

Templates below; fill as milestones produce runnable harnesses. Do not optimize
from intuition — keep benchmark scripts and results here (brief §24). Target
rows are project *targets*, not current claims; the M1 section records actual
observed numbers.

## M1 spike — observed (2026-07-20)

| Field | Value |
|---|---|
| Machine | AMD Ryzen 7 9800X3D (8C/16T), 61.6 GB RAM, Windows 11 |
| JDK | Temurin/OpenJDK 21.0.11 (compiled `--release 17`) |
| Engine / Arc | v159.7 / c9686eb5… / 208a754044 |
| Scenario | in-code 48×48 flat + copper patch + 1 Sharded core, no waves |

| Metric | Observed | Conditions |
|---|---|---|
| Engine-only stepping | **~32,700 ticks/sec** (~545× real-time @60 tps) | single 3,000-tick step, warm JVM; `engine_ms` only |
| 600-tick smoke (10×60) | ~20 ms engine total, ~30,500 ticks/sec | first chunk ~4.7 ms (JIT warmup), then ~1.2–2.3 ms/chunk |
| Observation capture | ~0.1 ms/step | M1 observation + SHA-256 hash |
| Reset latency | **~3.8 ms median** (min 3.2, max 5.8) | client-observed incl. socket RTT; warm JVM; Gate 2 target <250 ms |
| Cold boot (content init → READY) | ~11–13 s | one-time per JVM |

Measured via `scripts/smoke.sh` / `scripts/determinism.sh` and the launcher.
These are rough single-run numbers on an otherwise-loaded workstation, not a
controlled benchmark; treat them as order-of-magnitude. Determinism verified:
two fresh JVMs and two in-JVM resets produce byte-identical state hashes.

## M2 measurements — observed (2026-07-20)

Produced by `bash scripts/benchmark.sh` (single-env speed, protocol overhead,
1/2/4-JVM scaling) and `bash scripts/stress-reset.sh` (1000 resets). Numbers are
single-run on an otherwise-loaded shared workstation — order-of-magnitude, not a
controlled benchmark; they vary run to run.

| Field | Value |
|---|---|
| Machine | AMD Ryzen 7 9800X3D (8C/16T), 61.6 GB RAM, Windows 11 |
| JDK | Temurin/OpenJDK 21.0.11 (compiled `--release 17`) |
| Python | 3.12.5 |
| Engine / Arc | v159.7 / c9686eb5… / 208a754044 |
| Scenario | in-code 48×48 flat + copper patch + 1 Sharded core, no waves |

### Single-env (layers 1 / 4 / 7)

| Metric | Observed | Notes |
|---|---|---|
| Engine-only stepping | **~76,000 ticks/sec** (~1,270× real-time @60 tps) | warm JVM, 100×60-tick chunks, `engine_ms` only |
| Python-wrapper (end-to-end, 1 env) | **~54,000 ticks/sec** | full client round-trip incl. socket + JSON |
| Reset latency (benchmark, warm) | median **2.1 ms**, max 5.1 ms | client-observed incl. socket RTT |
| Reset latency (stress, 1000×) | median **0.84 ms**, p95 **1.52 ms**, max 33.7 ms (first) | Gate 2 target <250 ms — **PASS** |

### Protocol overhead (layers 5 + 6)

| Metric | Observed | Notes |
|---|---|---|
| Round-trip minus engine+obs | **~0.25 ms/step** | fixed per-step Python + socket + JSON cost |
| Overhead as % of round-trip | **~22%** (of a 60-tick step) | see note below |

The absolute overhead is tiny (~0.25 ms). Expressed as a *percentage* it is large
here only because a 60-tick chunk is ~0.8 ms of engine work, so the fixed cost is
a big fraction of a small round-trip. The step granularity is a knob: at larger
action-repeat (e.g. 600-tick steps, as training will use) engine time dominates
and overhead falls well under Gate 6's ~10% line. Recorded honestly: Gate 6 is
**conditional on step size** — met at large steps, not at 60-tick steps.

### Scaling — aggregate ticks/sec (layer 9)

| JVMs | Aggregate ticks/sec | Per-JVM ticks/sec | Efficiency |
|---|---|---|---|
| 1 | ~42,000 | ~42,000 | 100% |
| 2 | ~66,000 | ~33,000 | ~79% |
| 4 | ~89,000 | ~22,000 | ~53% |

Scaling to 2 JVMs is near-linear; at 4 JVMs aggregate throughput keeps rising but
per-JVM efficiency drops to ~50%. Root cause is *not* the engine: with 60-tick
chunks each engine step is <1 ms, so the `VectorCollector`'s Python-side work
(JSON encode/decode is GIL-bound; only the socket wait releases the GIL) becomes
the bottleneck when four worlds finish near-simultaneously. Larger step chunks or
a process-based collector would scale further; both are future work. The pool is
**capped at 4 JVMs on purpose** — this is a shared workstation running other
unrelated agent projects, so the benchmark leaves CPU headroom rather than
saturating all 16 threads.

### Leak / stability (Gate 5, partial)

`stress-reset.sh` runs **1000 in-JVM resets, same seed, one persistent JVM**:
all 1000 initial `state_hash` values were byte-identical (0 mismatches) across
three independent runs. Memory: no per-reset leak — peak RSS ~285 MiB over 1000
resets under `-Xmx350m`, far below the 650 MiB leak ceiling (`Xmx + 300 MiB`
allowance). Methodology note: the original growth-trend check proved flaky
(+0.2% on one run, +24% on a re-verification run of the identical workload under
`-Xmx512m` — lazy heap expansion timing, not a leak), so the tool now uses the
absolute-ceiling check under a capped heap. The full Gate 5 (≥10,000 resets /
overnight) is not yet run.

## Environment (record for every run)

| Field | Value |
|---|---|
| Date | TODO |
| Machine (CPU / cores / RAM / OS) | TODO |
| JDK | TODO (dev: Temurin 21) |
| Engine tag / commit / Arc | v159.7 / c9686eb5… / 208a754044 |
| Scenario / version | bootstrap-defense-v0 / 1 |
| Protocol version | 1 |

## Benchmark layers (brief §24, "Benchmark method")

Measure each layer separately; do not conflate them.

| # | Layer | Metric | Result |
|---|---|---|---|
| 1 | Empty engine tick | ticks/sec | TODO |
| 2 | Scenario tick without agents | ticks/sec | TODO |
| 3 | Scripted skills | ticks/sec | TODO |
| 4 | Observation extraction | ms/step, ticks/sec | TODO |
| 5 | Serialization | ms/step | TODO |
| 6 | Socket transport | ms/step | TODO |
| 7 | Python wrapper | ticks/sec | TODO |
| 8 | Neural inference | ms/decision | TODO |
| 9 | Full collector | env-steps/sec aggregate | TODO |

## Performance gates (brief §24)

| Gate | Target | Stretch | Status |
|---|---|---|---|
| 1. Deterministic stepping | Identical hash ≥10,000 ticks; exact tick advance; no wall-clock dep | — | **PASS** (M7.1 golden: 16,200 ticks / 672 checkpoints across two complete expert episodes; legacy 79-boundary replay also passes) |
| 2. Reset | <250 ms reset, no JVM restart, no stale state | <100 ms | **PASS** (median ~0.8 ms over 1000 resets, no restart) |
| 3. Single-env speed | ≥10× real-time on small scenario | ≥30× | **PASS** (engine ~1,270× real-time; wrapper ~900×) |
| 4. Aggregate parallel | Stable scaling 1/2/4/8/16 JVMs; ≥100× aggregate | more | partial (1/2/4 measured, near-linear to 2; capped at 4 on this shared host) |
| 5. Long-run stability | ≥10,000 resets / overnight; no leak, no orphans, no hash drift | — | partial (1000 resets: no leak, no orphans, no drift; ≥10,000 pending) |
| 6. Protocol overhead | serialization+transport < ~10% of step time | — | conditional (~0.25 ms/step; <10% at large step sizes, ~22% at 60-tick steps) |

Do not proceed to expensive RL training until the relevant gates pass.

## M6 scripted expert evaluation (2026-07-20)

Command: `make evaluate-scripted` (equivalently
`bash scripts/evaluate-scripted.sh`). The evaluator uses one persistent JVM,
the pinned `scripted-expert-v1` policy, three agents, scenario version 1, and
writes `runs/scripted-evaluation.jsonl`. Copper in/out totals below are honest
net changes at deterministic external step boundaries; they are not claimed as
per-engine-operation accounting.

| seed | outcome | core hp | first drill | line complete | turrets built | supplied | units lost | messages |
|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| 12345 | win | 848 | 15 | 40 | 250 | 1082 | 0 | 158 / 5 |
| 23456 | win | 884 | 15 | 40 | 250 | 1082 | 0 | 158 / 5 |
| 34567 | win | 1001 | 15 | 40 | 250 | 1082 | 0 | 158 / 5 |
| 45678 | win | 920 | 15 | 40 | 250 | 1082 | 1 | 158 / 5 |
| 987666666 | win | 983 | 15 | 40 | 250 | 1082 | 1 | 158 / 5 |

Aggregate: **5/5 wins**, minimum final core health **848**, mean **927.2**,
two agent losses, 790 structured messages and 25 rendered announcements. The
primary seed reports boundary-observed copper 250 start / 21 final / 272 peak /
1 minimum, with 219 total positive and 448 total negative boundary deltas.

## M6 real-server demo acceptance (2026-07-20)

Command: `make demo-server` (equivalently `bash scripts/demo-server.sh`). This is
an acceptance probe, not a throughput benchmark. It builds `server:dist` and the
official-layout plugin, boots them from an isolated data directory, and opens no
network port. The verified run loaded one plugin, spawned three agents, completed
the copper-line and east-Duo plans, expanded them to 20 fortifications/four
Duos, supplied all four, entered continuous reserve mining at approximately
real-time server tick 1060, matched both checked-in block orders, and proved
pause/resume/emergency-stop before exiting 0. Wall time was about 22 seconds
including the incremental Gradle build and about 16 seconds in the server.

`DEMO_SURVIVAL=1 make demo-server` is the no-port real-time survival acceptance.
The final 2026-07-20 run entered reserve mining at tick 1072; after wave 1 it
built a nine-block layer and grew from four to six supplied Duos, then repeated
that expansion after wave 2 for eight supplied Duos and 14 new walls total.
Waves cleared at ticks 3074/4864/6659 and the run reached tick 8100 with
**1091/1100** core health. Stable slots lost in combat were rebound with
explicit `AGENT-DEMO REBOUND` telemetry.

The human path is intentionally separate: `DEMO_JOIN=1 make demo-server` opens
port 6567 only after an explicit request and waits for a stock v159.7 client.
A stock client joined locally, resumed the policy, visually observed the
mining/building/supplying/chat behavior through all three waves, then issued
`/agents stop`; the log showed all three active tasks abandoned immediately.

## M7.1 consolidation revalidation (2026-07-20)

The expert now derives its wave/termination values, ore tiles, reference-turret
tiles, and defend/rebuild regions from the scenario metadata instead of copied
literals. This intentionally changed its defense action trace, so the two-seed
golden was regenerated in its own commit. Before and after are both two wins at
tick 8100 with 16,200 total ticks; the new trace has 672 checkpoints (previously
678), replays exactly, and still fails the deliberate one-line MINE mutation.
The smoke mine/deliver/build/schematic/supply/rebuild ledgers all remain exact.

Current five-seed evaluation:

| seed | outcome | core hp | first drill | line complete | turrets built | supplied | units lost | messages |
|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| 12345 | win | 803 | 15 | 40 | 250 | 1082 | 0 | 158 / 5 |
| 23456 | win | 875 | 15 | 40 | 250 | 1082 | 0 | 158 / 5 |
| 34567 | win | 803 | 15 | 40 | 250 | 1082 | 0 | 158 / 5 |
| 45678 | win | 974 | 15 | 40 | 250 | 1082 | 1 | 158 / 5 |
| 987666666 | win | 749 | 15 | 40 | 250 | 1082 | 1 | 158 / 5 |

Aggregate: **5/5 wins**, minimum/mean final core health **749/840.8**, two
agent losses. Relative to the M6 baseline, wins and unit losses are unchanged;
health is lower because the old magic defend anchor/radius was replaced by a
tactical hold point and radius derived from `east_lane`. This is recorded as a
baseline shift, not hidden as noise.

The reset-path revalidation completed 1,000 resets with zero hash mismatches,
1.31 ms median / 2.60 ms p95 latency, 298.3 MiB peak RSS, and no leak. The
real-server no-port probe reported the dynamic opening counts (20 blocks/four
turrets); its survival variant reported 9 blocks/two turrets for each expansion,
cleared all three waves, and reached tick 8100 with **1100/1100** core health.

## M7.2 decision-parity and survival acceptance (2026-07-21)

Command: `make coordination-parity` (equivalently
`bash scripts/coordination-parity.sh`). This is a behavioral acceptance gate,
not a throughput benchmark.

| Check | Observed result |
|---|---|
| Recorded snapshot parity | 90 snapshots, 366 decisions, 89 selections; two independent shared-driver runs matched exactly |
| Selected task coverage | `HARVEST_RESOURCE`, `BUILD_SCHEMATIC`, `BUILD_LINE`, `SUPPLY_TURRET`, `REPAIR_REGION`, `DEFEND_REGION` |
| Fixed-step live opening | 33 selections through tick 990 |
| No-port plugin live opening | 33 selections; expert ready/reserve mining at tick 1062 |
| Cross-runtime normalized digest | `f335f6b950ac1b58857ca84b40e7151f966d5d53408fd0e643fbc54a39671385` — exact match |

The normalized digest intentionally excludes tick values because fixed-step and
real-time pacing observe the same policy milestones at different engine ticks;
it includes decision kind, agent, task type, and target. The separate no-port
`DEMO_SURVIVAL=1 make demo-server` run after extraction built both nine-block/
two-turret expansion layers, cleared waves at ticks 3102/4865/6655, and reached
tick 8100 with **1091/1100** core health. No game port was opened.

## M7.3 public greedy-candidate evaluation (2026-07-21)

Commands: `make candidate-policy-check`, `make evaluate-scripted`, and
`make scripted-demo`. The primary runner uses public candidate observations,
masks, `SELECT_CANDIDATE_TASK`, board claims/reservations, and skills. The
frozen M6 macro is not used.

| seed | outcome | core hp | first drill | line | initial turrets | supplied | wave clears | lost | messages |
|---:|:---:|---:|---:|---:|---:|---:|:---|---:|---:|
| 12345 | win | 1100 | 37 | 62 | 250 | 1470 | 3000/4770/6630 | 2 | 3445/53 |
| 23456 | win | 1100 | 37 | 62 | 250 | 1470 | 2940/4770/6570 | 1 | 2644/56 |
| 34567 | win | 1100 | 37 | 62 | 250 | 1470 | 2970/4800/6600 | 3 | 1933/38 |
| 45678 | win | 1082 | 37 | 62 | 250 | 1470 | 2970/4770/6600 | 2 | 2605/51 |
| 987666666 | win | 1100 | 37 | 62 | 250 | 1470 | 2940/4770/6600 | 2 | 2441/42 |

Aggregate: **5/5 wins**, minimum/mean final core health **1082/1096.4**.
Pre-wave construction is intentionally identical because scenario version 1 is
seed-independent before tick 2700. Wave-clear timing, messages, losses, and core
health vary from native root-seeded spawn spread; the policy adds no random
branch. The legal 18-wall pre-spend variant also wins at tick 8100 with **209**
core health and **7** explicit resource replans.

The M7.3 plan enrichment changed the M7.2 parity baseline without weakening it:
the recorded probe now matches 90 snapshots, 356 decisions, and 42 selections;
fixed-step and plugin openings both make 43 selections with digest
`157134ba5a4e3f39ccc3cf237093481dc8474b7edd1d20e16b274ec338b1a6c2`.

The final stock-paced `DEMO_SURVIVAL=1 make demo-server` probe reached expert
readiness at tick 1814 with 22 fortification blocks/six supplied turrets,
completed the eight-/ten-turret expansions, cleared waves at ticks
3015/4799/6606, and finished tick 8100 with **1100/1100** core health. No game
port was opened.

Recurring/retry task identity now includes current board state, so its
coordination hashes intentionally differ from the prior checked-in trace. The
frozen macro remains two wins over 16,200 ticks and 672 checkpoints; the
separately regenerated golden replays exactly in a fresh JVM and the deliberate
one-line MINE mutation still diverges.

## M7.6 evaluation ladder and teammate scorecard (2026-07-21)

Command: `make evaluate-ladder` (equivalently
`bash scripts/evaluate-ladder.sh`). The certified Windows run starts a fresh
JVM for every policy/seed-set cell and runs one JVM at a time, below the shared
host's four-JVM ceiling. This avoids cross-policy reset history and host-load
effects. Every scored episode follows an unscored same-seed idle-through-wave-1
trace, matching M7.5's reset/action-trace precondition. The complete 65-episode
run took 39.6 seconds. A second certified run
produced byte-identical episode JSONL.

All intervals below are deterministic 95% percentile bootstrap intervals over
10,000 episode-level resamples. `help` is `n/a` in every cell because no ladder
policy requested help; the JSONL retains `null` plus request/fulfilment counts.
Recovery is also nullable when no qualifying agent-loss reassignment occurred.

| seed set | policy | wins | win rate 95% CI | core HP mean | idle | duplicates | announcements / transition | abandonment | recovery ticks |
|:---|:---|---:|:---|---:|---:|---:|---:|---:|---:|
| fixed | random-valid | 4/5 | 0.80 [0.40, 1.00] | 860.2 | 0.036 | 2.0 | 0.119 | 0.005 | 147.6 |
| fixed | greedy-utility | 5/5 | 1.00 [1.00, 1.00] | 763.4 | 0.049 | 6.2 | 0.126 | 0.000 | 193.9 |
| fixed | role-assignment | 4/5 | 0.80 [0.40, 1.00] | 836.8 | 0.073 | 19.2 | 0.095 | 0.016 | 224.6 |
| fixed | frozen-expert | 5/5 | 1.00 [1.00, 1.00] | 826.4 | 0.934 | 0.0 | 0.500 | 0.333 | n/a |
| fixed | adaptive-v1 | 5/5 | 1.00 [1.00, 1.00] | 572.6 | 0.063 | 9.6 | 0.141 | 0.111 | 91.0 |
| dev v1 | random-valid | 4/10 | 0.40 [0.10, 0.70] | 350.9 | 0.033 | 2.5 | 0.131 | 0.004 | 308.1 |
| dev v1 | greedy-utility | 9/10 | 0.90 [0.70, 1.00] | 715.5 | 0.037 | 5.4 | 0.135 | 0.000 | 160.6 |
| dev v1 | role-assignment | 7/10 | 0.70 [0.40, 1.00] | 568.4 | 0.039 | 15.6 | 0.079 | 0.009 | 152.1 |
| dev v1 | adaptive-v1 | 8/10 | 0.80 [0.50, 1.00] | 683.8 | 0.071 | 9.2 | 0.143 | 0.089 | 140.7 |

These fixed/dev results are descriptive. ADR-0012 requires strict held-out
win-rate CI separation from `greedy-utility` for promotion. No held-out episode
was run, so the aggregate correctly reports `promotion: not evaluated`.
