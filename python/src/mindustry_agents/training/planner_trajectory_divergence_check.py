"""Run ADR-0131's one-root live implementation preflight."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT, repo_root
from mindustry_agents.training.candidate_distill import (
    _configure_torch,
    _git_commit,
    _write_json,
)
from mindustry_agents.training.planner_trajectory_divergence import (
    PROTOCOL_SHA256,
    _run_once,
    validate_inputs,
)


def _compact_episode(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        key: episode[key]
        for key in (
            "seed",
            "policy",
            "outcome",
            "reset_tick",
            "terminal_tick",
            "terminal_state_hash",
            "core_health",
            "grid_samples",
            "trace_sha256",
        )
    }


def run(output: Path, *, java: str, port: int) -> dict[str, Any]:
    root = repo_root()
    protocol, config, seeds = validate_inputs(root)
    _configure_torch(config)
    report = _run_once(
        root,
        protocol,
        config,
        seeds[:1],
        java=java,
        port=port,
        run_index=1,
        log_dir=output.parent,
    )
    student = report["policies"]["student"]["roots"][0]
    planner = report["policies"]["planner"]["roots"][0]
    result = {
        "schema": "m9_planner_trajectory_divergence_live_preflight_v1",
        "implementation_commit": _git_commit(root),
        "protocol_sha256": PROTOCOL_SHA256,
        "data_classification": "public_dev_only",
        "seed": int(seeds[0]),
        "student": _compact_episode(student),
        "planner": _compact_episode(planner),
        "paired": report["paired"]["roots"][0],
        "model_state_sha256": report["model_state_sha256"],
        "optimizer_state_sha256": report["optimizer_state_sha256"],
        "model_or_optimizer_modified": report[
            "model_or_optimizer_modified"
        ],
        "terminal_reset_replay_equal": report[
            "terminal_reset_replay_equal"
        ],
        "target_identifiers_recorded": False,
        "raw_observations_published": False,
        "confirmation_or_held_out_access": False,
        "passed": (
            report["terminal_reset_replay_equal"]
            and report["model_or_optimizer_modified"] is False
        ),
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
        default=(
            root
            / "runs/m9-planner-trajectory-divergence-v1-live-preflight.json"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.output.resolve(), java=args.java, port=args.port)
    except Exception as error:
        print(
            f"M9 PLANNER TRAJECTORY PREFLIGHT FAIL: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "M9 PLANNER TRAJECTORY PREFLIGHT "
        f"{'PASS' if result['passed'] else 'FAIL'} "
        f"student={result['student']['outcome']} "
        f"planner={result['planner']['outcome']} "
        f"samples={result['paired']['common_grid_samples']}",
        flush=True,
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
