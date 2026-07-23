"""M9 IPPO checkpoint, lineage, and reproducibility artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from typing import Any

import torch

from mindustry_agents import ENGINE_COMMIT, ENGINE_TAG, PROTOCOL_VERSION
from mindustry_agents.process.launcher import DEFAULT_JVM_ARGS, repo_root
from mindustry_agents.training.ippo import (
    IPPO_MODEL_ARCHITECTURE,
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V1_CONFIG_SHA256,
    IPPO_V1_PROTOCOL_SHA256,
    load_ippo_v1_config,
    sha256_path,
)

ARC_HASH = "208a754044"
CHECKPOINT_SCHEMA = "m9_ippo_checkpoint_v1"
RUN_MANIFEST_SCHEMA = "m9_ippo_training_run_v1"
REPRODUCIBILITY_SCHEMA = "m9_ippo_full_run_reproducibility_v1"


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _state_digest(value: Any) -> str:
    digest = hashlib.sha256()

    def visit(item: Any) -> None:
        if isinstance(item, torch.Tensor):
            tensor = item.detach().cpu().contiguous()
            digest.update(b"tensor\0")
            digest.update(str(tensor.dtype).encode("ascii"))
            digest.update(b"\0")
            digest.update(json.dumps(list(tensor.shape)).encode("ascii"))
            digest.update(b"\0")
            digest.update(tensor.numpy().tobytes())
        elif isinstance(item, dict):
            digest.update(b"dict\0")
            for key in sorted(item, key=lambda candidate: str(candidate)):
                visit(key)
                visit(item[key])
        elif isinstance(item, (list, tuple)):
            digest.update(b"sequence\0")
            for child in item:
                visit(child)
        elif item is None or isinstance(item, (str, int, float, bool)):
            digest.update(
                json.dumps(
                    item, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
            )
            digest.update(b"\0")
        else:
            raise TypeError(f"unsupported checkpoint state value: {type(item)!r}")

    visit(value)
    return digest.hexdigest()


def save_ippo_checkpoint(
    path: Path,
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    *,
    update: int,
    parent_checkpoint_content_sha256: str | None,
) -> dict[str, Any]:
    if update < 0:
        raise ValueError("M9 IPPO checkpoint update cannot be negative")
    optimizer_state = optimizer.state_dict()
    identity = {
        "schema": CHECKPOINT_SCHEMA,
        "config_sha256": IPPO_V1_CONFIG_SHA256,
        "reward_schema": "ippo_reward_v1",
        "model_schema": model.model_schema,
        "model_architecture": IPPO_MODEL_ARCHITECTURE,
        "update": update,
        "parent_checkpoint_content_sha256": parent_checkpoint_content_sha256,
        "model_state_sha256": model_state_digest(model),
        "optimizer_state_sha256": _state_digest(optimizer_state),
    }
    payload = {
        **identity,
        "checkpoint_content_sha256": _json_digest(identity),
        "model_state": model.state_dict(),
        "optimizer_state": optimizer_state,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    # The default ZIP archive embeds filename-dependent container details.
    # Legacy serialization is stable across output paths for the same ordered
    # tensor/state payload, which lets raw checkpoint SHA participate in direct
    # lineage evidence.
    torch.save(payload, temporary, _use_new_zipfile_serialization=False)
    temporary.replace(path)
    return {
        "path": path,
        "file_sha256": sha256_path(path),
        "checkpoint_content_sha256": payload["checkpoint_content_sha256"],
        "model_state_sha256": payload["model_state_sha256"],
        "optimizer_state_sha256": payload["optimizer_state_sha256"],
        "update": update,
        "parent_checkpoint_content_sha256": parent_checkpoint_content_sha256,
    }


def load_ippo_checkpoint(
    path: Path,
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    expected = (
        CHECKPOINT_SCHEMA,
        IPPO_V1_CONFIG_SHA256,
        "ippo_reward_v1",
        model.model_schema,
        IPPO_MODEL_ARCHITECTURE,
    )
    actual = (
        payload.get("schema"),
        payload.get("config_sha256"),
        payload.get("reward_schema"),
        payload.get("model_schema"),
        payload.get("model_architecture"),
    )
    if actual != expected:
        raise ValueError("M9 IPPO checkpoint schema/config mismatch")
    if int(payload.get("update", -1)) < 0:
        raise ValueError("M9 IPPO checkpoint update is invalid")
    identity = {
        key: payload[key]
        for key in (
            "schema",
            "config_sha256",
            "reward_schema",
            "model_schema",
            "model_architecture",
            "update",
            "parent_checkpoint_content_sha256",
            "model_state_sha256",
            "optimizer_state_sha256",
        )
    }
    if _json_digest(identity) != payload.get("checkpoint_content_sha256"):
        raise ValueError("M9 IPPO checkpoint content digest mismatch")
    candidate = SharedRecurrentSelector(9601)
    candidate.load_state_dict(payload["model_state"])
    if model_state_digest(candidate) != payload.get("model_state_sha256"):
        raise ValueError("M9 IPPO checkpoint model digest mismatch")
    if _state_digest(payload["optimizer_state"]) != payload.get(
        "optimizer_state_sha256"
    ):
        raise ValueError("M9 IPPO checkpoint optimizer digest mismatch")
    model.load_state_dict(payload["model_state"])
    if model_state_digest(model) != payload["model_state_sha256"]:
        raise ValueError("M9 IPPO loaded model digest mismatch")
    if optimizer is not None:
        optimizer.load_state_dict(payload["optimizer_state"])
    return payload


def _git_evidence(root: Path) -> dict[str, Any]:
    def run(*arguments: str, strip: bool = True) -> str:
        output = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return output.strip() if strip else output

    status = run("status", "--short", strip=False).splitlines()
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(status), "status": status}


def reproducibility_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "engine",
        "protocol_version",
        "scenario",
        "runtime",
        "source_config",
        "public_protocol",
        "public_baseline",
        "seed_sets",
        "rng_seeds",
        "model_architecture",
        "optimizer_ppo",
        "budget",
        "initial_model_state_sha256",
        "optimizer_updates",
        "checkpoint_selection",
        "train",
        "dev",
        "deterministic_checkpoint_verification",
    )
    evidence = {key: copy.deepcopy(manifest[key]) for key in keys}
    for key in (
        "pretraining_gate",
        "public_comparison",
        "construction_passed",
        "mappo_statistical_thresholds_passed",
        "failure",
        "selected_checkpoint_payload_update",
    ):
        if key in manifest:
            evidence[key] = copy.deepcopy(manifest[key])
    checkpoint = manifest["selected_checkpoint"]
    evidence["selected_checkpoint"] = (
        {
            key: checkpoint[key]
            for key in (
                "update",
                "parent_checkpoint_content_sha256",
                "model_state_sha256",
                "optimizer_state_sha256",
            )
        }
        if checkpoint is not None
        else None
    )
    return evidence


def finalize_run_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(manifest)
    digest = _json_digest(reproducibility_evidence(result))
    result["full_run_reproducibility"] = {
        "schema": REPRODUCIBILITY_SCHEMA,
        "digest": digest,
        "bit_exact": True,
    }
    return result


def compare_ippo_run_manifests(first: Path, second: Path) -> str:
    manifests = [
        json.loads(path.read_text(encoding="utf-8")) for path in (first, second)
    ]
    evidence = [reproducibility_evidence(item) for item in manifests]
    digests = [_json_digest(item) for item in evidence]
    for manifest, digest in zip(manifests, digests, strict=True):
        if manifest.get("full_run_reproducibility", {}).get("digest") != digest:
            raise ValueError("M9 IPPO manifest reproducibility digest is invalid")
    if evidence[0] != evidence[1]:
        raise RuntimeError(
            "M9 IPPO independent runs diverged: "
            f"{digests[0][:16]} != {digests[1][:16]}"
        )
    return digests[0]


def base_run_manifest(
    config_path: Path,
    *,
    initial_model_state_sha256: str,
    train_seed_set: dict[str, Any],
    dev_seed_set: dict[str, Any],
    baseline_path: Path,
) -> dict[str, Any]:
    root = repo_root()
    config = load_ippo_v1_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V1_PROTOCOL_SHA256:
        raise ValueError("M9 IPPO public protocol hash drifted")
    lock_path = root / "python/requirements-rl-linux-py312.lock"
    jar_path = root / "rl-server/build/libs/rl-server.jar"
    return {
        "schema": RUN_MANIFEST_SCHEMA,
        "engine": {"tag": ENGINE_TAG, "commit": ENGINE_COMMIT, "arc": ARC_HASH},
        "protocol_version": PROTOCOL_VERSION,
        "scenario": {
            "id": config["scenario_id"],
            "version": config["scenario_version"],
        },
        "repository": _git_evidence(root),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "device": "cpu",
            "torch_threads": torch.get_num_threads(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "jvm_args": list(DEFAULT_JVM_ARGS),
            "rl_lockfile": str(lock_path.relative_to(root).as_posix()),
            "rl_lock_sha256": sha256_path(lock_path),
            "rl_server_jar_sha256": sha256_path(jar_path),
        },
        "source_config": {
            "path": str(config_path.relative_to(root).as_posix()),
            "sha256": IPPO_V1_CONFIG_SHA256,
        },
        "public_protocol": {
            "path": str(protocol_path.relative_to(root).as_posix()),
            "sha256": IPPO_V1_PROTOCOL_SHA256,
        },
        "public_baseline": {
            "path": str(baseline_path.relative_to(root).as_posix()),
            "sha256": sha256_path(baseline_path),
        },
        "seed_sets": {
            "train": train_seed_set,
            "dev": dev_seed_set,
            "confirmation": None,
            "held_out": None,
            "active_splits": ["train", "dev"],
        },
        "rng_seeds": {
            key: config[key]
            for key in (
                "model_init_seed",
                "action_sampling_seed",
                "shuffle_seed",
                "minibatch_seed",
            )
        },
        "model_architecture": config["model_architecture"],
        "optimizer_ppo": config["optimizer_ppo"],
        "budget": {
            "training_cycles": config["training_cycles"],
            "episodes_per_update": config["episodes_per_update"],
            "total_episodes": (
                config["training_cycles"] * config["episodes_per_update"]
            ),
        },
        "initial_model_state_sha256": initial_model_state_sha256,
        "optimizer_updates": [],
        "checkpoint_selection": [],
        "selected_checkpoint": None,
        "train": [],
        "dev": [],
        "deterministic_checkpoint_verification": None,
    }


def atomic_write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
