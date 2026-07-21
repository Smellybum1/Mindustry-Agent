# ADR-0032: V21 corrected WAIT-release-boundary retraining

**Status:** Accepted

## Context

V20 reproduced exactly and materially reduced disagreement with its adaptive
teacher, but reusable permanent idle remained definitively worse than greedy.
The low-teacher hypothesis is therefore closed rather than tuned again.

Exact reconstruction of assignment occupancy from the authoritative structured
events in all ten reusable V20 episodes matches the runtime idle counters. It
locates the largest idle gaps after successful `WAIT` completion emitted
`RELEASE`: the adapter cleared the assignment without advancing its decision
revision, so stop-on-event waited for an unrelated later event. Individual
unassigned gaps reached 2,086 ticks.

The corrected runtime marks a successful automatic wait release as assignment
`task_terminal` while preserving the board's authoritative `RELEASE` and `OPEN`
state. The live check proves stop-on-event returns on that release tick after
the deterministic 61-tick wait lifecycle. Existing checkpoints cannot learn
from the corrected transition and reward sequence.

## Decision

1. V21 retrains from scratch under runtime contract
   `successful_abandon_one_tick_wait_release_same_tick_v2`.
2. V21 keeps V20's train/dev roots, reward, model, optimizer, RNGs, schedule,
   checkpoint-selection rule, teacher coefficient, and every other config field
   exact. Freezing teacher coefficient `0.05` isolates the runtime correction;
   it does not reopen the closed coefficient-tuning line.
3. Two pinned 2,048-episode replicas must reproduce the selected checkpoint,
   checkpoint frontier, model state, replay, full-run digest, and direct lineage.
4. Reusable dev-v1 must reach at least 9/10 construction wins, mean idle strictly
   below 0.25, and pass both permanent-greedy and matched-greedy scorecards.
5. Retire V20's unopened dev-v16. Freeze dev-v17 now at globally disjoint roots
   `171001..171160` for one exclusive confirmation only after all reusable gates
   pass. Held-out-v4 remains sealed.
6. Training may begin only after the exact-config reward adversaries, Python
   suite, pinned build, smoke, and determinism gates pass from the precommit.

## Alternatives

- Reverting to V19's zero teacher coefficient was rejected because changing the
  loss and runtime together would confound the boundary hypothesis.
- Further teacher or reward tuning was rejected because V20 changed behavior
  without closing permanent idle, while the structured trace identifies a
  concrete runtime cause.
- Replaying an existing checkpoint can measure corrected inference but cannot
  establish a trained candidate under the new decision sequence.

## Consequences

- V21 changes no engine state, observation, action mask, structured
  communication authority, reward component, or framework boundary.
- Automatic wait completion now produces immediate replanning instead of hidden
  idle, changing rollout durations and credit assignment deterministically.
- V21 may fail reproduction, construction, or either reusable scorecard. Any
  such failure stops before dev-v17 and held-out-v4.

Pretraining validation passes all 44 exact-config reward adversaries, the full
142-test Python suite, the pinned build, smoke, and golden determinism. Config
SHA-256 is
`5567e1c1d79cae0f2ffe276df0534abe0d42299a9fa56347fa063d875092cc1a`;
adversary report SHA-256 is
`732536ffcd358d25a03f27fb48807ac15d4b9ed78ad107ee8f5c55683718d836`.

The two pinned replicas reproduce exactly and select update 29 at 9/10 wins
with mean idle 0.04383598. Checkpoint `68c3dfba722e0b75...`, model state
`5c09bf859571ac2c...`, replay `81ca21dfe5d634b4...`, full run
`5d5831a59032c57e...`, and direct lineage `df5af947a70f6a8c...` match.

Reusable dev-v1 rejects V21 before confirmation. The corrected boundary closes
the permanent-idle gap to -0.00047581 (95% CI
-0.00999458..+0.01044892) and decisively improves matched idle and recovery.
However, non-forced task abandonment is definitively worse by 0.04347388
against both permanent greedy (95% CI +0.02043040..+0.06680916) and matched
greedy (95% CI +0.01956487..+0.06757326). Six episodes each select the same
resource-short supply target, abandon it, and repeat three times at two-tick
cadence before the fourth selection succeeds: 18 non-forced replans that the
matched greedy control avoids. Announcements, duplicates, and permanent
recovery also remain uncertain. Dev-v17 stays unopened and held-out-v4 stays
sealed. Preflight report SHA-256 is
`f1a8e47d4cd771793b89eafd6677bcb791572649066aaef4a61be1807b299b5c`.
