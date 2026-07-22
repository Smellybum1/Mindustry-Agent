# ADR-0054: V40 partner-intent teacher-conflict filter

**Status:** Accepted

## Context

V39 passed every implementation and pretraining gate but failed its frozen
construction floor. Fifteen of 32 reusable checkpoints reached 8/10 wins and
none reached 9/10. Strong late checkpoints share a deterministic tick-zero
`BUILD_LINE` opening; seed 2005 is the only loss common to reusable updates
12, 13, 16, 20, 25, and 26. Replica B, reusable scorecards, confirmation, and
final access did not run.

Reusable counterfactual evaluation of rank-best update 25 isolates the new
signal. With V39 partner intent enabled, every seed switches at tick zero from
the duplicated seat-1 `BUILD_SCHEMATIC` to `BUILD_LINE`; the result is 8/10
with losses on 2005 and 2006. With only that input disabled, the same checkpoint
is also 8/10, losing 2002 and 2007. Seat 2's harvest intent never changes the
opening. The seat-1 risk value flips all ten reusable openings within the tight
range `0.100813646..0.110020827`, so a scalar adjustment cannot isolate the
regressed seeds and is rejected.

The training labels contain a narrower contradiction. V39 computes the exact
partner-intent risk before model selection, then retains the scripted teacher's
ordinary action as the imitation label. Across the fixed 256-episode teacher
warmup schedule, 752 of 3,956 teacher-eligible transitions select a candidate
that the same transition marks as partner-intent duplication risk. All 256
episodes contain a conflict: 325 schematic, 38 harvest, and 389 supply labels;
256 occur at tick zero and 496 later. The 94 successful episodes contribute 189
conflicts to the 1,079-transition warmup/rehearsal corpus. V39 samples those
conflicts 177 times in warmup and 734 times in rehearsal; the complete
rehearsal schedule reaches 188 unique conflicts, leaving one unsampled. The
on-policy PPO
teacher term at coefficient `0.05` applies the same unfiltered label rule.

This is contradictory supervision, not an action-authority defect: PPO can
still select the duplicate when its learned value outweighs risk, but teacher
imitation should not explicitly reward a label that the structured input marks
as duplicate work at that boundary.

## Decision

1. V40 holds V39 exact except for one training-only eligibility coordinate.
   When the configured partner-intent feature is active and the scripted
   teacher's exact action index is in that boundary's exact risk-candidate
   indices, that transition is excluded from teacher imitation.
2. The exclusion applies identically to teacher warmup, per-update teacher
   rehearsal, and PPO's `teacher_imitation_coefficient` term. It does not remove
   the transition from PPO policy/value/entropy learning, reward accumulation,
   episode traces, or checkpoint evaluation.
3. Matching remains exact candidate-index evidence derived from exact
   structured `task_id` equality. Task type, target text, rendered messages,
   heuristic similarity, outcomes, or future state cannot substitute.
4. The coordinate is explicitly configured as
   `partner_intent_teacher_conflict_filter_v1`. Configurations that omit it
   retain byte-for-byte historical warmup, rehearsal, and PPO teacher masks.
   Invalid schema, match, coverage, or use without the V39 partner-intent
   feature fails closed before an episode.
5. Runtime action selection remains V39-exact. The action mask, structured
   communication, feature dimensions, model, reward, optimizer coefficients,
   training/reusable roots, budgets, RNGs, scripted partners, policy prior,
   checkpoint gate, and final binding remain unchanged.
6. Focused tests must prove the positive exclusion and retain nonmatching,
   no-risk, forced, historical omitted-config, ordinary PPO actor/value, and
   deterministic sample-schedule behavior. A reusable/train-only diagnostic
   must archive the conflict counts and verify that every configured imitation
   path applies the same filter before model work.
7. The full V39 pretraining boundary remains required: public survival and
   staging, Python and pinned Java suites, smoke, cross-process/reset/seed
   determinism, golden replay and negative control, plus all exact-config reward
   adversaries. Any runtime, public, replay, or reward regression rejects V40.
8. Replica A retains the exact V39 model, roots, reward, optimizer, 256-episode
   warmup, 2,048-episode/32-update PPO budget, and RNGs. It must reach at least
   9/10 reusable wins with mean idle below `0.25` before replica B. Exact twins,
   direct lineage, fresh permanent baselines, and both reusable scorecards
   remain mandatory under ADR-0051.
