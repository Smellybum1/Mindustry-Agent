"""Deterministic M5.3 scripted task policies (no RL framework dependencies)."""

from __future__ import annotations

import itertools
from typing import Any, Iterable


_MASK_64 = (1 << 64) - 1


def _continue_or_none(action_mask: dict[str, Any]) -> dict[str, Any] | None:
    if action_mask.get("continue_current_task", False):
        return {"type": "CONTINUE_CURRENT_TASK"}
    return None


def _valid_candidates(
    observation: dict[str, Any],
    action_mask: dict[str, Any],
    task_types: Iterable[str] | None = None,
) -> list[tuple[int, dict[str, Any]]]:
    allowed_types = None if task_types is None else frozenset(task_types)
    masks = action_mask.get("candidate_task", [])
    result = []
    for candidate in observation.get("task_candidates", []):
        index = int(candidate["index"])
        if index >= len(masks) or not masks[index]:
            continue
        if allowed_types is not None and candidate["task_type"] not in allowed_types:
            continue
        result.append((index, candidate))
    return result


def _highest_utility(
    candidates: list[tuple[int, dict[str, Any]]],
) -> int | None:
    if not candidates:
        return None
    # Highest utility first; lowest stable candidate index breaks exact ties.
    return max(candidates, key=lambda entry: (float(entry[1]["utility"]), -entry[0]))[0]


def _blocked_abandon(
    agent_id: int,
    observation: dict[str, Any],
    action_mask: dict[str, Any],
) -> dict[str, Any] | None:
    skill = observation.get("skill", {})
    if action_mask.get("abandon", False) and skill.get("status") == "BLOCKED":
        reason = str(skill.get("reason", "unknown")).lower()
        return {
            "agent_id": agent_id,
            "task_action": {"type": "ABANDON", "reason": f"baseline_blocked:{reason}"},
        }
    return None


class PureGreedyUtilityPolicy:
    """Permanent non-adaptive baseline: highest utility, with blocked-task release."""

    def observe_action_results(self, results: list[dict[str, Any]]) -> None:
        del results

    def actions(
        self,
        observations: list[dict[str, Any]],
        action_masks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self.action(agent_id, observation, action_masks[agent_id])
            for agent_id, observation in enumerate(observations)
        ]

    def action(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
    ) -> dict[str, Any]:
        blocked = _blocked_abandon(agent_id, observation, action_mask)
        if blocked is not None:
            return blocked
        task_action = _continue_or_none(action_mask)
        if task_action is None:
            selected = _highest_utility(_valid_candidates(observation, action_mask))
            task_action = (
                {"type": "SELECT_CANDIDATE_TASK", "candidate_index": selected}
                if selected is not None
                else {"type": "WAIT"}
            )
        return {"agent_id": agent_id, "task_action": task_action}


class RandomValidPolicy:
    """Root-seeded random-valid baseline with a version-stable integer mixer."""

    def __init__(self, seed: int):
        self.seed = int(seed) & _MASK_64
        self._decisions: dict[int, int] = {}

    def observe_action_results(self, results: list[dict[str, Any]]) -> None:
        del results

    def actions(
        self,
        observations: list[dict[str, Any]],
        action_masks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self.action(agent_id, observation, action_masks[agent_id])
            for agent_id, observation in enumerate(observations)
        ]

    def _draw(self, agent_id: int, bound: int) -> int:
        decision = self._decisions.get(agent_id, 0)
        self._decisions[agent_id] = decision + 1
        value = (
            self.seed
            + 0x9E3779B97F4A7C15 * (decision + 1)
            + 0xD1B54A32D192ED03 * (agent_id + 1)
        ) & _MASK_64
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK_64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK_64
        value ^= value >> 31
        return value % bound

    def action(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
    ) -> dict[str, Any]:
        blocked = _blocked_abandon(agent_id, observation, action_mask)
        if blocked is not None:
            return blocked
        task_action = _continue_or_none(action_mask)
        if task_action is None:
            candidates = _valid_candidates(observation, action_mask)
            selected = (
                candidates[self._draw(agent_id, len(candidates))][0]
                if candidates
                else None
            )
            task_action = (
                {"type": "SELECT_CANDIDATE_TASK", "candidate_index": selected}
                if selected is not None
                else {"type": "WAIT"}
            )
        return {"agent_id": agent_id, "task_action": task_action}


