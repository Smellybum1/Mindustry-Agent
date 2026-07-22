# Candidate expressiveness gaps

This began as the M7.3 audit of what the public task-candidate seam could and
could not express when it replaced the frozen `ExpertEpisode` macro. M7.4 now
records which rigidity gaps were closed before scenario variation and learning.

## Starting failure

The unmodified M5 catalog plus `GreedyUtilityPolicy` lost seed `12345` at tick
3780 with a destroyed core, two turrets, 89 selections, and 118 rejected task
actions. It exposed only the reference line/schematic, one-shot harvest and
supply work, repair, defense, and wait. The winning M6 macro's core
fortification, post-wave expansions, deeper ammo reserve, recurring work, and
resource recovery were not selectable through `SELECT_CANDIDATE_TASK`.

## Gaps closed in M7.3

1. **No fortification or expansion candidates.** `ExpertCoordinationPlan` now
   owns scenario-derived opening and per-wave schematics. `EngineCandidates`
   exposes the next physically eligible schematic through the normal bounded
   catalog, and `CoordinationAdapter` executes and reserves its real footprint.
2. **One-shot task IDs prevented retry and recurrence.** Harvest, line,
   schematic, supply, and repair work now receives deterministic boundary/wave
   identity. The adapter suppresses concurrent semantic duplicates while a
   task is active, but a terminally abandoned task can be regenerated and
   selected again. Physical schematic completion, rather than an old board ID,
   gates the next planned schematic.
3. **Blocked work only retried.** The pure greedy policy converts
   `BLOCKED(RESOURCES_SHORT|CORE_SHORT)` into structured
   `ABANDON(resources_short_replan)`, then regenerates and reselects candidates.
   `resource_replans` makes that recovery observable. The legal 18-wall
   pre-spend variant wins seed `12345` at tick 8100 with 209 core health and
   seven explicit resource replans.
4. **The ammo objective was too shallow for survival.** The scenario objective
   remains the minimum validity threshold, while the expert catalog targets a
   30-ammo reserve (15 copper) per turret, matching the shared demo expert's
   supply quantity.
5. **The defense plan was below the catalog policy's execution margin.** The
   shared data-driven opening fortification adds four supporting Duos behind
   the reference pair. Two two-Duo expansions remain wave-gated. This same plan
   feeds the fixed-step catalog and real-time shared driver; it is not a Python
   coordinate macro.
6. **Defense identity serialized all agents.** DEFEND IDs include wave and
   agent identity and remain non-exclusive, so multiple seats can legally hold
   the lane. The adapter completes those assignments when a seen wave actually
   clears rather than only when a duration expires.
7. **Planned-schematic utility used the reference schematic's completion and
   the agent's current location.** Planned work now has its own urgency and
   scenario-derived anchor distance. Deterministic role-fit terms separate the
   builder, supplier/defender, and miner/defender seats without adding random
   behavior.
8. **A dead fixed registry slot could stall the shared demo driver.** Shared
   policy dispatch now skips unavailable agents and treats those maintenance
   seats as complete; surviving agents continue the plan.
9. **The external adapter could heartbeat a dead seat forever.** A destroyed
   fixed-step unit now structurally abandons its task as `agent_death`,
   releases reservations, wakes the decision boundary, exposes only no-op WAIT,
   and cannot claim new work. The public five-seed gate observes 12 such releases
   and surviving seats still win every episode.
10. **Regenerated blocked work ignored its skill retry boundary.** The adapter
    now retains and hashes every active `next_retry_tick`, rejects a direct
    bypass as `retry_not_due`, and reopens held work at the exact tick. Resource-
    and core-short failures are task-type scoped so a seat cannot alternate
    equivalent targets; other failures remain target-local and unrelated task
    types stay selectable.

## Fixed-scenario evidence

