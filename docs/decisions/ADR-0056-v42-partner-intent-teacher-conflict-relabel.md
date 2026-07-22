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
