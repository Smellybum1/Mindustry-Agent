"""Adaptive expert over the public candidate/mask/task-action seam."""

from __future__ import annotations

from typing import Any

from mindustry_agents.policies import GreedyUtilityPolicy
from mindustry_agents.tools.expert_common import EpisodeResult, ScenarioLayout

TERMINAL_SKILLS = {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}


class UtilityExpertEpisode:
    """Run the pure greedy selector over server-generated candidate utilities."""

    def __init__(
        self,
        env,
        seed: int,
        *,
        blocked_variant: bool = False,
        scenario_id: str = "bootstrap-defense-v0",
        scenario_version: int = 0,
        require_win: bool = True,
        policy: Any | None = None,
        policy_name: str = "adaptive-v1",
    ):
        self.env = env
        self.seed = seed
        self.blocked_variant = blocked_variant
        self.require_win = require_win
        reset = env.reset(
            root_seed=seed,
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            agent_count=3,
        )
        self.layout = ScenarioLayout(reset.metadata)
        self.episode = reset.episode_id
        self.tick = reset.tick
        self.observations = reset.initial_observations
        self.action_masks = reset.action_masks
        self.policy = policy or GreedyUtilityPolicy()
        self.policy_name = policy_name
        self.announcements: list[str] = []
        self.task_events: list[dict[str, Any]] = []
        self.game_events: list[dict[str, Any]] = []
        self.agent_loss_ticks: dict[int, int] = {}
        self._previous_dead = [
            bool(observation["unit"]["dead"]) for observation in self.observations
        ]
        self.line_complete_tick = -1
        self.schematic_complete_tick = -1
        self.first_drill_tick = -1
        self.turrets_supplied_tick = -1
        self.defense_ready_tick = -1
        self.decision_wakeups = 0
        self.decision_reasons: dict[str, int] = {}
        self.wave_clear_ticks: list[int] = []
        self.previous_enemies = 0
        self.copper_start = int(self.observations[0]["team"]["copper"])
        self.last_copper = self.copper_start
        self.copper_peak = self.copper_start
        self.copper_min = self.copper_start
        self.copper_boundary_in = 0
        self.copper_boundary_out = 0
        self.response = None

    def step(self, ticks: int = 30, actions=None, *, event_driven: bool = False):
        response = self.env.step(
            self.episode,
            expected_tick=self.tick,
            ticks_to_advance=ticks,
            agent_actions=actions or [],
            stop_on_decision_event=event_driven,
        )
        self.tick = response.tick
        self.observations = response.observations
        self.action_masks = response.action_masks
        self.response = response
        self.policy.observe_action_results(response.action_results)
        self.task_events.extend(response.task_events)
        self.game_events.extend(response.game_events)
        self._record_events(response.task_events)
        self._record_boundary(response)
        boundary = response.decision_boundary
        if boundary.get("triggered", False):
            self.decision_wakeups += 1
            for reason in boundary.get("reasons", []):
                key = str(reason)
                self.decision_reasons[key] = self.decision_reasons.get(key, 0) + 1
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
        for event in response.game_events:
            if event.get("type") == "unit_destroy" and int(
                event.get("agent_id", -1)
            ) >= 0:
                self.agent_loss_ticks[int(event["agent_id"])] = int(event["tick"])
        for agent_id, observation in enumerate(response.observations):
            dead = bool(observation["unit"]["dead"])
            if (
                dead
                and not self._previous_dead[agent_id]
                and agent_id not in self.agent_loss_ticks
            ):
                self.agent_loss_ticks[agent_id] = response.tick
            self._previous_dead[agent_id] = dead

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
        target_ammo = int(team.get("target_ammo_per_turret", 0))
        if (
            self.turrets_supplied_tick < 0
            and float(team.get("defense_turret_coverage", 0.0)) >= 1.0
            and all(int(turret["total_ammo"]) >= target_ammo for turret in turrets)
        ):
            self.turrets_supplied_tick = response.tick
        if self.defense_ready_tick < 0 and float(team.get("defense_readiness", 0.0)) >= 1.0:
            self.defense_ready_tick = response.tick

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
        wall_tiles = (
            [(core_x - 2, y) for y in range(core_y - 2, core_y + 3)]
            + [(core_x + 2, y) for y in range(core_y - 2, core_y + 1)]
            + [(x, core_y - 2) for x in range(core_x - 1, core_x + 2)]
            + [(x, core_y + 2) for x in range(core_x - 1, core_x + 1)]
            + [(core_x + 3, y) for y in range(core_y - 3, core_y + 2)]
            + [(core_x + 4, core_y)]
        )
        walls = [
            {
                "type": "BUILD",
                "block": "copper-wall",
                "tile_x": tile_x,
                "tile_y": tile_y,
                "rotation": 0,
            }
            for tile_x, tile_y in wall_tiles
        ]
        for start in range(0, len(walls), 3):
            self._drive_commands(
                {
                    agent_id: command
                    for agent_id, command in enumerate(walls[start : start + 3])
                }
            )

        self._drive_commands(
            {
                agent_id: {
                    "type": "NAVIGATE",
                    "x": core_x * self.layout.tile_size + self.layout.tile_size / 2,
                    "y": core_y * self.layout.tile_size + self.layout.tile_size / 2,
                    "tolerance": self.layout.tile_size,
                }
                for agent_id in range(3)
            }
        )

        def candidate(agent_id: int, task_type: str) -> int:
            for item in self.observations[agent_id]["task_candidates"]:
                if item["task_type"] == task_type:
                    return int(item["index"])
            raise AssertionError(f"blocked fixture missing {task_type} candidate")

        started = self.step(
            1,
            [
                {
                    "agent_id": 0,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": candidate(0, "BUILD_LINE"),
                    },
                },
                {
                    "agent_id": 1,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": candidate(1, "BUILD_SCHEMATIC"),
                    },
                },
            ],
        )
        if not all(result.get("accepted", False) for result in started.action_results):
            raise AssertionError(
                f"blocked fixture could not reserve both plans: {started.action_results}"
            )
        # The two accepted plans reserve exactly 131 copper against the remaining
        # 136. These legal walls are built after reservation and consume 18,
        # outpacing the new line's startup trickle and forcing one plan through
        # the real RESOURCES_SHORT -> reselection path.
        for offset in range(-2, 1):
            self._drive_commands(
                {
                    2: {
                        "type": "BUILD",
                        "block": "copper-wall",
                        "tile_x": core_x - 3,
                        "tile_y": core_y + offset,
                        "rotation": 0,
                    }
                }
            )

    def _policy_actions(self) -> list[dict[str, Any]]:
        return self.policy.actions(self.observations, self.action_masks)

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
                min(30, boundary - self.tick),
                self._policy_actions(),
                event_driven=True,
            )
            if response.outcome != "running":
                break

        if self.response is None:
            raise AssertionError("utility expert produced no step response")
        response = self.response
        team = response.observations[0]["team"]
        metrics = dict(response.coordination_metrics)
        metrics["policy_name"] = self.policy_name
        metrics["decision_wakeups"] = self.decision_wakeups
        metrics["decision_wakeup_reasons"] = dict(sorted(self.decision_reasons.items()))
        replans = int(metrics.get("resource_replans", 0))
        if self.blocked_variant and replans <= 0:
            raise AssertionError("blocked variant performed no legal resource replan")
        if self.require_win and response.outcome != "win":
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
            defense_ready_tick=self.defense_ready_tick,
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
            task_events=self.task_events,
            game_events=self.game_events,
            agent_loss_ticks=self.agent_loss_ticks,
        )


def run_utility_episode(
    env,
    seed: int,
    *,
    blocked_variant: bool = False,
    scenario_id: str = "bootstrap-defense-v0",
    scenario_version: int = 0,
    require_win: bool = True,
    policy: Any | None = None,
    policy_name: str = "adaptive-v1",
) -> EpisodeResult:
    return UtilityExpertEpisode(
        env,
        seed,
        blocked_variant=blocked_variant,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        require_win=require_win,
        policy=policy,
        policy_name=policy_name,
    ).run()
