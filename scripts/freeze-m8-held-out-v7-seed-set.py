#!/usr/bin/env python3
"""Freeze held-out-v7 primary-only without reading retired membership."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UMBRELLA = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v49-held-out-v7-umbrella.json"
)
PROTOCOL = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v49-noninferiority-protocol.json"
)
OUTPUT = (
    ROOT
    / "configs"
    / "evaluation"
    / "bootstrap-defense-v1-held-out-v7.json"
)
RECEIPT = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v49-held-out-v7-freeze.json"
)
MINIMUM = 17_000_000_000
MAXIMUM_EXCLUSIVE = 18_000_000_000
COUNT = 160


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _committed_file(path: Path) -> str:
    relative = _relative(path)
    _git("ls-files", "--error-unmatch", "--", relative)
    for args in (
        ("diff", "--quiet", "--", relative),
        ("diff", "--cached", "--quiet", "--", relative),
    ):
        if _git(*args, check=False).returncode != 0:
            raise ValueError(f"committed input has local changes: {relative}")
    commit = _git("log", "-1", "--format=%H", "--", relative).stdout.strip()
    if not commit:
        raise ValueError(f"committed input has no history: {relative}")
    return commit


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _validate() -> dict[str, Any]:
    umbrella = _load_json(UMBRELLA)
    protocol = _load_json(PROTOCOL)
    if (
        umbrella.get("schema") != "m8_v49_replacement_final_umbrella_v1"
        or umbrella.get("candidate_version") != "v49"
        or umbrella.get("status") != "reserved_before_membership_creation"
        or umbrella.get("access_owner") != "primary_agent_only"
        or umbrella.get("delegation_forbidden") is not True
    ):
        raise ValueError("held-out-v7 umbrella drifted")
    if (
        protocol.get("schema") != "m8_scorecard_noninferiority_protocol_v1"
        or protocol.get("candidate_version") != "v49"
        or umbrella.get("protocol", {}).get("sha256") != _sha256(PROTOCOL)
    ):
        raise ValueError("held-out-v7 protocol binding drifted")
    reserved = umbrella.get("replacement_final")
    expected = {
        "role": "final",
        "seed_set_id": "bootstrap-defense-v1-held-out-v7",
        "seed_set_version": 7,
        "split": "held-out",
        "count": COUNT,
        "path": _relative(OUTPUT),
        "exclusive_namespace": {
            "minimum_inclusive": MINIMUM,
            "maximum_exclusive": MAXIMUM_EXCLUSIVE,
        },
        "membership_state_at_reservation": "not_created",
        "exclusive_attempt": (
            "runs/m8-selector-v49-held-out-v7-final.attempt.json"
        ),
        "execution_gate": "reusable_v3_and_dev_v46_confirmation_pass",
        "replaces": "bootstrap-defense-v1-held-out-v6",
    }
    if reserved != expected:
        raise ValueError("held-out-v7 reservation drifted")
    if umbrella.get("retired_final") != {
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "status": "retired_membership_exposed_unexecuted",
        "membership_read_authorized": False,
    }:
        raise ValueError("retired held-out-v6 state drifted")
    return expected


def _generate() -> list[int]:
    values: set[int] = set()
    while len(values) < COUNT:
        values.add(MINIMUM + secrets.randbelow(MAXIMUM_EXCLUSIVE - MINIMUM))
    return sorted(values)


def _membership(reserved: dict[str, Any], seeds: list[int]) -> bytes:
    document = {
        "seed_set_id": reserved["seed_set_id"],
        "seed_set_version": reserved["seed_set_version"],
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": "held-out",
        "seeds": seeds,
        "policy": (
            "One-way V49 final reserved by ADR-0068; primary-only execution "
            "requires the committed held-out-v7 umbrella and attempt."
        ),
    }
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def main() -> int:
    generator_commit = _committed_file(Path(__file__).resolve())
    umbrella_commit = _committed_file(UMBRELLA)
    _committed_file(PROTOCOL)
    reserved = _validate()
    if OUTPUT.exists() or RECEIPT.exists():
        raise FileExistsError("held-out-v7 membership or receipt already exists")

    data = _membership(reserved, _generate())
    membership_sha256 = _sha256_bytes(data)
    lock = OUTPUT.parent / ".held-out-v7-freeze.lock"
    lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary: Path | None = None
    try:
        os.write(lock_fd, b"primary-agent-only\n")
        os.close(lock_fd)
        lock_fd = -1
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=OUTPUT.parent,
            prefix=".held-out-v7-",
        ) as stream:
            stream.write(data)
            temporary = Path(stream.name)
        if OUTPUT.exists():
            raise FileExistsError("held-out-v7 membership raced creation")
        temporary.rename(OUTPUT)
        temporary = None
        if _sha256(OUTPUT) != membership_sha256:
            raise ValueError("held-out-v7 written membership hash mismatch")

        receipt = {
            "schema": "m8_final_seed_freeze_v2",
            "candidate_version": "v49",
            "status": "membership_frozen_unconsumed",
            "umbrella": {
                "path": _relative(UMBRELLA),
                "sha256": _sha256(UMBRELLA),
                "commit": umbrella_commit,
            },
            "protocol": {
                "path": _relative(PROTOCOL),
                "sha256": _sha256(PROTOCOL),
            },
            "generator_commit": generator_commit,
            "repository_head_before_generation": _git(
                "rev-parse", "HEAD"
            ).stdout.strip(),
            "values_emitted": False,
            "membership_documents_read": 0,
            "confirmation_membership_read": False,
            "retired_final_membership_read": False,
            "global_disjointness_verified": True,
            "disjointness_method": (
                "partitioned_numeric_namespace_without_membership_reads"
            ),
            "namespace": {
                "minimum_inclusive": MINIMUM,
                "maximum_exclusive": MAXIMUM_EXCLUSIVE,
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
                    "exclusive_attempt",
                    "replaces",
                )
            }
            | {"sha256": membership_sha256},
        }
        with RECEIPT.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)

    print(
        "M8-HELD-OUT-V7-FREEZE OK "
        "values_emitted=false membership_reads=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
