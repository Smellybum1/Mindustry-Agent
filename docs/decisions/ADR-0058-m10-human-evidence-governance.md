# ADR-0058: M10 human evidence requires pin-compatible sessions and explicit comparisons

**Status:** Accepted

## Context

M10.4 records objective teammate metrics plus four explicit human judgments.
M10.6 requires targets across at least three distinct serious sessions, learned
performance no worse than the scripted team, and project-owner preference for
agents present versus absent on the same scenario. Per-session scorecards exist,
but no aggregation contract currently prevents unrelated policies, scenarios,
or runtimes from being pooled. Rating v1's `keep_this_team` answer is useful but
does not itself prove a paired agents-present versus agents-absent preference.

## Decision

1. Human evidence is aggregated only from complete capture plus digest-bound
   rating pairs. A scorecard alone is insufficient because it omits the capture's
   runtime, scenario, and policy pins.
2. Distinctness is the complete capture content SHA-256. Duplicate digests are
   rejected rather than double-counted.
3. Capture-v1 pin-compatible groups require exact equality of engine tag/commit,
   Arc version, protocol version, scenario id/version, and policy identity.
   This is not full executable equivalence: capture v1 lacks the project commit
   and built-artifact hashes and therefore remains acceptance-ineligible.
4. Only ratings explicitly marked `serious_session=true` count toward the
   roadmap's minimum-three-session floor. Smoke/probe ratings remain visible but
   do not count.
5. Meeting the session-count floor is readiness evidence, not acceptance. The
   report may summarize observed metrics but may not invent or infer scorecard
   thresholds after seeing human results.
6. Rating v1 does not prove agents-present versus agents-absent preference. A
   future paired-condition schema and target contract must be accepted before
   those acceptance sessions are collected. Likewise, learned-versus-scripted
   parity must use explicitly identified policy conditions.
7. Reports contain capture digests and public runtime/scenario/policy pins only.
   Human identity, display names, free text, chat, secrets, and wall-clock time
   remain excluded.
8. A versioned capture successor must add project and executable provenance
   before human sessions may count as final learned/scripted or north-star
   acceptance evidence. Existing v1 captures remain usable as exploratory
   operational baselines only.

## Alternatives

- Pool rated scorecard files directly: rejected because policy and scenario
  identity cannot be verified from scorecard v1.
- Treat three positive `keep_this_team` answers as north-star acceptance:
  rejected because this is not a paired present-versus-absent comparison.
- Choose scorecard thresholds after exploratory sessions: rejected as post-hoc
  acceptance design.
- Add identity fields to prove distinct humans: rejected; the roadmap requires
  distinct sessions, and identity collection is unnecessary and privacy-hostile.

## Consequences

- Scripted sessions can establish operational baselines now, but they cannot
  promote a learned team or close the north-star preference checkbox.
- The evidence report fails closed on duplicates and separates incompatible
  groups instead of producing a misleading global pass.
- Capture-v1 reports carry an explicit missing-executable-provenance blocker.
- A later ADR must precommit paired conditions and scorecard targets before M10.6
  acceptance collection begins.

## Reversal conditions

Supersede this ADR only with a versioned evidence protocol that retains exact
capture/rating binding, pin-compatible comparison, explicit human authority, and
privacy at least as strong as this decision.
