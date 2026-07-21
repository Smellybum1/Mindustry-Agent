# ADR-0037: V26 final full-boundary teacher step

**Status:** Accepted

## Context

V25 doubled full-boundary teacher regularization from `0.05` to `0.10`. It
accelerated early construction from 1/10 to 7/10 at update 1 and reduced the
mean selected-minus-teacher logit gap at disagreement boundaries from
`1.49301094` to `1.07148486`. Its best checkpoint nevertheless remained 8/10
with the same 73 disagreements and losses on seeds 2004 and 2005.

The directional logit movement supports one final bounded coefficient step.
V26 doubles `0.10` to `0.20`, still fivefold below V10's failed `1.0`. This is
the terminal fixed-coefficient experiment: failure to reach construction closes
the line rather than authorizing another coefficient increase.

## Decision

1. V26 retrains from scratch under unchanged runtime contract
   `abandon_wait_resource_scoped_retry_agent_death_available_idle_v5`.
2. The only behavioral config change from V25 is
   `teacher_imitation_coefficient 0.10 -> 0.20`, mirrored in the optimizer
   manifest. Candidate ID, label, and confirmation path are governance metadata;
   all reward, root, model, optimizer, RNG, schedule, and selection fields stay
   exact.
3. Replica B starts only if replica A reaches at least 9/10 wins with mean idle
   below 0.25. Passing replicas must reproduce checkpoint, complete frontier,
   model state, replay, full-run digest, and direct lineage.
4. Reusable preflight still requires both permanent-greedy and matched-greedy
   scorecards before any one-way confirmation.
5. Retire V25's unopened dev-v21. Freeze dev-v22 at globally disjoint roots
   `221001..221160`; it remains unopened until every reusable gate passes.
   Held-out-v4 stays sealed.
6. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate gate, smoke, and determinism
   including negative replay pass from a committed packet.

## Alternatives

- Another `0.10` replica was rejected because the deterministic recipe already
  failed construction.
- Jumping above `0.20` was rejected because `1.0` failed and the bounded logit
  trend does not justify a large step.
- Reward/runtime changes were rejected because this final test isolates the
  teacher-loss coordinate.
- Opening dev-v21 was rejected because V25 failed before confirmation.

## Consequences

- V26 changes training loss only; inference, reward, action masks, lifecycle,
  engine pins, fixed stepping, and communication authority remain unchanged.
- A construction failure retires dev-v22 unopened and closes the fixed full-
  boundary teacher-strength line.
- Construction success still does not imply promotion; exact reproduction and
  all scorecard/confirmation/final gates remain mandatory.

No V26 model work began before this precommit.

Pretraining validation passes all 44 exact-config reward adversaries, the full
148-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`b5e3bf17a1dc1acede170abd59b6adc86a4916fce13871254bef0abef4f6bae3`;
adversary report SHA-256 is
`202e71a48bf8a05fe88cf6f226cb0907b37c1e92a4a118e9fb9419467c03713b`.
