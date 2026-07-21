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
