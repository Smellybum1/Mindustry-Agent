# ADR-0051: Selected-only baseline loading and runtime provenance

**Status:** Accepted

## Context

Reusable promotion evidence must identify exactly which seeds, configuration,
repository state, runtime JAR, and selected checkpoint produced every baseline
and candidate episode. The historical baseline registry mode can resolve and
load more than the selected entry, and older invocation paths can infer a seed
set or invoke Gradle implicitly. Those conveniences are useful for legacy local
analysis, but they are unsafe at a promotion boundary: an unused registry entry
can trigger an embargoed membership read, an inferred set can cross a declared
split, and a rebuilt or replaced JAR can make apparently matched records
incomparable.

V38 also needs a reusable-only rejection decision before any confirmation set
is opened. That requires a direct, auditable path that cannot read confirmation
membership as a side effect and that rejects stale runtime provenance before
promotion evidence is accepted.

## Decision

1. Governed permanent-baseline evaluation loads only explicitly selected seed-
   set manifests. It does not enumerate or eagerly load the legacy seed-set
   registry. Candidate and matched-control evaluation continues to use the
   explicit checkpoint, config, lineage, and seed-set inputs of the promotion
   command.
2. `--seed-set-file` is explicit-only. A governed run must supply it directly;
   no default, inferred registry entry, or neighboring manifest may select the
   episode roots.
3. Every governed invocation declares its split. A held-out split requires the
   one-way pre-read gate before any semantic membership load. Reusable and
   confirmation runs must not share an invocation or resolve each other's seed
   files as a side effect.
4. The runner does not invoke Gradle implicitly. The caller must prebuild the
   repository fat JAR; the runner resolves it fail-closed and records the
   configuration SHA-256, repository commit, and JAR SHA-256 used for the
   episodes.
5. Promotion comparison is fail-closed on provenance. Missing, mismatched, or
   stale configuration, repository, JAR, checkpoint, or seed-set provenance
   rejects the comparison rather than warning and continuing.
6. The guard implementation is commit
   `9bc96f91c7219ad9e9656f99b29f15331b78b399`. Its Python suite passes 176/176.
   The exact-config reward audit remains green at 44/44, report SHA-256
   `e44865297a31ab1625bf4a43116cf1ff712b96657043c200c0af629ddd4f59bf`.

## Legacy compatibility

The registry loader remains available for historical, non-promotion workflows
whose callers depend on its multi-entry behavior. It is not silently redefined:
legacy records can still be reproduced through that explicit compatibility
path. Such output is diagnostic only unless it is converted to the selected-
only contract and passes all current provenance checks. Promotion, confirmation,
and final evaluation must never fall back to registry discovery.

This preserves old analysis entry points without allowing their broad loading
semantics to weaken the current sealed-data boundary. A legacy caller that omits
the explicit seed-set file or runtime provenance now fails at the governed
boundary; compatibility is not an authorization bypass.

## Consequences

- Reusable baseline generation is deterministic and attributable to one direct
  policy selection and one declared seed set.
- A runtime rebuild or repository/config drift requires fresh baselines; stale
  artifacts cannot be promoted by path or label alone.
- Held-out membership remains protected until its one-way gate authorizes the
  first read. Reusable rejection can complete without inspecting confirmation
  or held-out membership.
- Callers must build the runtime explicitly before evaluation. A missing fat
  JAR is an error rather than permission to invoke Gradle.
