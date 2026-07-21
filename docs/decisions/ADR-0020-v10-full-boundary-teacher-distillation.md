# ADR-0020: V10 full-boundary teacher distillation

**Status:** Accepted

## Context

V9 was not promoted and ADR-0019 now requires development scorecard parity
against permanent and matched greedy. Reusable dev-v5 evidence shows V9 agreed
with adaptive-v1 on only 5.3% of 8,180 unforced decisions. Its mixed team had
mean idle fraction about 0.310 and abandonment rate about 0.202. Adaptive-v1 on
the same 80 dev roots won 61/80 with mean idle about 0.076 and abandonment about
0.118. Role assignment reduced idle further but won only 43/80 and greatly
increased duplicate work. Another WAIT-logit adjustment is therefore not an
adequate quality hypothesis.

The earlier V4/V5 auxiliary applied coefficients 0.05/0.10 only to unforced
samples from already successful on-policy episodes. It did not teach losing
episodes and is not evidence against full-boundary distillation.

## Decision

1. V10 uses the V6 64-root, 32-cycle PPO recipe and changes one training term:
   coefficient `1.0` cross-entropy toward adaptive-v1 on every unforced
   transition with a valid teacher action. Reward, features, model, masks,
   lifecycle, optimizer, RNGs, and evaluation behavior remain unchanged.
2. Historical configs default the new coefficient to zero. The all-boundary
   teacher loss and sample count are stored separately in optimizer telemetry.
3. V10's immutable config names held-out-v4 before implementation or training.
4. Two independent pinned runs must reproduce the selected checkpoint, replay,
   full-run digest, and teacher telemetry exactly.
5. Dev-v1 is only an early win/agreement screen. It cannot authorize held-out.
6. Freeze `bootstrap-defense-v1-dev-v6` now with 160 unique roots
   `61001..61160`, globally disjoint from every governed split. A started
   confirmation attempt consumes it.
7. Before dev-v6 confirmation, refresh permanent aggregate and exact seed-level
   records. Corrected preflight must strictly beat all observed win comparators
   and pass paired scorecards against both permanent greedy and matched greedy.
8. Only full dev-v6 eligibility may authorize held-out-v4. Failure or abort
   rejects V10; individual dev-v6 outcomes cannot tune a successor.

## Consequences

- The next experiment targets the largest permitted train/dev behavior gap
  without changing inference semantics or adding unaudited reward.
- Strong imitation can reduce PPO exploration or cap performance at the
  teacher. Win and dual-scorecard gates remain authoritative and can reject it.
- Held-out-v1 through v3 and dev-v2 through v5 remain consumed.

