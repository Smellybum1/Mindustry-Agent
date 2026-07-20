"""Milestone 6 deterministic scripted expert for bootstrap-defense-v0."""

from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass, field
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess

WIN_TICK = 8100
WAVE_TICKS = (2700, 4500, 6300)
TERMINAL_SKILLS = {"SUCCEEDED", "BLOCKED", "FAILED"}
DEFEND_COMMAND = {"type": "DEFEND", "x": 244, "y": 196, "radius": 220, "ticks": 9000}


@dataclass
class EpisodeResult:
    seed: int
    outcome: str
    tick: int
    core_health: float
    announcements: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    line_complete_tick: int = -1
    schematic_complete_tick: int = -1
    wave_clear_ticks: list[int] = field(default_factory=list)
    resources_short_replans: int = 0
    first_drill_tick: int = -1
    turrets_supplied_tick: int = -1
    copper_start: int = 250
    copper_final: int = 0
    copper_peak: int = 250
    copper_min: int = 250
    copper_boundary_in: int = 0
    copper_boundary_out: int = 0
    units_lost: int = 0


class ExpertEpisode:
    def __init__(self, env, seed: int, *, blocked_variant: bool = False):
        self.env = env
        self.seed = seed
        self.blocked_variant = blocked_variant
        reset = env.reset(root_seed=seed, agent_count=3)
        self.episode = reset.episode_id
        self.tick = reset.tick
        self.observations = reset.initial_observations
        self.step_response = None
        self.announcements: list[str] = []
        self.line_complete_tick = -1
        self.schematic_complete_tick = -1
        self.wave_clear_ticks: list[int] = []
        self.resources_short_replans = 0
        self.first_drill_tick = -1
        self.turrets_supplied_tick = -1
        self.copper_start = int(self.observations[0]["team"]["copper"])
        self.last_copper = self.copper_start
        self.copper_peak = self.copper_start
        self.copper_min = self.copper_start
        self.copper_boundary_in = 0
        self.copper_boundary_out = 0
        self.trace_records: list[dict[str, Any]] = [
            {
                "kind": "reset",
                "seed": seed,
                "agent_count": 3,
                "state_hash": reset.state_hash,
            }
        ]

    def step(self, ticks: int = 30, actions: list[dict[str, Any]] | None = None):
        request_tick = self.tick
        request_actions = copy.deepcopy(actions or [])
        response = self.env.step(
            self.episode,
            expected_tick=self.tick,
            ticks_to_advance=ticks,
            agent_actions=request_actions,
        )
        self.tick = response.tick
        self.observations = response.observations
        self.step_response = response
        self.trace_records.append(
            {
                "kind": "step",
                "expected_tick": request_tick,
                "ticks_to_advance": ticks,
                "agent_actions": request_actions,
                "state_hash": response.state_hash,
                "task_events": copy.deepcopy(response.task_events),
                "outcome": response.outcome,
            }
        )
        copper = int(response.observations[0]["team"]["copper"])
        delta = copper - self.last_copper
        if delta > 0:
            self.copper_boundary_in += delta
        elif delta < 0:
            self.copper_boundary_out -= delta
        self.last_copper = copper
        self.copper_peak = max(self.copper_peak, copper)
        self.copper_min = min(self.copper_min, copper)
        for event in response.task_events:
            line = event.get("announcement", "")
            if line:
                self.announcements.append(line)
            if event.get("act") == "COMPLETE":
                if event.get("task_type") == "BUILD_LINE":
                    self.line_complete_tick = int(event["tick"])
                elif event.get("task_type") == "BUILD_SCHEMATIC":
                    self.schematic_complete_tick = int(event["tick"])
            if event.get("act") == "BLOCKED" and event.get("reason_code") == "resources_short":
                self.resources_short_replans += 1
            if (
                self.first_drill_tick < 0
                and event.get("task_type") == "BUILD_LINE"
                and event.get("act") == "PROGRESS"
                and float(event.get("progress", 0.0)) >= 1.0 / 9.0
            ):
                self.first_drill_tick = int(event["tick"])
        return response

    @staticmethod
    def _candidate(observation: dict[str, Any], task_type: str) -> int:
        for candidate in observation["task_candidates"]:
            if candidate["task_type"] == task_type:
                return int(candidate["index"])
        raise AssertionError(f"candidate not found: {task_type}")

    def _start_opening(self) -> None:
        actions = [
            {
                "agent_id": 0,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": self._candidate(self.observations[0], "BUILD_LINE"),
                },
            },
            {
                "agent_id": 1,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": self._candidate(
                        self.observations[1], "BUILD_SCHEMATIC"
                    ),
                },
            },
            {
                "agent_id": 2,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": self._candidate(
                        self.observations[2], "HARVEST_RESOURCE"
                    ),
                },
            },
        ]
        self.step(1, actions)
        while self.tick < 2400 and (
            self.line_complete_tick < 0 or self.schematic_complete_tick < 0
        ):
            self.step(30)
        if self.line_complete_tick < 0 or self.schematic_complete_tick < 0:
            raise AssertionError(
                f"opening did not complete by {self.tick}: "
                f"line={self.line_complete_tick} schematic={self.schematic_complete_tick}"
            )

        board = self.step_response.task_board
        harvest = next(
            (task for task in board if task["task_type"] == "HARVEST_RESOURCE"), None
        )
        if harvest and harvest.get("owner_agent_id") == 2:
            self.step(
                1,
                [
                    {
                        "agent_id": 2,
                        "task_action": {
                            "type": "ABANDON",
                            "reason": "opening_economy_ready",
                        },
                    }
                ],
            )

    def _spend_for_blocked_variant(self) -> None:
        walls = [
            {"type": "BUILD", "block": "copper-wall", "tile_x": 10, "tile_y": y, "rotation": 0}
            for y in range(4, 34)
        ]
        for start in range(0, len(walls), 3):
            self._drive_commands(
                {
                    agent_id: command
                    for agent_id, command in enumerate(walls[start : start + 3])
                },
                600,
            )

    def _drive_commands(self, commands: dict[int, dict[str, Any]], limit: int = 900) -> None:
        actions = [
            {"agent_id": agent_id, "command": command}
            for agent_id, command in sorted(commands.items())
        ]
        elapsed = 0
        response = self.step(1, actions)
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

    def _bootstrap_copper(self, rounds: int = 2) -> None:
        mine_tiles = ((28, 18), (31, 18), (28, 21))
        for _ in range(rounds):
            self._drive_commands(
                {
                    agent_id: {
                        "type": "MINE",
                        "tile_x": tile[0],
                        "tile_y": tile[1],
                        "amount": 20,
                    }
                    for agent_id, tile in enumerate(mine_tiles)
                },
                600,
            )
            self._drive_commands(
                {agent_id: {"type": "DELIVER_CORE"} for agent_id in range(3)}, 300
            )

    def _build_defense(self) -> None:
        walls = (
            [(22, y) for y in range(22, 27)]
            + [(26, y) for y in range(22, 25)]
            + [(x, 22) for x in range(23, 26)]
            + [(x, 26) for x in range(23, 25)]
            + [(27, y) for y in range(21, 27) if y != 26]
        )
        builds: list[dict[str, Any]] = [
            {"type": "BUILD", "block": "copper-wall", "tile_x": x, "tile_y": y, "rotation": 0}
            for x, y in walls
        ]
        builds += [
            {"type": "BUILD", "block": "duo", "tile_x": 29, "tile_y": 23, "rotation": 1},
            {"type": "BUILD", "block": "duo", "tile_x": 29, "tile_y": 25, "rotation": 1},
        ]
        for start in range(0, len(builds), 3):
            batch = {
                agent_id: command
                for agent_id, command in enumerate(builds[start : start + 3])
            }
            self._drive_commands(batch, 600)

    def _turret_tiles(self) -> list[tuple[int, int]]:
        return sorted(
            (int(turret["tile_x"]), int(turret["tile_y"]))
            for turret in self.observations[0]["team"]["turrets"]
        )

    def _supply_all(self) -> None:
        for index, (tile_x, tile_y) in enumerate(self._turret_tiles()):
            self._supply_one(index % 3, tile_x, tile_y)

    def _supply_one(self, agent_id: int, tile_x: int, tile_y: int) -> None:
        command = {
            "type": "SUPPLY",
            "item": "copper",
            "tile_x": tile_x,
            "tile_y": tile_y,
            "amount": 15,
        }
        try:
            self._drive_commands({agent_id: command}, 300)
        except AssertionError:
            skill = self.observations[agent_id]["skill"]
            if skill["status"] != "BLOCKED" or skill["reason"] != "CORE_SHORT":
                raise
            if int(skill.get("target_stock", 0)) >= 10:
                return
            helper = (agent_id + 1) % 3
            mine_tiles = ((28, 18), (31, 18), (28, 21))
            tile = mine_tiles[helper]
            self._drive_commands(
                {
                    helper: {
                        "type": "MINE",
                        "tile_x": tile[0],
                        "tile_y": tile[1],
                        "amount": 20,
                    }
                },
                600,
            )
            self._drive_commands({helper: {"type": "DELIVER_CORE"}}, 300)
            try:
                self._drive_commands({agent_id: command}, 300)
            except AssertionError:
                skill = self.observations[agent_id]["skill"]
                if not (
                    skill["status"] == "BLOCKED"
                    and skill["reason"] == "CORE_SHORT"
                    and int(skill.get("target_stock", 0)) >= 10
                ):
                    raise

    def _start_defenders(self) -> None:
        self.step(
            1,
            [
                {"agent_id": agent_id, "command": dict(DEFEND_COMMAND)}
                for agent_id in range(3)
            ],
        )

    def _rebuild(self) -> None:
        command = {"type": "REBUILD", "x1": 20, "y1": 18, "x2": 36, "y2": 30}
        try:
            self._drive_commands({0: command}, 900)
            return
        except AssertionError:
            skill = self.observations[0]["skill"]
            if skill["status"] != "BLOCKED" or skill["reason"] != "RESOURCES_SHORT":
                raise

        mine_tiles = ((31, 18), (28, 21))
        for _ in range(3):
            self._drive_commands(
                {
                    agent_id + 1: {
                        "type": "MINE",
                        "tile_x": tile[0],
                        "tile_y": tile[1],
                        "amount": 20,
                    }
                    for agent_id, tile in enumerate(mine_tiles)
                },
                600,
            )
            self._drive_commands(
                {agent_id: {"type": "DELIVER_CORE"} for agent_id in (1, 2)}, 300
            )
            for _ in range(60):
                response = self.step(15)
                status = response.observations[0]["skill"]["status"]
                if status == "SUCCEEDED":
                    return
                if status == "FAILED":
                    break
        raise AssertionError(
            f"rebuild did not recover after legal mining: {self.observations[0]['skill']}"
        )

    def _hold_to_win(self) -> None:
        self._start_defenders()
        previous_enemies = 0
        last_refill = self.tick
        while self.tick < WIN_TICK and self.step_response.outcome == "running":
            response = self.step(min(30, WIN_TICK - self.tick))
            team = response.observations[0]["team"]
            enemies = int(team["enemy_count"])
            if previous_enemies > 0 and enemies == 0:
                self.wave_clear_ticks.append(self.tick)
                if len(self.wave_clear_ticks) < len(WAVE_TICKS):
                    self._rebuild()
                    self._supply_all()
                    self._start_defenders()
                last_refill = self.tick
            elif enemies > 0 and self.tick - last_refill >= 300:
                low = [
                    turret
                    for turret in team["turrets"]
                    if int(turret["total_ammo"]) <= 6
                ]
                if low and int(team["copper"]) >= 5:
                    turret = sorted(low, key=lambda value: int(value["id"]))[0]
                    self._supply_one(
                        0, int(turret["tile_x"]), int(turret["tile_y"])
                    )
                    self.step(1, [{"agent_id": 0, "command": dict(DEFEND_COMMAND)}])
                    last_refill = self.tick
            previous_enemies = enemies

    def run(self) -> EpisodeResult:
        if self.blocked_variant:
            self._spend_for_blocked_variant()
        self._start_opening()
        if self.blocked_variant and self.resources_short_replans == 0:
            raise AssertionError("insufficient-copper variant emitted no resources_short block")
        self._bootstrap_copper(rounds=4 if self.blocked_variant else 2)
        self._build_defense()
        self._supply_all()
        self.turrets_supplied_tick = self.tick
        self._hold_to_win()
        response = self.step_response
        team = response.observations[0]["team"]
        return EpisodeResult(
            seed=self.seed,
            outcome=response.outcome,
            tick=response.tick,
            core_health=float(team["core_health"]),
            announcements=self.announcements,
            metrics=response.coordination_metrics,
            line_complete_tick=self.line_complete_tick,
            schematic_complete_tick=self.schematic_complete_tick,
            wave_clear_ticks=self.wave_clear_ticks,
            resources_short_replans=self.resources_short_replans,
            first_drill_tick=self.first_drill_tick,
            turrets_supplied_tick=self.turrets_supplied_tick,
            copper_start=self.copper_start,
            copper_final=int(team["copper"]),
            copper_peak=self.copper_peak,
            copper_min=self.copper_min,
            copper_boundary_in=self.copper_boundary_in,
            copper_boundary_out=self.copper_boundary_out,
            units_lost=sum(bool(observation["unit"]["dead"]) for observation in self.observations),
        )


def run_episode(env, seed: int, *, blocked_variant: bool = False) -> EpisodeResult:
    return ExpertEpisode(env, seed, blocked_variant=blocked_variant).run()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M6 scripted expert demonstration")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    parser.add_argument("--blocked-variant", action="store_true")
    args = parser.parse_args(argv)

    try:
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            env.handshake()
            result = run_episode(env, args.seed, blocked_variant=args.blocked_variant)
    except Exception as exc:
        print(f"SCRIPTED-DEMO FAIL: {exc}", file=sys.stderr)
        return 1

    print("announcement transcript:")
    for line in result.announcements:
        print(f"  {line}")
    print(
        f"outcome={result.outcome} tick={result.tick} core_health={result.core_health:.0f} "
        f"line={result.line_complete_tick} schematic={result.schematic_complete_tick} "
        f"wave_clears={result.wave_clear_ticks} blocked_replans={result.resources_short_replans}"
    )
    if result.outcome != "win" or result.tick != WIN_TICK:
        print("SCRIPTED-DEMO FAIL: expert did not reach the tick-8100 win", file=sys.stderr)
        return 1
    print("SCRIPTED-DEMO OK: deterministic three-agent expert survived all waves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
