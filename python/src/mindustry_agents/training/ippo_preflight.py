"""Fail-closed validation of every committed M9 IPPO pretraining artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo_ppo import (
    IPPO_V1_CONFIG_SHA256,
    IPPO_V1_PROTOCOL_SHA256,
    load_ippo_v1_config,
    sha256_path,
)

EXPECTED = {
    "configs/evaluation/m9-ippo-v1-reward-adversaries.json": (
        "f6b87fb96ccf206c6e946d6e0cb2504c7f6338905c79b76caa094016bf5f20dd"
    ),
    "configs/evaluation/m9-ippo-v1-rollout-check.json": (
        "70284030cb0cc2b47bc1a30df37ef7c3650b9da0ef6098450b81d1b0b5187d4e"
    ),
    "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json": (
        "ba4c9182f346a6eefc8c904d3e7825ee23933aede535b7c516ec63800f6a2d70"
    ),
    "configs/evaluation/m9-ippo-v1-artifact-check.json": (
        "2a5b536ce71d07eea54d122c3be0714140e3eeb1a22dbc5cef4dcb4929622e3f"
    ),
}


def _load(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    actual = sha256_path(path)
    if actual != EXPECTED[relative]:
        raise ValueError(f"M9 pretraining artifact hash drifted: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_preflight(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    config_path = root / "configs/training/m9-ippo-v1.json"
    config = load_ippo_v1_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V1_PROTOCOL_SHA256:
        raise ValueError("M9 public protocol hash drifted")
    if sha256_path(config_path) != IPPO_V1_CONFIG_SHA256:
        raise ValueError("M9 config hash drifted")
    if (
        config["confirmation_seed_set"] is not None
        or config["held_out_seed_set"] is not None
    ):
        raise ValueError("M9 pretraining config gained sealed-data authority")

    reward = _load(
        root, "configs/evaluation/m9-ippo-v1-reward-adversaries.json"
    )
    rollout = _load(root, "configs/evaluation/m9-ippo-v1-rollout-check.json")
    baseline = _load(
        root, "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
    )
    artifact = _load(
        root, "configs/evaluation/m9-ippo-v1-artifact-check.json"
    )
    if not reward.get("all_passed") or len(reward.get("cases", [])) != 6:
        raise ValueError("M9 reward adversary evidence is incomplete")
    if not rollout.get("repeated_rollouts_equal"):
        raise ValueError("M9 stochastic reset evidence failed")
    if (
        baseline.get("aggregate", {}).get("episodes") != 40
        or not baseline.get("terminal_reset_replay_equal")
        or baseline.get("manifest", {}).get("project_commit")
        != "dea79c487adc88b176f765e14f60e27dbbf70f6d"
    ):
        raise ValueError("M9 frozen public baseline evidence is invalid")
    checkpoint = artifact.get("checkpoint", {})
    if (
        not artifact.get("fresh_checkpoint_replays_equal")
        or not artifact.get("manifest_twins_equal")
        or artifact.get("confirmation_or_held_out_access") is not False
        or checkpoint.get("update") != 0
        or checkpoint.get("parent_checkpoint_content_sha256") is not None
    ):
        raise ValueError("M9 checkpoint/manifest evidence is invalid")
    return {
        "schema": "m9_ippo_preflight_v1",
        "config_sha256": IPPO_V1_CONFIG_SHA256,
        "protocol_sha256": IPPO_V1_PROTOCOL_SHA256,
        "artifacts": EXPECTED,
        "public_baseline_wins": baseline["aggregate"]["wins"],
        "checkpoint_content_sha256": checkpoint["checkpoint_content_sha256"],
        "checkpoint_trace_sha256": artifact["episode"]["trace_sha256"],
        "manifest_reproducibility_digest": artifact[
            "manifest_reproducibility_digest"
        ],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def main() -> int:
    print(json.dumps(validate_preflight(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
