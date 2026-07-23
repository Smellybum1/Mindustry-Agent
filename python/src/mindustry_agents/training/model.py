"""Pinned feed-forward actor/critics for ``selector_features_v1``."""

from __future__ import annotations

import torch
from torch import nn

MODEL_SCHEMA_V1 = "selector_actor_critic_v1"
MODEL_SCHEMA_V2 = "selector_actor_critic_v2_set_context"
MODEL_SCHEMA_V3 = "selector_actor_critic_v3_lagged_set_context"
MODEL_SCHEMA_V4 = "selector_actor_critic_v4_residual_lagged_set_context"
MODEL_SCHEMA_V5 = "selector_actor_critic_v5_expert_defer_control"
MODEL_SCHEMA = MODEL_SCHEMA_V1

MODEL_ARCHITECTURE_V1 = {
    "schema": MODEL_SCHEMA_V1,
    "candidate_encoder": [37, 64, 64],
    "scalar_encoder": [56, 64, 64],
    "select_head": [128, 64, 1],
    "special_head": [64, 64, 2],
    "critic": [128, 64, 1],
    "activation": "Tanh",
}
MODEL_ARCHITECTURE_V2 = {
    "schema": MODEL_SCHEMA_V2,
    "candidate_encoder": [37, 64, 64],
    "scalar_encoder": [56, 64, 64],
    "candidate_context": "masked_mean_other_candidates",
    "select_head": [192, 64, 1],
    "special_context": "masked_mean_all_candidates",
    "special_head": [128, 64, 2],
    "critic": [128, 64, 1],
    "activation": "Tanh",
}
MODEL_ARCHITECTURE_V3 = {
    "schema": MODEL_SCHEMA_V3,
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
MODEL_ARCHITECTURE_V4 = {
    "schema": MODEL_SCHEMA_V4,
    "candidate_encoder": [37, 64, 64],
    "current_scalar_encoder": [56, 64, 64],
    "lagged_context_encoder": [104, 64, 64],
    "lagged_context": {
        "previous_scalars": 56,
        "previous_candidate_masked_mean": 37,
        "previous_candidate_count_fraction": 1,
        "previous_action_one_hot": 10,
        "initial_value": "all_zero",
    },
    "candidate_context": "masked_mean_other_candidates",
    "base_select_head": [192, 64, 1],
    "temporal_select_head": [256, 64, 1],
    "base_special_head": [128, 64, 2],
    "temporal_special_head": [192, 64, 2],
    "temporal_output_initialization": "zero_weight_zero_bias",
    "actor_combination": "base_logits_plus_temporal_residual",
    "critic": [128, 64, 1],
    "activation": "Tanh",
}
MODEL_ARCHITECTURE_V5 = {
    "schema": MODEL_SCHEMA_V5,
    "candidate_encoder": [37, 64, 64],
    "current_scalar_encoder": [56, 64, 64],
    "lagged_context_encoder": [104, 64, 64],
    "lagged_context": {
        "previous_scalars": 56,
        "previous_candidate_masked_mean": 37,
        "previous_candidate_count_fraction": 1,
        "previous_action_one_hot": 10,
        "initial_value": "all_zero",
    },
    "expert_action_encoder": [10, 16, 16],
    "candidate_context": "masked_mean_other_candidates",
    "base_select_head": [192, 64, 1],
    "temporal_select_head": [256, 64, 1],
    "base_special_head": [128, 64, 2],
    "temporal_special_head": [192, 64, 2],
    "expert_defer_head": [208, 64, 1],
    "temporal_output_initialization": "zero_weight_zero_bias",
    "expert_defer_output_initialization": "zero_weight_zero_bias",
    "actor_combination": "v45_ordinary_logits_plus_expert_defer_logit",
    "critic": [128, 64, 1],
    "activation": "Tanh",
}


class SelectorActorCritic(nn.Module):
    """Shared 37->64 candidate encoder, 56->64 context encoder, actor and critic."""

    model_schema = MODEL_SCHEMA_V1

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


class SelectorSetContextActorCritic(nn.Module):
    """V2 actor whose logits see the masked set of present candidates."""

    model_schema = MODEL_SCHEMA_V2

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
                nn.Linear(192, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.special_head = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 2)
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
        weights = candidate_present.to(encoded_candidates.dtype).unsqueeze(-1)
        candidate_sum = (encoded_candidates * weights).sum(dim=1)
        candidate_count = weights.sum(dim=1)
        pooled = candidate_sum / candidate_count.clamp_min(1.0)

        other_sum = candidate_sum[:, None, :] - encoded_candidates * weights
        other_count = candidate_count[:, None, :] - weights
        other_pooled = other_sum / other_count.clamp_min(1.0)
        other_pooled = other_pooled * (other_count > 0).to(other_pooled.dtype)

        repeated_scalars = encoded_scalars[:, None, :].expand(-1, 8, -1)
        select_logits = self.select_head(
            torch.cat(
                (encoded_candidates, repeated_scalars, other_pooled), dim=-1
            )
        ).squeeze(-1)
        special_logits = self.special_head(
            torch.cat((encoded_scalars, pooled), dim=-1)
        )
        raw_logits = torch.cat((select_logits, special_logits), dim=-1)
        masked_logits = raw_logits.masked_fill(
            ~action_mask, torch.finfo(raw_logits.dtype).min
        )
        value = self.critic(
            torch.cat((encoded_scalars, pooled), dim=-1)
        ).squeeze(-1)
        return raw_logits, masked_logits, value


class SelectorLaggedSetContextActorCritic(SelectorSetContextActorCritic):
    """V3 set-context actor with an explicit lagged-boundary scalar input."""

    model_schema = MODEL_SCHEMA_V3

    def __init__(self, seed: int):
        nn.Module.__init__(self)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.candidate_encoder = nn.Sequential(
                nn.Linear(37, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.scalar_encoder = nn.Sequential(
                nn.Linear(160, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.select_head = nn.Sequential(
                nn.Linear(192, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.special_head = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            self.critic = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )


class SelectorResidualLaggedSetContextActorCritic(SelectorSetContextActorCritic):
    """V4 actor that adds zero-initialized temporal residual logits to V2."""

    model_schema = MODEL_SCHEMA_V4

    def __init__(self, seed: int):
        nn.Module.__init__(self)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            # Preserve V2 module construction order and initialization exactly.
            self.candidate_encoder = nn.Sequential(
                nn.Linear(37, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.scalar_encoder = nn.Sequential(
                nn.Linear(56, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.select_head = nn.Sequential(
                nn.Linear(192, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.special_head = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            self.critic = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.lagged_context_encoder = nn.Sequential(
                nn.Linear(104, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.temporal_select_head = nn.Sequential(
                nn.Linear(256, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.temporal_special_head = nn.Sequential(
                nn.Linear(192, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            nn.init.zeros_(self.temporal_select_head[-1].weight)
            nn.init.zeros_(self.temporal_select_head[-1].bias)
            nn.init.zeros_(self.temporal_special_head[-1].weight)
            nn.init.zeros_(self.temporal_special_head[-1].bias)

    def forward(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if scalars.shape[-1] != 160:
            raise ValueError("V4 scalar input must contain 56 current + 104 lag values")
        current_scalars = scalars[:, :56]
        lagged_context = scalars[:, 56:]
        encoded_candidates = self.candidate_encoder(candidates)
        encoded_scalars = self.scalar_encoder(current_scalars)
        encoded_lag = self.lagged_context_encoder(lagged_context)
        weights = candidate_present.to(encoded_candidates.dtype).unsqueeze(-1)
        candidate_sum = (encoded_candidates * weights).sum(dim=1)
        candidate_count = weights.sum(dim=1)
        pooled = candidate_sum / candidate_count.clamp_min(1.0)

        other_sum = candidate_sum[:, None, :] - encoded_candidates * weights
        other_count = candidate_count[:, None, :] - weights
        other_pooled = other_sum / other_count.clamp_min(1.0)
        other_pooled = other_pooled * (other_count > 0).to(other_pooled.dtype)

        repeated_scalars = encoded_scalars[:, None, :].expand(-1, 8, -1)
        repeated_lag = encoded_lag[:, None, :].expand(-1, 8, -1)
        base_select = self.select_head(
            torch.cat((encoded_candidates, repeated_scalars, other_pooled), dim=-1)
        ).squeeze(-1)
        temporal_select = self.temporal_select_head(
            torch.cat(
                (
                    encoded_candidates,
                    repeated_scalars,
                    other_pooled,
                    repeated_lag,
                ),
                dim=-1,
            )
        ).squeeze(-1)
        base_special = self.special_head(torch.cat((encoded_scalars, pooled), dim=-1))
        temporal_special = self.temporal_special_head(
            torch.cat((encoded_scalars, pooled, encoded_lag), dim=-1)
        )
        raw_logits = torch.cat(
            (base_select + temporal_select, base_special + temporal_special), dim=-1
        )
        masked_logits = raw_logits.masked_fill(
            ~action_mask, torch.finfo(raw_logits.dtype).min
        )
        value = self.critic(torch.cat((encoded_scalars, pooled), dim=-1)).squeeze(-1)
        return raw_logits, masked_logits, value


class SelectorExpertDeferControlActorCritic(SelectorSetContextActorCritic):
    """V5 V45-exact ordinary actor plus one bounded expert-defer control logit."""

    model_schema = MODEL_SCHEMA_V5

    def __init__(self, seed: int):
        nn.Module.__init__(self)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            # Preserve V4 module construction order and initialization exactly.
            self.candidate_encoder = nn.Sequential(
                nn.Linear(37, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.scalar_encoder = nn.Sequential(
                nn.Linear(56, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.select_head = nn.Sequential(
                nn.Linear(192, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.special_head = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            self.critic = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.lagged_context_encoder = nn.Sequential(
                nn.Linear(104, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.temporal_select_head = nn.Sequential(
                nn.Linear(256, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.temporal_special_head = nn.Sequential(
                nn.Linear(192, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            nn.init.zeros_(self.temporal_select_head[-1].weight)
            nn.init.zeros_(self.temporal_select_head[-1].bias)
            nn.init.zeros_(self.temporal_special_head[-1].weight)
            nn.init.zeros_(self.temporal_special_head[-1].bias)
            self.expert_action_encoder = nn.Sequential(
                nn.Linear(10, 16), nn.Tanh(), nn.Linear(16, 16), nn.Tanh()
            )
            self.expert_defer_head = nn.Sequential(
                nn.Linear(208, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            nn.init.zeros_(self.expert_defer_head[-1].weight)
            nn.init.zeros_(self.expert_defer_head[-1].bias)

    def forward(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if scalars.shape[-1] != 170:
            raise ValueError(
                "V5 scalar input must contain 56 current + 104 lag + "
                "10 expert-action values"
            )
        if action_mask.shape[-1] != 11:
            raise ValueError("V5 action mask must contain 11 control actions")
        ordinary_scalars = scalars[:, :160].contiguous()
        current_scalars = ordinary_scalars[:, :56]
        lagged_context = ordinary_scalars[:, 56:]
        expert_action = scalars[:, 160:]
        encoded_candidates = self.candidate_encoder(candidates)
        encoded_scalars = self.scalar_encoder(current_scalars)
        encoded_lag = self.lagged_context_encoder(lagged_context)
        weights = candidate_present.to(encoded_candidates.dtype).unsqueeze(-1)
        candidate_sum = (encoded_candidates * weights).sum(dim=1)
        candidate_count = weights.sum(dim=1)
        pooled = candidate_sum / candidate_count.clamp_min(1.0)

        other_sum = candidate_sum[:, None, :] - encoded_candidates * weights
        other_count = candidate_count[:, None, :] - weights
        other_pooled = other_sum / other_count.clamp_min(1.0)
        other_pooled = other_pooled * (other_count > 0).to(other_pooled.dtype)

        repeated_scalars = encoded_scalars[:, None, :].expand(-1, 8, -1)
        repeated_lag = encoded_lag[:, None, :].expand(-1, 8, -1)
        base_select = self.select_head(
            torch.cat((encoded_candidates, repeated_scalars, other_pooled), dim=-1)
        ).squeeze(-1)
        temporal_select = self.temporal_select_head(
            torch.cat(
                (
                    encoded_candidates,
                    repeated_scalars,
                    other_pooled,
                    repeated_lag,
                ),
                dim=-1,
            )
        ).squeeze(-1)
        base_special = self.special_head(torch.cat((encoded_scalars, pooled), dim=-1))
        temporal_special = self.temporal_special_head(
            torch.cat((encoded_scalars, pooled, encoded_lag), dim=-1)
        )
        ordinary_logits = torch.cat(
            (base_select + temporal_select, base_special + temporal_special), dim=-1
        )
        ordinary_masked_logits = ordinary_logits.masked_fill(
            ~action_mask[:, :10], torch.finfo(ordinary_logits.dtype).min
        )
        value = self.critic(torch.cat((encoded_scalars, pooled), dim=-1)).squeeze(-1)
        encoded_expert = self.expert_action_encoder(expert_action)
        expert_defer_logit = self.expert_defer_head(
            torch.cat(
                (encoded_scalars, pooled, encoded_lag, encoded_expert), dim=-1
            )
        )
        raw_logits = torch.cat((ordinary_logits, expert_defer_logit), dim=-1)
        masked_logits = torch.cat(
            (
                ordinary_masked_logits,
                expert_defer_logit.masked_fill(
                    ~action_mask[:, 10:],
                    torch.finfo(expert_defer_logit.dtype).min,
                ),
            ),
            dim=-1,
        )
        return raw_logits, masked_logits, value


SelectorModel = (
    SelectorActorCritic
    | SelectorSetContextActorCritic
    | SelectorLaggedSetContextActorCritic
    | SelectorResidualLaggedSetContextActorCritic
    | SelectorExpertDeferControlActorCritic
)


def expected_model_schema(config: dict[str, object]) -> str:
    """Validate a governed architecture declaration and return its schema."""

    architecture = config.get("model_architecture")
    if architecture is None and config.get("schema") == (
        "selector_checkpoint_logit_adjustment_v1"
    ):
        return MODEL_SCHEMA_V1
    if not isinstance(architecture, dict):
        raise ValueError("model_architecture must be an object")
    schema = architecture.get("schema")
    expected = {
        MODEL_SCHEMA_V1: MODEL_ARCHITECTURE_V1,
        MODEL_SCHEMA_V2: MODEL_ARCHITECTURE_V2,
        MODEL_SCHEMA_V3: MODEL_ARCHITECTURE_V3,
        MODEL_SCHEMA_V4: MODEL_ARCHITECTURE_V4,
        MODEL_SCHEMA_V5: MODEL_ARCHITECTURE_V5,
    }.get(schema)
    if expected is None:
        raise ValueError(f"unknown model architecture schema: {schema!r}")
    if architecture != expected:
        raise ValueError(f"model architecture mismatch for {schema}")
    return str(schema)


def build_selector_model(config: dict[str, object]) -> SelectorModel:
    """Construct exactly the model declared by a governed training config."""

    schema = expected_model_schema(config)
    normalizers = config.get("normalizers")
    if isinstance(normalizers, dict):
        feature_schema = normalizers.get("feature_schema")
        required_feature_schema = (
            "selector_features_v2_lagged_boundary"
            if schema in (MODEL_SCHEMA_V3, MODEL_SCHEMA_V4)
            else (
                "selector_features_v3_expert_defer"
                if schema == MODEL_SCHEMA_V5
                else "selector_features_v1"
            )
        )
        if feature_schema != required_feature_schema:
            raise ValueError(
                "model/feature schema mismatch: "
                f"{schema} requires {required_feature_schema!r}"
            )
    seed = int(config["model_init_seed"])
    if schema == MODEL_SCHEMA_V1:
        return SelectorActorCritic(seed)
    if schema == MODEL_SCHEMA_V2:
        return SelectorSetContextActorCritic(seed)
    if schema == MODEL_SCHEMA_V3:
        return SelectorLaggedSetContextActorCritic(seed)
    if schema == MODEL_SCHEMA_V4:
        return SelectorResidualLaggedSetContextActorCritic(seed)
    return SelectorExpertDeferControlActorCritic(seed)


def model_schema(model: nn.Module) -> str:
    """Return a model instance's pinned checkpoint schema, failing closed."""

    schema = getattr(model, "model_schema", None)
    if schema not in (
        MODEL_SCHEMA_V1,
        MODEL_SCHEMA_V2,
        MODEL_SCHEMA_V3,
        MODEL_SCHEMA_V4,
        MODEL_SCHEMA_V5,
    ):
        raise ValueError("selector model has no recognized schema")
    return str(schema)


def feature_tensors(features, *, device: str = "cpu") -> tuple[torch.Tensor, ...]:
    """Convert one framework-neutral boundary to a batch of one."""

    return (
        torch.tensor([features.candidates], dtype=torch.float32, device=device),
        torch.tensor([features.scalars], dtype=torch.float32, device=device),
        torch.tensor([features.candidate_present], dtype=torch.bool, device=device),
        torch.tensor([features.action_mask], dtype=torch.bool, device=device),
    )
