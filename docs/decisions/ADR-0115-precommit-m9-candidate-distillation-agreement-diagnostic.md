# ADR-0115: Precommit M9 candidate-distillation agreement diagnostic

**Status:** Accepted

## Context

ADR-0114 rejects the first candidate-native behavioral-cloning construction.
Within-current-update presentation accuracy reached `0.9594`, but autonomous
public-dev survival peaked at 18/40 and finished at 9/40. That result does not
distinguish failure to generalize the supervised mapping from compounding
closed-loop state drift. Choosing replay, sequence gradients, or dataset
aggregation without that distinction would be post-result mechanism shopping.

## Decision

Freeze one immutable-checkpoint, public-only diagnostic before implementation
or execution. Candidate-native planner v11 controls the environment over all
40 existing public M9 dev roots while the rejected update-3 and update-32
models advance their own private recurrent states and predict deterministic
argmax actions at the same actor-valid boundaries. Forced controls execute but
do not count as agreement labels.

For each checkpoint the diagnostic records eligible labels, teacher-label NLL,
top-1 agreement, teacher-task to student-task confusion, and teacher-action to
student-action confusion. Two fresh JVM runs and terminal-reset replay must
produce exact reports. Teacher-forced fit is retained only at top-1 agreement
at least `0.90` and NLL at most `0.35`. Retained fit with fewer than 30
autonomous public-dev wins is a closed-loop-shift signal; final top-1 at least
`0.05` below update 3 is a forgetting signal; neither checkpoint retaining fit
is a supervised-generalization-gap signal.

The protocol SHA-256 is
`f779cd313fcd46da5335787b931f746f3d42881a722213392e302dc2e2e895d6`.

## Constraints

- Checkpoint paths, file/content hashes, teacher, seed set, thresholds, action
  mode, and report identity are frozen before diagnostic implementation.
- The diagnostic cannot select, repair, train, modify, resume, or promote a
  checkpoint.
- It cannot authorize PPO, MAPPO, confirmation, held-out access, or learned
  human sessions.
- M8 held-out-v7 remains sealed. Only the already-public M9 dev roots may be
  read.

## Consequences

- A completed exact result may justify a separately named, prospectively
  frozen successor mechanism.
- Until that result is accepted, no new M9 learned recipe is authorized.
