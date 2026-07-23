# ADR-0082: Accept the M9 v4 deterministic-mode instability signal

**Status:** Accepted

## Context

ADR-0081 prospectively froze an immutable-checkpoint diagnostic to distinguish
whole-distribution damage from deterministic mode movement across rejected v4
updates 31 and 32. Each checkpoint ran on the same 40 public roots under one
argmax stream and four fixed categorical streams. The complete 400-episode
matrix ran twice in fresh JVMs, and both reports matched exactly.

The deterministic streams reproduced the immutable manifest: update 31 won
18/40 and update 32 won 0/40. Update 31 won 64/160 categorical episodes across
the four fixed streams (`15`, `18`, `21`, and `10`). Update 32 still won 60/160
(`11`, `20`, `13`, and `16`), retaining `60/64 = 93.75%` of update 31's
categorical wins despite the 18-win argmax drop.

The frozen mode-instability rule required update 32 to retain at least 32
categorical wins and at least 80% of update 31's categorical wins. It passed.
The optimizer-distribution-collapse rule required retention of at most 50%; it
failed. The exact fresh-JVM run digest is
`a69c48c6120b87f1465326fb6d5ffed29c6d5b225d51c221a2ff8252675674aa`.
The full report SHA-256 is
`c82fa1f01c045a537540e64e96f215b368a631de851dc4acf51500655231083e`.
The compact public result is
`configs/evaluation/m9-ippo-v4-late-checkpoint-diagnostic-result.json`,
SHA-256
`727309809788960122f7a092f6de0df3328b7f3373aff7d06437050adda54d73`.
No restricted data was accessed.

## Decision

1. Accept the predeclared `deterministic_mode_instability` diagnostic outcome.
   Reject the `optimizer_distribution_collapse` hypothesis for this boundary.
2. Keep v4 rejected and immutable. The diagnostic does not select update 31,
   repair update 32, authorize Replica B, or change the construction floor.
3. Do not start MAPPO, confirmation, or held-out evaluation.
4. The next candidate may isolate one successful-mode consolidation mechanism:
   success-conditioned self-imitation over the candidate's own sampled public
   training trajectories. Its purpose is to increase the deterministic
   probability of unforced actions that occurred in winning episodes.
5. A v5 precommit must freeze the exact loss, coefficient, actor-valid
   transition filter, interaction with PPO and entropy, telemetry, data flow,
   budget, roots, RNGs, and gates before implementation or training. It must
   use only within-candidate public training data, with no external teacher,
   post-hoc replay selection, extra episodes, or restricted evidence.
6. Until that separate precommit exists, no new model update or training
   trajectory is authorized.

## Alternatives

- An optimizer-step stabilizer is deferred because update 32 preserved 93.75%
  of update 31's categorical wins; the frozen collapse criterion did not fire.
- Selecting or blending rejected v4 checkpoints is rejected because it would
  repair a failed candidate after observing its public result.
- Negative entropy, lower temperature, or stochastic production inference is
  rejected as the next direction because none makes sampled successful actions
  specifically authoritative; argmax production remains the requirement.
- External expert distillation is deferred because the diagnostic supports
  using the candidate's own successful public behavior without new teacher
  data.

## Consequences

- M9.1 remains in progress and MAPPO remains blocked.
- The v4 policy distribution demonstrably retains substantial public survival
  behavior after its deterministic mode collapses.
- The next work is a separate v5 self-imitation precommit, not implementation,
  training, or restricted evaluation.
