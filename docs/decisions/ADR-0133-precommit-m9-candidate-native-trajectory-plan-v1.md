# ADR-0133: Precommit M9 candidate-native trajectory plan v1

**Status:** Accepted

## Context

ADR-0132 accepts a prospectively frozen trajectory-supervision signal: on 19
planner-win/student-loss public roots, the independent planner and rejected
update-64 student differ on a median `0.5982906` of fixed-grid three-seat
task-family occupancy and have median normalized compressed sequence distance
`0.6428571`. Pointwise imitation, hard-example pressure, contiguous BPTT,
maximal label freshness, and online planner correction have already failed.

The owner explicitly authorized a new plan and its execution. The narrow
supported change is to make macro task-family intent an explicit learned
coordinate while preserving candidate-native action authority.

## Decision

Freeze `m9-candidate-native-trajectory-plan-v1` before implementation or
training. It initializes every inherited parameter and Adam moment from the
exact rejected on-policy-relabel update-64 checkpoint. It adds one four-slot,
16-family plan head over the existing 200-value actor context:

`Linear(200,64) -> Tanh -> Linear(64,4*16)`.

The final plan-head weight and bias are all zero, so initialization preserves
every source action logit exactly. Slot-zero family logits add a fixed `1.0`
bias to ordinary candidate logits through the existing candidate task-family
one-hot slice `[13:29]`. CONTINUE and WAIT special logits receive no plan
bias.

Collection remains deterministic student control on the exact existing 2,048
unique public roots. Planner v11 labels the same pre-action student states.
Every eligible label receives a four-family program: its current planner
recommended family followed by the next three distinct eligible planner
families for that same episode and seat. Missing future slots repeat the final
available family. CONTINUE uses the accepted student active family before the
boundary, or WAIT when none exists. Programs never cross an episode, seat,
authoritative recurrent reset, or terminal boundary.

Training retains non-overlapping 16-boundary per-seat recurrent windows,
stored detached window-start hidden state, eight epochs per 64-root update,
and deterministic window shuffling. The exact loss is mean teacher-action NLL
from the plan-biased action logits plus `0.25` times mean four-slot
task-family cross-entropy, both over eligible supervised transitions.

The source Adam state is restored exactly for inherited parameters. One new
parameter group is appended in module parameter order for the plan head, with
the same `0.0001` learning rate and `1e-8` epsilon and initially empty moments.
No other optimizer value or RNG stream changes.

The candidate continues for 32 updates, lineage 65 through 96, with the same
32-by-64 public schedule, dev evaluation after every update, 30/40
construction floor, exclusive idle threshold `0.25`, ranking, and conditional
Replica B rule.

Configuration/public-protocol SHA-256 values are
`ae0d29aa7fd8882e51582df111e5f27830382228c992765c6def7d6998b7f95f`
/
`1812f19c8c64cc980399def88d9dec43e0cda0cb589b5a4bcae1afd88f68962b`.

## Constraints

- Only the plan head, slot-zero family bias, and fixed four-slot plan loss are
  new. Planner, candidates, features, masks, roots, recurrent width, inherited
  weights, inherited Adam state, base NLL, schedule, budget, dev gate, and
  replica rule remain frozen.
- No plan-slot, horizon, bias-scale, loss-coefficient, learning-rate, or
  initialization sweep is authorized.
- The rejected source is initialization only; it remains unselected,
  unrepaired, and unpromotable.
- Replica A may start only after exact source/logit/optimizer inheritance,
  program-boundary, gradient, checkpoint, deterministic replica, live-reset,
  and complete exact-current-commit gates pass.
- Replica B is prohibited unless Replica A reaches both construction and idle
  gates.
- No reward, critic loss, PPO, MAPPO, target identifiers, confirmation,
  held-out, learned human-session, or other restricted data is authorized.
  M8 held-out-v7 remains sealed.

## Consequences

Implementation may add one trajectory-plan model/collector/optimizer,
candidate-specific checkpoint/manifest path, preflight, commands, tests, and
public result. No implementation, candidate state, optimizer update, or
restricted access preceded this precommit.
