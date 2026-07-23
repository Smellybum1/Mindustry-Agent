#!/usr/bin/env python3
"""Primary-only V48 confirmation freeze without any membership read."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts/freeze-v47-confirmation-seed-set.py"
SPEC = importlib.util.spec_from_file_location("v48_freezer_primitives", HELPER_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

MIN_ROOT_SEED = 14_000_000_000
MAX_ROOT_SEED_EXCLUSIVE = 15_000_000_000
ROOT_SEED_SPAN = MAX_ROOT_SEED_EXCLUSIVE - MIN_ROOT_SEED
CONFIG_PATH = "configs/training/m8-selector-v48-per-seat-history-cache.json"
CONFIG_SHA256 = (
    "714bd13db0ffee6f70c2d777f5bfa9c45221f77fe173cef35c15d3ead5441d2c"
)
UMBRELLA_PATH = "configs/evaluation/m8-selector-v48-confirmation-umbrella.json"
UMBRELLA_SHA256 = (
    "656602be6dd5c3cf7107420d44f9ba8543f9bfc4170a28930ce3e382a7cec7b7"
)
PUBLIC_EVIDENCE_PATH = "configs/evaluation/m8-selector-v47-reusable-v2-result.json"
PUBLIC_EVIDENCE_SHA256 = (
    "d30226fb7ecd0a2d4320ad856ec104311a61ce65bb5d46981e36206eac9a7cb9"
)
REUSABLE_V2_SHA256 = (
    "c529951782ec0426f94671ece39824d0057e303c2aa7edc11b3610a63c7f86f3"
)
RECEIPT_PATH = "configs/evaluation/m8-selector-v48-dev-v45-freeze.json"
IMPLEMENTATION_COMMIT = "07c6951a7ffe8da0252b83a63b1e0afea6f9ca7a"
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
    if umbrella.get("candidate_version") != "v48":
        raise ValueError("umbrella is not for V48")
    if umbrella.get("status") != "reserved_before_membership_creation":
        raise ValueError("umbrella is not in pre-membership reservation state")
    if umbrella.get("access_owner") != "primary_agent_only":
        raise ValueError("umbrella is not primary-agent-only")
    if umbrella.get("delegation_forbidden") is not True:
        raise ValueError("umbrella does not forbid delegated membership access")
    expected_config = {
        "path": CONFIG_PATH,
        "sha256": CONFIG_SHA256,
    }
    if (
        umbrella.get("training_config") != expected_config
        or config_sha256 != CONFIG_SHA256
    ):
        raise ValueError("umbrella training config hash mismatch")
    expected_public = {
        "path": PUBLIC_EVIDENCE_PATH,
        "sha256": PUBLIC_EVIDENCE_SHA256,
    }
    if umbrella.get("public_evidence") != expected_public:
        raise ValueError("umbrella public-evidence binding drifted")
    expected_reusable = {
        "seed_set_id": "bootstrap-defense-v1-reusable-scorecard-v2",
        "seed_set_version": 2,
        "split": "dev",
        "count": 160,
        "path": (
            "configs/evaluation/bootstrap-defense-v1-reusable-scorecard-v2.json"
        ),
        "sha256": REUSABLE_V2_SHA256,
        "role": "public_reusable_only",
    }
    if umbrella.get("reusable_screen") != expected_reusable:
        raise ValueError("umbrella reusable-screen binding drifted")
    expected = {
        "role": "confirmation",
        "seed_set_id": "bootstrap-defense-v1-dev-v45",
        "seed_set_version": 45,
        "split": "dev",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-dev-v45.json",
        "exclusive_namespace": {
            "minimum_inclusive": MIN_ROOT_SEED,
            "maximum_exclusive": MAX_ROOT_SEED_EXCLUSIVE,
        },
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": (
            "runs/m8-selector-v48-dev-v45-umbrella-attempt.json"
        ),
        "replaces": "bootstrap-defense-v1-dev-v44",
    }
    if umbrella.get("replacement_set") != expected:
        raise ValueError("umbrella replacement-set reservation drifted")
    if umbrella.get("retired_sets") != {
        "dev_v42": "retired_unopened_unconsumed",
        "dev_v44": "retired_unopened_unconsumed",
    }:
        raise ValueError("retired-set binding drifted")
    expected_sealed = {
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "seed_set_version": 6,
        "split": "held-out",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-held-out-v6.json",
        "sha256": HELD_OUT_V6_SHA256,
        "consumption_state": "sealed_unconsumed",
        "membership_read_for_v48_reservation": False,
    }
    if umbrella.get("sealed_final_binding") != expected_sealed:
        raise ValueError("umbrella sealed-final binding drifted")
    return expected


def _generate(count: int) -> list[int]:
    if count < 1 or count > ROOT_SEED_SPAN:
        raise ValueError("reserved seed count is outside the V48 namespace")
    values: set[int] = set()
    while len(values) < count:
        values.add(MIN_ROOT_SEED + secrets.randbelow(ROOT_SEED_SPAN))
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
            "One-way V48 confirmation set reserved under ADR-0066; primary-only "
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
    return {
        "schema": "m8_confirmation_seed_freeze_v1",
        "candidate_version": "v48",
        "status": "membership_frozen_unconsumed",
        "umbrella": {
            "path": _relative(root, umbrella_path),
            "sha256": UMBRELLA_SHA256,
            "commit": umbrella_commit,
        },
        "generator_commit": script_commit,
        "helper_commit": helper_commit,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "repository_head_before_generation": _git(
            root, "rev-parse", "HEAD"
        ).stdout.strip(),
        "values_emitted": False,
        "membership_documents_read": 0,
        "generated_membership_read_after_write": False,
        "retired_dev_v44_membership_read": False,
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
            "v45_confirmation_min_inclusive": 9_000_000_000,
            "v45_confirmation_max_exclusive": 10_000_000_000,
            "v46_confirmation_min_inclusive": 10_000_000_000,
            "v46_confirmation_max_exclusive": 11_000_000_000,
            "reusable_v2_min_inclusive": 11_000_000_000,
            "reusable_v2_max_exclusive": 12_000_000_000,
            "cancelled_dev_v43_min_inclusive": 12_000_000_000,
            "cancelled_dev_v43_max_exclusive": 13_000_000_000,
            "v47_confirmation_min_inclusive": 13_000_000_000,
            "v47_confirmation_max_exclusive": 14_000_000_000,
            "v48_confirmation_min_inclusive": MIN_ROOT_SEED,
            "v48_confirmation_max_exclusive": MAX_ROOT_SEED_EXCLUSIVE,
        },
        "public_evidence": {
            "path": PUBLIC_EVIDENCE_PATH,
            "sha256": PUBLIC_EVIDENCE_SHA256,
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
        raise ValueError("unexpected V48 umbrella path")
    script_commit = _committed_file(root, script_path)
    helper_commit = _committed_file(root, HELPER_PATH)
    umbrella_commit = _committed_file(root, umbrella_path)
    if (
        _git(
            root,
            "merge-base",
            "--is-ancestor",
            IMPLEMENTATION_COMMIT,
            "HEAD",
            check=False,
        ).returncode
        != 0
    ):
        raise ValueError("V48 implementation commit is not an ancestor of HEAD")
    if _sha256(umbrella_path) != UMBRELLA_SHA256:
        raise ValueError("V48 umbrella hash mismatch")
    if _relative(root, receipt_path) != RECEIPT_PATH:
        raise ValueError("unexpected V48 freeze receipt path")
    if receipt_path.exists():
        raise FileExistsError(f"receipt already exists: {receipt_path}")

    umbrella = _json(umbrella_path)
    training_config = root / str(umbrella["training_config"]["path"])
    reserved = _validate_reservation(umbrella, _sha256(training_config))
    _committed_file(root, training_config)
    public_evidence = root / PUBLIC_EVIDENCE_PATH
    _committed_file(root, public_evidence)
    if _sha256(public_evidence) != PUBLIC_EVIDENCE_SHA256:
        raise ValueError("V48 public evidence hash mismatch")
    output_path = root / reserved["path"]
    _relative(root, output_path)
    if output_path.exists():
        raise FileExistsError(f"reserved membership already exists: {output_path}")
    config = _json(training_config)
    if config.get("confirmation_seed_set") != reserved["path"]:
        raise ValueError("training config confirmation path drifted")
    if config.get("learned_seat_history", {}).get("schema") != (
        "per_seat_scripted_prior_boundary_cache_v1"
    ):
        raise ValueError("training config seat-history schema drifted")

    data = _encoded(_manifest(reserved, _generate(int(reserved["count"]))))
    membership_sha256 = _sha256_bytes(data)
    lock_path = output_path.parent / ".v48-confirmation-seed-freeze.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary: Path | None = None
    try:
        os.write(lock_fd, b"primary-agent-only\n")
        os.close(lock_fd)
        lock_fd = -1
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=output_path.parent, prefix=".dev-v45-"
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
    print("V48-CONFIRMATION-SEED-FREEZE OK values_emitted=false membership_reads=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
