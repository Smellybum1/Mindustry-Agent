# ADR-0068: V49 prospective operational non-inferiority protocol

**Status:** Accepted

## Context

M8's scorecard gate currently labels a metric non-regressing only when the
paired 95% bootstrap interval for candidate-minus-baseline has an upper bound
at or below exactly zero. That is not merely a non-regression test: it requires
statistical evidence that every observed quality metric is at least as good as
the baseline.

ADR-0064 increased the reusable screen from 10 to 160 roots without changing
that zero-margin rule. The larger screen correctly rejects material
regressions, but it also confirms the mismatch between the name and the
decision. V47 wins 125/160 versus permanent greedy's 84/160 while its mean idle
is slightly favorable. It is rejected because the idle interval extends only
to `+0.00412952`, plus one automatic `plan_removed` event produces an
abandonment interval ending at `+0.00045732`. V47 update 32 removes
abandonment and improves mean idle to `-0.00288642`, yet remains rejected
because its interval ends at `+0.00107884`.

Public-only diagnostics also reject per-seat cached retraining, direct-WAIT
escape, retiring learned authority after death, and forcing a legal non-WAIT
fallback. Another policy wrapper is not supported by the evidence.

The project owner explicitly authorized a direction change on 2026-07-23. A
post-hoc pass on reusable-v2 would still be invalid. Any corrected
non-inferiority rule must therefore be fixed before a fresh reusable membership
exists, keep the candidate weights fixed, and preserve the strict held-out win
criterion.

ADR-0067 separately retires held-out-v6 after an unauthorized manifest read
that exposed no seed value or outcome.

## Decision

1. V49 changes evaluation governance only. Its learned behavior is exactly
   V47's reproducible selected update 25: config
   `ff112f910c13603c...`, checkpoint `ea821b97dd1e6f4c...`, and model state
   `ae3affeea7c1d22f...`. No weight, checkpoint rank, runtime action, reward,
   feature, failover rule, training root, optimizer, or RNG changes.
2. Scorecard pass/fail becomes prospective operational non-inferiority.
   Candidate-minus-baseline remains lower-is-better. Every observed metric
   must have both its mean and paired 95% bootstrap upper bound at or below its
   immutable metric margin. Uncertainty beyond the margin remains failure.
3. Margins are defined from bounded operational units, not V47's observed
   gaps:
   - announcements per meaningful transition: `0.01`, one additional
     announcement per 100 transitions;
   - duplicate-work incidents: `0.05`, one additional incident per 20
     episodes;
   - idle fraction: `1/150`, one additional second in a 150-second episode;
   - recovery after agent loss: `60` ticks, one second;
   - non-forced task-abandonment rate: `0.01`, one additional abandon per 100
     terminal tasks;
   - time to help: `60` ticks, one second.
4. Historical protocols retain an implicit zero margin and reproduce their
   decisions exactly. The new rule is activated only by the exact V49 protocol
   document and its hash must appear in reusable, confirmation, and final
   reports.
5. V49 receives exactly one fresh public reusable-v3 screen over 160
   deterministic roots in `[15_000_000_000,16_000_000_000)`. Membership is
   generated only after this ADR, protocol, and generator are committed.
   Reusable-v2 cannot decide V49.
6. All existing reusable gates remain mandatory: candidate wins versus both
   permanent baselines and both matched controls, both greedy scorecard
   families, mean DEFER at or below `0.25`, one learned brain, reward
   adversaries, lineage, and reproducibility.
7. If reusable-v3 passes, dev-v45 is retired unopened/unconsumed and one
   primary-only dev-v46 confirmation may be constructed in
   `[16_000_000_000,17_000_000_000)`. Its membership and result are one-way.
8. Held-out-v6 is retired membership-exposed and unexecuted under ADR-0067.
   Held-out-v7 is reserved at 160 cryptographically sampled roots in
   `[17_000_000_000,18_000_000_000)`. It must be frozen value-free from a
   committed primary-only generator and remain sealed until reusable-v3 and
   dev-v46 both pass.
9. Final promotion still requires the learned candidate's held-out win-rate
   95% interval lower bound to be strictly above both permanent random and
   permanent greedy upper bounds, plus operational non-inferiority versus both
   greedy scorecards. This ADR does not relax the primary success criterion.
10. Any V49 reusable, confirmation, or final failure ends this protocol. Its
    margins, candidate, sets, or sample sizes cannot be revised in response.

## Alternatives

- Applying margins to the already observed reusable-v2 result is rejected as
  post-hoc acceptance.
- Selecting V47 update 32 is rejected because reusable-v2 was used to identify
  it; V49 keeps the originally selected reproducible checkpoint.
- Increasing reusable sample size again is rejected: 160 roots already expose
  the zero-margin semantic problem rather than mere low power.
- Dropping idle or abandonment is rejected; all six scorecard metrics remain.
- Weakening held-out win CI separation is rejected.
- Continuing one-coordinate policy variants is rejected until this
  prospectively frozen governance question is resolved.

## Consequences

- ADR-0064 remains the historical reusable-v2 decision but is superseded for
  future scorecard pass thresholds by this protocol.
- The implementation must accept explicit per-metric margins, default to zero,
  validate exact metric coverage and finite nonnegative values, and include the
  protocol identity in every governed artifact.
- Fresh evaluation cost increases by one reusable, one conditional
  confirmation, and one conditional final ladder. No training run is required.
- The immutable protocol is
  `configs/evaluation/m8-selector-v49-noninferiority-protocol.json`, SHA-256
  `6711d6e43fab8f65b21d97f091767c963f85458147fc43e47b8fd96b67c3b965`.
  The generator commit is recorded before reusable-v3 membership is
  constructed.

## Construction and result

The protocol and deterministic reusable-v3 generator were committed at
`d5b9dc4bd2` before implementation or membership. Margin-aware reusable,
confirmation, and final gates were committed at `38cccc05da`; the historical
zero-margin path remains byte-compatible in its decision fields. The full
Python suite passes 370 tests.

Reusable-v3 was then constructed at 160 public roots in `[15B,16B)` with
membership SHA-256 `8655fe3c785ba99e40fe8186643ddff731e1cfa36aa157594bb30f0ced9affe5`.
Fresh permanent random and greedy won 61/160 and 82/160. The unchanged V47
checkpoint won 123/160; matched random and greedy won 58/160 and 24/160. All
four observed win comparisons, matched-greedy scorecard, mean DEFER
(`0.163862 <= 0.25`), one-brain authority, reward, lineage, and reproducibility
gates pass.

V49 nevertheless fails its prospectively frozen permanent-greedy idle margin.
Candidate-minus-greedy idle is `+0.00567867`, with paired 95% CI
`[-0.00022269,+0.01242934]`; the upper bound exceeds the immutable `1/150`
margin. Preflight SHA-256 is
`4834b8c2832a0b6a2185307eedcddd6a57c5e7b049e07de491dbfcd83cc41158`.
V49 is rejected before confirmation. Dev-v46 was never constructed and
held-out-v7 remains sealed/unconsumed. The committed public result SHA-256 is
`9e2f31ee8053b296fa8695ecab5f98308782e9c7be60b1570721e552952100d7`;
the final 371-test Python suite, smoke, determinism, and
664-checkpoint/16,200-tick golden replay pass.
