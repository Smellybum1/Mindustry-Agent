#!/usr/bin/env python3
"""Primary-only V39 final freeze without reading any prior membership."""

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

MIN_ROOT_SEED = 3_000_000_000
ROOT_SEED_SPAN = 1_000_000_000


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, check=check, capture_output=True, text=True
    )


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(f"path is outside repository: {path}") from error


def _committed_file(root: Path, path: Path) -> str:
    relative = _relative(root, path)
    _git(root, "ls-files", "--error-unmatch", "--", relative)
    for args in (("diff", "--quiet", "--", relative), ("diff", "--cached", "--quiet", "--", relative)):
        if _git(root, *args, check=False).returncode != 0:
            raise ValueError(f"committed input has local changes: {relative}")
    commit = _git(root, "log", "-1", "--format=%H", "--", relative).stdout.strip()
    if not commit:
        raise ValueError(f"committed input has no history: {relative}")
    return commit


def _validate(umbrella: dict[str, Any], config_sha256: str) -> dict[str, Any]:
    if umbrella.get("schema") != "m8_replacement_final_evaluation_umbrella_v1":
        raise ValueError("unsupported replacement-final umbrella")
    if umbrella.get("candidate_version") != "v39" or umbrella.get("status") != "reserved_before_membership_creation":
        raise ValueError("replacement-final umbrella state drifted")
    if umbrella.get("access_owner") != "primary_agent_only" or umbrella.get("delegation_forbidden") is not True:
        raise ValueError("replacement-final umbrella access drifted")
    config = umbrella.get("training_config", {})
    if config.get("path") != "configs/training/m8-selector-v39-partner-intent-duplication-risk.json" or config.get("sha256") != config_sha256:
        raise ValueError("replacement-final training config drifted")
    confirmation = umbrella.get("confirmation_binding", {})
    if confirmation.get("membership_read_for_rebinding") is not False or confirmation.get("consumption_state") != "frozen_unconsumed":
        raise ValueError("confirmation binding drifted")
    reserved = umbrella.get("replacement_final")
    expected = {
        "role": "final",
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "seed_set_version": 6,
        "split": "held-out",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-held-out-v6.json",
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": "runs/m8-selector-v39-held-out-v6-umbrella-attempt.json",
        "replaces": "bootstrap-defense-v1-held-out-v5",
    }
    if reserved != expected:
        raise ValueError("replacement-final reservation drifted")
    return expected


def _generate(count: int) -> list[int]:
    values: set[int] = set()
    while len(values) < count:
        values.add(MIN_ROOT_SEED + secrets.randbelow(ROOT_SEED_SPAN))
    return sorted(values)


def _encoded(reserved: dict[str, Any], seeds: list[int]) -> bytes:
    document = {
        "seed_set_id": reserved["seed_set_id"],
        "seed_set_version": reserved["seed_set_version"],
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": "held-out",
        "seeds": seeds,
        "policy": "One-way V39 final reserved under ADR-0053; primary-only consumption requires its committed umbrella attempt.",
    }
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--umbrella", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    umbrella_path = args.umbrella.resolve()
    receipt_path = args.receipt.resolve()
    generator_commit = _committed_file(root, Path(__file__).resolve())
    umbrella_commit = _committed_file(root, umbrella_path)
    umbrella = _json(umbrella_path)
    config_path = root / str(umbrella["training_config"]["path"])
    _committed_file(root, config_path)
    reserved = _validate(umbrella, _sha256(config_path))
    output_path = root / reserved["path"]
    _relative(root, output_path)
    _relative(root, receipt_path)
    if output_path.exists() or receipt_path.exists():
        raise FileExistsError("reserved final membership or receipt already exists")
    data = _encoded(reserved, _generate(int(reserved["count"])))
    lock_path = output_path.parent / ".final-seed-freeze.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary: Path | None = None
    try:
        os.write(lock_fd, b"primary-agent-only\n")
        os.close(lock_fd)
        lock_fd = -1
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=output_path.parent, prefix=".held-out-v6-") as handle:
            handle.write(data)
            temporary = Path(handle.name)
        if output_path.exists():
            raise FileExistsError("reserved final membership raced creation")
        temporary.rename(output_path)
        temporary = None
        if _sha256(output_path) != _sha256_bytes(data):
            raise ValueError("written final membership hash mismatch")
        receipt = {
            "schema": "m8_final_seed_freeze_v1",
            "candidate_version": "v39",
            "status": "membership_frozen_unconsumed",
            "umbrella": {"path": _relative(root, umbrella_path), "sha256": _sha256(umbrella_path), "commit": umbrella_commit},
            "generator_commit": generator_commit,
            "repository_head_before_generation": _git(root, "rev-parse", "HEAD").stdout.strip(),
            "values_emitted": False,
            "membership_documents_read": 0,
            "confirmation_membership_read": False,
            "retired_final_membership_read": False,
            "global_disjointness_verified": True,
            "disjointness_method": "partitioned_numeric_namespace_without_reads",
            "namespace": {"min_inclusive": MIN_ROOT_SEED, "max_exclusive": MIN_ROOT_SEED + ROOT_SEED_SPAN},
            "set": {key: reserved[key] for key in ("role", "seed_set_id", "seed_set_version", "split", "count", "path", "exclusive_umbrella_attempt", "replaces")} | {"sha256": _sha256_bytes(data)},
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
    print("FINAL-SEED-FREEZE OK values_emitted=false membership_reads=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
