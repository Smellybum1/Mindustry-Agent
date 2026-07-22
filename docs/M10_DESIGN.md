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
reservations, and skills used by the externally stepped runtime. That
prerequisite is now satisfied. The legacy `ExpertCoordinationDriver` path is an
explicit regression oracle only; adding commands there would create a second
privileged policy surface and violate the roadmap's “same brain that trains”
requirement.

The implementation order is therefore:

1. port the demo scripted fallback onto the public candidate/action path while
   preserving no-command behavior and survival;
2. add the structured human-control state and candidate overlay;
3. expose the command grammar through queued simulation-thread application;
4. add opt-in session capture and only later learned-policy demo inference.

Current implementation state: the shared runtime-registry seam, real-time
registry, and engine-neutral Java greedy fallback are complete. The default
real-time path now runs that fallback through
`EngineCandidates`, masks, typed actions, `CoordinationAdapter`, the board,
reservations, and skills. Its probe has reached full readiness after ordinary
wave-damage recovery and agent rebind. All prerequisite gates are green, and
`DEMO_PUBLIC_POLICY=0` retains the old shared driver only as an explicit
regression oracle. The stock-clock
public-path survival gate is green through tick 8100 with core health 1100: its
authoritative world-state telemetry records all three wave clears, both post-
wave expansion schematics, both maintenance completions, and productive reserve
mining. The isolated fixed-step probe now records the real public candidate
tables, masks, skill states, Java actions, and authoritative results. Python
replay matches all 390 decision boundaries and 1,170 actions; two fresh JVMs
reproduce 225 accepted selections with digest
`aaf2e734ea384fe4b537cbdf3bd5342fb5e954f3432a91470ebce311fa503714`.
The logistics seat now remains dedicated during undersupplied combat, reducing
seven repeated abandon/reclaim cycles to two phase-entry rebalances and seven
unassigned waits. The engine-free `HumanControl` parser and simulation-thread
state are implemented and tested with strict grammar, stable rejection reasons,
bounded ordered goals, assignments, autonomy/quiet settings, deterministic ids
and revisions, and reset behavior. Explicit `TaskOrigin`/source-goal provenance
and the engine-free `HumanGoalResolver` are also implemented: only an already-
valid structured ordinary candidate may be wrapped, goal order reserves bounded
slots, and WAIT remains last. Autonomous task bytes, observations, and hashes
omit the new metadata and remain unchanged. Engine matching, assignment masks,
and queued plugin command application are now integrated. Server/client
callbacks parse and enqueue only; the simulation thread applies stable
structured results before policy decisions. Structured scenario matching,
human-priority rescoring, explicit and NORMAL implicit assignment masks,
LOW/NORMAL/HIGH behavior, terminal cancellation, reversible release, and quiet rendering are
live. `DEMO_HUMAN_CONTROL=1` completes an assigned human BUILD_LINE through
candidate → mask → typed action → board → skill, then exercises assigned LOW
defense, release and stable-id reassignment, unassigned HIGH defense, cancel,
and quiet suppression. The same probe injects an engine `BuildPlan` over an
active goal, observes one reservation yield/notice, preserves the block's live
resource floor, holds the completed-construction zone for 600 ticks, and proves
that no agent plan re-enters it. The
no-command public digest and stock-clock tick-8100/full-health survival remain
unchanged. M10.1 and M10.2 are complete; opt-in session capture remains next.

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

## Human presence reservations

On each real-time simulation update, the plugin scans the authoritative build
queues of same-team human players. Each plan becomes a deterministic presence
bundle keyed only by tile, block, rotation, and build/break intent. It reserves
the block's exact multiblock footprint and, for construction, its rules-scaled
item requirements. Player identity and wall-clock time are not inputs.

A human tile reservation overrides an overlapping agent reservation. A live
human resource floor may also yield the newest agent resource task until current
core stock can preserve all human requirements. The yielded controller clears
its build plans immediately. Human-origin goals use reversible board `RELEASE`
so their stable id can resume later; autonomous work ends with a structured,
non-rendered `ABANDON(yield_to_human)`. The reservation-conflict board event is
therefore the one rendered yield notice. While presence remains, masks exclude
overlapping builds and work that would spend below the human floor.

`BlockBuildEndEvent` from a human builder converts the plan to a tile-only
recent-construction reservation for exactly 600 simulation ticks. Its resource
floor is released because the items were consumed, while agents remain unable
to replace or build through the completed work. Cancelled or disconnected plans
release on the next sim-thread scan. With no human plans, the tracker emits no
changes and the public action path remains byte-identical.

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