`make candidate-policy-check` drives only public observations, masks,
`SELECT_CANDIDATE_TASK`, board claims/reservations, and task actions. The pinned
five seeds win at tick 8100. Under the corrected wait/loss lifecycle their
current minimum/mean final core health is 236/761.6; this is survival evidence,
not a claim that the old scorecard remains numerically unchanged. First-drill, opening-line,
initial-turret, and initial-supply ticks remain identical because the scenario
is deliberately seed-independent before wave 1. Native seeded spawn spread
then produces genuine differences: wave-clear ticks, message counts, unit
losses, and final core health vary; no cosmetic randomness was added.

`ExpertEpisode` remains behaviorally frozen as `run_frozen_episode` for the
M7.6 ladder and golden replay.

## Gaps closed in M7.4

- Fixed priorities, the 600-tick lead, and the magic 30-ammo target were
  replaced by live copper/economy/health/ammo coverage and engine-derived wave
  HP/DPS, Duo DPS, inaccuracy, magazine, travel, and clear-time values.
- `stop_on_decision_event` wakes the selector on task terminal/BLOCKED,
  economy-ready, wave spawn/clear, and core damage. Default callers retain exact
  requested stepping.
- Recoverable BLOCKED reasons regenerate/reselect with a 3-per-180-tick policy
  bound; assignment history supplies live switching cost.
- Assignment range comes from scenario objective geometry, with real normalized
  agent-to-target travel cost.
- Live block/rotation traversal and a 600-tick automated core-inflow ledger now
  implement `conveyor_path_connects` and `core_item_inflow_ge` (finding 7).
- Wave preemption and one readiness-triggered logistics seat prevent build work
  from blindly consuming every combat seat. DEFEND recurrence includes boundary
  identity so that seat can legally return after resupply.

## M7.5 variant evidence and remaining gaps

`make scenario-variation-check` evaluates the frozen ten-seed dev set without
touching the held-out set. Adaptive-v1 wins **8/10**, exactly meeting the 80%
gate. Seeds 2005 and 2007 both lose during/after wave 3. Both resolve the
optional upper-east lane on wave 3 and add one Dagger to that wave; the current
plan still constructs a fixed lower-east fortification, so readiness can report
full aggregate ammo/health without proving lane-specific firing coverage. This
is a real planning gap for M7.6's scorecard/ladder, not a reason to rotate seeds
or weaken the bounded variation.

- Supply targets still use live engine entity IDs in task identity. Ordering is
  deterministic within a boundary, but a future learned feature table should
  prefer stable spatial/logical turret identity.
- The accepted real-time default still uses the shared Java utility driver, but
  the opt-in `PublicCandidateDemo` now selects through the same public candidate,
  mask, typed-action, board, reservation, and skill path as training. Its exact
  Java/Python trace parity and stock-clock survival gates pass. Repeated combat
  logistics rebalance remains before default promotion and M10.1 commands.
- WAIT retains one shared task ID, so simultaneous idle seats can produce
  harmless rejected bids. This is visible in duplicate/rejection telemetry.
- Candidate generation does not yet produce alternative fortification anchors
  from the resolved spawn/lane geometry. The v2 policy can defend the wider
  region, but it cannot choose a lane-specific build plan.

## M7.6 ladder findings

- The permanent pure greedy baseline wins 9/10 dev variants while adaptive-v1
  wins 8/10. Their bootstrap win-rate intervals overlap, and dev is not a
  promotion set in any case. Adaptive-v1's wave preemption/readiness switching
  raises mean task abandonment from 0.000 to 0.089 without a dev win benefit;
  this is an M8 feature/reward-design input, not permission to tune on dev.
- None of the five ladder policies issues the explicit request/offer/accept
  helper protocol during ordinary defense episodes. `time_to_help_ticks` is
  therefore `null` with zero fulfilments throughout the ladder. Learning or a
  future scripted capability must deliberately exercise that seam before the
  metric can judge teammate help quality.
- The step-scoped `unit_destroy` event now gives the non-imputed recovery metric
  an exact loss tick: when a seat dies while holding a task type, the scorecard
  measures until a surviving seat next starts that type. Cells with no observed
  qualifying loss or restart remain `null` and report their coverage count.
