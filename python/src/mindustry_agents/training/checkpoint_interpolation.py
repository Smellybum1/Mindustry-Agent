"""Deterministic, manifest-verified construction of an M8.5 selector checkpoint."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.training.model import SelectorActorCritic
from mindustry_agents.training.ppo_selector import (
    FEATURE_SCHEMA,
    MODEL_SCHEMA,
    REWARD_SCHEMA,
    _git_evidence,
    _json_digest,
    _model_state_digest,
    _reproducibility_evidence,
    _sha256,
    load_checkpoint,
)
from mindustry_agents.process.launcher import repo_root

INTERPOLATION_SCHEMA = "selector_checkpoint_interpolation_v1"
CHECKPOINT_KIND = "weighted_model_interpolation_v1"
ALLOWED_DIRTY_PATHS = frozenset(
    {
        "AGENTS.md",
        "annotations/src/main/resources/classids.properties",
        "core/src/mindustry/ai/BlockIndexer.java",
        "core/src/mindustry/entities/Units.java",
    }
)


@dataclass(frozen=True)
class ParentEvidence:
    role: str
    weight: float
    update: int
    checkpoint_path: Path
    checkpoint_sha256: str
    checkpoint_model_state_sha256: str
    manifest_path: Path
    manifest_sha256: str
    manifest_reproducibility_sha256: str
    training_config_path: Path
    training_config_sha256: str
    initial_model_state_sha256: str
    repository_commit: str
    state: dict[str, torch.Tensor]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def _unexpected_dirty(status: list[str]) -> list[str]:
    return [
        line
        for line in status
        if line[3:].replace("\\", "/") not in ALLOWED_DIRTY_PATHS
    ]


def _validate_construction_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    if config.get("schema") != INTERPOLATION_SCHEMA:
        raise ValueError("interpolation config schema mismatch")
    parents = config.get("checkpoint_construction", {}).get("parents", [])
    if [item.get("role") for item in parents] != ["base", "auxiliary"]:
        raise ValueError("interpolation parents must be ordered base, auxiliary")
    weights = [float(item.get("weight", -1.0)) for item in parents]
    if any(weight <= 0.0 or weight >= 1.0 for weight in weights):
        raise ValueError(
            "interpolation parent weights must be strictly between 0 and 1"
        )
    if abs(sum(weights) - 1.0) > 1e-12:
        raise ValueError("interpolation parent weights must sum to 1")
    if any(int(item.get("update", 0)) < 1 for item in parents):
        raise ValueError("interpolation parent updates must be positive")
    return parents


def _manifest_reproducibility_digest(manifest: dict[str, Any]) -> str:
    if manifest.get("schema") != "selector_training_run_v1":
        raise ValueError("parent training manifest schema mismatch")
    digest = _json_digest(_reproducibility_evidence(manifest))
    recorded = manifest.get("full_run_reproducibility", {}).get("digest")
    if recorded != digest:
        raise ValueError("parent training manifest reproducibility digest mismatch")
    return digest


def _load_parent(
    *,
    root: Path,
    construction: dict[str, Any],
    spec: dict[str, Any],
    checkpoint_path: Path,
    manifest_path: Path,
) -> ParentEvidence:
    role = str(spec["role"])
    checkpoint_path = checkpoint_path.resolve()
    manifest_path = manifest_path.resolve()
    training_config_path = (root / str(spec["training_config"])).resolve()
    manifest = _load_json(manifest_path)
    manifest_digest = _manifest_reproducibility_digest(manifest)
    training_config_sha256 = _sha256(training_config_path)
    source_config = manifest.get("source_config", {})
    if source_config.get("path") != _relative(training_config_path, root):
        raise ValueError(f"{role} manifest training config path mismatch")
    if source_config.get("sha256") != training_config_sha256:
        raise ValueError(f"{role} manifest training config hash mismatch")

    model_seed = int(construction["model_init_seed"])
    model = SelectorActorCritic(model_seed)
    checkpoint = load_checkpoint(checkpoint_path, model)
    checkpoint_sha256 = _sha256(checkpoint_path)
    update = int(spec["update"])
    if checkpoint.get("config_sha256") != training_config_sha256:
        raise ValueError(f"{role} checkpoint training config hash mismatch")
    if int(checkpoint.get("update", 0)) != update:
        raise ValueError(f"{role} checkpoint update mismatch")
    selection = [
        item
        for item in manifest.get("dev_checkpoint_selection", [])
        if int(item.get("update", 0)) == update
    ]
    if (
        len(selection) != 1
        or selection[0].get("checkpoint_sha256") != checkpoint_sha256
    ):
        raise ValueError(f"{role} checkpoint is absent from parent dev evidence")

    if int(manifest.get("rng_seeds", {}).get("model_init_seed", -1)) != model_seed:
        raise ValueError(f"{role} model initialization seed mismatch")
    if manifest.get("model_architecture") != construction.get("model_architecture"):
        raise ValueError(f"{role} model architecture mismatch")
    repository = manifest.get("repository", {})
    if repository.get("commit") != construction["active_repository_commit"]:
        raise ValueError(f"{role} repository commit mismatch")
    unexpected_dirty = _unexpected_dirty(list(repository.get("status", [])))
    if unexpected_dirty:
        raise ValueError(f"{role} parent run has unexpected repository dirt")

    return ParentEvidence(
        role=role,
        weight=float(spec["weight"]),
        update=update,
        checkpoint_path=checkpoint_path,
        checkpoint_sha256=checkpoint_sha256,
        checkpoint_model_state_sha256=_model_state_digest(checkpoint["model_state"]),
        manifest_path=manifest_path,
        manifest_sha256=_sha256(manifest_path),
        manifest_reproducibility_sha256=manifest_digest,
        training_config_path=training_config_path,
        training_config_sha256=training_config_sha256,
        initial_model_state_sha256=str(manifest["initial_model_state_sha256"]),
        repository_commit=str(repository["commit"]),
        state=checkpoint["model_state"],
    )


def interpolate_model_states(
    parents: list[ParentEvidence],
) -> dict[str, torch.Tensor]:
    """Interpolate aligned state dictionaries in the governed parent order."""

    if len(parents) != 2:
        raise ValueError("exactly two interpolation parents are required")
    names = list(parents[0].state)
    if any(list(parent.state) != names for parent in parents[1:]):
        raise ValueError("parent model state keys or ordering differ")
    output: dict[str, torch.Tensor] = {}
    for name in names:
        tensors = [parent.state[name].detach().cpu() for parent in parents]
        first = tensors[0]
        if any(
            tensor.shape != first.shape or tensor.dtype != first.dtype
            for tensor in tensors[1:]
        ):
            raise ValueError(f"parent tensor schema differs for {name}")
        if first.is_floating_point():
            value = tensors[0] * parents[0].weight
            for parent, tensor in zip(parents[1:], tensors[1:]):
                value = value + tensor * parent.weight
            output[name] = value
        else:
            if any(not torch.equal(first, tensor) for tensor in tensors[1:]):
                raise ValueError(f"non-floating parent tensor differs for {name}")
            output[name] = first.clone()
    return output


def _lineage_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": manifest["schema"],
        "source_config_sha256": manifest["source_config"]["sha256"],
        "repository_commit": manifest["repository"]["commit"],
        "schemas": manifest["schemas"],
        "model_init_seed": manifest["model_init_seed"],
        "initial_model_state_sha256": manifest["initial_model_state_sha256"],
        "parents": [
            {
                key: parent[key]
                for key in (
                    "role",
                    "weight",
                    "update",
                    "checkpoint_sha256",
                    "checkpoint_model_state_sha256",
                    "manifest_reproducibility_sha256",
                    "training_config_sha256",
                )
            }
            for parent in manifest["parents"]
        ],
        "checkpoint_model_state_sha256": manifest["checkpoint"][
            "model_state_sha256"
        ],
        "checkpoint_sha256": manifest["checkpoint"]["sha256"],
    }


def construct_checkpoint(
    *,
    root: Path,
    config_path: Path,
    base_checkpoint: Path,
    base_manifest: Path,
    auxiliary_checkpoint: Path,
    auxiliary_manifest: Path,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path.resolve()
    config = _load_json(config_path)
    specs = _validate_construction_config(config)
    repository = _git_evidence(root)
    unexpected_dirty = _unexpected_dirty(repository["status"])
    if unexpected_dirty:
        raise ValueError("checkpoint construction requires a frozen repository")
    construction = config | {"active_repository_commit": repository["commit"]}

    paths = (
        (base_checkpoint, base_manifest),
        (auxiliary_checkpoint, auxiliary_manifest),
    )
    parents = [
        _load_parent(
            root=root,
            construction=construction,
            spec=spec,
            checkpoint_path=checkpoint,
            manifest_path=parent_manifest,
        )
        for spec, (checkpoint, parent_manifest) in zip(specs, paths)
    ]
    initial_digests = {parent.initial_model_state_sha256 for parent in parents}
    if len(initial_digests) != 1:
        raise ValueError("parent initial model states are not aligned")
    expected_initial = _model_state_digest(
        SelectorActorCritic(int(config["model_init_seed"])).state_dict()
    )
    if initial_digests != {expected_initial}:
        raise ValueError("parent initial model state does not match current model")

    state = interpolate_model_states(parents)
    model_state_sha256 = _model_state_digest(state)
    config_sha256 = _sha256(config_path)
    parent_rows = [
        {
            "role": parent.role,
            "weight": parent.weight,
            "update": parent.update,
            "checkpoint_sha256": parent.checkpoint_sha256,
            "checkpoint_model_state_sha256": parent.checkpoint_model_state_sha256,
            "manifest_reproducibility_sha256": (
                parent.manifest_reproducibility_sha256
            ),
            "training_config_sha256": parent.training_config_sha256,
        }
        for parent in parents
    ]
    checkpoint = {
        "checkpoint_kind": CHECKPOINT_KIND,
        "feature_schema": FEATURE_SCHEMA,
        "reward_schema": REWARD_SCHEMA,
        "model_schema": MODEL_SCHEMA,
        "config_sha256": config_sha256,
        "parent_checkpoint": [parent.checkpoint_sha256 for parent in parents],
        "parents": parent_rows,
        "update": 0,
        "model_state_sha256": model_state_sha256,
        "model_state": state,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, output_path)
    checkpoint_sha256 = _sha256(output_path)

    manifest = {
        "schema": INTERPOLATION_SCHEMA,
        "source_config": {
            "path": _relative(config_path, root),
            "sha256": config_sha256,
        },
        "repository": repository,
        "schemas": {
            "feature": FEATURE_SCHEMA,
            "reward": REWARD_SCHEMA,
            "model": MODEL_SCHEMA,
        },
        "model_init_seed": int(config["model_init_seed"]),
        "initial_model_state_sha256": expected_initial,
        "parents": [
            row
            | {
                "checkpoint_path": _relative(parent.checkpoint_path, root),
                "manifest_path": _relative(parent.manifest_path, root),
                "manifest_sha256": parent.manifest_sha256,
                "training_config_path": _relative(
                    parent.training_config_path, root
                ),
            }
            for row, parent in zip(parent_rows, parents)
        ],
        "checkpoint": {
            "path": _relative(output_path, root),
            "sha256": checkpoint_sha256,
            "model_state_sha256": model_state_sha256,
        },
    }
    lineage_digest = _json_digest(_lineage_evidence(manifest))
    manifest["lineage_reproducibility"] = {
        "schema": "selector_checkpoint_lineage_reproducibility_v1",
        "digest": lineage_digest,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"checkpoint={checkpoint_sha256[:16]} "
        f"model_state={model_state_sha256[:16]} lineage={lineage_digest[:16]}"
    )
    print("M8-CHECKPOINT-INTERPOLATION OK")
    return manifest


def compare_lineage_manifests(first: Path, second: Path) -> str:
    manifests = [_load_json(path) for path in (first, second)]
    evidence = [_lineage_evidence(manifest) for manifest in manifests]
    digests = [_json_digest(item) for item in evidence]
    recorded = [
        manifest.get("lineage_reproducibility", {}).get("digest")
        for manifest in manifests
    ]
    if recorded != digests:
        raise RuntimeError("lineage reproducibility digest is missing or invalid")
    if evidence[0] != evidence[1]:
        raise RuntimeError("independent checkpoint constructions diverged")
    print(f"lineage_reproducibility={digests[0][:16]} bit_exact=True")
    print("M8-CHECKPOINT-INTERPOLATION-REPRODUCIBILITY OK")
    return digests[0]


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description="Construct the M8.5 checkpoint")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--base-checkpoint", type=Path)
    parser.add_argument("--base-manifest", type=Path)
    parser.add_argument("--auxiliary-checkpoint", type=Path)
    parser.add_argument("--auxiliary-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument(
        "--compare-manifests", nargs=2, type=Path, metavar=("FIRST", "SECOND")
    )
    args = parser.parse_args(argv)
    if args.compare_manifests:
        compare_lineage_manifests(*args.compare_manifests)
        return 0
    required = {
        "config": args.config,
        "base checkpoint": args.base_checkpoint,
        "base manifest": args.base_manifest,
        "auxiliary checkpoint": args.auxiliary_checkpoint,
        "auxiliary manifest": args.auxiliary_manifest,
        "output": args.output,
        "manifest output": args.manifest_output,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error("missing required construction arguments: " + ", ".join(missing))
    construct_checkpoint(
        root=root,
        config_path=args.config,
        base_checkpoint=args.base_checkpoint,
        base_manifest=args.base_manifest,
        auxiliary_checkpoint=args.auxiliary_checkpoint,
        auxiliary_manifest=args.auxiliary_manifest,
        output_path=args.output,
        manifest_path=args.manifest_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
