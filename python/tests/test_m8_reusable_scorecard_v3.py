"""Governance checks for the prospective M8 reusable-scorecard v3 screen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMBERSHIP = (
    ROOT
    / "configs"
    / "evaluation"
    / "bootstrap-defense-v1-reusable-scorecard-v3.json"
)
PROTOCOL = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v49-noninferiority-protocol.json"
)
RECEIPT = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v49-reusable-v3-freeze.json"
)
DOMAIN = "mindustry-agent:m8:reusable-scorecard-v3"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_seeds() -> list[int]:
    values: set[int] = set()
    counter = 0
    while len(values) < 160:
        digest = hashlib.sha256(f"{DOMAIN}:{counter}".encode()).digest()
        values.add(
            15_000_000_000
            + int.from_bytes(digest[:8], "big") % 1_000_000_000
        )
        counter += 1
    return sorted(values)


def test_reusable_v3_is_fresh_deterministic_and_frozen_before_use() -> None:
    membership = json.loads(MEMBERSHIP.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert membership["seed_set_id"] == (
        "bootstrap-defense-v1-reusable-scorecard-v3"
    )
    assert membership["seed_set_version"] == 3
    assert membership["split"] == "dev"
    assert membership["seeds"] == _expected_seeds()
    assert len(membership["seeds"]) == len(set(membership["seeds"])) == 160
    assert all(
        15_000_000_000 <= seed < 16_000_000_000
        for seed in membership["seeds"]
    )

    assert protocol["status"] == "precommitted_before_reusable_v3_membership"
    assert receipt["status"] == "membership_frozen_unevaluated"
    assert receipt["protocol"]["sha256"] == _sha256(PROTOCOL)
    assert receipt["membership"]["sha256"] == _sha256(MEMBERSHIP)
    assert receipt["membership"]["evaluation_episodes_at_freeze"] == 0
    assert set(receipt["restricted_access"].values()) == {0}
