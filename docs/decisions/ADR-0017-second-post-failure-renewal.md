# ADR-0017: Second post-failure held-out renewal

**Status:** Accepted

## Context

V8 completed the exclusive held-out-v2 final and was not promoted. It achieved
strict win-rate CI separation but failed required teammate-quality scorecards.
Held-out-v2 is consumed permanently. Individual outcomes and traces are
quarantined from all future policy design.

## Decision

1. `bootstrap-defense-v1-held-out-v2` is permanently consumed and cannot be
   rerun for selection, diagnosis, or promotion.
2. Freeze `bootstrap-defense-v1-held-out-v3` now, before another candidate is
   designed or trained. It contains 80 unique roots `920001..920080`, globally
   disjoint from every fixed, train, development, and earlier held-out root.
3. Development tools must refuse held-out-v3. Tests may inspect only its exact
   contract and disjointness; they must never execute its scenarios.
4. A future candidate's immutable config must name held-out-v3 before model
   work begins and must use newly governed development/confirmation evidence.
5. Held-out-v3 permits one exclusive final attempt after every existing win,
   reward, lineage, repository, matched-control, and teammate-scorecard gate
   passes. A started attempt consumes the split.
6. Future policy decisions may use train/dev evidence and the aggregate fact
   that V8 was not promoted, but not v2 seed-level outcomes or traces.
7. M9 remains gated on a promoted M8 selector unless a later accepted ADR
   explicitly changes that dependency.

## Consequences

- Eighty roots provide finer win and scorecard intervals while being selected
  before future learning.
- V8 remains a reproducible research artifact, not a promoted policy.
- Another failed or aborted v3 final would require a new accepted renewal ADR
  before any further one-way evaluation.

