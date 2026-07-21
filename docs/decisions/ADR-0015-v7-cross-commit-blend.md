# ADR-0015: V7 cross-commit blend and one-way confirmation

**Status:** Accepted

## Context

V6 reached 9/10 dev-v1 but was rejected when its one-way dev-v2 confirmation
aborted after marker creation. No confirmation outcomes were persisted and
held-out-v2 remains unopened. A successor must be a new policy, use only
train/dev evidence, and cannot reuse dev-v2.

## Decision

1. V7 is a deterministic 90/10 model-state interpolation of two reproducible,
   aligned parents: V6 update 31 (`4d3cacb8...`) and teacher-regularized V4
   update 5 (`8f25b0cc...`). The choice uses only their frozen train/dev
   evidence: V6 supplies 9/10 capacity and V4 supplies a structured teacher
   prior. No dev-v2 or held-out-v1 outcome informs the blend.
2. Cross-commit interpolation must name each parent's full training commit and
   validate it against the run manifest. Both parents retain exact config,
   checkpoint, update, model-state, reproducibility, schema, and dirt checks.
3. Two independent constructions, using the A and B replicas respectively,
   must produce identical checkpoint bytes and lineage evidence.
4. V7 first runs the ordinary dev-v1 screen and full scorecard preflight. It
   must beat every observed win comparator before confirmation.
5. Freeze `bootstrap-defense-v1-dev-v3` now, before V7 construction. It contains
   40 unique roots `31001..31040`, globally disjoint from every prior split.
6. If dev-v1 qualifies, V7 gets one exclusive dev-v3 confirmation attempt with
   freshly matched permanent baselines. A started attempt consumes dev-v3.
   Failure or abort rejects V7; individual outcomes cannot tune a successor.
7. Only a successful dev-v3 confirmation may authorize the still-sealed,
   exclusive held-out-v2 final under ADR-0013.

## Consequences

- V7 is materially distinct from rejected V6 while preserving deterministic
  fixed-step inference and the same one-seat typed action surface.
- Historical run commits remain immutable evidence instead of being rewritten
  to match the construction commit.
- Dev-v2 remains consumed and is never reused.

