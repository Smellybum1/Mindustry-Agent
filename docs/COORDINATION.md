# Coordination core (`agent-core`) — the decentralized contract board

This document specifies the engine-independent coordination layer implemented in
`agent-core/src/main/java/agentcore/`. It is the "decentralized contract board"
of brief §11: a shared blackboard with contract-net semantics that scripted
policies drive in Milestone 5 and a learned policy drives later. It decides
nothing about *what* an agent should do; it stores commitments and enforces that
they are valid.

The board is **pure Java 17** and has **no dependency on mindustry `:core`
classes**. Task targets, item types, and coordinates are plain value types
(strings/ints/longs); the engine adapter maps them onto real `Tile`/`Building`/
`Unit`/`Item` content later, in the skill and plugin layers. This keeps the board
headless, deterministic, and fast to unit-test.

## Design invariants

- **Deterministic.** No wall-clock, no unseeded randomness. Tasks iterate in
  insertion order (`LinkedHashMap`); claim contests resolve by an explicit total
  order; resource costs and capability sets iterate in sorted order.
- **Single-threaded by contract** (brief §23.6). Only the simulation thread
  touches the board. It is deliberately **not** synchronized.
- **Ticks are `long`, ids are `String`, item types are `String`.** Documented so
  the engine adapter knows what it must translate.
- **Every state transition emits exactly one `CoordinationEvent`.** The structured
  event log is authoritative; human-readable announcements are *rendered from* it
  (ADR-0005), never the reverse.

## Package map

| Package | Contents |
|---|---|
| `agentcore` | Existing enums: `TaskType` (16), `CoordinationAct` (13), `SkillStatus` (6), `AgentId`. |
| `agentcore.task` | `TaskSpec` (immutable + builder), `TaskStatus`, `Target` (sealed: `TileTarget`/`RegionTarget`/`EntityTarget`/`ResourceTarget`), `ResourceCost`, `HelperOffer`, `HelperContract`. |
| `agentcore.board` | `TaskBoard` (the blackboard), `TaskState` (mutable lifecycle, board-only mutation), `Claim`, `ClaimOutcome`/`ClaimResult`, `OpResult`. |
| `agentcore.reservation` | `ReservationRegistry`, `Reservation` (sealed: tile/resource/region), `Rect`, `ReservationOutcome`/`ReservationResult`, `ReservationConflict`. |
| `agentcore.event` | `CoordinationEvent` (immutable, §11.3 schema), `EventLog` (drainable, message-id counter), `RateLimiter`. |
| `agentcore.announce` | `AnnouncementRenderer` (deterministic §20.3 templates). |
| `agentcore.utility` | `TaskUtility`, `HandTunedUtility`, `FeatureSource`, `UtilityFeatures`, `UtilityWeights`, `UtilityBreakdown`. |

## Task status state machine

```
                         propose
                            │
                            ▼
                        ┌───────┐   claim (lease)   ┌─────────┐
                        │ OPEN  │ ────────────────▶ │ CLAIMED │
                        └───────┘                   └─────────┘
                         ▲  ▲                         │   │  │
             release ────┘  │                  start  │   │  │ complete
          (voluntary,       │                         ▼   │  ▼
           reopen)          │                    ┌─────────┐ └────────▶ COMPLETED (terminal)
                            │                    │ RUNNING │
                            │        reportBlocked│  ▲   │  │ complete
                            │                    ▼  │   │  └────────▶ COMPLETED (terminal)
                            │                ┌─────────┐│
                            │                │ BLOCKED ││ reportProgress / heartbeat
                            │                └─────────┘│  (BLOCKED → RUNNING)
                            │                    │      │
                            │           abandon  │      │ abandon
                            │                    ▼      ▼
                            │                 ABANDONED (terminal)
                            │
                            │   expireStale(tick)  (lease lapsed, from CLAIMED/RUNNING/BLOCKED)
                            └──────────────────── EXPIRED ──▶ reopened to OPEN
```

- `CLAIMED`, `RUNNING`, `BLOCKED` are all "active" (owner holds the lease).
- `COMPLETED` and `ABANDONED` are terminal; ownership is cleared and reservations
  released.
- `EXPIRED` is a transient marker: `expireStale` emits it, releases reservations,
  and immediately reopens the task to `OPEN`.
- The board currently enforces a **single owner for every task** (the `exclusive`
  flag on `TaskSpec` is informational for now). Shared work is expressed through
  helper contracts, not co-ownership. This directly satisfies the safety property
  "no two agents validly own the same exclusive task" (brief §23.5).

## Leases and conflict resolution (brief §11.5)

- A **claim is a lease, not a lock.** `claim` sets `leaseExpiryTick = tick +
  leaseDurationTicks` (default 600 ticks ≈ 10 s at 60 tps).
- `start`, `heartbeat`, and `reportProgress` **renew** the lease. A task that
  keeps heartbeating never expires; one that stops becomes available.
