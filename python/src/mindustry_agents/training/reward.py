"""Audited, framework-neutral ``selector_reward_v1`` accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REWARD_SCHEMA = "selector_reward_v1"
COMPONENT_KEYS = (
    "reward.team.milestone_highwater",
    "reward.team.terminal_outcome",
    "reward.team.unresolved_tick_cost",
    "reward.penalty.invalid_action",
    "reward.penalty.abandonment_liability",
)
MILESTONE_VALUES = {
    "line_operational": 1.0,
    "defense_ready": 1.0,
    "wave_clear_1": 2.0,
    "wave_clear_2": 2.0,
    "wave_clear_3": 2.0,
}
ABANDON_EXCLUSIONS = (
    "wave",
    "readiness",
    "death",
    "lease",
    "human",
    "terminal",
    "cleanup",
)


class RewardAuditError(ValueError):
    """Raised when reward attribution cannot be audited safely."""


@dataclass(frozen=True)
class RewardBreakdown:
    """One transition's separately stored reward components and evidence."""

    components: dict[str, float]
    milestone_ids: tuple[str, ...]
    charged_ticks: int
    invalid_action_count: int
    abandonment_reason_counts: dict[str, int]

    @property
    def total(self) -> float:
        return sum(self.components.values())


@dataclass
class SelectorReward:
    """Per-episode monotonic reward state for the learned selector seat."""

    credited_milestones: set[str] = field(default_factory=set)
    spawned_waves: set[int] = field(default_factory=set)
    learned_task_ids: set[str] = field(default_factory=set)
    terminal_emitted: bool = False
    invalid_action_count: int = 0
    abandonment_count: int = 0
    charged_ticks: int = 0
    abandonment_reason_counts: dict[str, int] = field(default_factory=dict)

    def record_learned_selection(self, task_id: str) -> None:
        if task_id:
            self.learned_task_ids.add(task_id)

    def observe(
        self,
        previous_team: dict[str, Any],
        current_team: dict[str, Any],
        *,
        advanced_ticks: int,
        tick_cap: int,
        outcome: str = "running",
        task_events: list[dict[str, Any]] | None = None,
        boundary_reasons: list[str] | tuple[str, ...] = (),
        raw_action_valid: bool = True,
        environment_mask_valid: bool = True,
    ) -> RewardBreakdown:
        if advanced_ticks < 0 or tick_cap <= 0:
            raise RewardAuditError("advanced_ticks and tick_cap are invalid")
        if not environment_mask_valid:
            raise RewardAuditError("environment mask/boundary mismatch")
        components = {key: 0.0 for key in COMPONENT_KEYS}
        emitted: list[str] = []
        reasons = set(boundary_reasons)

        if current_team.get("line_operational", False):
            self._milestone("line_operational", emitted)
        if float(current_team.get("defense_readiness", 0.0)) >= 1.0:
            self._milestone("defense_ready", emitted)

        previous_enemies = int(previous_team.get("enemy_count", 0))
        current_enemies = int(current_team.get("enemy_count", 0))
        if "wave_spawn" in reasons and previous_enemies == 0 and current_enemies > 0:
            wave = min(3, len(self.spawned_waves) + 1)
            self.spawned_waves.add(wave)
        pending_waves = sorted(
            wave
            for wave in self.spawned_waves
            if f"wave_clear_{wave}" not in self.credited_milestones
        )
        if (
            "wave_clear" in reasons
            and previous_enemies > 0
            and current_enemies == 0
            and pending_waves
        ):
            self._milestone(f"wave_clear_{pending_waves[0]}", emitted)
        components["reward.team.milestone_highwater"] = sum(
            MILESTONE_VALUES[item] for item in emitted
        )

        charged = 0
        if len(self.credited_milestones) < len(MILESTONE_VALUES):
            charged += advanced_ticks
        if outcome in {"loss", "truncated"}:
            current_tick = int(current_team.get("tick", 0))
            charged += max(0, tick_cap - current_tick)
        self.charged_ticks += charged
        components["reward.team.unresolved_tick_cost"] = -0.0002 * charged

        if outcome != "running":
            if self.terminal_emitted:
                raise RewardAuditError("terminal reward emitted more than once")
            if outcome not in {"win", "loss", "truncated"}:
                raise RewardAuditError(f"unknown terminal outcome: {outcome}")
            self.terminal_emitted = True
            components["reward.team.terminal_outcome"] = (
                10.0 if outcome == "win" else -10.0
            )

        if not raw_action_valid and self.invalid_action_count < 4:
            self.invalid_action_count += 1
            components["reward.penalty.invalid_action"] = -0.25

        for event in task_events or []:
            if event.get("act") != "ABANDON" or int(event.get("agent_id", -1)) != 0:
                continue
            if str(event.get("task_id", "")) not in self.learned_task_ids:
                continue
            reason = str(event.get("reason_code", "")).lower()
            self.abandonment_reason_counts[reason] = (
                self.abandonment_reason_counts.get(reason, 0) + 1
            )
            if any(token in reason for token in ABANDON_EXCLUSIONS):
                continue
            if self.abandonment_count < 10:
                self.abandonment_count += 1
                components["reward.penalty.abandonment_liability"] -= 0.05

        return RewardBreakdown(
            components=components,
            milestone_ids=tuple(emitted),
            charged_ticks=charged,
            invalid_action_count=self.invalid_action_count,
            abandonment_reason_counts=dict(sorted(self.abandonment_reason_counts.items())),
        )

    def _milestone(self, milestone: str, emitted: list[str]) -> None:
        if milestone not in MILESTONE_VALUES:
            raise RewardAuditError(f"unknown milestone: {milestone}")
        if milestone not in self.credited_milestones:
            self.credited_milestones.add(milestone)
            emitted.append(milestone)
