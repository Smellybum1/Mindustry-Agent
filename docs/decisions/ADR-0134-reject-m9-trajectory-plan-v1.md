# ADR-0134: Reject M9 trajectory plan v1

**Status:** Accepted

## Context

ADR-0133 froze one candidate-native trajectory-supervision architecture from
the exact rejected update-64 model and Adam state. The complete
exact-current-commit gate passed at
`97a558270b8c7c4c9e92b000fdcfb696e1c4ee98`.

Replica A then completed the frozen 2,048 unique public roots, 32 optimizer
updates, and all 32 public-dev evaluations. Every checkpoint payload, model
state, optimizer state, selection row, and parent link from lineage update 65
through 96 validates exactly.

No checkpoint reached the frozen 30/40 construction floor. Continuation update
3, lineage update 67, was best at 12/40 wins, mean core health `239.325`, and
idle `0.0890581`. Final continuation update 32 reached 9/40, core `192.6`, and
idle `0.0885152`.

The authoritative manifest SHA-256 is
`9486145007d33895dd057445fdd05c2f7a9d0c2c727d92595bfe119811e1e517`,
its canonical run SHA-256 is
`d4f2653464606f348fb238e0cd408eab2d1f3e08983f7772d2d41e6f8a172fb3`,
and the compact result SHA-256 is
`cf2a1fb00d732ebde6661c2679f759c7beadf3677799586b7437799c85a412e3`.

## Decision

1. Reject `m9-candidate-native-trajectory-plan-v1`.
2. Replica B is prohibited because Replica A missed construction by 18 wins.
3. Neither continuation update 3 nor 32 is selected, repaired, promoted, or
   available for learned human-session work.
4. Preserve the full public run as rejection evidence.
5. The fixed four-slot task-family head did not convert the accepted
   trajectory-divergence signal into construction. Do not authorize a
   plan-slot, horizon, bias-scale, loss-coefficient, epoch, learning-rate, or
   initialization sweep.
6. Another learned candidate requires a separately prospective architecture
   or supervision-class decision. This result does not authorize reward, PPO,
   MAPPO, checkpoint repair, or restricted-data access.
7. No confirmation or held-out data was accessed. M8 held-out-v7 remains
   sealed.

## Consequences

M9 learned construction remains unmet, Replica B and MAPPO remain blocked, and
no learned checkpoint is available for human-session work. Autonomous model
work stops at this governance boundary.
