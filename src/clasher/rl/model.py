from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Optional, cast

import numpy as np
import torch
from torch import Tensor, nn
from torch.distributions import Categorical

from .common import NUM_HAND_SLOTS, NUM_TILES
from .structured_obs import (
    ACTOR_GLOBAL_SIZE,
    CRITIC_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    PRIVILEGED_CARD_SLOTS,
    VISIBLE_CARD_SLOTS,
    build_canonical_tile_features,
)


@dataclass(frozen=True)
class PolicyConfig:
    num_tokens: int
    max_entities: int
    entity_feature_size: int = ENTITY_FEATURE_SIZE
    actor_global_size: int = ACTOR_GLOBAL_SIZE
    critic_global_size: int = CRITIC_GLOBAL_SIZE
    d_model: int = 128
    num_heads: int = 4
    actor_layers: int = 4
    critic_layers: int = 2
    memory_size: int = 256
    dropout: float = 0.0

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "PolicyConfig":
        return cls(**payload)


@dataclass
class PolicyInputs:
    entity_ids: Tensor
    entity_features: Tensor
    entity_mask: Tensor
    hand_ids: Tensor
    global_features: Tensor
    action_mask: Tensor
    previous_actions: Tensor
    previous_rewards: Tensor
    episode_starts: Tensor
    critic_entity_ids: Optional[Tensor] = None
    critic_entity_features: Optional[Tensor] = None
    critic_entity_mask: Optional[Tensor] = None
    critic_card_ids: Optional[Tensor] = None
    critic_global_features: Optional[Tensor] = None

    @property
    def batch_size(self) -> int:
        return int(self.entity_ids.shape[0])

    @property
    def sequence_length(self) -> int:
        return int(self.entity_ids.shape[1])


@dataclass
class PolicyOutput:
    joint_logits: Tensor
    values: Tensor
    opponent_hand_logits: Tensor
    opponent_elixir: Tensor
    next_state: tuple[Tensor, Tensor]
    action_type_logits: Tensor
    location_logits: Tensor

    def distribution(self) -> Categorical:
        return Categorical(logits=self.joint_logits)


class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, num_heads: int, dropout: float) -> None:
        super().__init__()
        self.norm_attention = nn.LayerNorm(d_model)
        self.attention = nn.MultiheadAttention(
            d_model,
            num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm_mlp = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 4 * d_model),
            nn.GELU(),
            nn.Linear(4 * d_model, d_model),
            nn.Dropout(dropout),
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, tokens: Tensor, valid_mask: Tensor) -> Tensor:
        normalized = self.norm_attention(tokens)
        attended, _ = self.attention(
            normalized,
            normalized,
            normalized,
            key_padding_mask=~valid_mask,
            need_weights=False,
        )
        tokens = tokens + self.dropout(attended)
        tokens = tokens + self.mlp(self.norm_mlp(tokens))
        return tokens.masked_fill(~valid_mask.unsqueeze(-1), 0.0)


class CrossAttentionBlock(nn.Module):
    def __init__(self, d_model: int, num_heads: int, dropout: float) -> None:
        super().__init__()
        self.query_norm = nn.LayerNorm(d_model)
        self.context_norm = nn.LayerNorm(d_model)
        self.attention = nn.MultiheadAttention(
            d_model,
            num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.mlp_norm = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 2 * d_model),
            nn.GELU(),
            nn.Linear(2 * d_model, d_model),
        )

    def forward(self, queries: Tensor, context: Tensor, context_mask: Tensor) -> Tensor:
        attended, _ = self.attention(
            self.query_norm(queries),
            self.context_norm(context),
            self.context_norm(context),
            key_padding_mask=~context_mask,
            need_weights=False,
        )
        queries = queries + attended
        return cast(Tensor, queries + self.mlp(self.mlp_norm(queries)))


