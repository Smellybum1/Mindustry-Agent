# Scenarios

## bootstrap-defense-v0 (target first scenario — spec only, not implemented)

A tiny custom Serpulo cooperative survival scenario designed for fast reset,
obvious task decomposition, and measurable teamwork (brief §12). **Not the
campaign.** Spec lives here; the loadable scenario lands in roadmap M6. Detailed
stub in `scenarios/bootstrap-defense-v0/README.md`.

### World

- Size: ~48×48 or 64×64 tiles.
- One Sharded core.
- 2–4 agent-controlled Alpha-style builder units.
- One human slot in demo mode.
- Copper and lead patches.
- One or two enemy approaches.
- Short deterministic wave schedule: **three initial waves**.
- Limited or no weather.
- No campaign sector logic, no tech tree, no launch/planet metagame, no
  unnecessary content.

### Allowed content (first useful version)

Keep the block/unit set small:

- Mechanical Drill
- Conveyor
- Junction or Router
- Duo
- Copper Wall
- Mender only after power is introduced
- Combustion Generator + basic power nodes only in a later curriculum stage
- Core unit plus a very small unit subset

The first scenario must not require every subsystem at once.

### Team objective

> Establish a copper supply line, construct and supply two east-facing Duo
> turrets, repair damage, and survive three waves.

Decomposes into: gather initial copper; build/complete the copper line;
construct the defensive schematic; supply the turrets; defend and repair; help a
stalled builder; respond to changing wave pressure.

### Initial scripted demonstration (acceptance target, brief §12.4)

1. Agent Copper announces it will establish the copper line.
2. Agent Shield announces it will build the east defence and requests help.
3. Agent Relay offers to deliver resources to Shield.
4. The task board records claims and helper contracts.
5. Agents execute real Mindustry actions.
6. A deliberately blocked task causes a `BLOCKED` announcement and replanning.
7. The team survives the short scenario.
8. Same seed + scripted action/coordination trace reproduces the same state hashes.
9. The demo server lets a human join and observe the same announcements in real time.

Deterministic scripted task selection is acceptable for v0 — proving the
environment and coordination stack matters more than training immediately.

### Determinism and versioning

- `scenario_id = "bootstrap-defense-v0"`, `scenario_version = 1`.
- All stochastic systems seeded from `root_seed` (see `docs/PROTOCOL.md`).
- Wave schedule and spawn points are fixed and part of the versioned scenario
  definition; changing them bumps `scenario_version`.
