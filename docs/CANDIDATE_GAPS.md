# Candidate expressiveness gaps

This is the M7.3 audit of what the public task-candidate seam could and could
not express when it replaced the frozen `ExpertEpisode` macro as the primary
expert. It is evidence for M7.4, not a claim that the current catalog is
adaptive enough for learned play.

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

## Remaining gaps assigned to M7.4+

- Candidate priorities, estimates, the 600-tick defense lead, and the 30-ammo
  reserve are fixed constants rather than readiness/incoming-DPS calculations.
- Decisions are still polled at 30-tick external boundaries. Task terminal,
  block, wave, and damage events do not yet wake a selector immediately.
- Resource shortage has explicit regeneration/reselection; other failure and
  damage cases can still retry or wait too long. Switching cost is not yet fed
  from live assignment history.
- `assignmentRange` is the map diagonal, so range masking remains inert even
  though travel distance now uses real planned anchors.
- `conveyor_path_connects` and `core_item_inflow_ge` remain proxy predicates
  (REVIEW_M6 finding 7).
- Base/fortification work can remain in flight when a wave arrives. Expansion
  generation is enemy-gated, but full event-driven preemption belongs to M7.4.
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
