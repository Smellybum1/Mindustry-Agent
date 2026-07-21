# ADR-0024: Scorecard v2 forced-abandonment semantics

**Status:** Accepted

## Context

The v1 teammate scorecard derives `task_abandonment_rate` from the cumulative
`tasks_abandoned` counter. That counter includes forced wave/readiness safety
preemption and lifecycle cleanup. Reward v2 and its accepted audit explicitly
exclude wave, readiness, death, lease, human, terminal, and cleanup reasons
because they are not discretionary policy churn. Reusable dev-v1 evidence
shows the mismatch materially: V13 has 36 forced `wave_preempt` events and 23
non-forced learned-seat resource replans. Counting both makes the scorecard
contradict the reward contract and obscures the actionable behavior.

## Decision

1. Introduce ladder/scorecard schema v2 for all future evaluation records.
2. `task_abandonment_rate` counts only structured `ABANDON` events whose
   normalized reason contains none of the accepted forced-exclusion tokens:
   wave, readiness, death, lease, human, terminal, or cleanup.
3. Its denominator is completed tasks plus non-forced abandons. The scorecard
   also records separate forced and non-forced abandonment counts so the
   exclusion remains auditable rather than deleting safety telemetry.
4. The authoritative coordination metrics expose cumulative forced and
   non-forced abandonment counters and per-agent idle ticks. These are
   simulation-thread-owned, reset in-process, and diagnostic only; total idle
   and total abandonment remain available for compatibility.
5. Existing v1 records and every consumed dev/held-out decision remain
   immutable. V13 stays rejected. Scorecard v2 applies only to newly generated
   baselines and candidates on a future, precommitted confirmation set.
6. Reward exclusions and scorecard exclusions must share adversarial tests for
   every token. Unknown/empty reasons remain non-forced and therefore charged.

## Consequences

- Safety preemption no longer appears as learned coordination churn, while its
  count and reason events remain visible.
- The correction cannot rescue or rerun V13, dev-v9, or any prior final set.
- Idle, announcements, recovery, duplicate work, wins, and all permanent-plus-
  matched comparison requirements remain unchanged.
