"""Value-free checks for the held-out-v7 reservation and freezer."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UMBRELLA = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v49-held-out-v7-umbrella.json"
)


def test_held_out_v7_is_reserved_without_membership_access() -> None:
    umbrella = json.loads(UMBRELLA.read_text(encoding="utf-8"))
    reserved = umbrella["replacement_final"]

    assert umbrella["status"] == "reserved_before_membership_creation"
    assert umbrella["access_owner"] == "primary_agent_only"
    assert umbrella["delegation_forbidden"] is True
    assert reserved["seed_set_id"] == "bootstrap-defense-v1-held-out-v7"
    assert reserved["seed_set_version"] == 7
    assert reserved["membership_state_at_reservation"] == "not_created"
    assert reserved["exclusive_namespace"] == {
        "minimum_inclusive": 17_000_000_000,
        "maximum_exclusive": 18_000_000_000,
    }
    assert umbrella["retired_final"] == {
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "status": "retired_membership_exposed_unexecuted",
        "membership_read_authorized": False,
    }
