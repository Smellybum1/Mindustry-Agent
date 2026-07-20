"""Dependency-free M6 scripted evaluation summaries and aggregation."""

from __future__ import annotations

from typing import Any, Iterable

from mindustry_agents.tools.scripted_demo import EpisodeResult

EVALUATION_SEEDS = (12345, 23456, 34567, 45678, 987666666)


def episode_summary(result: EpisodeResult, manifest: dict[str, Any]) -> dict[str, Any]:
    metrics = result.metrics
    return {
        "manifest": dict(manifest),
        "seed": result.seed,
        "outcome": result.outcome,
        "tick": result.tick,
        "milestones": {
            "first_drill_tick": result.first_drill_tick,
            "line_complete_tick": result.line_complete_tick,
            "turrets_built_tick": result.schematic_complete_tick,
            "turrets_supplied_tick": result.turrets_supplied_tick,
            "wave_clear_ticks": list(result.wave_clear_ticks),
        },
        "core": {
            "health_final": result.core_health,
            "damage": max(0.0, 1100.0 - result.core_health),
        },
        "units_lost": result.units_lost,
        "resources": {
            "copper_start": result.copper_start,
            "copper_final": result.copper_final,
            "copper_peak": result.copper_peak,
            "copper_min": result.copper_min,
            "boundary_in": result.copper_boundary_in,
            "boundary_out": result.copper_boundary_out,
            "boundary_note": "net changes observed at deterministic external step boundaries",
        },
        "tasks": {
            "completed": int(metrics.get("tasks_completed", 0)),
            "abandoned": int(metrics.get("tasks_abandoned", 0)),
            "duplicated": int(metrics.get("duplicate_work_incidents", 0)),
        },
        "idle_fraction": float(metrics.get("idle_fraction", 0.0)),
        "messages": {
            "structured": int(metrics.get("structured_messages", 0)),
            "announced": int(metrics.get("announced_messages", 0)),
        },
        "resources_short_replans": result.resources_short_replans,
    }


def aggregate(summaries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(summaries)
    wins = sum(row["outcome"] == "win" for row in rows)
    health = [float(row["core"]["health_final"]) for row in rows]
    return {
        "episodes": len(rows),
        "wins": wins,
        "win_rate": wins / len(rows) if rows else 0.0,
        "core_health_min": min(health) if health else 0.0,
        "core_health_mean": sum(health) / len(health) if health else 0.0,
        "units_lost": sum(int(row["units_lost"]) for row in rows),
        "structured_messages": sum(int(row["messages"]["structured"]) for row in rows),
        "announced_messages": sum(int(row["messages"]["announced"]) for row in rows),
    }
