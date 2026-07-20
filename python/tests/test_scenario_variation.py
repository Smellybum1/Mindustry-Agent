"""Fast governance checks for the M7.5 scenario-variation harness."""

from __future__ import annotations

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
