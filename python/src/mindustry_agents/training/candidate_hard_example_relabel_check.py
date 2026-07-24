"""Exact-commit preflight for ADR-0123 hard-example relabeling."""

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
from mindustry_agents.training.candidate_hard_example_relabel import (
    CONFIG_SHA256,
    DIAGNOSTIC_RESULT_SHA256,
    HARD_EXAMPLE_WEIGHT,
    PROTOCOL_SHA256,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_RESULT_SHA256,
    _load_protocol,
    _load_seed_set,
    _load_source,
    _source_model_and_optimizer,
    load_hard_example_config,
    weighted_distillation_update,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    _git_commit,
    _student_episode,
)
from mindustry_agents.training.ippo import model_state_digest
from mindustry_agents.training.ippo_artifacts import save_ippo_checkpoint


def _ordinary_equivalence_probe(
    root: Path,
    config: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    transitions = _synthetic_transitions()
    model_old, optimizer_old, _ = _source_model_and_optimizer(root, config)
    model_new, optimizer_new, _ = _source_model_and_optimizer(root, config)
    old_metrics = distillation_update(
        model_old,
        optimizer_old,
        transitions,
        config,
        torch.Generator().manual_seed(int(config["shuffle_seed"])),
    )
    new_metrics = weighted_distillation_update(
        model_new,
        optimizer_new,
        transitions,
        [False] * len(transitions),
        config,
        torch.Generator().manual_seed(int(config["shuffle_seed"])),
    )
    old_checkpoint = save_ippo_checkpoint(
        output.with_name(f"{output.stem}-ordinary-old.pt"),
        model_old,
        optimizer_old,
        update=65,
        parent_checkpoint_content_sha256=(
            SOURCE_CHECKPOINT_CONTENT_SHA256
        ),
        config_sha256_value=CONFIG_SHA256,
    )
    new_checkpoint = save_ippo_checkpoint(
        output.with_name(f"{output.stem}-ordinary-new.pt"),
        model_new,
        optimizer_new,
        update=65,
        parent_checkpoint_content_sha256=(
            SOURCE_CHECKPOINT_CONTENT_SHA256
        ),
        config_sha256_value=CONFIG_SHA256,
    )
    if (
        old_checkpoint["checkpoint_content_sha256"]
        != new_checkpoint["checkpoint_content_sha256"]
        or old_metrics["teacher_nll"] != new_metrics["teacher_nll"]
        or new_metrics["hard_example_labels"] != 0.0
        or new_metrics["total_example_weight"] != float(len(transitions))
    ):
        raise RuntimeError(
            "M9 hard-example ordinary-weight equivalence diverged"
        )
    return {
        "all_ordinary_matches_unweighted_update": True,
        "checkpoint_content_sha256": old_checkpoint[
            "checkpoint_content_sha256"
        ],
        "model_state_sha256": old_checkpoint["model_state_sha256"],
        "optimizer_state_sha256": old_checkpoint[
            "optimizer_state_sha256"
        ],
        "teacher_nll": old_metrics["teacher_nll"],
    }


def _weighted_optimizer_probe(
    root: Path,
    config: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    transitions = _synthetic_transitions()
    flags = [
        index < 8 for index in range(len(transitions))
    ]
    rows = []
    for replica in ("a", "b"):
        model, optimizer, _ = _source_model_and_optimizer(root, config)
        metrics = weighted_distillation_update(
            model,
            optimizer,
            transitions,
            flags,
            config,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
        )
        checkpoint = save_ippo_checkpoint(
            output.with_name(f"{output.stem}-weighted-{replica}.pt"),
            model,
            optimizer,
            update=65,
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
        raise RuntimeError("M9 hard-example optimizer probe diverged")
    metrics = rows[0]["metrics"]
    if (
        metrics["hard_example_labels"] != 8.0
        or metrics["ordinary_example_labels"]
        != float(len(transitions) - 8)
        or metrics["total_example_weight"]
        != 8 * HARD_EXAMPLE_WEIGHT + len(transitions) - 8
    ):
        raise RuntimeError("M9 hard-example weight telemetry drifted")
    return {"replicas_equal": True, **rows[0]}


def _inherited_contract_probe(
    root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    parent = json.loads(
        (
            root
            / "configs/training/"
            "m9-candidate-native-on-policy-relabel-v1.json"
        ).read_text(encoding="utf-8")
    )
    exact_keys = (
        "teacher_policy",
        "runtime_contract",
        "scenario_id",
        "scenario_version",
        "agent_count",
        "train_seed_set",
        "train_seed_set_sha256",
        "dev_seed_set",
        "dev_seed_set_sha256",
        "confirmation_seed_set",
        "held_out_seed_set",
        "shuffle_seed",
        "torch_threads",
        "continuation_updates",
        "episodes_per_update",
        "learning_rate",
        "adam_epsilon",
        "epochs_per_update",
        "minibatch_size",
        "max_grad_norm",
        "model_architecture",
    )
    schedule_keys = (
        "root_count",
        "reuse_count",
        "shuffle",
        "shuffle_seed",
        "updates",
        "episodes_per_update",
    )
    selection_keys = (
        "minimum_wins",
        "maximum_mean_team_idle_fraction_exclusive",
        "ranking",
    )
    if any(config[key] != parent[key] for key in exact_keys):
        raise ValueError("M9 hard-example inherited config drifted")
    if any(
        config["training_root_schedule"][key]
        != parent["training_root_schedule"][key]
        for key in schedule_keys
    ):
        raise ValueError("M9 hard-example inherited schedule drifted")
    if any(
        config["checkpoint_selection"][key]
        != parent["checkpoint_selection"][key]
        for key in selection_keys
    ):
        raise ValueError("M9 hard-example inherited selection drifted")
    return {
        "parent_candidate": parent["candidate_version"],
        "exact_config_fields": list(exact_keys),
        "exact_schedule_fields": list(schedule_keys),
        "exact_selection_fields": list(selection_keys),
        "only_learning_change": "normalized_disagreement_example_weight",
        "passed": True,
    }


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
        / "configs/training/"
        "m9-candidate-native-hard-example-relabel-v1.json"
    )
    config = load_hard_example_config(config_path)
    _load_protocol(root, config)
    _load_source(root, config)
    _configure_torch(config)
    inherited = _inherited_contract_probe(root, config)
    ordinary = _ordinary_equivalence_probe(root, config, output)
    weighted = _weighted_optimizer_probe(root, config, output)
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
            env.handshake("m9-candidate-hard-example-relabel-preflight")
            first = _student_episode(env, model, config, seed=seed)
            second = _student_episode(env, model, config, seed=seed)

        def identity(item: Any) -> dict[str, Any]:
            hard_examples = sum(item.hard_example_flags)
            return {
                "seed": item.seed,
                "outcome": item.outcome,
                "tick": item.tick,
                "core_health": item.core_health,
                "eligible_labels": item.eligible_labels,
                "forced_controls": item.forced_controls,
                "student_teacher_matches": item.student_teacher_matches,
                "hard_examples": hard_examples,
                "ordinary_examples": (
                    item.eligible_labels - hard_examples
                ),
                "total_example_weight": (
                    hard_examples * HARD_EXAMPLE_WEIGHT
                    + item.eligible_labels
                    - hard_examples
                ),
                "rejected_student_actions": (
                    item.rejected_student_actions
                ),
                "trace_sha256": item.trace_sha256,
            }

        if identity(first) != identity(second):
            raise RuntimeError(
                "M9 hard-example terminal reset replay diverged"
            )
        if len(first.hard_example_flags) != len(first.transitions):
            raise RuntimeError(
                "M9 hard-example live weights are misaligned"
            )
        live_result = {
            "ran": True,
            "terminal_reset_replay_equal": True,
            **identity(first),
        }
    return {
        "schema": "m9_candidate_native_hard_example_relabel_preflight_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "diagnostic_result_sha256": DIAGNOSTIC_RESULT_SHA256,
        "source_checkpoint_content_sha256": (
            SOURCE_CHECKPOINT_CONTENT_SHA256
        ),
        "inherited_contract_probe": inherited,
        "ordinary_equivalence_probe": ordinary,
        "weighted_optimizer_probe": weighted,
        "live_student_state_probe": live_result,
        "confirmation_or_held_out_access": False,
        "passed": (
            inherited["passed"]
            and ordinary["all_ordinary_matches_unweighted_update"]
            and weighted["replicas_equal"]
            and (
                not live
                or live_result["terminal_reset_replay_equal"]
            )
        ),
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=root
        / "runs/m9-candidate-hard-example-relabel-preflight.json",
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
        print(
            f"M9 HARD-EXAMPLE PREFLIGHT FAIL: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "M9 HARD-EXAMPLE PREFLIGHT "
        f"{'OK' if report['passed'] else 'FAIL'} "
        f"output={args.output}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
