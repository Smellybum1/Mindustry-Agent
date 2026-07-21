# ADR-0036: V25 moderate full-boundary teacher regularization

**Status:** Accepted

## Context

V24 isolated the resource-scoped retry decision sequence and completed all
2,048 training episodes, but its best reusable-dev checkpoint reached only
8/10 wins. It therefore stopped before replica B and dev-v20.

Reusable evidence identifies a bounded training-only hypothesis. Under the
same current runtime, adaptive-v1 wins 10/10 with mean idle `0.07308979` and
zero task abandonment. V24's best-ranked update 19 disagrees with that teacher
on 73 of 427 unforced decisions and loses seeds 2004 and 2005. V24 used a
full-boundary teacher coefficient of `0.05`. The historical `1.0` coefficient
failed badly under V10, so another large step is not justified; doubling to
`0.10` is the smallest precommitted moderate-strength test on the established
coefficient grid and remains tenfold below that failed value.

This auxiliary changes training loss only. It does not change reward,
inference, action masks, lifecycle, candidate generation, or evaluation.

## Decision

1. V25 retrains from scratch under the unchanged runtime contract
   `abandon_wait_resource_scoped_retry_agent_death_available_idle_v5`.
2. The only behavioral config change from V24 is
   `teacher_imitation_coefficient 0.05 -> 0.10`, mirrored in the optimizer
   manifest. Candidate ID, descriptive intervention label, and confirmation
   path change as governance metadata. Every reward, root, model, optimizer,
   RNG, schedule, and checkpoint-selection field remains exact.
3. Two pinned 2,048-episode replicas must reproduce checkpoint, complete
   frontier, model state, replay, full-run digest, and direct lineage. Replica B
   starts only if replica A passes the frozen construction gate.
4. Reusable dev-v1 must reach at least 9/10 construction wins, mean idle strictly
   below 0.25, and pass both permanent-greedy and matched-greedy scorecards.
5. Retire V24's unopened dev-v20. Freeze dev-v21 now at globally disjoint roots
   `211001..211160` for one exclusive confirmation only after every reusable
   gate passes. Held-out-v4 remains sealed.
6. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate-policy gate, smoke, and determinism
   including negative replay pass from this committed pretraining packet.

## Alternatives

- Repeating V24 was rejected because its deterministic recipe already failed
  the frozen construction gate.
- Increasing the data budget was deferred because the current-runtime teacher
  already demonstrates 10/10 behavior and V24 retains substantial disagreement;
  the direct loss coordinate is the narrower causal test.
- Restoring coefficient `1.0` was rejected because V10 produced only 1/10.
- Changing reward or runtime again was rejected because V24's idle is low and
  the action-mask defect is already closed.
- Opening dev-v20 was rejected because V24 failed before confirmation.

## Consequences

- V25 preserves engine pins, fixed stepping, simulation-thread ownership,
  structured-communication authority, and framework neutrality.
- A construction or reproducibility failure stops before reusable scorecards,
  dev-v21, and held-out-v4.
- Passing construction is not promotion; dual reusable scorecards and the
  exclusive confirmation/final gates remain mandatory.

No V25 model work began before this precommit.

Pretraining validation passes all 44 exact-config reward adversaries, the full
147-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`90b50d1b7add7fd0cf02a4ea9b225b701cb1e965c77f78b8a0388284c303687a`;
adversary report SHA-256 is
`8faa7834e426678e6da452d69f9b4b2ec0d99dd55d7f47140a3c9d433756254a`.

## Outcome

Replica A completed all 2,048 episodes and 32 updates, then correctly failed
the frozen construction gate. No checkpoint reached 9/10. Updates 16 and 17
were best at 8/10; update 16 has mean return `1.2083000000000041`, mean core
health `693.7`, and mean idle `0.06516475136727648`. The retained complete
frontier hashes to
`0ad699ece62ab94b75bfe19c704460611dc3ba7af653e3293d7d99591491f56e`.
Replica B did not start, dev-v21 remained unopened, and held-out-v4 remained
sealed.

The stronger coefficient changed optimization but not the best policy's
discrete behavior. V25 update 1 improved to 7/10 from V24's 1/10. At the best
checkpoint, the mean selected-minus-teacher logit gap over disagreement
boundaries fell from V24's `1.49301094` to `1.07148486`, but both candidates
still disagree on 73 unforced decisions and lose seeds 2004 and 2005. V25 is
rejected and dev-v21 is retired unopened.
