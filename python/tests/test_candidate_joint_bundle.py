"""Governance tests for ADR-0135's joint-bundle candidate."""

import json
from pathlib import Path

import pytest
import torch

from mindustry_agents.training.candidate_joint_bundle import (
    ACTION_DESCRIPTOR_WIDTH,
    CONFIG_SHA256,
    PROTOCOL_SHA256,
    JointBundleBoundary,
    JointBundleEpisode,
    JointBundleSelector,
    _bundle_actions,
    _bundle_index,
    _packed_minibatches,
    joint_bundle_update,
    load_joint_bundle_config,
    source_model_and_optimizer,
    validate_protocol,
)
from mindustry_agents.training.candidate_joint_bundle_train import (
    load_checkpoint,
    save_checkpoint,
    validate_preflight,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_ppo import IPPOTransition, sha256_path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT / "configs/training/m9-candidate-native-joint-bundle-v1.json"
)
PROTOCOL = (
    ROOT
    / "configs/evaluation/"
    "m9-candidate-native-joint-bundle-v1-public-protocol.json"
)


def _transition(
    *,
    agent_id: int,
    action: int,
    hidden_value: float = 0.0,
) -> IPPOTransition:
    candidates = torch.zeros((8, 37), dtype=torch.float32)
    for index in range(8):
        candidates[index, index % 13] = (index + 1) / 10.0
        candidates[index, 13 + (index % 16)] = 1.0
    return IPPOTransition(
        agent_id=agent_id,
        candidates=candidates,
        scalars=torch.linspace(0.0, 1.0, 160),
        candidate_present=torch.ones(8, dtype=torch.bool),
        action_mask=torch.ones(10, dtype=torch.bool),
        hidden_input=torch.full((64,), hidden_value),
        action=action,
        old_log_prob=0.0,
        old_value=0.0,
        team_reward=0.0,
        individual_reward=0.0,
        advanced_ticks=60,
        done=False,
        policy_loss_mask=True,
        recurrent_reset=False,
    )


def _episode() -> JointBundleEpisode:
    boundaries = (
        JointBundleBoundary(
            transitions=(
                _transition(agent_id=0, action=1),
                _transition(agent_id=1, action=2, hidden_value=0.1),
                _transition(agent_id=2, action=3, hidden_value=0.2),
            ),
            student_actions=(0, 0, 0),
        ),
        JointBundleBoundary(
            transitions=(
                _transition(agent_id=0, action=4),
                _transition(agent_id=2, action=5, hidden_value=0.2),
            ),
            student_actions=(0, 0),
        ),
        JointBundleBoundary(
            transitions=(_transition(agent_id=1, action=6),),
            student_actions=(0,),
        ),
    )
    return JointBundleEpisode(
        seed=1,
        outcome="loss",
        tick=120,
        core_health=0.0,
        boundaries=boundaries,
        actor_labels=6,
        forced_controls=0,
        student_teacher_matches=0,
        rejected_student_actions=0,
        trace_sha256="0" * 64,
    )


def test_config_and_protocol_are_exact_public_only():
    assert sha256_path(CONFIG) == CONFIG_SHA256
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    config = load_joint_bundle_config(CONFIG)
    protocol = validate_protocol(ROOT, config)
    assert protocol["training"]["unique_public_roots"] == 2048
    assert protocol["training"]["only_changes"] == [
        "same_boundary_cross_seat_action_descriptors",
        "zero_output_initialized_pairwise_compatibility_head",
        "normalized_legal_joint_bundle_nll",
    ]
    assert not protocol["downstream_authority"]["may_access_confirmation"]
    assert not protocol["downstream_authority"]["may_access_held_out"]


def test_zero_pairwise_head_preserves_base_logits_and_bundle_argmax():
    base = SharedRecurrentSelector(9601)
    model = JointBundleSelector(1, pairwise_head_seed=9621)
    incompatible = model.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert set(incompatible.missing_keys) == {
        "pairwise_head.0.weight",
        "pairwise_head.0.bias",
        "pairwise_head.2.weight",
        "pairwise_head.2.bias",
    }
    transitions = [
        _transition(agent_id=index, action=index + 1)
        for index in range(3)
    ]
    base_logits = []
    joint_logits = []
    descriptors = []
    for transition in transitions:
        arguments = (
            transition.candidates.unsqueeze(0),
            transition.scalars.unsqueeze(0),
            transition.candidate_present.unsqueeze(0),
            transition.action_mask.unsqueeze(0),
            torch.tensor([transition.agent_id]),
            transition.hidden_input.unsqueeze(0),
        )
        with torch.no_grad():
            _, base_masked, base_value, base_hidden = base(*arguments)
            _, masked, value, hidden, descriptor = (
                model.forward_with_descriptors(*arguments)
            )
        assert torch.equal(masked, base_masked)
        assert torch.equal(value, base_value)
        assert torch.equal(hidden, base_hidden)
        assert descriptor.shape == (1, 10, ACTION_DESCRIPTOR_WIDTH)
        base_logits.append(base_masked[0])
        joint_logits.append(masked[0])
        descriptors.append(descriptor[0])
    stacked = torch.stack(joint_logits)[None, :]
    descriptor_batch = torch.stack(descriptors)[None, :]
    with torch.no_grad():
        scores = model.joint_scores(stacked, descriptor_batch)
    expected = (
        base_logits[0][:, None, None]
        + base_logits[1][None, :, None]
        + base_logits[2][None, None, :]
    ).reshape(1, 1000)
    assert torch.equal(scores, expected)
    independent = tuple(
        int(torch.argmax(logits).item()) for logits in base_logits
    )
    assert _bundle_actions(int(torch.argmax(scores).item()), 3) == independent


