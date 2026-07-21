# ADR-0021: V11 V6/V10 governed blend

**Status:** Accepted

## Context

V10's coefficient-1.0 all-boundary teacher run reproduced exactly but collapsed
to 1/10 dev wins, so it cannot continue directly. Its model nevertheless
contains a substantially stronger adaptive-teacher prior than the successful-
episode V4 auxiliary. V7 established that a 90/10 interpolation can preserve
V6's 9/10 dev capacity while transferring a teacher-trained prior. V10 and V6
share the same initialization, architecture, feature, reward, and model schema.

## Decision

1. V11 is constructed once as 90% reproducible V6 update 31 and 10%
   reproducible V10 update 6. The weights are fixed by the successful V7
   precedent, not swept.
2. Both parent pairs must reproduce exactly. Cross-commit lineage must validate
   the recorded training commits, configs, updates, manifests, checkpoints, and
   model-state digests before interpolation.
3. V11 names held-out-v4 in its immutable config. Reward, features, masks,
   lifecycle, architecture, and inference code do not change.
4. V11 must reach at least 9/10 dev-v1 wins or stop before confirmation.
5. Dev-v6 was never opened but remains reserved to the rejected V10 contract.
   Freeze dev-v7 now with 160 disjoint roots `71001..71160` for one exclusive
   V11 confirmation after dev-v1 qualification.
6. Dev-v7 must use ADR-0019's exact permanent records and dual scorecards. Only
   full eligibility may authorize held-out-v4.

## Consequences

- The teacher prior is tested at a bounded strength without another training
  run or a coefficient sweep.
- Failure rejects V11 and consumes no held-out evidence.
- Dev-v2 through v5 are consumed; dev-v6 is retired unopened; held-out-v4
  remains sealed.

