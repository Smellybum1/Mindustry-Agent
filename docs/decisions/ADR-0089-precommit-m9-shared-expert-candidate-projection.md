# ADR-0089: Precommit M9 shared-expert candidate projection diagnostic

**Status:** Accepted

## Context

ADR-0088 rejects v6 and requires a public v1--v6 synthesis before another
candidate. `docs/M9_V1_V6_SYNTHESIS.md` finds that v5 and v6 both fail when
terminal winning episodes supply labels for every actor-valid sampled
transition. The source of labels, rather than another scalar applied to those
labels, is now the unresolved coordinate.

The ordinary candidate-path greedy policy is compatible with the M9 action
surface but lost all five randomized architecture-parity episodes. The frozen
simulation-thread `ExpertCoordinationDriver` wins 36/40 public M9 dev episodes,
yet controls skills internally. Its decisions cannot become training labels
until exact, unambiguous candidate projection and ordinary-path replay are
demonstrated.

## Decision

1. Freeze the public-only diagnostic protocol at
   `configs/evaluation/m9-shared-expert-candidate-projection-protocol.json`,
   SHA-256
   `3aea109ad7d876fb4f0b220162a8b545a0adf2e0de5ea7d6f823e28d21369dc9`.
2. Use only the existing 40-root M9 public dev-v1 document, SHA-256
   `5d834a1ea8db828e05f2e7343a88cea1ba49721bd1570d1f435ca73778fb6b83`.
   The source oracle is the already frozen 36/40 shared-expert baseline,
   report SHA-256
   `ba4c9182f346a6eefc8c904d3e7825ee23933aede535b7c516ec63800f6a2d70`.
3. Add only diagnostic structured telemetry emitted from the simulation thread.
   Every expert `SELECT_TASK` row must bind its authoritative same-boundary
   agent, task type, and semantic target. I/O threads may serialize the result
   but may not inspect mutable engine state.
4. Project a row only when exactly one candidate with those semantic fields is
   actor-valid in the authoritative same-boundary catalog and action mask.
   Utility, public outcome, later state, checkpoint behavior, and arbitrary
   candidate order cannot break a tie. Forced controls remain actor-excluded.
5. Replay projected labels through ordinary external
   `SELECT_CANDIDATE_TASK` actions. Missing or ambiguous labels, invalid masks,
   rejected actions, semantic-order drift, or fallback WAIT fail closed.
6. Run collection/projection/replay twice in fresh JVMs and require
   byte-identical canonical reports plus terminal-reset replay.
7. Classify the source as supported only if unique projection covers at least
   95% of all expert selections and 100% of selections in winning episodes,
   every projected action is accepted, semantic decision sequences match, and
   projected ordinary-path replay wins at least 30/40 while retaining at least
   80% of the source expert's wins. Otherwise classify it unsupported.
8. Before execution, implementation must be committed and pass focused
   projection/ambiguity/mask/timing tests, the full Python and Java suites,
   smoke, determinism, and golden replay.
9. This diagnostic cannot modify a model, train, select a checkpoint, promote
   a policy, allocate M9 restricted sets, authorize v7, or access confirmation
   or held-out data. A supported result permits only a separate prospective v7
   precommit.
10. M8 held-out-v7 remains sealed and unavailable.

## Alternatives

- Directly behavior-cloning the internal expert is rejected because its
  skill-owning control path has not been shown equivalent to ordinary
  candidate actions.
- Reusing the five-episode architecture parity teacher is rejected because it
  lost every episode and is only a path oracle.
- Another v5/v6 coefficient or filter is rejected by ADR-0088.
- Training on public dev projection rows is rejected; this diagnostic only
  tests whether the supervision source is technically and behaviorally valid.
- Permitting fuzzy target matching or a WAIT fallback is rejected because it
  could manufacture apparent coverage without decision-sequence parity.

## Consequences

- No v7 model, optimizer update, or environment trajectory is authorized.
- Implementation may add bounded diagnostic telemetry, but normal external and
  shared-expert behavior, state hashes, actions, and accepted ADRs must remain
  unchanged.
- A passing result leads to a separately frozen public training corpus and v7
  recipe. A failing result closes this projection route and requires a
  candidate-native planner.
