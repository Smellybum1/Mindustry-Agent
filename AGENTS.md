# AGENTS.md — Instructions for coding agents

This file is the **source of truth** for any AI coding agent (Claude, Codex, etc.)
working in this repository. `CLAUDE.md` intentionally points here rather than
duplicating content. Read this fully before making changes.

This is a **fork-based monorepo**: a checkout of [`Anuken/Mindustry`](https://github.com/Anuken/Mindustry)
pinned at tag `v159.7` (commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`), on
branch `coop-agent/v159.7`, with custom modules layered on top to build a
deterministic, externally-stepped, multi-agent RL environment with cooperating
agents. See `docs/ARCHITECTURE.md` for the full picture and `docs/decisions/`
for the architectural decisions (ADR-0001..0010) that are settled — do not
relitigate them.

---

## 1. Build and test commands

All entry points are Makefile targets that delegate to `scripts/*.sh`. Scripts
must run in **Git Bash on Windows** and in **Linux/WSL2** (the reference
training runtime) unchanged. `make` may not be installed on Windows; invoke the
underlying `bash scripts/<name>.sh` directly if so.

| Command | Purpose | Status |
|---|---|---|
| `make bootstrap` | Verify toolchain versions (JDK 21, Python ≥3.11, Git Bash), print them | Works |
| `make build` | Build Java modules + Python package | Delegates to Gradle (do not run while a background build is active) |
| `make test` | All fast tests (Java + Python) | Python works; Java pending harness wiring |
| `make test-java` | JUnit tests | Pending |
| `make test-python` | `python -m pytest python/tests -q` | Works |
| `make smoke` | One reset/step/close against a JVM env | Not implemented (M1) |
| `make determinism` | Golden replay / hash check | Not implemented (M1) |
| `make stress-reset` | Repeated in-memory reset test | Works (M2: 1000 resets) |
| `make benchmark` | Scaling + timing report | Works (M2: 1/2/4 JVMs) |
| `make scripted-demo` | Headless scripted team | Not implemented (M6) |
| `make demo-server` | Human-joinable real-time server | Not implemented (M6/M10) |

Unimplemented targets **must exit nonzero** with `not implemented: see
docs/ROADMAP.md#<item>`. Never make a stub print success.

**Do not run Gradle builds** if a background `./gradlew` build is active — the
daemon and build cache contend. Syntax-check Gradle files by eye instead.

---

## 2. Coding conventions

Match upstream Mindustry style so diffs stay reviewable:

- **Java**: brace-on-same-line (`void foo(){`), no space before the paren in
  control statements (`if(x){`), 4-space indent, `mindustry.*` package roots.
  Our modules use `mindustry.rl` (rl-server), `agentcore` (agent-core), and the
  plugin package under `mindustry.agentplugin`.
- Prefer Arc collections (`arc.struct.Seq`, `ObjectMap`) over `java.util` in
  hot paths that touch engine code, as upstream does.
- **Python**: PEP 8, `src/` layout, type hints, module docstrings. Core package
  must be importable with **zero third-party deps**; optional features go behind
  `[dev]` / `[rl]` extras.
- No secrets, absolute machine paths, or user-specific config in committed files.

---

## 3. Architecture invariants (do not violate)

1. **Threading rule.** I/O threads may parse and queue requests. **Only the
   simulation/main thread may read mutable game state for an observation
   boundary or apply a game action.** Mindustry is not thread-safe. Every
   exception must be documented in `docs/ARCHITECTURE.md`.
2. **External fixed-step application** (ADR-0002): 1 engine update == 1 game
   tick at fixed delta `1/60 s`. No wall-clock pacing in training mode.
3. **One environment per JVM** (ADR-0003). Parallelism = multiple persistent
   JVM processes. Reset happens in-process without a JVM restart.
4. **Structured communication is authoritative** (ADR-0005). Human-readable
   text is *rendered from* structure. No LLM in the training loop.
5. **Env layer is framework-neutral** (ADR-0007). No `torch` import in the
   PettingZoo env or protocol code.
6. **Determinism.** Same seed + same action trace → identical `state_hash`.
   Anything that breaks this is a bug, not a tradeoff.

---

## 4. Files and areas you must NOT edit

- `core/src/mindustry/gen/**` and any generated `mindustry.gen` class — **never**
  hand-edit generated code.
- Upstream files under `core/`, `server/`, `desktop/`, `annotations/`, `tools/`,
  `tests/`, `build.gradle`, `settings.gradle` — **avoid**. If an edit is truly
  unavoidable, keep it minimal, purpose-specific, and record it in
  `docs/UPSTREAM_PATCHES.md` (file, reason, diff summary) in the **same commit**.
- `docs/ENGINE_NOTES.md` — owned by the engine-stepping design track; do not touch.
- The engine version pin (`ENGINE_VERSION`, and the Arc hash in
  `gradle.properties`) — engine upgrades happen only in dedicated branches with
  golden-replay regression (ADR-0001, ADR-0010).

Add-only areas (safe to work in): `rl-server/`, `agent-core/`, `agent-plugin/`,
`python/`, `docs/`, `scripts/`, `scenarios/`, `configs/`.

---

## 5. Source pin rule

Never track `master`, `latest`, or an unbounded dependency range during
experiments. The full Java environment is identified by one commit plus
`ENGINE_VERSION`. Record engine tag, commit, Arc hash, protocol version,
scenario version, Python lockfile, and training config in every run manifest.

---

## 6. Documentation update rule

Docs are part of "done", not an afterthought. When you change behaviour:

- Keep `docs/STATUS.md` and `docs/HANDOFF.md` **truthful** — they must reflect
  reality, including what is stubbed or unverified.
- Update `docs/ROADMAP.md` checkboxes only when exit criteria are genuinely met.
- New architectural decisions get a new ADR in `docs/decisions/`; don't mutate
  the intent of an accepted one — supersede it with a new file instead.
- Every reward component must be entered in `docs/REWARD_AUDIT.md` before it
  influences training.

---

## 7. Definition of done (brief §28)

An issue is complete only when **all** of these hold:

- code is implemented;
- tests cover the important behaviour;
- failure paths are handled;
- telemetry is added (where the change is observable at runtime);
- docs are updated;
- commands are reproducible and noninteractive;
- dependencies are pinned;
- no secret or machine-specific path is committed;
- upstream modifications are catalogued in `docs/UPSTREAM_PATCHES.md`;
- the relevant benchmark is rerun if the change is performance-sensitive;
- `STATUS.md` and `HANDOFF.md` remain truthful;
- changes are committed in small, descriptively named commits.

"The code exists" is not "done".
