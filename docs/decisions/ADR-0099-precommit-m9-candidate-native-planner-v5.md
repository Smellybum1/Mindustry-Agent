# ADR-0099: Precommit M9 candidate-native planner v5

**Status:** Accepted

## Context

ADR-0098 establishes that v4's supply rule is a no-op because supply candidate
actionability precedes positive aggregate turret coverage.

## Decision

Freeze `candidate-native-planner-v5-actionable-supply` at protocol SHA-256
`f408fcc9c200a74e4e6150f9f2e69ff466ee18ca36fcf9bcdf96fdfa3a35965d`.
Inherit v4 exactly and remove only the positive turret-coverage precondition.
During active-build defer with ammo below one, any valid actor-masked
SUPPLY_TURRET candidate ranks above harvest. All gates and prohibited
authorities remain unchanged. Commit implementation/tests before evaluation.
