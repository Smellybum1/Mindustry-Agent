"""Validation for the prospective M8 operational non-inferiority protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from mindustry_agents.evaluation.promotion import validate_scorecard_margins


PROTOCOL_SCHEMA = "m8_scorecard_noninferiority_protocol_v1"
SCORECARD_SCHEMA = "paired_operational_noninferiority_v1"
PASS_RULE = "mean_and_ci95_upper_bound_at_or_below_metric_margin"
PROTOCOL_ROLES = ("reusable", "confirmation", "final")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolved_protocol_path(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"scorecard protocol {label} path is invalid")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(
            f"scorecard protocol {label} path is outside repository"
        ) from error
    return path


def load_scorecard_protocol(
    protocol_path: Path,
    *,
    root: Path,
    config_path: Path,
    checkpoint_path: Path,
    seed_set_path: Path,
    role: str,
) -> dict[str, Any]:
    """Load and bind the exact V49 protocol without reading seed membership."""

    if role not in PROTOCOL_ROLES:
        raise ValueError(f"unsupported scorecard protocol role: {role}")
    protocol_path = protocol_path.resolve()
    document = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or document.get("schema") != PROTOCOL_SCHEMA
        or document.get("candidate_version") != "v49"
        or document.get("status")
        != "precommitted_before_reusable_v3_membership"
    ):
        raise ValueError("unsupported scorecard noninferiority protocol")

    candidate = document.get("candidate")
    if not isinstance(candidate, dict) or candidate.get("behavior") != (
        "v47_selected_checkpoint_unchanged"
    ):
        raise ValueError("scorecard protocol candidate binding is invalid")
    config = candidate.get("training_config")
    checkpoint = candidate.get("checkpoint")
    if not isinstance(config, dict) or not isinstance(checkpoint, dict):
        raise ValueError("scorecard protocol candidate artifacts are missing")
    if (
        _resolved_protocol_path(root, config.get("path"), "config")
        != config_path.resolve()
        or config.get("sha256") != _sha256(config_path.resolve())
        or _resolved_protocol_path(root, checkpoint.get("path"), "checkpoint")
        != checkpoint_path.resolve()
        or checkpoint.get("sha256") != _sha256(checkpoint_path.resolve())
    ):
        raise ValueError("scorecard protocol candidate artifact drifted")

    scorecard = document.get("scorecard")
    confidence_level = (
        scorecard.get("confidence_level")
        if isinstance(scorecard, dict)
        else None
    )
    if (
        not isinstance(scorecard, dict)
        or scorecard.get("schema") != SCORECARD_SCHEMA
        or scorecard.get("direction")
        != "candidate_minus_baseline; lower is better"
        or scorecard.get("bootstrap_resamples") != 10000
        or isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or float(confidence_level) != 0.95
        or scorecard.get("uncertainty_is_failure") is not True
        or scorecard.get("pass_rule") != PASS_RULE
        or scorecard.get("required_baselines")
        != ["permanent_greedy_utility", "matched_greedy_utility"]
    ):
        raise ValueError("scorecard protocol decision rule drifted")
    margins = validate_scorecard_margins(scorecard.get("margins"))
    if not any(value > 0.0 for value in margins.values()):
        raise ValueError("scorecard protocol requires operational margins")

    seed_set = document.get(role)
    if not isinstance(seed_set, dict):
        raise ValueError(f"scorecard protocol {role} reservation is missing")
    if (
        _resolved_protocol_path(root, seed_set.get("path"), role)
        != seed_set_path.resolve()
    ):
        raise ValueError(f"scorecard protocol {role} seed path drifted")
    if (
        seed_set.get("split") != ("held-out" if role == "final" else "dev")
        or seed_set.get("count") != 160
        or not isinstance(seed_set.get("seed_set_id"), str)
        or isinstance(seed_set.get("seed_set_version"), bool)
        or not isinstance(seed_set.get("seed_set_version"), int)
    ):
        raise ValueError(f"scorecard protocol {role} identity is invalid")

    return {
        "schema": PROTOCOL_SCHEMA,
        "candidate_version": "v49",
        "role": role,
        "path": str(protocol_path),
        "sha256": _sha256(protocol_path),
        "scorecard_schema": SCORECARD_SCHEMA,
        "pass_rule": PASS_RULE,
        "margins": margins,
        "seed_set": {
            "id": seed_set["seed_set_id"],
            "version": int(seed_set["seed_set_version"]),
            "split": seed_set["split"],
            "path": str(seed_set_path.resolve()),
        },
    }
