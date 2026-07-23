# ADR-0062: V45 residual lagged context

**Status:** Accepted

## Context

V44 reproducibly selects update 1 at 9/10 reusable wins, passes every observed
win comparison, but fails both frozen scorecards. Permanent idle decisively
regresses and several duplicate/recovery rows remain uncertain. Dev-v40 is
retired unopened and unconsumed; held-out-v6 remains sealed and unconsumed.

The full frontier distinguishes a bad checkpoint choice from an architecture
failure: update 1 is the only 9-win checkpoint and later checkpoints fall to
4-8 wins. V44 routed the exact bounded lagged context through a single 160->64
scalar encoder, replacing V43's proven 56->64 current-state path. The model can
no longer preserve the same-boundary policy while learning whether temporal
context helps. The residual-lag hypothesis remains untested.

## Decision

1. V45 retains V44's exact feature schema and V43's exact current-boundary set
   actor as a base path. Runtime, authority, masks, reward, teacher trajectory/
   relabeling, roots, budgets, optimizer, checkpoint ranking, RNG values,
   scripted seats, and engine pins remain V44-exact.
2. The first 56 scalars use a dedicated 56->64->64 Tanh encoder. The remaining
   104 lag values use a separate 104->64->64 Tanh encoder. Feature ordering,
   snapshot timing, zero initialization, padding semantics, and reset behavior
   remain `selector_features_v2_lagged_boundary` exact.
3. Base SELECT logits retain V43's candidate/current-scalar/other-candidate
   192->64->1 head. A temporal 256->64->1 head additionally consumes the lag
   embedding and produces a residual logit. Base CONTINUE/WAIT retain V43's
   current-scalar/all-candidate 128->64->2 head; a 192->64->2 temporal head
   produces their residual logits.
4. The output layers of both temporal heads are initialized to exact zero
   weights and bias. At construction, the actor is therefore exactly
   independent of lagged values while retaining ordinary seeded V43 base-path
   initialization. Training may move the residual away from zero.
5. Final raw logits are base plus temporal residual before the unchanged action
   mask. The critic remains V43's current-scalar plus all-candidate-pool
   128->64->1 path, isolating the tested coordinate to actor temporal routing.
6. Config selection and checkpoint identity fail closed. Tests must cover exact
   zero residuals, base-path lag independence at initialization, subsequent lag
   sensitivity after a controlled temporal-weight change, set equivariance/
   invariance, masks, deterministic initialization, and v1/v2/v3 compatibility.
7. The complete public/pretraining boundary and all 44 exact-config reward
   adversaries must pass before any dev-v41 construction or model run.
8. Replica A retains V44's exact budget and must reach at least 9/10 reusable
   wins with mean idle below `0.25` before replica B. Exact twins, direct
   lineage, fresh permanent baselines, all four win comparisons, and both
   reusable scorecards remain mandatory. Uncertainty is failure.
9. Dev-v40 stays retired unopened and unconsumed. V45 reserves primary-only
   dev-v41 at 160 roots in `[9_000_000_000,10_000_000_000)`. Membership may be
   created value-free only after the committed implementation/pretraining gate.
   Held-out-v6 remains sealed and unconsumed under ADR-0053.

## Alternatives

- Re-ranking the V44 frontier cannot help: no later checkpoint reaches nine
  wins, and update 1 already wins the frozen ranking.
- A full recurrent network is still broader than the evidence requires. V44
  tested temporal data only through a destructive bottleneck, not a residual
  path that preserves current-state behavior.
- Another reward, teacher, opening, or runtime prior is closed by earlier
  governed evidence and would not address V44's training collapse.

## Consequences

- V45 is a fresh construction; no V44 checkpoint may initialize or authorize it.
- The immutable config is
  `configs/training/m8-selector-v45-residual-lagged-context.json`, SHA-256
  `a7d0c8029acebe79dfc33224c96fdce89b33c043744dde222f8982053324be8c`.
- The confirmation umbrella is
  `configs/evaluation/m8-selector-v45-confirmation-umbrella.json`, SHA-256
  `e4fe0b56a95fa64cb59e5ea853c878b4d678f86c629bba72b393a68b5eb7b8f2`.
- This packet authorizes implementation only after commit. It does not authorize
  dev-v41 construction, replica A, confirmation, or held-out-v6 access.

## Implementation status

The config-selected v4 actor is implemented with V2-exact base module order and
weights, a separate lag encoder, exact-zero temporal output layers, residual
logit combination, unchanged critic, and dynamic checkpoint/model identity.
Focused tests prove construction-time equality with V43, exact lag independence,
learnable lag sensitivity after a controlled residual change, masks, set
symmetry, scalar-width failure, and v1-v3 compatibility.

The embargo-safe Python suite passes 273 tests. The 43 scenario-variation tests
last passed in the complete 310-test pre-dev-v40-freeze suite; they are not
rerun because that legacy module glob-reads every seed manifest, which would
violate retired dev-v40's no-read rule. Pinned Java, public 5/5 survival with
ten staging starts, both focused checks, smoke, determinism, 664-checkpoint/
16,200-tick golden and negative replay all pass. All 44 V45 reward adversaries
pass; report SHA is
`84cd359cf9cbd4014cf4cdb13cadf7b19c6f96c402fb66b22b1500696a06f660`.
Dev-v41 remains unconstructed; dev-v40 is retired unopened; held-out-v6 remains
sealed; no V45 training episode has run.
