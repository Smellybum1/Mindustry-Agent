# ADR-0116: Accept M9 candidate-distillation closed-loop-shift signal

**Status:** Accepted

## Context

ADR-0115 froze a teacher-forced agreement diagnostic over the rejected
candidate-native distillation update-3 and update-32 checkpoints. The
implementation was committed as
`e1b449b5e2674cd22bc40860eea3e222b482b1d1` before any diagnostic episode.

Two fresh JVMs and terminal-reset replay reproduce exactly. Candidate-native
planner v11 wins 32/40 public-dev episodes and supplies 4,232 eligible labels.
Update 3 matches 3,522 labels (`0.8322306238`) at NLL `0.4489596918`, so it
does not retain the frozen teacher-forced-fit bar. Update 32 matches 4,071
labels (`0.9619565217`) at NLL `0.1524716850`, clearing both the `0.90` top-1
and `0.35` NLL bars, despite winning only 9/40 when it controls the same
public-dev environment.

The full report SHA-256 is
`56f3680eb67945ca8120a465a9ce04e4eb65e187c628d460dd7c1b9d32f43ac3`;
its canonical digest is
`3f2778201fd928605739819d1458c6075bcd3cfc4aac466b2bb26b0fe47dca05`.
The compact result is
`configs/evaluation/m9-candidate-distill-v1-agreement-diagnostic-result.json`,
SHA-256
`7909e6a2013258d288c5b951748947818f05188b355851271fed5bdfcdfdede9`.

## Decision

1. Accept the prospectively defined closed-loop-shift signal. The final model
   reproduces planner labels on planner-visited states but fails when its own
   actions determine subsequent states.
2. Do not accept a forgetting signal: final teacher-forced agreement improves
   by `0.1297258979` over update 3. Do not accept a supervised-generalization
   gap: update 32 clears the frozen fit thresholds.
3. Keep `m9-candidate-native-distill-v1` rejected. Neither checkpoint is
   selected, repaired, promoted, or authorized as a successful learned policy.
4. Authorize only a separately named, prospectively frozen public successor
   whose isolated learning change queries planner-v11 labels on states visited
   under learned control. Any checkpoint initialization, mixture schedule,
   aggregation window, roots, optimizer budget, selection bar, and replica
   requirement must be fixed before implementation or model work.
5. Do not authorize PPO, MAPPO, confirmation, held-out access, or learned
   human-session collection.

## Alternatives

- More teacher-controlled behavioral cloning is rejected as the next isolated
  change because update 32 already clears the teacher-forced-fit bar.
- Recurrent sequence gradients are rejected as the immediate direction because
  the diagnostic isolates visited-state distribution, not insufficient
  teacher-trajectory fit.
- Promoting update 32 is rejected because its autonomous score is 9/40.

## Consequences

- M9.1 remains open.
- The next autonomous work is a precommit for one student-state
  teacher-relabeling construction, not an unrestricted training search.
- M8 held-out-v7 remains sealed and all restricted M9 evaluation remains
  prohibited.
