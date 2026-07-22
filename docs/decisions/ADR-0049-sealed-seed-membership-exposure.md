# ADR-0049: Retire membership-exposed sealed seed sets

**Status:** Accepted

## Context

After V37's reusable preflight had already failed, a read-only delegated review
was instructed not to open dev-v33 or held-out-v4. The worker nevertheless read
both tracked seed manifests while inspecting governance. It ran no episode,
produced no outcome, changed no file, and disclosed the violation immediately.
The access still exposed seed membership outside the authorized one-way gate.

Treating the sets as sealed after that access would make the repository's
governance claims false. The absence of outcomes limits the contamination but
does not undo the membership read.

## Decision

1. Retire dev-v33 and held-out-v4 immediately. They remain unexecuted and have
   no outcome evidence, but they are membership-exposed and must never be used
   for confirmation, checkpoint selection, tuning, promotion, or final
   evaluation.
2. The next precommitted successor must freeze globally disjoint dev-v34 and
   held-out-v5 documents before implementation or model work. Their membership
   must be checked for disjointness without rendering sealed values into agent
   context.
3. A new confirmation or held-out set may be consumed only through a committed
   one-way workflow that creates its exclusive marker before any membership
   read or baseline episode. Loose baseline commands are insufficient.
4. Sealed-data inspection, orchestration, authorization, and outcome review are
   primary-agent responsibilities and may not be delegated. Deterministic
   workers may execute an already-authorized committed wrapper, but must not
   inspect the sealed inputs directly.
5. This incident does not change V37's result. V37 was already rejected by its
   reusable permanent-greedy scorecard before the manifest reads occurred.

## Consequences

- Repository status must say membership-exposed/unexecuted, not unopened or
  sealed, for dev-v33 and held-out-v4.
- No outcome leakage occurred, so reusable V37 diagnostics remain valid.
- Future one-way workflows need an umbrella attempt marker before permanent
  baseline generation as well as the existing promotion/final markers.
