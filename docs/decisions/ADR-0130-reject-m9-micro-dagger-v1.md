# ADR-0130: Reject M9 micro-DAgger v1

**Status:** Accepted

## Context

ADR-0129 froze maximal intra-update label freshness as the last isolated
pure-CE covariate-shift test. From the exact rejected teacher-forced update-32
model and Adam state, every fixed 64-root macro group was recollected under the
current model before each of eight one-epoch micro updates.

The exact-current-commit gate passed at
`36dbabdd4723c389aeea43afa4e1f6839fdfa423`. Replica A completed 2,048
unique public roots, 16,384 collection episodes, 256 micro updates, and
1,254,627 freshly collected actor-valid labels. All 32 checkpoint parent,
model, optimizer, and content identities validate.

No checkpoint reached the frozen 30/40 construction floor. Macro update 21 was
best at 15/40 wins, mean core health `271.425`, and idle `0.0943284`. Final
macro update 32 reached 8/40, core `150.25`, and idle `0.0905110`.

The authoritative manifest SHA-256 is
`412efca56ce1c4a7e7a71debef9ec5fc13ee905b83fab0b4cf7542964b1fadd2`,
its canonical run SHA-256 is
`690b4a3b6cd8af9763fbbbf42dc071e072637571b3cc2534e39e1176a77fd557`,
and the compact result SHA-256 is
`8c0f857db09681ce7618a00c1621f18aefc79ca91a3d36559bcb9e08d0ddc29b`.

## Decision

1. Reject `m9-candidate-native-micro-dagger-v1`.
2. Replica B is prohibited because Replica A missed construction by 15 wins.
3. Neither macro update 21 nor 32 is selected, repaired, or promotable.
4. Preserve the full public run as rejection evidence.
5. Maximal within-update freshness did not close the construction gap; do not
   authorize a cadence, epoch, root-reuse, or learning-rate sweep.
6. Pure pointwise candidate-native imitation from this lineage is exhausted.
   Another learned candidate requires a separately prospective architecture or
   supervision-class decision with explicit owner direction.
7. No confirmation or held-out data was accessed. M8 held-out-v7 remains
   sealed.

## Consequences

M9 learned construction remains unmet, Replica B and MAPPO remain blocked, and
no learned checkpoint is available for human-session work. Autonomous model
work stops at this governance boundary.
