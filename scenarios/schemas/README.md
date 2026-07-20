# Scenario schemas (stub)

Home for the versioned schema definitions that validate scenario files
(`scenario.yaml` and friends). **Not implemented yet** — lands with the first
loadable scenario (roadmap M6).

Planned contents:

- `scenario.schema.json` — JSON Schema for a scenario definition: id, version,
  world size, seed policy, block/unit whitelist, wave schedule, spawn points,
  objective markers, agent count bounds.
- Compatibility notes tying `scenario_version` to the protocol
  `scenario_schema_version` field (`docs/PROTOCOL.md`).

Until then, `docs/SCENARIOS.md` is the human-readable source of truth.
