# ADR-0067: Retire held-out-v6 after an unauthorized manifest read

**Status:** Accepted

## Context

During public-only M8 diagnostics on 2026-07-23, the primary agent searched
repository namespace metadata with a broad recursive `rg` command whose scope
included `configs/evaluation/`. That scope caused `rg` to open the sealed
`bootstrap-defense-v1-held-out-v6.json` manifest before any reusable or
confirmation gate authorized final access.

The command output displayed only the manifest's `seed_set_id` line. It did not
display any seed value, run an episode, produce an outcome, or use held-out
membership to choose behavior. Nevertheless, project policy defines any
manifest read as data access. Continuing to call held-out-v6 sealed would make
the repository's governance record false.

## Decision

1. Held-out-v6 is retired immediately as membership-exposed and unexecuted. It
   must never be used for training, diagnostics, confirmation, tuning,
   promotion, or final evaluation.
2. No held-out-v6 outcome exists. Public reusable results and all prior
   candidate decisions remain unchanged.
3. The next final set must be a value-free, primary-only held-out-v7
   construction in a globally disjoint numeric namespace. Its reservation,
   generator, one-way attempt contract, and receipt checks must be committed
   before membership is created.
4. Disjointness for the replacement must be established from reserved numeric
   namespaces and receipts only. No retired, confirmation, or final membership
   document may be opened to check it.
5. Repository searches for namespace/governance metadata must name explicit
   safe receipt, umbrella, ADR, or status paths. Broad searches over
   `configs/evaluation/` are prohibited while a sealed manifest exists.
6. Future tests may verify a sealed document's tracked existence and
   value-free receipt hash, but must not open the document.

## Consequences

- Held-out-v6 must be described as `retired_membership_exposed_unexecuted`, not
  sealed or unconsumed.
- M8 cannot complete against held-out-v6. A newly precommitted held-out-v7 is
  required before any final gate can become eligible.
- Because no seed value or outcome was rendered, the incident contaminates the
  final set identity rather than the learned policy or public evaluation data.
- This ADR supersedes ADR-0053 only for the usability and state of held-out-v6;
  ADR-0053 remains the historical record of its value-free construction.

## Replacement evidence

The held-out-v7 umbrella and primary-only freezer were committed at
`71d7fcf168` before construction. The freezer then created 160 roots in the
exclusive `[17_000_000_000,18_000_000_000)` namespace without reading any
retired or confirmation manifest or emitting a value. Its receipt SHA-256 is
`8b78b27153d597fba7a51691d8495c4d14d856445ef072e81b82c6517922a3b1`;
the sealed membership SHA-256 recorded by that receipt is
`f6d84b50d10ec6fc4141e826a74df6717db3659af7df12ea2cc11c22b8d98657`.
Held-out-v7 remains sealed and unconsumed.
