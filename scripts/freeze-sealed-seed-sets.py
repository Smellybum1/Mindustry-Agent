#!/usr/bin/env python3
"""Primary-only sealed seed-set construction without membership output."""

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


MIN_ROOT_SEED = 1_000_000_000
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


def _validate_committed_umbrella(root: Path, path: Path) -> str:
    relative = _relative(root, path)
    _git(root, "ls-files", "--error-unmatch", "--", relative)
    if _git(root, "diff", "--quiet", "--", relative, check=False).returncode != 0:
        raise ValueError("umbrella reservation has uncommitted changes")
    if (
        _git(
            root, "diff", "--cached", "--quiet", "--", relative, check=False
        ).returncode
        != 0
    ):
        raise ValueError("umbrella reservation has staged changes")
    commit = _git(root, "log", "-1", "--format=%H", "--", relative).stdout.strip()
    if not commit:
        raise ValueError("umbrella reservation has no committed history")
    if (
        _git(
            root,
            "merge-base",
            "--is-ancestor",
            commit,
            "HEAD",
            check=False,
        ).returncode
        != 0
    ):
        raise ValueError("umbrella commit is not an ancestor of HEAD")
    return commit


def _existing_membership(evaluation_dir: Path) -> tuple[set[int], int]:
    used: set[int] = set()
    documents = 0
    for path in sorted(evaluation_dir.glob("bootstrap-defense-*.json")):
        document = _json(path)
        seeds = document.get("seeds")
        if not isinstance(seeds, list) or not all(
            isinstance(seed, int) for seed in seeds
        ):
            raise ValueError(f"invalid governed seed list: {path.name}")
        if len(seeds) != len(set(seeds)):
            raise ValueError(f"duplicate governed seed: {path.name}")
        overlap = used.intersection(seeds)
        if overlap:
            raise ValueError(f"existing governed sets overlap: {path.name}")
        used.update(seeds)
        documents += 1
    return used, documents


def _generate(count: int, used: set[int]) -> list[int]:
    values: set[int] = set()
    while len(values) < count:
        value = MIN_ROOT_SEED + secrets.randbelow(ROOT_SEED_SPAN)
        if value not in used:
            values.add(value)
    used.update(values)
    return sorted(values)


def _manifest(reserved: dict[str, Any], seeds: list[int]) -> dict[str, Any]:
    split = str(reserved["split"])
    role = str(reserved["role"])
    return {
        "seed_set_id": str(reserved["seed_set_id"]),
        "seed_set_version": int(reserved["seed_set_version"]),
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": split,
        "seeds": seeds,
        "policy": (
            f"One-way V38 {role} set reserved under ADR-0050; primary-only "
            "consumption requires its committed umbrella attempt, and changes "
            "require a new seed_set_version."
        ),
    }


def _encoded(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--umbrella", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    umbrella_path = args.umbrella.resolve()
    receipt_path = args.receipt.resolve()
    _relative(root, receipt_path)
    if receipt_path.exists():
        raise FileExistsError(f"receipt already exists: {receipt_path}")

    umbrella_commit = _validate_committed_umbrella(root, umbrella_path)
    umbrella = _json(umbrella_path)
    if umbrella.get("schema") != "m8_sealed_evaluation_umbrella_v1":
        raise ValueError("unsupported sealed evaluation umbrella")
    if umbrella.get("status") != "reserved_before_membership_creation":
        raise ValueError("umbrella is not in pre-membership reservation state")
    if umbrella.get("access_owner") != "primary_agent_only":
        raise ValueError("umbrella is not primary-agent-only")
    if umbrella.get("delegation_forbidden") is not True:
        raise ValueError("umbrella does not forbid delegated membership access")

    config = root / str(umbrella["training_config"]["path"])
    if _sha256(config) != str(umbrella["training_config"]["sha256"]):
        raise ValueError("umbrella training config hash mismatch")

    reserved_sets = list(umbrella.get("replacement_sets", []))
    if len(reserved_sets) != 2:
        raise ValueError("umbrella must reserve exactly two replacement sets")
    output_paths = [root / str(item["path"]) for item in reserved_sets]
    for item, path in zip(reserved_sets, output_paths):
        _relative(root, path)
        if item.get("membership_state_at_reservation") != "not_created":
            raise ValueError("reserved set was not marked absent")
        if path.exists():
            raise FileExistsError(f"reserved membership already exists: {path}")

    evaluation_dir = output_paths[0].parent
    if any(path.parent != evaluation_dir for path in output_paths):
        raise ValueError("reserved sets must share the evaluation directory")
    used, existing_documents = _existing_membership(evaluation_dir)
    existing_seed_count = len(used)

    generated: list[tuple[Path, dict[str, Any], bytes]] = []
    for item, path in zip(reserved_sets, output_paths):
        count = int(item["count"])
        if count < 1:
            raise ValueError("reserved seed count must be positive")
        document = _manifest(item, _generate(count, used))
        data = _encoded(document)
        generated.append((path, document, data))

    lock_path = evaluation_dir / ".sealed-seed-freeze.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary: list[Path] = []
    try:
        os.write(lock_fd, b"primary-agent-only\n")
        os.close(lock_fd)
        lock_fd = -1
        for path, _, data in generated:
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, dir=path.parent, prefix=".sealed-"
            ) as handle:
                handle.write(data)
                temporary.append(Path(handle.name))
        for temporary_path, (path, _, _) in zip(temporary, generated):
            if path.exists():
                raise FileExistsError(f"reserved membership raced creation: {path}")
            temporary_path.rename(path)
        temporary.clear()
        for path, _, data in generated:
            if _sha256(path) != _sha256_bytes(data):
                raise ValueError(f"written membership hash mismatch: {path}")

        receipt = {
            "schema": "sealed_seed_freeze_receipt_v1",
            "umbrella_path": _relative(root, umbrella_path),
            "umbrella_sha256": _sha256(umbrella_path),
            "umbrella_commit": umbrella_commit,
            "repository_head": _git(root, "rev-parse", "HEAD").stdout.strip(),
            "existing_governed_documents": existing_documents,
            "existing_unique_seed_count": existing_seed_count,
            "values_emitted": False,
            "generated": [
                {
                    "seed_set_id": document["seed_set_id"],
                    "seed_set_version": document["seed_set_version"],
                    "split": document["split"],
                    "count": len(document["seeds"]),
                    "path": _relative(root, path),
                    "sha256": _sha256_bytes(data),
                }
                for path, document, data in generated
            ],
        }
        with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        for path in temporary:
            path.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)

    print("SEALED-SEED-FREEZE OK values_emitted=false sets=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
