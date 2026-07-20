"""Primary M7.3 expert over the public candidate/mask/task-action seam."""

from __future__ import annotations

from typing import Any

from mindustry_agents.policies import GreedyUtilityPolicy
from mindustry_agents.tools.expert_common import EpisodeResult, ScenarioLayout

TERMINAL_SKILLS = {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}
EXPERT_TURRET_TARGET_AMMO = 30


class UtilityExpertEpisode:
    """Run the pure greedy selector over server-generated candidate utilities."""

    def __init__(self, env, seed: int, *, blocked_variant: bool = False):
        self.env = env
        self.seed = seed
        self.blocked_variant = blocked_variant
        reset = env.reset(root_seed=seed, agent_count=3)
        self.layout = ScenarioLayout(reset.metadata)
        self.episode = reset.episode_id
        self.tick = reset.tick
        self.observations = reset.initial_observations
        self.action_masks = reset.action_masks
        self.policy = GreedyUtilityPolicy()
        self.announcements: list[str] = []
        self.line_complete_tick = -1
        self.schematic_complete_tick = -1
        self.first_drill_tick = -1
        self.turrets_supplied_tick = -1
        self.wave_clear_ticks: list[int] = []
        self.previous_enemies = 0
        self.copper_start = int(self.observations[0]["team"]["copper"])
        self.last_copper = self.copper_start
        self.copper_peak = self.copper_start
        self.copper_min = self.copper_start
        self.copper_boundary_in = 0
        self.copper_boundary_out = 0
        self.response = None

    def step(self, ticks: int = 30, actions=None):
        response = self.env.step(
            self.episode,
            expected_tick=self.tick,
            ticks_to_advance=ticks,
            agent_actions=actions or [],
        )
        self.tick = response.tick
        self.observations = response.observations
        self.action_masks = response.action_masks
        self.response = response
        self._record_events(response.task_events)
        self._record_boundary(response)
        return response

    def _record_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            announcement = event.get("announcement", "")
            if announcement:
                self.announcements.append(announcement)
            if event.get("act") == "COMPLETE":
                if self.line_complete_tick < 0 and event.get("task_id", "").startswith(
                    "T2:build:"
                ):
                    self.line_complete_tick = int(event["tick"])
                elif self.schematic_complete_tick < 0 and event.get(
                    "task_id", ""
                ).startswith("T3:build:"):
                    self.schematic_complete_tick = int(event["tick"])
            if (
                self.first_drill_tick < 0
                and event.get("task_id", "").startswith("T2:build:")
                and event.get("act") == "PROGRESS"
                and float(event.get("progress", 0.0)) >= self.layout.first_drill_progress
            ):
                self.first_drill_tick = int(event["tick"])

    def _record_boundary(self, response) -> None:
        team = response.observations[0]["team"]
        copper = int(team["copper"])
        delta = copper - self.last_copper
        if delta > 0:
            self.copper_boundary_in += delta
        elif delta < 0:
            self.copper_boundary_out -= delta
        self.last_copper = copper
        self.copper_peak = max(self.copper_peak, copper)
        self.copper_min = min(self.copper_min, copper)

        enemies = int(team["enemy_count"])
        if self.previous_enemies > 0 and enemies == 0:
            self.wave_clear_ticks.append(response.tick)
        self.previous_enemies = enemies

        turrets = team["turrets"]
        objective_ammo = int(
            self.layout.metadata["objectives"]["SUPPLY_TURRET"]["threshold"]
        )
        target_ammo = max(objective_ammo, EXPERT_TURRET_TARGET_AMMO)
        if (
            self.turrets_supplied_tick < 0
            and len(turrets) >= 4
            and all(int(turret["total_ammo"]) >= target_ammo for turret in turrets)
        ):
            self.turrets_supplied_tick = response.tick

    def _drive_commands(self, commands: dict[int, dict[str, Any]], limit: int = 600) -> None:
        response = self.step(
            1,
            [
                {"agent_id": agent_id, "command": command}
                for agent_id, command in sorted(commands.items())
            ],
        )
        elapsed = 0
        while elapsed < limit:
            pending = [
                agent_id
                for agent_id in commands
                if response.observations[agent_id]["skill"]["status"]
                not in TERMINAL_SKILLS
            ]
            if not pending:
                break
            advance = min(15, limit - elapsed)
            response = self.step(advance)
            elapsed += advance
        for agent_id, command in commands.items():
            skill = response.observations[agent_id]["skill"]
            if skill["status"] != "SUCCEEDED":
                raise AssertionError(
                    f"agent {agent_id} {command} failed at tick {self.tick}: {skill}"
                )

    def _spend_for_blocked_variant(self) -> None:
        core_x, core_y = self.layout.core_tile
        walls = [
            {
                "type": "BUILD",
                "block": "copper-wall",
                "tile_x": max(1, core_x - 22),
                "tile_y": core_y - 20 + offset,
                "rotation": 0,
            }
            for offset in range(18)
        ]
        for start in range(0, len(walls), 3):
            self._drive_commands(
                {
                    agent_id: command
                    for agent_id, command in enumerate(walls[start : start + 3])
                }
            )

    def _policy_actions(self) -> list[dict[str, Any]]:
        return [
            self.policy.action(
                agent_id,
                self.observations[agent_id],
                self.action_masks[agent_id],
            )
            for agent_id in range(len(self.observations))
        ]

    def run(self) -> EpisodeResult:
        if self.blocked_variant:
            self._spend_for_blocked_variant()
        while self.tick < self.layout.tick_cap:
            boundary = (
                self.layout.win_tick
                if self.tick < self.layout.win_tick
                else self.layout.tick_cap
            )
            response = self.step(
                min(30, boundary - self.tick), self._policy_actions()
            )
            if response.outcome != "running":
                break

        if self.response is None:
            raise AssertionError("utility expert produced no step response")
        response = self.response
        team = response.observations[0]["team"]
        metrics = dict(response.coordination_metrics)
        metrics["policy_name"] = "greedy-utility-expert-v1"
        replans = int(metrics.get("resource_replans", 0))
        if self.blocked_variant and replans <= 0:
            raise AssertionError("blocked variant performed no legal resource replan")
        if response.outcome != "win":
            raise AssertionError(
                f"utility expert failed seed {self.seed}: {response.outcome} at {response.tick}"
            )

        return EpisodeResult(
            seed=self.seed,
            outcome=response.outcome,
            tick=response.tick,
            core_health=float(team["core_health"]),
            announcements=self.announcements,
            metrics=metrics,
            line_complete_tick=self.line_complete_tick,
            schematic_complete_tick=self.schematic_complete_tick,
            wave_clear_ticks=self.wave_clear_ticks,
            resources_short_replans=replans,
            first_drill_tick=self.first_drill_tick,
            turrets_supplied_tick=self.turrets_supplied_tick,
            copper_start=self.copper_start,
            copper_final=int(team["copper"]),
            copper_peak=self.copper_peak,
            copper_min=self.copper_min,
            copper_boundary_in=self.copper_boundary_in,
            copper_boundary_out=self.copper_boundary_out,
            units_lost=sum(
                bool(observation["unit"]["dead"])
                for observation in self.observations
            ),
            win_tick=self.layout.win_tick,
        )


def run_utility_episode(env, seed: int, *, blocked_variant: bool = False) -> EpisodeResult:
    return UtilityExpertEpisode(env, seed, blocked_variant=blocked_variant).run()
