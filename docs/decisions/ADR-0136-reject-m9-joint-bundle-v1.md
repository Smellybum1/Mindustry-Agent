# ADR-0136: Reject M9 joint bundle v1

**Status:** Accepted

## Context

ADR-0135 froze one prospective joint-bundle architecture from the exact
rejected update-64 model and Adam state. The complete exact-current-commit gate
passed at `c05366454d95fc51e0347be2b7deecb065678c00`.

Replica A then completed the frozen 2,048 unique public roots, 32 optimizer
updates, and all 32 public-dev evaluations. Independent post-run validation
loaded every checkpoint and verified every payload identity, model state,
optimizer state, selection row, and parent link from lineage update 65 through
96. The manifest's canonical run identity also recomputes exactly.

No checkpoint reached the frozen 30/40 construction floor. Continuation update
9, lineage update 73, was best at 13/40 wins, mean core health `193.7`, and
idle `0.0891664`. Final continuation update 32 reached 8/40, core `152.05`,
and idle `0.0916070`. The idle gate passed throughout; construction was the
failure.

The authoritative manifest SHA-256 is
`8ca4065a1e47d8a80123ab3c8b3d683de249998f3d5df135dc27c6d4833d481e`,
its canonical run SHA-256 is
`61f0be9f41f58d1864a7d581663a679e6d27f7815051818adea16d3c61f15527`,
and the compact result SHA-256 is
`ca3d905c7679bb44e1e447233d838cdd2dd39aecef35ab3d30ee03d5c8be8e3d`.

## Decision

1. Reject `m9-candidate-native-joint-bundle-v1`.
2. Replica B is prohibited because Replica A missed construction by 17 wins.
3. Neither continuation update 9 nor 32 is selected, repaired, promoted, or
   available for learned human-session work.
4. Preserve the complete public run as rejection evidence.
5. Pairwise same-boundary compatibility trained to high supervised accuracy,
   but normalized legal joint-bundle NLL did not convert planner labels into
   construction. Do not authorize a head-width, descriptor, pairwise-weight,
   loss-scale, epoch, learning-rate, initialization, or bundle-enumeration
   sweep.
6. Another learned candidate requires a separately prospective architecture
   or supervision-class decision. This result does not authorize reward, PPO,
   MAPPO, target IDs, planner changes, checkpoint repair, or restricted-data
   access.
7. No confirmation or held-out data was accessed. M8 held-out-v7 remains
   sealed.

## Consequences

M9 learned construction remains unmet, Replica B and MAPPO remain blocked, and
no learned checkpoint is available for human-session work. Autonomous model
work stops at this governance boundary.
