# M10 design — human command and teammate surface

**Status:** architecture accepted; implementation in progress (2026-07-23).
**Decision:** ADR-0057.

## Scope and sequencing

M10 is the human-teammate milestone. Its command and session-capture work may
advance against the scripted team while M8 promotion and M9 learning remain
gated. It must not start M9, authorize a learned successor, or access any
confirmation or held-out membership.

M10.1 has one mandatory prerequisite: the real-time plugin must select through
the same bounded public candidate table, masks, typed task actions, board,
reservations, and skills used by the externally stepped runtime. The plugin
currently uses `ExpertCoordinationDriver`'s remaining stage-local candidate
construction. Adding human commands there would create a second privileged
policy surface and violate the roadmap's “same brain that trains” requirement.

The implementation order is therefore:

1. port the demo scripted fallback onto the public candidate/action path while
   preserving no-command behavior and survival;
2. add the structured human-control state and candidate overlay;
3. expose the command grammar through queued simulation-thread application;
4. add opt-in session capture and only later learned-policy demo inference.

Current implementation state: the shared runtime-registry seam, real-time
registry, and engine-neutral Java greedy fallback are complete. An explicit
`DEMO_PUBLIC_POLICY=1` no-port path now runs that fallback through
`EngineCandidates`, masks, typed actions, `CoordinationAdapter`, the board,
reservations, and skills. Its probe has reached full readiness after ordinary
wave-damage recovery and agent rebind. It remains opt-in while combat logistics
churn is closed; human commands are not implemented. The stock-clock
public-path survival gate is green through tick 8100 with core health 1100: its
authoritative world-state telemetry records all three wave clears, both post-
wave expansion schematics, both maintenance completions, and productive reserve
mining. The isolated fixed-step probe now records the real public candidate
tables, masks, skill states, Java actions, and authoritative results. Python
replay matches all 338 decision boundaries and 1,014 actions; two fresh JVMs
reproduce 170 accepted selections with digest
`127bc6f8dc02b276531d17c94ce348d209a7de692bbbcff2ff18284cfc177907`.

## Command grammar

The existing `status`, `start`, `pause`, `resume`, and emergency `stop` commands
remain. M10.1 adds:

```text
/agents goal <task-type> <region-id>
/agents cancel <goal-id>
/agents assign <agent> <goal-id>
/agents release <agent>
/agents autonomy low|normal|high
/agents quiet on|off
```

Commands are case-insensitive only for fixed keywords and enum aliases. Goal,
region, and agent identity is returned in canonical form. Unknown task types,
regions, agents, goals, extra arguments, duplicate active goals, and illegal
state transitions are rejected without mutation. At most four active human
goals may exist; overflow is rejected rather than silently truncating the
ordinary eight-row candidate table.

Every mutation produces a structured result with a stable reason code. Client
text and server logs are rendered from that result. “Queued” is not “applied”:
the caller receives an immediate queued acknowledgement and an applied/rejected
result after the simulation thread drains the command.

## Structured control state

`agent-core` owns engine-free immutable records/enums for:

- `HumanGoal`: deterministic `human:goal:<sequence>` id, task type, canonical
  region id, author id, creation tick, revision, and active/cancelled status;
- `HumanAssignment`: agent index and goal id;
- `AutonomyLevel`: `LOW`, `NORMAL`, or `HIGH`;
- `HumanControlSnapshot`: ordered active goals, assignments, autonomy, quiet;
- `HumanControlCommand` and `HumanControlEvent`: parsed intent and authoritative
  application result.

Goal ids and revisions are allocated only on the simulation thread. No
wall-clock value, player display text, rendered announcement, or engine entity
id is authoritative. Reset clears the state. The default empty snapshot is
behavior-neutral.

Control events are a separate control-plane schema; they do not expand the 13
accepted coordination acts. Once a goal produces a task candidate, ordinary
board events remain authoritative for proposal, claim, start, progress,
completion, abandonment, and reservation conflicts.

## Public candidate integration

The plugin may not call a skill or mutate `TaskBoard` in response to a human
goal. A `HumanGoalResolver` receives the immutable control snapshot and the
ordinary candidate set at a decision boundary. It matches task type and region
using structured scenario geometry, never target prose. A match is wrapped as
an ordinary candidate with:

- task id equal to the stable goal id;
- the matched candidate's target, cost, capabilities, and executable task type;
- explicit `TaskOrigin.HUMAN` and source goal id;
- `human_priority = 1.0` through the existing utility feature coordinate.

If no safe ordinary candidate matches, the goal remains active and emits one
structured `no_valid_candidate` result; it does not invent coordinates, bypass
a mask, or call a skill. Human candidates reserve deterministic catalog space,
active-goal sequence breaks ties, and the canonical WAIT row remains available.
With an empty control snapshot, candidate order, masks, action/state hashes, and
policy decisions must remain byte-identical.

An explicit assignment constrains only that agent's ordinary action mask to the
matching goal candidate, continuation of that goal, forced lifecycle/safety
actions, or WAIT when the goal is temporarily unavailable. Other agents cannot
claim an assigned exclusive goal. Release removes the constraint and returns
the still-active goal to the unassigned pool. Cancel structurally abandons any
active assignment with reason `human_goal_cancelled`, releases reservations,
and removes the goal candidate at the next boundary.

## Autonomy semantics

- `LOW`: only explicitly assigned human goals may start; unassigned seats WAIT
  after safely abandoning autonomous work at the next decision boundary.
- `NORMAL` (default): each unassigned human goal deterministically binds the
  highest-utility capable idle seat; remaining seats may select autonomous work.
- `HIGH`: explicit assignments remain mandatory, while unassigned human goals
  are high-priority advisory candidates and every seat otherwise remains fully
  autonomous.

Forced emergency retreat, agent-loss handling, lease expiry, invalid-action
fallback, and emergency stop remain authoritative at every level. Autonomy never
permits deconstruction of human work or violation of human reservations.

## Quiet and acknowledgement semantics

Quiet mode suppresses only nonurgent rendered coordination chatter. Structured
events, counters, task state, command acknowledgements, emergency-stop output,
human-reservation yields, and urgent safety/blockage messages remain recorded
and visible. Switching quiet mode cannot change policy inputs, action masks,
board transitions, rewards, or state hashes.

## Threading and pacing

Server/client callbacks may parse tokens and enqueue immutable commands only.
The stock simulation thread drains them at the start of an update, before the
next policy decision. All validation that reads scenario, player, agent, board,
or world state and every mutation occurs there. Pause and emergency stop must be
applied within one real-time tick. The externally stepped runtime accepts no
human commands unless a future explicit protocol version adds the same
structured input; default training behavior is unchanged.

## Telemetry and replay

Opt-in demo telemetry records command queued/applied ticks, canonical command,
author id, result/reason, control revision, affected goal/agent, subsequent task
events, and rendered/suppressed announcement status. It contains no chat prose
as authority and no secrets. A deterministic replay consumes applied control
events at their recorded simulation ticks.

The existing training `state_hash` and selector tensor schema do not change for
the empty-control default. Any later policy-visible control observation requires
an explicit protocol/feature-schema version and fresh learning governance.

## Acceptance gates

M10.1 is complete only when all of the following pass:

1. parser/state tests cover every command, canonicalization, bounds, duplicate,
   invalid transition, reset, revision, and deterministic ordering;
2. a thread-boundary test proves callbacks only enqueue and the simulation
   thread alone reads/mutates scenario, board, registry, and world state;
3. a no-command parity gate preserves the public policy decisions, demo
   survival, command controls, smoke, determinism, and golden/negative replay;
4. an end-to-end private-server probe creates, assigns, executes, releases, and
   cancels a goal through candidate → mask → typed action → board → skill;
5. all autonomy modes and quiet rendering semantics are exercised, including
   forced safety behavior and urgent messages;
6. human reservations cause deterministic yield and exactly one rendered
   conflict notification; agents never deconstruct or consume reserved work;
7. `STATUS.md`, `HANDOFF.md`, `ROADMAP.md`, protocol/control schemas, and
   command help remain truthful.

No item may be checked from parser-only, board-only, or demo-only evidence.
