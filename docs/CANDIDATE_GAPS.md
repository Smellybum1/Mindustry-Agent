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

## Fixed-scenario evidence

`make candidate-policy-check` drives only public observations, masks,
`SELECT_CANDIDATE_TASK`, board claims/reservations, and task actions. The pinned
five seeds win at tick 8100. `make evaluate-scripted` uses the same path and
records minimum/mean final core health 1082/1096.4. First-drill, opening-line,
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

## Remaining gaps assigned to M7.5+

- Supply targets still use live engine entity IDs in task identity. Ordering is
  deterministic within a boundary, but a future learned feature table should
  prefer stable spatial/logical turret identity.
- The real-time plugin uses the shared Java utility driver and the same
  scenario plan, while the externally stepped primary expert selects through
  the public protocol seam. A future reusable policy port should eliminate the
  remaining stage-local candidate construction in the demo driver.
- WAIT retains one shared task ID, so simultaneous idle seats can produce
  harmless rejected bids. This is visible in duplicate/rejection telemetry.
- Scenario variation and held-out seed governance are intentionally deferred
  to M7.5; this audit covers fixed scenario version 1 only.
