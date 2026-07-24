# ADR-0126: Accept M9 low planner-correction signal

**Status:** Accepted

## Context

ADR-0125 prospectively froze a paired public-only intervention over the exact
rejected update-64 and update-96 final checkpoints. The complete preflight
passed at implementation commit `1988b79fc5`, and the evidence-commit gate
passed again before execution. The full diagnostic then completed from
`2183a33e30` without model or optimizer mutation or restricted-data access.

Both fresh-JVM reports and every terminal reset replay matched exactly. Both
baselines reproduced their frozen 13/40 wins and mean core health exactly:
`242.975` for update 64 and `234.425` for update 96. The diagnostic is valid.

For update 64, `correct_first` reached 10/40 and `correct_all` reached 9/40
with mean core health `134.325`. Relative to baseline, `correct_all` preserved
eight wins, harmed five wins, rescued one loss, and left 26 losses unchanged;
the descriptive exact paired p-value is `0.21875`.

For update 96, `correct_first` remained 13/40 but reduced mean core health to
`224.75`. `correct_all` again reached 9/40 with mean core health `134.325`.
It preserved seven wins, harmed six, rescued two, and left 25 losses unchanged;
the descriptive exact paired p-value is `0.2890625`.

The full report SHA-256 is
`799a845b98ddc7082eb920df53aa7af9b533f7f187a7c5e7803b2d5986ef3d48`,
and its canonical report SHA-256 is
`ee99794e2ea46ad891c2931538111d42f21523db3ddf32a0cfea3423de90c518`.
The compact result SHA-256 is
`af4725e0fa034761d3cb69e46cfc2c05014724e8c6533544cfaccad416d2c7df`.

## Decision

1. Accept the frozen `low_correction_signal`. Both `correct_all` cells are
   9/40, below the prospective at-most-21/40 threshold.
2. Reject online planner correction—both one-shot and every-disagreement
   variants—as an M9 construction or deployment mechanism.
3. Do not use this result to select, repair, promote, or further weight either
   rejected checkpoint. No successor training is authorized by this result.
4. Do not infer that every individual planner label is wrong or that every
   baseline disagreement is causally irrelevant. The intervention changed
   future states and replaced the complete actor-authoritative planner bundle
   at trigger boundaries; the supported claim is that this governed online
   correction rule has low and directionally harmful value.
5. Treat the combined evidence from ADR-0124 and this result as negative for
   further scalar disagreement weighting, planner takeover, first-K correction
   sweeps, and post-result checkpoint repair.
6. The next recommended design question is isolated recurrent sequence
   coherence: contiguous unroll presentation with truncated backpropagation
   through time, without simultaneously adding EMA, replay, a learning-rate
   change, a planner change, reward, PPO, or MAPPO. This result permits only
   drafting a separately named prospective ADR for that question; it does not
   authorize implementation or model work.
7. No confirmation or held-out data was accessed. M8 held-out-v7 remains
   sealed.

## Alternatives

- A correction-strength or first-K sweep is rejected as post-result tuning.
- Selecting update 94 is rejected because it was descriptively chosen after
  the failed hard-example run and was excluded prospectively.
- Treating the paired p-values as a promotion or rejection threshold is
  rejected; they are descriptive, while the replicated 9/40 cells determine
  the frozen classification.
- Bundling truncated BPTT with EMA, replay, optimizer, or architecture changes
  is rejected because it would not isolate the sequence-coherence hypothesis.

## Consequences

The public disagreement line is closed as a direct intervention target:
ordinary scalar reweighting failed construction and online planner correction
reduced wins on both primary checkpoints. M9 learned construction remains
unmet. Any sequence-coherence successor requires a new prospective protocol,
exact source and optimizer hashes, deterministic contiguous-unroll semantics,
budget/replica rules, and a complete exact-commit preflight before model work.