class EntityEncoder(nn.Module):
    def __init__(
        self,
        *,
        num_tokens: int,
        card_stat_features: Tensor,
        entity_feature_size: int,
        global_size: int,
        max_card_slots: int,
        d_model: int,
        num_heads: int,
        layers: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.max_card_slots = max_card_slots
        self.token_embedding = nn.Embedding(num_tokens, d_model, padding_idx=0)
        self.card_stat_features: Tensor
        self.register_buffer("card_stat_features", card_stat_features.clone().float())
        self.card_stat_projection = nn.Sequential(
            nn.Linear(card_stat_features.shape[-1], d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )
        self.entity_projection = nn.Sequential(
            nn.Linear(entity_feature_size, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )
        self.global_projection = nn.Sequential(
            nn.Linear(global_size, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )
        self.slot_embedding = nn.Embedding(max_card_slots, d_model)
        self.kind_embedding = nn.Embedding(3, d_model)
        self.blocks = nn.ModuleList(
            TransformerBlock(d_model, num_heads, dropout) for _ in range(layers)
        )
        self.final_norm = nn.LayerNorm(d_model)

    def _card_tokens(self, ids: Tensor, slot_count: int) -> Tensor:
        stat_features = self.card_stat_features[ids]
        slots = torch.arange(slot_count, device=ids.device).view(1, slot_count)
        return cast(
            Tensor,
            self.token_embedding(ids)
            + self.card_stat_projection(stat_features)
            + self.slot_embedding(slots)
            + self.kind_embedding.weight[1].view(1, 1, -1),
        )

    def forward(
        self,
        entity_ids: Tensor,
        entity_features: Tensor,
        entity_mask: Tensor,
        card_ids: Tensor,
        global_features: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        if card_ids.shape[-1] > self.max_card_slots:
            raise ValueError(
                f"received {card_ids.shape[-1]} card slots, capacity is {self.max_card_slots}"
            )
        global_token = (
            self.global_projection(global_features)
            + self.kind_embedding.weight[0].view(1, -1)
        ).unsqueeze(1)
        card_tokens = self._card_tokens(card_ids, card_ids.shape[-1])
        entity_tokens = (
            self.token_embedding(entity_ids)
            + self.card_stat_projection(self.card_stat_features[entity_ids])
            + self.entity_projection(entity_features)
            + self.kind_embedding.weight[2].view(1, 1, -1)
        )
        tokens = torch.cat([global_token, card_tokens, entity_tokens], dim=1)
        valid_mask = torch.cat(
            [
                torch.ones((entity_ids.shape[0], 1), dtype=torch.bool, device=entity_ids.device),
                card_ids != 0,
                entity_mask,
            ],
            dim=1,
        )
        for block in self.blocks:
            tokens = block(tokens, valid_mask)
        tokens = self.final_norm(tokens)
        global_context = tokens[:, 0]
        card_context = tokens[:, 1 : 1 + card_ids.shape[-1]]
        entity_context = tokens[:, 1 + card_ids.shape[-1] :]
        return global_context, card_context, entity_context, valid_mask


class ClasherPolicy(nn.Module):
    """Recurrent entity-spatial actor with a separate full-state critic."""

    def __init__(
        self,
        config: PolicyConfig,
        card_stat_features: np.ndarray | Tensor,
    ) -> None:
        super().__init__()
        self.config = config
        card_stats = torch.as_tensor(card_stat_features, dtype=torch.float32)
        if card_stats.shape[0] != config.num_tokens:
            raise ValueError("card_stat_features token dimension does not match config")
        d_model = config.d_model
        self.actor_encoder = EntityEncoder(
            num_tokens=config.num_tokens,
            card_stat_features=card_stats,
            entity_feature_size=config.entity_feature_size,
            global_size=config.actor_global_size,
            max_card_slots=VISIBLE_CARD_SLOTS,
            d_model=d_model,
            num_heads=config.num_heads,
            layers=config.actor_layers,
            dropout=config.dropout,
        )
        self.critic_encoder = EntityEncoder(
            num_tokens=config.num_tokens,
            card_stat_features=card_stats,
            entity_feature_size=config.entity_feature_size,
            global_size=config.critic_global_size,
            max_card_slots=PRIVILEGED_CARD_SLOTS,
            d_model=d_model,
            num_heads=config.num_heads,
            layers=config.critic_layers,
            dropout=config.dropout,
        )

        self.action_type_embedding = nn.Embedding(NUM_HAND_SLOTS + 2, 32)
        tile_features = torch.from_numpy(build_canonical_tile_features())
        self.tile_features: Tensor
        self.register_buffer("tile_features", tile_features)
        self.previous_tile_projection = nn.Sequential(
            nn.Linear(tile_features.shape[-1], 32),
            nn.GELU(),
        )
        self.recurrent_input_projection = nn.Sequential(
            nn.Linear(d_model + 65, config.memory_size),
            nn.LayerNorm(config.memory_size),
            nn.GELU(),
        )
        self.memory = nn.LSTMCell(config.memory_size, config.memory_size)

        self.tile_projection = nn.Sequential(
            nn.Linear(tile_features.shape[-1], d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )
        self.memory_tile_film = nn.Linear(config.memory_size, 2 * d_model)
        self.tile_decoder = CrossAttentionBlock(d_model, config.num_heads, config.dropout)
        self.tile_key = nn.Linear(d_model, d_model, bias=False)
        self.card_query = nn.Sequential(
            nn.Linear(d_model + config.memory_size, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model, bias=False),
        )
        self.location_bias = nn.Linear(d_model, 1)
        self.action_type_head = nn.Sequential(
            nn.Linear(d_model + config.memory_size, config.memory_size),
            nn.GELU(),
            nn.Linear(config.memory_size, NUM_HAND_SLOTS + 2),
        )
        self.value_head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, 1),
        )
        self.opponent_hand_head = nn.Linear(config.memory_size, config.num_tokens)
        self.opponent_elixir_head = nn.Sequential(
            nn.Linear(config.memory_size, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    @property
    def num_actions(self) -> int:
        return NUM_HAND_SLOTS * NUM_TILES + 2

    def initial_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
    ) -> tuple[Tensor, Tensor]:
        parameter = next(self.parameters())
        target_device = parameter.device if device is None else torch.device(device)
        shape = (batch_size, self.config.memory_size)
        return (
            torch.zeros(shape, dtype=parameter.dtype, device=target_device),
            torch.zeros(shape, dtype=parameter.dtype, device=target_device),
        )

    def _previous_action_features(self, actions: Tensor, rewards: Tensor) -> Tensor:
        placement = actions < NUM_HAND_SLOTS * NUM_TILES
        action_types = torch.where(
            placement,
            actions // NUM_TILES,
            NUM_HAND_SLOTS + (actions == NUM_HAND_SLOTS * NUM_TILES + 1).long(),
        ).clamp(0, NUM_HAND_SLOTS + 1)
        tile_indices = torch.where(placement, actions % NUM_TILES, torch.zeros_like(actions))
        tile_context = self.previous_tile_projection(self.tile_features[tile_indices])
        tile_context = tile_context * placement.unsqueeze(-1)
        return torch.cat(
            [
                self.action_type_embedding(action_types),
                tile_context,
                rewards.unsqueeze(-1),
            ],
            dim=-1,
        )

    def _run_memory(
        self,
        global_context: Tensor,
        previous_actions: Tensor,
        previous_rewards: Tensor,
        episode_starts: Tensor,
        state: Optional[tuple[Tensor, Tensor]],
    ) -> tuple[Tensor, tuple[Tensor, Tensor]]:
        batch_size, sequence_length, _ = global_context.shape
        hidden, cell = self.initial_state(batch_size, device=global_context.device) if state is None else state
        outputs: list[Tensor] = []
        previous_context = self._previous_action_features(previous_actions, previous_rewards)
        recurrent_inputs = self.recurrent_input_projection(
            torch.cat([global_context, previous_context], dim=-1)
        )
        for index in range(sequence_length):
            keep = (~episode_starts[:, index]).to(global_context.dtype).unsqueeze(-1)
            hidden = hidden * keep
            cell = cell * keep
            hidden, cell = self.memory(recurrent_inputs[:, index], (hidden, cell))
            outputs.append(hidden)
        return torch.stack(outputs, dim=1), (hidden, cell)

    @staticmethod
    def _masked_log_softmax(logits: Tensor, mask: Tensor, dim: int) -> Tensor:
        masked = logits.masked_fill(~mask, -1e9)
        result = torch.log_softmax(masked, dim=dim)
        return result.masked_fill(~mask, -1e9)

    def _joint_action_logits(
        self,
        action_type_logits: Tensor,
        location_logits: Tensor,
        action_mask: Tensor,
    ) -> Tensor:
        placement_mask = action_mask[..., : NUM_HAND_SLOTS * NUM_TILES].reshape(
            *action_mask.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
        )
        slot_mask = placement_mask.any(dim=-1)
        special_mask = action_mask[..., NUM_HAND_SLOTS * NUM_TILES :]
        type_mask = torch.cat([slot_mask, special_mask], dim=-1)
        type_log_prob = self._masked_log_softmax(action_type_logits, type_mask, dim=-1)
        location_log_prob = self._masked_log_softmax(
            location_logits, placement_mask, dim=-1
        )
        placement_log_prob = type_log_prob[..., :NUM_HAND_SLOTS].unsqueeze(-1) + location_log_prob
        return torch.cat(
            [
                placement_log_prob.reshape(*action_mask.shape[:-1], -1),
                type_log_prob[..., NUM_HAND_SLOTS:],
            ],
            dim=-1,
        ).masked_fill(~action_mask, -1e9)

    def forward(
        self,
        inputs: PolicyInputs,
        state: Optional[tuple[Tensor, Tensor]] = None,
    ) -> PolicyOutput:
        batch_size = inputs.batch_size
        sequence_length = inputs.sequence_length
        flat_size = batch_size * sequence_length

        def flatten(value: Tensor) -> Tensor:
            return value.reshape(flat_size, *value.shape[2:])

        actor_global, actor_cards, actor_entities, actor_valid = self.actor_encoder(
            flatten(inputs.entity_ids),
            flatten(inputs.entity_features),
            flatten(inputs.entity_mask),
            flatten(inputs.hand_ids),
            flatten(inputs.global_features),
        )
        actor_tokens = torch.cat(
            [actor_global.unsqueeze(1), actor_cards, actor_entities], dim=1
        )
        actor_global_sequence = actor_global.reshape(batch_size, sequence_length, -1)
        memory, next_state = self._run_memory(
            actor_global_sequence,
            inputs.previous_actions,
            inputs.previous_rewards,
            inputs.episode_starts,
            state,
        )
        flat_memory = memory.reshape(flat_size, -1)

        tile_queries = self.tile_projection(self.tile_features).unsqueeze(0).expand(
            flat_size, -1, -1
        )
        scale, shift = self.memory_tile_film(flat_memory).chunk(2, dim=-1)
        tile_queries = tile_queries * (1.0 + 0.1 * torch.tanh(scale).unsqueeze(1))
        tile_queries = tile_queries + shift.unsqueeze(1)
        tile_context = self.tile_decoder(tile_queries, actor_tokens, actor_valid)

        card_context = actor_cards[:, :NUM_HAND_SLOTS]
        card_memory = flat_memory.unsqueeze(1).expand(-1, NUM_HAND_SLOTS, -1)
        card_queries = self.card_query(torch.cat([card_context, card_memory], dim=-1))
        tile_keys = self.tile_key(tile_context)
        location_logits = torch.einsum("bsd,btd->bst", card_queries, tile_keys) / math.sqrt(
            self.config.d_model
        )
        location_logits = location_logits + self.location_bias(tile_context).transpose(1, 2)
        action_type_logits = self.action_type_head(
            torch.cat([actor_global, flat_memory], dim=-1)
        )

        action_type_logits = action_type_logits.reshape(
            batch_size, sequence_length, NUM_HAND_SLOTS + 2
        )
        location_logits = location_logits.reshape(
            batch_size, sequence_length, NUM_HAND_SLOTS, NUM_TILES
        )
        joint_logits = self._joint_action_logits(
            action_type_logits, location_logits, inputs.action_mask
        )

        if inputs.critic_entity_ids is not None:
            assert inputs.critic_entity_features is not None
            assert inputs.critic_entity_mask is not None
            assert inputs.critic_card_ids is not None
            assert inputs.critic_global_features is not None
            critic_global, _, _, _ = self.critic_encoder(
                flatten(inputs.critic_entity_ids),
                flatten(inputs.critic_entity_features),
                flatten(inputs.critic_entity_mask),
                flatten(inputs.critic_card_ids),
                flatten(inputs.critic_global_features),
            )
            values = self.value_head(critic_global).reshape(batch_size, sequence_length)
        else:
            values = self.value_head(actor_global).reshape(batch_size, sequence_length)

        return PolicyOutput(
            joint_logits=joint_logits,
            values=values,
            opponent_hand_logits=self.opponent_hand_head(memory),
            opponent_elixir=self.opponent_elixir_head(memory).squeeze(-1),
            next_state=next_state,
            action_type_logits=action_type_logits,
            location_logits=location_logits,
        )

    @torch.no_grad()
    def act(
        self,
        inputs: PolicyInputs,
        state: Optional[tuple[Tensor, Tensor]] = None,
        *,
        deterministic: bool = False,
    ) -> tuple[Tensor, Tensor, Tensor, tuple[Tensor, Tensor], PolicyOutput]:
        output = self.forward(inputs, state)
        distribution = output.distribution()
        actions = (
            torch.argmax(output.joint_logits, dim=-1)
            if deterministic
            else distribution.sample()
        )
        return (
            actions,
            distribution.log_prob(actions),
            output.values,
            output.next_state,
            output,
        )


# The public name now points to the new architecture. Legacy modules import
# their explicit baseline from ``legacy_model`` during the remaining migration.
MaskedPolicyValueNet = ClasherPolicy
