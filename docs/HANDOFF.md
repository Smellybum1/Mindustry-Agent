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
| `make test-java` | **Exits 1** — not implemented (M0). |
| `make smoke` | **Exits 1** — not implemented (M1). |
| `make determinism` | **Exits 1** — not implemented (M1). |
| `make stress-reset` | **Exits 1** — not implemented (M2). |
| `make benchmark` | **Exits 1** — not implemented (M2). |
| `make scripted-demo` | **Exits 1** — not implemented (M6). |
| `make demo-server` | **Exits 1** — not implemented (M6/M10). |

(If `make` is unavailable on Windows, run `bash scripts/<name>.sh` directly.)

## Architecture map

- **Key modules**: `rl-server` (headless fixed-step launcher, `mindustry.rl`),
  `agent-core` (`agentcore`), `agent-plugin` (`mindustry.agentplugin`); Python
  `mindustry_agents` package. See `docs/ARCHITECTURE.md`.
- **Important classes/functions**: `mindustry.rl.RlServerMain` (entry point,
  placeholder); `agentcore.{TaskType,CoordinationAct,SkillStatus,AgentId}`;
  `mindustry_agents.protocol.{encode,decode,decode_stream,read_message}`.
- **Protocol entry points**: `docs/PROTOCOL.md` (spec v1);
  `python/src/mindustry_agents/protocol.py` (reference impl). Java encoder TODO
  (M1).
- **Simulation thread rules**: only the sim thread reads/mutates game state; I/O
  threads parse+queue (`docs/ARCHITECTURE.md` threading rule).
- **Reset path**: TODO (M1/M2) — in-process reset, no JVM restart.
- **Step path**: TODO (M1) — atomic action bundle → advance exact ticks → hash.
- **Observation path**: TODO (M1/M3) — built on the sim thread at a boundary.
- **Task/skill path**: TODO (M3–M5) — task board + skill executors in `agent-core`.

## Current performance

- **Machine information**: TODO (benchmark not run).
- **Single-environment ticks/sec**: TODO.
- **Reset latency**: TODO (target <250 ms, stretch <100 ms; brief §24 Gate 2).
- **Memory per JVM**: TODO.
- **Scaling table**: TODO.
- **Known bottleneck**: TODO (unmeasured).

## Tests

- **Passing**: 13 Python tests (`test_import.py`, `test_protocol.py`).
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
