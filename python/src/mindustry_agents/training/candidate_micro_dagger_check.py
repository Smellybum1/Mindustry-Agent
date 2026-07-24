"""Exact-commit preflight for ADR-0129 micro-DAgger."""

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
    TRAIN_MAXIMUM,
    TRAIN_MINIMUM,
    _configure_torch,
    _load_seed_set,
    _write_json,
    distillation_update,
)
from mindustry_agents.training.candidate_distill_check import (
    _synthetic_transitions,
)
from mindustry_agents.training.candidate_micro_dagger import (
    CONFIG_SHA256,
    PROTOCOL_SHA256,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_MODEL_SHA256,
    SOURCE_OPTIMIZER_SHA256,
    _load_protocol,
    _load_source,
    _one_fresh_optimizer_epoch,
    _source_model_and_optimizer,
    load_micro_dagger_config,
    micro_dagger_optimizer_schedule,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    _git_commit,
    _student_episode,
)
from mindustry_agents.training.ippo import model_state_digest
from mindustry_agents.training.ippo_artifacts import save_ippo_checkpoint


def _single_update_equivalence(
    root: Path, config: dict[str, Any], output: Path
) -> dict[str, Any]:
    transitions = _synthetic_transitions()
    old_model, old_optimizer, _ = _source_model_and_optimizer(root, config)
    new_model, new_optimizer, _ = _source_model_and_optimizer(root, config)
    local = dict(config)
    local["epochs_per_update"] = 1
    seed = int(config["shuffle_seed"])
    old_metrics = distillation_update(
        old_model, old_optimizer, transitions, local,
        torch.Generator().manual_seed(seed),
    )
    new_metrics = _one_fresh_optimizer_epoch(
        new_model, new_optimizer, transitions, config,
        torch.Generator().manual_seed(seed),
    )
    rows = []
    for name, model, optimizer in (
        ("flat", old_model, old_optimizer),
        ("micro", new_model, new_optimizer),
    ):
        rows.append(save_ippo_checkpoint(
            output.with_name(f"{output.stem}-{name}.pt"),
            model, optimizer, update=33,
            parent_checkpoint_content_sha256=(
                SOURCE_CHECKPOINT_CONTENT_SHA256
            ),
            config_sha256_value=CONFIG_SHA256,
        ))
    if (
        old_metrics != new_metrics
        or rows[0]["checkpoint_content_sha256"]
        != rows[1]["checkpoint_content_sha256"]
    ):
        raise RuntimeError("M9 micro single-update equivalence diverged")
    return {
        "matches_flat_nll_exactly": True,
        "checkpoint_content_sha256": rows[0][
            "checkpoint_content_sha256"
        ],
        "metrics": old_metrics,
    }


def _configured_schedule_probe(
    root: Path, config: dict[str, Any], output: Path
) -> dict[str, Any]:
    base = _synthetic_transitions()
    datasets = [
        base[index:] + base[:index] for index in range(8)
    ]
    rows = []
    for replica in ("a", "b"):
        model, optimizer, _ = _source_model_and_optimizer(root, config)
        metrics = micro_dagger_optimizer_schedule(
            model, optimizer, datasets, config,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
        )
        checkpoint = save_ippo_checkpoint(
            output.with_name(f"{output.stem}-schedule-{replica}.pt"),
            model, optimizer, update=33,
            parent_checkpoint_content_sha256=(
                SOURCE_CHECKPOINT_CONTENT_SHA256
            ),
            config_sha256_value=CONFIG_SHA256,
        )
        rows.append({
            "model_state_sha256": model_state_digest(model),
            "optimizer_state_sha256": checkpoint[
                "optimizer_state_sha256"
            ],
            "checkpoint_content_sha256": checkpoint[
                "checkpoint_content_sha256"
            ],
            "micro_metrics": metrics,
        })
    if rows[0] != rows[1]:
        raise RuntimeError("M9 micro configured schedule diverged")
    return {"replicas_equal": True, **rows[0]}


