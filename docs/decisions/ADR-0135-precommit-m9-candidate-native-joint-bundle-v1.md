# ADR-0135: Precommit M9 candidate-native joint bundle v1

**Status:** Accepted

## Context

The accepted M9 actor scores each seat independently from that seat's
candidate rows, shared pre-step scalars, private hidden state, and role. It
submits those three independent argmax actions atomically. It cannot represent
compatibility between the current actions of two seats because neither action
score consumes the other seat's current candidate rows or action choice.

Candidate-native planner v11 instead scores the Cartesian product of the
three-seat action bundle and wins 32/40 public-dev roots. The exact rejected
update-64 independent actor wins 13/40, with 19 planner-only wins and median
three-seat task-family occupancy mismatch `0.5982906`. Scalar disagreement
pressure, online planner correction, contiguous recurrent NLL, maximal label
freshness, and a per-seat four-slot plan head all failed construction. The plan
head peaked at 12/40. It added temporal family supervision but retained the
same independent current-action factorization.

The owner explicitly authorized one new evidence-supported architecture or
supervision class using public data only. The remaining isolated structural
coordinate is same-boundary cross-seat action compatibility.

## Decision

Freeze `m9-candidate-native-joint-bundle-v1` before implementation or training.
It initializes every inherited parameter and Adam moment from the exact
rejected on-policy-relabel update-64 checkpoint. It adds one shared pairwise
compatibility head:

`Linear(404,64) -> Tanh -> Linear(64,1)`.

Each legal per-seat action has a fixed 202-value descriptor. Ordinary
candidate actions concatenate the existing encoded candidate, existing pool of
other candidates, next private hidden state, role embedding, and zero
two-value special code. CONTINUE and WAIT replace the candidate encoding with
zeros, use the existing candidate pool, hidden state, and role, and set their
respective special code.

For actor-authoritative seats at one immutable pre-step boundary, enumerate the
ascending legal Cartesian product, at most `10^3` bundles. A bundle logit is
the sum of inherited per-seat logits plus fixed-scale `1.0` pairwise
compatibility over every unordered variable-seat pair. Forced controls execute
unchanged and are neither variables nor loss terms.

The pairwise head's final weight and bias are all zero. Therefore every initial
bundle score factorizes into the inherited per-seat logits and deterministic
joint argmax exactly reproduces the source actor's independent bundle,
including tie order. Inherited parameters and Adam moments remain exact; the
new head is appended as one same-hyperparameter Adam group with empty moments.

Collection remains deterministic student control over the exact 2,048 unique
public roots. Planner v11 labels the complete canonical actor-authoritative
sub-bundle at the same pre-action student state without execution. The sole
loss is legal joint-bundle negative log probability, summed across atomic
boundaries and divided by the number of actor-authoritative seat labels in the
minibatch. With zero pairwise compatibility this is exactly the inherited mean
per-seat teacher NLL. Boundaries are shuffled deterministically for eight
epochs and packed whole into a maximum 256-label minibatch. Hidden inputs are
the stored private student states detached at that boundary; no temporal
backpropagation is added.

The candidate continues for 32 updates, lineage 65 through 96, with the same
32-by-64 public schedule, dev evaluation after every update, 30/40
construction floor, exclusive idle threshold `0.25`, ranking, and conditional
Replica B rule.

Configuration/public-protocol SHA-256 values are
`c8138e9d26b8addcd821068ff93b02ecdec03b1053cc8ecf7be2f40b6b3ce0b4`
/
`f3a9b9eecfaeae0858ac46db52e8eea27a6927a2b4ba688d22fcaaab5e27a98b`.

## Architecture relationship

This decision supersedes `docs/M9_DESIGN.md` D1 only for this prospectively
named candidate's action-scoring function. There is still one shared parameter
set, one immutable pre-step observation/mask/board bundle, ascending seat
order, private per-seat recurrent state, and one atomic `StepRequest`. No seat
observes another seat's newly selected action; the joint scorer consumes only
the common pre-step boundary and evaluates bundle compatibility
simultaneously. Server stepping and all project-wide architecture invariants
remain unchanged.

## Constraints

- Only same-boundary action descriptors, the zero-output pairwise head, and
  normalized joint-bundle NLL are new. Planner, candidates, governed feature
  values, masks, roots, recurrent width, inherited weights, inherited Adam
  state, schedule, budget, dev gate, and replica rule remain frozen.
- No pairwise width, scale, loss, minibatch, initialization, epoch,
  learning-rate, or source-checkpoint sweep is authorized.
- No target identifier, semantic-target hard-coding, sequential within-bundle
  observation, plan head, recurrent-window change, EMA, replay, reward,
  critic loss, PPO, or MAPPO is authorized.
- The rejected source is initialization only and remains unselected,
  unrepaired, and unpromotable.
- Replica A may start only after exact source/bundle/optimizer inheritance,
  factorization-equivalence, legal-enumeration, forced-control, gradient,
  checkpoint, deterministic replica, live-reset, and complete
  exact-current-commit gates pass.
- Replica B is prohibited unless Replica A reaches both construction and idle
  gates.
- No confirmation, held-out, learned human-session, or other restricted data
  is authorized. M8 held-out-v7 remains sealed.

## Consequences

Implementation may add one joint-bundle model, collector, optimizer,
checkpoint/manifest path, preflight, commands, tests, and public result. No
implementation, candidate state, optimizer update, or restricted access
preceded this precommit. Failure exhausts this isolated same-boundary
compatibility architecture and cannot become a sweep.
