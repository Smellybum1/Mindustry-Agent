"""Emit exact-commit evidence for ADR-0079's entropy schedule."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo_diverse_roots import (
    validate_diverse_root_packet,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V3_CONFIG_SHA256,
    IPPO_V3_PROTOCOL_SHA256,
    IPPO_V4_CONFIG_SHA256,
    IPPO_V4_PROTOCOL_SHA256,
    entropy_coefficient_for_update,
    load_ippo_v3_config,
    load_ippo_v4_config,
    sha256_path,
)


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalized_v4_config(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    result["schema"] = "ippo_training_config_v3"
    result["candidate_version"] = "m9-ippo-v3-diverse2048"
    result["public_evaluation_protocol"] = (
        "configs/evaluation/m9-ippo-v3-diverse2048-public-protocol.json"
    )
    result.pop("parent_candidate_version")
    result.pop("sole_learning_change")
    result.pop("entropy_coefficient_schedule")
    result["optimizer_ppo"].pop("entropy_coefficient_schedule")
    return result


def _normalized_v4_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(protocol)
    result["schema"] = "m9_ippo_public_protocol_v3"
    result["candidate_version"] = "m9-ippo-v3-diverse2048"
    return result


def build_report(root: Path) -> dict[str, Any]:
    """Return current exact-commit v4 inheritance and schedule evidence."""

    v3_config_path = root / "configs/training/m9-ippo-v3-diverse2048.json"
    v4_config_path = root / "configs/training/m9-ippo-v4-entropy-anneal.json"
    v3 = load_ippo_v3_config(v3_config_path)
    v4 = load_ippo_v4_config(v4_config_path)
    if _normalized_v4_config(v4) != v3:
        raise ValueError("M9 IPPO v4 changed more than entropy scheduling")

    v3_protocol_path = (
        root
        / "configs/evaluation/m9-ippo-v3-diverse2048-public-protocol.json"
    )
    v4_protocol_path = (
        root
        / "configs/evaluation/m9-ippo-v4-entropy-anneal-public-protocol.json"
    )
    if (
        sha256_path(v3_protocol_path) != IPPO_V3_PROTOCOL_SHA256
        or sha256_path(v4_protocol_path) != IPPO_V4_PROTOCOL_SHA256
    ):
        raise ValueError("M9 IPPO v4 protocol hash drifted")
    v3_protocol = json.loads(v3_protocol_path.read_text(encoding="utf-8"))
    v4_protocol = json.loads(v4_protocol_path.read_text(encoding="utf-8"))
    if _normalized_v4_protocol(v4_protocol) != v3_protocol:
        raise ValueError("M9 IPPO v4 public protocol changed semantically")

    coefficients = [
        {
            "update": update,
            "entropy_coefficient": entropy_coefficient_for_update(v4, update),
        }
        for update in range(1, 33)
    ]
    values = [item["entropy_coefficient"] for item in coefficients]
    if (
        values[0] != 0.02
        or values[-1] != 0.0
        or any(left <= right for left, right in zip(values, values[1:]))
    ):
        raise ValueError("M9 IPPO v4 entropy schedule is not strictly annealed")
    roots = validate_diverse_root_packet(root)
    return {
        "schema": "m9_ippo_v4_entropy_check_v1",
        "candidate_version": "m9-ippo-v4-entropy-anneal",
        "implementation_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip(),
        "config_sha256": IPPO_V4_CONFIG_SHA256,
        "protocol_sha256": IPPO_V4_PROTOCOL_SHA256,
        "parent_config_sha256": IPPO_V3_CONFIG_SHA256,
        "parent_protocol_sha256": IPPO_V3_PROTOCOL_SHA256,
        "semantic_inheritance_exact": True,
        "coefficient_schedule": coefficients,
        "coefficient_schedule_sha256": _json_digest(coefficients),
        "training_schedule_sha256": roots["schedule_sha256"],
        "training_root_count": roots["root_count"],
        "training_root_reuse_count": roots["root_reuse_count"],
        "confirmation_or_held_out_access": False,
        "all_passed": True,
    }


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-ippo-v4-entropy-check.json",
    )
    args = parser.parse_args()
    report = build_report(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        "M9 IPPO V4 ENTROPY OK "
        f"schedule={report['coefficient_schedule_sha256'][:16]} "
        f"roots={report['training_schedule_sha256'][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