class GreedyUtilityPolicy:
    """Continue active work; otherwise select the valid highest-utility candidate."""

    REPLANABLE_BLOCKS = frozenset(
        {
            "RESOURCES_SHORT",
            "CORE_SHORT",
            "INVALID_TARGET",
            "NO_CORE",
            "CORE_FULL",
            "STUCK",
            "OCCUPIED",
            "OUT_OF_RANGE",
            "PLAN_REMOVED",
            "CARGO_MISMATCH",
        }
    )
    REPLAN_WINDOW_TICKS = 180
    MAX_REPLANS_PER_WINDOW = 3

    def __init__(self) -> None:
        self._replan_ticks: dict[int, list[int]] = {}
        self._last_tick: dict[int, int] = {}
        self._preferred_types: dict[int, str] = {}
        self._pending_preferred: dict[int, str] = {}
        self._logistics_seats: set[int] = set()

    def observe_action_results(self, results: list[dict[str, Any]]) -> None:
        """Advance preference state only after the server accepts a selection."""

        for result in results:
            agent_id = int(result.get("agent_id", -1))
            preferred = self._pending_preferred.pop(agent_id, None)
            if preferred is None or not result.get("accepted", False):
                continue
            if preferred == "SUPPLY_TURRET":
                # Retain the logistics seat across successive magazines and brief
                # full-coverage intervals. Returning after each delivery churns it.
                self._preferred_types[agent_id] = "SUPPLY_TURRET"
                self._logistics_seats.add(agent_id)
            else:
                self._preferred_types.pop(agent_id, None)
                if preferred == "DEFEND_REGION":
                    self._logistics_seats.discard(agent_id)

    def alternate_nonconflicting_candidate(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
        excluded_candidate_indices: Iterable[int],
    ) -> int | None:
        """Purely select an adaptive-preference-preserving nonrisk label."""

        candidates = observation.get("task_candidates", [])
        for position, candidate in enumerate(candidates[:8]):
            if (
                not isinstance(candidate, dict)
                or type(candidate.get("index")) is not int
                or candidate["index"] != position
            ):
                raise ValueError("candidate catalog/index drift in first eight entries")

        excluded = frozenset(excluded_candidate_indices)
        masks = action_mask.get("candidate_task", [])
        allowed: list[tuple[int, dict[str, Any]]] = []
        for candidate in candidates[:8]:
            index = candidate["index"]
            if (
                index in excluded
                or index >= len(masks)
                or not masks[index]
                or candidate.get("valid") is False
                or str(candidate.get("task_type", "")) == "WAIT"
            ):
                continue
            allowed.append((index, candidate))

        preferred_type = self._preferred_types.get(agent_id)
        if preferred_type is None and agent_id in self._logistics_seats:
            preferred_type = "DEFEND_REGION"
        preferred = (
            [
                entry
                for entry in allowed
                if entry[1].get("task_type") == preferred_type
            ]
            if preferred_type is not None
            else []
        )
        if (
            not preferred
            and preferred_type == "SUPPLY_TURRET"
            and agent_id in self._logistics_seats
        ):
            if int(observation.get("team", {}).get("enemy_count", 0)) > 0:
                return None
            self._preferred_types.pop(agent_id, None)
            self._logistics_seats.discard(agent_id)
        return _highest_utility(preferred or allowed)

    def actions(
        self,
        observations: list[dict[str, Any]],
        action_masks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Select one atomic team bundle and retain one logistics seat in combat."""

        actions = [
            self.action(agent_id, observation, action_masks[agent_id])
            for agent_id, observation in enumerate(observations)
        ]
        if not observations:
            return actions

        team = observations[0].get("team", {})
        if int(team.get("enemy_count", 0)) <= 0 or float(
            team.get("defense_ammo_coverage", 1.0)
        ) >= 1.0:
            return actions

        suppliers = [
            agent_id
            for agent_id, observation in enumerate(observations)
            if observation.get("skill", {}).get("type") == "SUPPLY"
        ]
        defenders = [
            agent_id
            for agent_id, observation in enumerate(observations)
            if observation.get("skill", {}).get("type") == "DEFEND"
            and action_masks[agent_id].get("abandon", False)
        ]
        # Keep two combat seats occupied, but move the stable highest-index seat
        # to the public supply candidate as soon as the derived magazine target
        # stops being met.
        if not suppliers and len(defenders) > 2:
            agent_id = max(defenders)
            self._preferred_types[agent_id] = "SUPPLY_TURRET"
            actions[agent_id] = {
                "agent_id": agent_id,
                "task_action": {
                    "type": "ABANDON",
                    "reason": "readiness_rebalance",
                },
            }
        return actions

    def action(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
    ) -> dict[str, Any]:
        skill = observation.get("skill", {})
        team = observation.get("team", {})
        tick = int(team.get("tick", 0))
        if tick < self._last_tick.get(agent_id, tick):
            self._replan_ticks.pop(agent_id, None)
            self._preferred_types.pop(agent_id, None)
            self._pending_preferred.pop(agent_id, None)
            self._logistics_seats.discard(agent_id)
        self._last_tick[agent_id] = tick

        preferred_type = self._preferred_types.get(agent_id)
        if skill.get("type") == "DEFEND":
            self._logistics_seats.discard(agent_id)

        if (
            action_mask.get("abandon", False)
            and int(team.get("enemy_count", 0)) > 0
            and skill.get("type") not in {"", "DEFEND", "SUPPLY"}
        ):
            return {
                "agent_id": agent_id,
                "task_action": {"type": "ABANDON", "reason": "wave_preempt"},
            }

        reason = str(skill.get("reason", ""))
        if (
            action_mask.get("abandon", False)
            and skill.get("status") == "BLOCKED"
            and reason in self.REPLANABLE_BLOCKS
        ):
            history = self._replan_ticks.setdefault(agent_id, [])
            cutoff = tick - self.REPLAN_WINDOW_TICKS
            history[:] = [recorded for recorded in history if recorded > cutoff]
            if len(history) < self.MAX_REPLANS_PER_WINDOW:
                history.append(tick)
                replan_reason = (
                    "resources_short_replan"
                    if reason in {"RESOURCES_SHORT", "CORE_SHORT"}
                    else f"blocked_replan:{reason.lower()}"
                )
                return {
                    "agent_id": agent_id,
                    "task_action": {"type": "ABANDON", "reason": replan_reason},
                }
        task_action = _continue_or_none(action_mask)
        if task_action is None:
            if preferred_type is None and agent_id in self._logistics_seats:
                preferred_type = "DEFEND_REGION"
            preferred = (
                _valid_candidates(observation, action_mask, (preferred_type,))
                if preferred_type is not None
                else []
            )
            selected = _highest_utility(preferred)
            if (
                selected is None
                and preferred_type == "SUPPLY_TURRET"
                and agent_id in self._logistics_seats
            ):
                if int(team.get("enemy_count", 0)) > 0:
                    return {
                        "agent_id": agent_id,
                        "task_action": {"type": "WAIT"},
                    }
                preferred_type = None
                self._preferred_types.pop(agent_id, None)
                self._logistics_seats.discard(agent_id)
            if selected is None:
                if preferred_type is not None:
                    self._preferred_types.pop(agent_id, None)
                    self._logistics_seats.discard(agent_id)
                selected = _highest_utility(_valid_candidates(observation, action_mask))
            task_action = (
                {"type": "SELECT_CANDIDATE_TASK", "candidate_index": selected}
                if selected is not None
                else {"type": "WAIT"}
            )
            if selected is not None and preferred_type is not None:
                self._pending_preferred[agent_id] = preferred_type
        return {"agent_id": agent_id, "task_action": task_action}


class CandidateNativePlanner:
    """Deterministic team allocator over authoritative candidates and masks."""

    REPLANABLE_BLOCKS = GreedyUtilityPolicy.REPLANABLE_BLOCKS
    REPLAN_WINDOW_TICKS = GreedyUtilityPolicy.REPLAN_WINDOW_TICKS
    MAX_REPLANS_PER_WINDOW = GreedyUtilityPolicy.MAX_REPLANS_PER_WINDOW

    def __init__(
        self,
        *,
        maximum_build_schematic_selections: int | None = None,
        defer_schematics_during_active_build: bool = False,
        prioritize_supply_during_active_build: bool = False,
        require_positive_turret_coverage_for_active_build_supply: bool = True,
        suppress_line_after_completed_fortification: bool = False,
        suppress_line_during_active_fortification: bool = False,
        demobilize_defend_during_safe_interwave: bool = False,
        maximum_active_defend_tasks: int | None = None,
        preempt_noncombat_on_wave_increment: bool = False,
    ) -> None:
        if (
            maximum_build_schematic_selections is not None
            and maximum_build_schematic_selections < 1
        ):
            raise ValueError(
                "maximum_build_schematic_selections must be positive"
            )
        if (
            maximum_active_defend_tasks is not None
            and maximum_active_defend_tasks < 1
        ):
            raise ValueError("maximum_active_defend_tasks must be positive")
        self._replan_ticks: dict[int, list[int]] = {}
        self._last_tick = -1
        self._last_wave: int | None = None
        self._maximum_build_schematic_selections = (
            maximum_build_schematic_selections
        )
        self._defer_schematics_during_active_build = (
            defer_schematics_during_active_build
        )
        self._prioritize_supply_during_active_build = (
            prioritize_supply_during_active_build
        )
        self._require_positive_turret_coverage_for_active_build_supply = (
            require_positive_turret_coverage_for_active_build_supply
        )
        self._suppress_line_after_completed_fortification = (
            suppress_line_after_completed_fortification
        )
        self._suppress_line_during_active_fortification = (
            suppress_line_during_active_fortification
        )
        self._demobilize_defend_during_safe_interwave = (
            demobilize_defend_during_safe_interwave
        )
        self._maximum_active_defend_tasks = maximum_active_defend_tasks
        self._preempt_noncombat_on_wave_increment = (
            preempt_noncombat_on_wave_increment
        )

    def reset(self) -> None:
        self._replan_ticks.clear()
        self._last_tick = -1
        self._last_wave = None

    def observe_action_results(self, results: list[dict[str, Any]]) -> None:
        del results

    @staticmethod
    def _simple(agent_id: int, action_type: str, **values: Any) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "task_action": {"type": action_type, **values},
        }

    def _fixed_action(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
        tick: int,
        enemy_count: int,
        time_to_wave: int,
        defend_lead: int,
        wave_advanced: bool,
    ) -> dict[str, Any] | None:
        unit = observation.get("unit", {})
        if unit.get("dead", False):
            return self._simple(agent_id, "WAIT")

        skill = observation.get("skill", {})
        reason = str(skill.get("reason", ""))
        if (
            action_mask.get("abandon", False)
            and skill.get("status") == "BLOCKED"
            and reason in self.REPLANABLE_BLOCKS
        ):
            history = self._replan_ticks.setdefault(agent_id, [])
            cutoff = tick - self.REPLAN_WINDOW_TICKS
            history[:] = [recorded for recorded in history if recorded > cutoff]
            if len(history) < self.MAX_REPLANS_PER_WINDOW:
                history.append(tick)
                detail = (
                    "resources_short_replan"
                    if reason in {"RESOURCES_SHORT", "CORE_SHORT"}
                    else f"blocked_replan:{reason.lower()}"
                )
                return self._simple(agent_id, "ABANDON", reason=detail)

        if (
            action_mask.get("abandon", False)
            and enemy_count > 0
            and skill.get("type") not in {"", "DEFEND", "SUPPLY"}
        ):
            return self._simple(agent_id, "ABANDON", reason="wave_preempt")
        if (
            self._preempt_noncombat_on_wave_increment
            and action_mask.get("abandon", False)
            and wave_advanced
            and skill.get("type") not in {"", "DEFEND", "SUPPLY"}
        ):
            return self._simple(
                agent_id,
                "ABANDON",
                reason="wave_spawn_preempt",
            )
        if (
            self._demobilize_defend_during_safe_interwave
            and action_mask.get("abandon", False)
            and enemy_count == 0
            and not wave_advanced
            and time_to_wave > defend_lead
            and skill.get("type") == "DEFEND"
        ):
            return self._simple(
                agent_id,
                "ABANDON",
                reason="safe_interwave_demobilize",
            )
        if action_mask.get("continue_current_task", False):
            return self._simple(agent_id, "CONTINUE_CURRENT_TASK")
        return None

    @staticmethod
    def _candidates(
        observation: dict[str, Any], action_mask: dict[str, Any]
    ) -> list[dict[str, Any]]:
        masks = action_mask.get("candidate_task", [])
        result = []
        for position, candidate in enumerate(observation.get("task_candidates", [])):
            if (
                not isinstance(candidate, dict)
                or type(candidate.get("index")) is not int
                or candidate["index"] != position
            ):
                raise ValueError("candidate catalog/index drift")
            if (
                position >= len(masks)
                or not masks[position]
                or candidate.get("valid") is False
                or candidate.get("task_type") == "WAIT"
            ):
                continue
            result.append(candidate)
        return result

    def _phase_score(
        self,
        agent_id: int,
        candidate: dict[str, Any],
        team: dict[str, Any],
        active_build: bool,
    ) -> int:
        task_type = str(candidate.get("task_type", ""))
        enemies = int(team.get("enemy_count", 0))
        ammo = float(team.get("defense_ammo_coverage", 0.0))
        if (
            self._prioritize_supply_during_active_build
            and active_build
            and task_type == "SUPPLY_TURRET"
            and (
                not self._require_positive_turret_coverage_for_active_build_supply
                or float(team.get("defense_turret_coverage", 0.0)) > 0.0
            )
            and ammo < 1.0
        ):
            return 980
        if enemies > 0:
            preferred = (
                {
                    "DEFEND_REGION": 900,
                    "REPAIR_REGION": 760,
                    "SUPPLY_TURRET": 720,
                    "HARVEST_RESOURCE": 420,
                }
                if agent_id < 2
                else {
                    "SUPPLY_TURRET": 920 if ammo < 1.0 else 780,
                    "DEFEND_REGION": 860,
                    "REPAIR_REGION": 760,
                    "HARVEST_RESOURCE": 420,
                }
            )
            return preferred.get(task_type, 200)

        line_ready = bool(team.get("line_operational", False))
        turret_coverage = float(team.get("defense_turret_coverage", 0.0))
        opening = not line_ready and turret_coverage < 1.0
        if opening:
            role_order = (
                ("BUILD_LINE", "BUILD_SCHEMATIC", "HARVEST_RESOURCE"),
                ("BUILD_SCHEMATIC", "BUILD_LINE", "HARVEST_RESOURCE"),
                ("HARVEST_RESOURCE", "BUILD_LINE", "BUILD_SCHEMATIC"),
            )
            try:
                rank = role_order[agent_id].index(task_type)
            except (IndexError, ValueError):
                rank = 3
            return 900 - rank * 120

        time_to_wave = int(team.get("time_to_next_wave", 0))
        defend_lead = int(team.get("defend_lead_ticks", 0))
        broken = int(team.get("broken_block_count", 0))
        priorities = {
            "REPAIR_REGION": 920 if broken > 0 else 620,
            "BUILD_LINE": 900 if not line_ready else 500,
            "BUILD_SCHEMATIC": 880 if turret_coverage < 1.0 else 640,
            "SUPPLY_TURRET": 860 if ammo < 1.0 else 600,
            "DEFEND_REGION": 840 if time_to_wave <= defend_lead else 580,
            "HARVEST_RESOURCE": 720,
            "DELIVER_RESOURCE": 700,
        }
        score = priorities.get(task_type, 400)
        if task_type == "SUPPLY_TURRET" and agent_id == 2:
            score += 40
        if task_type == "DEFEND_REGION" and agent_id < 2:
            score += 30
        return score

    def _conflicts(
        self,
        candidates: tuple[dict[str, Any] | None, ...],
        maximum_new_defend_selections: int | None = None,
    ) -> bool:
        exclusive_ids: set[str] = set()
        semantic_targets: set[tuple[str, str]] = set()
        build_schematic_selections = 0
        defend_selections = 0
        for candidate in candidates:
            if candidate is None:
                continue
            if candidate.get("task_type") == "DEFEND_REGION":
                defend_selections += 1
                if (
                    maximum_new_defend_selections is not None
                    and defend_selections > maximum_new_defend_selections
                ):
                    return True
            if candidate.get("task_type") == "BUILD_SCHEMATIC":
                build_schematic_selections += 1
                if (
                    self._maximum_build_schematic_selections is not None
                    and build_schematic_selections
                    > self._maximum_build_schematic_selections
                ):
                    return True
            task_id = str(candidate.get("task_id", ""))
            semantic = (
                str(candidate.get("task_type", "")),
                str(candidate.get("target", "")),
            )
            if semantic in semantic_targets:
                return True
            semantic_targets.add(semantic)
            if candidate.get("exclusive", False):
                if task_id in exclusive_ids:
                    return True
                exclusive_ids.add(task_id)
        return False

    def actions(
        self,
        observations: list[dict[str, Any]],
        action_masks: list[dict[str, Any]],
        task_board: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if len(observations) != len(action_masks):
            raise ValueError("observation/action-mask seat count mismatch")
        if not observations:
            return []

        team = observations[0].get("team", {})
        tick = int(team.get("tick", 0))
        if tick < self._last_tick:
            self.reset()
        self._last_tick = tick
        wave = int(team.get("wave", 0))
        wave_advanced = self._last_wave is not None and wave > self._last_wave
        self._last_wave = wave
        enemy_count = int(team.get("enemy_count", 0))
        time_to_wave = int(team.get("time_to_next_wave", 0))
        defend_lead = int(team.get("defend_lead_ticks", 0))
        active_build = self._defer_schematics_during_active_build and any(
            task.get("task_type") in {"BUILD_LINE", "BUILD_SCHEMATIC"}
            and task.get("status") in {"CLAIMED", "RUNNING", "BLOCKED"}
            for task in (task_board or [])
        )
        fortification_blocks_line = (
            (
                self._suppress_line_after_completed_fortification
                or self._suppress_line_during_active_fortification
            )
            and any(
                task.get("task_type") == "BUILD_SCHEMATIC"
                and task.get("target") == "region expert_fortification_v1"
                and (
                    task.get("status") == "COMPLETED"
                    or (
                        self._suppress_line_during_active_fortification
                        and task.get("status")
                        in {"CLAIMED", "RUNNING", "BLOCKED"}
                    )
                )
                for task in (task_board or [])
            )
        )
        active_defend_tasks = sum(
            task.get("task_type") == "DEFEND_REGION"
            and task.get("status") in {"CLAIMED", "RUNNING", "BLOCKED"}
            for task in (task_board or [])
        )
        available_defend_slots = (
            None
            if self._maximum_active_defend_tasks is None
            else max(
                0,
                self._maximum_active_defend_tasks - active_defend_tasks,
            )
        )

        actions: list[dict[str, Any] | None] = [None] * len(observations)
        allocatable: list[int] = []
        options: list[list[dict[str, Any] | None]] = []
        for agent_id, (observation, action_mask) in enumerate(
            zip(observations, action_masks, strict=True)
        ):
            fixed = self._fixed_action(
                agent_id,
                observation,
                action_mask,
                tick,
                enemy_count,
                time_to_wave,
                defend_lead,
                wave_advanced,
            )
            if fixed is not None:
                actions[agent_id] = fixed
                continue
            allocatable.append(agent_id)
            candidates = self._candidates(observation, action_mask)
            if active_build:
                candidates = [
                    candidate
                    for candidate in candidates
                    if candidate.get("task_type") != "BUILD_SCHEMATIC"
                ]
            if fortification_blocks_line:
                candidates = [
                    candidate
                    for candidate in candidates
                    if candidate.get("task_type") != "BUILD_LINE"
                ]
            options.append(candidates + [None])

        best: tuple[dict[str, Any] | None, ...] | None = None
        best_key: tuple[Any, ...] | None = None
        for allocation in itertools.product(*options):
            if self._conflicts(allocation, available_defend_slots):
                continue
            selected = [candidate for candidate in allocation if candidate is not None]
            phase_total = sum(
                self._phase_score(agent_id, candidate, team, active_build)
                for agent_id, candidate in zip(
                    allocatable, allocation, strict=True
                )
                if candidate is not None
            )
            utility_total = sum(float(candidate.get("utility", 0.0)) for candidate in selected)
            stable_indices = tuple(
                -int(candidate["index"]) if candidate is not None else -10_000
                for candidate in allocation
            )
            key = (len(selected), phase_total, utility_total, stable_indices)
            if best_key is None or key > best_key:
                best = allocation
                best_key = key

        if best is None:
            best = tuple(None for _ in allocatable)
        for agent_id, candidate in zip(allocatable, best, strict=True):
            actions[agent_id] = (
                self._simple(
                    agent_id,
                    "SELECT_CANDIDATE_TASK",
                    candidate_index=int(candidate["index"]),
                )
                if candidate is not None
                else self._simple(agent_id, "WAIT")
            )
        return [action for action in actions if action is not None]


class CandidateNativePlannerV2(CandidateNativePlanner):
    """V1-exact planner with prospective schematic-selection serialization."""

    def __init__(self) -> None:
        super().__init__(maximum_build_schematic_selections=1)


class CandidateNativePlannerV3(CandidateNativePlanner):
    """V2-exact planner that defers schematics behind active build work."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
        )


