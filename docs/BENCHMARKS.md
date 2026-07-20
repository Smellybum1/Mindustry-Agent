# Benchmarks

**Status: no measurements yet.** Templates below; fill as milestones produce
runnable harnesses. Do not optimize from intuition — keep benchmark scripts and
results here (brief §24). Numbers are project *targets*, not current claims.

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
