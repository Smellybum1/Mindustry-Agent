"""CPU-only adversarial gate for ADR-0070's individual reward."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo_reward import (
    INDIVIDUAL_COMPONENT_KEY,
    IPPOReward,
)
from mindustry_agents.training.ippo_ppo import load_ippo_v1_config
from mindustry_agents.training.reward import RewardAuditError

CASES = (
    "m9-own-idle-cap",
    "m9-own-idle-unavailable-zero",
    "m9-own-idle-seat-isolation",
    "m9-own-idle-chunk-invariance",
    "m9-own-idle-counter-rollback",
    "m9-own-idle-busywork-ordering",
)


def _team(tick: int) -> dict[str, Any]:
    return {
        "tick": tick,
        "line_operational": False,
        "defense_readiness": 0.0,
        "enemy_count": 0,
    }


def _metrics(
    idle: list[int],
    *,
    unavailable: list[int] | None = None,
    duplicate: int = 0,
    announcements: int = 0,
) -> dict[str, Any]:
    unavailable = unavailable or [0, 0, 0]
    return {
        "agent_ticks": 27000,
        "idle_agent_ticks": sum(idle),
        "idle_agent_ticks_by_agent": idle,
        "unavailable_agent_ticks": sum(unavailable),
        "unavailable_agent_ticks_by_agent": unavailable,
        "duplicate_work_incidents": duplicate,
        "announced_messages": announcements,
    }


def _reward(config: dict[str, Any]) -> IPPOReward:
    return IPPOReward(
        quality_reward=config["team_quality_reward"],
        individual_shaping=config["individual_shaping"],
    )


def _observe(
    reward: IPPOReward,
    previous_tick: int,
    tick: int,
    metrics: dict[str, Any],
    *,
    task_events: list[dict[str, Any]] | None = None,
):
    return reward.observe(
        _team(previous_tick),
        _team(tick),
        advanced_ticks=tick - previous_tick,
        tick_cap=9000,
        coordination_metrics=metrics,
        task_events=task_events,
    )


def run_case(case: str, config: dict[str, Any]) -> dict[str, Any]:
    if case not in CASES:
        raise ValueError(f"unknown M9 reward adversary: {case}")
    evidence: dict[str, Any] = {"case": case}
    if case == "m9-own-idle-cap":
        reward = _reward(config)
        first = _observe(reward, 0, 5000, _metrics([5000, 0, 0]))
        after = _observe(reward, 5000, 5001, _metrics([5001, 0, 0]))
        passed = (
            first.individual_components == (-1.0, 0.0, 0.0)
            and after.individual_components == (0.0, 0.0, 0.0)
        )
        evidence["components"] = [
            first.individual_components,
            after.individual_components,
        ]
    elif case == "m9-own-idle-unavailable-zero":
        result = _observe(
            _reward(config),
            0,
            100,
            _metrics([0, 0, 0], unavailable=[100, 0, 0]),
        )
        passed = result.individual_components == (0.0, 0.0, 0.0)
        evidence["components"] = result.individual_components
    elif case == "m9-own-idle-seat-isolation":
        result = _observe(
            _reward(config), 0, 60, _metrics([10, 20, 30])
        )
        passed = result.individual_components == (-0.0025, -0.005, -0.0075)
        evidence["components"] = result.individual_components
    elif case == "m9-own-idle-chunk-invariance":
        single = _observe(
            _reward(config), 0, 300, _metrics([300, 180, 60])
        )
        chunked_reward = _reward(config)
        chunked = None
        for start, end, scale in ((0, 100, 1), (100, 200, 2), (200, 300, 3)):
            chunked = _observe(
                chunked_reward,
                start,
                end,
                _metrics([100 * scale, 60 * scale, 20 * scale]),
            )
        passed = (
            chunked is not None
            and single.own_idle_penalty_totals
            == chunked.own_idle_penalty_totals
        )
        evidence["single_totals"] = single.own_idle_penalty_totals
        evidence["chunked_totals"] = chunked.own_idle_penalty_totals
    elif case == "m9-own-idle-counter-rollback":
        reward = _reward(config)
        _observe(reward, 0, 10, _metrics([10, 10, 10]))
        try:
            _observe(reward, 10, 20, _metrics([9, 10, 10]))
        except RewardAuditError as error:
            passed = "rolled back" in str(error)
            evidence["error"] = str(error)
        else:
            passed = False
    else:
        honest = _observe(
            _reward(config), 0, 9000, _metrics([9000, 9000, 9000])
        )
        abandonments = [
            {
                "act": "ABANDON",
                "agent_id": index % 3,
                "reason_code": "blocked_replan",
            }
            for index in range(20)
        ]
        busy = _observe(
            _reward(config),
            0,
            9000,
            _metrics([0, 0, 0], duplicate=140),
            task_events=abandonments,
        )
        passed = (
            all(
                busy.reward_by_agent[index] <= honest.reward_by_agent[index]
                for index in range(3)
            )
            and busy.team.quality_counters["duplicate_work_incidents"] > 0
            and busy.team.quality_penalty_totals[
                "reward.penalty.team_abandonment"
            ]
            > 0
        )
        evidence["honest_reward_by_agent"] = honest.reward_by_agent
        evidence["busy_reward_by_agent"] = busy.reward_by_agent
        evidence["busy_quality_counters"] = busy.team.quality_counters
    return {
        "schema": "m9_ippo_reward_adversary_case_v1",
        "reward_schema": "ippo_reward_v1",
        "individual_component": INDIVIDUAL_COMPONENT_KEY,
        **evidence,
        "pass": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=repo_root() / "configs/training/m9-ippo-v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "runs/m9-ippo-reward-adversaries.json",
    )
    args = parser.parse_args()
    config = load_ippo_v1_config(args.config)
    cases = [run_case(case, config) for case in CASES]
    report = {
        "schema": "m9_ippo_reward_adversary_report_v1",
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "all_passed": all(case["pass"] for case in cases),
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["all_passed"]:
        raise AssertionError("M9 IPPO reward adversary gate failed")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
