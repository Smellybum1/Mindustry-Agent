# ADR-0041: V30 budgeted diverse successful teacher corpus

**Status:** Accepted

## Context

V29 expanded the successful teacher corpus from V28's five episodes/121
transitions to 37 episodes/860 transitions. Keeping the epoch counts fixed also
expanded the imitation budget: warmup grew from 968 to 6,880 presentations and
from 8 to 56 optimizer batches, while each rehearsal update grew from 121 to
860 presentations and from 1 to 7 batches. Rehearsal CE fell from `1.32362124`
to `0.46930411`, but the best construction result collapsed from V28's 8/10 to
V29's 4/10.

V29 therefore confounded corpus diversity with approximately seven times more
CE optimization. The complete frozen corpus is useful train evidence, but its
failed strength must not be repeated. A presentation cap can isolate diversity
while restoring the last non-collapsed update count.

## Decision

1. V30 is the exact V29 construction except each warmup epoch and each
   rehearsal epoch consumes at most 121 transitions. The cap equals V28's
   complete successful corpus size, yielding exactly 968 warmup presentations
   and 121 presentations after each PPO update when V29's 860-transition corpus
   is reproduced.
2. Sampling uses the existing separately seeded `torch.randperm` generators.
   Each epoch samples without replacement from all eligible transitions; no
   fixed favorable subset or outcome-driven selection is permitted. The exact
   transition indices, per-call unique coverage, and schedule SHA-256 join the
   warmup/rehearsal reports and full-run reproducibility evidence.
3. All 37 V29 winning episodes remain eligible. The auxiliary teacher roots,
   success-only filter, eight warmup epochs, one rehearsal epoch per PPO update,
   online teacher coefficient `0.05`, PPO roots/budget, reward, runtime, model,
   optimizer values, all RNG seeds, checkpoint selection, and inference stay
   exact. Candidate ID, quality label, caps, and confirmation path are the only
   config differences.
4. Absent caps preserve the historical full-corpus update and report schema.
   Invalid non-positive caps fail before environment work begins.
5. Replica B starts only if replica A reaches at least 9/10 reusable
   construction wins with mean idle below 0.25. Passing replicas must reproduce
   corpus outcomes, sample schedules, checkpoint/frontier/model/replay/full-run
   evidence, and direct lineage exactly.
6. Retire V29's unopened dev-v25. Freeze dev-v26 at globally disjoint roots
   `261001..261160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays
   sealed.
7. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate gate, smoke, and determinism
   including negative replay pass from a committed packet.

## Alternatives

- Reusing all 860 labels per epoch was rejected by V29's 4/10 construction.
- Returning to the five-episode corpus was rejected because V27/V28 already
  showed that repeated optimization over those 121 labels did not flip the
  reusable teacher disagreements.
- Freezing one 121-transition subset was rejected because it would discard the
  diversity being tested. Deterministic reshuffling lets the same update budget
  rotate through the larger corpus.
- Changing CE coefficient, PPO roots/budget, reward, model capacity, or runtime
  was rejected because it would confound presentation-budget isolation.

## Consequences

- V30 retains the 256 teacher-control episodes needed to reconstruct the frozen
  successful corpus, but restores V28's CE optimizer-step count.
- The realized cross-update coverage is unknown until replica A and is governed
  construction evidence, not a tuning input.
- Reward, externally stepped timing, simulation-thread ownership, structured
  communication authority, action masks, lifecycle, evaluation behavior, and
  engine pins remain unchanged.
- Construction failure retires dev-v26 unopened. Construction success still
  authorizes only exact reproduction and reusable preflight.

No V30 teacher collection or model work occurred before this precommit.

Pretraining validation passes all 44 exact-config reward adversaries, the full
155-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`c57556695157dcd4b405ea7a69a527ee6f3c304a67cd042599e9ebf84571473d`;
adversary report SHA-256 is
`a3bcf116478e1be0948c8653deccba749bd5f97b84b058093275eb22c5298677`.
