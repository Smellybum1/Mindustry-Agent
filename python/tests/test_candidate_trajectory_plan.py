"""Governance tests for ADR-0133's trajectory-plan candidate."""

import json
from pathlib import Path

import pytest
import torch

from mindustry_agents.training.candidate_trajectory_plan import (
    CONFIG_SHA256,
    FAMILY_COUNT,
    PLAN_SLOTS,
    PROTOCOL_SHA256,
    TASK_TYPE_TO_INDEX,
    TrajectoryPlanEpisode,
    TrajectoryPlanSelector,
    build_plan_targets,
    load_trajectory_plan_config,
    source_model_and_optimizer,
    trajectory_plan_update,
    validate_protocol,
)
from mindustry_agents.training.candidate_trajectory_plan_train import (
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
    ROOT
    / "configs/training/m9-candidate-native-trajectory-plan-v1.json"
)
PROTOCOL = (
    ROOT
    / "configs/evaluation/"
    "m9-candidate-native-trajectory-plan-v1-public-protocol.json"
)


def _transition(
    *,
    agent_id: int = 0,
    action: int = 0,
    family: int = 0,
    supervised: bool = True,
    recurrent_reset: bool = False,
    done: bool = False,
) -> IPPOTransition:
    candidates = torch.zeros((8, 37), dtype=torch.float32)
    for index in range(8):
        candidates[index, 13 + ((family + index) % FAMILY_COUNT)] = 1.0
    return IPPOTransition(
        agent_id=agent_id,
        candidates=candidates,
        scalars=torch.zeros(160),
        candidate_present=torch.ones(8, dtype=torch.bool),
        action_mask=torch.ones(10, dtype=torch.bool),
        hidden_input=torch.zeros(64),
        action=action,
        old_log_prob=0.0,
        old_value=0.0,
        team_reward=0.0,
        individual_reward=0.0,
        advanced_ticks=60,
        done=done,
        policy_loss_mask=supervised,
        recurrent_reset=recurrent_reset,
    )


def test_config_and_protocol_are_exact_public_only():
    assert sha256_path(CONFIG) == CONFIG_SHA256
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    config = load_trajectory_plan_config(CONFIG)
    protocol = validate_protocol(ROOT, config)
    assert config["trajectory_plan"]["task_family_order"]
    assert protocol["training"]["unique_public_roots"] == 2048
    assert not protocol["downstream_authority"]["may_access_confirmation"]
    assert not protocol["downstream_authority"]["may_access_held_out"]


def test_zero_output_plan_head_preserves_every_base_logit():
    base = SharedRecurrentSelector(9601)
    model = TrajectoryPlanSelector(1, plan_head_seed=9617)
    incompatible = model.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert set(incompatible.missing_keys) == {
        "plan_head.0.weight",
        "plan_head.0.bias",
        "plan_head.2.weight",
        "plan_head.2.bias",
    }
    transition = _transition()
    arguments = (
        transition.candidates.unsqueeze(0),
        transition.scalars.unsqueeze(0),
        transition.candidate_present.unsqueeze(0),
        transition.action_mask.unsqueeze(0),
        torch.tensor([0]),
        transition.hidden_input.unsqueeze(0),
    )
    with torch.no_grad():
        base_raw, base_masked, base_value, base_hidden = base(*arguments)
        raw, masked, value, hidden, plans = model.forward_with_plan(
            *arguments
        )
    assert torch.equal(raw, base_raw)
    assert torch.equal(masked, base_masked)
    assert torch.equal(value, base_value)
    assert torch.equal(hidden, base_hidden)
    assert torch.count_nonzero(plans) == 0


def test_source_model_optimizer_inheritance_is_exact_and_new_group_empty():
    config = load_trajectory_plan_config(CONFIG)
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
        if not name.startswith("plan_head.")
    }
    base = SharedRecurrentSelector(2)
    base.load_state_dict(inherited)
    assert model_state_digest(base) == payload["model_state_sha256"]


