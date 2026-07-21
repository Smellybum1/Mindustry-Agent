# ADR-0031: V20 low full-boundary teacher regularization

**Status:** Accepted

## Context

V19 reproduced exactly and reduced selected-dev idle-cap saturation from 8/10
episodes to 2/10. Its reusable permanent-idle gap improved from 0.06547793 to
0.05480651, but remained definitively worse; recovery stayed uncertain and a
small non-forced-abandonment regression returned. The cap-extension hypothesis
is therefore closed rather than extended again.

Reusable dev-v1 evidence provides a causal alternative. The all-adaptive
scripted teacher wins 9/10 and has a permanent-greedy idle gap of 0.01737902
(95% CI +0.00762127..+0.02707198), far smaller than V19, with zero abandonment
difference. V19 disagrees with its adaptive teacher on 529 of 607 unforced
decisions. Its quality reward already makes announcements and duplicate work
non-regressing, so a bounded teacher loss can target task choice while retaining
those learned improvements.

V10 proved that full-boundary teacher coefficient `1.0` overwhelms the outcome
objective and collapses construction to 1/10. V4's successful-episode
coefficient `0.05` improved its construction screen without domination. The
unexplored causal test is therefore the same low scale applied to every
unforced boundary under V19's stronger quality reward.

## Decision

1. V20 keeps V19's engine/runtime contract, train/dev roots, reward, model,
   optimizer, RNGs, schedule, checkpoint-selection rule, and every other loss
   coefficient fixed.
2. Change only `teacher_imitation_coefficient` from `0.0` to `0.05` in the
   top-level and mirrored optimizer contract. It is cross-entropy against the
   adaptive scripted action at the same structured boundary, applied only to
   unforced policy transitions. It is training-only and separately metered;
   reward, inference logits, action masks, and evaluation remain unchanged.
3. Add behavior-neutral `teacher_candidate_diagnostics` to archived training
   traces so task-type/target disagreements can be audited. The field is
   excluded from the action/state trace digest and cannot affect training or
   replay behavior.
4. V20 must pass the exact 44-case V19 reward adversary set and full regression
   suite before training. Two pinned 2,048-episode replicas must reproduce the
   selected checkpoint, frontier, model state, replay, and full-run digest.
5. Reusable dev-v1 must pass construction and both permanent/matched
   scorecards. Retire V19's unopened dev-v15 and freeze dev-v16 at globally
   disjoint roots `161001..161160` for one exclusive confirmation only after
   all reusable gates pass. Held-out-v4 remains sealed.

## Alternatives

- Repeating or enlarging the idle cap was rejected because V19 substantially
  removed saturation without clearing idle and reintroduced abandonment.
- Reusing V10's coefficient `1.0` was rejected by its 1/10 construction result.
- Blending or biasing inference logits was rejected because the train-time
  teacher coordinate has not yet been tested at a non-dominating scale under
  the current reward and preserves a cleaner learned-policy contract.
- Changing teammates or promotion baselines was rejected because it would
  weaken the accepted M8.5 comparison rather than improve the candidate.

## Consequences

- V20 adds no runtime dependency and does not change structured communication,
  simulation-thread ownership, external stepping, or engine state.
- The low teacher term may still reduce construction or fail to outperform the
  all-adaptive reference. Any reusable failure stops before dev-v16.

Pretraining validation passes all 44 exact-config reward adversaries, the full
141-test Python suite, smoke, and golden determinism. Config SHA-256 is
`22604e484c82601aa6905ad55582f93936067583e6edfc539d5c5720462fe270`;
adversary report SHA-256 is
`b72ab95c45ec418fe79f17d5235fce54031e49f1eab792f52189191390aa37af`.

The two pinned replicas reproduce exactly and select update 32 at 9/10 wins
with mean idle 0.09850656. Checkpoint `6209f46876db0778...`, model state
`1ba534267c67ff54...`, replay `a1bc0eec0c7f0002...`, full run
`a407aa303e839844...`, and direct lineage `564f7fdca22f0ba9...` match. Teacher
disagreement falls from 529/607 to 170/362 unforced decisions and abandonment
returns to zero, but permanent idle remains 0.05419477 worse (95% CI
+0.02812093..+0.08298135). Permanent announcements/duplicates and both
recovery comparisons are uncertain. Dev-v16 therefore remains unopened and
held-out-v4 remains sealed. Reusable preflight report SHA-256 is
`a4ae30d0be2a6ec258bf9375ef4b61baf9152e472a9d27edafa4190694c8f12b`.
