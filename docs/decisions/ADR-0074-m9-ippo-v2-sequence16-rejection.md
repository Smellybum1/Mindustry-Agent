# ADR-0074: Reject M9 IPPO v2 sequence-16 at construction

**Status:** Accepted

## Context

ADR-0073 froze `m9-ippo-v2-sequence16` before implementation or training. Its
only learning change from v1 was deterministic truncated recurrent
backpropagation through same-seat windows of at most 16 boundaries. The full
public-only gate passed at the exact training commit
`e6a29fb35142fa2686625d3267824e07cffbc284`.

Replica A then completed all 2,048 public train episodes and 32 optimizer
updates. No checkpoint reached the frozen 30/40 public construction threshold.
The best result was update 2 at 11/40 wins, mean return `-14.70004`, mean core
health `260.425`, and mean idle `0.29205803`. The final update was 0/40.
Training produced 513 wins, below v1's 598, and the canonical full-run digest
is `ba57726bd57a7286e030fd9910928ea11854bcc3151e1bef054b182cc02755ef`.

The compact public-only result is
`configs/evaluation/m9-ippo-v2-sequence16-result.json`, SHA-256
`42b4a2c4ee6eb542be7f857c3c62feba4edc4905559f64118c3fe8452ed00f22`.
No confirmation or held-out namespace was allocated or accessed. M8
held-out-v7 remains sealed.

## Decision

1. Reject `m9-ippo-v2-sequence16`. It is immutable and must not be rerun,
   retuned, or assigned a checkpoint after observing the result.
2. Record construction as failed with no selected checkpoint.
3. Do not run replica B. ADR-0073 authorizes B only after A passes
   construction.
4. Do not start MAPPO, paired promotion comparison, or selected-checkpoint
   lineage work. All require a qualifying IPPO checkpoint.
5. Reject sequence-16 recurrent credit as the explanation for v1's public
   generalization failure. It preserved deterministic execution but regressed
   both the public frontier and repeated-root training.
6. Any successor must be separately named and prospectively frozen. Public
   evidence now favors testing training-root diversity while returning to the
   accepted v1 one-boundary optimizer; the exact seed namespace, schedule,
   recipe, gates, and continuation rule require a new ADR before trajectories.

## Alternatives

- Running replica B is rejected because A failed the explicit construction
  prerequisite.
- Lowering the threshold, selecting update 2, extending the budget, or tuning
  sequence length is rejected as post-result redefinition.
- Starting MAPPO is rejected by ADR-0008, ADR-0070, and ADR-0073.
- Opening confirmation or held-out evidence is rejected because public
  construction already failed decisively.

## Consequences

- M9.1 remains in progress and MAPPO remains blocked.
- The v2 implementation, deterministic sequence tests, exact-commit gate, and
  manifest machinery remain valid reusable evidence, but v2 is not a model
  candidate.
- Replica B consumes no CPU budget.
- The next work is a public-only, prospectively governed IPPO successor aimed
  at the repeated-root training distribution, not another recurrence change.
