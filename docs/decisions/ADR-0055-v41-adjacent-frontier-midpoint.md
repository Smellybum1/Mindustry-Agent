# ADR-0055: V41 adjacent-frontier midpoint

**Status:** Accepted

## Context

V40 reproducibly selects update 28 at 10/10 reusable wins but fails both
precommitted scorecards. Permanent-greedy announcements and idle and matched-
greedy recovery remain uncertain, so dev-v36 is retired unopened. The V40
frontier also contains adjacent 10/10 checkpoints at updates 25 and 26.

A pinned reusable-only diagnostic evaluates those two checkpoints under the
same dev-v1 roots, permanent records, matched controls, runtime, and canonical
bootstrap labels as the official V40 gate. Updates 25, 26, and 28 all pass all
four win comparisons and all fail the same three scorecard rows. Update 25 has
the best recovery mean and removes update 26/28's seed-2006 idle outlier, but
introduces a seed-2004 idle outlier. Update 26 has the best idle, announcement,
and core-health means and avoids update 25's seed-2004 outlier. No existing
checkpoint is promotable, while the adjacent aligned states expose one bounded
construction hypothesis rather than another training-coordinate sweep.

## Decision

1. V41 is one deterministic 50/50 model-state interpolation of V40 update 26
   as base and update 25 as auxiliary. Equal weight is the unswept midpoint:
   neither observed failure topology is privileged after both parents reach
   10/10 and neither passes the reusable gate.
2. Both parents use exact V40 config
   `configs/training/m8-selector-v40-partner-intent-teacher-conflict-filter.json`
   and training commit `c288483436c1003d25dc64ce7aba968600d45f3a`.
   Construction A uses Replica A parents; construction B uses Replica B
   parents. Parent checkpoints, manifests, configs, updates, model-state
   schemas, initial state, repository evidence, and full-run digests must
   validate before interpolation.
3. The two path-independent constructions must match checkpoint bytes, model
   state, and canonical lineage exactly before any reusable episode runs.
   There is no coefficient sweep, fallback weight, or post-result parent swap.
4. Runtime selection, features, reward, typed action authority, scripted seat-2
   opening, structured partner intent, model architecture, scenario, reusable
   roots, action RNG, and fixed-step engine behavior remain V40-exact. V41
   changes only the derived model state and its governed config identity.
5. Fresh ADR-0051 selected-only permanent baselines are required because the
   runtime config hash changes. V41 must reach at least 9/10 reusable wins with
   mean idle `<0.25`, beat all four observed win comparators, pass all 44 exact-
   config reward adversaries, and pass both frozen scorecards. Any uncertainty
   is failure.
6. Dev-v36 is retired unopened and unconsumed. Reserve dev-v37 at 160 roots in
   the exclusive `[5_000_000_000,6_000_000_000)` namespace without reading any
   prior membership. Membership construction and access are primary-only.
   Dev-v37 must be frozen value-free before checkpoint construction and may be
   consumed only after exact constructions and the complete reusable gate pass.
7. Held-out-v6 remains sealed and unconsumed. Only a fully eligible one-way
   dev-v37 confirmation may authorize its separate final gate.

## Alternatives

- Selecting update 25 or 26 directly is rejected because the canonical
  diagnostic shows both fail the same scorecard rows as update 28.
- Sweeping interpolation weights is rejected as reusable-set coefficient
  fitting. The equal midpoint is one precommitted construction.
- More idle/recovery reward pressure and teacher-coefficient changes are
  rejected because ADR-0026..0031 and ADR-0036..0037 already exercised those
  lines without resolving the governed scorecards.
- Opening dev-v36 to resolve uncertainty is prohibited because V40 failed its
  prerequisite reusable gate.

## Consequences

- Weight-space interpolation may not interpolate behavior; construction or the
  first reusable screen may reject V41 without confirmation access.
- V41 uses accepted deterministic interpolation machinery and adds no runtime
  branch, feature, reward component, dependency, or engine change.
- The immutable construction config is
  `configs/training/m8-selector-v41-adjacent-frontier-midpoint.json`, SHA-256
  `c4705974f18512a627ac9f12646b140ea60da79e0e8c50c5f35248298f00eac9`.
- The value-free confirmation umbrella is
  `configs/evaluation/m8-selector-v41-confirmation-umbrella.json`, SHA-256
  `7ce8f5cf640978ef479165584d05c520a4e0200c3f49f986a14ae489d6d180f0`.
- The canonical frontier diagnostic records/report SHA-256 are
  `4463ba2b62cdaa4a1a20ebfd76a6cf7571d52b128552866f9c2477a6ead5d2a0`
  and `7da028137a4550a39daa9081f2945e9c21d33e497698404ded93385838d4d3fe`.
  Its update-28 scorecard objects reproduce the official V40 report exactly.

This ADR authorizes config/governance tests and the unchanged-runtime gate
review after the precommit packet is committed. It does not authorize dev-v37
membership construction, checkpoint construction, reusable evaluation,
confirmation consumption, or held-out-v6 access until their preceding gates
are committed and pass.

## Outcome

The 44/44 exact-config reward adversaries pass. Dev-v37 was frozen value-free
and remained unopened. After correcting the generic constructor to propagate
the config-selected reward schema, independent pinned-toolchain constructions
matched exactly at checkpoint `b6b5e98ddee56740...`, model state
`93594bd64193740a...`, and canonical lineage `37c4b1e571fca96c...`.

Reusable evaluation rejects V41 before confirmation. The candidate is 10/10
versus permanent random/greedy 4/10 and 8/10 and matched random/greedy 5/10 and
6/10, so every observed win comparison passes. The permanent-greedy scorecard
fails uncertain idle (mean `-0.00739956`, 95% CI
`[-0.02001559,+0.01067689]`), while the matched-greedy scorecard fails uncertain
recovery (mean `-19.85`, 95% CI `[-81.80125,+29.65]`). The records, aggregate,
and report SHA-256 values are `543e50b729097326...`,
`056b356de88704f0...`, and `ca7b39c84a9f51d1...`. Dev-v37 is retired unopened
and unconsumed; held-out-v6 remains sealed and unconsumed.
