# ADR-0060: V43 candidate-set-context actor

**Status:** Accepted

## Context

V42 reproduces at 9/10 reusable wins and passes every observed win comparator,
but its frozen dual scorecards fail on permanent-greedy announcements and idle
and matched-greedy recovery. Dev-v38 is therefore retired unopened and
unconsumed. Held-out-v6 remains sealed and unconsumed.

The rejected build-line-prior diagnostic shows that a runtime prior can remove
the idle gap while preserving 9/10 wins, but announcements and recovery remain
uncertain. It has no promotion authority and closes that runtime line. Accepted
ADRs also close further WAIT-logit, danger-label, exact-death recovery, broader
staging, reward-pressure, teacher-strength, alternate-teacher-trajectory, and
checkpoint-interpolation coordinates.

One architecture limitation remains untested. `selector_actor_critic_v1`
encodes all candidate rows, but each SELECT logit sees only its own candidate
embedding and the scalar context. It cannot condition a candidate score on the
other candidates present. More importantly, the CONTINUE and WAIT logits see
only scalar context and cannot see the candidate catalog at all. This is an
information-routing limitation, not missing structured state: reusable and
train-only evidence contains 682 deterministic nonconflicting teacher
alternates, 11 alternate supply choices at observed collisions, and a catalog-
dependent idle correction. M8's accepted design explicitly permits
reconsidering the feed-forward architecture after the independent scorer fails
the matched promotion gate.

## Decision

1. V43 retrains the exact V42 recipe with one changed coordinate: model schema
   `selector_actor_critic_v2_set_context` replaces the independent v1 actor.
   Runtime behavior, action vocabulary and authority, features, masks, reward,
   teacher trajectory and relabeling, roots, budgets, optimizer, checkpoint
   ranking, RNG values, scripted seats, and engine pins remain V42-exact.
2. The 37->64->64 candidate encoder and 56->64->64 scalar encoder remain
   unchanged. Candidate presence, not action validity, defines masked pooling;
   this preserves observation semantics while the existing action mask remains
   authoritative for selection.
3. Each SELECT logit consumes its candidate embedding, scalar embedding, and
   the masked mean embedding of every *other* present candidate. The other-set
   context is exactly zero when no other candidate is present. The head is
   192->64->1 with Tanh.
4. CONTINUE and WAIT consume the scalar embedding plus the masked mean of all
   present candidates through a 128->64->2 Tanh head. The critic retains its
   existing scalar-plus-all-candidate-pool 128->64->1 shape.
5. Pooling must ignore zero padding, remain permutation-equivariant for SELECT
   logits, remain permutation-invariant for CONTINUE/WAIT and value, be finite
   for zero or one present candidate, and never unmask an action. Stable
   evaluation argmax and lowest-index tie breaking remain unchanged.
6. Model construction must be config-selected and fail closed on an unknown or
   mismatched architecture. Historical v1 checkpoints/configs remain exactly
   loadable and reproducible; v1/v2 checkpoint or lineage substitution must be
   rejected by model schema and architecture validation.
7. Focused tests must cover exact v2 shapes and deterministic initialization,
   padding exclusion, singleton context, SELECT permutation equivariance,
   special/value permutation invariance, masked-action preservation, config
   selection, checkpoint mismatch, and unchanged v1 behavior.
8. The complete public/pretraining boundary is required before any confirmation
   membership construction or model run: Python and pinned Java suites, public
   survival/staging, focused coordination checks, smoke, cross-process/reset/
   alternate-seed determinism, golden replay plus negative control, and all 44
   exact-config reward adversaries.
9. Replica A retains the exact 256-episode warmup and 2,048-episode/32-update
   V42 budget. It must reach at least 9/10 reusable wins with mean idle below
   `0.25` before replica B. Exact twins, direct lineage, fresh selected-only
   permanent baselines, all four win comparisons, and both reusable scorecards
   remain mandatory. Uncertainty is failure.
10. Dev-v38 stays retired unopened and unconsumed. V43 reserves primary-only
    dev-v39 at 160 roots in the exclusive `[7_000_000_000,8_000_000_000)`
    namespace. Membership may be created value-free only after this precommit
    and the full implementation/pretraining boundary are committed. Held-out-v6
    remains sealed and unconsumed under ADR-0053.

## Alternatives

- The rejected build-line prior is not reusable as a successor because it is
  off-contract and still fails two scorecard rows.
- A recurrent model is broader than the evidence requires. The observation
  already carries bounded task history and boundary reasons; the demonstrated
  omission is candidate-set context at the same authoritative boundary.
- Adding candidate aggregates as new hand-authored features would duplicate
  model-computable information and require a new feature schema. Masked pooling
  uses only the already accepted structured observation.
- Self-attention is unnecessary at eight rows for the first test of this
  hypothesis. Deterministic masked means isolate the missing comparison
  coordinate with fewer parameters and no new dependency.
- Another reward, teacher, opening, or runtime coordinate is closed by the V38-
  V42 governed evidence and would not test the identified architecture defect.

## Consequences

- V43 is a fresh training construction. V42 checkpoints remain diagnostic
  history and cannot initialize, interpolate into, or authorize V43.
