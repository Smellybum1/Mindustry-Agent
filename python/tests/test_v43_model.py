"""Focused ADR-0060 candidate-set-context model checks."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import torch

from mindustry_agents.training.model import (
    MODEL_ARCHITECTURE_V1,
    MODEL_ARCHITECTURE_V2,
    MODEL_SCHEMA_V1,
    MODEL_SCHEMA_V2,
    SelectorActorCritic,
    SelectorSetContextActorCritic,
    build_selector_model,
    expected_model_schema,
)
from mindustry_agents.training.ppo_selector import load_checkpoint, save_checkpoint


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


def _inputs() -> tuple[torch.Tensor, ...]:
    generator = torch.Generator().manual_seed(7001)
    candidates = torch.rand((2, 8, 37), generator=generator)
    scalars = torch.rand((2, 56), generator=generator)
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


def test_v43_factory_is_exact_deterministic_and_v1_compatible() -> None:
    v42 = json.loads(V42_CONFIG.read_text(encoding="utf-8"))
    v43 = json.loads(V43_CONFIG.read_text(encoding="utf-8"))

    assert expected_model_schema(v42) == MODEL_SCHEMA_V1
    assert expected_model_schema(v43) == MODEL_SCHEMA_V2
    assert v42["model_architecture"] == MODEL_ARCHITECTURE_V1
    assert v43["model_architecture"] == MODEL_ARCHITECTURE_V2
    assert isinstance(build_selector_model(v42), SelectorActorCritic)
    first = build_selector_model(v43)
    second = build_selector_model(v43)
    assert isinstance(first, SelectorSetContextActorCritic)
    assert all(
        torch.equal(left, right)
        for left, right in zip(first.state_dict().values(), second.state_dict().values())
    )


def test_v43_pooling_ignores_padding_and_handles_singleton_context() -> None:
    model = SelectorSetContextActorCritic(7002).eval()
    candidates, scalars, present, mask = _inputs()
    altered = candidates.clone()
    altered[0, 3:] = 1000.0
    altered[1, 1:] = -1000.0

    with torch.no_grad():
        first = model(candidates, scalars, present, mask)
        second = model(altered, scalars, present, mask)

    assert torch.allclose(first[0][0, :3], second[0][0, :3])
    assert torch.allclose(first[0][1, :1], second[0][1, :1])
    assert torch.allclose(first[0][:, 8:], second[0][:, 8:])
    assert torch.allclose(first[2], second[2])
    assert torch.isfinite(first[0]).all()
    assert torch.isfinite(first[2]).all()


def test_v43_is_set_equivariant_invariant_and_mask_preserving() -> None:
    model = SelectorSetContextActorCritic(7003).eval()
    candidates, scalars, present, mask = _inputs()
    permutation = torch.tensor([2, 0, 1, 3, 4, 5, 6, 7])
    permuted_mask = torch.cat((mask[:, :8][:, permutation], mask[:, 8:]), dim=1)

    with torch.no_grad():
        raw, masked, value = model(candidates, scalars, present, mask)
        permuted_raw, permuted_masked, permuted_value = model(
            candidates[:, permutation],
            scalars,
            present[:, permutation],
            permuted_mask,
        )

    assert torch.allclose(permuted_raw[:, :8], raw[:, :8][:, permutation])
    assert torch.allclose(permuted_raw[:, 8:], raw[:, 8:])
    assert torch.allclose(permuted_value, value)
    assert torch.allclose(permuted_masked[:, :8], masked[:, :8][:, permutation])
    assert torch.equal(
        torch.isfinite(masked), mask
    ) or torch.equal(masked > torch.finfo(masked.dtype).min, mask)


def test_v43_factory_and_checkpoint_schema_fail_closed() -> None:
    v42 = json.loads(V42_CONFIG.read_text(encoding="utf-8"))
    v43 = json.loads(V43_CONFIG.read_text(encoding="utf-8"))
    invalid = dict(v43)
    invalid["model_architecture"] = dict(v43["model_architecture"])
    invalid["model_architecture"]["select_head"] = [128, 64, 1]
    with pytest.raises(ValueError, match="model architecture mismatch"):
        build_selector_model(invalid)
    invalid["model_architecture"] = {"schema": "unknown"}
    with pytest.raises(ValueError, match="unknown model architecture"):
        build_selector_model(invalid)

    with tempfile.TemporaryDirectory() as directory:
        v2 = build_selector_model(v43)
        optimizer = torch.optim.Adam(v2.parameters(), lr=0.0)
        checkpoint = Path(directory) / "v2.pt"
        save_checkpoint(
            checkpoint,
            v2,
            optimizer,
            config_sha256="v43",
            parent_checkpoint="",
            update=1,
            reward_schema="selector_reward_v2",
        )
        with pytest.raises(ValueError, match="checkpoint schema mismatch"):
            load_checkpoint(
                checkpoint,
                build_selector_model(v42),
                reward_schema="selector_reward_v2",
            )
        payload = load_checkpoint(
            checkpoint,
            build_selector_model(v43),
            reward_schema="selector_reward_v2",
        )
        assert payload["model_schema"] == MODEL_SCHEMA_V2
