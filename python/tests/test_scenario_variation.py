"""Fast governance checks for the M7.5 scenario-variation harness."""

from __future__ import annotations

import hashlib
import json

import pytest

from mindustry_agents.tools.scenario_variation_check import (
    DEFAULT_SEED_SET,
    _load_seed_set,
    _validate_governance,
)


def test_held_out_set_cannot_be_selected():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-held-out-v1.json")
    with pytest.raises(ValueError, match="sealed"):
        _load_seed_set(path)


def test_checked_in_governance_has_disjoint_named_splits():
    selected = _load_seed_set(DEFAULT_SEED_SET)
    _validate_governance(DEFAULT_SEED_SET, selected)


def test_post_failure_held_out_v2_is_sealed_exact_and_globally_disjoint():
    v2_path = DEFAULT_SEED_SET.with_name(
        "bootstrap-defense-v1-held-out-v2.json"
    )

    with pytest.raises(ValueError, match="sealed"):
        _load_seed_set(v2_path)

    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    assert v2["seed_set_id"] == "bootstrap-defense-v1-held-out-v2"
    assert v2["seed_set_version"] == 2
    assert v2["split"] == "held-out"
    assert v2["seeds"] == list(range(910001, 910041))

    other_names = (
        "bootstrap-defense-v0-fixed-v1.json",
        "bootstrap-defense-v1-train-v1.json",
        "bootstrap-defense-v1-dev-v1.json",
        "bootstrap-defense-v1-held-out-v1.json",
    )
    v2_seeds = set(v2["seeds"])
    for name in other_names:
        path = DEFAULT_SEED_SET.with_name(name)
        other = json.loads(path.read_text(encoding="utf-8"))
        assert v2_seeds.isdisjoint(other["seeds"]), name


