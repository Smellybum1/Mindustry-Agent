# ADR-0122: Accept M9 feature-distinguishable ranking signal

**Status:** Accepted

## Context

ADR-0121 froze a semantic-target diagnostic to decide whether update 64's
same-task-family mistakes arise from target-specific concentration, feature
aliasing, or ranking over distinguishable candidates.

## Decision

Accept only the feature-distinguishable-ranking signal. Two fresh JVM reports
and terminal-reset replay match exactly. The rejected checkpoint repeats its
89 disagreements over 3,200 eligible labels, including 39 same-family
disagreements.

None of those 39 pairs has an identical governed 37-float candidate row, so
the exact feature-alias fraction is `0.0`. The three most common semantic target
pairs cover only `0.2820513`, below the frozen `0.50` concentration threshold.
The distinguishing fields are chiefly proximity/travel cost (all 39 pairs),
then priority/team value/urgency (30 pairs), with resource cost and estimated
copper separating 21 pairs.

Do not infer that any named turret target causes losses. Same-family
disagreements occur 25 times in wins and 14 times in losses, and their semantic
target identities are diffuse. The evidence supports changing ranking pressure
over already-represented candidates, not adding target identifiers or
hard-coding a target pair.

The full report SHA-256 is
`84fb4455228c9c6c0d32354a1698d44b238c4bfe32adf4201c2656ac52744f17`,
its canonical report SHA-256 is
`25d594aaf8dde0340a1e9d3f79cb31a560fbd9632bcdb5af6cbc9698bffd6e2c`,
and the compact result SHA-256 is
`959e55f140fce098ac9b51ed69f247408c516bbf63bcc510617ab93af2d6cb88`.

## Constraints

- Update 64 remains rejected and cannot be selected or repaired.
- The result does not authorize training, PPO/MAPPO, promotion, confirmation,
  held-out access, or learned human sessions.
- A successor must be separately precommitted and may alter learning pressure
  only; this result does not justify a feature-schema or planner change.
- M8 held-out-v7 remains sealed.

## Consequences

The next authorized design is one prospective student-state continuation that
upweights pre-update planner/student disagreements while preserving the
candidate surface, model, public roots, reward-free labels, and deterministic
execution.
