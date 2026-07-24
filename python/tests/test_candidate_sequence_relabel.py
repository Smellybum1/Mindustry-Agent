"""Focused ADR-0127 contiguous sequence relabeling tests."""

import copy
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from mindustry_agents.training.candidate_distill_check import (
    _synthetic_transitions,
)
from mindustry_agents.training.candidate_sequence_relabel import (
    CONFIG_SHA256,
    SEQUENCE_LENGTH,
    SEQUENCES_PER_MINIBATCH,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_MODEL_SHA256,
    SOURCE_OPTIMIZER_SHA256,
    _load_source,
    _source_model_and_optimizer,
    load_sequence_relabel_config,
    sequence_distillation_update,
    supervised_sequence_windows,
)
from mindustry_agents.training.candidate_sequence_relabel_check import (
    _episodes_for_synthetic_sequence,
    build_report,
)
from mindustry_agents.training.ippo import model_state_digest
from mindustry_agents.training.ippo_ppo import IPPOEpisodeRollout


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    ROOT
    / "configs/training/m9-candidate-native-sequence-relabel-v1.json"
)


def test_config_binds_rejected_update64_and_only_sequence_change():
    config = load_sequence_relabel_config(CONFIG_PATH)
    source = config["source_checkpoint"]
    learning = config["sequence_relabeling"]
    assert source["lineage_update"] == 64
    assert not source["construction_passed"]
    assert not source["selected_or_promoted"]
    assert not source["repaired"]
    assert source["load_model_state"]
    assert source["load_optimizer_state"]
    assert learning["sequence_length"] == SEQUENCE_LENGTH
    assert (
        learning["sequences_per_minibatch"]
        == SEQUENCES_PER_MINIBATCH
    )
    assert not learning["example_weighting"]
    assert not learning["ppo_loss"]
    assert not learning["critic_loss"]
    assert not learning["ema"]
    assert not learning["replay"]
    assert config["confirmation_seed_set"] is None
    assert config["held_out_seed_set"] is None


def test_bound_local_source_is_rejected_and_exact():
    config = load_sequence_relabel_config(CONFIG_PATH)
    checkpoint_path = ROOT / config["source_checkpoint"]["path"]
    if not checkpoint_path.exists():
        pytest.skip("ignored immutable source checkpoint is not local")
    result, diagnostic, checkpoint = _load_source(ROOT, config)
    assert not result["replica_a"]["construction_passed"]
    assert result["replica_a"]["selected_checkpoint"] is None
    assert diagnostic["classification"]["low_correction_signal"]
    assert not diagnostic["successor_training_authorized"]
    assert checkpoint.exists()


def test_config_rejects_digest_drift(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_bytes(CONFIG_PATH.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest drifted"):
        load_sequence_relabel_config(path)


def test_source_model_and_optimizer_load_exact_rejected_states():
    config = load_sequence_relabel_config(CONFIG_PATH)
    if not (ROOT / config["source_checkpoint"]["path"]).exists():
        pytest.skip("ignored immutable source checkpoint is not local")
    model, optimizer, payload = _source_model_and_optimizer(ROOT, config)
    assert model_state_digest(model) == SOURCE_MODEL_SHA256
    assert payload["optimizer_state_sha256"] == SOURCE_OPTIMIZER_SHA256
    assert payload["checkpoint_content_sha256"] == (
        SOURCE_CHECKPOINT_CONTENT_SHA256
    )
    assert optimizer.state_dict()["state"]


def test_windows_partition_by_agent_reset_and_drop_empty_context():
    raw = _synthetic_transitions()[:4]
    transitions = (
        replace(
            raw[0],
            agent_id=0,
            recurrent_reset=True,
            policy_loss_mask=False,
        ),
        replace(
            raw[1],
            agent_id=0,
            recurrent_reset=False,
            policy_loss_mask=False,
        ),
        replace(
            raw[2],
            agent_id=0,
            recurrent_reset=True,
            policy_loss_mask=False,
        ),
        replace(
            raw[3],
            agent_id=0,
            recurrent_reset=False,
            policy_loss_mask=True,
        ),
    )
    episode = IPPOEpisodeRollout(1, "win", transitions)
    flattened, windows, metrics = supervised_sequence_windows(
        [episode], sequence_length=16
    )
    assert all(
        first is second
        for first, second in zip(flattened, transitions, strict=True)
    )
    assert windows == ((2, 3),)
    assert metrics == {
        "all_windows": 2,
        "retained_windows": 1,
        "dropped_zero_label_windows": 1,
        "retained_transitions": 2,
        "dropped_context_transitions": 2,
    }


def test_governed_optimizer_is_deterministic_and_counts_padding():
    config = load_sequence_relabel_config(CONFIG_PATH)
    episodes = _episodes_for_synthetic_sequence(_synthetic_transitions())
    rows = []
    for _ in range(2):
        model, optimizer, _ = _source_model_and_optimizer(ROOT, config)
        metrics = sequence_distillation_update(
            model,
            optimizer,
            episodes,
            config,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
        )
        rows.append((model_state_digest(model), metrics))
    assert rows[0] == rows[1]
    assert rows[0][1]["labels"] == 32.0
    assert rows[0][1]["retained_context_transitions"] == 8.0
    assert rows[0][1]["real_transition_presentations"] == 320.0
    assert rows[0][1]["padded_transition_slots"] == 64.0


def test_public_optimizer_rejects_sequence_contract_drift():
    config = copy.deepcopy(load_sequence_relabel_config(CONFIG_PATH))
    config["sequence_relabeling"]["sequence_length"] = 1
    model, optimizer, _ = _source_model_and_optimizer(ROOT, config)
    with pytest.raises(ValueError, match="contract drifted"):
        sequence_distillation_update(
            model,
            optimizer,
            _episodes_for_synthetic_sequence(_synthetic_transitions()),
            config,
            torch.Generator().manual_seed(9613),
        )


def test_public_free_preflight_is_exact(tmp_path: Path):
    config = load_sequence_relabel_config(CONFIG_PATH)
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
    assert report["inherited_contract_probe"]["passed"]
    assert report["length_one_equivalence_probe"][
        "matches_flat_optimizer_exactly"
    ]
    assert report["configured_optimizer_probe"]["replicas_equal"]
    assert report["context_gradient_probe"][
        "masked_context_changes_supervised_gradient"
    ]
    assert report["live_student_state_probe"] == {"ran": False}
    assert report["confirmation_or_held_out_access"] is False
    assert report["passed"]
