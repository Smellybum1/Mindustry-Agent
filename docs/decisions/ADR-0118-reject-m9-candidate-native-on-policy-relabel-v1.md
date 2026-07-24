# ADR-0118: Reject M9 candidate-native on-policy relabel v1

**Status:** Accepted

## Context

ADR-0117 froze a single closed-loop correction: exact rejected-final
model/optimizer initialization, deterministic student control on the same
2,048 public train roots, and planner-v11 labels on the same pre-action
student-visited states. The complete exact-commit gate passed at
`4fee79ca6aaebf4a0672ff3dfe79cc1ac61da9ef`.

Replica A completed all 2,048 episodes and 32 continuation updates. It won
581/2,048 training episodes. The model retained high label fit on its own
visited states: mean pre-update student/teacher top-1 agreement was
`0.9551109044`, mean NLL was `0.1557045606`, and post-update presentation
accuracy was `0.9608913649`. The student nevertheless produced 1,756 rejected
actions across training, while 51,161 forced controls were correctly excluded.

Public-dev construction did not follow. The final continuation checkpoint was
also best, at 13/40 wins, mean core health `242.975`, and mean team idle
fraction `0.0925962318`. No checkpoint met the frozen 30/40 bar.

The compact result is
`configs/evaluation/m9-candidate-native-on-policy-relabel-v1-result.json`,
SHA-256
`ebea0b741abbf2b7e3d995af1f87d7528ddee08d94089db4f837f40c730e60ee`.
The authoritative manifest/canonical SHA-256 values are
`f34c50a024f05d6084a8661fb627fa8c3c5cd223dc45bd03273258877f489952` /
`1cf33117526a04c8053bc66ce786945964a88e1d32a1de3227bd2af042524c81`.

## Decision

1. Reject `m9-candidate-native-on-policy-relabel-v1`. It does not satisfy
   learned construction.
2. Replica B is prohibited. The update-64 checkpoint is not selected,
   promotable, or authorized to initialize PPO.
3. Preserve the full run, checkpoints, logs, and compact public result.
4. Do not interpret high aggregate student-state agreement as sufficient.
   Before another recipe, prospectively freeze an immutable-checkpoint,
   student-controlled public diagnostic comparing source update 32 and relabel
   update 64. It must localize first teacher disagreement, task/action
   confusion, action rejections, and outcome association on the same 40 dev
   roots in exact fresh JVMs.
5. Do not authorize another learned recipe until that diagnostic distinguishes
   concentrated critical errors from diffuse residual disagreement.
6. M8 held-out-v7 remains sealed; M9 confirmation/final, MAPPO, and learned
   human sessions remain unauthorized.

## Alternatives

- Running Replica B is rejected because Replica A missed construction by
  17 wins.
- Extending current-update relabeling or lowering the gate is rejected as
  post-result repair.
- Adding replay, scripted fallback, or task-specific loss weights immediately
  is rejected because the current aggregate telemetry does not identify which
  residual disagreements cause autonomous failure.

## Consequences

- M9.1 remains open.
- The next work is a bounded public diagnostic, not more training.
