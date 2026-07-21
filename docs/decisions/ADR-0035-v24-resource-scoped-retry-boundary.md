# ADR-0035: V24 resource-scoped retry-boundary retraining

**Status:** Accepted

## Context

V23 reproduced exactly and passed its construction gate, but reusable dev-v1
preflight rejected it before dev-v19. Task abandonment was definitively worse
than both greedy scorecards. Structured trace review found 31 of 32 non-forced
abandons alternating between two resource-short `SUPPLY_TURRET` targets every
two ticks.

The cause was a decision-sequence defect rather than a reward-coefficient
choice. `CoordinationAdapter` retained only one target-local retry slot per
agent. Blocking target B replaced target A's holdoff, so the learned seat could
cycle through targets that shared the same unavailable core inventory. A
multi-target diagnostic confirmed that target-local retention merely enlarged
the cycle. The corrected runtime treats `CORE_SHORT` and `RESOURCES_SHORT` as
shared task-type feasibility failures, while retaining target-local semantics
for other block reasons.

The ordered holdoff set is part of canonical state. A live two-turret fixture
proves both supply targets are masked from block tick 432 until due tick 492,
direct bypass returns `retry_not_due`, unrelated task types remain legal, and
both targets reopen exactly when due. This changes the learned decision
sequence, so the V23 checkpoint cannot be promoted or used as a V24 parent.

## Decision

1. V24 retrains from scratch under runtime contract
   `abandon_wait_resource_scoped_retry_agent_death_available_idle_v5`.
2. V24 keeps V23's train/reusable-dev roots, reward coefficients and caps,
   quality intervention, model, optimizer, RNGs, schedule, checkpoint-selection
   rule, teacher coefficient, and every other config field exact. Candidate ID,
   runtime contract, and confirmation path are the only differences.
3. Two pinned 2,048-episode replicas must reproduce the selected checkpoint,
   checkpoint frontier, model state, replay, full-run digest, and direct lineage.
   A rejected construction gate must retain its complete frontier artifact.
4. Reusable dev-v1 must reach at least 9/10 construction wins, mean idle strictly
   below 0.25, and pass both permanent-greedy and matched-greedy scorecards.
5. Retire V23's unopened dev-v19. Freeze dev-v20 now at globally disjoint roots
   `201001..201160` for one exclusive confirmation only after every reusable
   gate passes. Held-out-v4 remains sealed.
6. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate-policy gate, smoke, and determinism
   including negative replay pass from this committed pretraining packet.

## Alternatives

- Promoting or fine-tuning V23 was rejected because its recorded decision
  sequence predates the resource-scoped action mask.
- Keeping one holdoff per target was rejected because the diagnostic checkpoint
  cycled through more turret IDs instead of waiting for shared feasibility.
- Applying every failure to a whole task type was rejected because invalid
  targets and other target-specific conditions must not suppress independent
  work.
- Changing reward strength, teacher coefficient, or model architecture was
  rejected because this experiment isolates the runtime decision boundary.
- Opening dev-v19 was rejected because V23 failed reusable preflight and its
  successor requires a newly frozen, untouched confirmation set.

## Consequences

- V24 changes no engine pin, fixed-step contract, simulation-thread ownership,
  structured-communication authority, or framework-neutral boundary.
- Resource/core retry feasibility is deterministic, canonical-hashed, and
  enforced by both action masks and selection validation.
- V23, its preflight, and inference-only diagnostics remain immutable failure
  evidence; none is promotion evidence under the new runtime.
- V24 may fail reproduction, construction, or reusable scorecards. Any such
  failure stops before dev-v20 and held-out-v4.

No V24 model work began before this precommit.

Pretraining validation passes all 44 exact-config reward adversaries, the full
146-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`94a7ae8cf57cb1ce890e99e7139749039726624929e138c50ec84c3e76dfb6ca`;
adversary report SHA-256 is
`4cd7f5096bbd0ebc9031b82290156dc4f5ae3f50d089b97278879c252b9720b5`.

## Outcome

Replica A completed all 2,048 episodes and 32 updates, then correctly failed
the precommitted construction gate. No checkpoint reached 9/10 reusable-dev
wins. The best frozen-ranking row was update 19 at 8/10, mean return
`1.207300000000004`, mean core health `692.8`, and mean idle
`0.06516475136727648`. The complete retained frontier hashes to
`90ead621f808c53f4b5443941e6f322cd7190dceef4eab3c4d6cc1212c51c5ba`.
Replica B did not start, no selected manifest or lineage was created, dev-v20
remained unopened, and held-out-v4 remained sealed.

Permitted reusable-dev diagnosis evaluated the current-runtime all-adaptive
reference: it wins 10/10 with mean idle `0.07308978685499233` and zero task
abandonment. Its record and aggregate hashes are
`fd90b6232b3017a2a933f557ce450f86a694c03eb89382c03218eb232b19bce5`
and
`94c423e042f8537a70a32b93d538c772033089b04217a91324cc4c7648e5ea91`.
V24 update 19 disagrees with that teacher on 73 of 427 unforced decisions; its
two losses are seeds 2004 and 2005. V24 is rejected and dev-v20 is retired
unopened.
