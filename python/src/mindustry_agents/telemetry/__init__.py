"""Telemetry.

Will write run manifests (engine tag/commit, Arc hash, protocol/scenario
version, seeds, config), structured event logs, and convert those logs into
plots, tables, and replay summaries (brief §21). Reward telemetry must always
store the per-component breakdown, never only the sum (brief §17.6).

Currently a skeleton package; telemetry lands in roadmap M2+.
"""
