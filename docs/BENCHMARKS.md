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
| 1. Deterministic stepping | Identical hash ≥10,000 ticks; exact tick advance; no wall-clock dep | — | not measured |
| 2. Reset | <250 ms reset, no JVM restart, no stale state | <100 ms | not measured |
| 3. Single-env speed | ≥10× real-time on small scenario | ≥30× | not measured |
| 4. Aggregate parallel | Stable scaling 1/2/4/8/16 JVMs; ≥100× aggregate | more | not measured |
| 5. Long-run stability | ≥10,000 resets / overnight; no leak, no orphans, no hash drift | — | not measured |
| 6. Protocol overhead | serialization+transport < ~10% of step time | — | not measured |

Do not proceed to expensive RL training until the relevant gates pass.