9. Dev-v35 is retired unopened and unconsumed. The value-free V40 umbrella
   reserves dev-v36 at 160 roots in `[4_000_000_000,5_000_000_000)`, disjoint
   by namespace without a governed membership read. Dev-v36 construction and
   access are primary-only. Held-out-v6 remains sealed and unconsumed under
   ADR-0053.

## Alternatives

- Changing partner-intent risk magnitude is rejected because every reusable
  opening crosses within the same narrow interval; it cannot separate the
  stable loss without seed-conditioned overfitting.
- Disabling partner intent at tick zero or for seat 1 merely restores the
  duplicated schematic on every reusable seed and does not resolve the 8/10
  ceiling.
- Disabling all teacher imitation changes several established training
  coordinates and discards nonconflicting structured supervision.
- Masking, redirecting, forcing, or rewriting the learned action remains
  rejected by ADR-0050 and ADR-0052.

## Consequences

- V40 must retrain because the deterministic teacher sample eligibility and
  optimizer trajectory change. No runtime code or observation shape changes.
- Warmup and rehearsal reports must record eligible, excluded-conflict, sampled
  conflict, and retained presentation counts so replicas can compare the new
  training boundary directly.
- The immutable preimplementation config is
  `configs/training/m8-selector-v40-partner-intent-teacher-conflict-filter.json`,
  SHA-256
  `230759e7e02dcca9a6b7608f7784b20f85845c40da0f7a28dd1ec13641d0013a`.
- The value-free dev-v36 reservation is
  `configs/evaluation/m8-selector-v40-confirmation-umbrella.json`, SHA-256
  `27c1948085e53dff1abdf7a6b99a8226f8d7e4f5e60c5f58b14cd1224b44d4be`.
- This ADR authorizes implementation and pretraining gates after the precommit
  packet is committed. It does not authorize dev-v36 membership construction,
  replica A, confirmation consumption, or held-out-v6 access.

The implementation is committed at `c9459c58f4`. The bound train-only
diagnostic reproduces 256 episodes, 94 wins, 3,956 teacher-eligible transitions,
752 conflicts, and the corrected 1,079/189 successful-corpus counts. Warmup
samples 177 conflict presentations and rehearsal samples 734 across 188 unique
conflicts. The ignored report SHA-256 is
`4fe2960225d659cb5e2d78e02ab199484b6c09dbfd8b09a9393bfb60c1de387e`;
its deterministic payload digest is
`8484c36bf959fd9efffba60a0540b388e6e470fae854d657d5b4df897bfe4096`.

The complete pretraining boundary subsequently passed: 208 Python tests;
pinned `agent-core:test`, `rl-server:test`, and `agent-plugin:classes`; public
candidate survival 5/5 with 10 proactive staging starts; focused secondary-wake
and owned-schematic staging checks; smoke; determinism at cross-process
`20a97f36407167597981e77c`, reset `a2cf4a73ee901c844f30f486`, and alternate
seed `495ba05fa71697bdc8ff2951`; 664-checkpoint/16,200-tick golden replay plus
negative mutation control; and all 44 exact-config reward adversaries. The
ignored reward report SHA-256 is
`9677e5caed4d891cb9f31c6a34475e1f276359dfa5c794f8b13210cd9ffe0dd5`.
No confirmation membership, baseline episode, or model work preceded the
green boundary.

The primary-only dev-v36 freezer packet adds
`scripts/freeze-v40-confirmation-seed-set.py` and pure no-membership tests. It
generates solely within `[4B,5B)`, hashes in-memory bytes, never opens a prior,
sealed, or generated membership document, and emits only a value-free receipt.
The 211-test Python suite passes before the freezer is committed or run.

The freezer was committed at `54db674e2e` before construction. Its value-free
receipt records 160 roots, zero membership-document reads, no read-back of the
generated membership, no retired-confirmation or sealed-final read, and no
emitted values. Dev-v36 membership SHA-256 is
`d4bfbcf88d99f4f2daee9cffbdceb7a9aa74de664da6a777800b94f18e8cdf9b`;
receipt SHA-256 is
`fce63a49f80d1653777ed1cae2b3d6f730928da7d1c0a8075142403edd1353d7`.
Dev-v36 remains frozen and unconsumed; held-out-v6 remains sealed and
unconsumed. The receipt-aware Python suite passes 212 tests without opening
membership.
