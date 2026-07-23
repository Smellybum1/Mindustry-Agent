#!/usr/bin/env python3
"""Primary-only V45 confirmation freeze without any membership read."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts/freeze-v44-confirmation-seed-set.py"
SPEC = importlib.util.spec_from_file_location("v45_freezer_primitives", HELPER_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

MIN_ROOT_SEED = 9_000_000_000
MAX_ROOT_SEED_EXCLUSIVE = 10_000_000_000
ROOT_SEED_SPAN = MAX_ROOT_SEED_EXCLUSIVE - MIN_ROOT_SEED
CONFIG_PATH = "configs/training/m8-selector-v45-residual-lagged-context.json"
CONFIG_SHA256 = (
    "a7d0c8029acebe79dfc33224c96fdce89b33c043744dde222f8982053324be8c"
)
UMBRELLA_PATH = "configs/evaluation/m8-selector-v45-confirmation-umbrella.json"
UMBRELLA_SHA256 = (
    "e4fe0b56a95fa64cb59e5ea853c878b4d678f86c629bba72b393a68b5eb7b8f2"
)
RECEIPT_PATH = "configs/evaluation/m8-selector-v45-dev-v41-freeze.json"
HELD_OUT_V6_SHA256 = BASE.HELD_OUT_V6_SHA256

_sha256_bytes = BASE._sha256_bytes
_sha256 = BASE._sha256
_json = BASE._json
_git = BASE._git
_relative = BASE._relative
_committed_file = BASE._committed_file
_encoded = BASE._encoded


def _validate_reservation(
    umbrella: dict[str, Any], config_sha256: str
) -> dict[str, Any]:
    if umbrella.get("schema") != "m8_confirmation_evaluation_umbrella_v1":
        raise ValueError("unsupported confirmation evaluation umbrella")
    if umbrella.get("candidate_version") != "v45":
        raise ValueError("umbrella is not for V45")
    if umbrella.get("status") != "reserved_before_membership_creation":
        raise ValueError("umbrella is not in pre-membership reservation state")
    if umbrella.get("access_owner") != "primary_agent_only":
        raise ValueError("umbrella is not primary-agent-only")
    if umbrella.get("delegation_forbidden") is not True:
        raise ValueError("umbrella does not forbid delegated membership access")
    training_config = umbrella.get("training_config")
    if (
        not isinstance(training_config, dict)
        or training_config.get("path") != CONFIG_PATH
        or training_config.get("sha256") != CONFIG_SHA256
        or training_config.get("sha256") != config_sha256
    ):
        raise ValueError("umbrella training config hash mismatch")
    expected = {
        "role": "confirmation",
        "seed_set_id": "bootstrap-defense-v1-dev-v41",
        "seed_set_version": 41,
        "split": "dev",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-dev-v41.json",
        "exclusive_namespace": {
            "minimum_inclusive": MIN_ROOT_SEED,
            "maximum_exclusive": MAX_ROOT_SEED_EXCLUSIVE,
        },
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": (
            "runs/m8-selector-v45-dev-v41-umbrella-attempt.json"
        ),
        "replaces": "bootstrap-defense-v1-dev-v40",
    }
    if umbrella.get("replacement_set") != expected:
        raise ValueError("umbrella replacement-set reservation drifted")
    expected_sealed = {
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "seed_set_version": 6,
        "split": "held-out",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-held-out-v6.json",
        "sha256": HELD_OUT_V6_SHA256,
        "consumption_state": "sealed_unconsumed",
        "membership_read_for_v45_reservation": False,
    }
    if umbrella.get("sealed_final_binding") != expected_sealed:
        raise ValueError("umbrella sealed-final binding drifted")
    return expected


def _generate(count: int) -> list[int]:
    if count < 1 or count > ROOT_SEED_SPAN:
        raise ValueError("reserved seed count is outside the V45 namespace")
    values: set[int] = set()
    while len(values) < count:
        values.add(MIN_ROOT_SEED + BASE.secrets.randbelow(ROOT_SEED_SPAN))
    return sorted(values)


def _manifest(reserved: dict[str, Any], seeds: list[int]) -> dict[str, Any]:
    return {
        "seed_set_id": reserved["seed_set_id"],
        "seed_set_version": reserved["seed_set_version"],
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": "dev",
        "seeds": seeds,
        "policy": (
            "One-way V45 confirmation set reserved under ADR-0062; primary-only "
            "consumption requires its committed umbrella attempt, and changes "
            "require a new seed_set_version."
        ),
    }


def _receipt(
    root: Path,
    umbrella_path: Path,
    umbrella_commit: str,
    script_commit: str,
    helper_commit: str,
    reserved: dict[str, Any],
    membership_sha256: str,
) -> dict[str, Any]:
    document = {
        "schema": "m8_confirmation_seed_freeze_v1",
        "candidate_version": "v45",
        "status": "membership_frozen_unconsumed",
        "umbrella": {
            "path": _relative(root, umbrella_path),
            "sha256": UMBRELLA_SHA256,
            "commit": umbrella_commit,
        },
        "generator_commit": script_commit,
        "helper_commit": helper_commit,
        "repository_head_before_generation": _git(
            root, "rev-parse", "HEAD"
        ).stdout.strip(),
        "values_emitted": False,
        "membership_documents_read": 0,
        "generated_membership_read_after_write": False,
        "retired_confirmation_membership_read": False,
        "sealed_final_membership_read": False,
        "global_disjointness_verified": True,
        "disjointness_method": "partitioned_numeric_namespace_without_reads",
        "namespace_proof": {
            "legacy_max_exclusive": 1_000_000_000,
            "v38_sealed_max_exclusive": 2_000_000_000,
            "v39_confirmation_max_exclusive": 2_147_483_648,
            "held_out_v6_min_inclusive": 3_000_000_000,
            "held_out_v6_max_exclusive": 4_000_000_000,
            "v40_confirmation_min_inclusive": 4_000_000_000,
            "v40_confirmation_max_exclusive": 5_000_000_000,
            "v41_confirmation_min_inclusive": 5_000_000_000,
            "v41_confirmation_max_exclusive": 6_000_000_000,
            "v42_confirmation_min_inclusive": 6_000_000_000,
            "v42_confirmation_max_exclusive": 7_000_000_000,
            "v43_confirmation_min_inclusive": 7_000_000_000,
            "v43_confirmation_max_exclusive": 8_000_000_000,
            "v44_confirmation_min_inclusive": 8_000_000_000,
            "v44_confirmation_max_exclusive": 9_000_000_000,
            "v45_confirmation_min_inclusive": MIN_ROOT_SEED,
            "v45_confirmation_max_exclusive": MAX_ROOT_SEED_EXCLUSIVE,
        },
        "set": {
            key: reserved[key]
            for key in (
                "role",
                "seed_set_id",
                "seed_set_version",
                "split",
                "count",
                "path",
                "exclusive_namespace",
                "exclusive_umbrella_attempt",
                "replaces",
            )
        }
        | {"sha256": membership_sha256},
    }
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--umbrella", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    root = ROOT
    script_path = Path(__file__).resolve()
    umbrella_path = args.umbrella.resolve()
    receipt_path = args.receipt.resolve()
    if _relative(root, umbrella_path) != UMBRELLA_PATH:
        raise ValueError("unexpected V45 umbrella path")
    script_commit = _committed_file(root, script_path)
    helper_commit = _committed_file(root, HELPER_PATH)
    umbrella_commit = _committed_file(root, umbrella_path)
    if _sha256(umbrella_path) != UMBRELLA_SHA256:
        raise ValueError("V45 umbrella hash mismatch")
    if _relative(root, receipt_path) != RECEIPT_PATH:
        raise ValueError("unexpected V45 freeze receipt path")
    if receipt_path.exists():
        raise FileExistsError(f"receipt already exists: {receipt_path}")

    umbrella = _json(umbrella_path)
    training_config = root / str(umbrella["training_config"]["path"])
    reserved = _validate_reservation(umbrella, _sha256(training_config))
    _committed_file(root, training_config)
    output_path = root / reserved["path"]
    _relative(root, output_path)
    if output_path.exists():
        raise FileExistsError(f"reserved membership already exists: {output_path}")
    if _json(training_config).get("confirmation_seed_set") != reserved["path"]:
        raise ValueError("training config confirmation path drifted")

    data = _encoded(_manifest(reserved, _generate(int(reserved["count"]))))
    membership_sha256 = _sha256_bytes(data)
    lock_path = output_path.parent / ".v45-confirmation-seed-freeze.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary: Path | None = None
    try:
        os.write(lock_fd, b"primary-agent-only\n")
        os.close(lock_fd)
        lock_fd = -1
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=output_path.parent, prefix=".dev-v41-"
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        if output_path.exists():
            raise FileExistsError("reserved membership raced creation")
        temporary.rename(output_path)
        temporary = None
        document = _receipt(
            root,
            umbrella_path,
            umbrella_commit,
            script_commit,
            helper_commit,
            reserved,
            membership_sha256,
        )
        with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)
    print("V45-CONFIRMATION-SEED-FREEZE OK values_emitted=false membership_reads=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
