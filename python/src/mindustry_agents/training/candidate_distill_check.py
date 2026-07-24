"""Exact-commit preflight for ADR-0113 candidate-native distillation."""

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
    CONFIG_SHA256,
    PROTOCOL_SHA256,
    SOURCE_RESULT_SHA256,
    _configure_torch,
    _git_commit,
    _load_protocol,
    _load_seed_set,
    _load_source,
    _teacher_episode,
    distillation_update,
    load_distillation_config,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import save_ippo_checkpoint
from mindustry_agents.training.ippo_ppo import IPPOTransition


def _synthetic_transitions() -> list[IPPOTransition]:
    generator = torch.Generator().manual_seed(11_311)
    result = []
    for index in range(40):
        mask = torch.ones(10, dtype=torch.bool)
        result.append(
            IPPOTransition(
                agent_id=index % 3,
                candidates=torch.randn(8, 37, generator=generator),
                scalars=torch.randn(160, generator=generator),
                candidate_present=torch.ones(8, dtype=torch.bool),
                action_mask=mask,
                hidden_input=torch.randn(64, generator=generator),
                action=index % 10,
                old_log_prob=0.0,
                old_value=0.0,
                team_reward=0.0,
                individual_reward=0.0,
                advanced_ticks=1,
                done=False,
            )
        )
    return result


def _optimizer_probe(
    config: dict[str, Any], output: Path
) -> dict[str, Any]:
    transitions = _synthetic_transitions()
    rows = []
    for replica in ("a", "b"):
        model = SharedRecurrentSelector(int(config["model_init_seed"]))
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=float(config["learning_rate"]),
            eps=float(config["adam_epsilon"]),
        )
        generator = torch.Generator().manual_seed(int(config["shuffle_seed"]))
        metrics = distillation_update(
            model, optimizer, transitions, config, generator
        )
        checkpoint = save_ippo_checkpoint(
            output.with_name(f"{output.stem}-optimizer-{replica}.pt"),
            model,
            optimizer,
            update=1,
            parent_checkpoint_content_sha256=None,
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
        raise RuntimeError("M9 distillation optimizer probe diverged")
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
        root / "configs/training/m9-candidate-native-distill-v1.json"
    )
    config = load_distillation_config(config_path)
    _load_protocol(root, config)
    _load_source(root, config)
    _configure_torch(config)
    optimizer = _optimizer_probe(config, output)
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
        model = SharedRecurrentSelector(int(config["model_init_seed"]))
        with RlServerProcess(
            LaunchConfig(
                port=port,
                java=java,
                build_if_missing=False,
            )
        ) as env:
            env.handshake("m9-candidate-native-distill-preflight")
            first = _teacher_episode(env, model, config, seed=seed)
            second = _teacher_episode(env, model, config, seed=seed)
        identity = lambda item: {
            "seed": item.seed,
            "outcome": item.outcome,
            "tick": item.tick,
            "core_health": item.core_health,
            "eligible_labels": item.eligible_labels,
            "forced_controls": item.forced_controls,
            "trace_sha256": item.trace_sha256,
        }
        if identity(first) != identity(second):
            raise RuntimeError("M9 distillation teacher reset replay diverged")
        live_result = {
            "ran": True,
            "terminal_reset_replay_equal": True,
            **identity(first),
        }
    return {
        "schema": "m9_candidate_native_distill_preflight_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "optimizer_probe": optimizer,
        "live_teacher_probe": live_result,
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
        default=root / "runs/m9-candidate-native-distill-preflight.json",
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
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"M9 DISTILL PREFLIGHT FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 DISTILL PREFLIGHT "
        f"{'OK' if report['passed'] else 'FAIL'} "
        f"output={args.output}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
