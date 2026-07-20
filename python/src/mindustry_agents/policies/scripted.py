"""Deterministic M5.3 scripted task policies (no RL framework dependencies)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


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


@dataclass(frozen=True)
class GreedyUtilityPolicy:
    """Continue active work; otherwise select the valid highest-utility candidate."""

    def action(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
    ) -> dict[str, Any]:
        skill = observation.get("skill", {})
        if (
            action_mask.get("abandon", False)
            and skill.get("status") == "BLOCKED"
            and skill.get("reason") in {"RESOURCES_SHORT", "CORE_SHORT"}
        ):
            return {
                "agent_id": agent_id,
                "task_action": {
                    "type": "ABANDON",
                    "reason": "resources_short_replan",
                },
            }
        task_action = _continue_or_none(action_mask)
        if task_action is None:
            selected = _highest_utility(_valid_candidates(observation, action_mask))
            task_action = (
                {"type": "SELECT_CANDIDATE_TASK", "candidate_index": selected}
                if selected is not None
                else {"type": "WAIT"}
            )
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

    def action(
        self,
        agent_id: int,
        observation: dict[str, Any],
        action_mask: dict[str, Any],
    ) -> dict[str, Any]:
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
