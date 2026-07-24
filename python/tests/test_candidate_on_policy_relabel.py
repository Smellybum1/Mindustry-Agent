"""Focused ADR-0117 on-policy relabeling tests."""

from pathlib import Path

import pytest
import torch

from mindustry_agents.policies import CandidateNativePlannerV11
from mindustry_agents.training.candidate_on_policy_relabel import (
    CONFIG_SHA256,
    DIAGNOSTIC_RESULT_SHA256,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_MODEL_SHA256,
    SOURCE_OPTIMIZER_SHA256,
    _load_source,
    _source_model_and_optimizer,
    load_on_policy_relabel_config,
    teacher_labels,
)
from mindustry_agents.training.candidate_on_policy_relabel_check import (
    build_report,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    SharedSeatState,
    decide_all_seats,
    model_state_digest,
)
from test_ippo import _boundary


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    ROOT
    / "configs/training/m9-candidate-native-on-policy-relabel-v1.json"
)


def test_config_binds_rejected_source_and_closed_loop_signal():
    config = load_on_policy_relabel_config(CONFIG_PATH)
    assert config["source_checkpoint"]["diagnostic_result_sha256"] == (
        DIAGNOSTIC_RESULT_SHA256
    )
    assert not config["source_checkpoint"]["selected_or_promoted"]
    assert config["on_policy_relabeling"]["student_controls_environment"]
    assert not config["on_policy_relabeling"]["teacher_action_execution"]
    assert config["confirmation_seed_set"] is None
    assert config["held_out_seed_set"] is None


def test_bound_local_source_is_rejected_and_exact():
    config = load_on_policy_relabel_config(CONFIG_PATH)
    checkpoint_path = ROOT / config["source_checkpoint"]["path"]
    if not checkpoint_path.exists():
        pytest.skip("ignored immutable source checkpoint is not local")
    result, diagnostic, checkpoint = _load_source(ROOT, config)
    assert not result["replica_a"]["construction_passed"]
    assert diagnostic["classification"]["closed_loop_shift_signal"]
    assert checkpoint.exists()


def test_config_rejects_digest_drift(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_bytes(CONFIG_PATH.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest drifted"):
        load_on_policy_relabel_config(path)


def test_source_model_and_optimizer_load_exact_states():
    config = load_on_policy_relabel_config(CONFIG_PATH)
    if not (ROOT / config["source_checkpoint"]["path"]).exists():
        pytest.skip("ignored immutable source checkpoint is not local")
    model, optimizer, payload = _source_model_and_optimizer(ROOT, config)
    assert model_state_digest(model) == SOURCE_MODEL_SHA256
    assert payload["optimizer_state_sha256"] == SOURCE_OPTIMIZER_SHA256
    assert payload["checkpoint_content_sha256"] == (
        SOURCE_CHECKPOINT_CONTENT_SHA256
    )
    assert optimizer.state_dict()["state"]


def test_student_actions_and_teacher_labels_have_separate_authority():
    observations, masks, metadata = _boundary()
    model = SharedRecurrentSelector(9601)
    decision = decide_all_seats(
        model,
        SharedSeatState.fresh(),
        observations,
        masks,
        metadata,
        evaluation=True,
    )
    planner = CandidateNativePlannerV11()
    teacher = planner.actions(observations, masks, [])
    labels = teacher_labels(decision, teacher, observations)
    assert decision.agent_actions
    assert labels
    assert all(
        decision.features[agent_id].action_mask[label]
        for agent_id, label in labels.items()
    )

    forced_teacher = [
        {
            "agent_id": agent_id,
            "task_action": {"type": "ABANDON", "reason": "diagnostic"},
        }
        for agent_id in range(3)
    ]
    assert teacher_labels(decision, forced_teacher, observations) == {}


def test_public_free_preflight_is_exact(tmp_path: Path):
    config = load_on_policy_relabel_config(CONFIG_PATH)
    if not (ROOT / config["source_checkpoint"]["path"]).exists():
        pytest.skip("ignored immutable source checkpoint is not local")
    report = build_report(
        ROOT,
        tmp_path / "preflight.json",
        java="java",
        port=47810,
        live=False,
    )
    assert report["config_sha256"] == CONFIG_SHA256
    assert report["optimizer_probe"]["replicas_equal"]
    assert report["live_student_state_probe"] == {"ran": False}
    assert report["confirmation_or_held_out_access"] is False
    assert report["passed"]
