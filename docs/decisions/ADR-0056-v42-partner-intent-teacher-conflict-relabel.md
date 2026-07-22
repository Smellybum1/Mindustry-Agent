# ADR-0056: V42 partner-intent teacher-conflict relabel

**Status:** Accepted

## Context

V41 preserves 10/10 reusable wins and beats all four observed win comparators,
but its permanent-greedy idle and matched-greedy recovery intervals still cross
zero. Dev-v37 is therefore retired unopened and unconsumed. Held-out-v6 remains
sealed and unconsumed.

Public trace diagnosis closes several apparent successor lines. The sole
adverse permanent-idle pair is seed 2006. The learned seat dies while harvesting;
its subsequent WAIT actions are forced with no valid SELECT action. Both surviving
scripted partners later select the structured `runtime:wait` candidate because no
productive between-wave candidate exists, then resume distinct defense tasks at
the next wave. The learned and scripted teacher selections before every public
learned-seat death agree and both expose danger `0`. Additional WAIT bias, danger
supervision, exact-death recovery bias, broader staging, masking, redirection,
reward pressure, interpolation sweeps, and teacher-strength changes are therefore
either falsified by this evidence or already closed by accepted ADRs.

One training-only coordinate remains untried. V40 filters an imitation label when
the scripted teacher selects the same exact structured `task_id` as a fixed
partner. A behavior-neutral diagnostic replayed the exact 256-episode ordinary
teacher train schedule with no optimizer update. It reproduces V40's 94 wins,
3,956 eligible transitions, 752 exact conflicts, 1,079 successful-corpus eligible
transitions, and 189 successful conflicts. A pure counterfactual that preserves
the adaptive teacher's current preferred task type and return-to-defense state,
but excludes the exact conflicting candidate indices, finds a valid non-WAIT
alternate for 682/752 conflicts and 174/189 successful-corpus conflicts. All 256
tick-zero conflicts have an alternate; 70 later conflicts, including 15 in the
successful corpus, have none and still require filtering. The counterfactual was
never sent to the environment, and all action/state evidence remains V40-exact.

## Decision

1. V42 retrains the exact V40 recipe with one changed training coordinate. An
   exact partner-intent conflict uses a deterministic nonconflicting alternate as
   the teacher-imitation label when one exists; otherwise the transition retains
   V40's exclusion from teacher imitation.
2. Conflict matching remains the exact original teacher action index in the exact
   risk-candidate indices derived from structured fixed-partner `task_id`
   equality. Task type, target text, rendered communication, heuristic similarity,
   outcomes, and future state cannot substitute.
3. Alternate construction is pure and nonmutating. Candidate catalog position
   must equal its stable `candidate.index` for the first eight entries or the run
   fails closed. Exact risk indices and WAIT candidates are excluded. The teacher's
   current preferred task type, including return-to-defense's `DEFEND_REGION`
   preference, is tried first; if absent, the full remaining pool is used. Highest
   scalar utility wins and the lower stable candidate index breaks exact ties.
   The result must be a valid original selector action in indices `0..7`; otherwise
   no alternate exists and V40 filtering applies.
4. The original scripted action remains authoritative for teacher-controlled
   trajectory behavior and for advancing scripted-policy state. V42 stores a
   separate effective imitation label. It does not alter the environment action
   mask, learned action, fixed-partner action, forced-action handling, reward,
   environment state transition, or original-action runtime trace.
5. Relabeling applies identically to teacher warmup, per-update teacher rehearsal,
   and PPO's `teacher_imitation_coefficient` term. Warmup and rehearsal sample
   over nonconflicting plus successfully relabeled transitions; fallback-filtered
   transitions are removed before the deterministic permutation. V42 retains
   `successful_teacher_imitation_coefficient: 0.0`; enabling an uncovered teacher
   imitation path with this relabel schema must fail closed.
6. Telemetry must retain the original teacher label and record the effective
   label, original conflicts, successful substitutions, fallback exclusions,
   sampled substitution presentations, and deterministic schedules. Historical
   configs that omit the new schema retain their existing V39/V40 behavior.
