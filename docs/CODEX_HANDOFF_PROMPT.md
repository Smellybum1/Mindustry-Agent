# Codex Handoff Prompt

This file IS the handoff prompt. When handing the project to Codex (or any
coding agent), paste the block below as its first instruction. Keep it updated
whenever the "verified state" or "first task" changes.

---

You are taking over **mindustry-coop-agents**: cooperative autonomous Mindustry
agents built on the exact game engine, at `C:\Codex\Mindustry Agent` (Windows 11;
Git Bash for scripts; JDK 21 Temurin on PATH; Python 3.12). It is a fork-based
monorepo of Anuken/Mindustry pinned at tag `v159.7`, commit
`c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c` (Arc `208a754044`), branch
`coop-agent/v159.7`, remote `upstream`. Never update the engine pin.

## Read in this order (do not skip)

1. `AGENTS.md` — build/test commands, conventions, invariants. The source of
   truth for how to work here.
2. `docs/HANDOFF.md` — verified project state, exact commands with expected
   outputs, architecture map, performance, known risks.
3. `docs/ROADMAP.md` — Milestones M4–M6 are broken into issue-sized items with
   acceptance criteria. **M6 is complete; your work queue begins with M7.1.**
4. `docs/M4_DESIGN.md` — the approved design you are implementing (it has open
   questions to resolve against engine source and record in place — follow the
   precedent in `docs/M3_DESIGN.md`, which shows the expected resolution style).
5. Before touching engine-adjacent code: `docs/ENGINE_NOTES.md` (source-verified
   engine facts) and `docs/UPSTREAM_PATCHES.md` (the only 2 upstream edits).
6. Context when needed: `docs/ARCHITECTURE.md`, `docs/PROTOCOL.md`,
   `docs/COORDINATION.md`, `docs/SCENARIOS.md`, `docs/STRATEGY_NOTES.md`.

## Verified state you can rely on (all re-verified 2026-07-20)

- M0–M5 complete + the bootstrap-defense-v0 scenario loader with deterministic
  enemy waves. `bash scripts/{bootstrap,build,test-java,test-python,smoke,
  determinism,stress-reset,benchmark}.sh` all exit 0. 102 JUnit + 38 pytest.
- The fixed-step headless env: ~76k engine ticks/sec, ~1 ms resets, determinism
  proven across processes at 79 hash boundaries including ordered
  `east_duo_v1` build+supply, a post-wave wall placement, and moving/re-pathing enemies;
  different seeds diverge (wave spawn spread), same seed never does.
- Agent units mine and deliver with an exactly-balanced resource ledger;
  skills are engine-free FSMs (`agentcore.skill`) behind an `AgentBody` port,
  executed by `mindustry.rl.SkillController` on the simulation thread.
- The coordination contract board is hosted per episode by the sim-thread M5.2
  adapter; typed actions, skill mapping, board/events/masks, and state hashing are
  live and cross-process deterministic.
- M5.3 dependency-free greedy/fixed-role policies drive that surface. The live
  helper trace records a real resources-short block, request/offer/accept, 21
  legally mined/delivered copper fulfilling a 20-copper contract, and one build
  completion; the complete transcript is byte-identical across fresh JVMs.
- M5.4 reserves exact schematic footprints and task copper before skill start,
  exposes and hashes reservation state, and cancels interrupted build plans. Its
  live overlap/release/resource-budget trace is byte-identical across JVMs.
- M5.5 deterministically freezes one validation agent mid-task, proves ordinary
  lease expiry/release/reclaim/completion, and reaches a normal episode outcome;
  its 3600-tick chaos transcript is byte-identical across fresh JVMs.
- M5.6 renders only rate-limiter-approved structured events, exposes cumulative
  coordination/idle/message metrics, and proves 112 structured events collapse
  to four coherent announcements in the live helper run. The full event/metric
  transcript is byte-identical across fresh JVMs.
- M6.1 adds the live `copper_line_v1` board task and a three-agent expert. All
  five evaluation seeds win at tick 8100; the legal insufficient-copper variant
  emits `resources_short`, replans through mining, and wins too.
- M6.2 emits pinned JSONL episode summaries and a reproducible aggregate table:
  5/5 seed-set wins, minimum/mean final core health 848/927.2.