class CandidateNativePlannerV4(CandidateNativePlanner):
    """V3-exact planner with readiness-preserving active-build fallback."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
        )


class CandidateNativePlannerV5(CandidateNativePlanner):
    """V4-exact planner using candidate validity as supply actionability."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
            require_positive_turret_coverage_for_active_build_supply=False,
        )


class CandidateNativePlannerV6(CandidateNativePlanner):
    """V5-exact planner that suppresses impossible post-fortification lines."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
            require_positive_turret_coverage_for_active_build_supply=False,
            suppress_line_after_completed_fortification=True,
        )


class CandidateNativePlannerV7(CandidateNativePlanner):
    """V6-exact planner suppressing lines throughout fortification lifecycle."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
            require_positive_turret_coverage_for_active_build_supply=False,
            suppress_line_after_completed_fortification=True,
            suppress_line_during_active_fortification=True,
        )


class CandidateNativePlannerV8(CandidateNativePlanner):
    """V7-exact planner that demobilizes defenders during safe inter-waves."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
            require_positive_turret_coverage_for_active_build_supply=False,
            suppress_line_after_completed_fortification=True,
            suppress_line_during_active_fortification=True,
            demobilize_defend_during_safe_interwave=True,
        )


class CandidateNativePlannerV9(CandidateNativePlanner):
    """V8-exact planner capped at two authoritative active defenders."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
            require_positive_turret_coverage_for_active_build_supply=False,
            suppress_line_after_completed_fortification=True,
            suppress_line_during_active_fortification=True,
            demobilize_defend_during_safe_interwave=True,
            maximum_active_defend_tasks=2,
        )


