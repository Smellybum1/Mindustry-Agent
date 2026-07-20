"""Dependency-free M7.6 ladder records, scorecards, and bootstrap statistics."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Iterable

from mindustry_agents.evaluation.scripted import episode_summary
from mindustry_agents.tools.expert_common import EpisodeResult

LADDER_SCHEMA_VERSION = 1
BOOTSTRAP_RESAMPLES = 10_000
POLICY_ORDER = (
    "random-valid",
    "greedy-utility",
    "role-assignment",
    "frozen-expert",
    "adaptive-v1",
)


def load_seed_set(path: Path) -> dict[str, Any]:
    """Load and minimally validate a checked-in immutable seed-set contract."""

    contract = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "seed_set_id",
        "seed_set_version",
        "scenario_id",
        "scenario_version",
        "split",
        "seeds",
    }
    missing = sorted(required - contract.keys())
    if missing:
        raise ValueError(f"seed set {path} missing fields: {missing}")
    seeds = [int(seed) for seed in contract["seeds"]]
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError(f"seed set {path} must contain unique seeds")
    contract["seeds"] = seeds
    return contract


def teammate_scorecard(result: EpisodeResult) -> dict[str, Any]:
    """Derive the v0 teammate scorecard only from existing episode telemetry."""

    events = result.task_events
    requests: dict[str, deque[int]] = defaultdict(deque)
    help_times: list[int] = []
    meaningful = 0
    announced = 0
    for event in events:
        tick = int(event.get("tick", 0))
        task_id = str(event.get("task_id", ""))
        act = str(event.get("act", ""))
        if event.get("announce", False):
            announced += 1
        from_status = str(event.get("from_status", ""))
        to_status = str(event.get("to_status", ""))
        if from_status != to_status and (from_status or to_status):
            meaningful += 1
        if act == "REQUEST_HELP":
            requests[task_id].append(tick)
        elif event.get("reason_code") == "help_fulfilled" and requests[task_id]:
            help_times.append(tick - requests[task_id].popleft())

    recovery_times: list[int] = []
    for lost_agent, loss_tick in sorted(result.agent_loss_ticks.items()):
        prior_types = {
            str(event.get("task_type", ""))
            for event in events
            if int(event.get("agent_id", -1)) == lost_agent
            and int(event.get("tick", 0)) <= loss_tick
            and event.get("act") in {"START_TASK", "PROGRESS", "BLOCKED", "HEARTBEAT"}
            and event.get("task_type")
        }
        recovery = next(
            (
                int(event["tick"]) - loss_tick
                for event in events
                if int(event.get("tick", 0)) > loss_tick
                and int(event.get("agent_id", -1)) != lost_agent
                and event.get("act") == "START_TASK"
                and event.get("task_type") in prior_types
            ),
            None,
        )
        if recovery is not None:
            recovery_times.append(recovery)

    metrics = result.metrics
    completed = int(metrics.get("tasks_completed", 0))
    abandoned = int(metrics.get("tasks_abandoned", 0))
    terminal_tasks = completed + abandoned
    return {
        "idle_fraction": float(metrics.get("idle_fraction", 0.0)),
        "duplicate_work_incidents": int(metrics.get("duplicate_work_incidents", 0)),
        "time_to_help_ticks": (
            sum(help_times) / len(help_times) if help_times else None
        ),
        "help_requests": sum(len(values) for values in requests.values())
        + len(help_times),
        "help_fulfilments": len(help_times),
        "announcements_per_meaningful_transition": (
            announced / meaningful if meaningful else None
        ),
        "meaningful_transitions": meaningful,
        "announced_messages": announced,
        "task_abandonment_rate": abandoned / terminal_tasks if terminal_tasks else 0.0,
        "recovery_time_after_agent_loss_ticks": (
            sum(recovery_times) / len(recovery_times) if recovery_times else None
        ),
        "agent_losses_observed": len(result.agent_loss_ticks),
        "agent_loss_recoveries_observed": len(recovery_times),
    }


def ladder_episode_record(
    result: EpisodeResult,
    manifest: dict[str, Any],
    seed_set: dict[str, Any],
) -> dict[str, Any]:
    """Build one stable JSONL episode record."""

    record = episode_summary(result, manifest)
    # Boundary-level copper deltas and routine structured-message totals are
    # useful diagnostics but are not ladder judgment fields. They can differ by
    # one when autonomous engine work completes within the same external chunk,
    # so the reproducible ladder contract retains their scorecard derivatives
    # rather than serializing those incidental counters.
    record.pop("resources", None)
    record.pop("messages", None)
    record.update(
        {
            "record_type": "episode",
            "ladder_schema_version": LADDER_SCHEMA_VERSION,
            "seed_set": {
                "id": seed_set["seed_set_id"],
                "version": int(seed_set["seed_set_version"]),
                "split": seed_set["split"],
            },
            "scorecard": teammate_scorecard(result),
        }
    )
    return record


def _stable_seed(*parts: str) -> int:
    payload = "\0".join(parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return value ^ (value >> 31)


def _quantile(sorted_values: list[float], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = probability * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def bootstrap_interval(
    values: Iterable[float],
    *,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    """Return a deterministic percentile bootstrap interval for the mean."""

    samples = [float(value) for value in values]
    if not samples:
        return {"n": 0, "mean": None, "ci95": [None, None]}
    means = []
    state = seed
    for _ in range(resamples):
        total = 0.0
        for _ in samples:
            state = _splitmix64(state)
            total += samples[state % len(samples)]
        means.append(total / len(samples))
    means.sort()
    return {
        "n": len(samples),
        "mean": sum(samples) / len(samples),
        "ci95": [_quantile(means, 0.025), _quantile(means, 0.975)],
    }


def aggregate_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one policy/seed-set cell with correlated episode resampling."""

    if not records:
        raise ValueError("cannot aggregate an empty ladder group")
    policy = str(records[0]["manifest"]["policy"])
    seed_set_id = str(records[0]["seed_set"]["id"])

    def interval(name: str, getter: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
        values = [getter(record) for record in records]
        present = [float(value) for value in values if value is not None]
        return bootstrap_interval(
            present,
            seed=_stable_seed(policy, seed_set_id, name),
        )

    score_names = (
        "idle_fraction",
        "duplicate_work_incidents",
        "time_to_help_ticks",
        "announcements_per_meaningful_transition",
        "task_abandonment_rate",
        "recovery_time_after_agent_loss_ticks",
    )
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return {
        "record_type": "aggregate",
        "ladder_schema_version": LADDER_SCHEMA_VERSION,
        "policy": policy,
        "seed_set": dict(records[0]["seed_set"]),
        "episodes": len(records),
        "wins": sum(record["outcome"] == "win" for record in records),
        "win_rate": interval("win_rate", lambda row: row["outcome"] == "win"),
        "core_health": interval(
            "core_health", lambda row: row["core"]["health_final"]
        ),
        "scorecard": {
            name: interval(name, lambda row, key=name: row["scorecard"][key])
            for name in score_names
        },
        "episode_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def aggregate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (record["manifest"]["policy"], record["seed_set"]["id"])
        groups[key].append(record)
    policy_index = {policy: index for index, policy in enumerate(POLICY_ORDER)}
    return [
        aggregate_group(groups[key])
        for key in sorted(
            groups,
            key=lambda item: (item[1], policy_index.get(item[0], len(policy_index))),
        )
    ]


def held_out_promotions(aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the one-way held-out win-rate CI separation rule."""

    held_out = {
        row["policy"]: row
        for row in aggregates
        if row["seed_set"]["split"] == "held-out"
    }
    baseline = held_out.get("greedy-utility")
    if baseline is None:
        return []
    baseline_low, baseline_high = baseline["win_rate"]["ci95"]
    results = []
    for policy, row in sorted(held_out.items()):
        if policy == "greedy-utility":
            continue
        low, high = row["win_rate"]["ci95"]
        if low > baseline_high:
            status = "better_ci_separated"
        elif high < baseline_low:
            status = "worse_ci_separated"
        else:
            status = "not_ci_separated"
        results.append(
            {
                "record_type": "promotion",
                "candidate": policy,
                "baseline": "greedy-utility",
                "seed_set": dict(row["seed_set"]),
                "metric": "win_rate",
                "status": status,
                "promoted": status == "better_ci_separated",
            }
        )
    return results
