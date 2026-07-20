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
3. `docs/ROADMAP.md` — **"Phase 2: The Teammate Roadmap" (M7–M10, restructured
   2026-07-27) is your work queue, beginning at M7.2.** The north star: agents
   that cooperate at a level top players would want on their team. M7 comes
   before any learning on purpose — read the section preamble.
4. `docs/REVIEW_M6.md` — the independent review of the milestone-6 work. Its
   findings ARE items M7.1/M7.2; its planning-primitiveness inventory is the
   design rationale for M7.3–M7.5. Do not skip it.
5. Before touching engine-adjacent code: `docs/ENGINE_NOTES.md` (source-verified
   engine facts) and `docs/UPSTREAM_PATCHES.md` (the only 2 upstream edits).
6. Context when needed: `docs/ARCHITECTURE.md`, `docs/PROTOCOL.md`,
   `docs/COORDINATION.md`, `docs/SCENARIOS.md`, `docs/STRATEGY_NOTES.md`.

## Verified state you can rely on (all re-verified 2026-07-20)

- M0–M6 and M7.1 complete + the bootstrap-defense-v0 scenario loader with deterministic
  enemy waves. `bash scripts/{bootstrap,build,test-java,test-python,smoke,
  determinism,stress-reset,benchmark}.sh` all exit 0. 103 JUnit + 40 pytest.
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
- M6.2 emits pinned JSONL episode summaries and a reproducible aggregate table.
  The M7.1 revalidation remains 5/5 wins, with minimum/mean final core health
  749/840.8 and the same two total unit losses as the M6 baseline.
- M6.3 checks in 16,200 ticks of complete expert actions/events/hashes. After
  deliberate M7.1 regeneration, fresh-JVM replay matches 672 checkpoints; the
  in-memory negative mutation flips one.
- M6.4's real-server plugin builds/supplies four Duos, mines continuously,
  expands to six/eight supplied Duos after waves 1–2, and clears all three waves
  at 1100 core health in the latest no-port probe. A stock v159.7 client observed the complete run and
  verified `/agents stop` halted all three tasks. M6.5's matrix/audit is recorded
  and the closure commit is tagged `milestone-6`.
- M7.1 resolves review findings 1/3/4/6/8/9/10/11/12: scenario-owned
  coordinates/timing feed both demos, candidate overflow is utility-ranked with
  DEFEND reserved, reset IDs are seed+counter deterministic, duplicated skill
  constants/dead branches are removed, stock telemetry consumers are explicit,
  and the Pathfinder patch catalogue is exact. Full closure validation is
  recorded in `docs/STATUS.md` and `docs/BENCHMARKS.md`.

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

`docs/ROADMAP.md` → **Milestone 7, item 7.2 (one coordination brain)**,
then 7.3 → 7.6 strictly in order. Milestones 4–6 and M7.1 are verified complete and
independently re-verified 2026-07-27 (all suites green; evaluation 5/5
reproduced exactly); M7.1's current golden replay is 672/672 checkpoints. Do NOT start learned-
selector work (M8) until every M7 exit criterion is met — M7 exists because
the M6 expert is a hand-authored macro (see REVIEW_M6.md) and a learned policy
must have adaptive baselines worth beating and an evaluation ladder to be
judged by.

Special notes for M7:
- 7.1 changed the golden replay as expected. The deliberate fixture-only
  regeneration is commit `00421cf76`; before/after both win twice at tick 8100,
  and smoke ledgers remain balanced.
- 7.2 (one coordination brain) is the parity backbone for everything that
  follows; treat any training/demo behaviour divergence found while unifying
  as a bug to surface, not to paper over.
- 7.3's `docs/CANDIDATE_GAPS.md` is a required deliverable even if the list is
  short — M8's design consumes it.

Before starting, run `bash scripts/smoke.sh && bash scripts/determinism.sh` to
confirm the baseline is green on your session; if it is not, diagnose that
first — do not build on a red baseline.

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
