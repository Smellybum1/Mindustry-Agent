"""Pinned feed-forward actor/critic for ``selector_features_v1``."""

from __future__ import annotations

import torch
from torch import nn

MODEL_SCHEMA = "selector_actor_critic_v1"


class SelectorActorCritic(nn.Module):
    """Shared 37->64 candidate encoder, 56->64 context encoder, actor and critic."""

    def __init__(self, seed: int):
        super().__init__()
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.candidate_encoder = nn.Sequential(
                nn.Linear(37, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.scalar_encoder = nn.Sequential(
                nn.Linear(56, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.select_head = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.special_head = nn.Sequential(
                nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            self.critic = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )

    def forward(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        encoded_candidates = self.candidate_encoder(candidates)
        encoded_scalars = self.scalar_encoder(scalars)
        repeated_scalars = encoded_scalars[:, None, :].expand(-1, 8, -1)
        select_logits = self.select_head(
            torch.cat((encoded_candidates, repeated_scalars), dim=-1)
        ).squeeze(-1)
        raw_logits = torch.cat(
            (select_logits, self.special_head(encoded_scalars)), dim=-1
        )
        masked_logits = raw_logits.masked_fill(
            ~action_mask, torch.finfo(raw_logits.dtype).min
        )
        weights = candidate_present.to(encoded_candidates.dtype).unsqueeze(-1)
        pooled = (encoded_candidates * weights).sum(dim=1) / weights.sum(
            dim=1
        ).clamp_min(1.0)
        value = self.critic(
            torch.cat((encoded_scalars, pooled), dim=-1)
        ).squeeze(-1)
        return raw_logits, masked_logits, value


def feature_tensors(features, *, device: str = "cpu") -> tuple[torch.Tensor, ...]:
    """Convert one framework-neutral boundary to a batch of one."""

    return (
        torch.tensor([features.candidates], dtype=torch.float32, device=device),
        torch.tensor([features.scalars], dtype=torch.float32, device=device),
        torch.tensor([features.candidate_present], dtype=torch.bool, device=device),
        torch.tensor([features.action_mask], dtype=torch.bool, device=device),
    )
