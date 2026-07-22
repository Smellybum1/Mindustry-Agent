# ADR-0053: V39 sealed-test read repair and replacement final

**Status:** Accepted

## Context

After ADR-0052's implementation gates passed, primary review found that the
historical V38 seed-governance test opened both frozen membership documents to
recheck values and disjointness. Running the full Python suite therefore read
held-out-v5 before authorization. No episode, outcome, individual seed value,
or delegated access occurred, but project policy defines a manifest read as
data access. Held-out-v5 is retired immediately. Dev-v34 was already retired.

Dev-v35 was then constructed primary-only from its committed umbrella after all
V39 implementation gates passed. Its value-free receipt records zero prior
membership reads, no held-out access, a partitioned numeric namespace, and no
emitted values. It remains frozen and unconsumed.

## Decision

1. The unsafe historical test must never open governed membership again. It
   verifies existence and the committed value-free receipt only.
2. Held-out-v5 is retired without outcomes. It cannot be used for V39 or any
   later candidate.
3. Held-out-v6 is reserved before creation at 160 roots in the exclusive
   `3_000_000_000..3_999_999_999` namespace. Legacy roots are below one
   billion, V38 sealed roots occupy `[1B,2B)`, and dev-v35 occupies the signed-
   int tail beginning at two billion. Disjointness therefore requires no
   membership read.
4. V39 changes only held-out identity/version from v5/5 to v6/6. The partner-
   intent behavior, model, reward, optimizer, roots used for training/reusable
   evaluation, RNGs, budget, and checkpoint selection remain exact. The
   revised config SHA-256 is
   `54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924`.
5. The replacement umbrella binds the value-free dev-v35 receipt and reserves
   held-out-v6. Neither membership may be delegated or opened before its
   existing one-way gate. ADR-0051 remains authoritative.

## Consequences

- ADR-0052's initial config hash and held-out-v5 binding remain historical;
  this ADR supersedes only that final-set metadata.
- Exact-config reward evidence must be regenerated for the revised hash.
- Runtime/public/determinism results remain valid because no behavior field or
  runtime code changed.
- No model work may begin until the replacement-final umbrella and freezer are
  committed and held-out-v6 is frozen value-free.

The primary-only freezer was committed at `dbb3955ab9` before construction.
Its value-free receipt records zero membership reads and no confirmation or
retired-final access. The receipt SHA-256 is
`4f31a7078e5cd45628c4c8e25843b7baac4c598c40782870942ec9559d3b9d3e`;
held-out-v6 membership SHA-256 is
`2bf4aa04ef54d873e961ff367db849c14c72b83bb4d280c4e31ba75bdeefa51c`.
Held-out-v6 remains unconsumed and no values were emitted.
