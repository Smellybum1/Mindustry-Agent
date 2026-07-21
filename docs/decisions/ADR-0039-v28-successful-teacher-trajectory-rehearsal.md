# ADR-0039: V28 successful teacher-trajectory rehearsal

**Status:** Accepted

## Context

V27 successfully transferred its governed teacher corpus before PPO: update 1
had a mean selected-minus-teacher logit gap of only `0.02482445` on disagreement
boundaries. The prior did not persist. By best-ranked update 20, disagreements
rose to 134/401 with mean gap `2.24436055`, worse than V24's 73/427 and
`1.49301094`. Both candidates remained 8/10; V27 changed one loss from seed 2005
to 2009 without clearing seed 2004.

This reusable dev-v1 evidence identifies forgetting during ordinary PPO, not a
failure to learn the initial successful sequences. More initial warmup epochs
would strengthen only the state that PPO already erased. Another online teacher
coefficient is forbidden by ADR-0037's closed line.

## Decision

1. V28 retrains from scratch as the exact V27 construction plus deterministic
   rehearsal of the same success-only teacher corpus after every PPO update.
2. Each update order is `PPO -> one rehearsal CE epoch -> checkpoint -> dev`.
   With the observed 121-transition corpus and minibatch size 128, this is one
   separately shuffled rehearsal batch per update. Rehearsal minibatch seed is
   `8607`; it does not consume warmup, action-sampling, or PPO-minibatch RNGs.
3. The same Adam instance is authoritative across warmup, PPO, and rehearsal.
   An atomic report records the exact warmup-report hash, compact corpus, every
   rehearsal loss/sample count, and post-rehearsal model digest even if the
   construction gate later fails.
4. Candidate ID, quality label, confirmation path, rehearsal epoch count, and
   rehearsal seed are the only differences from V27. Runtime, reward, train and
   reusable-dev roots, model, warmup, PPO budget, ordinary RNGs, online teacher
   coefficient `0.05`, checkpoint selection, and inference stay exact.
5. Replica B starts only if replica A reaches at least 9/10 reusable construction
   wins with mean idle below 0.25. Passing replicas must reproduce warmup and
   rehearsal evidence, checkpoint, complete frontier, model state, replay,
   full-run digest, and direct lineage.
6. Reusable preflight still requires both permanent-greedy and matched-greedy
   scorecards before any one-way confirmation. Retire V27's unopened dev-v23;
   freeze dev-v24 at globally disjoint roots `241001..241160`. It remains
   unopened until every reusable gate passes. Held-out-v4 stays sealed.
7. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate gate, smoke, and determinism
   including negative replay pass from a committed packet.

## Alternatives

- More initial warmup epochs were rejected because V27 learned the initial
  teacher margin and subsequently forgot it.
- Another online teacher coefficient was rejected because ADR-0037 closed that
  line after V26 regressed.
- Adding new teacher roots, reward terms, model capacity, or PPO episodes was
  rejected because the first test should isolate persistence of the exact V27
  corpus.
- Opening dev-v23 was rejected because V27 failed before confirmation.

## Consequences

- V28 adds 32 bounded CE optimizer steps but no environment episodes beyond
  V27's 64 warmup plus 2,048 PPO episodes.
- Reward, evaluation action selection, externally stepped timing, simulation-
  thread ownership, communication authority, masks, lifecycle, and engine pins
  remain unchanged.
- Construction failure retires dev-v24 unopened. Construction success still
  authorizes only exact reproduction and reusable preflight, never direct
  confirmation or held-out access.

No V28 model work began before this precommit. The generic rehearsal capability
was validated separately with a one-update probe; that probe is not candidate
or promotion evidence.

Pretraining validation passes all 44 exact-config reward adversaries, the full
153-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`ef58055e7da5566db94f72cd95fcc519f1f3b61beae5b88ffaafec18d3a33bee`;
adversary report SHA-256 is
`2d672a7f0e816a4163f887aa4f19a946985bcb9ec8fe34c79f3849ac1a26fe8a`.

## Outcome

Replica A completed all 64 warmup episodes, 2,048 PPO episodes, and 32
rehearsal-bearing updates, then failed the frozen construction gate. The
rehearsal corpus remained five episodes/121 transitions. Mean rehearsal CE fell
from `1.39527905` on update 1 to `1.31666994` on update 32; the complete atomic
report hashes to
`2bd187fea8635206865e12a37104420c6c79489a2428515dea42d797b53aba33`.

No checkpoint reached 9/10. Ten updates reached 8/10; the best-ranked row is
update 27 with mean return `1.11366`, mean core health `516.4`, and mean idle
`0.07046312`. Its reusable teacher disagreement remains 134/401, while mean
disagreement margin improves from V27's `2.24436055` to `1.81065121`; losses
remain seeds 2004 and 2009. The complete frontier hashes to
`ba963bea1d0d303b3e11304e8bb1a0ae3d476465f787bc1fea92647dc67f8972`.
Replica B did not start, dev-v24 remained unopened, and held-out-v4 remained
sealed. V28 is rejected before reusable preflight.
