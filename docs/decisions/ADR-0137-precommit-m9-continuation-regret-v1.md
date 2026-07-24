# ADR-0137: Precommit M9 counterfactual continuation regret v1

**Status:** Accepted

## Context

The exact rejected update-64 candidate-native actor wins 13/40 public-dev
roots. Candidate-native planner v11 wins 32/40, with 19 planner-only wins and
median three-seat task-family occupancy mismatch `0.5982906`. Accepted
ADR-0132 therefore supports trajectory supervision as a real signal, while
ADR-0126 closes disagreement as a direct intervention target. Scalar
disagreement pressure, online correction, recurrent NLL, maximal label
freshness, a plan head, and same-boundary pairwise joint NLL have all failed
construction. ADR-0136 prohibits a sweep of the rejected joint head.

The owner authorized one new evidence-supported mechanism-level architecture
or supervision class using public data only. A Pro consultation supplied
`mindustry_m9_new_architecture_plan.md`, SHA-256
`ebdada91825ad27e2132248c4a4bb7722f0434efb7eb85038229f7acfd21d201`.
That file is untrusted advice, is not a repository or runtime dependency, and
was independently checked against the accepted decisions and deterministic
runtime invariants.

The useful new class in that advice is offline cost-sensitive
counterfactual-continuation supervision. Its proposed disagreement-selected
states, explicit planner-top branch injection, 64-boundary horizon, and
98,304-branch budget are not adopted: the first two conflict with the closed
direct-correction line, and the latter two are not proportionate to the public
episode length or prior proven collection budget.

## Decision

Freeze `m9-candidate-native-continuation-regret-v1` before implementation,
collection, or optimizer update. Its complete machine-readable contract is
the configuration/public protocol whose SHA-256 values are
`947b09c84528005d752c976ce220bff51070f9764b243a27b2a387c0f6b9add1`
/
`7cb2881bd2ca388e8babef5127ece4ea872464bae61838c023476e13f5110ac7`.

The exact rejected update-64 actor model is loaded and frozen. Its file,
content, and model-state hashes remain
`cbfde7e932e718f49b6e80f79bfd2b0072fa2bb7fd1f04e4ca0d7da9ee8ed408`,
`55005ab5a0591b2688e32a4819678088f0f8701de920dbf788202539c046b865`,
and
`7838b9392b32d7dc5867dd53ffed78a77f9094f3492cf0b2ac4406ec551ae0d1`.
Its Adam state is provenance only and is not loaded, repaired, selected, or
continued.

### Public counterfactual dataset

Use the exact 2,048-root public schedule, shuffled once with seed `9613` into
32 groups of 64. At zero-based authoritative decision boundary 8 on each root,
enumerate at most 1,000 mask-legal atomic bundles. Include the frozen actor
argmax, then take the first seven remaining bundles in ascending SHA-256 order
under the fixed `m9-ccr-v1|root|8|ascending_bundle` domain. If fewer than eight
exist, use all of them. State selection is fixed before rollout and does not
consume disagreement, planner preference, outcome, reward, or return.

For each sampled planner-admissible branch, execute that bundle once, then the
exact frozen actor through at most 15 further authoritative boundaries. At
each boundary, a read-only candidate-native planner v11 observer assigns the
executed bundle its zero-based rank divided by
`max(1, legal_bundle_count - 1)`. The four targets are mean rank costs over the
available prefix lengths 1, 4, 8, and 16, including the branch boundary.
Terminal prefixes are neither padded nor outcome-labelled. A mask-legal bundle
that canonical planner v11 excludes receives four fixed costs of `1.0` and is
not executed. Any unexpected server rejection of an observer-admissible
bundle is a fatal collection error.

This yields at most 16,384 branch episodes and 262,144 post-branch decision
boundaries. The observer may expose ordering, rank, and admissibility only. It
must be trace-equivalent to uninstrumented planner v11 and must not serialize
or feed target IDs, semantic target pairs, scores, or planner actions into the
learned runtime.

### Architecture and initialization

Reuse the frozen actor's exact 202-value per-seat action descriptors. At every
immutable boundary, concatenate three mean legal descriptors (606), three
sets of normalized raw logits (30), three action masks (30), and three
actor-authoritative bits, for a fixed global input width of 669. One new
`GRUCell(669,128)` updates a single episode-global hidden state.

