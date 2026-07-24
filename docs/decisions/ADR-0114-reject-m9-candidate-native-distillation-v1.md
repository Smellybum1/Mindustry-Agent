# ADR-0114: Reject M9 candidate-native distillation v1

**Status:** Accepted

## Context

ADR-0113 froze the first learned consumer of accepted candidate-native planner
v11 before model work. Exact-current-commit pretraining authority at
`6ba880da66e6b80c2c901062b7d20c509c3d9dc5` passed all 486 Python tests,
pinned Java/custom-module checks, smoke, cross-process determinism, and the
664-checkpoint golden replay without confirmation or held-out access.

Replica A then completed all 2,048 unique public train episodes and 32
deterministic updates. The supervisor won 1,221/2,048 training episodes and
supplied 183,264 actor-valid labels; 15,258 forced controls were executed but
correctly excluded from actor loss. Within-current-update presentation
accuracy increased from `0.8184123138` to `0.9594071004` while teacher NLL fell
from `0.6271266397` to `0.1565120006`.

That batch fit did not produce the required public-dev behavior. Update 3 was
best at 18/40 wins, mean core health `398.025`, and mean team idle fraction
`0.0995369138`. Update 32 finished at 9/40, core `173.25`, and idle
`0.0865960410`. No checkpoint met the frozen 30/40 construction bar.

The compact result is
`configs/evaluation/m9-candidate-native-distill-v1-result.json`, SHA-256
`47ced62d5b7e3c15c980415bc3c05974bfacfd1ccbfd7e2af6c7f474486af590`.
The authoritative run-manifest SHA-256 is
`cd88deac884ee8513857e979d3eeea33e5d4ea925d220cdef455edb1b992c3c0`;
its canonical run digest is
`c3a283d3a8b703004a93800f02ee28040c3132086a81e566980008cf2cd8974e`.

## Decision

1. Reject `m9-candidate-native-distill-v1`. It does not satisfy the
   prospectively frozen learned-construction gate.
2. Replica B is prohibited because Replica A did not pass construction. No v1
   checkpoint is selected, promotable, or authorized to initialize PPO.
3. Preserve the full Replica A manifest, checkpoints, logs, and compact result
   as public development evidence.
4. Treat high within-batch presentation accuracy alongside poor autonomous
   dev survival as evidence requiring an immutable-checkpoint diagnostic, not
   as authority to claim catastrophic forgetting or covariate shift.
5. Before another learned recipe, prospectively freeze one public-only
   teacher-forced agreement diagnostic over immutable update-3 and update-32
   checkpoints. It may measure teacher-label NLL/top-1 agreement and
   task/action confusion on the existing public dev roots in exact fresh JVMs.
   It cannot select, repair, train, promote, or access restricted data.
6. M8 held-out-v7 remains sealed. M9 confirmation, final evaluation, MAPPO,
   and learned human-session collection remain unauthorized.

## Alternatives

- Running Replica B is rejected because ADR-0113 makes construction-passing
  Replica A a hard prerequisite.
- Selecting update 3 is rejected because 18/40 is far below the frozen 30/40
  bar.
- Immediately adding replay, sequence gradients, or on-policy aggregation is
  rejected because the current evidence does not distinguish forgetting from
  closed-loop distribution shift.
- Lowering the bar or opening restricted data is rejected as post-result
  repair.

## Consequences

- M9.1 remains open and MAPPO remains blocked.
- Candidate-native supervision remains viable as a source; this decision
  rejects only ADR-0113's exact within-update behavioral-cloning construction.
- The next authorized work is a separately precommitted, immutable-checkpoint,
  public-only agreement diagnostic.
