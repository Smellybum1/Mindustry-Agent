#!/usr/bin/env python3
"""Primary-only V42 confirmation freeze without any membership read."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from typing import Any


MIN_ROOT_SEED = 6_000_000_000
MAX_ROOT_SEED_EXCLUSIVE = 7_000_000_000
ROOT_SEED_SPAN = MAX_ROOT_SEED_EXCLUSIVE - MIN_ROOT_SEED
CONFIG_PATH = (
    "configs/training/"
    "m8-selector-v42-partner-intent-teacher-conflict-relabel.json"
)
CONFIG_SHA256 = (
    "3fcb0c8800c638a333068ab116f8270be076c1cbae2438b55cc6f193c0583d0d"
)
UMBRELLA_PATH = "configs/evaluation/m8-selector-v42-confirmation-umbrella.json"
UMBRELLA_SHA256 = (
    "c1644d2dd6dde231e3a3409632169e182bfb13ebaff84deb2225368a82371532"
)
RECEIPT_PATH = "configs/evaluation/m8-selector-v42-dev-v38-freeze.json"
HELD_OUT_V6_SHA256 = (
    "2bf4aa04ef54d873e961ff367db849c14c72b83bb4d280c4e31ba75bdeefa51c"
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _git(
    root: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
    )


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(f"path is outside repository: {path}") from error


def _committed_file(root: Path, path: Path) -> str:
    relative = _relative(root, path)
    _git(root, "ls-files", "--error-unmatch", "--", relative)
    for args in (
        ("diff", "--quiet", "--", relative),
        ("diff", "--cached", "--quiet", "--", relative),
    ):
        if _git(root, *args, check=False).returncode != 0:
            raise ValueError(f"committed input has local changes: {relative}")
    commit = _git(root, "log", "-1", "--format=%H", "--", relative).stdout.strip()
    if not commit:
        raise ValueError(f"committed input has no history: {relative}")
    if (
        _git(root, "merge-base", "--is-ancestor", commit, "HEAD", check=False)
        .returncode
        != 0
    ):
        raise ValueError(f"input commit is not an ancestor of HEAD: {relative}")
    return commit


def _validate_reservation(
    umbrella: dict[str, Any], config_sha256: str
) -> dict[str, Any]:
    if umbrella.get("schema") != "m8_confirmation_evaluation_umbrella_v1":
        raise ValueError("unsupported confirmation evaluation umbrella")
    if umbrella.get("candidate_version") != "v42":
        raise ValueError("umbrella is not for V42")
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
    reserved = umbrella.get("replacement_set")
    expected = {
        "role": "confirmation",
        "seed_set_id": "bootstrap-defense-v1-dev-v38",
        "seed_set_version": 38,
        "split": "dev",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-dev-v38.json",
        "exclusive_namespace": {
            "minimum_inclusive": MIN_ROOT_SEED,
            "maximum_exclusive": MAX_ROOT_SEED_EXCLUSIVE,
        },
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": (
            "runs/m8-selector-v42-dev-v38-umbrella-attempt.json"
        ),
        "replaces": "bootstrap-defense-v1-dev-v37",
    }
    if reserved != expected:
        raise ValueError("umbrella replacement-set reservation drifted")
    expected_sealed = {
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "seed_set_version": 6,
        "split": "held-out",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-held-out-v6.json",
        "sha256": HELD_OUT_V6_SHA256,
        "consumption_state": "sealed_unconsumed",
        "membership_read_for_v42_reservation": False,
    }
    if umbrella.get("sealed_final_binding") != expected_sealed:
        raise ValueError("umbrella sealed-final binding drifted")
    return expected


def _generate(count: int) -> list[int]:
    if count < 1 or count > ROOT_SEED_SPAN:
        raise ValueError("reserved seed count is outside the V42 namespace")
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
            "One-way V42 confirmation set reserved under ADR-0056; primary-only "
            "consumption requires its committed umbrella attempt, and changes "
            "require a new seed_set_version."
        ),
    }


def _encoded(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--umbrella", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    script_path = Path(__file__).resolve()
    umbrella_path = args.umbrella.resolve()
    receipt_path = args.receipt.resolve()
    if _relative(root, umbrella_path) != UMBRELLA_PATH:
        raise ValueError("unexpected V42 umbrella path")
    script_commit = _committed_file(root, script_path)
    umbrella_commit = _committed_file(root, umbrella_path)
    if _sha256(umbrella_path) != UMBRELLA_SHA256:
        raise ValueError("V42 umbrella hash mismatch")
    if _relative(root, receipt_path) != RECEIPT_PATH:
        raise ValueError("unexpected V42 freeze receipt path")
    if receipt_path.exists():
        raise FileExistsError(f"receipt already exists: {receipt_path}")

    umbrella = _json(umbrella_path)
    training_config = root / str(umbrella["training_config"]["path"])
    config_sha256 = _sha256(training_config)
    reserved = _validate_reservation(umbrella, config_sha256)
    _committed_file(root, training_config)

    output_path = root / reserved["path"]
    _relative(root, output_path)
    if output_path.exists():
        raise FileExistsError(f"reserved membership already exists: {output_path}")
    config = _json(training_config)
    if config.get("confirmation_seed_set") != reserved["path"]:
        raise ValueError("training config confirmation path drifted")

    data = _encoded(_manifest(reserved, _generate(int(reserved["count"]))))
    membership_sha256 = _sha256_bytes(data)
    lock_path = output_path.parent / ".v42-confirmation-seed-freeze.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary: Path | None = None
    try:
        os.write(lock_fd, b"primary-agent-only\n")
        os.close(lock_fd)
        lock_fd = -1
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=output_path.parent, prefix=".dev-v38-"
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        if output_path.exists():
            raise FileExistsError("reserved membership raced creation")
        temporary.rename(output_path)
        temporary = None

        receipt = {
            "schema": "m8_confirmation_seed_freeze_v1",
            "candidate_version": "v42",
            "status": "membership_frozen_unconsumed",
            "umbrella": {
                "path": _relative(root, umbrella_path),
                "sha256": UMBRELLA_SHA256,
                "commit": umbrella_commit,
            },
            "generator_commit": script_commit,
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
                "v42_confirmation_min_inclusive": MIN_ROOT_SEED,
                "v42_confirmation_max_exclusive": MAX_ROOT_SEED_EXCLUSIVE,
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
        with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)

    print(
        "V42-CONFIRMATION-SEED-FREEZE OK "
        "values_emitted=false membership_reads=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