- The model remains feed-forward, deterministic, CPU-only under the pinned
  Torch lock, and framework-neutral below the training package.
- The immutable config is
  `configs/training/m8-selector-v43-candidate-set-context.json`, SHA-256
  `29b4430839451f136bd5cae729f7341cefe74f4cc2b6710cd1bb1e124dc80e99`.
- The value-free confirmation umbrella is
  `configs/evaluation/m8-selector-v43-confirmation-umbrella.json`, SHA-256
  `99851aa2cdbfb469ac32ded36fa0b932a5149e29aa8b94ccb3bbc7f0000e1d1b`.
- This ADR authorizes implementation and public/pretraining verification after
  this packet is committed. It does not authorize dev-v39 membership creation,
  replica A, confirmation consumption, or held-out-v6 access before their
  preceding committed gates pass.

## Implementation status

The config-selected v1/v2 model factory, masked set-context actor, dynamic
checkpoint schema, training/replay/lineage/preflight/final plumbing, and focused
compatibility tests are implemented. Historical v1 training configs remain
exact, legacy logit-adjustment configs retain their pinned v1 interpretation,
and cross-schema checkpoint loading fails closed.

The complete 2026-07-23 pretraining boundary passes 293 Python tests and pinned
Java tests/classes. Public policy passes 5/5 with 10 proactive staging starts;
secondary-claim and owned-schematic checks pass; smoke passes; cross-process,
reset, and alternate-seed determinism remain `20a97f36407167597981e77c`,
`a2cf4a73ee901c844f30f486`, and `495ba05fa71697bdc8ff2951`. Golden replay
passes 664 checkpoints / 16,200 ticks / two wins, and its negative mutation is
detected. All 44 exact-config reward adversaries pass; the ignored report hashes
to `3e3210447ff4f428a6e3fcc7a77b86e2bf82c9e42df89b9df8a2ef37ce467060`.
Dev-v39 remains unconstructed, dev-v38 remains retired without a membership
read, held-out-v6 remains sealed, and no V43 training episode has run.

The primary-only dev-v39 freezer is now implemented and fail-closed against the
exact committed config/umbrella hashes, repository paths, candidate identity,
count, `[7B,8B)` namespace, and sealed-final binding. It atomically creates the
membership and a value-free receipt without reading any membership document.
All 298 Python tests pass. The freezer has not yet executed; dev-v39 remains
unconstructed until this tool commit becomes an ancestor of `HEAD`.

The committed freezer at `5007a7b9f3` then created dev-v39 value-free in the
reserved namespace. The membership and receipt hashes are
`0b88fda1b37647aa8ee8bb6225ac20a2ebf64d0154195461b5cf0ed804d69bb3`
and `6a736be55774a7002dbacbe33d7400cdb6947500f930ad3d48c376cc44e1ae66`;
the receipt reports
`values_emitted=false`, zero membership-document reads, and no generated,
retired-confirmation, or sealed-final read. Dev-v39 is frozen unconsumed. Replica
A remains prohibited until this membership/receipt packet is committed.

## Outcome

The membership/receipt packet was committed at `df7723c6cb` before model work.
Two independent pinned WSL Torch 2.12.1 constructions from that exact commit
select update 27 at 10/10 reusable wins, mean return `7.57468`, mean core health
`829.1`, and mean idle `0.008742327973619925`. All 32 checkpoint files are
byte-identical and the canonical manifest comparator passes. Checkpoint, model-
state, replay, action-state, and full-run hashes are
`b4cc691ad0c08d67d6d560f0e4bfc66651df65e3a8945dcb27f22a0db8129bfa`,
`0dea357a79bd33fcac9c7ddb8468ddf37a6a3fde267f611cc5c209035e65ab73`,
`12ed6b616310deb7a78040faccf09193a6e51030f15ec90b5204d46ff917b64c`,
`7224241af3bf6624501ebecca220bb7d72fdf547cf0518dc1b88cb27dbf8636b`,
and `66385a8f85ec7db76b478c9ee1a167710e0839320d2e828de280082d193af9b1`.
Direct-lineage digest/artifact hashes are `1f07166a5d27aa30...` /
`9da8c719c366752c...`.

Fresh selected-only permanent random/greedy baselines are 4/10 and 8/10. V43
is 10/10 versus matched random/greedy 5/10 and 6/10, so every observed win
comparison passes. The set-context architecture also makes permanent recovery a
decisive pass (mean `-108.35` ticks, CI `[-196.15,-41.0475]`) and improves all
matched announcement/duplicate/idle rows. The frozen dual scorecards still
fail: permanent announcements (mean `-0.00104554`, CI
`[-0.00652092,+0.00494021]`) and idle (mean `-0.00697822`, CI
`[-0.02003760,+0.01159576]`) are favorable but uncertain, while matched recovery
is uncertain (mean `-20.8`, CI `[-88.90875,+51.0025]`). Records/aggregate/report
hashes are `a3bf222c25ec52ea...` / `12c0272429e14f42...` /
`10f829a54a110507...`.

V43 is rejected before confirmation. Dev-v39 is retired unopened and
unconsumed without a membership read. Held-out-v6 remains sealed and
unconsumed. M8.5 remains unmet; a successor requires a new precommitted public/
train/reusable architecture hypothesis.
