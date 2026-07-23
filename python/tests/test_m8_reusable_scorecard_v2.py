"""Governance checks for the public 160-root M8 reusable-scorecard screen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMBERSHIP = (
    ROOT
    / "configs"
    / "evaluation"
    / "bootstrap-defense-v1-reusable-scorecard-v2.json"
)
UMBRELLA = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v46-reusable-v2-umbrella.json"
)
RECEIPT = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v46-reusable-v2-freeze.json"
)
RESULT = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v46-reusable-v2-result.json"
)
DOMAIN = "mindustry-agent:m8:reusable-scorecard-v2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_seeds() -> list[int]:
    values: set[int] = set()
    counter = 0
    while len(values) < 160:
        digest = hashlib.sha256(f"{DOMAIN}:{counter}".encode()).digest()
        values.add(
            11_000_000_000
            + int.from_bytes(digest[:8], "big") % 1_000_000_000
        )
        counter += 1
    return sorted(values)


def test_reusable_scorecard_v2_is_public_deterministic_and_precommitted() -> None:
    membership = json.loads(MEMBERSHIP.read_text(encoding="utf-8"))
    umbrella = json.loads(UMBRELLA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert membership["seed_set_id"] == (
        "bootstrap-defense-v1-reusable-scorecard-v2"
    )
    assert membership["seed_set_version"] == 2
    assert membership["split"] == "dev"
    assert membership["seeds"] == _expected_seeds()
    assert len(membership["seeds"]) == len(set(membership["seeds"])) == 160
    assert all(
        11_000_000_000 <= seed < 12_000_000_000
        for seed in membership["seeds"]
    )

    assert umbrella["status"] == "reserved_before_reusable_membership_creation"
    assert umbrella["reusable_set"]["membership_state_at_reservation"] == (
        "not_created"
    )
    assert umbrella["reusable_set"]["count"] == 160
    assert umbrella["replacement_confirmation_reservation"][
        "membership_state_at_reservation"
    ] == "not_created"
    assert umbrella["retired_confirmation"]["membership_read_authorized"] is False
    assert umbrella["sealed_final"]["membership_read_authorized"] is False

    assert receipt["status"] == "membership_frozen_unevaluated"
    assert receipt["membership"]["sha256"] == _sha256(MEMBERSHIP)
    assert receipt["membership"]["evaluation_episodes_at_freeze"] == 0
    assert set(receipt["restricted_access"].values()) == {0}


def test_reusable_scorecard_v2_rejection_preserves_restricted_sets() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    assert result["status"] == "rejected_before_confirmation"
    assert result["wins"]["learned_selector_v46"] == 96
    assert result["wins"]["greedy_utility"] == 84
    assert result["control"]["passed"] is True
    assert result["scorecards"]["permanent_greedy"]["passed"] is False
    assert result["scorecards"]["matched_greedy"]["passed"] is True
    assert result["eligible_for_confirmation"] is False
    assert result["restricted_access"] == {
        "dev_v42_membership_reads": 0,
        "dev_v43_constructed": False,
        "held_out_v6_membership_reads": 0,
        "confirmation_episodes": 0,
        "held_out_episodes": 0,
    }
