from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import torch
from torch import Tensor, nn


@dataclass(frozen=True)
class StructuredActionValueConfig:
    state_size: int
    entity_feature_size: int
    global_feature_size: int
    entity_card_feature_size: int
    card_feature_size: int
    tile_feature_size: int
    visible_card_slots: int
    d_model: int = 96
    num_heads: int = 4
    num_layers: int = 2
    hidden_size: int = 192
    identity_residual: bool = True
    recurrent_cell_size: int = 0
    play_hazard_size: int = 0


class PublicStructuredActionValueHead(nn.Module):
    """Action-conditioned set ranker over public structured battle state."""

    card_stat_features: Tensor

    def __init__(
        self,
        config: StructuredActionValueConfig,
        card_stat_features: Tensor,
    ) -> None:
        super().__init__()
        if config.d_model % config.num_heads:
            raise ValueError("structured action-value width must divide by heads")
        if card_stat_features.ndim != 2 or card_stat_features.shape[1] != (
            config.entity_card_feature_size
        ):
            raise ValueError("structured action-value card stat table is invalid")
        if config.recurrent_cell_size < 0 or config.play_hazard_size < 0:
            raise ValueError("structured recurrent feature sizes must be nonnegative")
        self.config = config
        self.register_buffer(
            "card_stat_features",
            card_stat_features.detach().to(dtype=torch.float32).clone(),
        )
        self.identity_embedding = (
            nn.Embedding(
                int(card_stat_features.shape[0]),
                config.d_model,
                padding_idx=0,
            )
            if config.identity_residual
            else None
        )
        self.entity_encoder = nn.Sequential(
            nn.LayerNorm(
                config.entity_feature_size + config.entity_card_feature_size
            ),
            nn.Linear(
                config.entity_feature_size + config.entity_card_feature_size,
                config.d_model,
            ),
            nn.GELU(),
        )
        self.global_encoder = nn.Sequential(
            nn.LayerNorm(
                config.state_size
                + config.global_feature_size
                + config.recurrent_cell_size
                + config.play_hazard_size
            ),
            nn.Linear(
                config.state_size
                + config.global_feature_size
                + config.recurrent_cell_size
                + config.play_hazard_size,
                config.d_model,
            ),
            nn.GELU(),
            nn.Linear(config.d_model, config.d_model),
        )
        self.hand_encoder = nn.Sequential(
            nn.LayerNorm(
                config.visible_card_slots * config.entity_card_feature_size
            ),
            nn.Linear(
                config.visible_card_slots * config.entity_card_feature_size,
                config.d_model,
            ),
            nn.GELU(),
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.num_heads,
            dim_feedforward=4 * config.d_model,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.state_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.num_layers,
            enable_nested_tensor=False,
        )
        self.state_token = nn.Parameter(torch.zeros(1, 1, config.d_model))
        action_size = config.card_feature_size + config.tile_feature_size + 3 + 2
        self.action_encoder = nn.Sequential(
            nn.LayerNorm(action_size),
            nn.Linear(action_size, config.d_model),
            nn.GELU(),
            nn.Linear(config.d_model, config.d_model),
        )
        self.action_attention = nn.MultiheadAttention(
            config.d_model,
            config.num_heads,
            dropout=0.0,
            batch_first=True,
        )
        self.scorer = nn.Sequential(
            nn.Linear(5 * config.d_model, config.hidden_size),
            nn.GELU(),
            nn.Linear(config.hidden_size, 1),
        )

    def forward(
        self,
        state_features: Tensor,
        entity_ids: Tensor,
        entity_features: Tensor,
        entity_mask: Tensor,
        hand_ids: Tensor,
        global_features: Tensor,
        candidate_card_features: Tensor,
        candidate_tile_features: Tensor,
        candidate_kinds: Tensor,
        policy_log_probabilities: Tensor,
        policy_type_log_probabilities: Tensor,
        recurrent_cell: Tensor | None = None,
        previous_play_hazard: Tensor | None = None,
    ) -> Tensor:
        if entity_ids.shape != entity_mask.shape:
            raise ValueError("structured entity IDs and mask do not match")
        if entity_features.shape[:-1] != entity_ids.shape:
            raise ValueError("structured entity features do not match IDs")
        if hand_ids.shape[-1] != self.config.visible_card_slots:
            raise ValueError("structured visible hand width is invalid")
        if candidate_card_features.shape[:-1] != candidate_tile_features.shape[:-1]:
            raise ValueError("structured candidate dimensions do not match")
        if state_features.shape[0] != entity_ids.shape[0]:
            raise ValueError("structured action-value batch dimensions do not match")
        expected_prefix = state_features.shape[:-1]
        recurrent_parts = []
        for name, value, width in (
            ("recurrent cell", recurrent_cell, self.config.recurrent_cell_size),
            (
                "previous play hazard",
                previous_play_hazard,
                self.config.play_hazard_size,
            ),
        ):
            if width == 0:
                if value is not None:
                    raise ValueError(f"structured {name} was not configured")
                continue
            if value is None or value.shape != expected_prefix + (width,):
                raise ValueError(f"structured {name} shape is invalid")
            recurrent_parts.append(value)

        entity_stats = self.card_stat_features[entity_ids.long()]
        entities = self.entity_encoder(
            torch.cat((entity_features, entity_stats), dim=-1)
        )
        if self.identity_embedding is not None:
            entities = entities + self.identity_embedding(entity_ids.long())
        global_context = self.global_encoder(
            torch.cat((state_features, global_features, *recurrent_parts), dim=-1)
        )
        hand_stats = self.card_stat_features[hand_ids.long()].flatten(start_dim=-2)
        global_context = global_context + self.hand_encoder(hand_stats)
        state_token = self.state_token.expand(entity_ids.shape[0], -1, -1)
        tokens = torch.cat((state_token + global_context.unsqueeze(1), entities), dim=1)
        token_mask = torch.cat(
            (
                torch.ones(
                    (entity_mask.shape[0], 1),
                    dtype=torch.bool,
                    device=entity_mask.device,
                ),
                entity_mask.bool(),
            ),
            dim=1,
        )
        encoded = self.state_encoder(tokens, src_key_padding_mask=~token_mask)
        summary = encoded[:, 0]

        kinds = torch.nn.functional.one_hot(
            candidate_kinds.clamp(0, 2).long(),
            num_classes=3,
        ).to(candidate_card_features.dtype)
        policy = torch.stack(
            (
                policy_log_probabilities.clamp(-20.0, 0.0) / 20.0,
                policy_type_log_probabilities.clamp(-20.0, 0.0) / 20.0,
            ),
            dim=-1,
        )
        actions = self.action_encoder(
            torch.cat(
                (
                    candidate_card_features,
                    candidate_tile_features,
                    kinds,
                    policy,
                ),
                dim=-1,
            )
        )
        queries = actions + summary.unsqueeze(1)
        attended, _ = self.action_attention(
            queries,
            encoded,
            encoded,
            key_padding_mask=~token_mask,
            need_weights=False,
        )
        state = summary.unsqueeze(1).expand_as(actions)
        score: Tensor = self.scorer(
            torch.cat(
                (
                    state,
                    actions,
                    attended,
                    actions * attended,
                    state * actions,
                ),
                dim=-1,
            )
        ).squeeze(-1)
        return score


def public_structured_action_value_checkpoint(
    *,
    head: PublicStructuredActionValueHead,
    source_policy: str,
    source_policy_sha256: str,
    corpus_sha256: str,
    minimum_score_gain: float,
) -> dict[str, Any]:
    return {
        "schema": "clasher.public_structured_action_value.v1",
        "config": asdict(head.config),
        "source_policy": source_policy,
        "source_policy_sha256": source_policy_sha256,
        "corpus_sha256": corpus_sha256,
        "minimum_score_gain": float(minimum_score_gain),
        "state_dict": {
            name: value.detach().cpu() for name, value in head.state_dict().items()
        },
    }
