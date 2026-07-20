# Handoff

Codex-ready handoff per brief §27. Kept truthful; `TODO` marks pending info.

## Project state

- **What currently works**: repository scaffold, all project docs + ADRs, the
  zero-dependency Python core package with a tested JSON protocol implementation
  (13 tests pass), and a working `scripts/bootstrap.sh`.
- **What is stubbed**: `rl-server` (prints engine pin, exits 0), `agent-core`
  (real typed vocabularies + `AgentId`, JUnit test written), `agent-plugin`
  (placeholder), all Python feature subpackages, the first scenario, and configs.
  See `docs/STATUS.md` for the full breakdown.
- **What is broken**: nothing known; but the Java modules are **unbuilt/unverified**
  (Gradle was not run — a background engine build was active).
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
| `make build` | Validates the Python package imports; prints that the Java build is not wired into this target yet. (Java build is manual until M0/M1.) |
| `make test` | Runs Python tests (13 pass) and notes the Java test harness is pending. Exit 0. |
| `make test-python` | `pytest python/tests -q` → all pass. |
| `make test-java` | `gradlew agent-core:test` (64 tests) + compile checks for `rl-server`/`agent-plugin`; ends `test-java: OK`, exit 0. Verified 2026-07-20. |
| `make smoke` | Builds `rl-server.jar` if missing, launches one JVM, handshake + `reset(seed=12345)` + 10×60 ticks; prints transcript ending `SMOKE OK: tick advanced exactly 600`, exit 0. Verified 2026-07-20. |
| `make determinism` | Two fresh JVMs, same seed/schedule → identical hashes at every boundary; in-JVM reset purity check; ends `DETERMINISM OK`, exit 0. Verified 2026-07-20. |
| `make stress-reset` | Boots one persistent JVM, resets 1000× (same seed) with no restart; all 1000 initial hashes identical, reset latency median/p95/max reported, child RSS sampled for leaks (heap bounded via `-Xmx512m`); ends `STRESS-RESET OK`, exit 0. Verified 2026-07-20. |
| `make benchmark` | Measures single-env engine ticks/sec + reset latency, protocol overhead, and 1/2/4-JVM aggregate scaling; prints a markdown report; ends `BENCHMARK OK`, exit 0. ~5 s of stepping + JVM boots, well under 10 min. Verified 2026-07-20. |
| `make scripted-demo` | **Exits 1** — not implemented (M6). |
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
  `ScenarioLoader` in `rl-server/src/main/java/mindustry/rl/`);
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
- **Task/skill path**: `agentcore` contract board implemented (M5-ready);
  skill executors + engine adapter TODO (M3–M5).

## Current performance

- **Machine information**: AMD Ryzen 7 9800X3D (8C/16T), 61.6 GB RAM, Windows 11,
  Temurin 21.0.11, Python 3.12.5.
- **Single-environment ticks/sec**: ~76,000 engine-only (~1,270× real-time);
  ~54,000 end-to-end through the Python client.
- **Reset latency**: median ~0.8 ms over 1000 resets (p95 ~1.5 ms) — Gate 2
  (<250 ms) passes comfortably; no JVM restart, no stale state.
- **Memory per JVM**: working set ~325 MiB steady-state with `-Xmx512m`; no
  per-reset leak (tail growth +0.2% over 1000 resets). Uncapped RSS climbs then
  plateaus — that is lazy heap sizing, not a leak.
- **Scaling table**: 1 JVM ~42k, 2 JVMs ~66k (~79%), 4 JVMs ~89k (~53%) aggregate
  ticks/sec. Near-linear to 2; capped at 4 on this shared host. Full table +
  caveats in `docs/BENCHMARKS.md` (M2 measurements).
- **Known bottleneck**: at 4 JVMs the per-step engine time (<1 ms for a 60-tick
  chunk) is smaller than the `VectorCollector`'s GIL-bound JSON encode/decode, so
  the Python side — not the engine — limits aggregate throughput. Larger step
  chunks or a process-based collector would scale further (future work).

## Tests

- **Passing**: 26 Python tests (`test_import.py`, `test_protocol.py`,
  `test_supervisor.py`, `test_env.py`). The M2 tests use a fake-server subprocess
  (`fake_server.py`) — no JVM — so the suite stays fast; real-JVM coverage is the
  shell scripts (smoke/determinism/stress/benchmark).
- **Skipped**: none.
- **Flaky**: none known.
- **Failing**: none.
- **Not yet run**: `agent-core` `AgentCoreTypesTest` (JUnit; Gradle not invoked).
- **Golden hashes**: none yet (determinism harness is M1).

## Known risks and bugs

- Java modules are unbuilt; a `build.gradle` idiom mismatch could surface on the
  first `./gradlew rl-server:dist agent-core:build agent-plugin:build`.
  Reproduction: run that command when no background Gradle build is active.
- The `--release 17` + JDK 21 combination is inherited from the root build and
  expected to work, but is unverified for the new modules.
- See `docs/decisions/` and brief §29 for the standing risk register.

## Next five issues

1. **Build & verify the three new Gradle modules.**
   - Objective: `./gradlew rl-server:dist agent-core:build agent-plugin:build`
     green; run `AgentCoreTypesTest`.
   - Why: M0 exit criterion; unblocks everything Java.
   - Likely files: `*/build.gradle`, `settings.gradle`.
   - Acceptance: all three build; JUnit passes; `rl-server` dist jar runs and
     prints the engine pin.
   - Tests: `agent-core:test`.
   - Dependencies: no active background Gradle build.
   - Excludes: engine stepping.
2. **M1 external-step spike in `rl-server`.**
   - Objective: headless init, fixed delta, handshake/reset/step/close, minimal
     observation, state hash, tiny scenario.
   - Acceptance: `make smoke` steps exactly 600 ticks and exits 0; timing report.
   - Depends on: issue 1 and `docs/ENGINE_NOTES.md` (other track).
3. **Java protocol encoder mirroring `docs/PROTOCOL.md`.**
   - Acceptance: round-trips against `protocol.py`; cross-language framing test.
4. **Python process supervisor + PettingZoo skeleton (M2 start).**
   - Acceptance: launch one JVM, handshake, reset, step, close over loopback TCP.
5. **Determinism harness + first golden hashes (M1/Gate 1).**
   - Acceptance: same seed+trace → identical hash over ≥600 ticks; wired into
     `make determinism`.

## Decisions

See `docs/decisions/ADR-0001..0010` (do not relitigate).

## Deviations from the brief in this scaffold

- `protocol/` is **not** a Gradle module. Per ADR-0004 the bootstrap transport is
  JSON; the schema lives in `docs/PROTOCOL.md` and `protocol.py`. Protobuf +
  generated bindings are deferred to Stage D. This avoids dead scaffolding.
- `make build` does not invoke Gradle yet (background-build safety).
- Java modules are scaffolded but unbuilt (see above).
- `tests/{determinism,integration,golden}/` from the brief tree are not created
  yet (no tests to place there); they arrive with M1.