For each atomic bundle, concatenate ordered action descriptors (606), three
unordered elementwise descriptor products (606), the three-seat elementwise
product (202), global hidden (128), source bundle cost (1), ordered source
action-rank fractions (3), and authority bits (3), for width 1,549. The cost
head is:

`Linear(1549,256) -> Tanh -> Linear(256,128) -> Tanh -> Linear(128,4)`.

Source bundle cost is one minus the source bundle score min-max normalized
over mask-legal bundles, or zero for all bundles when all source scores are
equal. The final linear weight and bias are zero, so each initial output is
exactly source bundle cost and ascending joint argmin exactly preserves the
source actor bundle. Private and global provisional hidden states commit only
after the atomic step is accepted. Planner v11 is absent at inference.

PyTorch default initialization under seed `9721` applies to the new GRU and
the first two cost-head layers; the final layer is then zeroed. A fresh AdamW
optimizer contains new parameters only, in module order: learning rate
`3e-4`, betas `(0.9,0.999)`, epsilon `1e-8`, weight decay `1e-4`, and gradient
norm cap `1.0`. Use Smooth L1 with beta `0.1`, averaged over all four available
targets. Each group performs exactly 256 minibatch updates of 64 branch rows,
uniformly sampled from all public rows collected so far with seed `9733`.
There is no scheduler, dropout, AMP, inherited optimizer state, reward,
critic, PPO, or MAPPO.

### Evaluation, telemetry, and replicas

Persist per-group collection counts, inadmissible counts, target availability
and distributions, loss, gradient norm, and exact-source-bundle rate. Persist
final public-dev wins, core health, idle fraction, learned-action rejections,
planner exact/rank diagnostics, state-trace hash, complete checkpoint parent
lineage, optimizer/model hashes, exact commit/config/protocol hashes, and a
canonical public-only manifest digest.

All 32 groups run without checkpoint ranking, early stopping, repair, or
selection. Only final group 32 may pass construction, requiring at least 30/40
public-dev wins, mean team idle fraction strictly below `0.25`, and zero
rejected learned actions. Replica A may begin only after the complete
exact-implementation-commit public preflight passes. Replica B is prohibited
unless final Replica A reaches both the 30/40 and idle gates; if authorized,
it uses identical seeds and must reproduce the checkpoint lineage and
canonical manifest exactly.

## Architecture relationship

The new learner changes only how complete same-boundary bundles are scored and
how public offline targets are constructed. One immutable observation/mask
bundle still produces one atomic all-seat `StepRequest`; only the simulation
thread observes mutable state or applies actions. One environment remains one
JVM, each engine update remains one fixed `1/60 s` tick, reset remains
in-process, structured communication remains authoritative, and the
framework-neutral environment remains free of Torch.

The candidate-native planner heuristic, candidate set, features, masks,
scenario, engine pins, and runtime planner are unchanged. The planner observer
is read-only training instrumentation whose action and trace equivalence is a
preflight gate, not a planner revision.

## Constraints

- No scalar sweep, disagreement selection, outcome selection, planner-top
  branch injection, target identifier, hard-coded target pair, reward, return,
  critic, PPO, MAPPO, online correction, or planner change is authorized.
- No horizon, state ordinal, branch budget, architecture width, optimizer,
  learning rate, loss, initialization, minibatch, or root-schedule sweep is
  authorized.
- No source or intermediate checkpoint may be selected, repaired, ranked, or
  promoted. The rejected source remains initialization/descriptor provenance.
- Any preflight failure stops before optimizer update. Any Replica A
  construction failure rejects the candidate and prohibits Replica B.
- No confirmation, held-out, restricted, or embargoed manifest or data access
  is authorized. M8 held-out-v7 remains sealed.

## Consequences

Implementation may add one read-only planner-rank observer, frozen-source
counterfactual collector, continuation-cost model, fresh optimizer,
checkpoint/manifest path, focused tests, exact-commit public preflight, and
public result. Failure exhausts this exact continuation-regret candidate and
cannot be converted into tuning or a nearby scalar variant.
