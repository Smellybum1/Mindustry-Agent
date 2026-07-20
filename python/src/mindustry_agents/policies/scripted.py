"""Deterministic M5.3 scripted task policies (no RL framework dependencies)."""

from __future__ import annotations

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
        self._return_to_defense: set[int] = set()

    def observe_action_results(self, results: list[dict[str, Any]]) -> None:
        """Advance preference state only after the server accepts a selection."""

        for result in results:
            agent_id = int(result.get("agent_id", -1))
            preferred = self._pending_preferred.pop(agent_id, None)
            if preferred is None or not result.get("accepted", False):
                continue
            self._preferred_types.pop(agent_id, None)
            if preferred == "SUPPLY_TURRET":
                self._return_to_defense.add(agent_id)

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
            self._return_to_defense.discard(agent_id)
        self._last_tick[agent_id] = tick

        preferred_type = self._preferred_types.get(agent_id)
        if skill.get("type") == "DEFEND":
            self._return_to_defense.discard(agent_id)

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
            if agent_id in self._return_to_defense:
                preferred_type = "DEFEND_REGION"
            preferred = (
                _valid_candidates(observation, action_mask, (preferred_type,))
                if preferred_type is not None
                else []
            )
            selected = _highest_utility(preferred)
            if selected is None:
                if preferred_type is not None:
                    self._preferred_types.pop(agent_id, None)
                selected = _highest_utility(_valid_candidates(observation, action_mask))
            task_action = (
                {"type": "SELECT_CANDIDATE_TASK", "candidate_index": selected}
                if selected is not None
                else {"type": "WAIT"}
            )
            if selected is not None and preferred_type is not None:
                self._pending_preferred[agent_id] = preferred_type
        return {"agent_id": agent_id, "task_action": task_action}


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
