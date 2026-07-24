"""Governance tests for ADR-0121's semantic-target diagnostic."""

import json
from pathlib import Path

import pytest

from mindustry_agents.training.candidate_semantic_target import (
    PROTOCOL_SHA256,
    classify,
    validate_inputs,
)
from mindustry_agents.training.ippo_ppo import sha256_path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT
    / "configs/evaluation/m9-candidate-semantic-target-diagnostic-protocol.json"
)


def _rules():
    return {
        "top_semantic_target_pairs": 3,
        "minimum_top_target_pair_fraction_for_concentration": 0.5,
        "minimum_exact_feature_alias_fraction": 0.5,
    }


def test_protocol_is_exact_public_only_and_non_mutating():
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["data_classification"] == "public_dev_only"
    assert protocol["checkpoint"]["lineage_update"] == 64
    assert not protocol["authority"]["may_train_or_modify_model"]
    assert not protocol["authority"]["may_access_confirmation"]
    assert not protocol["authority"]["may_access_held_out"]


def test_bound_local_inputs_are_exact_and_rejected():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if not (ROOT / protocol["checkpoint"]["path"]).exists():
        pytest.skip("ignored immutable checkpoint is not local")
    loaded, _, seeds = validate_inputs(ROOT)
    assert len(seeds) == len(set(seeds)) == 40
    assert loaded["checkpoint"]["lineage_update"] == 64


def test_classification_distinguishes_alias_and_ranking_signals():
    aliased = classify(
        {
            "same_family_disagreements": 10,
            "same_family_exact_feature_row_aliases": 6,
            "semantic_target_pair_confusion_by_outcome": {
                "[\"a\",\"b\"]:loss": 5,
                "[\"c\",\"d\"]:win": 3,
                "[\"e\",\"f\"]:loss": 1,
                "[\"g\",\"h\"]:win": 1,
            },
        },
        _rules(),
    )
    assert aliased["target_pair_concentration_signal"]
    assert aliased["feature_alias_signal"]
    assert not aliased["feature_distinguishable_ranking_signal"]
    assert not aliased["successor_training_authorized"]

    ranked = classify(
        {
            "same_family_disagreements": 10,
            "same_family_exact_feature_row_aliases": 2,
            "semantic_target_pair_confusion_by_outcome": {
                "[\"a\",\"b\"]:loss": 1,
                "[\"c\",\"d\"]:win": 1,
                "[\"e\",\"f\"]:loss": 1,
                "[\"g\",\"h\"]:win": 1,
                "[\"i\",\"j\"]:loss": 1,
                "[\"k\",\"l\"]:win": 1,
                "[\"m\",\"n\"]:loss": 1,
                "[\"o\",\"p\"]:win": 1,
                "[\"q\",\"r\"]:loss": 1,
                "[\"s\",\"t\"]:win": 1,
            },
        },
        _rules(),
    )
    assert not ranked["target_pair_concentration_signal"]
    assert not ranked["feature_alias_signal"]
    assert ranked["feature_distinguishable_ranking_signal"]
    drifted = _rules()
    drifted["top_semantic_target_pairs"] = 2
    with pytest.raises(ValueError, match="thresholds drifted"):
        classify(ranked, drifted)
