# ADR-0023: V13 quality-gated checkpoint selection

**Status:** Accepted

## Context

V12 reproduced exactly and its selected update 28 won 10/10 dev-v1 episodes,
but mean idle was 0.26628148, above ADR-0022's exclusive `<0.25` continuation
bar. The existing selector ranks checkpoints by wins, return, core health, and
earlier update; it does not apply the continuation gate during selection.
Permitted dev-v1 frontier analysis showed that reproducible update 24 won
10/10 with mean idle 0.24980951. Retroactively relabeling that artifact as V12
would change its selection rule after the result, so V12 remains rejected.

## Decision

1. V13 reruns V12's exact train/dev roots, reward v2, optimizer, architecture,
   seeds, and 64-root/32-cycle schedule. The only change is the checkpoint
   selection contract.
2. Every dev checkpoint summary records mean idle fraction. A checkpoint is
   eligible only with at least 9/10 wins and mean idle strictly below 0.25.
   With no eligible checkpoint, construction fails instead of silently falling
   back to the old ranking.
3. Eligible checkpoints are ranked by wins, mean return, mean core health, and
   earlier update, in that order. The rule is fixed before V13 implementation
   or training and is recorded in the immutable training config and manifest.
4. Two pinned 2,048-episode runs must reproduce the selected checkpoint,
   checkpoint frontier, replay, and full-run digest exactly.
5. Dev-v8 remains reserved to rejected V12 and is retired unopened. Freeze
   dev-v9 now with 160 disjoint roots `91001..91160` for V13's one exclusive
   ADR-0019 dual-scorecard confirmation.
6. V13 names held-out-v4. Only complete dev-v9 eligibility may authorize the
   still-sealed final set.

## Consequences

- Dev-v1 remains the reusable checkpoint-selection split it was designed to
  be; no confirmation or held-out outcome influenced this rule.
- The intervention changes selection, not model updates, reward, inference,
  features, masks, lifecycle, engine state, or communication authority.
- V13 may still fail to reproduce, find an eligible checkpoint, or pass the
  permanent/matched dual scorecards. Any such failure stops before held-out-v4.