7. Focused tests must cover exact config validation, catalog drift, state
   nonmutation, preferred and global selection, stable tie breaking, WAIT/masked/
   no-alternate fallback, all three configured imitation paths, deterministic
   warmup/rehearsal schedules, and unchanged PPO policy/value/runtime behavior.
8. The full V40 pretraining boundary remains required before any seed freeze or
   model work: public survival and staging, Python and pinned Java suites, smoke,
   cross-process/reset/seed determinism, golden replay plus negative control, and
   all 44 exact-config reward adversaries. Replica A retains the exact model,
   roots, reward, optimizer, 256-episode warmup, 2,048-episode/32-update budget,
   and RNGs. It must reach at least 9/10 reusable wins with mean idle below `0.25`
   before replica B. Exact twins, direct lineage, fresh permanent baselines, all
   four observed win comparisons, and both reusable scorecards remain mandatory.
9. Dev-v37 is retired unopened and unconsumed. V42 reserves primary-only dev-v38
   at 160 roots in the exclusive `[6_000_000_000,7_000_000_000)` namespace.
   Membership may be constructed value-free only after this precommit and the
   complete implementation/pretraining boundary are committed. Held-out-v6
   remains sealed and unconsumed under ADR-0053.

## Alternatives

- Keeping every conflict filtered is V40 and leaves 682 deterministic structured
  alternatives unused.
- Selecting the global utility maximum without adaptive preference is rejected
  because it changes the teacher definition on preferred supply/defense states.
- Executing the alternate, masking the learned action, or redirecting a selected
  action is rejected because it changes runtime authority and repeats failed V38
  diagnostics.
- Reward, WAIT-bias, teacher-coefficient, corpus-strength, recovery-bias, staging,
  and interpolation sweeps are closed by prior governed evidence.
- Using public outcomes, death proximity, danger labels, or future state to choose
  among alternates is rejected as outcome-conditioned supervision and is not this
  coordinate.

## Consequences

- V42 changes optimizer sampling because relabeled conflicts remain eligible,
  while the 70 no-alternate conflicts retain V40 filtering. It therefore requires
  fresh exact replicas rather than checkpoint reuse.
- Runtime behavior, action authority, feature dimensions, model architecture,
  rewards, engine pins, roots, budgets, and RNG values remain V40-exact.
- The immutable config is
  `configs/training/m8-selector-v42-partner-intent-teacher-conflict-relabel.json`,
  SHA-256
  `3fcb0c8800c638a333068ab116f8270be076c1cbae2438b55cc6f193c0583d0d`.
- The value-free confirmation umbrella is
  `configs/evaluation/m8-selector-v42-confirmation-umbrella.json`, SHA-256
  `c1644d2dd6dde231e3a3409632169e182bfb13ebaff84deb2225368a82371532`.
- The ignored train-only diagnostic/report SHA-256 values are
  `11d081f7e022393788f9dbf144f367ff4446960a62df626f30c901c5b699fe2a` /
  `551cdccdcd087a7343356fd15bc24ef2706866d03043d50c101781b68d7de26f`;
  its canonical payload digest is
  `af6a8dc4545f129a18a268c3ff35ba327c53e7b20f12d75481d0695b74eb45a0`.
- This ADR authorizes implementation and public/pretraining gates after the
  precommit packet is committed. It does not authorize dev-v38 membership
  construction, replica A, confirmation consumption, or held-out-v6 access.

## Implementation status

The production/test packet implements a pure nonmutating adaptive-preference
alternate selector, separate original/effective teacher labels, the shared
warmup/rehearsal/PPO effective-label rule, fail-closed config validation, and
V42-only conflict/relabel/fallback/schedule telemetry. Historical omitted-config
and V40 filter paths retain their existing keys and selection populations. The
live production diagnostic reproduces 752 conflicts, 682 relabels, and 70
fallbacks over 34,898 transitions and 3,956 eligible labels. Its report,
canonical payload, and action/state hashes are
`83f8dd6904e5356dc4819c937f941c783652d06487a4c9524558bb67938c80ea`,
`e92436ffb3773b8066b2ce0eb005ace23947f4eebb2db72683334131cb21478e`, and
`0e609742ba171c60fbff1f1f825c4eb071eab18c3bec0a5171702501308d8d87`.

