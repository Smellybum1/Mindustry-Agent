# ADR-0025: V14 corrected-abandon-boundary retraining

**Status:** Accepted

## Context

V13 is permanently rejected after its one-way dev-v9 confirmation. Reusable
dev-v1 traces subsequently exposed an environment scheduling defect: a
successful policy `ABANDON` changed the coordination revision after the server
had sampled its step baseline, so stop-on-event waited for an unrelated future
event. Thirty V13 abandon decisions consumed 23,371 engine ticks.

The corrected server samples the revision before applying actions, marks a
successful abandonment as `task_terminal`, and returns after one fixed engine
tick. Replaying the rejected V13 checkpoint on reusable dev-v1 under that
contract remains 10/10 wins and improves mean team idle from 0.24980951 to
0.20217810. It also exposes 105 immediate non-forced resource replans, so the
dual scorecard correctly remains ineligible. The already-trained checkpoint
cannot learn from the corrected transition/reward sequence.

## Decision

1. V14 retrains from scratch under the corrected abandonment-boundary runtime.
   Its train/dev roots, reward v2, optimizer, architecture, RNG seeds,
   64-root/32-cycle schedule, and quality-gated checkpoint selection are
   otherwise exactly V13's.
2. The immutable V14 config records candidate version `v14` and runtime
   contract `successful_abandon_task_terminal_one_tick_v1`. Training manifests
   must record the repository commit and the exact config hash.
3. Two pinned 2,048-episode runs must reproduce the selected checkpoint,
   checkpoint frontier, replay, model state, and full-run digest exactly.
4. The reusable dev-v1 construction gate remains at least 9/10 wins and mean
   idle strictly below 0.25. The corrected ADR-0019 preflight must then pass
   paired scorecard non-regression against both permanent and matched greedy;
   otherwise V14 stops without confirmation.
5. Freeze dev-v10 now with 160 globally disjoint roots `101001..101160` for
   V14's one exclusive scorecard-v2 confirmation. Its individual outcomes may
   not influence future design. V13's consumed dev-v9 is never rerun.
6. V14 continues to name held-out-v4. Only a complete eligible dev-v10 result
   may authorize the still-sealed final set.

## Consequences

- The intervention corrects environment transition timing and retrains; it
  does not change features, masks, reward coefficients, model architecture,
  communication authority, engine pins, or fixed-step ownership.
- Rapid resource-short churn is now visible to reward v2 instead of being
  hidden behind long unrelated transitions.
- V14 may fail to reproduce, find an eligible checkpoint, pass reusable
  dev-v1, or pass the dual scorecards. Any failure stops before dev-v10 or
  held-out-v4 as applicable.
