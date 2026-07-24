"""Governance tests for ADR-0137 continuation regret."""

import json
from pathlib import Path

import pytest
import torch

from mindustry_agents.policies import CandidateNativePlannerV11
from mindustry_agents.training.candidate_continuation_regret import (
    BUNDLE_INPUT_WIDTH,
    CONFIG_SHA256,
    GLOBAL_HIDDEN_WIDTH,
    GLOBAL_INPUT_WIDTH,
    HORIZONS,
    PROTOCOL_SHA256,
    ContinuationRegretSelector,
    ContinuationRootExample,
    continuation_update,
    load_continuation_config,
    planner_bundle_ranking,
    sample_bundles,
    source_model_and_optimizer,
    validate_protocol,
)
from mindustry_agents.training.candidate_continuation_regret_train import (
    load_checkpoint,
    save_checkpoint,
    validate_preflight,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import _state_digest
from mindustry_agents.training.ippo_ppo import sha256_path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs/training/m9-candidate-native-continuation-regret-v1.json"
)
PROTOCOL = (
    ROOT
    / "configs/evaluation/"
    "m9-candidate-native-continuation-regret-v1-public-protocol.json"
)


def _model() -> ContinuationRegretSelector:
    base = SharedRecurrentSelector(9601)
    model = ContinuationRegretSelector(1, new_parameter_seed=9721)
    incompatible = model.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert all(
        key.startswith(("global_recurrent_cell.", "bundle_cost_head."))
        for key in incompatible.missing_keys
    )
    model.freeze_source()
    return model


def _example() -> ContinuationRootExample:
    prefix = torch.linspace(
        -0.5, 0.5, 9 * GLOBAL_INPUT_WIDTH
    ).reshape(9, GLOBAL_INPUT_WIDTH)
    static = torch.zeros((8, BUNDLE_INPUT_WIDTH - GLOBAL_HIDDEN_WIDTH))
    static[:, 1414] = torch.linspace(0.0, 1.0, 8)
    targets = torch.stack(
        [torch.linspace(index / 20.0, index / 20.0 + 0.3, 4) for index in range(8)]
    )
    return ContinuationRootExample(
        seed=1,
        prefix_global_inputs=prefix,
        prefix_commit_mask=torch.ones(8, dtype=torch.bool),
        bundle_static_inputs=static,
        targets=targets,
        achieved_horizons=torch.tensor([HORIZONS] * 8),
        sampled_bundles=tuple((index, 0, 0) for index in range(8)),
        planner_inadmissible=(False,) * 8,
        selected_state_sha256="a" * 64,
        branch_trace_sha256=("b" * 64,) * 8,
    )


def test_config_and_protocol_are_exact_public_only():
    assert sha256_path(CONFIG) == CONFIG_SHA256
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    config = load_continuation_config(CONFIG)
    protocol = validate_protocol(ROOT, config)
    assert protocol["training"]["unique_public_roots"] == 2048
    assert protocol["mechanism"]["disagreement_targeting"] is False
    assert protocol["mechanism"]["planner_top_action_injection"] is False
    assert (
        protocol["downstream_authority"][
            "may_access_confirmation_restricted_held_out_or_embargoed_data"
        ]
        is False
    )


def test_zero_residual_preserves_source_bundle_order_exactly():
    model = _model()
    example = _example()
    with torch.no_grad():
        hidden = model.continuation_hidden(
            example.prefix_global_inputs, example.prefix_commit_mask
        )
        outputs = model.cost_outputs(
            example.bundle_static_inputs, hidden
        )[0]
    expected = example.bundle_static_inputs[:, 1414:1415].expand(-1, 4)
    assert torch.equal(outputs, expected)
    assert int(torch.argmin(outputs.mean(dim=-1)).item()) == 0


def test_hash_sampler_is_deterministic_source_anchored_and_unique():
    legal = tuple(
        (left, right, 9) for left in range(4) for right in range(3)
    )
    first = sample_bundles(legal, (2, 1, 9), seed=123)
    second = sample_bundles(legal, (2, 1, 9), seed=123)
    assert first == second
    assert first[0] == (2, 1, 9)
    assert len(first) == 8
    assert len(set(first)) == 8
    assert set(first) <= set(legal)