- `expireStale(tick)` sweeps every active task whose lease has lapsed and reopens
  it. `claim` also opportunistically takes over a lapsed lease, releasing the
  stale owner's reservations first.
- **Simultaneous claims** (same tick) resolve by a deterministic total order,
  regardless of call order:
  1. higher **bid** wins;
  2. tie → earlier **announcement tick** (`ANNOUNCE_INTENT`, falling back to the
     claim tick if the agent never announced);
  3. tie → lexicographically smaller **agent id** (the display-name string).
- A task validly leased on an **earlier** tick is not stealable except through
  lease expiry.

## Helper contracts (brief §11.5, §17.1)

Helpers hold explicit, measurable contracts — they do not merely shadow the lead.

```
offerHelp ──▶ HelperOffer (pending)
   owner: acceptHelp ──▶ HelperContract (accepted, fulfilled=false)
                            └─ reportHelpFulfilled ──▶ fulfilled=true
   owner: declineHelp ──▶ offer removed, no contract
```

`reportHelpFulfilled` is emitted as a `PROGRESS` act with reason
`help_fulfilled`; it is **not** announced (brief §11.7 does not list helper
fulfilment among announceable transitions) but is captured structurally so
"accepted helper contract successfully fulfilled" is a rewardable event.

## Reservations (brief §11.6)

Soft reservations for tiles (rects), resources (amount per item), and regions.
Acquired on demand and released with the task (`complete`/`abandon`/`release`/
`expireStale` all call `releaseAll(taskId)`).

- **Human override.** A reservation flagged `human` always wins. Acquiring a human
  reservation over overlapping agent reservations makes those agents **yield**
  (their reservations are removed and a `ReservationConflict` is recorded);
  acquiring an agent reservation over a human one is **rejected**. The board emits
  a coordination event for each yield with reason `yield_to_human`, flagged for a
  single human announcement (brief §20.2: "yield and announce the conflict once").
- **Agent vs agent.** Incompatible overlap between different tasks is rejected;
  same-task re-reservation is compatible.
- **Resource budget.** With a configured per-item capacity, an agent acquisition
  that would exceed it is rejected; human reservations bypass the budget and
  consume it first. Reserved amounts are a sum of non-negative reservations and
  are never driven negative — releasing only ever removes existing reservations
  (safety property, brief §23.5).

The M5.4 simulation adapter acquires reservations after deterministic
utility/agent/task ordering and before assigning an engine skill. The reference
schematic reserves its exact multiblock bounding rectangle and estimated copper;
turret supply reserves estimated copper. The soft copper capacity is the
scenario's declared starting loadout, so a temporarily short task may still
start, block, and request the M5.3 helper contribution. Active reservations are
part of the canonical hash and summarized per task in `task_board[]`.

## Event schema (brief §11.3)

`CoordinationEvent` carries the §11.3 message fields (`message_id`, `episode_id`,
`tick`, `agent_id`, `coordination_act`, `task_id`, `task_type`, `target`,
`priority`, `estimated_ticks`, `estimated_resource_cost`, `required_capabilities`,
`helpers_requested`, `offered_contribution`, `confidence`, `lease_expiry_tick`,
`parent_task_id`, `dependency_task_ids`, `reason_code`, `progress`) plus
telemetry aids: `fromStatus`/`toStatus`, `relatedAgent` (e.g. the lead for a help
act), and an `announce` flag.

`act` is **nullable**. It is null for the two board-internal transitions that have
no act in the brief §11.2 vocabulary — task **proposal** and lease **expiry** — and
for reservation-conflict events. This lets the board honour "every transition
emits an event" without growing the 13-act vocabulary (which is mirrored in
`docs/STATUS.md` and the Python protocol). See "Resolved ambiguities" below.

`EventLog` is drainable and owns a monotonic `message_id` counter that survives
drains and resets only at episode boundaries.

## Rate limiting (brief §11.7)

`RateLimiter.shouldAnnounce(agent, act, taskId, tick, urgent)` gates **rendering**
only — the structured event is always logged. Rules:

- **Routine acts are never announced:** `HEARTBEAT`, `PROGRESS`, and null-act board
  transitions.
- **Normal cooldown:** at most one normal announcement per agent every
  `minTicksBetweenNormal` ticks (default 180 ≈ 3 s).
- **Urgent bypass:** urgent events skip the cooldown. Urgent = caller flag OR an
  inherently-urgent act (`BLOCKED`).
- **Duplicate suppression:** a repeated `(agent, act, task)` within
  `duplicateWindowTicks` (default 300 ≈ 5 s) is suppressed, urgent or not.

Communication is never rewarded; spam has a cost, not a benefit (brief §17.5).
At the wire boundary, every `task_events[]` entry includes `announcement`: the
renderer output when `announce=true`, otherwise the empty string. Thus consumers
never infer significance from prose, and routine structured traffic stays silent.

