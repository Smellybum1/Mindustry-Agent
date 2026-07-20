# bootstrap-defense-v0 (spec complete — loader lands in M6)

Target first scenario. **This directory holds the full spec**; the loadable
map/definition (engine wiring) lands in roadmap M6. Full human-readable spec:
`docs/SCENARIOS.md`; strategy/balance rationale: `docs/STRATEGY_NOTES.md`;
machine-readable definition: `scenario.json` (schema:
`../schemas/README.md`).

- `scenario_id`: `bootstrap-defense-v0`
- `scenario_version`: `1`
- World: ~48×48–64×64 tiles, one Sharded core, 2–4 builder units, copper+lead,
  1–2 enemy approaches, **three deterministic waves**, no campaign/tech/planet
  metagame.
- Objective: establish a copper supply line, build and supply two east-facing
  Duo turrets, repair damage, survive three waves.
- Allowed content (v0): Mechanical Drill, Conveyor, Junction/Router, Duo, Copper
  Wall, core unit + tiny unit subset. (Mender/power only in a later stage.)

## Files

- `scenario.json` — **present.** Versioned, machine-readable definition (size,
  seed policy, block/unit whitelist, wave schedule, spawn/objective markers,
  engine-verified balance numbers).

## Planned files (not yet present)

- `map.msav` — not used; v0 is fully **procedural** (generated in code, matching
  `rl-server/.../Scenario.java`), so there is no map file to read.
- `schematics/east-duo-v1.msch` — the defensive schematic agents build (2 Duos +
  5 copper walls; its block list is inlined in `scenario.json` →
  `reference_schematic` until the `.msch` is authored).

Everything stochastic must seed from `root_seed`; in v0 nothing varies with the
seed. Changing the wave schedule, spawns, patches, whitelist, loadout, or
win/lose conditions bumps `scenario_version`.
