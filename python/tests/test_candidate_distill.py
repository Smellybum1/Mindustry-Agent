"""Focused ADR-0113 candidate-native distillation tests."""

from pathlib import Path

import torch

from mindustry_agents.training.candidate_distill import (
    CONFIG_SHA256,
    SOURCE_RESULT_SHA256,
    _load_source,
    distillation_update,
    load_distillation_config,
)
from mindustry_agents.training.candidate_distill_check import (
    _synthetic_transitions,
    build_report,
)
from mindustry_agents.training.ippo import (
    IPPO_MODEL_ARCHITECTURE,
    SharedRecurrentSelector,
    SharedSeatState,
    decide_all_seats,
    model_state_digest,
)
from test_ippo import _boundary


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    ROOT / "configs/training/m9-candidate-native-distill-v1.json"
)


def test_config_binds_public_candidate_native_source():
    config = load_distillation_config(CONFIG_PATH)
    assert config["model_architecture"] == IPPO_MODEL_ARCHITECTURE
    assert config["source_policy"]["accepted_result_sha256"] == (
        SOURCE_RESULT_SHA256
    )
    assert config["confirmation_seed_set"] is None
    assert config["held_out_seed_set"] is None
    assert _load_source(ROOT, config)["wins"] == 32


def test_config_rejects_digest_drift(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_bytes(CONFIG_PATH.read_bytes() + b"\n")
    try:
        load_distillation_config(path)
    except ValueError as error:
        assert "digest drifted" in str(error)
    else:
        raise AssertionError("drifted distillation config was accepted")


def test_distillation_update_is_exact_and_changes_model():
    config = load_distillation_config(CONFIG_PATH)
    transitions = _synthetic_transitions()
    rows = []
    for _ in range(2):
        model = SharedRecurrentSelector(int(config["model_init_seed"]))
        before = model_state_digest(model)
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=float(config["learning_rate"]),
            eps=float(config["adam_epsilon"]),
        )
        metrics = distillation_update(
            model,
            optimizer,
            transitions,
            config,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
        )
        rows.append((before, model_state_digest(model), metrics))
    assert rows[0] == rows[1]
    assert rows[0][0] != rows[0][1]
    assert rows[0][2]["labels"] == 40.0
    assert rows[0][2]["teacher_nll"] > 0.0


def test_distillation_rejects_illegal_label():
    config = load_distillation_config(CONFIG_PATH)
    transition = _synthetic_transitions()[0]
    transition.action_mask[transition.action] = False
    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)
    try:
        distillation_update(
            model,
            optimizer,
            [transition],
            config,
            torch.Generator().manual_seed(1),
        )
    except ValueError as error:
        assert "outside its mask" in str(error)
    else:
        raise AssertionError("illegal distillation label was accepted")


def test_public_free_preflight_is_exact(tmp_path: Path):
    report = build_report(
        ROOT,
        tmp_path / "preflight.json",
        java="java",
        port=47810,
        live=False,
    )
    assert report["config_sha256"] == CONFIG_SHA256
    assert report["optimizer_probe"]["replicas_equal"]
    assert report["live_teacher_probe"] == {"ran": False}
    assert report["confirmation_or_held_out_access"] is False
    assert report["passed"]


def test_teacher_can_execute_non_actor_abandon_without_label_authority():
    observations, masks, metadata = _boundary()
    teacher = [
        {
            "agent_id": agent_id,
            "task_action": {"type": "ABANDON", "reason": "wave_preempt"},
        }
        for agent_id in range(3)
    ]
    decision = decide_all_seats(
        SharedRecurrentSelector(9601),
        SharedSeatState.fresh(),
        observations,
        masks,
        metadata,
        evaluation=True,
        teacher_actions=teacher,
    )
    assert decision.agent_actions == teacher
    assert not any(decision.policy_loss_masks.values())