- M6.3 checks in 16,200 ticks of complete expert actions/events/hashes. Fresh-JVM
  replay matches 678 checkpoints; the in-memory negative mutation flips one.
- M6.4's real-server plugin builds/supplies four Duos, mines continuously,
  expands to six/eight supplied Duos after waves 1–2, and clears all three waves
  at 1091 core health. A stock v159.7 client observed the complete run and
  verified `/agents stop` halted all three tasks. M6.5's matrix/audit is recorded
  and the closure commit is tagged `milestone-6`.

## Invariants (violating these is failure, even if tests pass)

1. **Threading**: only the simulation thread reads or mutates game state. I/O
   threads parse and enqueue. No exceptions without an AGENTS.md update.
2. **Determinism is non-negotiable**: any cross-process hash drift is a
   blocking bug, never a documented caveat. No wall-clock in the sim path; all
   RNG seeded from `root_seed`; stable iteration everywhere.
3. **Upstream edits**: avoid; if truly necessary, minimal + additive, no
   behaviour change for normal game mode, catalogued in
   `docs/UPSTREAM_PATCHES.md`. Never edit `mindustry.gen` or the pin.
4. **No fake game actions**: no teleports, no free items, no direct state
   pokes. Resource ledgers in integration tests must balance exactly.
5. **Docs stay truthful**: `STATUS.md`/`HANDOFF.md`/`ROADMAP.md` updated in the
   same change as the code; never claim unverified results; run the scripts and
   report real numbers.
6. **Shared machine**: other unrelated agent projects run here (Slay the Spire
   2, Brotato, Factorio). Never kill processes by name — only PIDs you spawned.
   Loopback-only sockets (existing 47810+ probing scheme). Cap parallel JVMs
   at 4. No machine-global config changes (JAVA_HOME, global git config, PATH).
7. **Definition of done** per `AGENTS.md`/brief §28: code + tests + failure
   paths + telemetry + docs + reproducible commands + small descriptive commit.
   Do not push; commit locally on `coop-agent/v159.7`.

## Your first task

`docs/ROADMAP.md` → **Milestone 7, item 7.1 learned selector baseline
contract**. Milestones 4–6 are verified complete. The
thread-less pathfinder refresh is wall-clock-free and the 79-boundary determinism
trace legally executes and supplies the schematic, then builds a post-wave wall;
`BuildBlock` uses real engine plans and balances core resources; reset/step now
emit bounded scenario-driven task candidates and aligned validity masks; the
scripted policies demonstrate distinct work and measurable helper fulfilment;
rendered announcements and cumulative coordination metrics are live and
rate-limited. Each item lists objective, files,
acceptance, and dependencies. Before starting, run
`bash scripts/smoke.sh && bash scripts/determinism.sh` to confirm the baseline
is green on your session; if it is not, diagnose that first — do not build on a
red baseline.

## Verification you must run before declaring any item done

`./gradlew agent-core:test rl-server:dist` · `python -m pytest python/tests -q`
· `bash scripts/smoke.sh` · `bash scripts/determinism.sh` ·
`bash scripts/stress-reset.sh` (after anything touching reset/registry), plus
the item's own acceptance check. Report actual numbers, not summaries of
intent.

---

## Notes for the human doing the handoff (Tom)

- Working tree should be clean except the generated
  `annotations/src/main/resources/classids.properties` (never commit it —
  policy in `docs/UPSTREAM_PATCHES.md`).
- The repo has never been pushed to a remote; consider creating a private
  GitHub repo first (`git remote add origin ...`, push `coop-agent/v159.7`) so
  Codex sessions have a durable base. GPL-3.0 obligations are summarized in
  `NOTICE.md` and only bind on distribution of binaries.
- The training reference runtime is intended to be Linux/WSL2 eventually
  (ADR-0009); everything so far is verified on Windows + Git Bash. WSL re-verification
  is unstarted — flag this to Codex if you switch it to WSL.
- Fable's session history: M0–M3 + scenario built by Opus subagents under
  Fable orchestration, each milestone independently re-verified before the
  next was built on it. The one flaky test found (stress-reset leak check) was
  re-methodologized (absolute ceiling); details in `docs/BENCHMARKS.md`.
