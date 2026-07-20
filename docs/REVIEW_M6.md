# Milestone 6 Independent Review (2026-07-27)

Reviewer: Fable orchestration pass, independent of the implementing agent.
Scope: `46aed9307..cfbc42535` (29 commits, tagged `milestone-6`).

## Verification (all reproduced independently)

102 JUnit + 38 pytest green; smoke incl. scenario checks; determinism incl.
golden replay (678 checkpoints / 16,200 ticks / 2 episodes); evaluation 5/5
wins, core health min/mean 848/927.2 — identical to the implementer's report.

## Invariant verdicts

All six invariants CLEAN (threading, determinism, upstream policy, no fake
actions, docs truthfulness, module boundaries) — one doc-accuracy gap
(finding 1). Nothing requires revert.

## Findings (fix in M7.1/M7.2; severity-ordered)

1. **UPSTREAM_PATCHES.md diff summary is stale** vs the actual patched
   `Pathfinder.java` (shows pre-M4.1 body, wrong line range :356-378 vs real
   :366-402, omits the `needsRefresh` block). Regenerate from the current file.
   *Invariant-adjacent: the catalogue must be accurate.*
2. **The utility/candidate policy layer is dead relative to M6**: the winning
   expert (`tools/scripted_demo.py ExpertEpisode`) is a hand-authored linear
   macro that never imports `policies/scripted.py` (GreedyUtility/RoleAssignment
   are exercised only by tests). The learned selector (M8) plugs in at exactly
   this seam — resolve before building on it (M7.3 routes the expert through
   the candidate/utility layer).
3. **DemoCoordinator hardcodes counts in log strings asserted by the survival
   probe** (`:368 "fortifications=20 turrets=4"`, `:434 "planned_blocks=9"`) —
   not derived from the placement loops; probe can pass on stale literals.
4. **DemoCoordinator dead branches**: `MAINTENANCE_DELIVER` post-increment
   guard can never fire (:319); `DEFEND` re-issue at :339 is unreachable and
   diverges from :477 (drops per-agent offset). Delete both.
5. **Coordination brain duplicated**: `DemoCoordinator` (~800 lines) re-implements
   the lifecycle `CoordinationAdapter` (639 lines) owns. Shared: TaskBoard, skill
   FSMs, scenario data, renderer, SkillController. Not shared: staging, wave
   handling, expansion policy. The `PARITY OK` probe checks build order only.
   Divergence risk for everything after M6 — unify (M7.2).
6. **Hardcoded coordinates divorced from scenario.json**: expert builds Duos at
   (29,23)/(29,25) vs authoritative (32,23)/(32,25) and anchor [32,24]; mine
   tiles literal ×3 vs ore patch `B_copper_support`. Both processes already
   parse the JSON — derive from it.
7. **scenario.json success predicates stubbed to proxies**: T2's
   `conveyor_path_connects` + `core_item_inflow_ge 0.6/s` implemented as block
   presence+rotation; T4/T6 reduced to ammo/broken counts. Implement (M7.4) or
   annotate as planned.
8. **CandidateGenerator truncation drops by generation order, not utility**
   (:108-111) — DEFEND (priority 1.0) generated last, could be truncated as
   scenarios grow. Truncate lowest-utility / reserve a DEFEND slot.
9. **`System.nanoTime()` in the reset handler** (RlServer.java:301) for
   transport episode_id — benign (not hashed) but a wall-clock read on the
   reset path; derive from rootSeed + reset counter.
10. **Duplicated constants across the boundary**: ARRIVAL_TOLERANCE ×2;
    Python WIN_TICK/WAVE_TICKS/defend-duration re-literal scenario.json; the
    1/9 first-drill heuristic coupled to copper_line_v1's 9 blocks.
11. **SupplyBuilding.targetStockBefore/targetStock tracked but never consulted**
    — confirm downstream use or drop.
12. Minor: bare `60L` retry in EmergencyRetreat; `commitYields` blind-remove
    under `@SuppressWarnings`; inline fully-qualified `SkillStatus`.

## M7.1 resolution (verified 2026-07-20)

Findings 1, 3, 4, 6, 8, 9, 10, 11, and 12 are resolved by
`e81752706`, `7bb3b21db`, and the deliberately regenerated golden fixture in
`00421cf76`. `SupplyBuilding` stock values remain intentionally: smoke and
determinism consume both sides of the supply ledger, and the scripted expert
uses current target stock to decide whether a `CORE_SHORT` supply block needs
recovery. Findings 2, 5, and 7 remain assigned to M7.2–M7.4.

## M7.2 resolution (verified 2026-07-21)

Finding 5 is resolved by `488b76bf2`. `ExpertCoordinationDriver` now owns the
shared staging, task lifecycle, wave response, maintenance, expansion, and
reserve-mining policy; `CoordinationAdapter` and `DemoCoordinator` are runtime
ports over that one implementation. The parity gate compares complete recorded
decision sequences and the two live runtime openings, which match at 33
selections and normalized digest
`f335f6b950ac1b58857ca84b40e7151f966d5d53408fd0e643fbc54a39671385`.
Findings 2 and 7 remain assigned to M7.3 and M7.4 respectively.

## Planning-primitiveness inventory (drives M7.3–M7.5)

- **Candidate generation**: compiled-in 6-rule catalog, fixed order, single
  thresholds, magic priorities (0.70–1.0) and estimates; only anchors are
  data-driven; wave anticipation = one fixed 600-tick lead; assignmentRange =
  map diagonal (spatial gating inert).
- **Utility**: static 13-weight additive sum; clamped scalar features; no
  lookahead.
- **Skill FSMs**: reactive flag machines; on failure they block/retry/fail —
  never replan; RebuildRegion takes engine queue order; ExecuteSchematic is
  strict index order.
- **Scripted expert**: hand-authored linear pipeline (opening → bootstrap →
  defense → supply → hold), blocking terminal-status polling in ≤15-tick
  quanta, two hardcoded recovery paths, ~25 coordinate/threshold literals.
  Observable consequence: identical milestone ticks and message counts across
  all 5 seeds.

The four layers are separable; the learned selector seam
(`SELECT_CANDIDATE_TASK` / `utility.score`) is clean. A learned selector
inherits the candidate catalog's ceiling — richer candidates (M7.4) are a
prerequisite for meaningful learning, not a nice-to-have.

## Architecture note

M5 `CoordinationAdapter` is well-built (engine-free board, two-phase
deterministic claim resolution: utility desc → agent index → taskId). The M8+
work should extend it, not bypass it.