class CandidateNativePlannerV10(CandidateNativePlanner):
    """V9-exact planner preempting noncombat work at wave spawn."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
            require_positive_turret_coverage_for_active_build_supply=False,
            suppress_line_after_completed_fortification=True,
            suppress_line_during_active_fortification=True,
            demobilize_defend_during_safe_interwave=True,
            maximum_active_defend_tasks=2,
            preempt_noncombat_on_wave_increment=True,
        )


class CandidateNativePlannerV11(CandidateNativePlanner):
    """V9-exact planner capped at one authoritative active defender."""

    def __init__(self) -> None:
        super().__init__(
            maximum_build_schematic_selections=1,
            defer_schematics_during_active_build=True,
            prioritize_supply_during_active_build=True,
            require_positive_turret_coverage_for_active_build_supply=False,
            suppress_line_after_completed_fortification=True,
            suppress_line_during_active_fortification=True,
            demobilize_defend_during_safe_interwave=True,
            maximum_active_defend_tasks=1,
        )


class RoleAssignmentPolicy:
    """Fixed index roles with deterministic utility fallback inside each role."""

    ROLE_TYPES = {
        "miner": ("HARVEST_RESOURCE", "DELIVER_RESOURCE"),
        "builder": ("BUILD_SCHEMATIC", "REPAIR_REGION", "BUILD_LINE"),
        "supplier": ("SUPPLY_TURRET", "SUPPLY_BUILDING"),
        "defender": ("DEFEND_REGION", "ATTACK_TARGET"),
    }
    DEFAULT_ROLES = ("miner", "builder", "supplier", "defender")

    def __init__(self, roles: Iterable[str] | None = None):
        selected = tuple(roles or self.DEFAULT_ROLES)
        if not selected:
            raise ValueError("roles must not be empty")
        unknown = [role for role in selected if role not in self.ROLE_TYPES]
        if unknown:
            raise ValueError(f"unknown roles: {unknown}")
        self.roles = selected

    def role_for(self, agent_id: int) -> str:
        return self.roles[agent_id % len(self.roles)]

    def observe_action_results(self, results: list[dict[str, Any]]) -> None:
        del results

    def actions(
        self,
        observations: list[dict[str, Any]],
        action_masks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self.action(agent_id, observation, action_masks[agent_id])
            for agent_id, observation in enumerate(observations)
        ]

    def action(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
    ) -> dict[str, Any]:
        blocked = _blocked_abandon(agent_id, observation, action_mask)
        if blocked is not None:
            return blocked
        task_action = _continue_or_none(action_mask)
        if task_action is None:
            role = self.role_for(agent_id)
            preferred = _valid_candidates(
                observation, action_mask, self.ROLE_TYPES[role]
            )
            selected = _highest_utility(preferred)
            if selected is None:
                selected = _highest_utility(_valid_candidates(observation, action_mask))
            task_action = (
                {"type": "SELECT_CANDIDATE_TASK", "candidate_index": selected}
                if selected is not None
                else {"type": "WAIT"}
            )
        return {"agent_id": agent_id, "task_action": task_action}


class HelperCoordinator:
    """Pure helpers for the explicit request→offer→accept/decline contract flow."""

    @staticmethod
    def request(owner_id: int, helpers_requested: int = 1) -> dict[str, Any]:
        return {
            "agent_id": owner_id,
            "task_action": {
                "type": "REQUEST_HELP",
                "helpers_requested": max(1, helpers_requested),
            },
        }

    @staticmethod
    def nearest_idle_helper(
        owner_id: int,
        observations: list[dict[str, Any]],
        action_masks: list[dict[str, Any]],
    ) -> int | None:
        owner = observations[owner_id]["unit"]
        choices = []
        for agent_id, (observation, mask) in enumerate(zip(observations, action_masks)):
            if agent_id == owner_id or mask.get("continue_current_task", False):
                continue
            unit = observation["unit"]
            distance2 = (float(unit["x"]) - float(owner["x"])) ** 2 + (
                float(unit["y"]) - float(owner["y"])
            ) ** 2
            choices.append((distance2, agent_id))
        return min(choices)[1] if choices else None

    @staticmethod
    def offer(
        helper_id: int,
        task_index: int,
        contribution: str = "deliver copper",
        amount: int = 20,
    ) -> dict[str, Any]:
        return {
            "agent_id": helper_id,
            "task_action": {
                "type": "OFFER_HELP",
                "task_index": task_index,
                "contribution": contribution,
                "amount": max(0, amount),
            },
        }

    @staticmethod
    def accept(owner_id: int, offer_index: int = 0) -> dict[str, Any]:
        return {
            "agent_id": owner_id,
            "task_action": {"type": "ACCEPT_HELP", "offer_index": offer_index},
        }

    @staticmethod
    def decline(owner_id: int, offer_index: int = 0) -> dict[str, Any]:
        return {
            "agent_id": owner_id,
            "task_action": {"type": "DECLINE_HELP", "offer_index": offer_index},
        }
