# ADR-0078: Accept the M9 v3 policy-mode diagnostic result

**Status:** Accepted

## Context

ADR-0077 prospectively froze a bounded public-only diagnostic after ADR-0076
rejected `m9-ippo-v3-diverse2048`. The immutable update-29 checkpoint had won
0/40 deterministic public-dev episodes but came from a run with 585/2,048
stochastic train wins. The diagnostic fixed one argmax stream, four
categorical streams, 40 existing public roots per stream, two fresh JVMs, and
a 32/160 stochastic-win signal threshold before execution.

The implementation was committed at
`8f574ef2b68ce81c126ab66fc8fea840fbb4c1d7`. Both fresh JVM runs reproduced
exactly with canonical run digest
`8b0b5fdd9083953d7ff461c0cc2daec83c472619cada13b45e5483f97b6d0bba`.
The model digest remained
`87d85c4c78ae4c2d40e6c7f4bc67154bdd7ad94aa582baf4450048bd7826186e`.

Argmax reproduced the immutable 0/40 result. Fixed categorical sampling won
56/160 episodes (35%), with per-stream wins 13, 11, 17, and 15. Its aggregate
mean return was `-7.891955`, mean core health `284.48125`, and mean idle
`0.09732699`, versus argmax return `-14.022125`, core `0.0`, and idle
`0.12201736`. The compact result is
`configs/evaluation/m9-ippo-v3-policy-mode-diagnostic-result.json`, SHA-256
`50c823d2d3d6123db544ce33844c72cd4a3370812454ea3349e71e7b3fda18b1`.
No confirmation or held-out data was accessed.

## Decision

1. Accept the predeclared stochastic survival signal: 56 wins exceeds the
   frozen 32/160 threshold, and every fixed sampling stream contributes.
2. Keep v3 rejected with no selected checkpoint. The diagnostic is explanatory
   evidence only and does not authorize replica B, MAPPO, training, promotion,
   or stochastic official evaluation.
3. Retain deterministic argmax as the construction and deployment boundary.
   Reproducible coordination behavior remains a requirement.
4. Conclude that root repetition is not the immediate next mechanism to vary.
   The v3 policy distribution contains transferable successful behavior, but
   its deterministic mode does not consolidate that behavior.
5. Recommend that v4 derive from v3 and isolate one policy-consolidation
   mechanism: prospectively frozen entropy-coefficient annealing from the
   existing 0.02 toward zero over the unchanged 32 updates. All roots, model,
   rewards, PPO values, budgets, RNGs, dev protocol, and thresholds should
   remain exact unless a separate ADR justifies otherwise.
6. V4 requires its own precommit, implementation tests, exact-commit full gate,
   and Replica-A-first continuation rule before any trajectory.

## Alternatives

- Promoting stochastic sampling is rejected because 56/160 remains below the
  official 30/40 construction floor and action draws would change deployable
  behavior.
- Distilling successful v3 trajectories is deferred because it introduces a
  replay-selection policy and supervised objective in the same step.
- Expert behavior cloning is deferred because it adds teacher data and a
  supervised objective; it remains a later option if entropy annealing fails.
- Retuning learning rate, PPO clipping, recurrent length, root count, or budget
  is rejected for v4 because none isolates the observed policy-mode gap.
- Opening confirmation or held-out evidence is rejected; the public diagnostic
  already answered its bounded question.

## Consequences

- The policy-mode diagnostic is complete and immutable.
- M9.1 remains in progress and MAPPO remains blocked.
- The next authorized planning action is a separately precommitted v4 entropy
  annealing recipe; no v4 model update exists yet.
