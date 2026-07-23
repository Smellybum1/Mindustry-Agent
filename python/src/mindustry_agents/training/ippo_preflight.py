"""Fail-closed validation of every committed M9 IPPO pretraining artifact."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo_diverse_roots_check import build_report
from mindustry_agents.training.ippo_entropy_check import (
    build_report as build_entropy_report,
)
from mindustry_agents.training.ippo_success_imitation_check import (
    build_report as build_success_imitation_report,
)
from mindustry_agents.training.ippo_success_margin_check import (
    build_report as build_success_margin_report,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V1_CONFIG_SHA256,
    IPPO_V1_PROTOCOL_SHA256,
    IPPO_V2_CONFIG_SHA256,
    IPPO_V2_PROTOCOL_SHA256,
    IPPO_V3_CONFIG_SHA256,
    IPPO_V3_PROTOCOL_SHA256,
    IPPO_V4_CONFIG_SHA256,
    IPPO_V4_PROTOCOL_SHA256,
    IPPO_V5_CONFIG_SHA256,
    IPPO_V5_PROTOCOL_SHA256,
    IPPO_V6_CONFIG_SHA256,
    IPPO_V6_PROTOCOL_SHA256,
    load_ippo_v1_config,
    load_ippo_v2_config,
    load_ippo_v3_config,
    load_ippo_v4_config,
    load_ippo_v5_config,
    load_ippo_v6_config,
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
EXPECTED_V2 = {
    **EXPECTED,
    "configs/evaluation/m9-ippo-v2-sequence16-optimizer-check.json": (
        "580493699e7c342b1932afd272c43353fed20180b1fa6511fb2ad76809f6ea63"
    ),
}
EXPECTED_V3 = {
    **EXPECTED,
    "configs/evaluation/m9-ippo-v3-diverse2048-roots-check.json": (
        "e8334ee662e718b7d6e4f53aadaff0d58b51f2afeba18113c06393e399dfbcdd"
    ),
}
EXPECTED_V4 = {
    **EXPECTED_V3,
    "configs/evaluation/m9-ippo-v4-entropy-optimizer-check.json": (
        "44a33c55693686d347ad21fbca3874dc61222c07a8e9bdd55b131f8c4e2dcc49"
    ),
}
EXPECTED_V5 = {
    **EXPECTED_V4,
    "configs/evaluation/m9-ippo-v5-success-imitation-optimizer-check.json": (
        "c8676245cee741f0d2971543f3f4789522f8d8f25de8e34d54b6114ad150dd00"
    ),
}
EXPECTED_V6 = {
    **EXPECTED_V4,
    "configs/evaluation/m9-ippo-v6-success-margin-optimizer-check.json": (
        "4dc0463838756789c8e5a3b7e15a5b038a1095132379c4fe82059210ba26798a"
    ),
}

GATES = (
    "test-python",
    "test-java",
    "m9-reward-check",
    "m9-shared-policy-check",
    "m9-rollout-check",
    "m9-artifact-check",
    "smoke",
    "determinism",
)
V2_GATES = (
    "test-python",
    "test-java",
    "m9-reward-check",
    "m9-shared-policy-check",
    "m9-rollout-check",
    "m9-sequence-check",
    "m9-artifact-check",
    "smoke",
    "determinism",
)
V3_GATES = (
    "test-python",
    "test-java",
    "m9-reward-check",
    "m9-shared-policy-check",
    "m9-rollout-check",
    "m9-diverse-roots-check",
    "m9-artifact-check",
    "smoke",
    "determinism",
)
V4_GATES = (
    "test-python",
    "test-java",
    "m9-reward-check",
    "m9-shared-policy-check",
    "m9-rollout-check",
    "m9-diverse-roots-check",
    "m9-entropy-check",
    "m9-artifact-check",
    "smoke",
    "determinism",
)
V5_GATES = (
    "test-python",
    "test-java",
    "m9-reward-check",
    "m9-shared-policy-check",
    "m9-rollout-check",
    "m9-diverse-roots-check",
    "m9-entropy-check",
    "m9-success-imitation-check",
    "m9-artifact-check",
    "smoke",
    "determinism",
)
V6_GATES = (
    "test-python",
    "test-java",
    "m9-reward-check",
    "m9-shared-policy-check",
    "m9-rollout-check",
    "m9-diverse-roots-check",
    "m9-entropy-check",
    "m9-success-margin-check",
    "m9-artifact-check",
    "smoke",
    "determinism",
)


def _load(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    actual = sha256_path(path)
    if actual != EXPECTED[relative]:
        raise ValueError(f"M9 pretraining artifact hash drifted: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def _project_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
    ).strip()


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
        "implementation_commit": _project_commit(root),
        "config_sha256": IPPO_V1_CONFIG_SHA256,
        "protocol_sha256": IPPO_V1_PROTOCOL_SHA256,
        "artifacts": EXPECTED,
        "gates": list(GATES),
        "public_baseline_wins": baseline["aggregate"]["wins"],
        "checkpoint_content_sha256": checkpoint["checkpoint_content_sha256"],
        "checkpoint_trace_sha256": artifact["episode"]["trace_sha256"],
        "manifest_reproducibility_digest": artifact[
            "manifest_reproducibility_digest"
        ],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def _sequence_identity(report: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(report)
    result.pop("implementation_commit", None)
    return result


def _diverse_identity(report: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(report)
    result.pop("implementation_commit", None)
    return result


def _entropy_identity(report: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(report)
    result.pop("implementation_commit", None)
    return result


def _success_imitation_identity(
    report: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(report)
    result.pop("implementation_commit", None)
    return result


def _success_margin_identity(report: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(report)
    result.pop("implementation_commit", None)
    return result


def validate_v2_preflight(root: Path | None = None) -> dict[str, Any]:
    """Validate ADR-0073's committed and freshly rerun sequence boundary."""

    root = root or repo_root()
    config_path = root / "configs/training/m9-ippo-v2-sequence16.json"
    config = load_ippo_v2_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V2_PROTOCOL_SHA256:
        raise ValueError("M9 v2 public protocol hash drifted")
    if sha256_path(config_path) != IPPO_V2_CONFIG_SHA256:
        raise ValueError("M9 v2 config hash drifted")
    if (
        config["confirmation_seed_set"] is not None
        or config["held_out_seed_set"] is not None
    ):
        raise ValueError("M9 v2 pretraining config gained sealed-data authority")

    inherited = validate_preflight(root)
    baseline = _load(
        root, "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
    )
    sequence_path = (
        root
        / "configs/evaluation/m9-ippo-v2-sequence16-optimizer-check.json"
    )
    if sha256_path(sequence_path) != EXPECTED_V2[
        "configs/evaluation/m9-ippo-v2-sequence16-optimizer-check.json"
    ]:
        raise ValueError("M9 v2 committed sequence evidence hash drifted")
    sequence = json.loads(sequence_path.read_text(encoding="utf-8"))
    current_sequence_path = root / "runs/m9-ippo-v2-sequence-check.json"
    current_sequence = json.loads(
        current_sequence_path.read_text(encoding="utf-8")
    )
    commit = _project_commit(root)
    if (
        inherited.get("passed") is not True
        or inherited.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 v2 inherited public evidence is incomplete")
    if (
        sequence.get("schema") != "m9_ippo_v2_sequence_check_v1"
        or sequence.get("implementation_commit")
        != "9428d90055f28c402b5bb1456cf1b42b08c81a9e"
        or sequence.get("config_sha256") != IPPO_V2_CONFIG_SHA256
        or sequence.get("independent_processes_exact") is not True
        or sequence.get("optimizer_and_checkpoint_exact") is not True
        or sequence.get("confirmation_or_held_out_access") is not False
        or current_sequence.get("implementation_commit") != commit
        or _sequence_identity(current_sequence)
        != _sequence_identity(sequence)
    ):
        raise ValueError("M9 v2 sequence evidence is incomplete or divergent")
    return {
        "schema": "m9_ippo_v2_preflight_v1",
        "implementation_commit": commit,
        "sequence_implementation_commit": sequence[
            "implementation_commit"
        ],
        "config_sha256": IPPO_V2_CONFIG_SHA256,
        "protocol_sha256": IPPO_V2_PROTOCOL_SHA256,
        "artifacts": EXPECTED_V2,
        "gates": list(V2_GATES),
        "public_baseline_wins": baseline["aggregate"]["wins"],
        "sequence_checkpoint_content_sha256": sequence["checkpoint"][
            "checkpoint_content_sha256"
        ],
        "sequence_final_model_state_sha256": sequence[
            "final_model_state_sha256"
        ],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def validate_v3_preflight(root: Path | None = None) -> dict[str, Any]:
    """Validate ADR-0075's public diverse-root boundary."""

    root = root or repo_root()
    config_path = root / "configs/training/m9-ippo-v3-diverse2048.json"
    config = load_ippo_v3_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V3_PROTOCOL_SHA256:
        raise ValueError("M9 v3 public protocol hash drifted")
    if sha256_path(config_path) != IPPO_V3_CONFIG_SHA256:
        raise ValueError("M9 v3 config hash drifted")
    if (
        config["confirmation_seed_set"] is not None
        or config["held_out_seed_set"] is not None
    ):
        raise ValueError("M9 v3 pretraining config gained sealed-data authority")

    inherited = validate_preflight(root)
    baseline = _load(
        root, "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
    )
    committed_path = (
        root
        / "configs/evaluation/m9-ippo-v3-diverse2048-roots-check.json"
    )
    if sha256_path(committed_path) != EXPECTED_V3[
        "configs/evaluation/m9-ippo-v3-diverse2048-roots-check.json"
    ]:
        raise ValueError("M9 v3 committed diverse-root evidence hash drifted")
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    current_path = root / "runs/m9-ippo-v3-diverse-roots-check.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    expected = build_report(root)
    commit = _project_commit(root)
    if (
        inherited.get("passed") is not True
        or inherited.get("confirmation_or_held_out_access") is not False
        or current != expected
        or committed.get("schema")
        != "m9_ippo_v3_diverse_roots_check_v1"
        or committed.get("implementation_commit")
        != "f32cba6f7258a83d6f5b125ce95b76d8c9ecffb5"
        or committed.get("config_sha256") != IPPO_V3_CONFIG_SHA256
        or committed.get("protocol_sha256") != IPPO_V3_PROTOCOL_SHA256
        or committed.get("all_passed") is not True
        or committed.get("confirmation_or_held_out_access") is not False
        or current.get("implementation_commit") != commit
        or _diverse_identity(current) != _diverse_identity(committed)
    ):
        raise ValueError("M9 v3 diverse-root evidence is incomplete or divergent")
    return {
        "schema": "m9_ippo_v3_preflight_v1",
        "implementation_commit": commit,
        "diverse_roots_implementation_commit": committed[
            "implementation_commit"
        ],
        "config_sha256": IPPO_V3_CONFIG_SHA256,
        "protocol_sha256": IPPO_V3_PROTOCOL_SHA256,
        "artifacts": EXPECTED_V3,
        "gates": list(V3_GATES),
        "public_baseline_wins": baseline["aggregate"]["wins"],
        "train_seed_sha256": current["train_seed_sha256"],
        "training_schedule_sha256": current["schedule_sha256"],
        "training_root_count": current["root_count"],
        "training_root_reuse_count": current["root_reuse_count"],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def validate_v4_preflight(root: Path | None = None) -> dict[str, Any]:
    """Validate ADR-0079's public entropy-annealing boundary."""

    root = root or repo_root()
    config_path = root / "configs/training/m9-ippo-v4-entropy-anneal.json"
    config = load_ippo_v4_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V4_PROTOCOL_SHA256:
        raise ValueError("M9 v4 public protocol hash drifted")
    if sha256_path(config_path) != IPPO_V4_CONFIG_SHA256:
        raise ValueError("M9 v4 config hash drifted")
    if (
        config["confirmation_seed_set"] is not None
        or config["held_out_seed_set"] is not None
    ):
        raise ValueError("M9 v4 pretraining config gained sealed-data authority")

    inherited = validate_v3_preflight(root)
    baseline = _load(
        root, "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
    )
    committed_path = (
        root
        / "configs/evaluation/m9-ippo-v4-entropy-optimizer-check.json"
    )
    if sha256_path(committed_path) != EXPECTED_V4[
        "configs/evaluation/m9-ippo-v4-entropy-optimizer-check.json"
    ]:
        raise ValueError("M9 v4 committed entropy evidence hash drifted")
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    current_path = root / "runs/m9-ippo-v4-entropy-check.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    expected = build_entropy_report(root)
    commit = _project_commit(root)
    if (
        inherited.get("passed") is not True
        or inherited.get("confirmation_or_held_out_access") is not False
        or current != expected
        or committed.get("schema") != "m9_ippo_v4_entropy_check_v1"
        or committed.get("implementation_commit")
        != "d232d64dc5763c1a46bdada9b21c895459d493e8"
        or committed.get("config_sha256") != IPPO_V4_CONFIG_SHA256
        or committed.get("protocol_sha256") != IPPO_V4_PROTOCOL_SHA256
        or committed.get("semantic_inheritance_exact") is not True
        or committed.get("all_passed") is not True
        or committed.get("confirmation_or_held_out_access") is not False
        or current.get("implementation_commit") != commit
        or _entropy_identity(current) != _entropy_identity(committed)
    ):
        raise ValueError("M9 v4 entropy evidence is incomplete or divergent")
    return {
        "schema": "m9_ippo_v4_preflight_v1",
        "implementation_commit": commit,
        "entropy_implementation_commit": committed["implementation_commit"],
        "config_sha256": IPPO_V4_CONFIG_SHA256,
        "protocol_sha256": IPPO_V4_PROTOCOL_SHA256,
        "artifacts": EXPECTED_V4,
        "gates": list(V4_GATES),
        "public_baseline_wins": baseline["aggregate"]["wins"],
        "entropy_schedule_sha256": current["coefficient_schedule_sha256"],
        "training_schedule_sha256": current["training_schedule_sha256"],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def validate_v5_preflight(root: Path | None = None) -> dict[str, Any]:
    """Validate ADR-0083's public success-imitation boundary."""

    root = root or repo_root()
    config_path = (
        root / "configs/training/m9-ippo-v5-success-imitation.json"
    )
    config = load_ippo_v5_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V5_PROTOCOL_SHA256:
        raise ValueError("M9 v5 public protocol hash drifted")
    if sha256_path(config_path) != IPPO_V5_CONFIG_SHA256:
        raise ValueError("M9 v5 config hash drifted")
    if (
        config["confirmation_seed_set"] is not None
        or config["held_out_seed_set"] is not None
    ):
        raise ValueError("M9 v5 pretraining config gained sealed-data authority")

    inherited = validate_v4_preflight(root)
    baseline = _load(
        root, "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
    )
    relative = (
        "configs/evaluation/"
        "m9-ippo-v5-success-imitation-optimizer-check.json"
    )
    committed_path = root / relative
    if sha256_path(committed_path) != EXPECTED_V5[relative]:
        raise ValueError(
            "M9 v5 committed success-imitation evidence hash drifted"
        )
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    current_path = (
        root / "runs/m9-ippo-v5-success-imitation-check.json"
    )
    current = json.loads(current_path.read_text(encoding="utf-8"))
    expected = build_success_imitation_report(root)
    commit = _project_commit(root)
    metrics = committed.get("optimizer", {}).get("metrics", {})
    if (
        inherited.get("passed") is not True
        or inherited.get("confirmation_or_held_out_access") is not False
        or current != expected
        or committed.get("schema")
        != "m9_ippo_v5_success_imitation_check_v1"
        or committed.get("implementation_commit")
        != "d6969679ad7e500756660f2a820815b1998a51f9"
        or committed.get("config_sha256") != IPPO_V5_CONFIG_SHA256
        or committed.get("protocol_sha256") != IPPO_V5_PROTOCOL_SHA256
        or committed.get("semantic_inheritance_exact") is not True
        or committed.get("optimizer", {}).get("independent_runs_exact")
        is not True
        or metrics.get("success_imitation_coefficient") != 0.02
        or metrics.get("success_imitation_qualifying_episodes") != 1.0
        or metrics.get("success_imitation_qualifying_transitions") != 1.0
        or metrics.get("success_imitation_active_minibatches") != 8.0
        or committed.get("all_passed") is not True
        or committed.get("confirmation_or_held_out_access") is not False
        or current.get("implementation_commit") != commit
        or _success_imitation_identity(current)
        != _success_imitation_identity(committed)
    ):
        raise ValueError(
            "M9 v5 success-imitation evidence is incomplete or divergent"
        )
    return {
        "schema": "m9_ippo_v5_preflight_v1",
        "implementation_commit": commit,
        "success_imitation_implementation_commit": committed[
            "implementation_commit"
        ],
        "config_sha256": IPPO_V5_CONFIG_SHA256,
        "protocol_sha256": IPPO_V5_PROTOCOL_SHA256,
        "artifacts": EXPECTED_V5,
        "gates": list(V5_GATES),
        "public_baseline_wins": baseline["aggregate"]["wins"],
        "success_imitation_probe_sha256": current["optimizer"][
            "probe_sha256"
        ],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def validate_v6_preflight(root: Path | None = None) -> dict[str, Any]:
    """Validate ADR-0087's public success-margin boundary."""

    root = root or repo_root()
    config_path = root / "configs/training/m9-ippo-v6-success-margin.json"
    config = load_ippo_v6_config(config_path)
    protocol_path = root / config["public_evaluation_protocol"]
    if sha256_path(protocol_path) != IPPO_V6_PROTOCOL_SHA256:
        raise ValueError("M9 v6 public protocol hash drifted")
    if sha256_path(config_path) != IPPO_V6_CONFIG_SHA256:
        raise ValueError("M9 v6 config hash drifted")
    if (
        config["confirmation_seed_set"] is not None
        or config["held_out_seed_set"] is not None
    ):
        raise ValueError("M9 v6 pretraining config gained sealed-data authority")

    inherited = validate_v4_preflight(root)
    baseline = _load(
        root, "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
    )
    relative = (
        "configs/evaluation/m9-ippo-v6-success-margin-optimizer-check.json"
    )
    committed_path = root / relative
    if sha256_path(committed_path) != EXPECTED_V6[relative]:
        raise ValueError("M9 v6 committed success-margin evidence hash drifted")
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    current_path = root / "runs/m9-ippo-v6-success-margin-check.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    expected = build_success_margin_report(root)
    commit = _project_commit(root)
    metrics = committed.get("optimizer", {}).get("metrics", {})
    if (
        inherited.get("passed") is not True
        or inherited.get("confirmation_or_held_out_access") is not False
        or current != expected
        or committed.get("schema") != "m9_ippo_v6_success_margin_check_v1"
        or committed.get("implementation_commit")
        != "05e6b487727cbefae8f104838dd2a428ee9511c4"
        or committed.get("config_sha256") != IPPO_V6_CONFIG_SHA256
        or committed.get("protocol_sha256") != IPPO_V6_PROTOCOL_SHA256
        or committed.get("semantic_inheritance_exact") is not True
        or committed.get("optimizer", {}).get("independent_runs_exact")
        is not True
        or metrics.get("success_margin_coefficient") != 0.02
        or metrics.get("success_margin_target") != 0.1
        or metrics.get("success_margin_qualifying_episodes") != 1.0
        or metrics.get("success_margin_qualifying_transitions") != 1.0
        or metrics.get("success_margin_active_minibatches") != 8.0
        or committed.get("all_passed") is not True
        or committed.get("confirmation_or_held_out_access") is not False
        or current.get("implementation_commit") != commit
        or _success_margin_identity(current)
        != _success_margin_identity(committed)
    ):
        raise ValueError(
            "M9 v6 success-margin evidence is incomplete or divergent"
        )
    return {
        "schema": "m9_ippo_v6_preflight_v1",
        "implementation_commit": commit,
        "success_margin_implementation_commit": committed[
            "implementation_commit"
        ],
        "config_sha256": IPPO_V6_CONFIG_SHA256,
        "protocol_sha256": IPPO_V6_PROTOCOL_SHA256,
        "artifacts": EXPECTED_V6,
        "gates": list(V6_GATES),
        "public_baseline_wins": baseline["aggregate"]["wins"],
        "success_margin_probe_sha256": current["optimizer"]["probe_sha256"],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def write_preflight(
    path: Path,
    root: Path | None = None,
    *,
    candidate: str = "v1",
) -> dict[str, Any]:
    if candidate == "v2":
        result = validate_v2_preflight(root)
    elif candidate == "v3":
        result = validate_v3_preflight(root)
    elif candidate == "v4":
        result = validate_v4_preflight(root)
    elif candidate == "v5":
        result = validate_v5_preflight(root)
    elif candidate == "v6":
        result = validate_v6_preflight(root)
    else:
        result = validate_preflight(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate committed M9 pretraining evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="atomically write the deterministic preflight result",
    )
    parser.add_argument(
        "--candidate",
        choices=("v1", "v2", "v3", "v4", "v5", "v6"),
        default="v1",
    )
    args = parser.parse_args()
    result = (
        write_preflight(args.output, candidate=args.candidate)
        if args.output is not None
        else (
            validate_v6_preflight()
            if args.candidate == "v6"
            else (
                validate_v5_preflight()
                if args.candidate == "v5"
                else (
                    validate_v4_preflight()
                    if args.candidate == "v4"
                    else (
                        validate_v2_preflight()
                        if args.candidate == "v2"
                        else (
                            validate_v3_preflight()
                            if args.candidate == "v3"
                            else validate_preflight()
                        )
                    )
                )
            )
        )
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
