# ADR-0022: V12 quality-aligned reward v2

**Status:** Accepted

## Context

V11 won 137/160 on dev-v7 and passed every matched-team scorecard, but failed
permanent-greedy announcements, idle, recovery, and abandonment. V6 contains
621 successful train episodes, yet only two have idle fraction below 0.10, so
quality-filtered self-imitation has too few positive examples. Bias, blend, and
teacher-only interventions have not corrected team quality.

## Decision

1. Introduce `selector_reward_v2` as v1 plus four negative-only, cumulative-
   delta components from structured authoritative telemetry:
   - `-0.0001` per new idle agent tick (scenario maximum `-2.7`);
   - `-0.05` per new duplicate-work incident, capped at `-1.0`;
   - `-0.005` per new announced message, capped at `-1.0`;
   - `-0.1` per non-forced structured ABANDON by any team agent, capped at
     `-2.0`; v1's learned-seat liability remains separate.
2. Cumulative counters must be monotonic. Counter rollback, negative deltas, or
   missing required v2 fields fails the run. Exact deltas make reward invariant
   to decision-boundary chunking.
3. Forced wave/readiness/death/lease/human/terminal cleanup abandons remain
   excluded. The signal cannot reward messages, tasks, items, or raw progress.
4. V1 remains byte/behavior compatible by default. Checkpoints and manifests
   record their actual reward schema; cross-schema loading/interpolation fails.
5. V12 otherwise uses V6's 64-root, 32-cycle recipe and names held-out-v4.
6. Two pinned V12 runs must reproduce exactly. Dev-v1 continuation requires at
   least 9/10 wins and mean idle below 0.25.
7. Freeze dev-v8 now with 160 disjoint roots `81001..81160`. Only a V12 that
   meets the early bar may start its exclusive ADR-0019 dual-scorecard gate.

## Consequences

- Win/loss remains dominant: the maximum new penalty is `-6.7`, versus the
  `20`-point terminal win/loss gap.
- Negative-only shaping can encourage doing nothing; milestone, unresolved-
  tick, terminal, WAIT-only, and capped-signal adversaries remain mandatory.
- Dev-v8 and held-out-v4 stay sealed until the preceding gates pass.

