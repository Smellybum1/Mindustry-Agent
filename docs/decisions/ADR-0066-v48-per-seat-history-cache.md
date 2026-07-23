# ADR-0066: V48 per-seat scripted history cache

**Status:** Accepted

## Context

V47 proves the single-brain death-failover mechanism but fails reusable-v2
before confirmation. It wins 125/160 versus permanent greedy's 84/160 and
matched greedy's 22/160. Every win/control gate and all but two scorecard rows
pass. Permanent idle is effectively equal but uncertain (`-0.00006783`, CI
`[-0.00408121,+0.00412951]`), while one automatic `plan_removed` event makes
non-forced abandonment uncertain against both greedy comparators.

Public-only diagnostics close simpler successors. Highest-living failover falls
to 120 wins and worsens idle. Ten-win frontier update 27 eliminates abandonment
but worsens idle. The minimum-eligible, lowest-idle update 32 reaches 128 wins,
zero abandonment, and favorable mean idle `-0.00288642`, but its CI still
crosses zero at `+0.00107884`. Another checkpoint-ranking change cannot pass
the frozen gate.

The remaining variance concentrates after authority transfer. On update 32,
candidate-minus-permanent idle grouped by final active seat is `-0.00255224`
for seat 0, `+0.00344672` for seat 1, and `-0.00609440` for seat 2. V47 resets
`SelectorHistory` on transfer even though the target seat has just been acting
under the deterministic scripted policy at authoritative boundaries. This
throws away the exact lagged context that feature v3/model v5 were designed to
use.

The reward-pressure, teacher-strength, failover-selection, and frontier-ranking
lines are closed by existing evidence. No confirmation, retired, or held-out
membership was read.

## Decision

1. V48 retains exactly one learned brain, at most one learned model evaluation,
   and at most one learned action per authoritative boundary. It starts at seat
   0 and uses V47's sticky, death-only, lowest-living failover.
2. Replace V47's transfer-time history reset with one deterministic
   `SelectorHistory` cache per seat. All caches start at the existing all-zero
   initial value on reset.
3. At each authoritative boundary, the active seat records the same effective
   submitted ordinary action and structured feature snapshot as V47.
   Every living nonactive seat records its canonical submitted scripted action
   and that seat's structured feature snapshot. Dead seats retain their last
   cache without update.
4. On death failover, the learned brain receives the target living seat's
   cached prior boundary. It does not receive hidden state, future data, raw
   engine objects, wall-clock information, another seat's cache, or any
   privileged observation.
5. Per-seat snapshots use only the already-drained observation, mask, task
   board, boundary reasons, canonical adaptive expert proposal, and dynamic
   nonactive partner intents for that seat. They require no additional mutable
   game-state read and remain on the existing simulation-step client path.
6. Feature v3, model v5, reward v2, control v2, action vocabulary, DEFER rules,
   teacher/relabel behavior, and server action bundle remain exact. The new
   history-cache schema is explicit in config, manifest, lineage, telemetry,
   reusable preflight, confirmation, and final gates.
7. Focused tests must prove reset-local cache initialization, nonactive
   canonical-action updates, active effective-action updates, dead-cache
   retention, target-cache adoption on transfer, per-seat partner-intent
   isolation, exactly one model/action authority, deterministic replay, matched
   control parity, and bit-compatible V47 behavior when failover is absent.
8. Training roots, public dev/reusable sets, model, reward, optimizer,
   warmup/rehearsal, 2,048-episode budget, RNG values, scripted opening, engine
   pins, minimum 9/10 construction wins, idle `<0.25`, DEFER `<=0.25`, and both
   unchanged reusable-v2 scorecards remain V47-exact.
9. Dev-v44 is retired unopened/unconsumed. V48 reserves 160-root dev-v45 in
   `[14_000_000_000,15_000_000_000)`. Membership may be constructed value-free
   only after the implementation and complete public/pretraining boundary are
   committed.
10. Held-out-v6 remains sealed/unconsumed. No V48 confirmation or final access
    is authorized by this precommit.

## Alternatives

- Highest-living failover is rejected by its 120/160 public diagnostic.
- Reclassifying `plan_removed` after observing the gate is rejected; the frozen
  scorecard stands.
- Frontier updates 27 and 32 are rejected because both fail permanent idle.
- More idle reward, cap changes, and low teacher regularization are rejected by
  the completed V15-V20 evidence line.
- Training all seats or choosing a seat from learned scores remains M9 scope.
- Expanding reusable-v2 again is rejected as post-result goalpost movement.

## Consequences

- V48 adds bounded client-side structured bookkeeping for three seats but no
  second learned brain, model call, action, engine mutation, or thread-owner
  exception.
- The cache may fail to improve post-transfer idle or may harm survival. Any
  construction, reproducibility, control, or reusable-scorecard failure rejects
  V48 before dev-v45.
- The immutable config is
  `configs/training/m8-selector-v48-per-seat-history-cache.json`, SHA-256
  `714bd13db0ffee6f70c2d777f5bfa9c45221f77fe173cef35c15d3ead5441d2c`.
- The value-free confirmation umbrella is
  `configs/evaluation/m8-selector-v48-confirmation-umbrella.json`, SHA-256
  `656602be6dd5c3cf7107420d44f9ba8543f9bfc4170a28930ce3e382a7cec7b7`.
- This decision authorizes implementation and public/pretraining verification
  only after commit. It does not authorize membership construction, training,
  reusable evaluation, confirmation, or held-out access.
