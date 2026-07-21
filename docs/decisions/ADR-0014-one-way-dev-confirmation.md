# ADR-0014: One-way development confirmation after uncertain scorecards

**Status:** Accepted

## Context

The reproducible V6 selector won 9/10 on dev-v1 and beat every permanent and
matched comparator by observed win rate in the full preflight. Its idle,
recovery, and abandonment scorecard means were also better than matched greedy,
but their ten-pair bootstrap intervals crossed zero. Opening held-out-v2 on
uncertain development evidence would violate the promotion contract.

## Decision

1. Freeze `bootstrap-defense-v1-dev-v2` before executing any of its roots. It
   contains exactly 40 unique roots, `21001..21040`, disjoint from every fixed,
   train, dev-v1, held-out-v1, and held-out-v2 root.
2. Dev-v2 is a one-way confirmation set for the already frozen V6 checkpoint,
   not a new checkpoint-selection or hyperparameter-tuning set.
3. The confirmation runner creates an exclusive attempt marker before episodes
   execute and refuses existing marker/output artifacts. A started or completed
   attempt consumes dev-v2 for V6.
4. Permanent random-valid and greedy-utility baselines are refreshed on the same
   dev-v2 roots. The unchanged promotion preflight then evaluates learned,
   matched random, and matched greedy cells with the existing reward and paired
   scorecard gates.
5. V6 may proceed to held-out-v2 only if the one-way confirmation reports
   `eligible_for_held_out=true`. Any failure rejects V6. Individual dev-v2
   outcomes must not be used to revise a future policy.
6. Held-out-v2 remains sealed until confirmation completes successfully. Its
   exclusive final-attempt rule and every ADR-0013 promotion gate remain intact.

## Consequences

- The larger paired set can resolve dev-v1 sampling uncertainty without
  weakening a scorecard gate.
- Dev-v2 cannot become a repeated pseudo-held-out tuning loop.
- A later candidate requires newly governed confirmation evidence rather than
  reusing V6's consumed dev-v2 outcomes.

