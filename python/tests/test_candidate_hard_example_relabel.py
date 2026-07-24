"""Focused ADR-0123 hard-example relabeling tests."""

import copy
from pathlib import Path

import pytest
import torch

from mindustry_agents.training.candidate_distill import distillation_update
from mindustry_agents.training.candidate_distill_check import (
    _synthetic_transitions,
)
from mindustry_agents.training.candidate_hard_example_relabel import (
    CONFIG_SHA256,
    DIAGNOSTIC_RESULT_SHA256,
    HARD_EXAMPLE_WEIGHT,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_MODEL_SHA256,
    SOURCE_OPTIMIZER_SHA256,
    _load_source,
    _source_model_and_optimizer,
    load_hard_example_config,
    weighted_distillation_update,
)
from mindustry_agents.training.candidate_hard_example_relabel_check import (
    build_report,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import save_ippo_checkpoint


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    ROOT
    / "configs/training/m9-candidate-native-hard-example-relabel-v1.json"
)


def test_config_binds_rejected_update64_and_only_weight_change():
    config = load_hard_example_config(CONFIG_PATH)
    source = config["source_checkpoint"]
    learning = config["hard_example_relabeling"]
    assert source["lineage_update"] == 64
    assert source["diagnostic_result_sha256"] == DIAGNOSTIC_RESULT_SHA256
    assert not source["selected_or_promoted"]
    assert not source["repaired"]
    assert learning["hard_example_weight"] == HARD_EXAMPLE_WEIGHT
    assert learning["ordinary_example_weight"] == 1.0
    assert not learning["target_identifiers_added"]
    assert not learning["planner_change"]
    assert not learning["reward_loss"]
    assert not learning["ppo_loss"]
    assert not learning["mappo_loss"]
    assert config["confirmation_seed_set"] is None
    assert config["held_out_seed_set"] is None


def test_bound_local_source_is_rejected_and_exact():
    config = load_hard_example_config(CONFIG_PATH)
    checkpoint_path = ROOT / config["source_checkpoint"]["path"]
    if not checkpoint_path.exists():
        pytest.skip("ignored immutable source checkpoint is not local")
    result, diagnostic, checkpoint = _load_source(ROOT, config)
    assert not result["replica_a"]["construction_passed"]
    assert result["replica_a"]["selected_checkpoint"] is None
    assert diagnostic["classification"][
        "feature_distinguishable_ranking_signal"
    ]
    assert checkpoint.exists()


def test_config_rejects_digest_drift(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_bytes(CONFIG_PATH.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest drifted"):
        load_hard_example_config(path)


def test_source_model_and_optimizer_load_exact_rejected_states():
    config = load_hard_example_config(CONFIG_PATH)
    if not (ROOT / config["source_checkpoint"]["path"]).exists():
        pytest.skip("ignored immutable source checkpoint is not local")
    model, optimizer, payload = _source_model_and_optimizer(ROOT, config)
    assert model_state_digest(model) == SOURCE_MODEL_SHA256
    assert payload["optimizer_state_sha256"] == SOURCE_OPTIMIZER_SHA256
    assert payload["checkpoint_content_sha256"] == (
        SOURCE_CHECKPOINT_CONTENT_SHA256
    )
    assert optimizer.state_dict()["state"]


def test_weighted_update_rejects_misaligned_flags():
    config = load_hard_example_config(CONFIG_PATH)
    transitions = _synthetic_transitions()
    model = SharedRecurrentSelector(9601)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
    with pytest.raises(ValueError, match="weights are misaligned"):
        weighted_distillation_update(
            model,
            optimizer,
            transitions,
            [False],
            config,
            torch.Generator().manual_seed(9613),
        )


def test_all_ordinary_examples_are_exactly_unweighted(tmp_path: Path):
    config = load_hard_example_config(CONFIG_PATH)
    transitions = _synthetic_transitions()
    old_model = SharedRecurrentSelector(9601)
    new_model = SharedRecurrentSelector(9601)
    old_optimizer = torch.optim.Adam(
        old_model.parameters(), lr=0.0001, eps=1e-8
    )
    new_optimizer = torch.optim.Adam(
        new_model.parameters(), lr=0.0001, eps=1e-8
    )
    old_metrics = distillation_update(
        old_model,
        old_optimizer,
        transitions,
        config,
        torch.Generator().manual_seed(9613),
    )
    new_metrics = weighted_distillation_update(
        new_model,
        new_optimizer,
        transitions,
        [False] * len(transitions),
        config,
        torch.Generator().manual_seed(9613),
    )
    old_checkpoint = save_ippo_checkpoint(
        tmp_path / "old.pt",
        old_model,
        old_optimizer,
        update=1,
        parent_checkpoint_content_sha256="0" * 64,
        config_sha256_value=CONFIG_SHA256,
    )
    new_checkpoint = save_ippo_checkpoint(
        tmp_path / "new.pt",
        new_model,
        new_optimizer,
        update=1,
        parent_checkpoint_content_sha256="0" * 64,
        config_sha256_value=CONFIG_SHA256,
    )
    assert old_metrics["teacher_nll"] == new_metrics["teacher_nll"]
    assert old_checkpoint["checkpoint_content_sha256"] == (
        new_checkpoint["checkpoint_content_sha256"]
    )
    assert new_metrics["hard_example_labels"] == 0.0
    assert new_metrics["total_example_weight"] == float(len(transitions))


def test_weighted_nll_is_normalized_by_total_minibatch_weight():
    config = copy.deepcopy(load_hard_example_config(CONFIG_PATH))
    config["epochs_per_update"] = 1
    transitions = _synthetic_transitions()
    config["minibatch_size"] = len(transitions)
    flags = [index < 8 for index in range(len(transitions))]
    model = SharedRecurrentSelector(9601)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
    candidates = torch.stack([item.candidates for item in transitions])
    scalars = torch.stack([item.scalars for item in transitions])
    present = torch.stack(
        [item.candidate_present for item in transitions]
    )
    masks = torch.stack([item.action_mask for item in transitions])
    hidden = torch.stack(
        [item.hidden_input for item in transitions]
    ).detach()
    agent_ids = torch.tensor(
        [item.agent_id for item in transitions], dtype=torch.long
    )
    actions = torch.tensor(
        [item.action for item in transitions], dtype=torch.long
    )
    weights = torch.tensor(
        [HARD_EXAMPLE_WEIGHT if flag else 1.0 for flag in flags]
    )
    with torch.no_grad():
        _, logits, _, _ = model(
            candidates,
            scalars,
            present,
            masks,
            agent_ids,
            hidden,
        )
        nll = -torch.log_softmax(logits, dim=-1).gather(
            1, actions[:, None]
        ).squeeze(1)
        expected = float((weights * nll).sum().item() / weights.sum().item())
    metrics = weighted_distillation_update(
        model,
        optimizer,
        transitions,
        flags,
        config,
        torch.Generator().manual_seed(9613),
    )
    assert metrics["weighted_teacher_nll"] == pytest.approx(expected)
    assert metrics["hard_example_labels"] == 8.0
    assert metrics["total_example_weight"] == (
        8 * HARD_EXAMPLE_WEIGHT + len(transitions) - 8
    )


def test_public_free_preflight_is_exact(tmp_path: Path):
    config = load_hard_example_config(CONFIG_PATH)
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
    assert report["ordinary_equivalence_probe"][
        "all_ordinary_matches_unweighted_update"
    ]
    assert report["weighted_optimizer_probe"]["replicas_equal"]
    assert report["live_student_state_probe"] == {"ran": False}
    assert report["confirmation_or_held_out_access"] is False
    assert report["passed"]
