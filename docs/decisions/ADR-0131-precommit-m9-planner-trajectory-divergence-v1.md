# ADR-0131: Precommit M9 planner trajectory divergence v1

**Status:** Accepted

## Context

ADR-0130 rejects maximal-freshness micro-DAgger and closes the pointwise
candidate-native imitation line. The owner has explicitly authorized a new
prospective architecture or supervision-class plan.

The public planner-correction result already argues against making an atomic
joint-bundle actor the first architecture change. Replacing the student's
complete actor-authoritative bundle with planner v11 at every eligible
disagreement reduced both rejected 13/40 students to 9/40, while aggregate
task-switch and same-family-retarget rates changed little. What remains
unmeasured is whether the independently successful 32/40 planner follows a
materially different macro-task trajectory from the exact rejected update-64
student on roots where their outcomes differ.

## Decision

Freeze the public-only diagnostic
`m9-planner-trajectory-divergence-v1` before implementation or execution. It
compares two independently controlled policies on the same ordered 40 public
development roots:

1. the exact rejected on-policy-relabel update-64 model under deterministic
   argmax control; and
2. unchanged candidate-native planner v11 controlling the complete canonical
   three-seat bundle.

For each policy, sample the accepted active task family of all three seats on
the fixed reset-relative 60-tick grid through its terminal tick. Initial state
is `(WAIT, WAIT, WAIT)`. An accepted SELECT or WAIT at boundary `t` supplies
the token for grid ticks in `(t, next_boundary_tick]`; CONTINUE, ABANDON,
forced, or rejected actions preserve the prior token. Compare paired
trajectories only through the minimum terminal tick.

Record per root:

- the fraction of common grid ticks whose ordered three-seat task-family
  tuples differ; and
- unit-cost Levenshtein distance between consecutive-run-compressed joint
  token sequences, normalized by the larger compressed length.

The primary paired roots are planner wins and student losses. Exact frozen
student reproduction is 13/40 wins and mean core health `242.975`; exact
planner reproduction is 32/40 wins. Two fresh JVM reports must match root for
root and the first root must repeat exactly after terminal reset. The source
checkpoint model and optimizer hashes must remain unchanged.

A valid result is `trajectory_supervision_signal` only when there are at least
15 planner-win/student-loss roots and both median paired-root metrics are at
least `0.5`. It is `low_trajectory_signal` when planner-only wins are at most
9 or median occupancy mismatch is at most `0.25`; otherwise it is
`mixed_trajectory_signal`. Invalidity takes precedence, followed by strong,
low, and mixed classification.

The immutable protocol SHA-256 is
`bcd572fa49d859d56c780c55a389577835eccf59a9382887bff68ec834778d6a`.

## Constraints

- This diagnostic may not train, modify, select, repair, or promote a model or
  optimizer.
- It may not change planner v11, candidates, features, masks, actions, or
  public root membership.
- Published evidence contains task-family tokens and derived distances only;
  it contains no semantic target identifiers or raw observations.
- No reward, critic, PPO, MAPPO, confirmation, held-out, human-session, or
  other restricted-data authority is granted. M8 held-out-v7 remains sealed.
- Only a valid `trajectory_supervision_signal` may authorize drafting a new,
  separately prospective trajectory-supervision ADR. It does not itself
  authorize implementation or training.

## Consequences

Implementation may add one fail-closed evaluator, exact-current-commit
preflight, command surface, focused tests, and public derived result. No
diagnostic episode or model mutation preceded this precommit.
