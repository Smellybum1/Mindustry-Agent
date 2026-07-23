"""Focused ADR-0063 expert-defer actor checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import torch

from mindustry_agents.training.model import (
    MODEL_ARCHITECTURE_V5,
    MODEL_SCHEMA_V5,
    SelectorExpertDeferControlActorCritic,
    SelectorResidualLaggedSetContextActorCritic,
    build_selector_model,
    expected_model_schema,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/training/m8-selector-v46-expert-defer-control.json"
CONFIG_SHA256 = "b588ee43e66bd9d13a9bee5bacac08251cd4c49c3f8d5726eaf2675f06d5d835"


def _inputs() -> tuple[torch.Tensor, ...]:
    generator = torch.Generator().manual_seed(7301)
    candidates = torch.rand((2, 8, 37), generator=generator)
    current = torch.rand((2, 56), generator=generator)
    lag = torch.rand((2, 104), generator=generator)
    expert = torch.zeros((2, 10))
    expert[0, 0] = 1.0
    expert[1, 8] = 1.0
    present = torch.tensor(
        [
            [True, True, True, False, False, False, False, False],
            [True, False, False, False, False, False, False, False],
        ]
    )
    ordinary_mask = torch.tensor(
        [
            [True, True, False, False, False, False, False, False, True, True],
            [True, False, False, False, False, False, False, False, False, True],
        ]
    )
    control_mask = torch.cat(
        (ordinary_mask, torch.tensor([[True], [False]])), dim=-1
    )
    return candidates, current, lag, expert, present, ordinary_mask, control_mask


def test_v46_config_factory_is_exact_deterministic_and_zero_output() -> None:
    assert hashlib.sha256(CONFIG.read_bytes()).hexdigest() == CONFIG_SHA256
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert expected_model_schema(config) == MODEL_SCHEMA_V5
    assert config["model_architecture"] == MODEL_ARCHITECTURE_V5
    first = build_selector_model(config)
    second = build_selector_model(config)
    assert isinstance(first, SelectorExpertDeferControlActorCritic)
    assert all(
        torch.equal(left, right)
        for left, right in zip(first.state_dict().values(), second.state_dict().values())
    )
    for head in (
        first.temporal_select_head,
        first.temporal_special_head,
        first.expert_defer_head,
    ):
        assert torch.count_nonzero(head[-1].weight) == 0
        assert torch.count_nonzero(head[-1].bias) == 0


def test_v46_construction_and_outputs_preserve_v45_exactly() -> None:
    seed = 7302
    v45 = SelectorResidualLaggedSetContextActorCritic(seed).eval()
    v46 = SelectorExpertDeferControlActorCritic(seed).eval()
    candidates, current, lag, expert, present, ordinary_mask, control_mask = _inputs()

    shared_modules = (
        "candidate_encoder",
        "scalar_encoder",
        "select_head",
        "special_head",
        "critic",
        "lagged_context_encoder",
        "temporal_select_head",
        "temporal_special_head",
    )
    for name in shared_modules:
        left = getattr(v45, name).state_dict()
        right = getattr(v46, name).state_dict()
        assert all(torch.equal(left[key], right[key]) for key in left)

    with torch.no_grad():
        old = v45(
            candidates,
            torch.cat((current, lag), dim=-1),
            present,
            ordinary_mask,
        )
        new = v46(
            candidates,
            torch.cat((current, lag, expert), dim=-1),
            present,
            control_mask,
        )
    assert torch.equal(old[0], new[0][:, :10])
    assert torch.equal(old[1], new[1][:, :10])
    assert torch.equal(old[2], new[2])
    assert torch.equal(new[0][:, 10], torch.zeros(2))
    assert torch.equal(
        new[1] > torch.finfo(new[1].dtype).min,
        control_mask,
    )


def test_v46_expert_path_changes_only_defer_logit() -> None:
    model = SelectorExpertDeferControlActorCritic(7303).eval()
    candidates, current, lag, expert, present, _, control_mask = _inputs()
    scalars = torch.cat((current, lag, expert), dim=-1)
    changed = scalars.clone()
    changed[:, 160:] = torch.roll(changed[:, 160:], shifts=1, dims=-1)
    with torch.no_grad():
        model.expert_defer_head[-1].weight.fill_(0.5)
        first = model(candidates, scalars, present, control_mask)
        second = model(candidates, changed, present, control_mask)
    assert torch.equal(first[0][:, :10], second[0][:, :10])
    assert not torch.equal(first[0][:, 10], second[0][:, 10])
    assert torch.equal(first[2], second[2])
    assert torch.equal(
        first[1] > torch.finfo(first[1].dtype).min,
        control_mask,
    )


def test_v46_requires_exact_scalar_and_control_widths() -> None:
    model = SelectorExpertDeferControlActorCritic(7304)
    candidates, current, lag, expert, present, ordinary_mask, control_mask = _inputs()
    with pytest.raises(ValueError, match="56 current .* 10 expert-action"):
        model(
            candidates,
            torch.cat((current, lag), dim=-1),
            present,
            control_mask,
        )
    with pytest.raises(ValueError, match="11 control actions"):
        model(
            candidates,
            torch.cat((current, lag, expert), dim=-1),
            present,
            ordinary_mask,
        )
