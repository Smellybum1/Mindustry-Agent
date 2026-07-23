# ADR-0064: M8 reusable-scorecard power correction

**Status:** Accepted

## Context

V43, V45, and V46 each reproducibly won all ten original reusable roots and
improved the means of the remaining quality rows, but were rejected because
paired 95% confidence intervals from only ten roots crossed zero. V46's frozen
result is the clearest example: permanent announcements and idle had favorable
means of `-0.00135566` and `-0.00538749`, while matched recovery was `-18.0`;
all three intervals remained uncertain.

A reusable-only ablation masked V46's DEFER action without changing its
checkpoint. It remained 10/10 and produced nearly identical failures:
announcements `-0.00120232`, idle `-0.00546685`, and matched recovery `-22.1`.
The ablation preflight SHA-256 is
`109d0bd5ef8ca1770ce0941170004127ec9bce88ac53d6e590cea4f68eab01fb`.
This rejects another small control-head refinement as the next justified
coordinate: the underpowered screen, not the DEFER mechanism, is currently the
dominant uncertainty.

After reviewing that evidence, the project owner explicitly authorized this
direction change on 2026-07-23. The change must correct statistical power
without weakening the scorecard rule or opening retired, confirmation, or
held-out membership.

## Decision

1. The paired scorecard confidence rule is unchanged: every observed required
   metric passes only when the 95% bootstrap interval's upper bound is at or
   below zero; uncertainty remains failure.
2. The canonical reusable scorecard screen moves from ten roots to 160 roots,
   matching the established confirmation/final set size. It uses the public
   `bootstrap-defense-v1-reusable-scorecard-v2` set in the exclusive
   `[11_000_000_000,12_000_000_000)` namespace.
3. Membership is generated before any v2 episode by pinned SHA-256
   domain/counter sampling. It is public after construction, but forbidden for
   training, checkpoint selection, hyperparameter selection, confirmation, or
   final claims.
4. The frozen V46 checkpoint
   `93694e4d70ec56e4677e8c3c66fdf657f19a833fae38975eba11ac56289f577a`
   receives exactly one v2 screen. No weight, config, lineage, checkpoint rank,
   reward, runtime behavior, or DEFER limit changes.
5. Fresh permanent random-valid/greedy-utility baselines and fresh matched
   random/greedy episodes must use the same 160 roots, runtime provenance, and
   committed evaluation identity. All four win comparisons, both scorecard
   families, reward evidence, lineage, reproducibility, and the inclusive
   `0.25` mean-DEFER cap remain mandatory.
6. The original ten-root result remains valid historical evidence but no
   longer decides reusable scorecard eligibility. It remains the checkpoint
   construction/selection set and cannot be used to tune this revision.
7. Dev-v42 stays retired unopened and unconsumed. A replacement confirmation
   set, dev-v43, is reserved now at 160 roots in
   `[12_000_000_000,13_000_000_000)`. It may be constructed value-free only if
   every reusable-v2 gate passes.
8. Held-out-v6 remains sealed and unconsumed. This protocol revision does not
   authorize reading its membership or running any final episode.
9. The immutable reservation umbrella is
   `configs/evaluation/m8-selector-v46-reusable-v2-umbrella.json`, SHA-256
   `d623e7cadffaff1e67c16d081fdfb20fe7c2aa2b523cd8d98bd0b66493feb8c9`.
   The membership generator and this ADR must be committed before construction.

## Alternatives

- Relaxing the confidence threshold, treating favorable means as passes, or
  dropping a scorecard row is rejected because it would weaken M8 after seeing
  outcomes.
- Training V47 before resolving the power defect is rejected because the same
  ten-root interval would remain unable to distinguish another favorable
  candidate from noise.
- Reusing retired dev-v42 or reading held-out-v6 is prohibited.
- Expanding the learned action surface again is not supported by the V46
  no-DEFER ablation.

## Consequences

- Evaluation cost increases, but M8.3 already certifies enough throughput and
  the stronger screen is still reusable-only.
- A V46 v2 failure leaves V46 rejected and informs one future precommitted
  candidate. A pass authorizes only value-free dev-v43 construction and its
  existing one-way confirmation gate, never direct final access.
- This ADR supersedes ADR-0063 only for reusable-screen sample size and the
  post-rejection v2 rescreen. All control, reward, determinism, threading,
  typed-action, and held-out rules remain in force.

## Construction evidence

The precommit packet was committed at `26d25acd64` before membership creation.
Its pinned generator produced 160 unique public roots without running an
episode. Membership SHA-256 is
`c529951782ec0426f94671ece39824d0057e303c2aa7edc11b3610a63c7f86f3`;
the receipt records zero dev-v42 or held-out-v6 reads and zero confirmation or
final episodes. Reusable-v2 is frozen and unevaluated.

Fresh permanent baselines won 62/160 random-valid and 84/160 greedy-utility.
The frozen V46 checkpoint won 96/160; matched random/greedy won 69/160 and
67/160. V46 passed the DEFER cap at `0.22788814` and every matched-greedy
scorecard row. It failed permanent greedy on announcements (mean
`-0.00016845`, CI `[-0.00413065,+0.00377476]`) and idle (mean `+0.00391218`,
CI `[-0.00166438,+0.00971554]`). Preflight SHA-256 is
`d272edd51197166b44f29e297ce713a3c66a46b7dc6ddb0f13bd8df9d11c4928`.
V46 remains rejected; dev-v43 is unconstructed and held-out-v6 stays sealed.
