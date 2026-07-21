# ADR-0027: V16 high-slope capped idle pressure

**Status:** Accepted

## Context

V15 reproduced exactly and improved non-forced abandonment, but its selected
checkpoint remained idle for 0.21873675 of team agent-ticks and failed the
permanent-greedy idle scorecard. The best 10/10 point in its reusable dev-v1
frontier was still 0.16449283 idle versus the permanent comparator near 0.044,
so changing checkpoint ranking alone cannot satisfy the quality contract.

Increasing V14's idle coefficient from `0.0001` to V15's `0.0003` also raised
the full-horizon maximum from 2.7 to 8.1. Further increasing that coefficient
without separating its cap would eventually make full-horizon idle survival
less costly than early loss. The reward accumulator currently couples slope
and maximum by deriving the cap from coefficient times the scenario horizon.

## Decision

1. Reward v2 accepts an optional non-negative `idle_agent_tick_cap`. Omitting
   it preserves the exact V12-V15 derived-cap behavior. A negative cost or cap
   fails the run.
2. V16 keeps V15's corrected runtime, train/dev roots, architecture, optimizer,
   RNG seeds, all other reward coefficients/caps, 64-root/32-cycle schedule,
   and checkpoint-selection rule fixed.
3. V16 sets idle cost to `0.001` per idle agent tick and explicitly caps the
   component at `5.0`. This strongly separates the measured candidate and
   permanent-greedy idle regimes while leaving full-horizon idle survival worse
   than early loss. Non-forced abandonment remains `0.25`, capped at `2.0`.
4. Exact-config adversaries must prove the idle cap, post-cap zero charge,
   chunk invariance, early-loss ordering, busywork ordering, counter rollback,
   and all existing reward properties before training.
5. Two pinned 2,048-episode runs must reproduce checkpoint, frontier, model
   state, replay, and full-run digest exactly. Reusable dev-v1 must then pass
   its win/idle construction gate and both permanent/matched scorecards.
6. Retire V15's unopened dev-v11. Freeze dev-v12 now at globally disjoint roots
   `121001..121160` for one exclusive confirmation only after every reusable
   gate passes. Held-out-v4 remains sealed.

## Consequences

- V12-V15 reward behavior and checkpoint compatibility remain unchanged when
  the new cap field is absent.
- V16 increases the local gradient against long WAIT spans without allowing
  the maximum idle cost to invert the early-loss adversary.
- V16 stops before dev-v12 if construction, reproduction, or either reusable
  scorecard fails. Only an eligible dev-v12 result may authorize held-out-v4.

## Outcome

Two pinned 2,048-episode replicas reproduced exactly and selected update 23 at
9/10 construction wins with mean idle 0.10050130. The direct checkpoint lineage
also reproduced. Reusable dev-v1 measured zero non-forced abandonment and a
0.12929577 idle improvement against matched greedy, but permanent-greedy idle
remained 0.05618951 worse (95% CI +0.03029619..+0.08042806). Recovery was
uncertain against both governed scorecards. V16 is therefore rejected before
dev-v12; held-out-v4 remains sealed.
