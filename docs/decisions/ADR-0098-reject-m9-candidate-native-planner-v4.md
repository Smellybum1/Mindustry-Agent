# ADR-0098: Reject M9 candidate-native planner v4

**Status:** Accepted

## Context

V4 at `e275ac4b13` reproduces v3's complete canonical trace exactly:
3/40 wins, zero rejected actions/conflicts, and canonical trace
`e688e73c927447d2...`. Its positive `defense_turret_coverage` precondition
never activates even though valid actor-masked SUPPLY_TURRET candidates exist.
The candidate surface becomes actionable before that aggregate coverage field
turns positive.

Full/compact result SHA-256 values are
`b3b1bb9b86853d9447dd510b9c832dc4286d404a8de3fa10f3eb724c1344649c` /
`57aa6bdbdbacd84ee4c3219e74a7064ba54e182b7e90f446b15ff29ab750bc2b`.

## Decision

Reject v4 and preserve it. A successor may remove only the redundant positive-
turret-coverage condition, using existence of a valid masked supply candidate
as the authoritative actionability signal. No training or restricted access is
authorized.
