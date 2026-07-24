"""Focused ADR-0129 micro-DAgger tests."""

from pathlib import Path

import pytest
import torch

from mindustry_agents.training.candidate_distill_check import (
    _synthetic_transitions,
)
from mindustry_agents.training.candidate_micro_dagger import (
    CONFIG_SHA256,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_MODEL_SHA256,
    SOURCE_OPTIMIZER_SHA256,
    _source_model_and_optimizer,
    load_micro_dagger_config,
    micro_dagger_optimizer_schedule,
)
from mindustry_agents.training.candidate_micro_dagger_check import build_report
from mindustry_agents.training.ippo import model_state_digest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT / "configs/training/m9-candidate-native-micro-dagger-v1.json"
)


def test_config_freezes_maximal_freshness_only():
    config = load_micro_dagger_config(CONFIG)
    assert config["macro_updates"] == 32
    assert config["micro_updates_per_macro_update"] == 8
    assert config["optimizer_epochs_per_micro_update"] == 1
    assert config["training_root_schedule"]["total_collection_episodes"] == 16384
    learning = config["micro_dagger"]
    assert not learning["cross_micro_replay"]
    assert not learning["example_weighting"]
    assert not learning["sequence_backpropagation"]
    assert not learning["ppo_loss"]
    assert config["confirmation_seed_set"] is None
    assert config["held_out_seed_set"] is None


def test_config_rejects_digest_drift(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_bytes(CONFIG.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest drifted"):
        load_micro_dagger_config(path)


def test_exact_rejected_source_model_and_optimizer_load():
    config = load_micro_dagger_config(CONFIG)
    model, optimizer, payload = _source_model_and_optimizer(ROOT, config)
    assert model_state_digest(model) == SOURCE_MODEL_SHA256
    assert payload["optimizer_state_sha256"] == SOURCE_OPTIMIZER_SHA256
    assert payload["checkpoint_content_sha256"] == (
        SOURCE_CHECKPOINT_CONTENT_SHA256
    )
    assert optimizer.state_dict()["state"]


def test_schedule_requires_exactly_eight_fresh_datasets():
    config = load_micro_dagger_config(CONFIG)
    model, optimizer, _ = _source_model_and_optimizer(ROOT, config)
    with pytest.raises(ValueError, match="dataset count drifted"):
        micro_dagger_optimizer_schedule(
            model, optimizer, [_synthetic_transitions()], config,
            torch.Generator().manual_seed(9613),
        )


def test_configured_schedule_is_deterministic():
    config = load_micro_dagger_config(CONFIG)
    base = _synthetic_transitions()
    datasets = [base[index:] + base[:index] for index in range(8)]
    rows = []
    for _ in range(2):
        model, optimizer, _ = _source_model_and_optimizer(ROOT, config)
        metrics = micro_dagger_optimizer_schedule(
            model, optimizer, datasets, config,
            torch.Generator().manual_seed(9613),
        )
        rows.append((model_state_digest(model), metrics))
    assert rows[0] == rows[1]


def test_public_free_preflight(tmp_path: Path):
    report = build_report(
        ROOT, tmp_path / "preflight.json",
        java="java", port=47810, live=False,
    )
    assert report["config_sha256"] == CONFIG_SHA256
    assert report["single_micro_update_equivalence_probe"][
        "matches_flat_nll_exactly"
    ]
    assert report["configured_schedule_probe"]["replicas_equal"]
    assert report["live_fresh_collection_probe"] == {"ran": False}
    assert report["confirmation_or_held_out_access"] is False
    assert report["passed"]
