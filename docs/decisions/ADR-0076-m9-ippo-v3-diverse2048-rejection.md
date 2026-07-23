# ADR-0076: Reject M9 IPPO v3 diverse-2048 at construction

**Status:** Accepted

## Context

ADR-0075 froze `m9-ippo-v3-diverse2048` before implementation or training. Its
only learning change from v1 was replacing 32 repeats of 64 public train roots
with 2,048 unique public roots used exactly once. The one-boundary optimizer,
model, rewards, PPO values, budget, public dev roots, construction threshold,
and fixed shared-expert comparator remained exact.

The full public-only gate passed at exact training commit
`89de310520a5407de7912345ddf8462b7b87c65c`. Replica A then completed all
2,048 train episodes and 32 optimizer updates. No checkpoint won a public dev
episode. The best return was update 29 at 0/40 wins, mean return `-14.022125`,
mean core health `0.0`, and mean idle `0.12201736`. The final update was 0/40,
mean return `-20.0059`, and mean idle `0.49370650`.

Stochastic training produced 585 wins, close to v1's 598 and above v2's 513,
despite deterministic public-dev evaluation remaining 0/40 throughout. The
canonical full-run digest is
`b0830c2b7d1b9cdca352c2d02c9b262a9364949949a940e320e2a5d16c90357f`.
The compact public-only result is
`configs/evaluation/m9-ippo-v3-diverse2048-result.json`, SHA-256
`2e3ed1c113bcd1c0d5de5956d8ff7ea7b413d97be58faf1848b5ce98ee7eafe9`.
No confirmation or held-out namespace was allocated or accessed. M8
held-out-v7 remains sealed.

## Decision

1. Reject `m9-ippo-v3-diverse2048`. It is immutable and must not be rerun,
   retuned, extended, or assigned a checkpoint after observing the result.
2. Record construction as failed with no selected checkpoint.
3. Do not run replica B. ADR-0075 authorizes B only after A passes
   construction.
4. Do not start MAPPO, paired promotion comparison, or selected-checkpoint
   lineage work. All require a qualifying IPPO checkpoint.
5. Reject repeated train-root exposure as the sole explanation for v1's
   public generalization failure. Unique-root stochastic training retained
   substantial survival while the deterministic policy failed every dev root.
6. Before another training recipe, precommit one bounded public diagnostic
   that distinguishes stochastic-policy survival from deterministic argmax
   collapse using immutable v3 checkpoints, fixed public roots, and fixed RNG
   seeds. It cannot select, promote, or repair a v3 checkpoint.
7. Any v4 training successor must be separately named and prospectively
   frozen after that diagnostic. It must isolate one learning mechanism aimed
   at converting successful exploratory behavior into a robust deterministic
   policy.

## Alternatives

- Running replica B is rejected because A failed the explicit construction
  prerequisite.
- Lowering the threshold, selecting update 29, extending the budget, or
  changing evaluation to stochastic action sampling is rejected as
  post-result candidate repair.
- Combining root diversity with sequence backpropagation is rejected because
  v2 already rejected the recurrence mechanism and the combination would mix
  changes.
- Starting MAPPO is rejected by ADR-0008 and the accepted M9 construction
  gates.
- Opening confirmation or held-out evidence is rejected because public
  construction already failed decisively.

## Consequences

- M9.1 remains in progress and MAPPO remains blocked.
- V3's diverse-root runner, exact schedule evidence, and fail-closed
  pretraining authority remain reusable infrastructure, but v3 is not a model
  candidate.
- Replica B consumes no CPU budget.
- The next work is a precommitted public-only policy-mode diagnostic, not
  another training run or restricted evaluation.