## Announcements (brief §20.3)

`AnnouncementRenderer` turns events into deterministic lines, keyed by act and
specialized per task type with a generic fallback. Examples produced:

```
[Agent Copper] Starting: establish production line at region core.
[Agent Shield] Starting: defend region east-defense. Requesting 1 helper.
[Agent Relay] Helping Shield: deliver 120 copper.
[Agent Shield] Blocked: 18 copper short. Waiting up to 20 seconds.
[Agent Copper] Complete: establish production line at region core.
[Board] Proposed: harvest 120 copper.
```

Display names are prettified (`agent-copper` → `Copper`). Scenario-specific detail
(e.g. "at 4.2 items/sec") is supplied by callers via reason codes and targets so
the renderer stays purely structural.

Each step also exposes cumulative episode `coordination_metrics`: prevented
duplicate-work incidents, completed/abandoned tasks, agent ticks, idle agent
ticks, idle fraction, and structured/announced message counts. Occupancy is
sampled exactly once per externally advanced engine tick on the simulation
thread; these metrics are telemetry only and never affect reward or state.

## Utility scaffold (brief §11.1)

`HandTunedUtility` implements the additive utility:

```
utility = team_value + urgency + capability_fit + role_fit + proximity
        + help_synergy + human_priority
        - travel_cost - resource_cost - duplication_risk - switching_cost
        - danger - uncertainty
```

Raw feature magnitudes come from a pluggable `FeatureSource` (the engine adapter
fills in proximity, travel cost, danger, etc. later); `UtilityWeights` scales each
term, with documented hand-tuned defaults (`human_priority` dominates;
`team_value`/`urgency` drive autonomous choice; `duplication_risk`/`switching_cost`
discourage thrashing). `breakdown(...)` exposes every weighted term for telemetry.
This is the seam a learned policy replaces; the board keeps enforcing valid
commitments regardless of how the score is produced.

## How a future policy / skill layer plugs in

1. The M5.1 **candidate generator** produces a bounded, deterministic list of
   masked `TaskSpec`s from scenario objectives and a sim-thread world snapshot.
   M5.2 proposes selected candidates through `CoordinationAdapter`.
2. A **policy** (scripted now, learned later) scores candidates via a
   `TaskUtility`, then drives the board: `announceIntent` → `claim` → `start` →
   `reportProgress`/`heartbeat` → `complete`/`abandon`/`release`, plus
   `offerHelp`/`acceptHelp` and `reserve*`.
3. The existing M3/M4 **skill executors** perform real Mindustry actions; the
   M5.2 adapter maps claimed task types to those skills and feeds progress,
   blockage, completion, abandonment, and lease heartbeats back into the board.
4. **Telemetry / protocol** drains `board.events()` each step, serializes every
   structured event, renders the rate-limited subset with
   `AnnouncementRenderer`, and publishes cumulative coordination metrics.

Every board operation returns an `OpResult`/`ClaimOutcome`/`ReservationOutcome`
rather than throwing, so invalid actions are a maskable signal (brief §15.4), not
a crash.

## Intentionally NOT in this layer yet

- **Skills / engine adapter.** No mindustry `:core` types, no unit control, no
  build-plan execution, no real item transfer. Task *execution* comes later.
- **Candidate generation ownership.** The board stores and arbitrates tasks; the
  separate `agentcore.candidates` catalog invents them and remains engine-free.
- **Capability enforcement on claim.** The board records `required_capabilities`
  but does not check the claiming agent against them — the candidate generator
  filters by capability upstream.
- **Observation / reward construction.** Events are the substrate; observation
  tensors and reward accounting are built elsewhere.

## Resolved spec ambiguities

1. **Proposal / expiry have no coordination act.** The brief §11.2 vocabulary has
   13 acts and none for "propose" or "lease expired", yet §11.3 requires every
   transition to emit an event. `docs/STATUS.md` pins the count at 13 and it is
   out of this track's scope to change. Resolution: `CoordinationEvent.act` is
   nullable; proposal, expiry, and reservation-conflict events carry a null act
   and describe the transition via `fromStatus`/`toStatus` + `reason_code`. No new
   act was added; the 13-act vocabulary is unchanged.
2. **Helper fulfilment has no act.** Modeled as a `PROGRESS` act with reason
   `help_fulfilled`, not announced (consistent with §11.7's announceable list).
3. **`RELEASE` vs `ABANDON`.** Both are in §11.2. Resolution: `abandon` is
   terminal (task dies, `ABANDONED`); `release` is voluntary and reopens the task
   to `OPEN` for others. Both release reservations.
4. **Non-exclusive tasks.** The board enforces single ownership for all tasks for
   now; the `exclusive` flag is retained on `TaskSpec` for the future co-ownership
   case but is not yet acted upon. Helpers cover shared work.
```
