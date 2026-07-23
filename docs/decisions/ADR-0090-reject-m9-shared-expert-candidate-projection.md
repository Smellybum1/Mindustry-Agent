# ADR-0090: Reject direct M9 shared-expert candidate projection

**Status:** Accepted

## Context

ADR-0089 froze a public-only diagnostic before execution. Implementation commit
`6d9bd3708b1c9d3fbcc57fbf409bffcbeaa250d6` adds opt-in simulation-thread
telemetry that snapshots the authoritative candidate catalog immediately before
each shared-expert update. The full Python suite, pinned Java build/tests,
rebuilt fat runtime JAR, smoke, determinism, and golden replay passed before the
governed run.

Two fresh JVM passes reproduce the frozen source expert's 36/40 public wins and
all projection evidence exactly. The source emitted 3,833 `SELECT_TASK` rows,
including 3,585 from winning episodes. Only 65/3,833 (`1.6958%`) matched
exactly one same-boundary actor-valid ordinary candidate; winning-episode
coverage was 51/3,585 (`1.4226%`). BUILD_LINE, BUILD_SCHEMATIC, and
SUPPLY_TURRET had zero unique matches. The internal expert's tile/resource
targets and fine-grained task lifecycle are not the semantic action surface
exposed by the bounded candidate catalog.

The 95% overall and 100% winning-episode thresholds therefore failed before
ordinary-path replay. Per the frozen protocol, replay was not attempted. The
full report SHA-256 is
`83a457b702048960b84808eabb2988dd02e8c5a6b0258e3183742ecb9e7170c4`.
The compact result is
`configs/evaluation/m9-shared-expert-candidate-projection-result.json`,
SHA-256
`1d8eb99978ebf1486ee6e9cd5993b5ef670b2987494085cb589bf3e6075b29c6`.

## Decision

1. Classify the direct legacy shared-expert projection source as
   `candidate_native_supervision_source_not_supported`.
2. Do not normalize, fuzzily match, relabel, merge, or drop the unmatched
   internal decisions after observing this result. Such a repair would create
   a new teacher rather than validate the frozen source.
3. Do not run projected replay: ADR-0089 requires the projection thresholds to
   pass first.
4. Preserve the opt-in diagnostic telemetry, runner, tests, full local report,
   and compact result. Normal action paths remain unchanged.
5. Close direct behavior cloning or distillation from
   `ExpertCoordinationDriver` into M9's ordinary ten-action vocabulary.
6. Before any v7 model or trajectory, prospectively define and validate a
   candidate-native planner that itself acts only through authoritative
   candidates and masks on the randomized M9 scenario family. Its survival,
   exact replay, and label coverage must be frozen before it can become a
   supervision source.
7. M9.1 remains open, MAPPO remains unauthorized, and M8 held-out-v7 remains
   sealed.

## Alternatives

- Treating task type alone as a match is rejected because BUILD_SCHEMATIC and
  SUPPLY_TURRET each expose multiple materially different targets.
- Type-specific post-result normalization is rejected because the frozen
  protocol intentionally tested whether the existing expert already spoke the
  candidate action language.
- Replaying only the 65 matching rows is rejected because it would discard
  almost the entire winning decision sequence.
- Training a v7 model from the unmatched rows is rejected because no
  authoritative ordinary action label exists for them.

## Consequences

- The diagnostic provides a clean architecture result: the strong internal
  policy cannot be used as a drop-in teacher for the current actor vocabulary.
- The next useful work is a separately governed candidate-native planner, not
  another IPPO loss scalar or a projection repair.
- No confirmation or held-out data was accessed.
