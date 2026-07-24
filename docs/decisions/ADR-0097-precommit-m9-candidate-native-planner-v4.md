# ADR-0097: Precommit M9 candidate-native planner v4

**Status:** Accepted

## Context

ADR-0096 isolates v3's public regression to the active-build fallback choosing
harvest while two underfilled-turret supply candidates are valid.

## Decision

1. Freeze `candidate-native-planner-v4-active-build-supply` at
   `configs/evaluation/m9-candidate-native-planner-v4-protocol.json`, SHA-256
   `ffb5bff61b76161e5c7bef3fd520306049ee04a398ba23835af575cd8a7cf1a7`.
2. Inherit v3 exactly.
3. Change one ordering only: while active-build defer is true, turret coverage
   is positive, and ammo coverage is below one, rank valid SUPPLY_TURRET above
   HARVEST_RESOURCE. Outside that state all v3 scores remain exact.
4. Commit exact inheritance tests and implementation before the unchanged
   two-JVM/reset public gate.
5. Passing thresholds and prohibited authorities remain exact. This does not
   authorize v7, model work, confirmation, or held-out access.

## Consequences

- V4 tests a readiness-preserving substitute for the invalid early
  fortification.
- No restricted data has been accessed.
