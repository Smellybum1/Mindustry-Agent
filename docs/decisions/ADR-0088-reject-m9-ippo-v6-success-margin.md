# ADR-0088: Reject M9 IPPO v6 successful-action margin alignment

**Status:** Accepted

## Context

ADR-0087 froze one direct response to v5's retained stochastic success without
deterministic consolidation: inherit v4 and add a coefficient `0.02`, target
`0.1` strongest-other legal-action hinge over actor-valid transitions from
current-update winning episodes. Implementation commit
`05e6b487727cbefae8f104838dd2a428ee9511c4` passed deterministic twin optimizer
evidence. Exact-current-commit pretraining authority at
`f805e52842b1cd2d8abfc8475a479d0592f654d5` passed all 443 Python tests, pinned
Java checks, focused M9 checks, smoke, determinism, and golden replay without
confirmation or held-out access.

Replica A completed all 2,048 unique-root episodes and 32 updates. The margin
filter was active: 600 winning episodes contributed 30,412 actor-valid
transitions across 6,166 active minibatches. Deterministic public-dev behavior
improved late but never approached construction: update 29 peaked at 2/40 wins
with idle `0.1878284790404538`, update 31 retained 1/40, and update 32 finished
at 0/40 with idle `0.16793466436116314`. No checkpoint met the unchanged 30/40
and idle `<0.25` bar. V6 also remained far below v4's 18/40 update-31 frontier,
so direct all-winning-transition margin alignment did not preserve the
strongest public result it inherited.

The compact result is
`configs/evaluation/m9-ippo-v6-success-margin-result.json`, SHA-256
`37f3ecd470f7580a00b5af557cbb497e5d1069bdb5c25bdd6b747c37871ba33a`.
The authoritative run manifest SHA-256 is
`d6ecb9f820ec975f9313ce31ca4796895129a9136c231662a81855baad79e90c`;
its canonical full-run reproducibility digest is
`bc74e4b2f88a0e6f4823493b8ce96f5d131b5f7363697c4334fd01ffe911fdfa`.

## Decision

1. Reject `m9-ippo-v6-success-margin`. It does not satisfy M9.1 construction.
2. Replica B is prohibited because Replica A did not pass construction. V6
   checkpoints cannot be selected, promoted, retuned, resumed, or used for a
   direct v6 success claim.
3. Preserve the full Replica A manifest, checkpoints, logs, and compact result
   as public development evidence.
4. Treat v5 and v6 together as evidence against uniformly reinforcing every
   actor-valid transition from a winning stochastic episode. A terminal win
   does not establish that every sampled action in that trajectory is a
   desirable deterministic label.
5. Do not authorize another coefficient, target-margin, entropy, or
   success-filter retune from this result. Before any v7 model or trajectory,
   complete a public-only design synthesis across v1--v6 and prospectively
   freeze one mechanism that changes the source of action supervision rather
   than another scalar on the rejected self-imitation family.
6. M8 held-out-v7 remains sealed. No M9 confirmation or held-out namespace is
   authorized.

## Alternatives

- Running Replica B is rejected because ADR-0087 makes construction-passing
  Replica A a hard prerequisite.
- Selecting update 29 is rejected because 2/40 wins is far below the frozen
  30/40 construction floor.
- Increasing the hinge coefficient or reducing its target is rejected as
  post-result retuning without evidence that the terminal-win transition
  labels are causally sound.
- Combining v5 NLL and v6 margin is rejected because both act on the same
  noisy all-winning-transition labels and would confound two failed
  mechanisms.
- Reopening v4 update 31 is rejected because ADR-0080 already rejected v4 and
  no rejected checkpoint may be promoted.

## Consequences

- M9.1 remains open and MAPPO remains unauthorized.
- V6 is a completed negative construction result, not a runtime failure.
- The next authorized work is design synthesis and a separate prospective
  precommit; no v7 training is authorized by this ADR.
