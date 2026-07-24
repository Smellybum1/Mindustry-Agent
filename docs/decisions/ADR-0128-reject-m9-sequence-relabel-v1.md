# ADR-0128: Reject M9 sequence relabel v1

**Status:** Accepted

## Context

ADR-0127 froze one isolated sequence-coherence continuation from the exact
rejected update-64 model and Adam state. The only learning change was
contiguous truncated backpropagation through non-overlapping 16-boundary
per-seat windows. The deterministic student, planner labels, masks, public
2,048-root schedule, optimizer values, budget, and public-dev gate were
otherwise unchanged.

The complete exact-current-commit gate passed at
`cfffa026daef6324d854aff5557ffe6fbd376e82`. Replica A then completed all
2,048 public train episodes and 32 continuation updates. It collected 158,514
unchanged actor-valid labels and 52,018 loss-masked context transitions.
Windows retained 25,373 of those context transitions around supervised labels
and omitted 26,645 context transitions in 1,720 zero-label windows. Training
won 576/2,048 episodes.

No checkpoint reached the frozen 30/40 public construction floor. Update 18
was best at 12/40 wins, mean core health `208.95`, and mean team idle fraction
`0.0887584235`. Final update 32 reached 10/40, mean core health `196.475`, and
idle `0.0886239959`. Both are below the rejected source's frozen 13/40 result.

All 32 checkpoint parent links, model states, optimizer states, and content
identities validate from the source through lineage update 96. The
authoritative manifest SHA-256 is
`367cca23d30ea6c89201f6d94bf7e3a813c0cd4d4234209b8fa3df4718d1c7a4`,
its canonical run SHA-256 is
`d8830beec8cc3e2da8e2c63ea8c54f66fab5accfe8f3eed390a166cc5283a94d`,
and the compact result SHA-256 is
`156e12d2fb8b8e46b020cbd3b932f8e4e9f7043210169910fdf5da32518ca766`.

## Decision

1. Reject `m9-candidate-native-sequence-relabel-v1`.
2. Replica B is prohibited because Replica A missed construction by 18 wins.
3. Neither update 18 nor update 32 is selected, repaired, promotable, or
   authorized to initialize another optimizer.
4. Preserve the public run, checkpoints, logs, manifest, and compact result as
   rejection evidence.
5. Do not infer that longer or overlapping windows, retained zero-label
   windows, a changed learning rate, replay, weighting, planner changes,
   reward, PPO, or MAPPO are authorized.
6. Any successor requires a separately named prospective decision grounded in
   a new public-only synthesis or explicit owner direction before
   implementation or model work.
7. No confirmation or held-out data was accessed. M8 held-out-v7 remains
   sealed.

## Alternatives

- Replica B is rejected by the frozen conditional policy.
- Selecting update 18 is rejected: it underperforms the rejected 13/40 source
  and remains far below construction.
- Retuning sequence length or window admission after seeing this result is
  rejected as post-result repair.
- Falling back to hard-example pressure or planner takeover is rejected by
  ADR-0124 and ADR-0126.

## Consequences

M9 learned construction remains unmet and MAPPO remains blocked. The public
evidence now rejects both extra disagreement pressure and this isolated
sequence-coherence mechanism for the current candidate-native representation.
Autonomous model work stops at this governance boundary; further work requires
a new prospective public plan and cannot use confirmation or held-out data.
