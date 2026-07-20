# CLAUDE.md

**Read [`AGENTS.md`](AGENTS.md) — it is the source of truth for agent
instructions.** This file is a short pointer and intentionally does not
duplicate that content.

## Project orientation (10-line version)

1. This is `mindustry-coop-agents`: a fork-based monorepo of `Anuken/Mindustry`
   pinned at tag `v159.7` (commit `c9686eb5…`), branch `coop-agent/v159.7`.
2. Goal: a deterministic, externally-stepped, multi-agent RL environment where
   cooperating agents play a cut-down Mindustry defense scenario.
3. Upstream engine lives in `core/`, `server/`, `desktop/`; our code is added in
   new modules — never fight the upstream build.
4. Custom Java modules: `rl-server/` (headless fixed-step launcher),
   `agent-core/` (tasks/skills/coordination/observations), `agent-plugin/`
   (real-time demo adapter).
5. Python package `python/src/mindustry_agents/` hosts the PettingZoo env,
   process supervisor, policies, training, and telemetry.
6. Transport for the bootstrap phase is length-prefixed JSON over loopback TCP;
   spec in `docs/PROTOCOL.md`.
7. Settled decisions are in `docs/decisions/ADR-0001..0010`; do not relitigate.
8. Threading invariant: only the simulation thread reads/mutates game state.
9. Determinism is a hard requirement: same seed + action trace → same hash.
10. Truthful status lives in `docs/STATUS.md`; roadmap in `docs/ROADMAP.md`.
