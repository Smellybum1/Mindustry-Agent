# ADR-0120: Accept M9 concentrated critical-disagreement signal

**Status:** Accepted

## Context

ADR-0119 froze an immutable student-controlled diagnostic over the rejected
distillation update 32 and on-policy-relabel update 64 checkpoints. The run
completed from implementation commit `dff2c31f6846c8c307f5e1ccd4a2c878e871d48b`
using only the existing 40 public-dev roots.

## Decision

Accept the diagnostic's concentrated-critical-error classification. The two
fresh JVM reports and terminal-reset replay are exact. Update 64 produced 89
disagreements over 3,200 eligible labels (`0.9721875` agreement); its three
most common teacher/student task pairs account for `0.6741573` of all
disagreements, above the frozen `0.50` threshold.

The dominant pair is `SUPPLY_TURRET->SUPPLY_TURRET` with 39 disagreements.
Because the task family is equal while the authoritative action index differs,
this identifies candidate-slot or target selection—not merely task-family
priority—as the next question. It does not yet identify which target property
causes the choice.

Do not accept a rejection-association signal. Only `0.1111111` of losses had a
rejection versus `0.2307692` of wins, a loss-minus-win difference of
`-0.1196581`. The diffuse-residual signal is also false.

The full report SHA-256 is
`aa01d177ab312aff2a35b12263286ecd02a7e69ef2b18dd3469e7ae0e7bac044`,
its canonical report SHA-256 is
`5127aea85c2332f9bf96f08d8f710acf12bd59c5c29f0a4d97039958b617d030`,
and the compact result SHA-256 is
`464ab91a13c4ca370b0b4fb5f016e45b96c23a3a56ff3ebdac38342adde7b4a1`.

## Constraints

- Both learned checkpoints remain rejected and cannot be selected or repaired.
- The result does not authorize training, PPO/MAPPO, promotion, confirmation,
  held-out access, or learned human sessions.
- Before any successor model work, freeze one public-only diagnostic that
  resolves same-family disagreements to exact candidate identity and target.
- M8 held-out-v7 remains sealed.

## Consequences

The next authorized work is a separately precommitted immutable semantic-target
diagnostic. A training successor may be proposed only after that result
identifies a bounded mechanism; aggregate task-family weighting alone is not
supported.
