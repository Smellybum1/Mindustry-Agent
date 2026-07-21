# ADR-0040: V29 diverse successful teacher corpus

**Status:** Accepted

## Context

V28's distributed rehearsal reduced the best reusable disagreement margin from
`2.24436055` to `1.81065121`, but left the exact 134/401 disagreements and losses
on seeds 2004/2009 unchanged. Its corpus contains only five winning train-v2
episodes and 121 unique transitions. Increasing rehearsal strength would repeat
the same labels that already reduced margin without changing an action.

The next isolated lever is state/trajectory coverage. A larger, precommitted
train-only root set can yield more varied complete successful teacher sequences
without changing PPO roots, budget, reward, model, or evaluation. Its membership
must be frozen before any teacher outcome is observed so success filtering cannot
select favorable roots retrospectively.

## Decision

1. Freeze `bootstrap-defense-v1-teacher-train-v1` at 256 globally disjoint roots
   `291001..291256`, split `train`, before collecting any outcomes. It is used
   only for teacher-controlled warmup/rehearsal and never for PPO, dev,
   confirmation, or final evaluation.
2. V29 is the exact V28 construction except `teacher_warmup_seed_set` names that
   new artifact. One shuffled teacher cycle, success-only filtering, eight
   initial CE epochs, and one rehearsal epoch after each PPO update stay exact.
3. PPO still uses the original 64 train-v2 roots for 32 cycles, 2,048 episodes,
   and 32 updates. Runtime, reward, model, optimizer values, all RNG values,
   online teacher coefficient `0.05`, checkpoint selection, and inference stay
   exact. Candidate ID, quality label, and confirmation path are governance
   metadata.
4. The warmup report and manifest must bind the auxiliary set identity, all 256
   roots, shuffled schedule, complete episode outcomes, eligible successful
   corpus, pre/post model digests, and rehearsal evidence.
5. Replica B starts only if replica A reaches at least 9/10 reusable construction
   wins with mean idle below 0.25. Passing replicas must reproduce warmup and
   rehearsal evidence, checkpoint, complete frontier, model state, replay,
   full-run digest, and direct lineage.
6. Reusable preflight still requires both permanent-greedy and matched-greedy
   scorecards before any one-way confirmation. Retire V28's unopened dev-v24;
   freeze dev-v25 at globally disjoint roots `251001..251160`. It remains
   unopened until every reusable gate passes. Held-out-v4 stays sealed.
7. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate gate, smoke, and determinism
   including negative replay pass from a committed packet.

## Alternatives

- More rehearsal epochs were rejected because V28 moved margins but not actions
  on the fixed corpus.
- Selecting only roots known to win was rejected as outcome-driven train-set
  curation; all 256 roots are frozen before collection and every outcome is
  archived.
- Changing PPO roots/budget, reward, model capacity, or online teacher strength
  was rejected because it would confound the corpus-diversity test.
- Opening dev-v24 was rejected because V28 failed before confirmation.

## Consequences

- V29 adds 256 teacher-controlled environment episodes in place of V28's 64,
  but retains exactly 2,048 PPO episodes and 32 checkpoints.
- The number of successful teacher episodes and eligible transitions is unknown
  at precommit time and becomes governed construction evidence, not a tuning
  input.
- Reward, evaluation action selection, externally stepped timing, simulation-
  thread ownership, communication authority, masks, lifecycle, and engine pins
  remain unchanged.
- Construction failure retires dev-v25 unopened. Construction success still
  authorizes only exact reproduction and reusable preflight, never direct
  confirmation or held-out access.

No V29 teacher outcomes or model work were observed before this precommit.

Pretraining validation passes all 44 exact-config reward adversaries, the full
154-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`a40a8772ef5392fb20d1184c6f543b53efc431368fa5e7acd352bce5034bcd95`;
adversary report SHA-256 is
`cac12af7f0861deabb92733cd30c4451f9b58e5152d25c41193df0afe3ccd015`.

## Outcome

Replica A completed all 256 teacher episodes, 2,048 PPO episodes, and 32
rehearsal-bearing updates, then failed the frozen construction gate. The
precommitted teacher set yielded 37 wins and 860 eligible transitions. Eight
warmup epochs presented 6,880 samples at mean cross-entropy `1.38471070` and
changed model state
`dbae4c605e52b962... -> 90d6b964b2d85666...`. The complete warmup report
hashes to
`582f362322e4aa43916f0e80c65bcfec3fe1e33e713e2bf590f02ad7e96fe736`.

Rehearsal mean cross-entropy fell from `1.32362124` on update 1 to
`0.46930411` on update 32. The complete 32-update report hashes to
`b5c089bf4d85acd238f8c8cc3d0ed1b42e7916e877dbd3b8eb4b8c5391e0efcc`.
No checkpoint exceeded 4/10 wins. The best-ranked row is update 5 with mean
return `-10.68702`, mean core health `182.6`, and mean idle `0.21429663`.
The complete frontier hashes to
`26c6270efca0c85210fb4c4fb9486ecd6cfe9e4fc7fe71618c33bb811bb31c1a`.
Replica B did not start, dev-v25 remained unopened, and held-out-v4 remained
sealed. V29 is rejected before reusable preflight.
