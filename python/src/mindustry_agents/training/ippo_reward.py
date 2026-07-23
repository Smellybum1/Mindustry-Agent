"""Audited M9 all-seat reward accounting.

The existing selector reward remains the shared team signal.  This module adds
only ADR-0070's bounded, per-seat available-idle shaping and keeps every value
separate in rollout evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mindustry_agents.training.ippo import AGENT_COUNT
from mindustry_agents.training.reward import (
    RewardAuditError,
    RewardBreakdown,
    SelectorReward,
)

IPPO_REWARD_SCHEMA = "ippo_reward_v1"
INDIVIDUAL_REWARD_SCHEMA = "own_available_idle_ticks_v1"
INDIVIDUAL_COMPONENT_KEY = "reward.agent.own_available_idle_ticks"


@dataclass(frozen=True)
class IPPORewardBreakdown:
    """One boundary's shared and private reward values."""

    schema: str
    team: RewardBreakdown
    individual_components: tuple[float, float, float]
    reward_by_agent: tuple[float, float, float]
    own_idle_counters: tuple[int, int, int]
    own_idle_penalty_totals: tuple[float, float, float]


@dataclass
class IPPOReward:
    """Per-episode shared team reward plus capped per-seat shaping."""

    quality_reward: dict[str, float]
    individual_shaping: dict[str, Any]
    team: SelectorReward = field(init=False)
    prior_own_idle_counters: list[int] = field(
        default_factory=lambda: [0] * AGENT_COUNT
    )
    own_idle_penalty_totals: list[float] = field(
        default_factory=lambda: [0.0] * AGENT_COUNT
    )

    def __post_init__(self) -> None:
        if self.individual_shaping.get("schema") != INDIVIDUAL_REWARD_SCHEMA:
            raise RewardAuditError("M9 individual reward schema is invalid")
        if (
            self.individual_shaping.get("reward_key")
            != INDIVIDUAL_COMPONENT_KEY
        ):
            raise RewardAuditError("M9 individual reward key is invalid")
        if self.individual_shaping.get("unavailable_ticks_charged") is not False:
            raise RewardAuditError("M9 unavailable ticks must not be charged")
        cost = self.cost_per_tick
        cap = self.per_agent_cap
        if cost < 0.0 or cap < 0.0:
            raise RewardAuditError("M9 individual idle cost/cap is invalid")
        self.team = SelectorReward(quality_reward=self.quality_reward)

    @property
    def cost_per_tick(self) -> float:
        return float(self.individual_shaping["cost_per_tick"])

    @property
    def per_agent_cap(self) -> float:
        return float(self.individual_shaping["per_agent_episode_cap"])

    def observe(
        self,
        previous_team: dict[str, Any],
        current_team: dict[str, Any],
        *,
        advanced_ticks: int,
        tick_cap: int,
        outcome: str = "running",
        task_events: list[dict[str, Any]] | None = None,
        game_events: list[dict[str, Any]] | None = None,
        boundary_reasons: list[str] | tuple[str, ...] = (),
        coordination_metrics: dict[str, Any] | None,
    ) -> IPPORewardBreakdown:
        """Observe one authoritative boundary without cross-seat attribution."""

        own_idle, unavailable = self._validated_agent_counters(
            coordination_metrics, tick_cap
        )
        # The all-seat runtime rejects mask-invalid actions before submission.
        # Legacy learned-seat-only invalid/abandonment components consequently
        # stay zero; team abandonment is handled by selector_reward_v2.
        team = self.team.observe(
            previous_team,
            current_team,
            advanced_ticks=advanced_ticks,
            tick_cap=tick_cap,
            outcome=outcome,
            task_events=task_events,
            game_events=game_events,
            boundary_reasons=boundary_reasons,
            raw_action_valid=True,
            environment_mask_valid=True,
            coordination_metrics=coordination_metrics,
        )

        individual = []
        for agent_id, counter in enumerate(own_idle):
            prior_total = self.own_idle_penalty_totals[agent_id]
            target_total = min(
                counter * self.cost_per_tick,
                self.per_agent_cap,
            )
            charge = max(0.0, target_total - prior_total)
            self.own_idle_penalty_totals[agent_id] = target_total
            individual.append(-charge)
        self.prior_own_idle_counters = list(own_idle)
        rewards = tuple(team.total + value for value in individual)
        return IPPORewardBreakdown(
            schema=IPPO_REWARD_SCHEMA,
            team=team,
            individual_components=tuple(individual),
            reward_by_agent=rewards,
            own_idle_counters=own_idle,
            own_idle_penalty_totals=tuple(self.own_idle_penalty_totals),
        )

    def _validated_agent_counters(
        self, metrics: dict[str, Any] | None, tick_cap: int
    ) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        if metrics is None:
            raise RewardAuditError("M9 reward requires coordination metrics")
        try:
            own_idle_raw = metrics["idle_agent_ticks_by_agent"]
            unavailable_raw = metrics["unavailable_agent_ticks_by_agent"]
        except KeyError as error:
            raise RewardAuditError(
                "M9 per-seat coordination metrics are incomplete"
            ) from error
        if (
            not isinstance(own_idle_raw, list)
            or not isinstance(unavailable_raw, list)
            or len(own_idle_raw) != AGENT_COUNT
            or len(unavailable_raw) != AGENT_COUNT
        ):
            raise RewardAuditError("M9 per-seat counters must contain three seats")
        if any(type(value) is not int for value in own_idle_raw + unavailable_raw):
            raise RewardAuditError("M9 per-seat counters must be integers")
        own_idle = tuple(own_idle_raw)
        unavailable = tuple(unavailable_raw)
        if any(
            value < 0 or value > tick_cap
            for value in own_idle + unavailable
        ):
            raise RewardAuditError("M9 per-seat counters are outside episode bounds")
        if any(
            value < prior
            for value, prior in zip(own_idle, self.prior_own_idle_counters)
        ):
            raise RewardAuditError("M9 per-seat idle counter rolled back")
        if sum(own_idle) != int(metrics.get("idle_agent_ticks", -1)):
            raise RewardAuditError("M9 per-seat idle counters do not reconcile")
        if sum(unavailable) != int(metrics.get("unavailable_agent_ticks", -1)):
            raise RewardAuditError(
                "M9 per-seat unavailable counters do not reconcile"
            )
        return own_idle, unavailable
