# ADR-0119: Precommit M9 critical-disagreement diagnostic

**Status:** Accepted

## Context

ADR-0118 rejects current-update student-state relabeling at 13/40 public-dev
wins despite `0.95511` mean student/teacher agreement. Aggregate agreement is
therefore insufficient to choose between task-specific correction, rejection
avoidance, replay, or a broader representation change.

## Decision

Freeze one immutable, student-controlled public diagnostic before
implementation or execution. Rejected distillation update 32 and relabel
update 64 each control all 40 existing public-dev roots by deterministic
argmax. Candidate-native planner v11 labels the same pre-action states but is
never executed. Each checkpoint runs in two fresh JVMs and repeats the first
root after terminal reset.

The diagnostic records eligible labels/disagreements, the first disagreement
tick and teacher/student task pair per episode, task/action confusion split by
win/loss, rejected student actions by selected task/outcome, and the fraction
of win/loss episodes with a rejection. For update 64, a concentrated critical
error signal requires either the top three task pairs to cover at least `0.50`
of disagreements or one first-disagreement task pair to occur in at least
`0.50` of losing episodes. A rejection-association signal requires loss
episodes to exceed win episodes with any rejection by at least `0.25`. Neither
signal yields a diffuse-residual classification.

The protocol SHA-256 is
`aed6d1b231cc0992a31febb9927497879af2d6b813abaa457e499b8afb5535e0`.

## Constraints

- Both checkpoint file/content/model/config hashes, result hashes, public root
  path/hash, thresholds, execution mode, and report fields are frozen.
- The diagnostic cannot select, repair, modify, resume, train, or promote
  either checkpoint.
- It cannot authorize PPO, MAPPO, confirmation, held-out access, or learned
  human sessions.
- M8 held-out-v7 remains sealed.

## Consequences

- An exact result may authorize only a separately named prospective successor
  matching the accepted signal.
- Until then, no further learned recipe is authorized.
