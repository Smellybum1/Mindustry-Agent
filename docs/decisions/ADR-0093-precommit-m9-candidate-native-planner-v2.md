# ADR-0093: Precommit M9 candidate-native planner v2

**Status:** Accepted

## Context

ADR-0092 rejects v1 at 13/40 with exactly one `reservation_overlap` rejection
at tick 250 in every public episode. The rejected tasks are distinct
fortification `BUILD_SCHEMATIC` candidates whose footprints overlap. Task-id
and semantic-target uniqueness cannot detect that physical collision from the
bounded public catalog.

## Decision

1. Freeze `candidate-native-planner-v2-build-serialization` at
   `configs/evaluation/m9-candidate-native-planner-v2-protocol.json`, SHA-256
   `411c40c69ac7419fa0920a2270d5b4537a5b0885af52d0abf12a396f0b8a5246`.
2. Inherit v1's inputs, forbidden inputs, action vocabulary, phase/role
   priorities, bundle order, conflict keys, tie breaks, reset behavior,
   evaluation roots, and thresholds exactly.
3. Change one behavior only: an atomic bundle may contain at most one new
   `BUILD_SCHEMATIC` selection. Existing schematic work may continue normally;
   `BUILD_LINE`, harvest, supply, repair, defend, abandon, continue, and WAIT
   behavior are unchanged.
4. The implementation must validate exact v1 inheritance and the new bundle
   constraint. Commit it before the governed run.
5. Run the same two fresh JVMs plus terminal-reset public gate. Passing still
   requires exact reports, every action accepted, zero nonordinary fallback or
   cross-seat conflict, 30/40 wins, at least 80% retention of the 36-win source
   expert, and 95% non-WAIT selection coverage.
6. This gate cannot train, authorize v7, select a checkpoint, or access
   confirmation/held-out data.

## Alternatives

- Adding physical footprint fields to the public action schema is deferred:
  serialization is a sufficient bounded test and avoids an observation/schema
  change before evidence requires it.
- Changing role priorities or combat thresholds is rejected because the v1
  result isolates a structural rejection first.
- Ignoring rejected selections is rejected by the frozen all-actions-accepted
  gate.

## Consequences

- V2 tests whether removing the single known bundle invalidity is enough to
  make this candidate-native source viable.
- Failure requires another prospective public-trace diagnosis; v1/v2 may not be
  retrospectively tuned.
- No restricted data has been accessed.
