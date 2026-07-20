# bootstrap-defense-adaptive-probe

M7.4 acceptance variant for adaptive planning. Geometry, objectives, schematics,
wave schedule, and termination match `bootstrap-defense-v0`; the core starts
with 70 copper and receives a deterministic 450-copper grant at tick 1100.

The frozen M6 macro cannot recover its blocked opening. Adaptive-v1 regenerates
candidates, proves the production line with live connectivity plus a 600-tick
inflow window, and wins at tick 8100. See `docs/SCENARIOS.md` and
`make adaptive-planning-check`.
