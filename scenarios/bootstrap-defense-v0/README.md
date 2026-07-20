# bootstrap-defense-v0 (spec stub — not implemented)

Target first scenario. **This directory currently holds a spec only**; the
loadable map/definition lands in roadmap M6. Full spec: `docs/SCENARIOS.md`.

- `scenario_id`: `bootstrap-defense-v0`
- `scenario_version`: `1`
- World: ~48×48–64×64 tiles, one Sharded core, 2–4 builder units, copper+lead,
  1–2 enemy approaches, **three deterministic waves**, no campaign/tech/planet
  metagame.
- Objective: establish a copper supply line, build and supply two east-facing
  Duo turrets, repair damage, survive three waves.
- Allowed content (v0): Mechanical Drill, Conveyor, Junction/Router, Duo, Copper
  Wall, core unit + tiny unit subset. (Mender/power only in a later stage.)

## Planned files (not yet present)

- `scenario.yaml` — versioned scenario definition (size, seed handling, block/
  unit whitelist, wave schedule, spawn/objective markers).
- `map.msav` (or generator params) — the actual small map.
- `schematics/east-duo-v1.msch` — the defensive schematic agents build.

Everything stochastic must seed from `root_seed`; changing the wave schedule or
spawns bumps `scenario_version`.
