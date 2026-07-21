# ADR-0019: Third post-failure renewal and preflight parity

**Status:** Accepted

## Context

V9 completed held-out-v3 and was not promoted. Like V8, it strictly CI-beat
both permanent win baselines but failed permanent-greedy teammate scorecards.
The development preflight had evaluated scorecards only against matched greedy,
while the final correctly evaluated both permanent and matched greedy. That
asymmetry allowed candidates to reach an irreversible final without proving the
actual quality contract on development evidence.

## Decision

1. Held-out-v3 is permanently consumed. Individual outcomes and traces are
   quarantined from future policy work.
2. Development preflight must load seed-level permanent-baseline records and
   require paired teammate-scorecard non-regression against both permanent
   greedy-utility and matched greedy. Missing or stale baseline records fail.
3. Preflight artifacts must hash the permanent record source, and the final
   validator must reject any changed source.
4. Freeze `bootstrap-defense-v1-held-out-v4` now, before another candidate is
   designed. It contains 160 unique roots `930001..930160`, globally disjoint
   from every prior governed split and refused by development tools.
5. A future immutable candidate config must name held-out-v4 and use a newly
   governed confirmation set under the corrected dual-scorecard preflight.
6. Held-out-v4 permits one exclusive final only after every corrected preflight
   gate passes. A started attempt consumes it.
7. Future design may use train/dev evidence and the aggregate fact that V9 was
   not promoted, never held-out-v3 seed-level outcomes or traces.
8. M9 remains gated on M8 promotion.

## Consequences

- The development gate now matches the final teammate-quality contract and
  should stop unsuitable candidates before consuming another held-out set.
- The larger v4 final improves interval precision but cannot compensate for a
  failed development scorecard.
- V8 and V9 remain reproducible non-promoted artifacts.

