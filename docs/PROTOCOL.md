# Protocol specification — v1 (bootstrap phase)

Authoritative spec for the training-control protocol between the Python process
supervisor and each `rl-server` JVM. Transport is **length-prefixed JSON over
loopback TCP** for the bootstrap phase (ADR-0004). Java and Python
implementations must match this document; changing a field means changing this
file, `python/src/mindustry_agents/protocol.py`, and the Java protocol in the
**same commit**.

`protocol_version = 1`.

## 1. Framing

```text
+-------------------+-------------------------------+
| length (4 bytes)  | body (length bytes)           |
| big-endian uint32 | UTF-8 encoded JSON object      |
+-------------------+-------------------------------+
```

- The length prefix is a 4-byte big-endian unsigned integer giving the number of
  bytes in the JSON body that follows.
- The body is a single UTF-8 JSON **object**.
- The object always contains a string field **`type`** that discriminates the
  message (values listed below).
- **Maximum message size: 16 MiB** (`16 * 1024 * 1024`). A declared length or an
  encoded body above this bound is a protocol error and must be rejected, never
  truncated or partially applied.
- Unknown fields are ignored on decode (forward compatibility). Unknown `type`
  values are a protocol error.

## 2. Messages

Field names below are the JSON keys. Types: `int`, `float`, `str`, `bool`,
`obj` (nested JSON object), `[...]` (array).

### 2.1 Handshake

`HandshakeRequest` (`type = "handshake_request"`)

| field | type | notes |
|---|---|---|
| `protocol_version` | int | client's protocol version |
| `client_name` | str | free-form client identifier |
| `requested_features` | [str] | optional capability requests |

`HandshakeResponse` (`type = "handshake_response"`)

| field | type | notes |
|---|---|---|
| `protocol_version` | int | server's protocol version |
| `engine_version` | str | e.g. `v159.7` |
| `engine_commit` | str | full commit hash |
| `arc_version` | str | pinned Arc hash |
| `scenario_schema_version` | int | |
| `supported_features` | [str] | |
| `process_id` | int | OS pid of the JVM |

Fail fast on incompatible **major** versions.

### 2.2 Reset

`ResetRequest` (`type = "reset_request"`)

| field | type | notes |
|---|---|---|
| `request_id` | int | monotonically unique per connection |
| `scenario_id` | str | e.g. `bootstrap-defense-v0` |
| `scenario_version` | int | |
| `root_seed` | int | seeds all stochastic systems |
| `agent_count` | int | 2–4 for the first scenario |
| `difficulty` | str | |
| `deterministic` | bool | must be `true` in training |
| `options` | obj | scenario-specific overrides |

`ResetResponse` (`type = "reset_response"`)

| field | type | notes |
|---|---|---|
| `request_id` | int | echoes the request |
| `episode_id` | str | unique per episode |
| `tick` | int | always `0` after reset |
| `initial_observations` | [obj] | one per agent, agent-index order |
| `action_masks` | [obj] | one per agent |
| `state_hash` | str | stable hash of initial state |
| `metadata` | obj | scenario metadata |

### 2.3 Step

`StepRequest` (`type = "step_request"`)

| field | type | notes |
|---|---|---|
| `request_id` | int | monotonically unique |
| `episode_id` | str | must match the active episode |
| `expected_tick` | int | server's current tick as the client believes it; stale ⇒ reject |
| `ticks_to_advance` | int | exact number of engine updates to apply |
| `agent_actions` | [obj] | one high-level action per agent, applied atomically (see below) |

**`agent_actions[]` entry (M3, additive — docs/M3_DESIGN.md D5):**

```json
{"agent_id": 0, "command": {"type": "MINE", "tile_x": 32, "tile_y": 32, "amount": 20}}
```

`command.type` is one of `NAVIGATE` / `MINE` / `DELIVER_CORE` / `WAIT` / `BUILD` /
`SCHEMATIC` / `SUPPLY` / `REBUILD` / `CONTINUE`.
An absent `command` (or `CONTINUE`) keeps the agent's current skill running.
Params by type: `NAVIGATE {x, y, tolerance?}` (world coords), `MINE {tile_x, tile_y,
amount?}` (tile coords), `DELIVER_CORE {}`, `WAIT {ticks?}`,
`BUILD {block, tile_x, tile_y, rotation}` (scenario-whitelisted block id and tile
coords; rotation 0..3). `BUILD` enqueues the unit's real engine `BuildPlan`; the
engine consumes core resources incrementally and construction is never placed
directly. `SCHEMATIC {name, tile_x, tile_y}` executes a checked-in, ordered list
of anchor-relative `BUILD` entries; unknown names and out-of-bounds footprints are
rejected. `SUPPLY {item, tile_x, tile_y, amount}` withdraws up to the requested
item count from the core through the legal engine path, carries it, and deposits
what the target accepts. Its skill observation adds `requested`, `delivered`,
`target_stock_before`, and `target_stock`; item-turret stock is native ammo units.
`REBUILD {x1, y1, x2, y2}` executes queued destroyed-block plans inside the
inclusive tile rectangle in engine queue order. Its skill observation adds
`initial_broken` and `completed`; team observation adds `broken_block_count`.
Actions are applied on
the sim thread **before** advancing; each is validated and echoed in
`action_results[]` — an invalid action is rejected there, never crashes the step.

