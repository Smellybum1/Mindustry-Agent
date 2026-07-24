"""Exact-commit preflight for ADR-0117 on-policy relabeling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_distill import (
    _configure_torch,
    _write_json,
    distillation_update,
)
from mindustry_agents.training.candidate_distill_check import (
    _synthetic_transitions,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    CONFIG_SHA256,
    DIAGNOSTIC_RESULT_SHA256,
    PROTOCOL_SHA256,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_RESULT_SHA256,
    _git_commit,
    _load_protocol,
    _load_seed_set,
    _load_source,
    _source_model_and_optimizer,
    _student_episode,
    load_on_policy_relabel_config,
)
from mindustry_agents.training.ippo import model_state_digest
from mindustry_agents.training.ippo_artifacts import save_ippo_checkpoint


def _optimizer_probe(
    root: Path,
    config: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    transitions = _synthetic_transitions()
    rows = []
    for replica in ("a", "b"):
        model, optimizer, _ = _source_model_and_optimizer(root, config)
        metrics = distillation_update(
            model,
            optimizer,
            transitions,
            config,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
        )
        checkpoint = save_ippo_checkpoint(
            output.with_name(f"{output.stem}-optimizer-{replica}.pt"),
            model,
            optimizer,
            update=33,
            parent_checkpoint_content_sha256=(
                SOURCE_CHECKPOINT_CONTENT_SHA256
            ),
            config_sha256_value=CONFIG_SHA256,
        )
        rows.append(
            {
                "model_state_sha256": model_state_digest(model),
                "optimizer_state_sha256": checkpoint[
                    "optimizer_state_sha256"
                ],
                "checkpoint_content_sha256": checkpoint[
                    "checkpoint_content_sha256"
                ],
                "metrics": metrics,
            }
        )
    if rows[0] != rows[1]:
        raise RuntimeError("M9 on-policy relabel optimizer probe diverged")
    return {"replicas_equal": True, **rows[0]}


def build_report(
    root: Path,
    output: Path,
    *,
    java: str,
    port: int,
    live: bool = True,
) -> dict[str, Any]:
    config_path = (
        root
        / "configs/training/m9-candidate-native-on-policy-relabel-v1.json"
    )
    config = load_on_policy_relabel_config(config_path)
    _load_protocol(root, config)
    _load_source(root, config)
    _configure_torch(config)
    optimizer = _optimizer_probe(root, config, output)
    live_result: dict[str, Any] = {"ran": False}
    if live:
        train_set, _ = _load_seed_set(
            root,
            str(config["train_seed_set"]),
            split="train",
            count=2048,
            lower=18_000_000_000,
            upper=19_000_000_000,
        )
        seed = int(train_set["seeds"][0])
        model, _, _ = _source_model_and_optimizer(root, config)
        with RlServerProcess(
            LaunchConfig(
                port=port,
                java=java,
                build_if_missing=False,
            )
        ) as env:
            env.handshake("m9-candidate-on-policy-relabel-preflight")
            first = _student_episode(env, model, config, seed=seed)
            second = _student_episode(env, model, config, seed=seed)

        def identity(item: Any) -> dict[str, Any]:
            return {
                "seed": item.seed,
                "outcome": item.outcome,
                "tick": item.tick,
                "core_health": item.core_health,
                "eligible_labels": item.eligible_labels,
                "forced_controls": item.forced_controls,
                "student_teacher_matches": item.student_teacher_matches,
                "rejected_student_actions": item.rejected_student_actions,
                "trace_sha256": item.trace_sha256,
            }

        if identity(first) != identity(second):
            raise RuntimeError(
                "M9 on-policy relabel terminal reset replay diverged"
            )
        live_result = {
            "ran": True,
            "terminal_reset_replay_equal": True,
            **identity(first),
        }
    return {
        "schema": "m9_candidate_native_on_policy_relabel_preflight_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "diagnostic_result_sha256": DIAGNOSTIC_RESULT_SHA256,
        "source_checkpoint_content_sha256": (
            SOURCE_CHECKPOINT_CONTENT_SHA256
        ),
        "optimizer_probe": optimizer,
        "live_student_state_probe": live_result,
        "confirmation_or_held_out_access": False,
        "passed": optimizer["replicas_equal"]
        and (not live or live_result["terminal_reset_replay_equal"]),
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=root
        / "runs/m9-candidate-on-policy-relabel-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(
            root,
            args.output,
            java=args.java,
            port=args.port,
            live=not args.no_live,
        )
        _write_json(args.output, report)
    except Exception as error:
        print(f"M9 RELABEL PREFLIGHT FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 RELABEL PREFLIGHT "
        f"{'OK' if report['passed'] else 'FAIL'} "
        f"output={args.output}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
