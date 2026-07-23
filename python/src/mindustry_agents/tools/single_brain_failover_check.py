"""Live public single-brain death-failover acceptance check."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.ppo_selector import (
    LEARNED_SEAT_FAILOVER_SCHEMA,
    LEARNED_SEAT_HISTORY_SCHEMA,
    REWARD_SCHEMA,
    _action_generator,
    _configure_torch,
    _learned_seat_failover,
    _learned_seat_history,
    _partner_intent_duplication_risk,
    expected_control_schema,
    expected_feature_schema,
    rollout_episode,
)
from mindustry_agents.training.model import build_selector_model
from mindustry_agents.training.promotion import (
    GREEDY_MIXED,
    rollout_control_episode,
)


PUBLIC_FAILOVER_SEED = 11_307_756_240
DEFAULT_CONFIG = Path(
    "configs/training/m8-selector-v47-single-brain-death-failover.json"
)
EXPECTED_TRANSFERS = [
    {
        "from_agent_id": 0,
        "reason": "active_agent_dead",
        "tick": 2738,
        "to_agent_id": 1,
    },
    {
        "from_agent_id": 1,
        "reason": "active_agent_dead",
        "tick": 4462,
        "to_agent_id": 2,
    },
]


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("candidate_version") not in ("v47", "v48"):
        raise ValueError("single-brain check requires the exact V47 or V48 config")
    return config


def _validate_result(
    rollout,
    *,
    expected_history: bool,
) -> dict[str, Any]:
    metrics = rollout.coordination_metrics
    transfers = metrics.get("learned_seat_transfers")
    if metrics.get("learned_seat_failover_schema") != LEARNED_SEAT_FAILOVER_SCHEMA:
        raise AssertionError("single-brain failover schema telemetry is missing")
    if metrics.get("maximum_simultaneous_learned_seats") != 1:
        raise AssertionError("more than one learned seat was active")
    if transfers != EXPECTED_TRANSFERS:
        raise AssertionError(
            f"death-only transfer trace drifted: {transfers!r}"
        )
    if (
        metrics.get("learned_seat_initial_agent_id") != 0
        or metrics.get("learned_seat_final_agent_id") != 2
        or metrics.get("learned_seat_transfer_count") != len(EXPECTED_TRANSFERS)
    ):
        raise AssertionError("single-brain authority telemetry is inconsistent")
    if rollout.outcome != "win" or rollout.tick != 9000:
        raise AssertionError(
            f"public failover survival drifted: {rollout.outcome}@{rollout.tick}"
        )
    trace_transfers = [
        item["learned_seat_transfer"]
        for item in rollout.trace
        if "learned_seat_transfer" in item
    ]
    if trace_transfers != EXPECTED_TRANSFERS:
        raise AssertionError("trace and summary transfers disagree")
    if expected_history:
        if (
            metrics.get("learned_seat_history_schema")
            != LEARNED_SEAT_HISTORY_SCHEMA
            or metrics.get("maximum_learned_model_evaluations_per_boundary")
            != 1
            or metrics.get("maximum_learned_actions_per_boundary") != 1
        ):
            raise AssertionError("per-seat history authority telemetry is invalid")
        updates = metrics.get("learned_seat_history_boundary_updates")
        if (
            not isinstance(updates, list)
            or len(updates) != 3
            or any(type(value) is not int or value <= 0 for value in updates)
        ):
            raise AssertionError("per-seat history update telemetry is invalid")
        transfer_sources = [
            item.get("learned_seat_history_source")
            for item in rollout.trace
            if "learned_seat_transfer" in item
        ]
        if transfer_sources != ["target_agent_cache"] * len(EXPECTED_TRANSFERS):
            raise AssertionError("death failover did not adopt target-seat history")
    return {
        "seed": rollout.seed,
        "outcome": rollout.outcome,
        "tick": rollout.tick,
        "transfers": transfers,
        "maximum_simultaneous_learned_seats": 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check public live single-brain death failover"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
    )
    args = parser.parse_args(argv)
    config_path = (
        args.config
        if args.config.is_absolute()
        else repo_root() / args.config
    )
    try:
        config = _load_config(config_path.resolve())
        _configure_torch(config)
        failover = _learned_seat_failover(config)
        seat_history = _learned_seat_history(config)
        partner_intent_risk = _partner_intent_duplication_risk(config)
        model = build_selector_model(config) if seat_history is not None else None
        if model is not None:
            model.eval()
        with RlServerProcess(
            LaunchConfig(
                port=args.port,
                java=args.java,
                build_if_missing=False,
            )
        ) as env:
            env.handshake(
                f"m8-{config['candidate_version']}-single-brain-failover-check"
            )
            if model is None:
                rollouts = [
                    rollout_control_episode(
                        env,
                        seed=PUBLIC_FAILOVER_SEED,
                        scenario_id=str(config["scenario_id"]),
                        scenario_version=int(config["scenario_version"]),
                        control=GREEDY_MIXED,
                        scripted_partner_opening=config.get(
                            "scripted_partner_opening"
                        ),
                        feature_schema=expected_feature_schema(config),
                        control_schema=expected_control_schema(config),
                        learned_seat_failover=failover,
                    )
                    for _ in range(2)
                ]
            else:
                rollouts = [
                    rollout_episode(
                        env,
                        model,
                        seed=PUBLIC_FAILOVER_SEED,
                        scenario_id=str(config["scenario_id"]),
                        scenario_version=int(config["scenario_version"]),
                        evaluation=True,
                        action_generator=_action_generator(
                            int(config["action_sampling_seed"])
                        ),
                        reward_schema=str(
                            config.get("reward_schema", REWARD_SCHEMA)
                        ),
                        quality_reward=config.get("quality_reward"),
                        teacher_controlled=True,
                        scripted_partner_opening=config.get(
                            "scripted_partner_opening"
                        ),
                        partner_intent_duplication_risk=partner_intent_risk,
                        feature_schema=expected_feature_schema(config),
                        control_schema=expected_control_schema(config),
                        learned_seat_failover=failover,
                        learned_seat_history=seat_history,
                    )
                    for _ in range(2)
                ]
        results = [
            _validate_result(
                rollout,
                expected_history=seat_history is not None,
            )
            for rollout in rollouts
        ]
        if (
            results[0] != results[1]
            or rollouts[0].trace != rollouts[1].trace
            or rollouts[0].coordination_metrics
            != rollouts[1].coordination_metrics
        ):
            raise AssertionError("same-JVM reset replay drifted")
        result = results[0] | {"same_jvm_replays": len(rollouts)}
    except Exception as exc:
        print(f"SINGLE-BRAIN-FAILOVER FAIL: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    print(json.dumps(result, sort_keys=True))
    print("SINGLE-BRAIN-FAILOVER OK: one brain, death-only 0->1->2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