def test_bundle_index_round_trip_and_tie_order():
    for actions in ((0,), (9,), (1, 2), (9, 0), (1, 2, 3), (9, 9, 9)):
        assert _bundle_actions(_bundle_index(actions), len(actions)) == actions


def test_whole_boundary_packing_respects_actor_label_budget():
    boundaries = list(_episode().boundaries) * 100
    order = torch.arange(len(boundaries))
    packed = _packed_minibatches(boundaries, order, 256)
    assert [item for group in packed for item in group] == boundaries
    assert all(
        sum(item.actor_labels for item in group) <= 256
        for group in packed
    )


def test_joint_update_is_deterministic_and_trains_pairwise_head():
    def run():
        model = JointBundleSelector(9601, pairwise_head_seed=9621)
        optimizer = torch.optim.Adam(
            model.parameters(), lr=0.0001, eps=1e-8
        )
        metrics = joint_bundle_update(
            model,
            optimizer,
            [_episode()],
            {
                "epochs_per_update": 2,
                "actor_label_budget_per_minibatch": 256,
                "max_grad_norm": 0.5,
            },
            torch.Generator().manual_seed(9613),
        )
        return model_state_digest(model), metrics, model

    first_digest, first_metrics, first_model = run()
    second_digest, second_metrics, _ = run()
    assert first_digest == second_digest
    assert first_metrics == second_metrics
    assert first_metrics["labels"] == 6.0
    assert first_metrics["presentations"] == 12.0
    assert first_metrics["bundle_presentations"] == 6.0
    assert torch.count_nonzero(first_model.pairwise_head[-1].weight) > 0


def test_source_model_optimizer_inheritance_is_exact_and_new_group_empty():
    config = load_joint_bundle_config(CONFIG)
    checkpoint = ROOT / config["source_checkpoint"]["path"]
    if not checkpoint.exists():
        pytest.skip("ignored immutable checkpoint is not local")
    model, optimizer, payload = source_model_and_optimizer(ROOT, config)
    assert len(optimizer.param_groups) == 2
    assert len(optimizer.state) == len(payload["optimizer_state"]["state"])
    assert all(
        parameter not in optimizer.state
        for parameter in optimizer.param_groups[1]["params"]
    )
    inherited = {
        name: value
        for name, value in model.state_dict().items()
        if not name.startswith("pairwise_head.")
    }
    base = SharedRecurrentSelector(2)
    base.load_state_dict(inherited)
    assert model_state_digest(base) == payload["model_state_sha256"]


def test_candidate_checkpoint_round_trip_is_exact(tmp_path):
    model = JointBundleSelector(9601, pairwise_head_seed=9621)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=0.0001, eps=1e-8
    )
    path = tmp_path / "candidate.pt"
    saved = save_checkpoint(
        path,
        model,
        optimizer,
        update=65,
        parent_checkpoint_content_sha256="a" * 64,
    )
    restored = JointBundleSelector(1, pairwise_head_seed=2)
    restored_optimizer = torch.optim.Adam(
        restored.parameters(), lr=0.0001, eps=1e-8
    )
    loaded = load_checkpoint(path, restored, restored_optimizer)
    assert saved["checkpoint_content_sha256"] == loaded[
        "checkpoint_content_sha256"
    ]
    assert model_state_digest(restored) == model_state_digest(model)


def test_training_authority_requires_exact_head_live_preflight(
    tmp_path, monkeypatch
):
    path = tmp_path / "preflight.json"
    path.write_text(
        json.dumps(
            {
                "schema": "m9_candidate_native_joint_bundle_preflight_v1",
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
        "mindustry_agents.training.candidate_joint_bundle_train._git_commit",
        lambda root: "exact-head",
    )
    assert validate_preflight(path, ROOT)["passed"]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["implementation_commit"] = "stale-head"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="preflight is invalid"):
        validate_preflight(path, ROOT)