Capture schema v3 is implemented in `DemoSessionCapture` and documented in
`docs/HUMAN_SESSIONS.md`; the Python loader retains legacy-v1/v2 readability. An
explicit `mindustry.agents.demo.capture-path`
creates a new UTF-8 JSONL file and refuses overwrite. It records pinned session
metadata, the existing public-candidate trajectory at every decision boundary,
applied control events, authoritative coordination events with render outcome,
and human-plan/recent-construction changes. The terminal line carries a record
count and SHA-256 over every preceding line. The dependency-free Python loader
fails closed on pin, ordering, structure, replay-revision, count, or digest
drift and produces deterministic pace/role/plan-change summaries. V3 adds the
project commit plus canonical agent-plugin and server runtime-content SHA-256
values; the Git Bash/Linux launcher derives and injects them after building the
artifacts. The canonical digest hashes sorted entry names and decompressed
bytes, ignoring ZIP order/timestamps/compression and only the generated
`version.properties` comment/`buildDate`. Stable version fields remain hashed.

The five M10.3 partner styles have a versioned executable profile catalog at
`configs/partners/human-scripted-v1.json`. Their engine-neutral deterministic
decision function is implemented and tested. The catalog remains staged for
M9: it cannot enter training until M8 promotion authorizes M9 work.

The reproducible M10.3 substrate gate is `bash scripts/human-session-check.sh`.
It must pass complete-file/digest validation, control replay, statistics, and
all five profile contracts without opening a network port. This closes the
capture/statistics/model implementation slice, but not the roadmap item or M10
exit checkbox: population activation is an M9 action and remains gated.
The historical v1 probe digest is
`3e864f35ffc3cf3c52bb72cfe28fec8d970f1a63a990efb2325294f0b963346b`.
Committed v2 diagnostic captures differed (`7cee94a1...` / `489bbb68...`)
because whole-server-JAR bytes changed on each upstream build. Per-entry
diagnosis isolated only volatile `version.properties`; all other entry contents
matched. V3 supersedes v2 for acceptance provenance. Its gate passes with
unchanged control schedule digest
`d30d529355b07ce18c45d074f58a11d4c444b3dff0a2ec70b89bfeb8cbbef6ce`;
two fresh JVMs from committed provenance implementation `c19e652324` now
reproduce content digest
`7a2c68e638e9fff3bbce4de60fe7ad14ceb5b1d37a0b8403a0605788289c7d99`,
plugin content `faca436f81b865bd...`, and server content
`e02c4208749ee2ed...` exactly.

M10.4 scorecard v1 is derived only from capture structure. Intervention rate
uses unique accepted-control ticks intersecting trajectory boundaries; plan
conflicts use `yield_to_human`; presence additions pair FIFO with conflict
events for yield latency; cancelled-before-completion goals are excluded from
goal compliance; and task-ID help requests pair with `help_fulfilled`. Human
announcement usefulness, team preference, scripted-team comparison, and
serious-session status may enter only through a separate schema-v1 rating file
bound to the session content SHA-256. The writer refuses overwrite and the
probe supplies no rating. See `docs/HUMAN_SESSIONS.md`.
Captured private join mode preflights both create-new artifact paths before
opening the server. After a normal exit it runs the same complete validation,
replay, statistics, and objective-scorecard postprocessor as the deterministic
probe, writing a sibling `.scorecard.unrated.json` unless an explicit
`DEMO_SCORECARD_PATH` is supplied. It never creates or infers a human rating.
The dependency-free `mindustry_agents.tools.human_rating` command constructs
the exact rating schema from four explicit human answers, obtains the binding
digest from a fully validated capture, rejects unknown fields, and writes with
create-new semantics. This removes manual digest transcription without
weakening human authority over preference evidence.
ADR-0058 governs multi-session evidence. The dependency-free schema-v2
`mindustry_agents.tools.human_evidence` report reloads complete capture/rating
pairs, rejects duplicate digests, and groups only exact engine/Arc/protocol/
scenario/policy identities. Serious ratings count toward the roadmap's
three-session floor, but the report keeps acceptance `not_evaluated`: scorecard
targets are not yet precommitted, and rating v1 does not measure a paired
agents-present versus agents-absent preference. Legacy capture v1/v2 is
excluded from the collection floor; v3 groups require the project commit and
both canonical runtime-content hashes. This prevents operational
scripted sessions from being mislabeled as learned-team or north-star evidence.
The deterministic probe currently yields 5/83 intervention ticks, one conflict
with zero-tick yield latency, 1/1 eligible goal compliance, no observed help
request, and 10 rendered/four suppressed announcements.

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

Current evidence (2026-07-23): all seven gates pass. The no-port human-control
probe covers the full command path plus engine-plan detection, deterministic
yield, rules-scaled resource floor, recent-construction exclusion, cleared agent
plans, and exactly one rendered conflict notification. Java tests pin presence
diff/expiry and tile/resource override semantics. Exact no-command parity,
golden determinism, stock survival, and the documented surfaces remain green.
M10.1 is complete.
