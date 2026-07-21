# ADR-0013: Post-failure held-out renewal

**Status:** Accepted

## Context

The first governed M8.5 promotion attempt consumed
`bootstrap-defense-v1-held-out-v1`. The candidate was not promoted. That final
evaluation is immutable: its individual seed outcomes and traces are
quarantined from policy development, and the split cannot be reused for a
revised candidate.

Continuing model work requires a new final-evaluation split whose identity and
membership are frozen before the next algorithm, checkpoint, or selection rule
is chosen. The original ten-seed set also produced coarse confidence intervals,
so the successor set should be larger without being selected in response to a
new candidate.

## Decision

1. `bootstrap-defense-v1-held-out-v1` is permanently consumed. It must never be
   rerun for selection or promotion, and its individual outcomes must not inform
   future policy changes.
2. `bootstrap-defense-v1-held-out-v2` is the sealed successor final set. It has
   scenario version 2 and exactly 40 unique root seeds, `910001` through
   `910040` inclusive.
3. The v2 roots must remain disjoint from every fixed, training, development,
   and v1 held-out root for this scenario.
4. Development tools must refuse to execute any seed set whose split is
   `held-out`, including v2. Tests may inspect the seed-set document only to
   verify sealing, exact membership, and global disjointness; they must not run
   scenarios from it.
5. Before any future M8 training begins, its immutable candidate configuration
   must explicitly name `bootstrap-defense-v1-held-out-v2` as the final set.
6. V2 permits one exclusive final attempt. The attempt marker must be created
   before held-out membership is loaded, and completed attempts cannot be
   overwritten or retried.
7. The established promotion gates remain in force: frozen lineage and repo
   state, development preflight, permanent and matched baselines, confidence
   interval evidence, reward validation, and scorecard non-regression.
8. A failed M8 promotion cannot be bypassed by silently starting M9. M9 remains
   gated until a selector is promoted or a later accepted ADR explicitly
   changes that roadmap dependency.

## Consequences

- The next candidate may be designed only from training/development evidence
  and precommitted hypotheses, not from v1 held-out outcomes.
- Forty roots provide finer promotion evidence than the original ten while
  being chosen before new learning begins.
- Any v2 final result is terminal for that candidate and consumes the split;
  another post-failure continuation would require another accepted ADR and a
  newly frozen disjoint split.

