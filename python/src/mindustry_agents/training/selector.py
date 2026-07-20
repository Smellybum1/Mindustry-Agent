"""Framework-neutral ``selector_features_v1`` construction and action mapping."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

FEATURE_SCHEMA = "selector_features_v1"
MAX_CANDIDATES = 8
ACTION_COUNT = 10
TASK_TYPES = (
    "HARVEST_RESOURCE",
    "BUILD_LINE",
    "BUILD_SCHEMATIC",
    "SUPPLY_TURRET",
    "DEFEND_REGION",
    "REPAIR_REGION",
    "EXPAND_BASE",
    "SCOUT_AREA",
    "RETREAT",
    "ESCORT",
    "TRANSFER_RESOURCE",
    "WAIT",
    "ASSIST_BUILD",
    "ASSIST_COMBAT",
    "ASSIST_TRANSFER",
    "REQUEST_HELP",
)
UTILITY_FIELDS = (
    "team_value",
    "urgency",
    "capability_fit",
    "role_fit",
    "proximity",
    "help_synergy",
    "human_priority",
    "travel_cost",
    "resource_cost",
    "duplication_risk",
    "switching_cost",
    "danger",
    "uncertainty",
)
BOUNDARY_REASONS = (
    "task_terminal",
    "task_blocked",
    "economy_operational",
    "task_expired",
    "wave_spawn",
    "wave_clear",
    "core_damage",
)


class SelectorFeatureError(ValueError):
    """Raised when an observation cannot satisfy the pinned selector schema."""


@dataclass
class SelectorHistory:
    """Bounded recent-selection state carried by one learned seat."""

    previous_task_type: str | None = None
    selected_tick: int = 0

    def record_selection(self, task_type: str, tick: int) -> None:
        if task_type not in TASK_TYPES:
            raise SelectorFeatureError(f"unknown selected task type: {task_type}")
        self.previous_task_type = task_type
        self.selected_tick = int(tick)


@dataclass(frozen=True)
class SelectorFeatures:
    """Plain-list feature boundary consumed by the training-only tensor adapter."""

    candidates: list[list[float]]
    scalars: list[float]
    candidate_present: list[bool]
    action_mask: list[bool]
    policy_loss_mask: bool
    forced_task_action: dict[str, Any] | None


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SelectorFeatureError(f"{name} is not numeric") from exc
    if not math.isfinite(number):
        raise SelectorFeatureError(f"{name} is not finite")
    return number


def _unit(value: Any, name: str) -> float:
    return max(0.0, min(1.0, _finite(value, name)))


def _ratio(value: Any, denominator: Any, name: str) -> float:
    divisor = _finite(denominator, f"{name}.denominator")
    if divisor <= 0.0:
        raise SelectorFeatureError(f"{name} denominator must be positive")
    return _unit(_finite(value, name) / divisor, name)


def _candidate_row(candidate: dict[str, Any], metadata: dict[str, Any]) -> list[float]:
    task_type = str(candidate.get("task_type", ""))
    if task_type not in TASK_TYPES:
        raise SelectorFeatureError(f"unknown task type: {task_type!r}")
    raw = candidate.get("utility_features")
    if not isinstance(raw, dict):
        raise SelectorFeatureError("candidate is missing utility_features")
    row = [_unit(raw.get(name), f"utility_features.{name}") for name in UTILITY_FIELDS]
    row.extend(1.0 if name == task_type else 0.0 for name in TASK_TYPES)
    estimated_cost = candidate.get("estimated_cost", {})
    if not isinstance(estimated_cost, dict):
        raise SelectorFeatureError("estimated_cost must be an object")
    row.extend(
        (
            _unit(candidate.get("priority", 0.0), "priority"),
            _ratio(candidate.get("estimated_ticks", 0), metadata["tick_cap"], "estimated_ticks"),
            _ratio(estimated_cost.get("copper", 0), metadata["copper_budget"], "estimated_copper"),
            _ratio(candidate.get("helpers_requested", 0), 3, "helpers_requested"),
            _ratio(candidate.get("dependency_count", 0), 4, "dependency_count"),
            1.0 if candidate.get("exclusive", False) else 0.0,
            1.0 if candidate.get("semantic_task_active", False) else 0.0,
            1.0 if candidate.get("semantic_task_owned_by_other", False) else 0.0,
        )
    )
    if len(row) != 37:
        raise AssertionError(f"candidate schema drift: {len(row)} values")
    return row


def _wave_spacing(metadata: dict[str, Any]) -> int:
    ticks = [int(value) for value in metadata.get("wave_ticks", [])]
    spacings = [ticks[0]] if ticks else []
    spacings.extend(right - left for left, right in zip(ticks, ticks[1:]))
    return max(spacings or [int(metadata.get("wave_spacing", 1))])


def build_selector_features(
    observations: list[dict[str, Any]],
    action_masks: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    task_board: list[dict[str, Any]] | None = None,
    boundary_reasons: list[str] | tuple[str, ...] = (),
    history: SelectorHistory | None = None,
    agent_id: int = 0,
    terminated: bool = False,
    truncated: bool = False,
) -> SelectorFeatures:
    """Construct the exact 8x37 + 56 plain-number selector boundary."""

    if agent_id < 0 or agent_id >= len(observations) or agent_id >= len(action_masks):
        raise SelectorFeatureError("learned agent observation/mask is missing")
    observation = observations[agent_id]
    candidates = observation.get("task_candidates", [])
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise SelectorFeatureError("candidate row count must be between 0 and 8")
    rows = [_candidate_row(candidate, metadata) for candidate in candidates]
    present = [True] * len(rows) + [False] * (MAX_CANDIDATES - len(rows))
    rows.extend([[0.0] * 37 for _ in range(MAX_CANDIDATES - len(rows))])

    mask = action_masks[agent_id]
    server_select = list(mask.get("candidate_task", []))
    if len(server_select) != len(candidates):
        raise SelectorFeatureError("candidate mask length does not match candidate rows")
    select_mask = [
        bool(server_select[index]) and candidate.get("task_type") != "WAIT"
        for index, candidate in enumerate(candidates)
    ]
    select_mask.extend([False] * (MAX_CANDIDATES - len(select_mask)))
    action_mask = select_mask + [
        bool(mask.get("continue_current_task", False)),
        bool(mask.get("wait", False)),
    ]

    unit = observation.get("unit", {})
    skill = observation.get("skill", {})
    team = observation.get("team", {})
    dead = bool(unit.get("dead", False))
    forced: dict[str, Any] | None = None
    if bool(mask.get("abandon", False)) and skill.get("status") == "BLOCKED":
        reason = str(skill.get("reason", "blocked")).lower()
        forced = {"type": "ABANDON", "reason": f"blocked_replan:{reason}"}
    if dead or terminated or truncated:
        action_mask = [False] * 9 + [True]
        forced = {"type": "WAIT"}
    legal = sum(action_mask)
    if legal == 0:
        raise SelectorFeatureError("live controllable selector mask has no legal action")

    board = task_board or []
    status_counts = {
        name: sum(item.get("status") == name for item in board)
        for name in ("OPEN", "RUNNING", "BLOCKED")
    }
    self_owned = any(int(item.get("owner_agent_id", -1)) == agent_id for item in board)
    resource_reservations = sum(
        len(item.get("reserved_resources", {})) for item in board
    )
    tile_reservations = sum(int(item.get("tile_reservation_count", 0)) for item in board)
    tick = int(team.get("tick", 0))
    tick_cap = int(metadata["tick_cap"])
    width_units = int(metadata["width"]) * int(metadata["tile_size"])
    height_units = int(metadata["height"]) * int(metadata["tile_size"])
    diagonal = math.hypot(width_units, height_units)
    nearest = _finite(team.get("enemy_nearest_core_dist", -1), "enemy_nearest_core_dist")
    nearest_fraction = 1.0 if nearest < 0.0 else _unit(nearest / diagonal, "nearest_enemy")
    alive_fraction = sum(
        not bool(item.get("unit", {}).get("dead", False)) for item in observations
    ) / max(1, len(observations))

    scalars = [
        _ratio(unit.get("health", 0), unit.get("max_health", 0), "unit_health"),
        1.0 if dead else 0.0,
        _ratio(unit.get("x", 0), width_units, "unit_x"),
        _ratio(unit.get("y", 0), height_units, "unit_y"),
        _ratio(unit.get("item_amount", 0), unit.get("item_capacity", 0), "cargo"),
        _ratio(unit.get("build_queue_depth", 0), 8, "build_queue_depth"),
        _unit(unit.get("build_plan_progress", 0), "build_plan_progress"),
        _unit(skill.get("progress", 0), "skill_progress"),
        1.0 if mask.get("continue_current_task", False) else 0.0,
        1.0 if skill.get("status") == "BLOCKED" else 0.0,
        _ratio(team.get("copper", 0), metadata["copper_budget"], "core_copper"),
        _ratio(team.get("core_health", 0), metadata["core_health_max"], "core_health"),
        _ratio(
            team.get("core_copper_inflow_per_s", 0),
            team.get("core_copper_inflow_target_per_s", 1),
            "core_inflow",
        ),
        _ratio(team.get("time_to_next_wave", 0), _wave_spacing(metadata), "next_wave"),
        _ratio(team.get("wave", 0), metadata["wave_count"], "wave_ordinal"),
        _ratio(team.get("enemy_count", 0), 10, "enemy_count"),
        _ratio(team.get("enemy_total_health", 0), 5000, "enemy_health"),
        nearest_fraction,
        1.0 if team.get("line_operational", False) else 0.0,
        _unit(team.get("defense_ammo_coverage", 0), "defense_ammo_coverage"),
        _unit(team.get("defense_health_coverage", 0), "defense_health_coverage"),
        _unit(team.get("defense_turret_coverage", 0), "defense_turret_coverage"),
        _unit(team.get("defense_readiness", 0), "defense_readiness"),
        _ratio(team.get("broken_block_count", 0), 32, "broken_blocks"),
        _unit(alive_fraction, "alive_fraction"),
        _unit((tick_cap - tick) / tick_cap, "remaining_ticks"),
        _ratio(status_counts["OPEN"], 32, "board_open"),
        _ratio(status_counts["RUNNING"], 32, "board_running"),
        _ratio(status_counts["BLOCKED"], 32, "board_blocked"),
        1.0 if self_owned else 0.0,
        _ratio(resource_reservations, 32, "resource_reservations"),
        _ratio(tile_reservations, 32, "tile_reservations"),
    ]
    recent = history or SelectorHistory()
    scalars.extend(
        1.0 if recent.previous_task_type == task_type else 0.0
        for task_type in TASK_TYPES
    )
    scalars.append(
        0.0
        if recent.previous_task_type is None
        else _ratio(max(0, tick - recent.selected_tick), tick_cap, "ticks_since_selection")
    )
    reason_set = set(boundary_reasons)
    scalars.extend(1.0 if reason in reason_set else 0.0 for reason in BOUNDARY_REASONS)
    if len(scalars) != 56:
        raise AssertionError(f"scalar schema drift: {len(scalars)} values")
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in scalars):
        raise SelectorFeatureError("scalar output contains an invalid value")
    return SelectorFeatures(
        candidates=rows,
        scalars=scalars,
        candidate_present=present,
        action_mask=action_mask,
        policy_loss_mask=forced is None and legal > 1,
        forced_task_action=forced,
    )


def selector_action(index: int, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Map one legal selector index to the ordinary typed task-action seam."""

    if index < 0 or index >= ACTION_COUNT:
        raise SelectorFeatureError(f"selector action index out of range: {index}")
    if index < MAX_CANDIDATES:
        if index >= len(candidates) or candidates[index].get("task_type") == "WAIT":
            raise SelectorFeatureError(f"selector candidate action is unavailable: {index}")
        return {"type": "SELECT_CANDIDATE_TASK", "candidate_index": index}
    if index == 8:
        return {"type": "CONTINUE_CURRENT_TASK"}
    return {"type": "WAIT"}
