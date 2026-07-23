"""Emit exact-commit evidence for ADR-0075's public root schedule."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo_diverse_roots import (
    validate_diverse_root_packet,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V3_CONFIG_SHA256,
    IPPO_V3_PROTOCOL_SHA256,
    load_ippo_v3_config,
    sha256_path,
)


def build_report(root: Path) -> dict:
    """Return the current exact-commit v3 root-schedule evidence."""

    config_path = root / "configs/training/m9-ippo-v3-diverse2048.json"
    config = load_ippo_v3_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V3_PROTOCOL_SHA256:
        raise ValueError("M9 IPPO v3 public protocol hash drifted")
    packet = validate_diverse_root_packet(root)
    return {
        "schema": "m9_ippo_v3_diverse_roots_check_v1",
        "candidate_version": "m9-ippo-v3-diverse2048",
        "implementation_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip(),
        "config_sha256": IPPO_V3_CONFIG_SHA256,
        "protocol_sha256": IPPO_V3_PROTOCOL_SHA256,
        **packet,
        "all_passed": True,
    }


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-ippo-v3-diverse-roots-check.json",
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
        "M9 IPPO V3 DIVERSE ROOTS OK "
        f"count={report['root_count']} "
        f"schedule={report['schedule_sha256'][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
