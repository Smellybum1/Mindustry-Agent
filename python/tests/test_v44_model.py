"""Focused ADR-0061 lagged-boundary feature/model checks."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import torch

from mindustry_agents.training.model import (
    MODEL_ARCHITECTURE_V3,
    MODEL_SCHEMA_V3,
    SelectorLaggedSetContextActorCritic,
    build_selector_model,
    expected_model_schema,
)
from mindustry_agents.training.ppo_selector import load_checkpoint, save_checkpoint
from mindustry_agents.training.selector import (
    FEATURE_SCHEMA,
    FEATURE_SCHEMA_V2,
    expected_feature_schema,
)


ROOT = Path(__file__).resolve().parents[2]
V43_CONFIG = ROOT / "configs/training/m8-selector-v43-candidate-set-context.json"
V44_CONFIG = ROOT / "configs/training/m8-selector-v44-lagged-boundary-context.json"


def _inputs() -> tuple[torch.Tensor, ...]:
    generator = torch.Generator().manual_seed(7101)
    candidates = torch.rand((2, 8, 37), generator=generator)
    scalars = torch.rand((2, 160), generator=generator)
    present = torch.tensor(
        [
            [True, True, True, False, False, False, False, False],
            [True, False, False, False, False, False, False, False],
        ]
    )
    mask = torch.tensor(
        [
            [True, True, False, False, False, False, False, False, True, True],
            [True, False, False, False, False, False, False, False, False, True],
        ]
    )
    return candidates, scalars, present, mask


def test_v44_factory_is_exact_and_deterministic() -> None:
    config = json.loads(V44_CONFIG.read_text(encoding="utf-8"))
    assert expected_feature_schema(config) == FEATURE_SCHEMA_V2
    assert expected_model_schema(config) == MODEL_SCHEMA_V3
    assert config["model_architecture"] == MODEL_ARCHITECTURE_V3
    first = build_selector_model(config)
    second = build_selector_model(config)
    assert isinstance(first, SelectorLaggedSetContextActorCritic)
    assert all(
        torch.equal(left, right)
        for left, right in zip(first.state_dict().values(), second.state_dict().values())
    )


def test_v44_retains_set_equivariance_invariance_padding_and_masks() -> None:
    model = SelectorLaggedSetContextActorCritic(7102).eval()
    candidates, scalars, present, mask = _inputs()
    permutation = torch.tensor([2, 0, 1, 3, 4, 5, 6, 7])
    permuted_mask = torch.cat((mask[:, :8][:, permutation], mask[:, 8:]), dim=1)
    altered = candidates.clone()
    altered[0, 3:] = 1000.0
    altered[1, 1:] = -1000.0

    with torch.no_grad():
        raw, masked, value = model(candidates, scalars, present, mask)
        padded_raw, _, padded_value = model(altered, scalars, present, mask)
        permuted_raw, permuted_masked, permuted_value = model(
            candidates[:, permutation],
            scalars,
            present[:, permutation],
            permuted_mask,
        )

    assert torch.allclose(raw[:, 8:], padded_raw[:, 8:])
    assert torch.allclose(value, padded_value)
    assert torch.allclose(permuted_raw[:, :8], raw[:, :8][:, permutation])
    assert torch.allclose(permuted_raw[:, 8:], raw[:, 8:])
    assert torch.allclose(permuted_value, value)
    assert torch.allclose(permuted_masked[:, :8], masked[:, :8][:, permutation])
    assert torch.equal(masked > torch.finfo(masked.dtype).min, mask)


def test_v44_model_feature_and_checkpoint_schemas_fail_closed() -> None:
    v43 = json.loads(V43_CONFIG.read_text(encoding="utf-8"))
    v44 = json.loads(V44_CONFIG.read_text(encoding="utf-8"))
    invalid = dict(v44)
    invalid["normalizers"] = dict(v44["normalizers"])
    invalid["normalizers"]["feature_schema"] = FEATURE_SCHEMA
    with pytest.raises(ValueError, match="model/feature schema mismatch"):
        build_selector_model(invalid)

    with tempfile.TemporaryDirectory() as directory:
        model = build_selector_model(v44)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0)
        checkpoint = Path(directory) / "v44.pt"
        save_checkpoint(
            checkpoint,
            model,
            optimizer,
            config_sha256="v44",
            parent_checkpoint="",
            update=1,
            reward_schema="selector_reward_v2",
            feature_schema=FEATURE_SCHEMA_V2,
        )
        with pytest.raises(ValueError, match="checkpoint schema mismatch"):
            load_checkpoint(
                checkpoint,
                build_selector_model(v43),
                reward_schema="selector_reward_v2",
                feature_schema=FEATURE_SCHEMA,
            )
        payload = load_checkpoint(
            checkpoint,
            build_selector_model(v44),
            reward_schema="selector_reward_v2",
            feature_schema=FEATURE_SCHEMA_V2,
        )
        assert payload["feature_schema"] == FEATURE_SCHEMA_V2
        assert payload["model_schema"] == MODEL_SCHEMA_V3
