# ADR-0026: V15 stronger idle and abandonment pressure

**Status:** Accepted

## Context

V14 reproduced exactly, won 10/10 reusable dev-v1 episodes, and reduced mean
idle to 0.15861366, but the corrected dual preflight rejected it before dev-v10.
Permanent-greedy idle and non-forced abandonment were definitively worse.

Reusable dev-v1 traces show the remaining mechanism. Only 59 learned `WAIT`
decisions consume 34,993 of 81,000 total episode ticks. The selected update 32
is already the lowest-idle 10/10 point in V14's reproducible frontier, so a
selection-rule change cannot remove the gap. Thirty-six learned-seat
resource-short replans also remain. V14's idle coefficient charges only
`0.0001` per idle agent tick and its team abandonment coefficient charges
`0.1` per non-forced event.

## Decision

1. V15 keeps V14's corrected runtime, train/dev roots, architecture, optimizer,
   RNG seeds, reward components, caps, 64-root/32-cycle schedule, and
   quality-gated checkpoint selection exactly fixed.
2. Change only two reward-v2 coefficients: idle agent ticks from `0.0001` to
   `0.0003`, and non-forced team abandonment from `0.1` to `0.25`. The idle
   maximum becomes `8.1`, keeping full-horizon idle survival worse than early
   loss under the existing adversary. Abandonment retains its `2.0` cap.
3. The reward adversary runner must load and hash the exact V15 config. All
   adversaries, including early loss, chunk invariance, idle busywork, counter
   rollback, caps, and forced-abandon exclusions, must pass before training.
4. Two pinned 2,048-episode runs must reproduce the selected checkpoint,
   frontier, model state, replay, and full-run digest exactly.
5. Reusable dev-v1 must reach at least 9/10 wins, mean idle below 0.25, and pass
   both permanent and matched greedy scorecards before confirmation.
6. Retire V14's unopened dev-v10 without evaluating it. Freeze dev-v11 now at
   globally disjoint roots `111001..111160` for V15's one exclusive
   scorecard-v2 confirmation. Held-out-v4 remains sealed.

## Consequences

- The intervention directly prices the two measured failures without changing
  observations, action masks, communication authority, engine pins, or
  deterministic stepping.
- Stronger negative shaping can favor inactivity or early termination; the
  exact-config adversaries are a mandatory construction gate, not optional
  evidence.
- V15 stops before dev-v11 if reproduction, win/idle, or either reusable
  scorecard fails. Only an eligible dev-v11 result may authorize held-out-v4.
