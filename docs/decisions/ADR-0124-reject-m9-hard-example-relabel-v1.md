# ADR-0124: Reject M9 hard-example relabel v1

**Status:** Accepted

## Context

ADR-0123 froze one isolated learning-pressure continuation from the exact
rejected update-64 model and optimizer. The only change was normalized
teacher-NLL weighting: pre-update deterministic student/planner disagreements
received weight `4.0`, while ordinary examples retained weight `1.0`.

The complete exact-current-commit gate passed at
`9f5ea54f3cf4cd6a62b18e743ff0539b704eb660`. Replica A then completed all
2,048 public train episodes and 32 continuation updates. It saw 156,612
actor-valid labels, including 7,499 disagreement examples. Those examples were
`0.0478827` of labels and `0.1674734` of normalized loss weight. Training won
571/2,048 episodes.

No checkpoint reached the frozen 30/40 public construction floor. Update 30
was best at 17/40 wins, mean core health `261.625`, and mean team idle fraction
`0.1035208713`. Final update 32 reached 13/40, mean core health `234.425`, and
idle `0.0946722063`.

The authoritative manifest SHA-256 is
`e1690a0033bb42d36629b55ea0a4f0a73667e482904220e2c8778e5e0b993c0d`,
its canonical run SHA-256 is
`100cbe8f2cbec11eced5444c4cd05ff0fc4967bdcb4cb723a51646b63689196f`,
and the compact result SHA-256 is
`6cc01d04a7a58c7074ac6bb0f07972f282d80cc4bf532d948c41e5f7ea1a8414`.

## Decision

1. Reject `m9-candidate-native-hard-example-relabel-v1`.
2. Replica B is prohibited because Replica A missed construction by 13 wins.
3. Neither update 30 nor update 32 is selected, repaired, promotable, or
   authorized to initialize PPO.
4. Preserve the full public run, checkpoints, logs, manifest, and compact
   result as rejection evidence.
5. Do not infer that a larger disagreement multiplier, target-specific weight,
   pairwise objective, replay mechanism, model change, PPO, or MAPPO is
   authorized. Any successor requires a separately named prospective decision
   before implementation or model work.
6. No confirmation or held-out data was accessed. M8 held-out-v7 remains
   sealed.

## Alternatives

- Replica B is rejected by the frozen conditional policy.
- Selecting update 30 because it improves from the 13/40 source is rejected;
  17/40 remains far below the construction floor.
- Retuning the `4.0` weight from this result is rejected as post-result repair.
- Adding target identifiers or changing planner v11 remains unsupported by
  ADR-0122's diffuse-target, feature-distinguishable evidence.

## Consequences

M9 learned construction remains unmet and MAPPO remains blocked. The next
learned or diagnostic mechanism must be prospectively frozen from public
evidence under a separate ADR; this result itself grants no further model or
restricted-data authority.
