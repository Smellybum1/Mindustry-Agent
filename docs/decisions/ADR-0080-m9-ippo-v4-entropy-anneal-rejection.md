# ADR-0080: Reject M9 IPPO v4 entropy annealing at construction

**Status:** Accepted

## Context

ADR-0079 froze `m9-ippo-v4-entropy-anneal` before implementation or training.
Its only learning change from v3 was replacing the constant `0.02` entropy
coefficient with the inclusive linear schedule
`0.02 * (32 - update) / 31`, reaching zero at update 32. The unique public
roots, one-use schedule, model, rewards, PPO values, budget, public dev roots,
construction threshold, and fixed shared-expert comparator remained exact.

The full public-only gate passed at exact training commit
`fbca0c6bbc5b4f00ada903f17301211b59fd5b3c`. Replica A then completed all
2,048 train episodes and 32 optimizer updates. The late deterministic frontier
improved sharply: update 30 won 16/40 public-dev episodes and update 31 won
18/40 with mean return `-6.20459`, mean core health `491.4`, and mean idle
`0.09766800`. The zero-entropy final update then fell to 0/40, mean return
`-19.03695`, and mean idle `0.32090273`. No checkpoint reached the frozen
30/40 construction floor.

Stochastic training produced 603 wins, compared with 598 for v1, 513 for v2,
and 585 for v3. Entropy annealing therefore exposed a real late deterministic
consolidation signal, but not a qualifying policy. The canonical full-run
digest is
`69ee6d687d95eaff12871190eccfe2511d63ddbf3860f9ff7b4595a436b1a402`.
The compact public-only result is
`configs/evaluation/m9-ippo-v4-entropy-anneal-result.json`, SHA-256
`e85eb1d267412db47fd81dc0bc0ad9f935ac8c08c42f1d9ee929ed57d2698258`.
No confirmation or held-out namespace was allocated or accessed. M8
held-out-v7 remains sealed.

## Decision

1. Reject `m9-ippo-v4-entropy-anneal`. It is immutable and must not be rerun,
   retuned, extended, or assigned a checkpoint after observing the result.
2. Record construction as failed with no selected checkpoint.
3. Do not run replica B. ADR-0079 authorizes B only after A passes
   construction.
4. Do not start MAPPO, paired promotion comparison, selected-checkpoint
   lineage, confirmation, or held-out evaluation. All require a qualifying
   IPPO checkpoint.
5. Accept a bounded public signal: reducing the entropy incentive created the
   strongest M9 deterministic frontier so far, but the update-32 collapse
   shows that merely reaching zero entropy is not stable consolidation.
6. Before another training recipe, precommit one public-only diagnostic over
   immutable v4 late checkpoints. It must distinguish destructive optimizer
   movement from unstable deterministic mode selection, use fixed public
   roots and RNGs, run in fresh JVMs, remain unable to select or promote a v4
   checkpoint, and report exact model/checkpoint provenance.
7. Any v5 successor must be separately named and prospectively frozen. It may
   isolate one evidence-backed consolidation mechanism, but must keep the
   public construction bar, official argmax evaluation, data governance,
   engine pins, and deterministic externally stepped runtime unchanged.

## Alternatives

- Running replica B is rejected because A failed the explicit construction
  prerequisite.
- Lowering the 30/40 threshold, selecting update 31, stopping at update 31,
  or discarding update 32 is rejected as post-result candidate repair.
- Extending the budget or changing official evaluation to categorical
  sampling is rejected because either would change the observed candidate
  after its result.
- Treating the 18/40 checkpoint as sufficient evidence for MAPPO is rejected
  by ADR-0008 and the accepted M9 entry and construction gates.
- Opening confirmation or held-out evidence is rejected because public
  construction already failed.

## Consequences

- M9.1 remains in progress and MAPPO remains blocked.
- V4's update-aware optimizer, entropy telemetry, exact schedule evidence,
  and fail-closed runner remain reusable infrastructure, but v4 is not a model
  candidate.
- Replica B consumes no CPU budget.
- The next work is a precommitted immutable-checkpoint public diagnostic, not
  another training run or restricted evaluation.