def test_planner_observer_matches_canonical_wait_only_bundle():
    observations = [
        {
            "unit": {"dead": False},
            "skill": {"status": "IDLE", "type": "", "reason": ""},
            "team": {
                "tick": 0,
                "wave": 1,
                "enemy_count": 0,
                "time_to_next_wave": 100,
                "defend_lead_ticks": 20,
                "line_operational": False,
                "defense_turret_coverage": 0.0,
                "defense_ammo_coverage": 0.0,
                "broken_block_count": 0,
            },
            "task_candidates": [],
        }
        for _ in range(3)
    ]
    masks = [
        {
            "abandon": False,
            "continue_current_task": False,
            "candidate_task": [],
        }
        for _ in range(3)
    ]
    planner = CandidateNativePlannerV11()
    ranking = planner_bundle_ranking(planner, observations, masks, [])
    assert ranking.ordered_action_indices == ((9, 9, 9),)
    assert ranking.fractional_rank == {(9, 9, 9): 0.0}
    assert [
        item["task_action"]["type"] for item in ranking.canonical_actions
    ] == ["WAIT", "WAIT", "WAIT"]


def test_fresh_adamw_training_is_deterministic_and_source_stays_frozen():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["optimizer"]["optimizer_steps_per_group"] = 2
    config["optimizer"]["branch_rows_per_minibatch"] = 4

    def run():
        model = _model()
        source_before = {
            name: value.detach().clone()
            for name, value in model.state_dict().items()
            if not name.startswith(
                ("global_recurrent_cell.", "bundle_cost_head.")
            )
        }
        optimizer = torch.optim.AdamW(
            model.new_parameters(),
            lr=0.0003,
            betas=(0.9, 0.999),
            eps=1e-8,
            weight_decay=0.0001,
        )
        metrics = continuation_update(
            model,
            optimizer,
            [_example()],
            config,
            torch.Generator().manual_seed(9733),
        )
        assert all(
            torch.equal(model.state_dict()[name], value)
            for name, value in source_before.items()
        )
        return (
            model_state_digest(model),
            _state_digest(optimizer.state_dict()),
            metrics,
            model,
        )

    first = run()
    second = run()
    assert first[:3] == second[:3]
    assert first[2]["optimizer_steps"] == 2.0
    assert torch.count_nonzero(first[3].bundle_cost_head[-1].weight) > 0


def test_source_model_is_exact_frozen_and_source_optimizer_is_not_loaded():
    config = load_continuation_config(CONFIG)
    checkpoint = ROOT / config["source_checkpoint"]["path"]
    if not checkpoint.exists():
        pytest.skip("ignored immutable checkpoint is not local")
    model, optimizer, payload = source_model_and_optimizer(ROOT, config)
    inherited = {
        name: value
        for name, value in model.state_dict().items()
        if not name.startswith(
            ("global_recurrent_cell.", "bundle_cost_head.")
        )
    }
    base = SharedRecurrentSelector(2)
    base.load_state_dict(inherited)
    assert model_state_digest(base) == payload["model_state_sha256"]
    assert not optimizer.state
    assert all(
        not parameter.requires_grad
        for name, parameter in model.named_parameters()
        if not name.startswith(
            ("global_recurrent_cell.", "bundle_cost_head.")
        )
    )
    assert all(parameter.requires_grad for parameter in model.new_parameters())


def test_candidate_checkpoint_round_trip_is_exact(tmp_path):
    model = _model()
    optimizer = torch.optim.AdamW(model.new_parameters(), lr=0.0003)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["optimizer"]["optimizer_steps_per_group"] = 1
    config["optimizer"]["branch_rows_per_minibatch"] = 2
    continuation_update(
        model,
        optimizer,
        [_example()],
        config,
        torch.Generator().manual_seed(9733),
    )
    path = tmp_path / "candidate.pt"
    saved = save_checkpoint(
        path,
        model,
        optimizer,
        group=1,
        parent_checkpoint_content_sha256="a" * 64,
    )
    restored = _model()
    restored_optimizer = torch.optim.AdamW(
        restored.new_parameters(), lr=0.0003
    )
    loaded = load_checkpoint(path, restored, restored_optimizer)
    assert saved["checkpoint_content_sha256"] == loaded[
        "checkpoint_content_sha256"
    ]
    assert model_state_digest(restored) == model_state_digest(model)
    assert _state_digest(restored_optimizer.state_dict()) == _state_digest(
        optimizer.state_dict()
    )


def test_training_authority_requires_exact_head_public_preflight(
    tmp_path, monkeypatch
):
    path = tmp_path / "preflight.json"
    path.write_text(
        json.dumps(
            {
                "schema": (
                    "m9_candidate_native_continuation_regret_preflight_v1"
                ),
                "passed": True,
                "implementation_commit": "exact-head",
                "config_sha256": CONFIG_SHA256,
                "protocol_sha256": PROTOCOL_SHA256,
                "confirmation_or_held_out_access": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "mindustry_agents.training."
        "candidate_continuation_regret_train._git_commit",
        lambda root: "exact-head",
    )
    assert validate_preflight(path, ROOT)["passed"]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["implementation_commit"] = "stale"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="preflight is invalid"):
        validate_preflight(path, ROOT)
