# ADR-0033: V22 retry eligibility and agent-loss boundaries

**Status:** Accepted

## Context

V21 reproduced exactly and removed the definitive permanent-idle regression
after automatic WAIT release. Reusable preflight still rejected it because the
learned seat made 18 avoidable non-forced replans. In six episodes it selected
one resource-short supply target, abandoned it, and selected the same semantic
target again at two-tick cadence three times before the fourth attempt could
succeed.

Every blocked skill already reports `nextRetryTick`, documented as the earliest
legal retry. `CoordinationAdapter` retained blocked task identity for a soft
switching cost but discarded that authoritative tick, so both the public mask
and server-side selection validation admitted the same type/target immediately.
The adapter now retains and hashes the tick, masks only equivalent work while it
is not due, rejects a direct bypass as `retry_not_due`, and reopens the candidate
exactly at the reported boundary while leaving alternative work legal.

The full public-policy gate then exposed an adjacent lifecycle defect: a dead
fixed-step seat's controller stopped ticking while the adapter continued
heartbeating its assignment. The corrected runtime emits forced structured
`ABANDON(agent_death)`, releases reservations, wakes `task_terminal`, disables
all work actions immediately on the observed-death boundary, and permits only
board-neutral WAIT for that unavailable seat.

Both corrections change the rollout decision/action/state sequence. Existing
checkpoints remain historical evidence and cannot establish a candidate trained
under the corrected contract.

## Decision

1. V22 retrains from scratch under runtime contract
   `abandon_wait_retry_and_agent_death_boundaries_v3`.
2. V22 keeps V21's train/dev roots, reward, quality intervention, model,
   optimizer, RNGs, schedule, checkpoint-selection rule, teacher coefficient,
   and every other config field exact. Candidate ID, runtime contract, and
   confirmation path are the only differences.
3. Two pinned 2,048-episode replicas must reproduce the selected checkpoint,
   checkpoint frontier, model state, replay, full-run digest, and direct lineage.
4. Reusable dev-v1 must reach at least 9/10 construction wins, mean idle strictly
   below 0.25, and pass both permanent-greedy and matched-greedy scorecards.
5. Retire V21's unopened dev-v17. Freeze dev-v18 now at globally disjoint roots
   `181001..181160` for one exclusive confirmation only after all reusable gates
   pass. Held-out-v4 remains sealed.
6. Training may begin only after the exact-config reward adversaries, Python
   suite, pinned build, candidate-policy check, smoke, and determinism gates pass
   from this precommit.

## Alternatives

- Adding another abandonment penalty or teacher coefficient change was rejected
  because V21's structured trace identifies a violated runtime eligibility
  contract, not a missing reward signal.
- A fixed arbitrary cooldown was rejected because the skill already supplies an
  exact deterministic retry boundary.
- Masking every task after a block was rejected because eligibility is local to
  equivalent type/target work and alternatives must remain available.
- Leaving dead-seat cleanup to lease expiry was rejected because the stale
  controller continued issuing heartbeats, so the lease could never lapse.
- Replaying V21 inference under the new runtime may be diagnostic, but cannot
  replace governed from-scratch training.

## Consequences

- V22 changes no engine pin, reward component, structured communication
  authority, simulation-thread ownership, or framework-neutral boundary.
- Same-work retry eligibility and unavailable-seat lifecycle state are enforced
  by authoritative masks plus server validation and are included in deterministic
  state hashing.
- The frozen golden keeps two wins, 16,200 ticks, and 664 checkpoints; only hash
  fields change after retry eligibility joins canonical state, and the negative
  mutation still diverges.
- V22 may fail reproduction, construction, or either reusable scorecard. Any
  such failure stops before dev-v18 and held-out-v4.

Pretraining validation passes all 44 exact-config reward adversaries, the full
143-test Python suite, the pinned build, five-seed candidate-policy check, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`95bc200596718170b21e1aae47398486e6173996d7086d55af4d0e1a1757ee47`;
adversary report SHA-256 is
`18f337ac3ca54700b3b50ad193a33c292b578c3b376aa1a52156cbec93ab8998`.

## Outcome (2026-07-22)

Replica A completed all 2,048 training episodes and 32 updates, then stopped at
the precommitted dev quality gate. No frontier row had reported mean idle below
0.25 (`0.43868123..0.54747927`). Update 17 reached 10/10 wins but reported mean
idle `0.48320387`; update 32 also reached 10/10 at `0.47812454`. Replica B was
not started, dev-v18 remained unopened, and held-out-v4 remained sealed. The
deterministically reconstructed rejection frontier has SHA-256
`17d8afa6e7fb2f3360d327ef76d0ee082dc8fe3aa6d77926c532c7051ae380d4`.

Failure analysis found that the new honest agent-death cleanup exposed a metric
contract defect: `recordMetricsTick()` continued to count a permanently dead
fixed seat in both `agent_ticks` and `idle_agent_ticks`. That made impossible
post-death work look like policy idleness and also contaminated the idle reward
used during training. Re-evaluating update 17 diagnostically after partitioning
unavailable seat-ticks gives 10/10 wins and mean idle `0.13474577`, proving the
selection failure was metric-driven, but it cannot rehabilitate a checkpoint
trained with the contaminated reward. V22 is rejected. Its unopened dev-v18 is
retired, and any successor requires a fresh runtime contract, precommit, and
from-scratch exact replicas.
