# ADR-0095: Precommit M9 candidate-native planner v3

**Status:** Accepted

## Context

ADR-0094 shows that v2's only rejected selection overlaps an active build-line
reservation from a prior boundary. The structured task board is already an
authoritative planner input and exposes the task type and lifecycle status
without an engine read or schema change.

## Decision

1. Freeze `candidate-native-planner-v3-active-build-serialization` at
   `configs/evaluation/m9-candidate-native-planner-v3-protocol.json`, SHA-256
   `fc8be8ce0bf630152a3f9fa1775ea39b47af741ed894249c275743391f9ff0b8`.
2. Inherit v2 exactly, including its one-schematic-per-bundle constraint.
3. Change one behavior: when the task board contains a BUILD_LINE or
   BUILD_SCHEMATIC task in CLAIMED, RUNNING, or BLOCKED state, remove new
   BUILD_SCHEMATIC candidates before the unchanged allocator runs. Other work
   remains eligible, so this is a defer operation rather than forced WAIT.
4. Validate the board-state filter, v1/v2 behavior preservation outside the
   coordinate, and exact protocol identity. Commit before evaluation.
5. Reuse the same two-JVM/reset public gate and unchanged 30/40, source-
   retention, action-acceptance, conflict, and coverage thresholds.
6. This protocol cannot train, authorize v7, select a model, or access
   confirmation/held-out data.

## Consequences

- V3 tests whether authoritative cross-boundary lifecycle state closes the
  known reservation invalidity.
- A failure remains public construction evidence only.
- No restricted data has been accessed.
