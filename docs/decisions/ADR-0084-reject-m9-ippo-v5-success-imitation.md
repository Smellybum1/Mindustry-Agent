# ADR-0084: Reject M9 IPPO v5 success-conditioned self-imitation

**Status:** Accepted

## Context

ADR-0083 froze one bounded successor to rejected v4: add coefficient `0.02`
sampled-action negative log probability over actor-valid transitions from
winning episodes in the current public training update. Implementation commit
`d6969679ad7e500756660f2a820815b1998a51f9` passed deterministic twin optimizer
evidence. Exact-current-commit pretraining authority at
`84af0016f69f31a5d3b416ee95ad14c6fd9c9b42` passed all 430 Python tests, pinned
Java checks, M9 focused checks, smoke, determinism, and golden replay without
confirmation or held-out access.

Replica A then completed all 2,048 unique-root episodes and 32 updates. The
self-imitation filter was active: 559 winning episodes contributed 27,614
actor-valid transitions across 6,188 active minibatches. Training nevertheless
won only 559/2,048 episodes, versus v4's 603/2,048. Deterministic public-dev
performance peaked at update 7 with 1/40 wins and finished at update 32 with
0/40. No checkpoint met the unchanged 30/40 and idle `<0.25` construction bar.

The compact result is
`configs/evaluation/m9-ippo-v5-success-imitation-result.json`, SHA-256
`f969cb595526763cdf6e9f2938910c3319108680751a24cf2ade6cf869012b55`.
The authoritative run manifest SHA-256 is
`cdf0c86e3b5f5fa89952683acc904683c7b48c92d762f59c9132bc86aa2f83b6`;
its full-run reproducibility digest is
`ef37b266b9f061eac8699799eaa664575b0fe4244a6f977e53123e40d828306d`.

## Decision

1. Reject `m9-ippo-v5-success-imitation`. It does not satisfy M9.1
   construction.
2. Replica B is prohibited because Replica A did not pass construction. V5
   checkpoints cannot be selected, promoted, retuned, resumed, or used for a
   direct v5 success claim.
3. Preserve the full Replica A manifest, checkpoints, logs, and compact result
   as public development evidence.
4. Do not interpret the failure as evidence against success-conditioned
   learning in general. It rejects only ADR-0083's exact within-update,
   eight-epoch, coefficient `0.02` mechanism.
5. Before any v6 recipe or training, prospectively freeze a public-only
   diagnostic of v5's best and final checkpoints. It may measure deterministic
   argmax, fixed-seed categorical retention, action-mode margins, and
   successful-action probability response. It may not select, repair, train,
   promote, or access confirmation/held-out data.
6. M8 held-out-v7 remains sealed. No M9 confirmation or held-out namespace is
   authorized.

## Alternatives

- Running Replica B is rejected because ADR-0083 makes construction-passing
  Replica A a hard prerequisite.
- Selecting update 7 is rejected because 1/40 wins is far below the frozen
  30/40 bar and its idle fraction is `0.3876057735814631`.
- Reducing the coefficient or number of imitation applications immediately is
  rejected as post-result retuning without a precommitted diagnostic.
- Reverting to v4 update 31 is rejected because ADR-0080 already rejected v4
  and no rejected checkpoint may be promoted.

## Consequences

- M9.1 remains open.
- V5 is a completed negative construction result, not a runtime failure.
- The next authorized work is a separately precommitted, immutable-checkpoint,
  public-only diagnostic; no successor training is authorized by this ADR.