def test_m8_successor_recipe_precommits_diverse_train_roots_and_v2_final():
    config_path = DEFAULT_SEED_SET.parents[1] / "training/m8-selector-v3-diverse.json"
    train_path = DEFAULT_SEED_SET.with_name(
        "bootstrap-defense-v1-train-v2.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    train = json.loads(train_path.read_text(encoding="utf-8"))

    assert config["train_seed_set"].endswith(
        "bootstrap-defense-v1-train-v2.json"
    )
    assert config["held_out_seed_set_id"] == (
        "bootstrap-defense-v1-held-out-v2"
    )
    assert config["held_out_seed_set_version"] == 2
    assert config["training_cycles"] * len(train["seeds"]) == 512
    assert config["episodes_per_update"] == 64
    assert config["success_imitation_coefficient"] == 0.0
    assert train["split"] == "train"
    assert train["seeds"] == list(range(11001, 11065))

    governed_names = (
        "bootstrap-defense-v0-fixed-v1.json",
        "bootstrap-defense-v1-train-v1.json",
        "bootstrap-defense-v1-dev-v1.json",
        "bootstrap-defense-v1-held-out-v1.json",
        "bootstrap-defense-v1-held-out-v2.json",
    )
    train_seeds = set(train["seeds"])
    for name in governed_names:
        path = DEFAULT_SEED_SET.with_name(name)
        other = json.loads(path.read_text(encoding="utf-8"))
        assert train_seeds.isdisjoint(other["seeds"]), name


def test_m8_teacher_regularized_recipe_is_frozen_on_v2_contract():
    config_path = (
        DEFAULT_SEED_SET.parents[1]
        / "training/m8-selector-v4-teacher-regularized.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["train_seed_set"].endswith(
        "bootstrap-defense-v1-train-v2.json"
    )
    assert config["held_out_seed_set_id"] == (
        "bootstrap-defense-v1-held-out-v2"
    )
    assert config["held_out_seed_set_version"] == 2
    assert config["training_cycles"] == 8
    assert config["episodes_per_update"] == 64
    assert config["success_imitation_coefficient"] == 0.0
    assert config["successful_teacher_imitation_coefficient"] == 0.05


def test_m8_final_teacher_strength_changes_only_precommitted_coefficient():
    config_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v4 = json.loads(
        (config_dir / "m8-selector-v4-teacher-regularized.json").read_text(
            encoding="utf-8"
        )
    )
    v5 = json.loads(
        (config_dir / "m8-selector-v5-teacher-regularized.json").read_text(
            encoding="utf-8"
        )
    )

    assert v5["held_out_seed_set_id"] == "bootstrap-defense-v1-held-out-v2"
    assert v5["held_out_seed_set_version"] == 2
    assert v5["successful_teacher_imitation_coefficient"] == 0.1
    assert v5["optimizer_ppo"]["successful_teacher_imitation_coefficient"] == 0.1
    v4["successful_teacher_imitation_coefficient"] = 0.1
    v4["optimizer_ppo"]["successful_teacher_imitation_coefficient"] = 0.1
    assert v4 == v5


def test_m8_long_diverse_recipe_changes_only_precommitted_cycle_budget():
    config_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v3 = json.loads(
        (config_dir / "m8-selector-v3-diverse.json").read_text(encoding="utf-8")
    )
    v6 = json.loads(
        (config_dir / "m8-selector-v6-diverse-long.json").read_text(
            encoding="utf-8"
        )
    )

    assert v6["training_cycles"] == 32
    assert v6["episodes_per_update"] == 64
    assert v6["held_out_seed_set_id"] == "bootstrap-defense-v1-held-out-v2"
    assert v6["held_out_seed_set_version"] == 2
    v3["training_cycles"] = 32
    assert v3 == v6


def test_v6_confirmation_dev_v2_is_exact_and_globally_disjoint():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v2.json")
    confirmation = json.loads(path.read_text(encoding="utf-8"))

    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v2"
    assert confirmation["seed_set_version"] == 2
    assert confirmation["split"] == "dev"
    assert confirmation["seeds"] == list(range(21001, 21041))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other == path:
            continue
        document = json.loads(other.read_text(encoding="utf-8"))
        assert confirmation_seeds.isdisjoint(document["seeds"]), other.name


def test_v7_confirmation_dev_v3_is_exact_and_globally_disjoint():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v3.json")
    confirmation = json.loads(path.read_text(encoding="utf-8"))

    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v3"
    assert confirmation["seed_set_version"] == 3
    assert confirmation["split"] == "dev"
    assert confirmation["seeds"] == list(range(31001, 31041))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other == path:
            continue
        document = json.loads(other.read_text(encoding="utf-8"))
        assert confirmation_seeds.isdisjoint(document["seeds"]), other.name


def test_v8_confirmation_dev_v4_is_exact_and_globally_disjoint():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v4.json")
    confirmation = json.loads(path.read_text(encoding="utf-8"))

    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v4"
    assert confirmation["seed_set_version"] == 4
    assert confirmation["split"] == "dev"
    assert confirmation["seeds"] == list(range(41001, 41041))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other == path:
            continue
        document = json.loads(other.read_text(encoding="utf-8"))
        assert confirmation_seeds.isdisjoint(document["seeds"]), other.name


def test_post_v8_held_out_v3_is_sealed_exact_and_globally_disjoint():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-held-out-v3.json")
    with pytest.raises(ValueError, match="sealed"):
        _load_seed_set(path)

    held_out = json.loads(path.read_text(encoding="utf-8"))
    assert held_out["seed_set_id"] == "bootstrap-defense-v1-held-out-v3"
    assert held_out["seed_set_version"] == 3
    assert held_out["split"] == "held-out"
    assert held_out["seeds"] == list(range(920001, 920081))
    held_out_seeds = set(held_out["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other == path:
            continue
        document = json.loads(other.read_text(encoding="utf-8"))
        assert held_out_seeds.isdisjoint(document["seeds"]), other.name


def test_v9_confirmation_dev_v5_is_exact_and_globally_disjoint():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v5.json")
    confirmation = json.loads(path.read_text(encoding="utf-8"))

    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v5"
    assert confirmation["seed_set_version"] == 5
    assert confirmation["split"] == "dev"
    assert confirmation["seeds"] == list(range(51001, 51081))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other == path:
            continue
        document = json.loads(other.read_text(encoding="utf-8"))
        assert confirmation_seeds.isdisjoint(document["seeds"]), other.name


def test_post_v9_held_out_v4_is_sealed_exact_and_globally_disjoint():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-held-out-v4.json")
    with pytest.raises(ValueError, match="sealed"):
        _load_seed_set(path)

    held_out = json.loads(path.read_text(encoding="utf-8"))
    assert held_out["seed_set_id"] == "bootstrap-defense-v1-held-out-v4"
    assert held_out["seed_set_version"] == 4
    assert held_out["split"] == "held-out"
    assert held_out["seeds"] == list(range(930001, 930161))
    held_out_seeds = set(held_out["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other == path:
            continue
        document = json.loads(other.read_text(encoding="utf-8"))
        assert held_out_seeds.isdisjoint(document["seeds"]), other.name


def test_v10_confirmation_dev_v6_is_exact_and_globally_disjoint():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v6.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v6"
    assert confirmation["seed_set_version"] == 6
    assert confirmation["split"] == "dev"
    assert confirmation["seeds"] == list(range(61001, 61161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other == path:
            continue
        document = json.loads(other.read_text(encoding="utf-8"))
        assert confirmation_seeds.isdisjoint(document["seeds"]), other.name


def test_v10_config_precommits_full_teacher_and_held_out_v4():
    config = json.loads(
        (
            DEFAULT_SEED_SET.parents[1]
            / "training"
            / "m8-selector-v10-full-teacher.json"
        ).read_text(encoding="utf-8")
    )
    assert config["held_out_seed_set_id"] == "bootstrap-defense-v1-held-out-v4"
    assert config["held_out_seed_set_version"] == 4
    assert config["teacher_imitation_coefficient"] == 1.0
    assert config["successful_teacher_imitation_coefficient"] == 0.0
    assert config["optimizer_ppo"]["teacher_imitation_coefficient"] == 1.0


def test_v11_confirmation_and_blend_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v7.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v7"
    assert confirmation["seed_set_version"] == 7
    assert confirmation["seeds"] == list(range(71001, 71161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    config = json.loads(
        (
            DEFAULT_SEED_SET.parents[1]
            / "training"
            / "m8-selector-v11-interpolation.json"
        ).read_text(encoding="utf-8")
    )
    assert config["held_out_seed_set_id"] == "bootstrap-defense-v1-held-out-v4"
    parents = config["checkpoint_construction"]["parents"]
    assert [(item["role"], item["update"], item["weight"]) for item in parents] == [
        ("base", 31, 0.9),
        ("auxiliary", 6, 0.1),
    ]


def test_v12_quality_reward_and_dev_v8_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v8.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v8"
    assert confirmation["seed_set_version"] == 8
    assert confirmation["seeds"] == list(range(81001, 81161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    config = json.loads(
        (
            DEFAULT_SEED_SET.parents[1]
            / "training"
            / "m8-selector-v12-quality-reward.json"
        ).read_text(encoding="utf-8")
    )
    assert config["reward_schema"] == "selector_reward_v2"
    assert config["held_out_seed_set_id"] == "bootstrap-defense-v1-held-out-v4"
    assert config["quality_reward"] == {
        "idle_agent_tick_cost": 0.0001,
        "duplicate_work_cost": 0.05,
        "duplicate_work_cap": 1.0,
        "announcement_cost": 0.005,
        "announcement_cap": 1.0,
        "team_abandonment_cost": 0.1,
        "team_abandonment_cap": 2.0,
    }


def test_v13_quality_selection_and_dev_v9_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v9.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v9"
    assert confirmation["seed_set_version"] == 9
    assert confirmation["seeds"] == list(range(91001, 91161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    config = json.loads(
        (
            DEFAULT_SEED_SET.parents[1]
            / "training"
            / "m8-selector-v13-quality-gated-selection.json"
        ).read_text(encoding="utf-8")
    )
    assert config["reward_schema"] == "selector_reward_v2"
    assert config["held_out_seed_set_id"] == "bootstrap-defense-v1-held-out-v4"
    assert config["dev_checkpoint_selection"] == {
        "schema": "quality_gate_v1",
        "minimum_wins": 9,
        "maximum_mean_idle_fraction_exclusive": 0.25,
        "ranking": [
            "wins_desc",
            "mean_return_desc",
            "mean_core_health_desc",
            "update_asc",
        ],
    }
    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v9"] == path.name


def test_v14_corrected_boundary_retrain_and_dev_v10_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v10.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v10"
    assert confirmation["seed_set_version"] == 10
    assert confirmation["seeds"] == list(range(101001, 101161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v13 = json.loads(
        (training_dir / "m8-selector-v13-quality-gated-selection.json").read_text(
            encoding="utf-8"
        )
    )
    v14 = json.loads(
        (training_dir / "m8-selector-v14-corrected-abandon-boundary.json").read_text(
            encoding="utf-8"
        )
    )
    assert v14.pop("candidate_version") == "v14"
    assert v14.pop("runtime_contract") == (
        "successful_abandon_task_terminal_one_tick_v1"
    )
    assert v14.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v10.json"
    )
    assert v14 == v13

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v10"] == path.name


def test_v15_quality_pressure_and_dev_v11_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v11.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v11"
    assert confirmation["seed_set_version"] == 11
    assert confirmation["seeds"] == list(range(111001, 111161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v14 = json.loads(
        (training_dir / "m8-selector-v14-corrected-abandon-boundary.json").read_text(
            encoding="utf-8"
        )
    )
    v15 = json.loads(
        (training_dir / "m8-selector-v15-quality-pressure.json").read_text(
            encoding="utf-8"
        )
    )
    assert v15.pop("candidate_version") == "v15"
    assert v15.pop("quality_intervention") == (
        "idle_x3_and_nonforced_abandon_x2_5_v1"
    )
    assert v15.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v11.json"
    )
    assert v14.pop("candidate_version") == "v14"
    assert v14.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v10.json"
    )
    assert v15["quality_reward"].pop("idle_agent_tick_cost") == 0.0003
    assert v14["quality_reward"].pop("idle_agent_tick_cost") == 0.0001
    assert v15["quality_reward"].pop("team_abandonment_cost") == 0.25
    assert v14["quality_reward"].pop("team_abandonment_cost") == 0.1
    assert v15 == v14

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v11"] == path.name


def test_v16_capped_idle_pressure_and_dev_v12_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v12.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v12"
    assert confirmation["seed_set_version"] == 12
    assert confirmation["seeds"] == list(range(121001, 121161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v15 = json.loads(
        (training_dir / "m8-selector-v15-quality-pressure.json").read_text(
            encoding="utf-8"
        )
    )
    v16 = json.loads(
        (training_dir / "m8-selector-v16-capped-idle-pressure.json").read_text(
            encoding="utf-8"
        )
    )
    assert v16.pop("candidate_version") == "v16"
    assert v16.pop("quality_intervention") == "high_slope_capped_idle_v1"
    assert v16.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v12.json"
    )
    assert v15.pop("candidate_version") == "v15"
    assert v15.pop("quality_intervention") == (
        "idle_x3_and_nonforced_abandon_x2_5_v1"
    )
    assert v15.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v11.json"
    )
    assert v16["quality_reward"].pop("idle_agent_tick_cost") == 0.001
    assert v16["quality_reward"].pop("idle_agent_tick_cap") == 5.0
    assert v15["quality_reward"].pop("idle_agent_tick_cost") == 0.0003
    assert v16 == v15

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v12"] == path.name


def test_v17_doubled_capped_idle_slope_and_dev_v13_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v13.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v13"
    assert confirmation["seed_set_version"] == 13
    assert confirmation["seeds"] == list(range(131001, 131161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v16 = json.loads(
        (training_dir / "m8-selector-v16-capped-idle-pressure.json").read_text(
            encoding="utf-8"
        )
    )
    v17 = json.loads(
        (
            training_dir / "m8-selector-v17-doubled-capped-idle-pressure.json"
        ).read_text(encoding="utf-8")
    )
    assert v17.pop("candidate_version") == "v17"
    assert v17.pop("quality_intervention") == (
        "doubled_capped_idle_with_busywork_guard_v1"
    )
    assert v17.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v13.json"
    )
    assert v16.pop("candidate_version") == "v16"
    assert v16.pop("quality_intervention") == "high_slope_capped_idle_v1"
    assert v16.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v12.json"
    )
    assert v17["quality_reward"].pop("idle_agent_tick_cost") == 0.002
    assert v16["quality_reward"].pop("idle_agent_tick_cost") == 0.001
    assert v17["quality_reward"].pop("duplicate_work_cap") == 2.0
    assert v16["quality_reward"].pop("duplicate_work_cap") == 1.0
    assert v17 == v16

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v13"] == path.name


def test_v18_scorecard_quality_and_dev_v14_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v14.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v14"
    assert confirmation["seed_set_version"] == 14
    assert confirmation["seeds"] == list(range(141001, 141161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v17 = json.loads(
        (
            training_dir / "m8-selector-v17-doubled-capped-idle-pressure.json"
        ).read_text(encoding="utf-8")
    )
    v18 = json.loads(
        (training_dir / "m8-selector-v18-scorecard-aligned-quality.json").read_text(
            encoding="utf-8"
        )
    )
    assert v18.pop("candidate_version") == "v18"
    assert v18.pop("quality_intervention") == "scorecard_aligned_quality_v1"
    assert v18.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v14.json"
    )
    assert v17.pop("candidate_version") == "v17"
    assert v17.pop("quality_intervention") == (
        "doubled_capped_idle_with_busywork_guard_v1"
    )
    assert v17.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v13.json"
    )
    assert v18["quality_reward"].pop("idle_agent_tick_cost") == 0.004
    assert v17["quality_reward"].pop("idle_agent_tick_cost") == 0.002
    assert v18["quality_reward"].pop("duplicate_work_cap") == 4.0
    assert v17["quality_reward"].pop("duplicate_work_cap") == 2.0
    assert v18["quality_reward"].pop("announcement_cost") == 0.01
    assert v17["quality_reward"].pop("announcement_cost") == 0.005
    assert v18["quality_reward"].pop("recovery_delay_tick_cost") == 0.001
    assert v18["quality_reward"].pop("recovery_delay_tick_cap") == 3.0
    assert v18 == v17

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v14"] == path.name


def test_v19_unsaturated_idle_gradient_and_dev_v15_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v15.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v15"
    assert confirmation["seed_set_version"] == 15
    assert confirmation["seeds"] == list(range(151001, 151161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v18 = json.loads(
        (training_dir / "m8-selector-v18-scorecard-aligned-quality.json").read_text(
            encoding="utf-8"
        )
    )
    v19 = json.loads(
        (training_dir / "m8-selector-v19-unsaturated-idle-gradient.json").read_text(
            encoding="utf-8"
        )
    )
    assert v19.pop("candidate_version") == "v19"
    assert v19.pop("quality_intervention") == "unsaturated_idle_gradient_v1"
    assert v19.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v15.json"
    )
    assert v18.pop("candidate_version") == "v18"
    assert v18.pop("quality_intervention") == "scorecard_aligned_quality_v1"
    assert v18.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v14.json"
    )
    assert v19["quality_reward"].pop("idle_agent_tick_cost") == 0.002
    assert v18["quality_reward"].pop("idle_agent_tick_cost") == 0.004
    assert v19["quality_reward"].pop("idle_agent_tick_cap") == 8.0
    assert v18["quality_reward"].pop("idle_agent_tick_cap") == 5.0
    assert v19["quality_reward"].pop("duplicate_work_cap") == 7.0
    assert v18["quality_reward"].pop("duplicate_work_cap") == 4.0
    assert v19 == v18

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v15"] == path.name


def test_v20_low_teacher_regularization_and_dev_v16_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v16.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v16"
    assert confirmation["seed_set_version"] == 16
    assert confirmation["seeds"] == list(range(161001, 161161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v19 = json.loads(
        (training_dir / "m8-selector-v19-unsaturated-idle-gradient.json").read_text(
            encoding="utf-8"
        )
    )
    v20 = json.loads(
        (training_dir / "m8-selector-v20-low-teacher-regularized.json").read_text(
            encoding="utf-8"
        )
    )
    assert v20.pop("candidate_version") == "v20"
    assert v20.pop("quality_intervention") == (
        "unsaturated_idle_plus_low_full_teacher_v1"
    )
    assert v20.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v16.json"
    )
    assert v19.pop("candidate_version") == "v19"
    assert v19.pop("quality_intervention") == "unsaturated_idle_gradient_v1"
    assert v19.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v15.json"
    )
    assert v20.pop("teacher_imitation_coefficient") == 0.05
    assert v19.pop("teacher_imitation_coefficient") == 0.0
    assert v20["optimizer_ppo"].pop("teacher_imitation_coefficient") == 0.05
    assert v19["optimizer_ppo"].pop("teacher_imitation_coefficient") == 0.0
    assert v20 == v19

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v16"] == path.name


def test_v21_corrected_wait_boundary_and_dev_v17_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v17.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v17"
    assert confirmation["seed_set_version"] == 17
    assert confirmation["seeds"] == list(range(171001, 171161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v20 = json.loads(
        (training_dir / "m8-selector-v20-low-teacher-regularized.json").read_text(
            encoding="utf-8"
        )
    )
    v21 = json.loads(
        (training_dir / "m8-selector-v21-corrected-wait-boundary.json").read_text(
            encoding="utf-8"
        )
    )
    assert v21.pop("candidate_version") == "v21"
    assert v21.pop("runtime_contract") == (
        "successful_abandon_one_tick_wait_release_same_tick_v2"
    )
    assert v21.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v17.json"
    )
    assert v20.pop("candidate_version") == "v20"
    assert v20.pop("runtime_contract") == (
        "successful_abandon_task_terminal_one_tick_v1"
    )
    assert v20.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v16.json"
    )
    assert v21 == v20

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v17"] == path.name


def test_v22_retry_eligibility_and_dev_v18_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v18.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v18"
    assert confirmation["seed_set_version"] == 18
    assert confirmation["seeds"] == list(range(181001, 181161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v21 = json.loads(
        (training_dir / "m8-selector-v21-corrected-wait-boundary.json").read_text(
            encoding="utf-8"
        )
    )
    v22 = json.loads(
        (training_dir / "m8-selector-v22-retry-eligibility.json").read_text(
            encoding="utf-8"
        )
    )
    assert v22.pop("candidate_version") == "v22"
    assert v22.pop("runtime_contract") == (
        "abandon_wait_retry_and_agent_death_boundaries_v3"
    )
    assert v22.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v18.json"
    )
    assert v21.pop("candidate_version") == "v21"
    assert v21.pop("runtime_contract") == (
        "successful_abandon_one_tick_wait_release_same_tick_v2"
    )
    assert v21.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v17.json"
    )
    assert v22 == v21

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v18"] == path.name


def test_v23_available_idle_and_dev_v19_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v19.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v19"
    assert confirmation["seed_set_version"] == 19
    assert confirmation["seeds"] == list(range(191001, 191161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v22 = json.loads(
        (training_dir / "m8-selector-v22-retry-eligibility.json").read_text(
            encoding="utf-8"
        )
    )
    v23 = json.loads(
        (training_dir / "m8-selector-v23-available-idle.json").read_text(
            encoding="utf-8"
        )
    )
    assert v23.pop("candidate_version") == "v23"
    assert v23.pop("runtime_contract") == (
        "abandon_wait_retry_agent_death_available_idle_v4"
    )
    assert v23.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v19.json"
    )
    assert v22.pop("candidate_version") == "v22"
    assert v22.pop("runtime_contract") == (
        "abandon_wait_retry_and_agent_death_boundaries_v3"
    )
    assert v22.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v18.json"
    )
    assert v23 == v22

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v19"] == path.name


def test_v24_resource_scoped_retry_and_dev_v20_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v20.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v20"
    assert confirmation["seed_set_version"] == 20
    assert confirmation["seeds"] == list(range(201001, 201161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v23 = json.loads(
        (training_dir / "m8-selector-v23-available-idle.json").read_text(
            encoding="utf-8"
        )
    )
    v24 = json.loads(
        (training_dir / "m8-selector-v24-resource-scoped-retry.json").read_text(
            encoding="utf-8"
        )
    )
    assert v24.pop("candidate_version") == "v24"
    assert v24.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_v5"
    )
    assert v24.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v20.json"
    )
    assert v23.pop("candidate_version") == "v23"
    assert v23.pop("runtime_contract") == (
        "abandon_wait_retry_agent_death_available_idle_v4"
    )
    assert v23.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v19.json"
    )
    assert v24 == v23

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v20"] == path.name


def test_v25_moderate_full_teacher_and_dev_v21_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v21.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v21"
    assert confirmation["seed_set_version"] == 21
    assert confirmation["seeds"] == list(range(211001, 211161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v24 = json.loads(
        (training_dir / "m8-selector-v24-resource-scoped-retry.json").read_text(
            encoding="utf-8"
        )
    )
    v25 = json.loads(
        (training_dir / "m8-selector-v25-moderate-full-teacher.json").read_text(
            encoding="utf-8"
        )
    )
    assert v25.pop("candidate_version") == "v25"
    assert v25.pop("quality_intervention") == (
        "unsaturated_idle_plus_moderate_full_teacher_v2"
    )
    assert v25.pop("teacher_imitation_coefficient") == 0.1
    assert v25["optimizer_ppo"].pop("teacher_imitation_coefficient") == 0.1
    assert v25.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v21.json"
    )
    assert v24.pop("candidate_version") == "v24"
    assert v24.pop("quality_intervention") == (
        "unsaturated_idle_plus_low_full_teacher_v1"
    )
    assert v24.pop("teacher_imitation_coefficient") == 0.05
    assert v24["optimizer_ppo"].pop("teacher_imitation_coefficient") == 0.05
    assert v24.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v20.json"
    )
    assert v25 == v24

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v21"] == path.name


def test_v26_final_full_teacher_and_dev_v22_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v22.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v22"
    assert confirmation["seed_set_version"] == 22
    assert confirmation["seeds"] == list(range(221001, 221161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v25 = json.loads(
        (training_dir / "m8-selector-v25-moderate-full-teacher.json").read_text(
            encoding="utf-8"
        )
    )
    v26 = json.loads(
        (training_dir / "m8-selector-v26-final-full-teacher.json").read_text(
            encoding="utf-8"
        )
    )
    assert v26.pop("candidate_version") == "v26"
    assert v26.pop("quality_intervention") == (
        "unsaturated_idle_plus_final_full_teacher_v3"
    )
    assert v26.pop("teacher_imitation_coefficient") == 0.2
    assert v26["optimizer_ppo"].pop("teacher_imitation_coefficient") == 0.2
    assert v26.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v22.json"
    )
    assert v25.pop("candidate_version") == "v25"
    assert v25.pop("quality_intervention") == (
        "unsaturated_idle_plus_moderate_full_teacher_v2"
    )
    assert v25.pop("teacher_imitation_coefficient") == 0.1
    assert v25["optimizer_ppo"].pop("teacher_imitation_coefficient") == 0.1
    assert v25.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v21.json"
    )
    assert v26 == v25

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v22"] == path.name


def test_v27_successful_teacher_warmup_and_dev_v23_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v23.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v23"
    assert confirmation["seed_set_version"] == 23
    assert confirmation["seeds"] == list(range(231001, 231161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v24 = json.loads(
        (training_dir / "m8-selector-v24-resource-scoped-retry.json").read_text(
            encoding="utf-8"
        )
    )
    v27 = json.loads(
        (
            training_dir
            / "m8-selector-v27-successful-teacher-warmup.json"
        ).read_text(encoding="utf-8")
    )
    assert v27.pop("candidate_version") == "v27"
    assert v27.pop("quality_intervention") == (
        "unsaturated_idle_plus_successful_teacher_trajectory_warmup_v1"
    )
    assert v27.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v23.json"
    )
    assert v27.pop("teacher_warmup_cycles") == 1
    assert v27.pop("teacher_warmup_epochs") == 8
    assert v27.pop("teacher_warmup_minibatch_size") == 128
    assert v27.pop("teacher_warmup_success_only") is True
    assert v27.pop("teacher_warmup_shuffle_seed") == 8605
    assert v27.pop("teacher_warmup_minibatch_seed") == 8606
    assert v24.pop("candidate_version") == "v24"
    assert v24.pop("quality_intervention") == (
        "unsaturated_idle_plus_low_full_teacher_v1"
    )
    assert v24.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v20.json"
    )
    assert v27 == v24

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v23"] == path.name


def test_v28_successful_teacher_rehearsal_and_dev_v24_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v24.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v24"
    assert confirmation["seed_set_version"] == 24
    assert confirmation["seeds"] == list(range(241001, 241161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v27 = json.loads(
        (
            training_dir
            / "m8-selector-v27-successful-teacher-warmup.json"
        ).read_text(encoding="utf-8")
    )
    v28 = json.loads(
        (
            training_dir
            / "m8-selector-v28-successful-teacher-rehearsal.json"
        ).read_text(encoding="utf-8")
    )
    assert v28.pop("candidate_version") == "v28"
    assert v28.pop("quality_intervention") == (
        "unsaturated_idle_plus_successful_teacher_trajectory_rehearsal_v2"
    )
    assert v28.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v24.json"
    )
    assert v28.pop("teacher_rehearsal_epochs_per_update") == 1
    assert v28.pop("teacher_rehearsal_minibatch_seed") == 8607
    assert v27.pop("candidate_version") == "v27"
    assert v27.pop("quality_intervention") == (
        "unsaturated_idle_plus_successful_teacher_trajectory_warmup_v1"
    )
    assert v27.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v23.json"
    )
    assert v28 == v27

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v24"] == path.name


def test_v29_diverse_teacher_corpus_and_dev_v25_are_precommitted():
    teacher_path = DEFAULT_SEED_SET.with_name(
        "bootstrap-defense-v1-teacher-train-v1.json"
    )
    teacher = _load_seed_set(teacher_path)
    assert teacher["seed_set_id"] == "bootstrap-defense-v1-teacher-train-v1"
    assert teacher["seed_set_version"] == 1
    assert teacher["split"] == "train"
    assert teacher["seeds"] == list(range(291001, 291257))
    teacher_seeds = set(teacher["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != teacher_path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert teacher_seeds.isdisjoint(document["seeds"]), other.name

    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v25.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v25"
    assert confirmation["seed_set_version"] == 25
    assert confirmation["seeds"] == list(range(251001, 251161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v28 = json.loads(
        (
            training_dir
            / "m8-selector-v28-successful-teacher-rehearsal.json"
        ).read_text(encoding="utf-8")
    )
    v29 = json.loads(
        (
            training_dir
            / "m8-selector-v29-diverse-successful-teacher-corpus.json"
        ).read_text(encoding="utf-8")
    )
    assert v29.pop("candidate_version") == "v29"
    assert v29.pop("quality_intervention") == (
        "unsaturated_idle_plus_diverse_successful_teacher_trajectory_rehearsal_v3"
    )
    assert v29.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v25.json"
    )
    assert v29.pop("teacher_warmup_seed_set").endswith(
        "bootstrap-defense-v1-teacher-train-v1.json"
    )
    assert v28.pop("candidate_version") == "v28"
    assert v28.pop("quality_intervention") == (
        "unsaturated_idle_plus_successful_teacher_trajectory_rehearsal_v2"
    )
    assert v28.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v24.json"
    )
    assert v29 == v28

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v25"] == path.name


def test_v30_budgeted_diverse_teacher_corpus_and_dev_v26_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v26.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v26"
    assert confirmation["seed_set_version"] == 26
    assert confirmation["seeds"] == list(range(261001, 261161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v29 = json.loads(
        (
            training_dir
            / "m8-selector-v29-diverse-successful-teacher-corpus.json"
        ).read_text(encoding="utf-8")
    )
    v30 = json.loads(
        (
            training_dir
            / "m8-selector-v30-budgeted-diverse-teacher-corpus.json"
        ).read_text(encoding="utf-8")
    )
    assert v30.pop("candidate_version") == "v30"
    assert v30.pop("quality_intervention") == (
        "unsaturated_idle_plus_budgeted_diverse_successful_"
        "teacher_trajectory_rehearsal_v4"
    )
    assert v30.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v26.json"
    )
    assert v30.pop("teacher_warmup_samples_per_epoch") == 121
    assert v30.pop("teacher_rehearsal_samples_per_epoch") == 121
    assert v29.pop("candidate_version") == "v29"
    assert v29.pop("quality_intervention") == (
        "unsaturated_idle_plus_diverse_successful_teacher_trajectory_rehearsal_v3"
    )
    assert v29.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v25.json"
    )
    assert v30 == v29

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v26"] == path.name


def test_v31_initial_schematic_prior_and_dev_v27_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v27.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v27"
    assert confirmation["seed_set_version"] == 27
    assert confirmation["seeds"] == list(range(271001, 271161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v30 = json.loads(
        (
            training_dir
            / "m8-selector-v30-budgeted-diverse-teacher-corpus.json"
        ).read_text(encoding="utf-8")
    )
    v31 = json.loads(
        (
            training_dir
            / "m8-selector-v31-initial-schematic-prior.json"
        ).read_text(encoding="utf-8")
    )
    assert v31.pop("candidate_version") == "v31"
    assert v31.pop("quality_intervention") == (
        "unsaturated_idle_plus_budgeted_diverse_teacher_and_"
        "initial_schematic_prior_v5"
    )
    assert v31.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v27.json"
    )
    assert v31.pop("policy_logit_adjustment") == {
        "schema": "initial_task_type_logit_bias_v1",
        "tick": 0,
        "task_type": "BUILD_SCHEMATIC",
        "bias": 1.0,
    }
    assert v30.pop("candidate_version") == "v30"
    assert v30.pop("quality_intervention") == (
        "unsaturated_idle_plus_budgeted_diverse_successful_"
        "teacher_trajectory_rehearsal_v4"
    )
    assert v30.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v26.json"
    )
    assert v31 == v30

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v27"] == path.name


def test_v32_resource_actionability_staging_and_dev_v28_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v28.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v28"
    assert confirmation["seed_set_version"] == 28
    assert confirmation["seeds"] == list(range(281001, 281161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v31 = json.loads(
        (
            training_dir
            / "m8-selector-v31-initial-schematic-prior.json"
        ).read_text(encoding="utf-8")
    )
    v32 = json.loads(
        (
            training_dir
            / "m8-selector-v32-resource-actionability-staging.json"
        ).read_text(encoding="utf-8")
    )
    assert v32.pop("candidate_version") == "v32"
    assert v32.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
        "resource_actionability_staging_v6"
    )
    assert v32.pop("quality_intervention") == (
        "resource_actionability_and_proactive_staging_v6"
    )
    assert v32.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v28.json"
    )
    assert v31.pop("candidate_version") == "v31"
    assert v31.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_v5"
    )
    assert v31.pop("quality_intervention") == (
        "unsaturated_idle_plus_budgeted_diverse_teacher_and_"
        "initial_schematic_prior_v5"
    )
    assert v31.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v27.json"
    )
    assert v32 == v31

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v28"] == path.name


def test_v33_secondary_seat_staging_and_dev_v29_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v29.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v29"
    assert confirmation["seed_set_version"] == 29
    assert confirmation["seeds"] == list(range(282001, 282161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v32 = json.loads(
        (
            training_dir
            / "m8-selector-v32-resource-actionability-staging.json"
        ).read_text(encoding="utf-8")
    )
    v33 = json.loads(
        (
            training_dir / "m8-selector-v33-secondary-seat-staging.json"
        ).read_text(encoding="utf-8")
    )
    assert v33.pop("candidate_version") == "v33"
    assert v33.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
        "resource_actionability_primary_secondary_staging_v7"
    )
    assert v33.pop("quality_intervention") == (
        "resource_actionability_and_primary_secondary_staging_v7"
    )
    assert v33.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v29.json"
    )
    assert v32.pop("candidate_version") == "v32"
    assert v32.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
        "resource_actionability_staging_v6"
    )
    assert v32.pop("quality_intervention") == (
        "resource_actionability_and_proactive_staging_v6"
    )
    assert v32.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v28.json"
    )
    assert v33 == v32

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v29"] == path.name


def test_v34_claim_loss_wake_and_dev_v30_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v30.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v30"
    assert confirmation["seed_set_version"] == 30
    assert confirmation["seeds"] == list(range(283001, 283161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v32 = json.loads(
        (
            training_dir
            / "m8-selector-v32-resource-actionability-staging.json"
        ).read_text(encoding="utf-8")
    )
    v34 = json.loads(
        (
            training_dir / "m8-selector-v34-claim-loss-wake.json"
        ).read_text(encoding="utf-8")
    )
    assert v34.pop("candidate_version") == "v34"
    assert v34.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
        "resource_actionability_staging_claim_loss_wake_v8"
    )
    assert v34.pop("quality_intervention") == (
        "resource_actionability_staging_and_claim_loss_wake_v8"
    )
    assert v34.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v30.json"
    )
    assert v32.pop("candidate_version") == "v32"
    assert v32.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
        "resource_actionability_staging_v6"
    )
    assert v32.pop("quality_intervention") == (
        "resource_actionability_and_proactive_staging_v6"
    )
    assert v32.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v28.json"
    )
    assert v34 == v32

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v30"] == path.name


def test_v35_secondary_claim_loss_wake_and_dev_v31_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v31.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v31"
    assert confirmation["seed_set_version"] == 31
    assert confirmation["seeds"] == list(range(284001, 284161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v32 = json.loads(
        (
            training_dir
            / "m8-selector-v32-resource-actionability-staging.json"
        ).read_text(encoding="utf-8")
    )
    v35 = json.loads(
        (
            training_dir / "m8-selector-v35-secondary-claim-loss-wake.json"
        ).read_text(encoding="utf-8")
    )
    assert v35.pop("candidate_version") == "v35"
    assert v35.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
        "resource_actionability_staging_secondary_claim_loss_wake_v9"
    )
    assert v35.pop("quality_intervention") == (
        "resource_actionability_staging_and_secondary_claim_loss_wake_v9"
    )
    assert v35.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v31.json"
    )
    assert v32.pop("candidate_version") == "v32"
    assert v32.pop("runtime_contract") == (
        "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
        "resource_actionability_staging_v6"
    )
    assert v32.pop("quality_intervention") == (
        "resource_actionability_and_proactive_staging_v6"
    )
    assert v32.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v28.json"
    )
    assert v35 == v32

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v31"] == path.name


def test_v36_build_line_opening_and_dev_v32_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v32.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v32"
    assert confirmation["seed_set_version"] == 32
    assert confirmation["seeds"] == list(range(285001, 285161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v35 = json.loads(
        (
            training_dir / "m8-selector-v35-secondary-claim-loss-wake.json"
        ).read_text(encoding="utf-8")
    )
    v36 = json.loads(
        (
            training_dir / "m8-selector-v36-build-line-opening.json"
        ).read_text(encoding="utf-8")
    )
    assert v36.pop("candidate_version") == "v36"
    assert v36.pop("quality_intervention") == (
        "resource_actionability_staging_secondary_claim_wake_and_"
        "build_line_opening_v10"
    )
    assert v36.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v32.json"
    )
    v36_adjustment = v36.pop("policy_logit_adjustment")
    assert v36_adjustment == {
        "schema": "initial_task_type_logit_bias_v1",
        "tick": 0,
        "task_type": "BUILD_LINE",
        "bias": 1.0,
    }
    assert v35.pop("candidate_version") == "v35"
    assert v35.pop("quality_intervention") == (
        "resource_actionability_staging_and_secondary_claim_loss_wake_v9"
    )
    assert v35.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v31.json"
    )
    v35_adjustment = v35.pop("policy_logit_adjustment")
    assert v35_adjustment == {
        "schema": "initial_task_type_logit_bias_v1",
        "tick": 0,
        "task_type": "BUILD_SCHEMATIC",
        "bias": 1.0,
    }
    assert v36 == v35

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v32"] == path.name


def test_v37_seat2_harvest_opening_and_dev_v33_are_precommitted():
    path = DEFAULT_SEED_SET.with_name("bootstrap-defense-v1-dev-v33.json")
    confirmation = _load_seed_set(path)
    assert confirmation["seed_set_id"] == "bootstrap-defense-v1-dev-v33"
    assert confirmation["seed_set_version"] == 33
    assert confirmation["seeds"] == list(range(286001, 286161))
    confirmation_seeds = set(confirmation["seeds"])
    for other in DEFAULT_SEED_SET.parent.glob("bootstrap-defense-*.json"):
        if other != path:
            document = json.loads(other.read_text(encoding="utf-8"))
            assert confirmation_seeds.isdisjoint(document["seeds"]), other.name

    training_dir = DEFAULT_SEED_SET.parents[1] / "training"
    v35 = json.loads(
        (
            training_dir / "m8-selector-v35-secondary-claim-loss-wake.json"
        ).read_text(encoding="utf-8")
    )
    v37 = json.loads(
        (
            training_dir / "m8-selector-v37-seat2-harvest-opening.json"
        ).read_text(encoding="utf-8")
    )
    assert v37.pop("candidate_version") == "v37"
    assert v37.pop("quality_intervention") == (
        "resource_actionability_staging_secondary_claim_wake_and_"
        "seat2_harvest_opening_v10"
    )
    assert v37.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v33.json"
    )
    assert v37.pop("scripted_partner_opening") == {
        "schema": "fixed_seat_initial_task_type_v1",
        "tick": 0,
        "agent_id": 2,
        "task_type": "HARVEST_RESOURCE",
    }
    assert v35.pop("candidate_version") == "v35"
    assert v35.pop("quality_intervention") == (
        "resource_actionability_staging_and_secondary_claim_loss_wake_v9"
    )
    assert v35.pop("confirmation_seed_set").endswith(
        "bootstrap-defense-v1-dev-v31.json"
    )
    assert v37 == v35

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v33"] == path.name


def test_v38_owned_schematic_staging_and_sealed_sets_are_reserved():
    config_dir = DEFAULT_SEED_SET.parents[1] / "training"
    evaluation_dir = DEFAULT_SEED_SET.parent
    v37_path = config_dir / "m8-selector-v37-seat2-harvest-opening.json"
    v38_path = config_dir / "m8-selector-v38-owned-schematic-staging.json"
    umbrella_path = (
        evaluation_dir / "m8-selector-v38-sealed-evaluation-umbrella.json"
    )
    freeze_path = evaluation_dir / "m8-selector-v38-sealed-evaluation-freeze.json"

    v37 = json.loads(v37_path.read_text(encoding="utf-8"))
    v38 = json.loads(v38_path.read_text(encoding="utf-8"))
    expected_changes = {
        "candidate_version": "v38",
        "runtime_contract": (
            "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
            "resource_actionability_staging_secondary_claim_loss_wake_"
            "owned_schematic_staging_v10"
        ),
        "quality_intervention": (
            "resource_actionability_staging_secondary_claim_wake_seat2_"
            "harvest_and_owned_schematic_staging_v11"
        ),
        "confirmation_seed_set": (
            "configs/evaluation/bootstrap-defense-v1-dev-v34.json"
        ),
        "held_out_seed_set_id": "bootstrap-defense-v1-held-out-v5",
        "held_out_seed_set_version": 5,
    }
    assert {key: v38[key] for key in expected_changes} == expected_changes
    for key in expected_changes:
        v37.pop(key)
        v38.pop(key)
    assert v38 == v37

    umbrella = json.loads(umbrella_path.read_text(encoding="utf-8"))
    assert umbrella["schema"] == "m8_sealed_evaluation_umbrella_v1"
    assert umbrella["candidate_version"] == "v38"
    assert umbrella["status"] == "reserved_before_membership_creation"
    assert umbrella["training_config"] == {
        "path": "configs/training/m8-selector-v38-owned-schematic-staging.json",
        "sha256": "d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf",
    }
    assert hashlib.sha256(v38_path.read_bytes()).hexdigest() == (
        umbrella["training_config"]["sha256"]
    )
    assert umbrella["access_owner"] == "primary_agent_only"
    assert umbrella["delegation_forbidden"] is True

    expected_sets = [
        {
            "role": "confirmation",
            "seed_set_id": "bootstrap-defense-v1-dev-v34",
            "seed_set_version": 34,
            "split": "dev",
            "count": 160,
            "path": "configs/evaluation/bootstrap-defense-v1-dev-v34.json",
            "membership_state_at_reservation": "not_created",
            "exclusive_umbrella_attempt": (
                "runs/m8-selector-v38-dev-v34-umbrella-attempt.json"
            ),
            "replaces": "bootstrap-defense-v1-dev-v33",
        },
        {
            "role": "final",
            "seed_set_id": "bootstrap-defense-v1-held-out-v5",
            "seed_set_version": 5,
            "split": "held-out",
            "count": 160,
            "path": (
                "configs/evaluation/bootstrap-defense-v1-held-out-v5.json"
            ),
            "membership_state_at_reservation": "not_created",
            "exclusive_umbrella_attempt": (
                "runs/m8-selector-v38-held-out-v5-umbrella-attempt.json"
            ),
            "replaces": "bootstrap-defense-v1-held-out-v4",
        },
    ]
    assert umbrella["replacement_sets"] == expected_sets
    assert umbrella["rules"] == [
        (
            "This reservation must be committed before either membership "
            "document is created or read."
        ),
        (
            "Membership construction and disjointness verification are "
            "primary-agent-only and must not render seed values into agent "
            "output."
        ),
        (
            "The committed one-way consumer must atomically create the "
            "set-specific umbrella attempt before its first manifest read or "
            "baseline episode."
        ),
        (
            "A started, aborted, failed, exposed, or completed attempt consumes "
            "that set permanently."
        ),
        (
            "No confirmation access is authorized until exact replicas and "
            "reusable permanent-greedy and matched-greedy scorecards pass."
        ),
        (
            "No final access is authorized until confirmation passes every "
            "frozen gate."
        ),
    ]

    repository_root = DEFAULT_SEED_SET.parents[2]
    expected_hashes = {
        "bootstrap-defense-v1-dev-v34": (
            "bef6bb17c7759530dc216961733839808dbff228bb96a09232dced89a7ca5ac7"
        ),
        "bootstrap-defense-v1-held-out-v5": (
            "1118ef59b0953aacd86176737777013bb2c6498e128f28bcbb7850e6ad586910"
        ),
    }
    for reserved in expected_sets:
        path = (repository_root / reserved["path"]).resolve()
        # Membership existence is safe to verify; opening a governed manifest
        # before its one-way attempt is not. Hash/disjointness evidence comes
        # only from the committed value-free receipt below.
        assert path.is_file()

    from mindustry_agents.tools.evaluate_ladder import SEED_SET_FILES

    assert SEED_SET_FILES["dev-v34"] == "bootstrap-defense-v1-dev-v34.json"

    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    assert freeze["schema"] == "m8_sealed_evaluation_freeze_v1"
    assert freeze["candidate_version"] == "v38"
    assert freeze["status"] == "membership_frozen_unconsumed"
    assert freeze["umbrella"] == {
        "path": "configs/evaluation/m8-selector-v38-sealed-evaluation-umbrella.json",
        "sha256": (
            "a2e2389925797a5f5a8c93224561f68f36fd443afbebdc07f888aaf6bef6f27a"
        ),
        "commit": "de597c84623bae4f1eee6139992938bb46fe5108",
    }
    assert freeze["generator_commit"] == (
        "a7504a478177d2f751740ce2d15df377d66119f9"
    )
    assert freeze["repository_head_before_generation"] == (
        "a7504a478177d2f751740ce2d15df377d66119f9"
    )
    assert freeze["values_emitted"] is False
    assert freeze["global_disjointness_verified"] is True
    assert freeze["sets"] == [
        {
            **{
                key: expected_sets[0][key]
                for key in (
                    "role",
                    "seed_set_id",
                    "seed_set_version",
                    "split",
                    "count",
                    "path",
                )
            },
            "sha256": expected_hashes[expected_sets[0]["seed_set_id"]],
            "consumption_state": "unconsumed",
        },
        {
            **{
                key: expected_sets[1][key]
                for key in (
                    "role",
                    "seed_set_id",
                    "seed_set_version",
                    "split",
                    "count",
                    "path",
                )
            },
            "sha256": expected_hashes[expected_sets[1]["seed_set_id"]],
            "consumption_state": "unconsumed",
        },
    ]
    assert hashlib.sha256(freeze_path.read_bytes()).hexdigest() == (
        "7282a3cd405f2d6b00dd3942fb8da2b2f62eb3a8f567dc067edc07756787018e"
    )


def test_v39_partner_intent_coordinate_and_confirmation_umbrella_are_frozen():
    repository_root = DEFAULT_SEED_SET.parents[2]
    training_dir = repository_root / "configs" / "training"
    evaluation_dir = repository_root / "configs" / "evaluation"
    v38_path = training_dir / "m8-selector-v38-owned-schematic-staging.json"
    v39_path = training_dir / "m8-selector-v39-partner-intent-duplication-risk.json"
    umbrella_path = evaluation_dir / "m8-selector-v39-confirmation-umbrella.json"
    final_umbrella_path = (
        evaluation_dir / "m8-selector-v39-replacement-final-umbrella.json"
    )

    v38 = json.loads(v38_path.read_text(encoding="utf-8"))
    v39 = json.loads(v39_path.read_text(encoding="utf-8"))
    expected_changes = {
        "candidate_version": "v39",
        "runtime_contract": (
            "abandon_wait_resource_scoped_retry_agent_death_available_idle_"
            "resource_actionability_staging_secondary_claim_loss_wake_"
            "owned_schematic_staging_partner_intent_risk_v11"
        ),
        "quality_intervention": (
            "resource_actionability_staging_secondary_claim_wake_seat2_"
            "harvest_owned_schematic_staging_and_partner_intent_risk_v12"
        ),
        "confirmation_seed_set": (
            "configs/evaluation/bootstrap-defense-v1-dev-v35.json"
        ),
        "held_out_seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "held_out_seed_set_version": 6,
        "partner_intent_duplication_risk": {
            "schema": "fixed_partner_selected_task_duplication_risk_v1",
            "agent_ids": [1, 2],
            "match": "task_id",
            "feature": "utility_features.duplication_risk",
            "value": 1.0,
        },
    }
    assert {key: v39[key] for key in expected_changes} == expected_changes
    for key in expected_changes:
        v38.pop(key, None)
        v39.pop(key)
    assert v39 == v38

    expected_config_sha256 = (
        "54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924"
    )
    assert hashlib.sha256(v39_path.read_bytes()).hexdigest() == (
        expected_config_sha256
    )

    umbrella = json.loads(umbrella_path.read_text(encoding="utf-8"))
    assert umbrella["schema"] == "m8_confirmation_evaluation_umbrella_v1"
    assert umbrella["candidate_version"] == "v39"
    assert umbrella["status"] == "reserved_before_membership_creation"
    assert umbrella["training_config"] == {
        "path": (
            "configs/training/"
            "m8-selector-v39-partner-intent-duplication-risk.json"
        ),
        "sha256": (
            "0b883c41ab297a132aa40c9c43bd5760c13a7afb5d6239fe9666d00b80f2f995"
        ),
    }
    assert umbrella["access_owner"] == "primary_agent_only"
    assert umbrella["delegation_forbidden"] is True
    assert umbrella["replacement_set"] == {
        "role": "confirmation",
        "seed_set_id": "bootstrap-defense-v1-dev-v35",
        "seed_set_version": 35,
        "split": "dev",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-dev-v35.json",
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": (
            "runs/m8-selector-v39-dev-v35-umbrella-attempt.json"
        ),
        "replaces": "bootstrap-defense-v1-dev-v34",
    }
    assert umbrella["sealed_final_binding"] == {
        "seed_set_id": "bootstrap-defense-v1-held-out-v5",
        "seed_set_version": 5,
        "split": "held-out",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-held-out-v5.json",
        "sha256": (
            "1118ef59b0953aacd86176737777013bb2c6498e128f28bcbb7850e6ad586910"
        ),
        "consumption_state": "sealed_unconsumed",
        "membership_read_for_v39_reservation": False,
    }

    final_umbrella = json.loads(final_umbrella_path.read_text(encoding="utf-8"))
    assert final_umbrella["schema"] == "m8_replacement_final_evaluation_umbrella_v1"
    assert final_umbrella["training_config"]["sha256"] == expected_config_sha256
    assert final_umbrella["confirmation_binding"]["consumption_state"] == (
        "frozen_unconsumed"
    )
    assert final_umbrella["confirmation_binding"]["membership_read_for_rebinding"] is False
    assert final_umbrella["retired_final"]["seed_set_id"] == (
        "bootstrap-defense-v1-held-out-v5"
    )
    assert final_umbrella["replacement_final"]["seed_set_id"] == (
        "bootstrap-defense-v1-held-out-v6"
    )
    assert final_umbrella["replacement_final"]["membership_state_at_reservation"] == (
        "not_created"
    )