The complete 2026-07-23 public/runtime pretraining boundary passes 243 Python
tests and the Java gate; public policy passes 5/5 with 10 proactive staging
starts; secondary-claim and owned-schematic checks pass; smoke passes;
cross-process, reset, and alternate-seed determinism hashes are
`20a97f36407167597981e77c`, `a2cf4a73ee901c844f30f486`, and
`495ba05fa71697bdc8ff2951`; golden replay passes 664 checkpoints / 16,200 ticks /
two wins and negative replay detects the mutation. All 44 exact-config reward
adversaries pass; report SHA is
`272ac291ef143fa65170c06ddcd7b245b6602e99dfaf232d1fc35bb757f5268a`.
After that committed boundary, the primary-only freezer was committed at
`3e328ce91e` and created dev-v38 solely within `[6B,7B)`. The freeze commit is
`949b73f987`; membership and value-free receipt hashes are
`3f4b0d012cf8730301917a303ca5dfda14b3552ecff357cb3bb25d5ac1976224` and
`fea431ae993d10723432c661a2cc76073696bd8d420015af064256e40d3152cb`.
The receipt records zero membership-document reads, no values emitted, and no
held-out access. The full Python suite passes 248 tests. Dev-v38 remains
unopened/unconsumed.

Independent construction under pinned WSL Torch 2.12.1 and training commit
`12980ee2b9e427d65be1883d014da6fc67a29c5a` is exact across all 32 checkpoint
files. Both replicas select update 2 at 9/10 reusable wins, mean return
`4.73976`, core health `568.8`, and idle `0.03455784384563236`. Checkpoint,
model-state, replay, action-state, and full-run hashes are
`65f8e3dc3a41bf893a085018d3775d70dd3ac9a31fb949be5b18dd4ae8ba2287`,
`4363617f8535bc8b78783f52df69ca1cc016b9af3bff7abc8631a888089db5c9`,
`d01d0dfe425d1b0debd359b5061c8c36fbf18a260375d3c716c5009476f14087`,
`52751513f785c19644d870b5553bfa76a67352b9e23ffaf69f17305b94c6f026`, and
`cb719361da11ab6c5368c39d07695471962ed0461fbe080c3286c2bf861c3a10`.
Direct lineage digest/artifact hashes are
`b1dbf1abc6a7dacdb300aa84a9fa6b8ea0db8fd4d5f489d31a6f5b67ce55df0a` and
`100945a4820b203910dc5b8278765e63948e0f13e69cfa7979d5b40737bef3d0`.
Fresh permanent random/greedy are 4/10 and 8/10; candidate is 9/10 and matched
random/greedy are 5/10 and 6/10, so all four win comparisons pass. Both frozen
scorecards nevertheless fail. Against permanent greedy, announcements have mean
`-0.004178130793538602` with 95% CI
`[-0.021244981053576122,+0.00920378842876899]` and idle has mean
`+0.018837297020387483` with CI
`[-0.0011168581878396708,+0.043252101460647424]`. Against matched greedy,
recovery has mean `-38.3` with CI `[-117.30125,+32.30124999999998]`.
Uncertainty is failure. Baseline records/aggregate hashes are
`53170e04eda5c5e5431aacd9461b4d48705b4b566bebcca4f0416dd8a75c5eb4` and
`295e00a7b41421bc6f8a88b5ff663bcae5d37029a6a7618273249edc6665865d`.
Candidate records/aggregate/report hashes are
`e0a78468268bc021b89941a04b9d930f420138a6988887ef370bd3c8feb5b184`,
`dae12fbf3868c6ccdd6d926e2c5c78df618d7dfc3d9db1f7abe6c7df37dc923b`, and
`01bf941060bc7e6f3ee7ed75d3ba16caae4862bd35c2d01764003a0974e635d1`.
V42 is rejected before confirmation. Dev-v38 is retired unopened/unconsumed;
held-out-v6 remains sealed/unconsumed. No restricted access occurred.