`StepResponse` (`type = "step_response"`)

| field | type | notes |
|---|---|---|
| `request_id` | int | echoes the request |
| `episode_id` | str | |
| `previous_tick` | int | tick before advancing |
| `tick` | int | tick after advancing (`previous_tick + ticks_to_advance`) |
| `observations` | [obj] | one per agent (see per-agent shape below) |
| `action_masks` | [obj] | one per agent |
| `action_results` | [obj] | M3 additive: one per submitted action, `{agent_id, accepted, reason, command_type}` |
| `team_state` | obj | shared team-level summary |
| `reward_breakdowns` | [obj] | per-agent, per-component; never only a sum (brief §17.6) |
| `terminations` | [bool] | per agent |
| `truncations` | [bool] | per agent |
| `task_events` | [obj] | coordination/task-board events this step |
| `game_events` | [obj] | engine events (waves, deaths, builds) |
| `state_hash` | str | stable hash after advancing |
| `timing` | obj | `{engine_ms, observation_ms, serialization_ms, io_ms}` |

**Per-agent observation shape (M3 — docs/M3_DESIGN.md D6).** Each entry of
`observations[]` / `initial_observations[]` is agent-scoped:

```json
{
  "agent_id": 0,
  "unit":  {"x": 216.0, "y": 192.0, "vx": 0.0, "vy": 0.0, "health": 150.0,
            "item": "copper", "item_amount": 21, "mining": false, "flag": 0.0, "dead": false},
  "skill": {"type": "MINE", "status": "SUCCEEDED", "reason": "TARGET_REACHED",
            "progress": 1.0, "next_retry_tick": -1},
  "team":  {"tick": 860, "wave": 1, "copper": 100, "lead": 0, "unit_count": 2,
            "building_count": 1, "core_health": 1100.0, "done": false}
}
```

`skill.status` is one of `READY`/`RUNNING`/`SUCCEEDED`/`BLOCKED`/`FAILED`/`CANCELLED`;
`skill.reason` is a machine-readable code (e.g. `ARRIVED`, `INVALID_TARGET`, `STUCK`,
`DELIVERED`, `BUILT`, `RESOURCES_SHORT`, `OCCUPIED`, `OUT_OF_RANGE`,
`PLAN_REMOVED`). Raw floats are reported here; the state hash quantizes positions/velocity
to 1e-3 (docs/M3_DESIGN.md D6/D7).

### 2.4 Health and control

`HealthRequest` (`type = "health_request"`): `{request_id}`

`HealthResponse` (`type = "health_response"`):
`{request_id, ok, uptime_ticks, episode_id, detail}`

`CloseRequest` (`type = "close_request"`): `{request_id, reason}` — server drains
and exits cleanly.

`ErrorResponse` (`type = "error_response"`):
`{request_id, code, message, detail}` — returned for any rejected request
(stale tick, unknown episode, malformed bundle, oversized message, unknown type).

Reserved for later: `GetMetadataRequest`, `GetStateHashRequest` (brief §18.4).

## 3. Protocol invariants (brief §18.5)

1. Every request has a monotonically unique request ID.
2. Every step names the expected episode and tick.
3. A stale action bundle is rejected via `ErrorResponse`, never silently applied.
4. All agents in a world are stepped atomically (one bundle, one advance).
5. Unknown enum values are handled safely (rejected or mapped to a safe default,
   never crashing).
6. Message and list sizes are capped (16 MiB message cap; per-list caps defined
   per scenario).
7. The control socket binds to loopback by default.
8. Java game mutations occur only on the simulation thread (see
   `docs/ARCHITECTURE.md` threading rule).
9. Timing telemetry distinguishes engine, observation, serialization, and I/O
   time.

## 4. Versioning rules

- `protocol_version` is a single integer. Major-incompatible changes bump it and
  the handshake must reject mismatched majors.
- Additive, backward-compatible fields do not bump the version; decoders ignore
  unknown fields.
- The JSON encoding is the bootstrap transport. Migration to Protobuf is planned
  for Stage D **if** serialization exceeds ~10% of step time or schema drift
  becomes a risk (ADR-0004). The message shapes here are the contract that the
  Protobuf schema will preserve.

## 5. Reference implementation

`python/src/mindustry_agents/protocol.py` implements the framing and all message
dataclasses, with tests in `python/tests/test_protocol.py`. The Java encoder
lands with the M1 spike in `rl-server`.
