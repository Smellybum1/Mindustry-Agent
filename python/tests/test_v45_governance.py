"""Pure governance checks for the precommitted V45 residual coordinate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V44 = ROOT / "configs/training/m8-selector-v44-lagged-boundary-context.json"
V45 = ROOT / "configs/training/m8-selector-v45-residual-lagged-context.json"
UMBRELLA = ROOT / "configs/evaluation/m8-selector-v45-confirmation-umbrella.json"
CONFIG_SHA = "a7d0c8029acebe79dfc33224c96fdce89b33c043744dde222f8982053324be8c"
UMBRELLA_SHA = "e4fe0b56a95fa64cb59e5ea853c878b4d678f86c629bba72b393a68b5eb7b8f2"
PARENT = "cafe44c8e332d282fc61c5b06fb6f43ad044f253"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v45_changes_only_identity_confirmation_and_model_architecture() -> None:
    v44 = _load(V44)
    v45 = _load(V45)
    changed = {key for key in set(v44) | set(v45) if v44.get(key) != v45.get(key)}
    assert changed == {
        "candidate_version",
        "confirmation_seed_set",
        "quality_intervention",
        "model_architecture",
    }
    assert _sha(V45) == CONFIG_SHA
    assert v45["candidate_version"] == "v45"
    assert v45["confirmation_seed_set"] == (
        "configs/evaluation/bootstrap-defense-v1-dev-v41.json"
    )
    assert v45["normalizers"] == v44["normalizers"]
    architecture = v45["model_architecture"]
    assert architecture["schema"] == (
        "selector_actor_critic_v4_residual_lagged_set_context"
    )
    assert architecture["current_scalar_encoder"] == [56, 64, 64]
    assert architecture["lagged_context_encoder"] == [104, 64, 64]
    assert architecture["base_select_head"] == [192, 64, 1]
    assert architecture["temporal_select_head"] == [256, 64, 1]
    assert architecture["base_special_head"] == [128, 64, 2]
    assert architecture["temporal_special_head"] == [192, 64, 2]
    assert architecture["temporal_output_initialization"] == (
        "zero_weight_zero_bias"
    )
    assert architecture["actor_combination"] == (
        "base_logits_plus_temporal_residual"
    )


def test_v45_value_free_reservation_is_exact_and_access_gated() -> None:
    umbrella = _load(UMBRELLA)
    assert _sha(UMBRELLA) == UMBRELLA_SHA
    assert umbrella["repository_parent_commit"] == PARENT
    assert umbrella["training_config"] == {
        "path": "configs/training/m8-selector-v45-residual-lagged-context.json",
        "sha256": CONFIG_SHA,
    }
    replacement = umbrella["replacement_set"]
    assert replacement["seed_set_id"] == "bootstrap-defense-v1-dev-v41"
    assert replacement["seed_set_version"] == 41
    assert replacement["count"] == 160
    assert replacement["exclusive_namespace"] == {
        "minimum_inclusive": 9_000_000_000,
        "maximum_exclusive": 10_000_000_000,
    }
    assert replacement["membership_state_at_reservation"] == "not_created"
    binding = umbrella["sealed_final_binding"]
    assert binding["seed_set_id"] == "bootstrap-defense-v1-held-out-v6"
    assert binding["consumption_state"] == "sealed_unconsumed"
    assert binding["membership_read_for_v45_reservation"] is False
    assert "No dev-v41 access" in umbrella["rules"][5]