def _inherited_contract(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    parent = json.loads(
        (root / "configs/training/"
         "m9-candidate-native-on-policy-relabel-v1.json"
        ).read_text(encoding="utf-8")
    )
    exact = (
        "teacher_policy", "runtime_contract", "scenario_id",
        "scenario_version", "agent_count", "train_seed_set",
        "train_seed_set_sha256", "dev_seed_set", "dev_seed_set_sha256",
        "confirmation_seed_set", "held_out_seed_set", "shuffle_seed",
        "torch_threads", "learning_rate", "adam_epsilon",
        "minibatch_size", "max_grad_norm", "model_architecture",
    )
    if any(config[key] != parent[key] for key in exact):
        raise ValueError("M9 micro inherited contract drifted")
    if (
        config["macro_updates"] != parent["continuation_updates"]
        or config["unique_roots_per_macro_update"]
        != parent["episodes_per_update"]
        or config["micro_updates_per_macro_update"]
        != parent["epochs_per_update"]
    ):
        raise ValueError("M9 micro schedule comparison drifted")
    return {
        "exact_fields": list(exact),
        "only_change": "collect_optimize_interleaving",
        "passed": True,
    }


def build_report(
    root: Path, output: Path, *, java: str, port: int, live: bool = True
) -> dict[str, Any]:
    config = load_micro_dagger_config(
        root / "configs/training/m9-candidate-native-micro-dagger-v1.json"
    )
    _load_protocol(root, config)
    _load_source(root, config)
    _configure_torch(config)
    inherited = _inherited_contract(root, config)
    equivalence = _single_update_equivalence(root, config, output)
    schedule = _configured_schedule_probe(root, config, output)
    live_result: dict[str, Any] = {"ran": False}
    if live:
        train_set, _ = _load_seed_set(
            root, str(config["train_seed_set"]), split="train", count=2048,
            lower=TRAIN_MINIMUM, upper=TRAIN_MAXIMUM,
        )
        seed = int(train_set["seeds"][0])
        model, optimizer, _ = _source_model_and_optimizer(root, config)
        with RlServerProcess(LaunchConfig(
            port=port, java=java, build_if_missing=False
        )) as env:
            env.handshake("m9-micro-dagger-preflight")
            before = _student_episode(env, model, config, seed=seed)
            source_digest = model_state_digest(model)
            _one_fresh_optimizer_epoch(
                model, optimizer, before.transitions, config,
                torch.Generator().manual_seed(int(config["shuffle_seed"])),
            )
            updated_digest = model_state_digest(model)
            after_a = _student_episode(env, model, config, seed=seed)
            after_b = _student_episode(env, model, config, seed=seed)
        identity = lambda item: {
            "outcome": item.outcome,
            "tick": item.tick,
            "core_health": item.core_health,
            "eligible_labels": item.eligible_labels,
            "forced_controls": item.forced_controls,
            "trace_sha256": item.trace_sha256,
        }
        if source_digest == updated_digest:
            raise RuntimeError("M9 micro preflight model did not update")
        if identity(after_a) != identity(after_b):
            raise RuntimeError("M9 micro post-update reset diverged")
        live_result = {
            "ran": True,
            "source_model_state_sha256": source_digest,
            "updated_model_state_sha256": updated_digest,
            "post_update_collection_uses_current_model": True,
            "terminal_reset_replay_equal": True,
            "before": identity(before),
            "after": identity(after_a),
        }
    report = {
        "schema": "m9_candidate_native_micro_dagger_preflight_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_checkpoint_content_sha256":
            SOURCE_CHECKPOINT_CONTENT_SHA256,
        "source_model_sha256": SOURCE_MODEL_SHA256,
        "source_optimizer_sha256": SOURCE_OPTIMIZER_SHA256,
        "inherited_contract_probe": inherited,
        "single_micro_update_equivalence_probe": equivalence,
        "configured_schedule_probe": schedule,
        "live_fresh_collection_probe": live_result,
        "confirmation_or_held_out_access": False,
        "passed": (
            inherited["passed"]
            and equivalence["matches_flat_nll_exactly"]
            and schedule["replicas_equal"]
            and (
                not live
                or (
                    live_result["post_update_collection_uses_current_model"]
                    and live_result["terminal_reset_replay_equal"]
                )
            )
        ),
    }
    _write_json(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=root / "runs/m9-candidate-micro-dagger-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(
            root, args.output.resolve(), java=args.java, port=args.port,
            live=not args.no_live,
        )
    except Exception as error:
        print(f"M9 MICRO-DAGGER PREFLIGHT FAIL: {error}", file=sys.stderr)
        return 1
    print("M9 MICRO-DAGGER PREFLIGHT PASS")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
