"""Fast governance checks for the M7.5 scenario-variation harness."""

from __future__ import annotations

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
