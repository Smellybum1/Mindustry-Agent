"""Govern direct reproducible checkpoints and legacy interpolated lineages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.checkpoint_interpolation import (
    ALLOWED_DIRTY_PATHS,
    INTERPOLATION_SCHEMA,
    validate_lineage_manifest as validate_interpolation_lineage,
)
from mindustry_agents.training.model import build_selector_model
from mindustry_agents.training.ppo_selector import (
    LEARNED_SEAT_FAILOVER_SCHEMA,
    REWARD_SCHEMA,
    _git_evidence,
    _json_digest,
    _learned_seat_failover,
    _model_state_digest,
    _reproducibility_evidence,
    _sha256,
    _validated_reproducibility_digest,
    load_checkpoint,
)
from mindustry_agents.training.selector import (
    CONTROL_SCHEMA_V2,
    expected_control_schema,
    expected_feature_schema,
)

DIRECT_LINEAGE_SCHEMA = "selector_checkpoint_direct_lineage_v1"
DIRECT_LINEAGE_REPRODUCIBILITY_SCHEMA = (
    "selector_checkpoint_direct_lineage_reproducibility_v1"
)
ADJUSTMENT_LINEAGE_SCHEMA = "selector_checkpoint_logit_adjustment_v1"
ADJUSTMENT_LINEAGE_REPRODUCIBILITY_SCHEMA = (
    "selector_checkpoint_logit_adjustment_reproducibility_v1"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _unexpected_dirty(status: list[str]) -> list[str]:
    return [
        line
        for line in status
        if line[3:].replace("\\", "/") not in ALLOWED_DIRTY_PATHS
    ]


def _run_reproducibility_digest(manifest: dict[str, Any]) -> str:
    if manifest.get("schema") != "selector_training_run_v1":
        raise ValueError("training manifest schema mismatch")
    try:
        return _validated_reproducibility_digest(manifest)
    except ValueError as error:
        raise ValueError("training manifest reproducibility digest mismatch") from error


def _expected_lineage_schemas(config: dict[str, Any]) -> dict[str, str]:
    """Return the exact schema coordinate recorded by a governed training run."""

    control_schema = expected_control_schema(config)
    learned_seat_failover = _learned_seat_failover(config)
    return {
        "feature": expected_feature_schema(config),
        "reward": str(config.get("reward_schema", REWARD_SCHEMA)),
        "model": build_selector_model(config).model_schema,
        **(
            {"control": control_schema}
            if control_schema == CONTROL_SCHEMA_V2
            else {}
        ),
        **(
            {"seat_control": LEARNED_SEAT_FAILOVER_SCHEMA}
            if learned_seat_failover is not None
            else {}
        ),
    }


def _direct_lineage_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": manifest["schema"],
        "source_config_sha256": manifest["source_config"]["sha256"],
        "training_repository_commit": manifest["training_repository_commit"],
        "schemas": manifest["schemas"],
        "model_init_seed": manifest["model_init_seed"],
        "selected_update": manifest["selected_update"],
        "runs": [
            {
                key: run[key]
                for key in (
                    "manifest_sha256",
                    "full_run_reproducibility_sha256",
                    "checkpoint_sha256",
                    "checkpoint_model_state_sha256",
                )
            }
            for run in manifest["runs"]
        ],
        "checkpoint_sha256": manifest["checkpoint"]["sha256"],
        "checkpoint_model_state_sha256": manifest["checkpoint"][
            "model_state_sha256"
        ],
    }


def _adjustment_lineage_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": manifest["schema"],
        "source_config_sha256": manifest["source_config"]["sha256"],
        "repository_commit": manifest["repository"]["commit"],
        "schemas": manifest["schemas"],
        "model_init_seed": manifest["model_init_seed"],
        "parent": {
            key: manifest["parent"][key]
            for key in (
                "checkpoint_sha256",
                "checkpoint_model_state_sha256",
                "lineage_reproducibility_sha256",
                "source_config_sha256",
            )
        },
        "adjustment": manifest["adjustment"],
        "checkpoint_sha256": manifest["checkpoint"]["sha256"],
        "checkpoint_model_state_sha256": manifest["checkpoint"][
            "model_state_sha256"
        ],
    }


def build_direct_lineage(
    *,
    config_path: Path,
    checkpoint_paths: tuple[Path, Path],
    manifest_paths: tuple[Path, Path],
    repository: dict[str, Any],
) -> dict[str, Any]:
    """Validate two exact training replicas and describe one selected checkpoint."""

    config_path = config_path.resolve()
    checkpoint_paths = tuple(path.resolve() for path in checkpoint_paths)
    manifest_paths = tuple(path.resolve() for path in manifest_paths)
    config = _load_json(config_path)
    config_sha256 = _sha256(config_path)
    manifests = [_load_json(path) for path in manifest_paths]
    run_digests = [_run_reproducibility_digest(item) for item in manifests]
    if run_digests[0] != run_digests[1]:
        raise ValueError("independent training manifests diverge")
    if _reproducibility_evidence(manifests[0]) != _reproducibility_evidence(
        manifests[1]
    ):
        raise ValueError("independent training evidence diverges")

    source_paths = [item.get("source_config", {}).get("path") for item in manifests]
    source_hashes = [
        item.get("source_config", {}).get("sha256") for item in manifests
    ]
    if len(set(source_paths)) != 1 or source_hashes != [config_sha256, config_sha256]:
        raise ValueError("training config lineage mismatch")

    expected_schemas = _expected_lineage_schemas(config)
    if any(item.get("schemas") != expected_schemas for item in manifests):
        raise ValueError("training manifest schema mismatch")

    training_commits = [item.get("repository", {}).get("commit") for item in manifests]
    if len(set(training_commits)) != 1 or not training_commits[0]:
        raise ValueError("training repository commits differ")
    for manifest in manifests:
        if _unexpected_dirty(list(manifest.get("repository", {}).get("status", []))):
            raise ValueError("training run has unexpected repository dirt")

    checkpoint_hashes = [_sha256(path) for path in checkpoint_paths]
    if checkpoint_hashes[0] != checkpoint_hashes[1]:
        raise ValueError("independent selected checkpoints diverge")
    selected_updates = [
        int(item.get("checkpoint", {}).get("update", 0)) for item in manifests
    ]
    if len(set(selected_updates)) != 1 or selected_updates[0] < 1:
        raise ValueError("selected checkpoint updates differ")
    for manifest, checkpoint_hash in zip(manifests, checkpoint_hashes):
        if manifest.get("checkpoint", {}).get("sha256") != checkpoint_hash:
            raise ValueError("selected checkpoint is absent from training manifest")

    model_state_hashes: list[str] = []
    for checkpoint_path in checkpoint_paths:
        model = build_selector_model(config)
        checkpoint = load_checkpoint(
            checkpoint_path,
            model,
            reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
            feature_schema=expected_feature_schema(config),
        )
        if checkpoint.get("config_sha256") != config_sha256:
            raise ValueError("selected checkpoint config hash mismatch")
        if int(checkpoint.get("update", 0)) != selected_updates[0]:
            raise ValueError("selected checkpoint update mismatch")
        model_state_hashes.append(_model_state_digest(checkpoint["model_state"]))
    if model_state_hashes[0] != model_state_hashes[1]:
        raise ValueError("independent checkpoint model states diverge")

    runs = [
        {
            "role": role,
            "manifest_path": str(manifest_path),
            "manifest_sha256": _sha256(manifest_path),
            "full_run_reproducibility_sha256": run_digest,
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": checkpoint_hash,
            "checkpoint_model_state_sha256": model_state_hash,
        }
        for (
            role,
            manifest_path,
            run_digest,
            checkpoint_path,
            checkpoint_hash,
            model_state_hash,
        ) in zip(
            ("replica-a", "replica-b"),
            manifest_paths,
            run_digests,
            checkpoint_paths,
            checkpoint_hashes,
            model_state_hashes,
        )
    ]
    manifest = {
        "schema": DIRECT_LINEAGE_SCHEMA,
        "source_config": {
            "path": source_paths[0],
            "sha256": config_sha256,
        },
        "repository": repository,
        "training_repository_commit": training_commits[0],
        "schemas": manifests[0]["schemas"],
        "model_init_seed": int(config["model_init_seed"]),
        "selected_update": selected_updates[0],
        "runs": runs,
        "checkpoint": {
            "path": str(checkpoint_paths[0]),
            "sha256": checkpoint_hashes[0],
            "model_state_sha256": model_state_hashes[0],
        },
    }
    digest = _json_digest(_direct_lineage_evidence(manifest))
    manifest["lineage_reproducibility"] = {
        "schema": DIRECT_LINEAGE_REPRODUCIBILITY_SCHEMA,
        "digest": digest,
    }
    return manifest


def construct_direct_lineage(
    *,
    config_path: Path,
    checkpoint_paths: tuple[Path, Path],
    manifest_paths: tuple[Path, Path],
    output_path: Path,
) -> dict[str, Any]:
    root = repo_root()
    repository = _git_evidence(root)
    if _unexpected_dirty(repository["status"]):
        raise ValueError("direct checkpoint lineage requires a frozen repository")
    manifest = build_direct_lineage(
        config_path=config_path,
        checkpoint_paths=checkpoint_paths,
        manifest_paths=manifest_paths,
        repository=repository,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"checkpoint={manifest['checkpoint']['sha256'][:16]} "
        f"lineage={manifest['lineage_reproducibility']['digest'][:16]}"
    )
    print("M8-DIRECT-CHECKPOINT-LINEAGE OK")
    return manifest


def validate_lineage_manifest(
    *,
    manifest_path: Path,
    config_path: Path,
    checkpoint_path: Path,
) -> dict[str, Any]:
    """Validate either a legacy interpolation or direct reproducible lineage."""

    manifest_path = manifest_path.resolve()
    manifest = _load_json(manifest_path)
    if manifest.get("schema") == INTERPOLATION_SCHEMA:
        return validate_interpolation_lineage(
            manifest_path=manifest_path,
            config_path=config_path,
            checkpoint_path=checkpoint_path,
        )
    if manifest.get("schema") == ADJUSTMENT_LINEAGE_SCHEMA:
        digest = _json_digest(_adjustment_lineage_evidence(manifest))
        if manifest.get("lineage_reproducibility", {}).get("digest") != digest:
            raise ValueError("checkpoint adjustment reproducibility digest mismatch")
        config_path = config_path.resolve()
        checkpoint_path = checkpoint_path.resolve()
        config_sha256 = _sha256(config_path)
        if manifest.get("source_config", {}).get("sha256") != config_sha256:
            raise ValueError("checkpoint adjustment config hash mismatch")
        checkpoint_sha256 = _sha256(checkpoint_path)
        if manifest.get("checkpoint", {}).get("sha256") != checkpoint_sha256:
            raise ValueError("checkpoint adjustment artifact hash mismatch")
        config = _load_json(config_path)
        model = build_selector_model(config)
        checkpoint = load_checkpoint(
            checkpoint_path,
            model,
            reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
            feature_schema=expected_feature_schema(config),
        )
        if checkpoint.get("config_sha256") != config_sha256:
            raise ValueError("adjusted checkpoint config hash mismatch")
        model_state_sha256 = _model_state_digest(checkpoint["model_state"])
        if manifest["checkpoint"].get("model_state_sha256") != model_state_sha256:
            raise ValueError("checkpoint adjustment model state hash mismatch")
        return {
            "manifest_path": str(manifest_path),
            "manifest_sha256": _sha256(manifest_path),
            "lineage_reproducibility_sha256": digest,
            "checkpoint_sha256": checkpoint_sha256,
            "checkpoint_model_state_sha256": model_state_sha256,
            "source_config_sha256": config_sha256,
            "repository_commit": manifest["repository"]["commit"],
            "parents": [manifest["parent"]],
        }
    if manifest.get("schema") != DIRECT_LINEAGE_SCHEMA:
        raise ValueError("checkpoint lineage manifest schema mismatch")

    digest = _json_digest(_direct_lineage_evidence(manifest))
    if manifest.get("lineage_reproducibility", {}).get("digest") != digest:
        raise ValueError("checkpoint lineage reproducibility digest mismatch")
    config_path = config_path.resolve()
    checkpoint_path = checkpoint_path.resolve()
    config_sha256 = _sha256(config_path)
    if manifest.get("source_config", {}).get("sha256") != config_sha256:
        raise ValueError("checkpoint lineage config hash mismatch")
    checkpoint_sha256 = _sha256(checkpoint_path)
    if manifest.get("checkpoint", {}).get("sha256") != checkpoint_sha256:
        raise ValueError("checkpoint lineage artifact hash mismatch")
    config = _load_json(config_path)
    model = build_selector_model(config)
    checkpoint = load_checkpoint(
        checkpoint_path,
        model,
        reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
        feature_schema=expected_feature_schema(config),
    )
    if checkpoint.get("config_sha256") != config_sha256:
        raise ValueError("direct checkpoint config hash mismatch")
    model_state_sha256 = _model_state_digest(checkpoint["model_state"])
    if manifest["checkpoint"].get("model_state_sha256") != model_state_sha256:
        raise ValueError("checkpoint lineage model state hash mismatch")
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "lineage_reproducibility_sha256": digest,
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_model_state_sha256": model_state_sha256,
        "source_config_sha256": config_sha256,
        "repository_commit": manifest["repository"]["commit"],
        "training_repository_commit": manifest["training_repository_commit"],
        "parents": manifest["runs"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Govern a direct checkpoint from two reproducible runs"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint-a", type=Path, required=True)
    parser.add_argument("--manifest-a", type=Path, required=True)
    parser.add_argument("--checkpoint-b", type=Path, required=True)
    parser.add_argument("--manifest-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    construct_direct_lineage(
        config_path=args.config.resolve(),
        checkpoint_paths=(args.checkpoint_a.resolve(), args.checkpoint_b.resolve()),
        manifest_paths=(args.manifest_a.resolve(), args.manifest_b.resolve()),
        output_path=args.output.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
