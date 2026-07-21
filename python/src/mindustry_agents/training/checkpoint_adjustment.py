"""Construct a governed one-coordinate selector-logit adjustment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.checkpoint_lineage import (
    ADJUSTMENT_LINEAGE_REPRODUCIBILITY_SCHEMA,
    ADJUSTMENT_LINEAGE_SCHEMA,
    _adjustment_lineage_evidence,
    validate_lineage_manifest,
)
from mindustry_agents.training.checkpoint_interpolation import ALLOWED_DIRTY_PATHS
from mindustry_agents.training.model import SelectorActorCritic
from mindustry_agents.training.ppo_selector import (
    FEATURE_SCHEMA,
    MODEL_SCHEMA,
    REWARD_SCHEMA,
    _git_evidence,
    _json_digest,
    _model_state_digest,
    _sha256,
    load_checkpoint,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def adjust_model_state(
    state: dict[str, torch.Tensor], *, tensor_name: str, index: int, delta: float
) -> dict[str, torch.Tensor]:
    """Clone a state and adjust exactly one floating-point coordinate."""

    if tensor_name not in state:
        raise ValueError("adjustment tensor is absent from model state")
    output = {name: tensor.detach().cpu().clone() for name, tensor in state.items()}
    tensor = output[tensor_name]
    if not tensor.is_floating_point() or tensor.ndim != 1:
        raise ValueError("adjustment tensor must be a floating-point vector")
    if not 0 <= index < tensor.shape[0]:
        raise ValueError("adjustment index is out of range")
    tensor[index] += delta
    return output


def construct_adjusted_checkpoint(
    *,
    config_path: Path,
    parent_config_path: Path,
    parent_checkpoint_path: Path,
    parent_lineage_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    root = repo_root()
    repository = _git_evidence(root)
    unexpected = [
        line
        for line in repository["status"]
        if line[3:].replace("\\", "/") not in ALLOWED_DIRTY_PATHS
    ]
    if unexpected:
        raise ValueError("checkpoint adjustment requires a frozen repository")

    config_path = config_path.resolve()
    parent_config_path = parent_config_path.resolve()
    parent_checkpoint_path = parent_checkpoint_path.resolve()
    parent_lineage_path = parent_lineage_path.resolve()
    config = _load_json(config_path)
    if config.get("schema") != ADJUSTMENT_LINEAGE_SCHEMA:
        raise ValueError("checkpoint adjustment config schema mismatch")
    parent = validate_lineage_manifest(
        manifest_path=parent_lineage_path,
        config_path=parent_config_path,
        checkpoint_path=parent_checkpoint_path,
    )
    expected_parent = config.get("parent", {})
    if (
        expected_parent.get("checkpoint_sha256") != parent["checkpoint_sha256"]
        or expected_parent.get("lineage_reproducibility_sha256")
        != parent["lineage_reproducibility_sha256"]
    ):
        raise ValueError("checkpoint adjustment parent lineage mismatch")

    model = SelectorActorCritic(int(config["model_init_seed"]))
    payload = load_checkpoint(parent_checkpoint_path, model)
    adjustment = config.get("adjustment", {})
    state = adjust_model_state(
        payload["model_state"],
        tensor_name=str(adjustment.get("tensor")),
        index=int(adjustment.get("index", -1)),
        delta=float(adjustment.get("delta", 0.0)),
    )
    config_sha256 = _sha256(config_path)
    model_state_sha256 = _model_state_digest(state)
    checkpoint = {
        "checkpoint_kind": "single_logit_bias_adjustment_v1",
        "feature_schema": FEATURE_SCHEMA,
        "reward_schema": REWARD_SCHEMA,
        "model_schema": MODEL_SCHEMA,
        "config_sha256": config_sha256,
        "parent_checkpoint": parent["checkpoint_sha256"],
        "parent_lineage_reproducibility_sha256": parent[
            "lineage_reproducibility_sha256"
        ],
        "update": 0,
        "model_state_sha256": model_state_sha256,
        "model_state": state,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, output_path)
    checkpoint_sha256 = _sha256(output_path)
    manifest = {
        "schema": ADJUSTMENT_LINEAGE_SCHEMA,
        "source_config": {
            "path": str(config_path.relative_to(root)).replace("\\", "/"),
            "sha256": config_sha256,
        },
        "repository": repository,
        "schemas": {
            "feature": FEATURE_SCHEMA,
            "reward": REWARD_SCHEMA,
            "model": MODEL_SCHEMA,
        },
        "model_init_seed": int(config["model_init_seed"]),
        "parent": {
            "checkpoint_path": str(parent_checkpoint_path),
            "checkpoint_sha256": parent["checkpoint_sha256"],
            "checkpoint_model_state_sha256": parent[
                "checkpoint_model_state_sha256"
            ],
            "lineage_manifest_path": str(parent_lineage_path),
            "lineage_manifest_sha256": parent["manifest_sha256"],
            "lineage_reproducibility_sha256": parent[
                "lineage_reproducibility_sha256"
            ],
            "source_config_sha256": parent["source_config_sha256"],
        },
        "adjustment": {
            "tensor": str(adjustment["tensor"]),
            "index": int(adjustment["index"]),
            "delta": float(adjustment["delta"]),
        },
        "checkpoint": {
            "path": str(output_path),
            "sha256": checkpoint_sha256,
            "model_state_sha256": model_state_sha256,
        },
    }
    digest = _json_digest(_adjustment_lineage_evidence(manifest))
    manifest["lineage_reproducibility"] = {
        "schema": ADJUSTMENT_LINEAGE_REPRODUCIBILITY_SCHEMA,
        "digest": digest,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"checkpoint={checkpoint_sha256[:16]} "
        f"model_state={model_state_sha256[:16]} lineage={digest[:16]}"
    )
    print("M8-CHECKPOINT-ADJUSTMENT OK")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construct the V8 WAIT adjustment")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--parent-config", type=Path, required=True)
    parser.add_argument("--parent-checkpoint", type=Path, required=True)
    parser.add_argument("--parent-lineage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args(argv)
    construct_adjusted_checkpoint(
        config_path=args.config,
        parent_config_path=args.parent_config,
        parent_checkpoint_path=args.parent_checkpoint,
        parent_lineage_path=args.parent_lineage,
        output_path=args.output,
        manifest_path=args.manifest_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
