# ADR-0061: V44 lagged-boundary context

**Status:** Accepted

## Context

V43's masked candidate-set context is reproducible, wins all ten reusable roots,
and makes permanent-greedy recovery decisively favorable. It is still rejected
before confirmation because permanent-greedy announcements and idle are
favorable but uncertain, while matched-greedy recovery is uncertain. Dev-v39
is retired unopened and unconsumed; held-out-v6 remains sealed and unconsumed.

The remaining failures are temporal. Announcements measure decision churn,
idle depends on continued action across boundaries, and recovery is measured
after an agent-loss event. Yet `selector_actor_critic_v2_set_context` is
memoryless: it sees only the current authoritative boundary. The v1 feature
schema exposes the learned seat's previous selected task type and selection
age, but not the previous team/candidate state or previous action. On reusable
root 2004, V43 takes only five SELECT actions and 65 WAIT actions while reaching
idle fraction `0.0794107`; this single high-idle trajectory drives the uncertain
permanent idle interval. The same model cannot distinguish a newly changed
boundary from an otherwise similar repeated boundary.

Accepted evidence closes another reward, teacher, opening, runtime-prior, and
same-boundary candidate-routing coordinate. M8's accepted design permits a
temporal architecture after the feed-forward scorer fails the matched gate.

## Decision

1. V44 retrains the exact V43 recipe with one bounded temporal architecture
   coordinate. Runtime behavior, action vocabulary and authority, masks,
   reward, teacher trajectory/relabeling, roots, budgets, optimizer, checkpoint
   ranking, RNG values, scripted seats, and engine pins remain V43-exact.
2. Feature schema `selector_features_v2_lagged_boundary` retains the exact
   current 8x37 candidate rows and 56 current scalars. It appends exactly 104
   values from the immediately preceding authoritative decision boundary:
   its 56 base scalars, the masked mean of its present 37-value candidate rows,
   present-candidate count divided by eight, and a ten-way one-hot of the action
   index actually submitted by the learned seat. Initial lagged context is all
   zero and episode reset clears it.
3. Candidate presence, not action validity, defines the previous candidate
   mean. Padding is excluded. A boundary with no present candidates has a zero
   mean and zero count. The previous action is recorded even when forced; the
   canonical selector index maps ABANDON and WAIT to index 9, matching the
   existing training action seam.
4. History advances only after the environment accepts the externally stepped
   boundary response. Its snapshot is the features used for that action, never
   mutable engine state read after submission. Training, evaluation, matched
   controls, replay, and lineage must use the same deterministic update order.
5. Model schema `selector_actor_critic_v3_lagged_set_context` retains V43's
   candidate encoder, masked candidate pools, actor heads, and critic. Only the
   scalar encoder input changes from 56 to 160. This tests bounded temporal
   information without recurrent hidden state, backpropagation through time,
   or a new dependency.
6. Model and feature construction must be config-selected and fail closed.
   Historical v1/v2 features and model checkpoints remain exactly loadable and
   reproducible. Cross-feature or cross-model checkpoint substitution must be
   rejected.
7. Focused tests must cover exact lag order and dimensions, zero initialization,
   reset isolation, padding exclusion, previous-action encoding including
   forced WAIT/ABANDON, immutable snapshots, V43 compatibility, deterministic
   v3 construction, set equivariance/invariance, masks, and checkpoint mismatch.
8. The complete public/pretraining boundary is required before confirmation
   membership construction or model run: Python and pinned Java suites, public
   survival/staging, focused coordination checks, smoke, cross-process/reset/
   alternate-seed determinism, golden replay plus negative control, and all 44
   exact-config reward adversaries.
9. Replica A retains the exact 256-episode warmup and 2,048-episode/32-update
   V43 budget. It must reach at least 9/10 reusable wins with mean idle below
   `0.25` before replica B. Exact twins, direct lineage, fresh selected-only
   permanent baselines, all four win comparisons, and both reusable scorecards
   remain mandatory. Uncertainty is failure.
10. Dev-v39 stays retired unopened and unconsumed. V44 reserves primary-only
    dev-v40 at 160 roots in the exclusive `[8_000_000_000,9_000_000_000)`
    namespace. Membership may be created value-free only after this precommit
    and the full implementation/pretraining boundary are committed. Held-out-v6
    remains sealed and unconsumed under ADR-0053.

## Alternatives

- A GRU or LSTM is broader than the first temporal hypothesis requires and
  introduces hidden-state and sequence-minibatch complexity. One authoritative
  boundary of explicit context directly tests whether change/repetition is the
  missing information.
- A WAIT penalty, action-logit prior, or scripted recovery rule would alter
  incentives or runtime behavior and has no authority from the frozen scorecard.
- Hand-picking only an alive-change or WAIT-streak bit would encode the observed
  roots too narrowly. The bounded prior structured boundary is general,
  deterministic, and still compact.
- Reading confirmation membership to expand confidence is prohibited. A new
  architecture must earn access on the unchanged reusable gates.

## Consequences

- V44 is a fresh training construction. V43 checkpoints cannot initialize,
  interpolate into, or authorize V44.
- The immutable config is
  `configs/training/m8-selector-v44-lagged-boundary-context.json`, SHA-256
  `9a23c90567754eb84a06f47bfecfe99fd93ba85499167dd3bc3657ebfc9dc9c2`.
- The value-free confirmation umbrella is
  `configs/evaluation/m8-selector-v44-confirmation-umbrella.json`, SHA-256
  `4a526274d956872680cd16cb5fefb2b7f450931b9a9a83b7aa742034a45d09c8`.
- This ADR authorizes implementation and public/pretraining verification after
  this packet is committed. It does not authorize dev-v40 membership creation,
  replica A, confirmation consumption, or held-out-v6 access before their
  preceding committed gates pass.
