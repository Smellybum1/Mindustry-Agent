# ADR-0123: Precommit M9 hard-example relabel v1

**Status:** Accepted

## Context

ADR-0122 accepts only a feature-distinguishable-ranking signal from the
rejected on-policy-relabel update-64 checkpoint. On the 40 public-dev roots,
the deterministic student disagrees with planner v11 on 89/3,200 eligible
same-state labels. All 39 same-family disagreement pairs compare distinct
governed 37-float candidate rows; semantic targets are diffuse. The evidence
supports changing learning pressure over already represented candidates, not
adding identities, changing the planner, or hard-coding a target.

## Decision

Freeze `m9-candidate-native-hard-example-relabel-v1` before implementation or
training. It loads the exact rejected update-64 model and optimizer states as
immutable initialization without selecting, repairing, or promoting the
checkpoint.

The student controls the same deterministically shuffled 2,048 unique public
train roots by deterministic argmax. Planner v11 labels the same pre-action
student-visited states without execution. For each actor-valid label, the
student action used at collection time is compared with the planner label
before any optimizer step for that update. Disagreement examples receive fixed
weight `4.0`; all other examples receive weight `1.0`. Each minibatch minimizes
the sum of example-weight times teacher-action NLL divided by the sum of its
example weights. Recorded weights are not recomputed after optimizer steps.

The `4.0` multiplier is prospective and fixed. At the observed 89/3,200 public
diagnostic rate it would assign about `0.1026824` of normalized loss weight to
disagreements while leaving ordinary labels dominant. It is not selected from
a training sweep.

Every other coordinate is inherited exactly from
`m9-candidate-native-on-policy-relabel-v1`: planner labels, candidate features
and masks, deterministic student control, public 2,048-root schedule, 32 by 64
budget, eight Adam epochs, optimizer values and state, model, RNG, dev roots,
checkpoint ranking, 30/40 construction floor, and idle threshold.

Configuration/public-protocol SHA-256 values are
`c2401782578d2e8a3a3277fa8920d17fcee23f7cda89e92a9e1d09cfb166f459` /
`a42b1cd24a78f67404868835642c4c4a77143865f0e101bea57f6d197b88cab3`.

Replica A may start only after implementation, focused tests, deterministic
weighted-optimizer evidence, live terminal-reset replay, and the complete
public-only exact-current-commit preflight are committed and pass. Replica B is
authorized only if Replica A reaches at least 30/40 wins and the idle threshold;
otherwise it is prohibited. An authorized Replica B must reproduce the full
run and selected checkpoint exactly.

## Constraints

- The source checkpoint file/content/model/optimizer hashes, source
  manifest/result, accepted diagnostic, public seed files/hashes, schedule,
  model, optimizer, budget, and replica policy are frozen and fail closed.
- Only example weight changes. No target identifier, feature, mask, planner,
  action authority, reward, critic, PPO, MAPPO, entropy, replay, root, budget,
  or extra RNG change is authorized.
- The rejected source remains unselected, unrepaired, and unpromotable.
- No confirmation, held-out, or learned human-session access is authorized.
  M8 held-out-v7 remains sealed.
- A passing exact replica pair may initialize only a separately precommitted
  downstream successor.

## Consequences

Implementation may now add this one weighted-NLL mechanism and its fail-closed
preflight. No candidate trajectory, optimizer update, changed model state, or
restricted-data access preceded this precommit. Failure at Replica A must be
recorded honestly and prohibits Replica B.
