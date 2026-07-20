# Handoff

Codex-ready handoff per brief §27. Kept truthful; `TODO` marks pending info.

## Project state

- **What currently works** (M0–M2 complete, all verified 2026-07-20): the
  fixed-step headless `rl-server` (reset/step/hash over loopback JSON, smoke +
  determinism + 1000-reset stress all green), the `agent-core` coordination
  board (64 JUnit tests), the Python env/process layer (supervisor pool with
  crash-replacement, PettingZoo-shaped facade, vector collector; 26 pytest
  green), benchmarks recorded in `docs/BENCHMARKS.md`, and the full
  `bootstrap-defense-v0` scenario spec (`docs/SCENARIOS.md`, `scenario.json`).
- **What is stubbed**: `agent-plugin` (placeholder for the M6/M10 demo server);
  per-agent observations/actions (plumbing exists; payloads are world-level
  no-ops until M3 — see `docs/M3_DESIGN.md`); the scenario *loader* still builds
  the minimal M1 world, not the full bootstrap-defense-v0 spec (no waves yet);
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
| `make test` | Runs the Python suite (26 pass). Use `make test-java` for the JUnit suite. Exit 0. |
| `make test-python` | `pytest python/tests -q` → all pass. |
| `make test-java` | `gradlew agent-core:test` (64 tests) + compile checks for `rl-server`/`agent-plugin`; ends `test-java: OK`, exit 0. Verified 2026-07-20. |
| `make smoke` | Builds `rl-server.jar` if missing, launches one JVM, handshake + `reset(seed=12345)` + 10×60 ticks; prints transcript ending `SMOKE OK: tick advanced exactly 600`, exit 0. Verified 2026-07-20. |
| `make determinism` | Two fresh JVMs, same seed/schedule → identical hashes at every boundary; in-JVM reset purity check; ends `DETERMINISM OK`, exit 0. Verified 2026-07-20. |
| `make stress-reset` | Boots one persistent JVM, resets 1000× (same seed) with no restart; all 1000 initial hashes identical, reset latency median/p95/max reported, leak check = peak RSS under `Xmx(350m) + 300 MiB` ceiling (within-cap growth is heap ergonomics, informational only — trend thresholds proved flaky); ends `STRESS-RESET OK`, exit 0. Verified 2026-07-20 (twice, incl. after the methodology fix). |
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

- **Passing**: 26 Python tests (`test_import.py`, `test_protocol.py`,
  `test_supervisor.py`, `test_env.py`; fake-server subprocess, no JVM, fast) and
  64 Java JUnit tests (`agent-core`, via `make test-java`). Real-JVM coverage is
  the shell scripts (smoke/determinism/stress-reset/benchmark) — all verified
  green 2026-07-20 by a second party (orchestrator re-ran them independently).
- **Skipped**: none.
- **Flaky**: the stress-reset *leak* check was flaky under the original
  growth-trend methodology (passed for the author, failed on re-verification);
  fixed by switching to a capped-heap absolute-ceiling check. Hash stability was
  never flaky.
- **Failing**: none.
- **Golden hashes**: determinism harness compares live runs; checked-in golden
  trace files are still TODO (see next issues).

## Known risks and bugs

- **The seed lever is unexercised**: the M1/M2 scenario has no stochastic
  content, so different seeds produce identical hashes. Determinism of
  stepping/reset is proven; seed-sensitivity must be re-proven when waves/RNG
  arrive with the full scenario loader (M3+). Reproduction: pass different
  `root_seed`s and compare hashes — they currently match by design.
- **4-JVM scaling is Python-bound** (~53% efficiency): GIL-bound JSON in the
  collector, not the engine. Fine for now; revisit before large-scale training
  (larger tick chunks or process-based collection).
- **Protocol overhead** is ~22% of a 60-tick step wall-time (engine is just
  <1 ms/chunk); Gate 6 (<10%) passes only at larger action-repeat. Honest
  status in `docs/BENCHMARKS.md`; revisit alongside ADR-0004's Protobuf trigger.
- See `docs/decisions/` and brief §29 for the standing risk register.

## Next five issues

1. **M3: agent entities + first skills (mine/deliver).**
   - Objective: implement `docs/M3_DESIGN.md` — `RlAgentRegistry`,
     `SkillController` (custom `AIController`), skills NavigateTo / MineResource
     / DeliverToCore / Wait in `agentcore.skill`, per-agent observations and the
     additive action schema (D5/D6), hash extension (D7).
   - Why: first real agent behaviour in the exact engine; unblocks M4–M6.
   - Likely files: `agent-core/src/**/skill/`, `rl-server/src/**` (registry,
     controller, action decode, obs build), `python/.../tools/smoke.py`,
     `docs/PROTOCOL.md` (additive fields).
   - Acceptance (ROADMAP M3): scripted agent mines copper and delivers it —
     core copper increases by exactly the mined amount; skill failure reasons
     visible in responses; determinism holds with a scripted action trace.
   - Excludes: building/repair/defend (M4), task-board wiring (M5), rewards.
2. **Full bootstrap-defense-v0 scenario loader.**
   - Objective: extend the in-code generator to the spec in
     `scenarios/bootstrap-defense-v0/scenario.json` (patches, lead, east lane,
     spawn point, deterministic 3-wave schedule).
   - Acceptance: waves spawn at exact ticks; hashes reproduce across processes;
     losing (build nothing) and winning (per SCENARIOS.md arithmetic) both
     reachable; seed-sensitivity finally demonstrable.
3. **Golden replay files + `tests/golden/`.**
   - Objective: check in seed + action trace + expected hashes; wire
     `make determinism` to also verify against the stored trace (≥10k ticks,
     Gate 1).
   - Acceptance: byte-identical hashes vs the checked-in trace; CI-runnable.
4. **agent-plugin demo-server skeleton (M6 prep).**
   - Objective: plugin loads in the ordinary dedicated server, spawns one
     server-controlled unit driven by the same `agentcore.skill` code, announces
     via chat using `agentcore.announce`.
   - Acceptance: human can join locally (`make demo-server`) and watch it mine.
5. **Collector scaling fix (only if training start nears).**
   - Objective: raise 4-JVM efficiency above ~80% (larger tick chunks per
     request and/or process-based collector).
   - Acceptance: updated `docs/BENCHMARKS.md` scaling table.

## Decisions

See `docs/decisions/ADR-0001..0010` (do not relitigate).

## Deviations from the brief in this scaffold

- `protocol/` is **not** a Gradle module. Per ADR-0004 the bootstrap transport is
  JSON; the schema lives in `docs/PROTOCOL.md` and `protocol.py`. Protobuf +
  generated bindings are deferred to Stage D. This avoids dead scaffolding.
- `tests/{determinism,integration,golden}/` from the brief tree are not created
  yet; golden trace files are next-issue 3.
