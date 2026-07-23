"""Pure governance checks for the precommitted V44 temporal coordinate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V43_CONFIG = ROOT / "configs/training/m8-selector-v43-candidate-set-context.json"
V44_CONFIG = ROOT / "configs/training/m8-selector-v44-lagged-boundary-context.json"
V44_UMBRELLA = ROOT / "configs/evaluation/m8-selector-v44-confirmation-umbrella.json"
V44_CONFIG_SHA256 = "9a23c90567754eb84a06f47bfecfe99fd93ba85499167dd3bc3657ebfc9dc9c2"
V44_UMBRELLA_SHA256 = "4a526274d956872680cd16cb5fefb2b7f450931b9a9a83b7aa742034a45d09c8"
V44_PARENT_COMMIT = "be8e2c32b63c32f39d1880ffee9ac16ebd8fa47a"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v44_changes_only_identity_confirmation_and_temporal_architecture() -> None:
    v43 = _load(V43_CONFIG)
    v44 = _load(V44_CONFIG)
    changed = {
        key for key in set(v43) | set(v44) if v43.get(key) != v44.get(key)
    }
    assert changed == {
        "candidate_version",
        "confirmation_seed_set",
        "quality_intervention",
        "normalizers",
        "model_architecture",
    }
    assert _sha256(V44_CONFIG) == V44_CONFIG_SHA256
    assert v44["candidate_version"] == "v44"
    assert v44["confirmation_seed_set"] == (
        "configs/evaluation/bootstrap-defense-v1-dev-v40.json"
    )
    assert v44["normalizers"] == {
        "feature_schema": "selector_features_v2_lagged_boundary",
        "source": (
            "scenario metadata, fixed protocol bounds, and the previous "
            "authoritative decision boundary"
        ),
        "running_statistics": False,
    }
    architecture = v44["model_architecture"]
    assert architecture == {
        "schema": "selector_actor_critic_v3_lagged_set_context",
        "candidate_encoder": [37, 64, 64],
        "scalar_encoder": [160, 64, 64],
        "lagged_context": {
            "current_scalars": 56,
            "previous_scalars": 56,
            "previous_candidate_masked_mean": 37,
            "previous_candidate_count_fraction": 1,
            "previous_action_one_hot": 10,
            "initial_value": "all_zero",
        },
        "candidate_context": "masked_mean_other_candidates",
        "select_head": [192, 64, 1],
        "special_context": "masked_mean_all_candidates",
        "special_head": [128, 64, 2],
        "critic": [128, 64, 1],
        "activation": "Tanh",
    }


def test_v44_value_free_reservation_is_exact_and_access_gated() -> None:
    umbrella = _load(V44_UMBRELLA)
    assert _sha256(V44_UMBRELLA) == V44_UMBRELLA_SHA256
    assert umbrella["repository_parent_commit"] == V44_PARENT_COMMIT
    assert umbrella["training_config"] == {
        "path": "configs/training/m8-selector-v44-lagged-boundary-context.json",
        "sha256": V44_CONFIG_SHA256,
    }
    assert umbrella["replacement_set"] == {
        "role": "confirmation",
        "seed_set_id": "bootstrap-defense-v1-dev-v40",
        "seed_set_version": 40,
        "split": "dev",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-dev-v40.json",
        "exclusive_namespace": {
            "minimum_inclusive": 8_000_000_000,
            "maximum_exclusive": 9_000_000_000,
        },
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": (
            "runs/m8-selector-v44-dev-v40-umbrella-attempt.json"
        ),
        "replaces": "bootstrap-defense-v1-dev-v39",
    }
    binding = umbrella["sealed_final_binding"]
    assert binding["seed_set_id"] == "bootstrap-defense-v1-held-out-v6"
    assert binding["consumption_state"] == "sealed_unconsumed"
    assert binding["membership_read_for_v44_reservation"] is False
    rules = umbrella["rules"]
    assert "committed before dev-v40 membership creation or model work" in rules[0]
    assert "No dev-v40 access" in rules[5]
    assert "cannot be read until dev-v40 passes every frozen gate" in rules[6]
