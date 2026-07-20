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
| 1. Deterministic stepping | Identical hash ≥10,000 ticks; exact tick advance; no wall-clock dep | — | partial (M1: exact advance + reset purity proven; 1000 resets identical; seed lever inert until M3) |
| 2. Reset | <250 ms reset, no JVM restart, no stale state | <100 ms | **PASS** (median ~0.8 ms over 1000 resets, no restart) |
| 3. Single-env speed | ≥10× real-time on small scenario | ≥30× | **PASS** (engine ~1,270× real-time; wrapper ~900×) |
| 4. Aggregate parallel | Stable scaling 1/2/4/8/16 JVMs; ≥100× aggregate | more | partial (1/2/4 measured, near-linear to 2; capped at 4 on this shared host) |
| 5. Long-run stability | ≥10,000 resets / overnight; no leak, no orphans, no hash drift | — | partial (1000 resets: no leak, no orphans, no drift; ≥10,000 pending) |
| 6. Protocol overhead | serialization+transport < ~10% of step time | — | conditional (~0.25 ms/step; <10% at large step sizes, ~22% at 60-tick steps) |

Do not proceed to expensive RL training until the relevant gates pass.
