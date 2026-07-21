# ADR-0028: V17 doubled capped idle slope

**Status:** Accepted

## Context

V16 reproduced exactly and reduced reusable dev-v1 mean team idle from V15's
0.21873675 to 0.10050130 while retaining 9/10 construction wins. It eliminated
non-forced abandonment and beat matched greedy on idle, but permanent-greedy
idle remained 0.05618951 lower and recovery was uncertain.

The V16 reusable traces rule out another WAIT intervention: all 14 WAIT actions
were forced, and the learned model selected a candidate at every one of its 375
unforced decisions. The remaining idle is therefore downstream of task choice,
not a discretionary WAIT logit. V16's explicit cap now permits stronger local
pressure without increasing the full-horizon maximum or changing early-loss
ordering.

## Decision

1. V17 keeps V16's corrected runtime, train/dev roots, architecture, optimizer,
   RNG seeds, 64-root/32-cycle schedule, checkpoint-selection rule, and reward
   components fixed.
2. Change only `idle_agent_tick_cost` from `0.001` to `0.002`. Keep the explicit
   `idle_agent_tick_cap` at `5.0`, so the full-horizon idle maximum and
   early-loss ordering remain unchanged.
3. The exact-config busywork adversary requires a safety companion: 600 ticks
   of full-team idle now cost `3.6`, above V16's combined `3.0` duplicate and
   abandonment caps. Raise only `duplicate_work_cap` from `1.0` to `2.0`, making
   that pathological busywork cost `4.0`. V16 observed two duplicate incidents
   per reusable episode (`0.1` cost), so the higher cap does not alter the
   measured ordinary regime.
4. This is one bounded successor, not a coefficient sweep. It tests whether the
   V16 task-selection signal can close the remaining permanent-idle gap while
   retaining at least 9/10 construction wins.
5. The exact V17 config must pass every reward adversary and the full Python
   suite before training. Two pinned 2,048-episode replicas must reproduce
   checkpoint, frontier, model state, replay, and full-run digest exactly.
6. Reusable dev-v1 must pass its construction gate and both permanent/matched
   scorecards. V17 stops before confirmation if any reusable gate fails.
7. Retire V16's unopened dev-v12. Freeze dev-v13 now at globally disjoint roots
   `131001..131160` for one exclusive confirmation only after every reusable
   gate passes. Held-out-v4 remains sealed.

## Consequences

- Reward schema and inference behavior do not change; older configs and
  checkpoints remain exact.
- The experiment increases the gradient against task choices that leave team
  agents idle and preserves the audited idle-versus-busywork ordering without
  adding another WAIT bias or reopening the closed teacher coefficient line.
- V17 may lose construction capacity or remain above permanent-greedy idle. In
  either case dev-v13 remains unopened and the intervention is rejected.

Pretraining validation passed all 39 exact-config reward adversaries and the
full 135-test Python suite. Config SHA-256 is `71ffd120617ac860...`; the hashed
adversary report is `f716fc529c8aae8c...`.

## Outcome

Two pinned replicas reproduced exactly and selected update 17 at 9/10
construction wins with mean idle 0.08594077. Reusable dev-v1 improved matched
idle by 0.14385630 and retained zero non-forced abandonment, but
permanent-greedy idle remained 0.04162898 worse (95% CI
+0.01733907..+0.06734018). Permanent announcements and both recovery
comparisons were uncertain. V17 is rejected before dev-v13; held-out-v4 remains
sealed.
