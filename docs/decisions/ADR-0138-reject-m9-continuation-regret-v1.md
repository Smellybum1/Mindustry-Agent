# ADR-0138: Reject M9 counterfactual continuation regret v1

**Status:** Accepted

## Context

ADR-0137 froze one public-only counterfactual continuation-regret candidate
before implementation or optimizer update. The complete public gate passed at
exact implementation commit `1c060bca4a56849ce8c8a7e8cb7b4df6bb94c105`:
the complete Python suite, pinned Java/custom-module checks, repeated live
counterfactual collection, smoke, 79-boundary cross-process/reset/seed
determinism, and the 664-checkpoint/16,200-tick golden replay were green.

Replica A then completed the exact 2,048 unique public roots and all 32 groups
of 256 optimizer steps. Independent validation loaded every group-1-through-32
checkpoint and verified each payload identity and parent link. It also
recomputed the canonical run digest exactly. The authoritative manifest
SHA-256 is
`7df392ddbadb0eaeab2698b86f89245d40c78b550b5f8e0ce1ccbaa3905ae560`;
the canonical run SHA-256 is
`a5c2d10763e12c009836b962b22b54ac28cee3f87d0291c478cc41878bb0880b`;
the compact result SHA-256 is
`86de7be96808fcc1603d332de1bc112b79b20682c6540d83f3b78c9f36d0aea1`.

The final-only public-dev evaluation won 1/40, with mean core health `23.9`,
mean team idle fraction `0.2954330`, 34 rejected learned actions, planner
bundle exact rate `0.4724995`, and mean planner-rank cost `0.4926629`. It
missed all three frozen construction requirements: 30/40 wins, idle below
`0.25`, and zero learned-action rejection.

The training telemetry explains why supervised loss reduction did not
constitute useful continuation learning. Of 16,145 branch rows, 11,874
(`0.7351502`) were planner-inadmissible fixed-cost examples. All rows supplied
the immediate target, only 1,334 reached four ranked boundaries, and none
reached eight or sixteen. Mean group loss fell from `0.111354` to final
`0.0185331`, but final-group source-bundle retention was only `0.203125`.
The exact frozen sampler/stop rule therefore made the nominal long-horizon
heads overwhelmingly immediate-cost copies, while the learned scorer also
failed runtime legality and idle behavior.

## Decision

1. Reject `m9-candidate-native-continuation-regret-v1`.
2. Replica B is prohibited because Replica A reached neither the construction
   floor nor the idle gate.
3. Do not select, repair, rank, or promote the final or any intermediate
   checkpoint. All 32 checkpoints are rejection evidence only.
4. Preserve the public run and exact lineage as negative evidence.
5. Do not tune the fixed boundary, bundle sampler, admissibility treatment,
   horizon, target, model widths, loss, learning rate, optimizer, or budget.
   Such changes would be an unfrozen scalar/mechanism sweep of this rejected
   candidate.
6. The exact sampled continuation-regret mechanism is exhausted. Another
   learned candidate requires a separately prospective owner-authorized
   architecture or supervision-class decision.
7. No confirmation, held-out, restricted, or embargoed manifest or data was
   accessed. M8 held-out-v7 remains sealed.

## Consequences

M9 learned construction remains unmet. Replica B, MAPPO, learned human-session
work, and all restricted evaluation remain blocked. Planner v11 remains an
accepted supervision source only; it was not changed and was absent from
candidate inference. Autonomous model work stops at this governance boundary.
