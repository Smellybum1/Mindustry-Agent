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
