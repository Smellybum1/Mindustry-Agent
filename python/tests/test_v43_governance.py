"""Pure governance checks for the precommitted V43 architecture coordinate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V42_CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v42-partner-intent-teacher-conflict-relabel.json"
)
V43_CONFIG = (
    ROOT / "configs" / "training" / "m8-selector-v43-candidate-set-context.json"
)
V43_UMBRELLA = (
    ROOT / "configs" / "evaluation" / "m8-selector-v43-confirmation-umbrella.json"
)

V43_CONFIG_SHA256 = (
    "29b4430839451f136bd5cae729f7341cefe74f4cc2b6710cd1bb1e124dc80e99"
)
V43_UMBRELLA_SHA256 = (
    "99851aa2cdbfb469ac32ded36fa0b932a5149e29aa8b94ccb3bbc7f0000e1d1b"
)
V43_PARENT_COMMIT = "74b042587f8be2b7de4fbd32f5926077b39ee2a2"
HELD_OUT_V6_SHA256 = (
    "2bf4aa04ef54d873e961ff367db849c14c72b83bb4d280c4e31ba75bdeefa51c"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v43_changes_only_identity_confirmation_and_model_architecture() -> None:
    v42 = _load_json(V42_CONFIG)
    v43 = _load_json(V43_CONFIG)

    assert _sha256(V43_CONFIG) == V43_CONFIG_SHA256
    assert {
        key for key in set(v42) | set(v43) if v42.get(key) != v43.get(key)
    } == {
        "candidate_version",
        "quality_intervention",
        "confirmation_seed_set",
        "model_architecture",
    }
    assert v43["candidate_version"] == "v43"
    assert v43["confirmation_seed_set"] == (
        "configs/evaluation/bootstrap-defense-v1-dev-v39.json"
    )
    assert v43["model_architecture"] == {
        "schema": "selector_actor_critic_v2_set_context",
        "candidate_encoder": [37, 64, 64],
        "scalar_encoder": [56, 64, 64],
        "candidate_context": "masked_mean_other_candidates",
        "select_head": [192, 64, 1],
        "special_context": "masked_mean_all_candidates",
        "special_head": [128, 64, 2],
        "critic": [128, 64, 1],
        "activation": "Tanh",
    }


def test_v43_value_free_reservation_is_exact_and_access_gated() -> None:
    umbrella = _load_json(V43_UMBRELLA)

    assert _sha256(V43_UMBRELLA) == V43_UMBRELLA_SHA256
    assert umbrella["repository_parent_commit"] == V43_PARENT_COMMIT
    assert umbrella["status"] == "reserved_before_membership_creation"
    assert umbrella["access_owner"] == "primary_agent_only"
    assert umbrella["delegation_forbidden"] is True
    assert umbrella["training_config"] == {
        "path": "configs/training/m8-selector-v43-candidate-set-context.json",
        "sha256": V43_CONFIG_SHA256,
    }

    replacement = umbrella["replacement_set"]
    assert replacement == {
        "role": "confirmation",
        "seed_set_id": "bootstrap-defense-v1-dev-v39",
        "seed_set_version": 39,
        "split": "dev",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-dev-v39.json",
        "exclusive_namespace": {
            "minimum_inclusive": 7_000_000_000,
            "maximum_exclusive": 8_000_000_000,
        },
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": (
            "runs/m8-selector-v43-dev-v39-umbrella-attempt.json"
        ),
        "replaces": "bootstrap-defense-v1-dev-v38",
    }

    assert umbrella["sealed_final_binding"] == {
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "seed_set_version": 6,
        "split": "held-out",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-held-out-v6.json",
        "sha256": HELD_OUT_V6_SHA256,
        "consumption_state": "sealed_unconsumed",
        "membership_read_for_v43_reservation": False,
    }
    rules = umbrella["rules"]
    assert len(rules) == 7
    assert "committed before dev-v39 membership creation or model work" in rules[0]
    assert "[7000000000,8000000000)" in rules[2]
    assert "No dev-v39 access" in rules[5]
    assert "Held-out-v6" in rules[6]