def test_program_targets_use_future_distinct_families_and_stop_at_reset():
    transitions = [
        _transition(family=0, recurrent_reset=True),
        _transition(family=0),
        _transition(family=1),
        _transition(family=2),
        _transition(family=3, recurrent_reset=True),
        _transition(family=4, done=True),
    ]
    immediate = [0, 0, 1, 2, 3, 4]
    targets = build_plan_targets(transitions, immediate)
    assert targets[0] == (0, 1, 2, 2)
    assert targets[1] == (0, 1, 2, 2)
    assert targets[2] == (1, 2, 2, 2)
    assert targets[3] == (2, 2, 2, 2)
    assert targets[4] == (3, 4, 4, 4)
    assert targets[5] == (4, 4, 4, 4)


def test_plan_slot_zero_biases_only_matching_candidate_family():
    model = TrajectoryPlanSelector(9601, plan_head_seed=9617)
    transition = _transition(family=2)
    arguments = (
        transition.candidates.unsqueeze(0),
        transition.scalars.unsqueeze(0),
        transition.candidate_present.unsqueeze(0),
        transition.action_mask.unsqueeze(0),
        torch.tensor([0]),
        transition.hidden_input.unsqueeze(0),
    )
    with torch.no_grad():
        baseline = model(*arguments)[0]
        final = model.plan_head[-1]
        final.bias[2] = 3.0
        changed = model(*arguments)[0]
    assert changed[0, 0] == baseline[0, 0] + 3.0
    assert torch.equal(changed[0, 1:8], baseline[0, 1:8])
    assert torch.equal(changed[0, 8:], baseline[0, 8:])


def test_plan_update_is_deterministic_and_trains_plan_head():
    transitions = (
        _transition(family=0, recurrent_reset=True),
        _transition(family=1, done=True),
    )
    targets = ((0, 1, 1, 1), (1, 1, 1, 1))
    episode = TrajectoryPlanEpisode(
        seed=1,
        outcome="loss",
        tick=120,
        core_health=0.0,
        transitions=transitions,
        plan_targets=targets,
        eligible_labels=2,
        context_transitions=0,
        forced_controls=0,
        student_teacher_matches=0,
        rejected_student_actions=0,
        trace_sha256="0" * 64,
    )

    def run():
        model = TrajectoryPlanSelector(9601, plan_head_seed=9617)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
        metrics = trajectory_plan_update(
            model,
            optimizer,
            [episode],
            {"epochs_per_update": 1, "max_grad_norm": 0.5},
            torch.Generator().manual_seed(9613),
        )
        return model_state_digest(model), metrics, model

    first_digest, first_metrics, first_model = run()
    second_digest, second_metrics, _ = run()
    assert first_digest == second_digest
    assert first_metrics == second_metrics
    assert first_metrics["presentations"] == 2
    assert torch.count_nonzero(first_model.plan_head[-1].weight) > 0
    assert TASK_TYPE_TO_INDEX["WAIT"] == 11
    assert PLAN_SLOTS == 4


def test_candidate_checkpoint_round_trip_is_exact(tmp_path):
    model = TrajectoryPlanSelector(9601, plan_head_seed=9617)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
    path = tmp_path / "candidate.pt"
    saved = save_checkpoint(
        path,
        model,
        optimizer,
        update=65,
        parent_checkpoint_content_sha256="a" * 64,
    )
    restored = TrajectoryPlanSelector(1, plan_head_seed=2)
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
                "schema": (
                    "m9_candidate_native_trajectory_plan_preflight_v1"
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
        "candidate_trajectory_plan_train._git_commit",
        lambda root: "exact-head",
    )
    assert validate_preflight(path, ROOT)["passed"]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["implementation_commit"] = "stale-head"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="preflight is invalid"):
        validate_preflight(path, ROOT)
