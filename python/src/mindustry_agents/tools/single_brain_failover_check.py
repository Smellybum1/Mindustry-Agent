"""Live public V47 single-brain death-failover acceptance check."""

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
    _learned_seat_failover,
    expected_control_schema,
    expected_feature_schema,
)
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
    if config.get("candidate_version") != "v47":
        raise ValueError("single-brain check requires the exact V47 config")
    return config


def _validate_result(rollout) -> dict[str, Any]:
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
    return {
        "seed": rollout.seed,
        "outcome": rollout.outcome,
        "tick": rollout.tick,
        "transfers": transfers,
        "maximum_simultaneous_learned_seats": 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check V47's public live single-brain death failover"
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
        failover = _learned_seat_failover(config)
        with RlServerProcess(
            LaunchConfig(
                port=args.port,
                java=args.java,
                build_if_missing=False,
            )
        ) as env:
            env.handshake("m8-v47-single-brain-failover-check")
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
        results = [_validate_result(rollout) for rollout in rollouts]
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
