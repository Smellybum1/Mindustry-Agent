"""Run ADR-0133's live trajectory-plan implementation preflight."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_distill import (
    _canonical_sha256,
    _configure_torch,
    _write_json,
)
from mindustry_agents.training.candidate_on_policy_relabel import _git_commit
from mindustry_agents.training.candidate_trajectory_plan import (
    CONFIG_SHA256,
    PROTOCOL_SHA256,
    collect_trajectory_plan_episode,
    load_trajectory_plan_config,
    source_model_and_optimizer,
    validate_protocol,
)
from mindustry_agents.training.ippo import model_state_digest


def _summary(episode: Any) -> dict[str, Any]:
    return {
        "seed": episode.seed,
        "outcome": episode.outcome,
        "terminal_tick": episode.tick,
        "core_health": episode.core_health,
        "transitions": len(episode.transitions),
        "eligible_labels": episode.eligible_labels,
        "context_transitions": episode.context_transitions,
        "forced_controls": episode.forced_controls,
        "student_teacher_matches": episode.student_teacher_matches,
        "rejected_student_actions": episode.rejected_student_actions,
        "trace_sha256": episode.trace_sha256,
        "plan_target_sha256": _canonical_sha256(episode.plan_targets),
    }


def run(output: Path, *, java: str, port: int) -> dict[str, Any]:
    root = repo_root()
    config = load_trajectory_plan_config(
        root
        / "configs/training/m9-candidate-native-trajectory-plan-v1.json"
    )
    validate_protocol(root, config)
    _configure_torch(config)
    model, optimizer, source = source_model_and_optimizer(root, config)
    initial_digest = model_state_digest(model)
    optimizer_state_count = len(optimizer.state)
    new_group_empty = all(
        parameter not in optimizer.state
        for parameter in optimizer.param_groups[1]["params"]
    )
    seed = 18000000001
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=output.parent,
            log_name="trajectory-plan-preflight",
        )
    ) as env:
        env.handshake("m9-trajectory-plan-preflight")
        first = collect_trajectory_plan_episode(
            env, model, config, seed=seed
        )
        second = collect_trajectory_plan_episode(
            env, model, config, seed=seed
        )
    first_summary = _summary(first)
    second_summary = _summary(second)
    reset_equal = first_summary == second_summary
    unchanged = model_state_digest(model) == initial_digest
    result = {
        "schema": "m9_candidate_native_trajectory_plan_live_preflight_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "public_train_seed": seed,
        "episode": first_summary,
        "terminal_reset_replay_equal": reset_equal,
        "source_checkpoint_content_sha256": source[
            "checkpoint_content_sha256"
        ],
        "initial_augmented_model_state_sha256": initial_digest,
        "model_unchanged": unchanged,
        "inherited_optimizer_state_entries": optimizer_state_count,
        "new_optimizer_group_empty": new_group_empty,
        "confirmation_or_held_out_access": False,
        "passed": reset_equal and unchanged and new_group_empty,
    }
    _write_json(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-candidate-trajectory-plan-preflight.json",
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.output.resolve(), java=args.java, port=args.port)
    except Exception as error:
        print(f"M9 TRAJECTORY PLAN PREFLIGHT FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 TRAJECTORY PLAN PREFLIGHT "
        f"{'PASS' if result['passed'] else 'FAIL'} "
        f"labels={result['episode']['eligible_labels']} "
        f"context={result['episode']['context_transitions']}",
        flush=True,
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
