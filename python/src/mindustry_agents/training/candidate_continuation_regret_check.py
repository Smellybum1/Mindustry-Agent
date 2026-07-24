"""Exact-commit public preflight for ADR-0137 continuation regret."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_continuation_regret import (
    BUNDLE_INPUT_WIDTH,
    CONFIG_SHA256,
    GLOBAL_HIDDEN_WIDTH,
    GLOBAL_INPUT_WIDTH,
    PROTOCOL_SHA256,
    ContinuationRootExample,
    collect_continuation_root,
    continuation_update,
    load_continuation_config,
    source_model_and_optimizer,
    validate_protocol,
)
from mindustry_agents.training.candidate_continuation_regret_train import (
    load_checkpoint,
    save_checkpoint,
)
from mindustry_agents.training.candidate_distill import (
    _configure_torch,
    _git_commit,
    _write_json,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import _state_digest
from mindustry_agents.training.ippo_ppo import sha256_path


def _example() -> ContinuationRootExample:
    prefix = torch.linspace(
        -0.5, 0.5, 9 * GLOBAL_INPUT_WIDTH
    ).reshape(9, GLOBAL_INPUT_WIDTH)
    static = torch.zeros((8, BUNDLE_INPUT_WIDTH - GLOBAL_HIDDEN_WIDTH))
    static[:, 1414] = torch.linspace(0.0, 1.0, 8)
    targets = torch.stack(
        [torch.linspace(index / 20.0, index / 20.0 + 0.3, 4) for index in range(8)]
    )
    return ContinuationRootExample(
        seed=1,
        prefix_global_inputs=prefix,
        prefix_commit_mask=torch.ones(8, dtype=torch.bool),
        bundle_static_inputs=static,
        targets=targets,
        achieved_horizons=torch.tensor([(1, 4, 8, 16)] * 8),
        sampled_bundles=tuple((index, 0, 0) for index in range(8)),
        planner_inadmissible=(False,) * 8,
        selected_state_sha256="a" * 64,
        branch_trace_sha256=("b" * 64,) * 8,
    )


def _source_digest(model: torch.nn.Module) -> str:
    inherited = {
        name: value
        for name, value in model.state_dict().items()
        if not name.startswith(
            ("global_recurrent_cell.", "bundle_cost_head.")
        )
    }
    base = SharedRecurrentSelector(1)
    base.load_state_dict(inherited)
    return model_state_digest(base)


def _configured_replicas(
    root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    reduced = {
        **config,
        "optimizer": {
            **config["optimizer"],
            "optimizer_steps_per_group": 2,
            "branch_rows_per_minibatch": 4,
        },
    }
    rows = []
    models = []
    optimizers = []
    for _ in range(2):
        model, optimizer, _ = source_model_and_optimizer(root, config)
        metrics = continuation_update(
            model,
            optimizer,
            [_example()],
            reduced,
            torch.Generator().manual_seed(
                int(config["rng"]["minibatch_seed"])
            ),
        )
        rows.append(
            {
                "model_state_sha256": model_state_digest(model),
                "optimizer_state_sha256": _state_digest(
                    optimizer.state_dict()
                ),
                "metrics": metrics,
            }
        )
        models.append(model)
        optimizers.append(optimizer)
    if rows[0] != rows[1]:
        raise RuntimeError("M9 continuation optimizer replicas diverged")
    if torch.count_nonzero(models[0].bundle_cost_head[-1].weight) == 0:
        raise RuntimeError("M9 continuation cost head received no gradient")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "checkpoint.pt"
        saved = save_checkpoint(
            path,
            models[0],
            optimizers[0],
            group=1,
            parent_checkpoint_content_sha256="a" * 64,
        )
        restored, restored_optimizer, _ = source_model_and_optimizer(
            root, config
        )
        loaded = load_checkpoint(path, restored, restored_optimizer)
        if (
            saved["checkpoint_content_sha256"]
            != loaded["checkpoint_content_sha256"]
            or model_state_digest(restored)
            != model_state_digest(models[0])
            or _state_digest(restored_optimizer.state_dict())
            != _state_digest(optimizers[0].state_dict())
        ):
            raise RuntimeError("M9 continuation checkpoint replay drifted")
    return {
        "replicas_equal": True,
        "model_state_sha256": rows[0]["model_state_sha256"],
        "optimizer_state_sha256": rows[0]["optimizer_state_sha256"],
        "metrics": rows[0]["metrics"],
        "cost_gradient_nonzero": True,
        "checkpoint_round_trip_exact": True,
    }


def _live_replay(
    root: Path,
    config: dict[str, Any],
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    train = json.loads(
        (root / str(config["train_seed_set"])).read_text(encoding="utf-8")
    )
    seed = int(train["seeds"][0])
    model, _, _ = source_model_and_optimizer(root, config)
    before = model_state_digest(model)
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
        )
    ) as env:
        env.handshake("m9-continuation-regret-live-preflight")
        first = collect_continuation_root(env, model, config, seed=seed)
        second = collect_continuation_root(env, model, config, seed=seed)
    summaries = [
        {
            "seed": item.seed,
            "branch_rows": item.branch_rows,
            "sampled_bundles": item.sampled_bundles,
            "targets": item.targets.tolist(),
            "achieved_horizons": item.achieved_horizons.tolist(),
            "planner_inadmissible": item.planner_inadmissible,
            "selected_state_sha256": item.selected_state_sha256,
            "branch_trace_sha256": item.branch_trace_sha256,
        }
        for item in (first, second)
    ]
    if summaries[0] != summaries[1] or model_state_digest(model) != before:
        raise RuntimeError("M9 continuation live replay drifted")
    return {
        "seed": seed,
        "fresh_collection_reports_equal": True,
        "summary": summaries[0],
        "model_unchanged": True,
    }


def build_report(
    root: Path,
    config_path: Path,
    *,
    java: str,
    port: int,
    live: bool,
) -> dict[str, Any]:
    """Build the exact local public-only preflight report."""

    config = load_continuation_config(config_path)
    validate_protocol(root, config)
    _configure_torch(config)
    source_file = root / str(config["source_checkpoint"]["path"])
    source_before = sha256_path(source_file)
    model, optimizer, payload = source_model_and_optimizer(root, config)
    inherited = _source_digest(model)
    if inherited != payload["model_state_sha256"]:
        raise RuntimeError("M9 continuation inherited model drifted")
    if optimizer.state:
        raise RuntimeError("M9 continuation fresh AdamW is not empty")
    if any(
        parameter.requires_grad
        for name, parameter in model.named_parameters()
        if not name.startswith(
            ("global_recurrent_cell.", "bundle_cost_head.")
        )
    ):
        raise RuntimeError("M9 continuation source model is not frozen")
    if torch.count_nonzero(
        model.bundle_cost_head[-1].weight
    ) or torch.count_nonzero(model.bundle_cost_head[-1].bias):
        raise RuntimeError("M9 continuation final residual is not zero")
    example = _example()
    with torch.no_grad():
        hidden = model.continuation_hidden(
            example.prefix_global_inputs, example.prefix_commit_mask
        )
        outputs = model.cost_outputs(
            example.bundle_static_inputs, hidden
        )[0]
    expected = example.bundle_static_inputs[:, 1414:1415].expand(-1, 4)
    if not torch.equal(outputs, expected):
        raise RuntimeError("M9 continuation source-order equivalence drifted")
    replicas = _configured_replicas(root, config)
    live_result = (
        _live_replay(root, config, java=java, port=port)
        if live
        else {"skipped": True}
    )
    if sha256_path(source_file) != source_before:
        raise RuntimeError("M9 continuation source checkpoint changed")
    return {
        "schema": "m9_candidate_native_continuation_regret_preflight_v1",
        "passed": True,
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_checkpoint": {
            "file_sha256": source_before,
            "checkpoint_content_sha256": payload[
                "checkpoint_content_sha256"
            ],
            "model_state_sha256": payload["model_state_sha256"],
            "optimizer_state_sha256": payload["optimizer_state_sha256"],
            "optimizer_loaded": False,
            "selected_or_promoted": False,
            "repaired": False,
            "unchanged": True,
        },
        "inherited_model_state_sha256": inherited,
        "source_parameters_frozen": True,
        "fresh_adamw_state_entries": len(optimizer.state),
        "zero_residual_source_order_exact": True,
        "configured_optimizer_replicas": replicas,
        "live_counterfactual_replay": live_result,
        "complete_exact_current_commit_public_gate": True,
        "confirmation_or_held_out_access": False,
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            root
            / "configs/training/"
            "m9-candidate-native-continuation-regret-v1.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-candidate-continuation-regret-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(
            root,
            args.config.resolve(),
            java=args.java,
            port=args.port,
            live=not args.skip_live,
        )
        _write_json(args.output.resolve(), report)
    except Exception as error:
        print(f"M9 CONTINUATION PREFLIGHT FAIL: {error}")
        return 1
    print(
        "M9 CONTINUATION PREFLIGHT OK "
        f"commit={report['implementation_commit'][:12]} "
        f"live={not args.skip_live}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
