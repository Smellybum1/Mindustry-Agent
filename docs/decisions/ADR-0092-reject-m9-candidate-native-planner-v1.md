# ADR-0092: Reject M9 candidate-native planner v1

**Status:** Accepted

## Context

ADR-0091 froze the first candidate-native planner before implementation and
evaluation. Implementation commit `5eb450ab25b52ece08230840c2b9b7d10080a337`
passed 456 Python tests, pinned Java/custom-module tests, smoke, cross-process
determinism, and the 664-checkpoint golden replay.

The governed public run completed twice in fresh JVMs plus terminal-reset
replay. Reports and reset traces reproduce exactly. The planner won 13/40
episodes and labeled 4,959/4,963 eligible slots with a non-WAIT action
(`99.9194%`). It emitted no cross-seat duplicate exclusive/semantic key.
However, one `BUILD_SCHEMATIC` selection per episode was rejected at tick 250
with `reservation_overlap`: distinct fortification candidates can have
overlapping physical footprints even when task ids and semantic target strings
differ. All 40 episodes therefore contain one rejected action. Both the 30-win
survival threshold and all-actions-accepted threshold fail.

The full report SHA-256 is
`57f1c4d2c49075b1f1e8af30eca96ec916adcde057b45a5585990557f20591c3`.
The compact result is
`configs/evaluation/m9-candidate-native-planner-v1-result.json`, SHA-256
`5a9df7fce1c39f14212b18ef8f0a7920550d1c0411ea18e49e4b3ccd79ae577b`.

## Decision

1. Classify v1 as `candidate_native_supervision_source_not_supported`.
2. Do not use its decisions as model supervision and do not authorize v7,
   MAPPO, confirmation, or held-out access.
3. Preserve the exact implementation and result. Do not change v1 after its
   governed run.
4. Accept the public structural diagnosis that candidate identity alone does
   not encode build-footprint collision. A successor may serialize
   `BUILD_SCHEMATIC` selections within each atomic bundle, but must inherit all
   other v1 rules and gates unchanged and be precommitted separately.

## Consequences

- Coordinated candidate allocation improves the ordinary comparator from the
  earlier five-seed 0/5 architecture result to 13/40 on the public family, but
  remains well below the required supervision bar.
- The v1 evidence supplies one bounded successor coordinate; it does not permit
  a role, priority, or threshold sweep.
- No confirmation or held-out data was accessed.
