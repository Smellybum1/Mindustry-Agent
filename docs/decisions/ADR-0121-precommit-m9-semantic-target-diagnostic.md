# ADR-0121: Precommit M9 semantic-target diagnostic

**Status:** Accepted

## Context

ADR-0120 accepts a concentrated critical-error signal in the rejected
on-policy-relabel update 64 checkpoint. Its dominant disagreement is
`SUPPLY_TURRET->SUPPLY_TURRET`, but task-family aggregation cannot distinguish
a semantic target mistake from two candidates that are indistinguishable under
the governed 37-value candidate feature row.

## Decision

Freeze one immutable public diagnostic before implementation or execution.
Rejected update 64 controls all 40 existing public-dev roots by deterministic
argmax while planner v11 labels the same pre-action states without controlling
the environment. Two fresh JVM reports and the first-root terminal-reset replay
must match exactly.

For every disagreement, record the teacher and student candidate task type,
task id, and target. For the same-task-family subset, aggregate semantic target
pairs, task-id pairs, seat/outcome counts, exact equality of the two governed
37-float candidate rows, differing feature fields, and the first such loss
disagreement.

A target-pair-concentration signal requires the three most common semantic
target pairs to cover at least `0.50` of same-family disagreements. A
feature-alias signal requires exact candidate-row equality in at least `0.50`
of same-family disagreements. If same-family disagreements exist without that
alias threshold, accept a feature-distinguishable-ranking signal.

The protocol SHA-256 is
`8003d7ef159cf9940d1898aa7c2bc380dda8d1846e5a26ddd58c6ef0a9827ee9`.

## Constraints

- The checkpoint file/content/model/config hashes and compact source result are
  immutable and fail closed.
- The diagnostic cannot select, repair, modify, resume, train, or promote the
  checkpoint.
- It cannot authorize PPO, MAPPO, confirmation, held-out access, or learned
  human sessions.
- M8 held-out-v7 remains sealed.

## Consequences

An exact result may authorize only a separately named prospective mechanism
that addresses the accepted signal. No further learned recipe is authorized
until this diagnostic is complete and recorded.
