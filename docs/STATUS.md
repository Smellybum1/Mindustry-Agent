# Status

**Date:** 2026-07-20
**Branch:** `coop-agent/v159.7`
**Engine pin:** tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`, Arc `208a754044`

This file is kept truthful. It describes what actually exists, what is a stub,
and what is unverified.

## What exists and works

- **Repository scaffold**: top-level `AGENTS.md`, `CLAUDE.md`, `NOTICE.md`,
  `ENGINE_VERSION`, `Makefile`, `.gitignore` additions.
- **Docs**: `ARCHITECTURE.md`, `ROADMAP.md`, `STATUS.md`, `HANDOFF.md`,
  `UPSTREAM_PATCHES.md`, `PROTOCOL.md`, `REWARD_AUDIT.md`, `SCENARIOS.md`,
  `BENCHMARKS.md`, and ADR-0001..0010 under `docs/decisions/`.
- **Python core package** (`python/src/mindustry_agents/`): imports with zero
  third-party dependencies. `protocol.py` implements length-prefixed JSON framing
  and all v1 message dataclasses. **13 Python tests pass** via
  `python -m pytest python/tests -q` (verified 2026-07-20 with pytest 8.4.2 on
  Python 3.12.5).
- **`scripts/bootstrap.sh`**: verifies and prints the toolchain; exits 0 on this
  machine (JDK 21 Temurin, Python 3.12.5, Git 2.46). Verified working in Git Bash.
- **Not-implemented scripts** (`smoke`, `determinism`, `stress-reset`,
  `benchmark`, `scripted-demo`, `demo-server`, `test-java`): exit 1 with a
  pointer to `docs/ROADMAP.md`, by design.

## What is stubbed (compiles/imports, no real behaviour)

- **`rl-server`**: `mindustry.rl.RlServerMain` prints the engine pin and exits 0.
  No engine stepping, no protocol server, no scenario loading yet.
- **`agent-core`**: real, compilable, unit-tested types — `TaskType` (16),
  `CoordinationAct` (13), `SkillStatus` (6), `AgentId` record — plus a JUnit
  test. No task board, skills, observations, or reward logic yet.
- **`agent-plugin`**: `mindustry.agentplugin.AgentPlugin` placeholder; not a
  loadable Mindustry plugin. See `agent-plugin/README.md`.
- **Python subpackages** `env`, `process`, `policies`, `training`, `evaluation`,
  `telemetry`, `tools`: documented skeletons, no implementation.
- **`scenarios/bootstrap-defense-v0/`**: spec stub only.
- **`configs/`**: example YAML stubs marked unused-yet.

## What is unverified

- **Java build of the new modules.** A background `./gradlew server:dist` build
  was running during scaffolding, so this track did **not** run Gradle (to avoid
  daemon/cache contention, AGENTS.md §1). The three new module `build.gradle`
  files were syntax-checked by eye against `server/build.gradle` and
  `core/build.gradle` idioms but have **not** been compiled. First real build is
  an M0 exit-criterion item.
- **Java unit tests** (`agent-core` `AgentCoreTypesTest`): written, not run
  (same reason).
- **No CI** configured yet.
- **No lockfile** for Python yet (pinned deps are trivial/none for the core).

## Known deviations from the brief

See the end of `HANDOFF.md`. In summary: `protocol/` is intentionally **not** a
Gradle module (JSON bootstrap lives in `docs/PROTOCOL.md` + `protocol.py`, per
ADR-0004); the Makefile carries the full brief §33 target surface, with unbuilt
targets failing loudly.
