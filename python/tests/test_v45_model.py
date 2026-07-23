"""Focused ADR-0062 residual-temporal actor checks."""

from __future__ import annotations

import json
from pathlib import Path

import torch

from mindustry_agents.training.model import (
    MODEL_ARCHITECTURE_V4,
    MODEL_SCHEMA_V4,
    SelectorResidualLaggedSetContextActorCritic,
    SelectorSetContextActorCritic,
    build_selector_model,
    expected_model_schema,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/training/m8-selector-v45-residual-lagged-context.json"


def _inputs() -> tuple[torch.Tensor, ...]:
    generator = torch.Generator().manual_seed(7201)
    candidates = torch.rand((2, 8, 37), generator=generator)
    current = torch.rand((2, 56), generator=generator)
    lag = torch.rand((2, 104), generator=generator)
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
    return candidates, current, lag, present, mask


def test_v45_factory_is_exact_deterministic_and_zero_residual() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert expected_model_schema(config) == MODEL_SCHEMA_V4
    assert config["model_architecture"] == MODEL_ARCHITECTURE_V4
    first = build_selector_model(config)
    second = build_selector_model(config)
    assert isinstance(first, SelectorResidualLaggedSetContextActorCritic)
    assert all(
        torch.equal(left, right)
        for left, right in zip(first.state_dict().values(), second.state_dict().values())
    )
    for head in (first.temporal_select_head, first.temporal_special_head):
        assert torch.count_nonzero(head[-1].weight) == 0
        assert torch.count_nonzero(head[-1].bias) == 0


def test_v45_construction_matches_v43_base_and_ignores_lag_exactly() -> None:
    seed = 7202
    v43 = SelectorSetContextActorCritic(seed).eval()
    v45 = SelectorResidualLaggedSetContextActorCritic(seed).eval()
    candidates, current, lag, present, mask = _inputs()

    for name in ("candidate_encoder", "scalar_encoder", "select_head", "special_head", "critic"):
        left = getattr(v43, name).state_dict()
        right = getattr(v45, name).state_dict()
        assert all(torch.equal(left[key], right[key]) for key in left)

    with torch.no_grad():
        base = v43(candidates, current, present, mask)
        temporal = v45(candidates, torch.cat((current, lag), dim=-1), present, mask)
        changed_lag = v45(
            candidates,
            torch.cat((current, 1.0 - lag), dim=-1),
            present,
            mask,
        )
    assert all(torch.equal(left, right) for left, right in zip(base, temporal))
    assert all(torch.equal(left, right) for left, right in zip(temporal, changed_lag))


def test_v45_can_learn_lag_residual_without_unmasking() -> None:
    model = SelectorResidualLaggedSetContextActorCritic(7203).eval()
    candidates, current, lag, present, mask = _inputs()
    with torch.no_grad():
        model.temporal_select_head[-1].weight.fill_(0.5)
        model.temporal_special_head[-1].weight.fill_(0.5)
        first = model(candidates, torch.cat((current, lag), dim=-1), present, mask)
        second = model(
            candidates,
            torch.cat((current, torch.zeros_like(lag)), dim=-1),
            present,
            mask,
        )
    assert not torch.equal(first[0], second[0])
    assert torch.equal(first[1] > torch.finfo(first[1].dtype).min, mask)
    assert torch.equal(first[2], second[2])


def test_v45_requires_exact_scalar_width() -> None:
    model = SelectorResidualLaggedSetContextActorCritic(7204)
    candidates, current, _, present, mask = _inputs()
    try:
        model(candidates, current, present, mask)
    except ValueError as error:
        assert "56 current + 104 lag" in str(error)
    else:
        raise AssertionError("V45 accepted a v1 scalar tensor")
