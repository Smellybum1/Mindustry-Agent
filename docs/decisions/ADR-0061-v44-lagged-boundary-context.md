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

## Implementation status

The config-selected v1/v2/v3 feature/model path is implemented. Lagged history
uses immutable plain-number snapshots, is zero-initialized per episode, advances
only after a returned step boundary, and is shared by training, evaluation, and
matched lifecycle controls. Checkpoints, manifests, direct lineage, dev
preflight, and final evaluation now bind both feature and model schemas;
historical v1/v2 configs and checkpoints remain compatible.

The complete 2026-07-23 pretraining boundary passes 305 Python tests and the
pinned Java suites/classes. Public policy passes 5/5 with ten proactive staging
starts; secondary-claim and owned-schematic checks pass; smoke passes; cross-
process, reset, and alternate-seed determinism remain
`20a97f36407167597981e77c`, `a2cf4a73ee901c844f30f486`, and
`495ba05fa71697bdc8ff2951`. Golden replay passes 664 checkpoints / 16,200 ticks
/ two wins and its negative mutation is detected. All 44 exact-config reward
adversaries pass; the ignored report hashes to
`740aba578809911829448076e76a430bbb9ed819f7d99037e44c95726934bf9c`.
Dev-v40 remains unconstructed, dev-v39 remains retired without a membership
read, held-out-v6 remains sealed, and no V44 training episode has run.

The primary-only dev-v40 freezer is implemented and fails closed against the
exact committed config/umbrella hashes, repository paths, candidate identity,
count, `[8B,9B)` namespace, and sealed-final binding. It atomically creates the
membership and a value-free receipt without reading any membership document.
All 310 Python tests pass. The freezer has not executed and dev-v40 remains
unconstructed until this tool commit becomes an ancestor of `HEAD`.

The committed freezer at `6b7a6c5dca` then created dev-v40 value-free in the
reserved namespace. The membership and receipt hashes are
`05ca1f48227581fcbf29d3c60d96fa8bd06567737189c69528b45175f42d0515`
and `acffc919ab1c40e24f0881bf6db746b2fa8108cc4056036dc54038fbe24d2c31`;
the receipt reports `values_emitted=false`, zero membership-document reads, and
no generated, retired-confirmation, or sealed-final read. Dev-v40 is frozen
unconsumed. Replica A remains prohibited until this membership/receipt packet
is committed.

## Outcome

The membership/receipt packet was committed at `b510cc48a1` before model work.
Two independent pinned WSL Torch 2.12.1 constructions from that exact commit
select update 1 at 9/10 reusable wins, mean return `3.68136`, mean core health
`450.9`, and mean idle `0.07252723633246042`. All 32 checkpoint files and the
canonical manifests reproduce exactly. Checkpoint, model-state, replay, and
full-run hashes are
`4e51d31bd4f33a675d11d89f57c4e958b7d24ce989c1986d50aa32479fcd60ff`,
`c484b19a9dcd7411ab4841c21bb40f82c6080ce0bc2757c76c2382c166a7a45a`,
`a5ac208b8ea91f19...`, and
`029e77830406127a87cd20016c92cfe96339c03892547d8f9e617dc3377e195e`.
Direct-lineage digest/artifact hashes are `aa799280368304ae...` /
`d0870fd199d0233e...`.

Fresh permanent random/greedy baselines remain 4/10 and 8/10. V44 is 9/10
versus matched random/greedy 5/10 and 6/10, so every observed win comparison
passes. The temporal coordinate makes matched announcements decisively
favorable and retains decisive permanent recovery, but the frozen dual
scorecards reject V44: permanent idle decisively regresses (mean
`+0.05680669`, CI `[+0.04001655,+0.07345166]`); permanent announcements and
duplicates are uncertain; and matched duplicates, idle, and recovery are
uncertain. Records/aggregate/report hashes are `3ec9dfa9504f93e2...` /
`b364484245ec0213...` / `260625f302f3e268...`.

The frontier explains the architecture failure rather than a checkpoint-ranking
failure: update 1 is the only 9-win checkpoint; later updates fall to 4-8 wins.
The 160->64 scalar encoder displaced V43's dedicated current-state path and the
construction collapses after its early checkpoint. V44 is rejected before
confirmation. Dev-v40 is retired unopened and unconsumed without a membership
read. Held-out-v6 remains sealed and unconsumed. A successor must preserve the
V43 current-state path and add temporal information as a bounded residual.
