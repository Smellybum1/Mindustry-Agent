# ADR-0029: V18 scorecard-aligned quality reward

**Status:** Accepted

## Context

V17 reproduced exactly, retained 9/10 construction wins, and reduced reusable
mean idle to 0.08594077. It still failed permanent-greedy idle by 0.04162898,
while permanent announcements and both recovery comparisons remained
uncertain. V16-to-V17 idle pressure improved idle but moved mean permanent
recovery difference from -13.23 to only -7.15 ticks. Across V17's ten reusable
roots, idle-gap and recovery-gap correlation is approximately -0.08, so another
idle-only coefficient step does not address recovery causally.

The scorecard defines recovery as ticks from an agent's first loss until a
different agent starts one of the lost agent's prior task types. The training
rollout already receives simulation-thread-authored unit-destroy and structured
task events needed to reproduce that definition without reading mutable game
state or adding inference behavior.

## Decision

1. Reward v2 accepts optional `recovery_delay_tick_cost` and
   `recovery_delay_tick_cap` fields. When absent, historical configs retain
   their exact component keys and behavior. Providing only one field, a
   negative value, counter rollback, or an invalid event tick fails the run.
2. Recovery delay is separately metered as
   `reward.penalty.recovery_delay_ticks`. The accumulator snapshots each lost
   agent's prior structured task types at the first authoritative unit-destroy
   event, charges deterministic elapsed ticks until another agent starts a
   matching type, and continues charging an unrecovered role. Same-agent and
   unrelated starts do not recover it. The component is penalty-only and
   capped, so loss or non-recovery cannot farm positive reward.
3. V18 keeps V17's runtime, roots, model, optimizer, RNGs, schedule, selection
   rule, terminal/milestone terms, and all other reward fields fixed. It changes
   the remaining scorecard pressures once:
   - idle cost `0.002 -> 0.004`, with idle cap fixed at `5.0`;
   - duplicate-work cap `2.0 -> 4.0`, preserving the busywork ordering at the
     stronger idle slope while remaining inactive at V17's two incidents;
   - announcement cost `0.005 -> 0.01`, with cap fixed at `1.0`;
   - recovery delay cost `0.001` per tick, capped at `3.0`.
4. Exact-config adversaries must prove all prior reward properties plus exact
   recovery latency, unrelated/same-agent exclusion, chunk invariance, and
   post-cap zero charge. The full Python suite must pass before training.
5. Two pinned 2,048-episode replicas must reproduce checkpoint, frontier, model
   state, replay, and full-run digest exactly. Reusable dev-v1 must then pass
   construction and both permanent/matched scorecards.
6. Retire V17's unopened dev-v13. Freeze dev-v14 now at globally disjoint roots
   `141001..141160` for one exclusive confirmation only after every reusable
   gate passes. Held-out-v4 remains sealed.

## Consequences

- V18 targets all three remaining measured blockers without changing action
  masks, inference logits, structured communication authority, or engine state.
- Recovery telemetry is derived only from drained structured/game events and
  cumulative reward state, preserving external fixed-step determinism and
  simulation-thread ownership.
- V18 may still lose construction capacity or fail reusable scorecards. It
  stops before dev-v14 on any failure.

Pretraining validation passes all 43 exact-config adversaries and the full
138-test Python suite. Config SHA-256 is `fa6cdcfe3820da06...`; adversary report
SHA-256 is `96058a7e7c9dd6f0...`.

The two pinned training replicas reproduce exactly and select update 22 at
9/10 construction wins with mean idle 0.10978972. Checkpoint
`0984700a681bfdc5...`, model state `2fd25b37851c1d97...`, replay
`d098fba29b3de64f...`, full run `127410b515f6917e...`, and direct lineage
`b226742761e58852...` match. Reusable dev-v1 rejects promotion: permanent-greedy
idle regresses by 0.06547793 (95% CI +0.03188818..+0.09708444), and recovery is
uncertain against both governed scorecards. Dev-v14 therefore remains unopened
and held-out-v4 remains sealed. The reusable preflight report SHA-256 is
`37d9db2950801f7f2e46ee28e831b54c0cca7201c4bab9cce490580384e77384`.
