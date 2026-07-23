# ADR-0072: Reject M9 IPPO v1 at the public construction gate

**Status:** Accepted

## Context

ADR-0070 froze `m9-ippo-v1` before training: two independent CPU replicas,
2,048 public train episodes and 32 optimizer updates each, evaluation after
every update on all 40 public dev roots, and no eligible checkpoint below 30
wins or at mean team idle greater than or equal to `0.25`. ADR-0071 corrected
the forced-control validator before the clean replicas and required a new
exact-commit complete gate.

The complete gate passed from commit
`eabd0ce978f860e9bf8d4d1d2341d34c3ea65123`. Clean replicas A1 and B1 then
completed the entire immutable budget in independent processes. Their raw
manifests are byte-identical at SHA-256
`53dd0b29a29cfe85a77308e96ea0fd4a12cfcbb5815936e3f0cca147e5ecf443`,
and their canonical full-run reproducibility digest is
`186b7745c079f85a5af7a551fcf597c3ac3b1ef18b4898d9754da9d1a379c2e9`.

No checkpoint was eligible. The best public frontier point was update 11 at
16/40 wins, mean team return `-7.878245`, mean core health `390.05`, and mean
team idle `0.14656396`. The frozen server-expert baseline is 36/40 wins with
mean team return `-1.641725`. Updates 12 through 32 produced no more than zero
dev wins even though the training schedule continued to win on its repeated
roots. The exact replicas therefore establish a public generalization failure,
not nondeterminism, incomplete execution, or an infrastructure failure.

The compact immutable result is
`configs/evaluation/m9-ippo-v1-replica-result.json`, SHA-256
`7ea61a5bc3a624408e869d400e10bf8859356bbd1d9ca440e8d9b45eb6bf2cb3`.
No confirmation or held-out namespace was allocated or accessed. M8
held-out-v7 remains sealed.

## Decision

1. Reject `m9-ippo-v1`. It is immutable and must not be rerun, retuned, or
   retroactively assigned an eligible checkpoint.
2. Record construction as failed with no selected checkpoint. Raw serializer
   integrity and canonical full-run identity both reproduce exactly.
3. Do not perform the paired candidate/baseline promotion comparison or direct
   selected-checkpoint lineage check: both require an eligible selected
   checkpoint that does not exist.
4. Do not start MAPPO. ADR-0008 and ADR-0070 require a qualifying public IPPO
   result first.
5. Treat the observed train/dev divergence as evidence for a separately named,
   prospectively governed IPPO successor. Any successor must freeze its exact
   changed mechanism, recipe, budget, RNG streams, evidence namespaces, and
   continuation bar before collecting new trajectories or changing model
   weights.
6. The successor may use only public evidence until it passes its own
   construction and comparison gates. M8 held-out-v7 remains M8-only and
   unavailable.

## Alternatives

- Selecting update 11 despite the 16/40 result is rejected because it violates
  the frozen 30-win construction threshold.
- Extending the episode budget or lowering the gate in place is rejected
  because both decisions would be informed by the observed v1 frontier.
- Starting MAPPO after a reproducible IPPO failure is rejected because
  reproducibility alone does not satisfy ADR-0008's performance prerequisite.
- Opening confirmation or held-out evidence to diagnose construction is
  rejected because public train/dev evidence is sufficient and no such M9
  namespace has been authorized.

## Consequences

- M9.1 remains in progress and MAPPO remains blocked.
- The v1 infrastructure, exact-commit gate, atomic all-seat boundary, recurrent
  state isolation, reward audit, manifest lineage, and deterministic CPU
  execution remain accepted reusable machinery.
- The next work is public-only successor synthesis and prospective precommit,
  not another v1 run.
