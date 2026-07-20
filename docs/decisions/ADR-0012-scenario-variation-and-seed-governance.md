# ADR-0012: Bounded scenario variation and seed governance

**Status:** Accepted

## Context

The fixed `bootstrap-defense-v0` scenario is useful for regression testing but
does not test whether coordination survives small changes in economy geometry,
wave pressure, available resources, or approach direction. Unbounded procedural
generation would make failures difficult to reproduce and would invite accidental
tuning on evaluation seeds. Scenario identity, variation, and seed-set use need a
single reproducible contract before the evaluation ladder expands.

## Decision

- `bootstrap-defense-v1` is `scenario_version = 2`. Its observable contract adds
  five bounded axes resolved solely from `root_seed`:
  - main/support copper and optional lead patch origin jitter within declared
    per-patch rectangles;
  - a bounded starting-copper range;
  - one common initial-wave offset and one uniform spacing offset;
  - a bounded per-wave Dagger-count delta;
  - an optional upper-east spawn used by one later wave.
- Each axis uses a stable named seed derivation. Adding or reordering one axis
  must not silently perturb the others. Resolved values are returned in reset
  metadata and included in `state_hash`.
- The loader validates patch bounds/non-overlap, core clearance, named spawn
  references, positive wave timing/counts, and wave/win/cap ordering after
  variation is resolved. Only the simulation thread loads the resulting world.
- Reset discards callbacks posted by the outgoing episode. Each v2 native wave
  receives a disjoint deterministic entity-ID range immediately before spawn so
  transient allocations from an earlier episode cannot alter unit identity,
  hashes, or target tie-breaking.
- The checked-in seed sets under `configs/evaluation/` are immutable by
  `seed_set_id` and `seed_set_version`:
  - `train` may be used for development and future training;
  - `dev` is the frozen M7.5 acceptance set and may be used for diagnostics;
  - `held-out` is sealed until final evaluation. Development tools must refuse
    to execute it, and no behavior may be selected from its outcomes.
  The three sets must be pairwise disjoint. Changing membership creates a new
  seed-set version instead of editing the existing contract.
- Every variant run manifest records engine tag/commit, Arc hash, protocol
  version, scenario id/version, root seed, seed-set id/version, policy id, and
  agent count. A reset may request a nonzero scenario version; the server rejects
  a mismatch.
- Fixed and dev ladder results are descriptive only and cannot promote a
  policy. Held-out execution is a one-way final action behind the explicit
  `--allow-held-out-final` gate. For each policy, the ladder uses 10,000
  deterministic episode-level bootstrap resamples of win rate. A candidate is
  "better" than the permanent `greedy-utility` baseline only when its 95%
  interval lower bound is strictly greater than the baseline interval upper
  bound on the same held-out seed set. Overlap means no promotion claim;
  scorecard metrics remain diagnostic rather than a substitute promotion
  target. The exact held-out episode manifests and aggregate decision must be
  retained if that gate is ever used.
- Any change to a loaded variation axis, bound, derivation, base geometry,
  loadout, wave schedule/composition, allowed content, or termination rule bumps
  `scenario_version`. Documentation-only changes do not.

## Alternatives considered

- **One global RNG stream for all axes:** rejected because adding an unrelated
  draw would change every downstream variant and invalidate attribution.
- **Random seeds chosen at evaluation time:** rejected because the result would
  not be a stable acceptance gate and could conceal seed selection.
- **Use held-out seeds during development to improve the pass rate:** rejected;
  this converts the held-out set into another dev set and invalidates the final
  generalization claim.
- **Unbounded map generation:** rejected for v1 because it can create invalid or
  unsolvable layouts and makes deterministic diagnosis unnecessarily broad.

## Consequences

- Same scenario id/version, root seed, and action trace remain exactly
  reproducible across resets and fresh JVMs.
- The dev result is comparable over time and honest failures remain visible as
  planning/candidate gaps rather than being removed by seed churn.
- New variation axes require explicit schema, validation, version, and seed-set
  review, adding modest maintenance overhead.

## Reversal conditions

Supersede this ADR if the project adopts a separately versioned scenario compiler
or externally supplied scenario artifacts whose content hash fully replaces the
current id/version/seed contract. The train/dev/held-out separation remains in
force unless a later ADR defines an equally auditable evaluation protocol.
