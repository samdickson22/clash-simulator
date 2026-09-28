from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import cast

import numpy as np
import torch
from torch import Tensor, nn
from torch.distributions import Categorical
from torch.nn import functional as F

from .common import NUM_HAND_SLOTS, NUM_TILES
from .joint_action_value import FactorizedActionValueHead
from .structured_memory import StructuredBeliefCell, StructuredPublicStateTracker
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
    card_semantics_version: int = 1
    public_contract_version: int = 1
    public_token_names: tuple[str, ...] = ()
    canonical_lane_globals: bool = False
    public_history_slots: int = 0
    public_seen_card_slots: int = 0
    public_belief_action_context: str = "belief-only"
    public_belief_enemy_y_gate: float = 1.0
    public_observation_confidence: bool = False
    actor_observation_domain: str = "simulator-exact"
    entity_feature_size: int = ENTITY_FEATURE_SIZE
    actor_global_size: int = ACTOR_GLOBAL_SIZE
    critic_global_size: int = CRITIC_GLOBAL_SIZE
    d_model: int = 128
    num_heads: int = 4
    actor_layers: int = 4
    critic_layers: int = 2
    memory_size: int = 256
    structured_clock_horizon_steps: int = 750
    structured_resource_policy_gate_enabled: bool = False
    structured_deterministic_resource_enabled: bool = False
    encoder_kind: str = "attention"
    decoder_kind: str = "attention"
    memory_kind: str = "lstm"
    card_input_mode: str = "hybrid"
    deterministic_hierarchy: str = "slot"
    hierarchical_mode_gate_enabled: bool = False
    play_hazard_enabled: bool = False
    play_hazard_positive_weight: float = 1.0
    play_hazard_base_rate: float = 0.5
    play_hazard_threshold: float = 0.5
    play_hazard_adapter_size: int = 0
    play_hazard_adapter_enemy_y_gate: float = 1.0
    play_hazard_adapter_gain: float = 1.0
    dropout: float = 0.0
    placement_prior_enabled: bool = False
    action_type_adapter_enabled: bool = False
    safe_slot_choice_adapter_enabled: bool = False
    semantic_slot_choice_adapter_enabled: bool = False
    semantic_slot_choice_replace_base: bool = False
    mechanics_slot_choice_adapter_enabled: bool = False
    mechanics_slot_choice_replace_base: bool = False
    mechanics_slot_choice_base_scale: float = 1.0
    actor_current_hand_slot_invariant: bool = False
    equivariant_slot_choice: bool = False
    equivariant_deterministic_timing_pool: str = "log-mass"
    equivariant_timing_query_enabled: bool = False
    robust_action_type_adapter_size: int = 0
    repair_adapter_size: int = 0
    repair_prototype_count: int = 0
    repair_prototype_threshold: float = 0.999
    repair_prototype_feature_size: int = 0
    repair_prototype_frozen_prefix_count: int = 0
    repair_prototype_frozen_prefix_threshold: float = 0.99999
    repair_prototype_guard_count: int = 0
    repair_prototype_guard_threshold: float = 0.99999
    repair_prototype_linear_gate_count: int = 0
    repair_stage_sizes: tuple[int, ...] = ()
    repair_stage_prototype_counts: tuple[int, ...] = ()
    repair_stage_prototype_threshold: float = 0.99999
    repair_stage_prototype_thresholds: tuple[float, ...] = ()
    repair_stage_prototype_guard_counts: tuple[int, ...] = ()
    repair_stage_prototype_guard_thresholds: tuple[float, ...] = ()
    repair_stage_prototype_hard_guards: tuple[bool, ...] = ()
    repair_stage_yield_to_prior: tuple[bool, ...] = ()
    action_value_head_enabled: bool = False

    def __post_init__(self) -> None:
        if self.public_contract_version not in (1, 2, 3):
            raise ValueError("unsupported public observation contract")
        if self.public_contract_version >= 2 and (
            len(self.public_token_names) != self.num_tokens
            or self.public_token_names[:2] != ("<pad>", "<unknown>")
            or len(set(self.public_token_names)) != self.num_tokens
        ):
            raise ValueError("public contract v2 requires its exact token vocabulary")
        if self.actor_observation_domain not in {
            "simulator-exact",
            "causal-vision-v1",
            "causal-frame-v1",
        }:
            raise ValueError(
                "actor_observation_domain must be simulator-exact, "
                "causal-vision-v1, or causal-frame-v1"
            )
        if (
            self.actor_observation_domain in {"causal-vision-v1", "causal-frame-v1"}
            and not self.public_observation_confidence
        ):
            raise ValueError(
                "causal actor domain requires public_observation_confidence"
            )
        if self.memory_kind == "structured" and self.memory_size < 8:
            raise ValueError("structured memory requires memory_size >= 8")
        if (
            self.structured_resource_policy_gate_enabled
            and self.memory_kind != "structured"
        ):
            raise ValueError(
                "structured resource policy gate requires structured memory"
            )
        if self.structured_deterministic_resource_enabled:
            if self.memory_kind != "structured":
                raise ValueError(
                    "structured deterministic resource requires structured memory"
                )
            if self.memory_size < StructuredPublicStateTracker.REQUIRED_STATE_SIZE:
                raise ValueError(
                    "structured deterministic resource requires enough model-owned "
                    "public-state channels"
                )
            if self.card_input_mode == "id-only":
                raise ValueError(
                    "structured deterministic resource requires internal card costs"
                )
            if self.card_semantics_version == 2:
                raise ValueError(
                    "structured deterministic resource requires card semantics with "
                    "an exact cost channel"
                )
            if self.public_history_slots > 0:
                raise ValueError(
                    "structured deterministic public state consumes current-frame "
                    "events, not accumulated public history"
                )
        if self.structured_clock_horizon_steps <= 0:
            raise ValueError("structured clock horizon must be positive")
        if self.play_hazard_enabled:
            if self.memory_kind != "structured":
                raise ValueError("play hazard requires structured memory")
            if not self.hierarchical_mode_gate_enabled:
                raise ValueError("play hazard requires a hierarchical mode gate")
            if self.structured_deterministic_resource_enabled:
                raise ValueError(
                    "play hazard and deterministic resource cannot share hidden state"
                )
            if not math.isfinite(self.play_hazard_positive_weight) or (
                self.play_hazard_positive_weight < 1.0
            ):
                raise ValueError("play hazard positive weight must be finite and >= 1")
            if not 0.0 < self.play_hazard_threshold < 1.0:
                raise ValueError("play hazard threshold must be in (0, 1)")
            if not 0.0 < self.play_hazard_base_rate < 1.0:
                raise ValueError("play hazard base rate must be in (0, 1)")
        if self.play_hazard_adapter_size < 0:
            raise ValueError("play hazard adapter size must be non-negative")
        if self.play_hazard_adapter_size > 0 and not self.play_hazard_enabled:
            raise ValueError("play hazard adapter requires the hazard head")
        if not 0.0 < self.play_hazard_adapter_enemy_y_gate <= 1.0:
            raise ValueError("play hazard adapter enemy-y gate must be in (0, 1]")
        if not math.isfinite(self.play_hazard_adapter_gain) or not (
            0.0 <= self.play_hazard_adapter_gain <= 1.0
        ):
            raise ValueError("play hazard adapter gain must be finite and in [0, 1]")
        if self.play_hazard_adapter_gain != 1.0 and self.play_hazard_adapter_size == 0:
            raise ValueError("play hazard adapter gain requires the adapter")
        if (
            self.play_hazard_adapter_enemy_y_gate < 1.0
            and self.play_hazard_adapter_size == 0
        ):
            raise ValueError("play hazard enemy-y gate requires the adapter")
        if (self.deterministic_hierarchy == "hazard") != self.play_hazard_enabled:
            raise ValueError(
                "hazard deterministic hierarchy and play hazard must be enabled together"
            )
        if self.deterministic_hierarchy == "event":
            if self.memory_kind != "structured":
                raise ValueError("event accumulation requires structured memory")
            if not self.hierarchical_mode_gate_enabled:
                raise ValueError("event accumulation requires a hierarchical mode gate")
            if self.structured_deterministic_resource_enabled:
                raise ValueError(
                    "event accumulation and deterministic resource cannot share hidden state"
                )
            if not 0.0 < self.play_hazard_threshold < 1.0:
                raise ValueError("event accumulation threshold must be in (0, 1)")

    def to_dict(
        self,
    ) -> dict[
        str,
        str | int | float | tuple[int, ...] | tuple[float, ...] | tuple[bool, ...] | tuple[str, ...],
    ]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> PolicyConfig:
        normalized = dict(payload)
        for key in (
            "public_token_names",
            "repair_stage_sizes",
            "repair_stage_prototype_counts",
            "repair_stage_prototype_thresholds",
            "repair_stage_prototype_guard_counts",
            "repair_stage_prototype_guard_thresholds",
            "repair_stage_prototype_hard_guards",
            "repair_stage_yield_to_prior",
        ):
            if key in normalized:
                normalized[key] = tuple(normalized[key])
        return cls(**normalized)


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
    entity_id_confidence: Tensor | None = None
    entity_feature_confidence: Tensor | None = None
    hand_id_confidence: Tensor | None = None
    global_feature_confidence: Tensor | None = None
    critic_entity_ids: Tensor | None = None
    critic_entity_features: Tensor | None = None
    critic_entity_mask: Tensor | None = None
    critic_card_ids: Tensor | None = None
    critic_global_features: Tensor | None = None
    opponent_history_ids: Tensor | None = None
    opponent_history_ages: Tensor | None = None
    opponent_seen_card_ids: Tensor | None = None
    opponent_play_event_ids: Tensor | None = None
    opponent_play_event_confidence: Tensor | None = None
    own_last_play_ids: Tensor | None = None
    own_last_play_features: Tensor | None = None
    entity_levels: Tensor | None = None
    entity_level_confidence: Tensor | None = None

    @property
    def batch_size(self) -> int:
        return int(self.entity_ids.shape[0])

    @property
    def sequence_length(self) -> int:
        return int(self.entity_ids.shape[1])

    def with_exact_actor_confidence(self) -> PolicyInputs:
        """Mark an exact simulator actor observation as completely observed."""

        values = (
            self.entity_id_confidence,
            self.entity_feature_confidence,
            self.hand_id_confidence,
            self.global_feature_confidence,
        )
        if all(value is not None for value in values):
            return self
        if any(value is not None for value in values):
            raise ValueError("actor confidence inputs must be supplied together")
        entity_confidence = self.entity_mask.to(self.entity_features.dtype)
        return replace(
            self,
            entity_id_confidence=entity_confidence,
            entity_feature_confidence=entity_confidence.unsqueeze(-1).expand_as(
                self.entity_features
            ),
            hand_id_confidence=torch.ones_like(
                self.hand_ids,
                dtype=self.global_features.dtype,
            ),
            global_feature_confidence=torch.ones_like(self.global_features),
        )


@dataclass
class PolicyOutput:
    joint_logits: Tensor
    values: Tensor
    opponent_hand_logits: Tensor
    opponent_elixir: Tensor
    next_state: tuple[Tensor, Tensor]
    action_type_logits: Tensor
    location_logits: Tensor
    repair_features: Tensor | None = None
    deterministic_timing_logits: Tensor | None = None
    play_hazard_logits: Tensor | None = None
    hierarchical_mode_logits: Tensor | None = None
    action_values: Tensor | None = None

    def distribution(
        self,
        *,
        temperature: float = 1.0,
        force_play: Tensor | None = None,
    ) -> Categorical:
        if not math.isfinite(temperature) or temperature <= 0.0:
            raise ValueError("policy temperature must be finite and positive")
        if force_play is not None:
            if force_play.shape != self.joint_logits.shape[:-1]:
                raise ValueError("play gate must match policy batch and sequence")
            placement_mask = self.joint_logits[
                ..., : NUM_HAND_SLOTS * NUM_TILES
            ].reshape(
                *self.joint_logits.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
            ) > -1e8
            slot_mask = placement_mask.any(dim=-1)
            special_mask = self.joint_logits[
                ..., NUM_HAND_SLOTS * NUM_TILES :
            ] > -1e8
            timing_logits = (
                self.action_type_logits
                if self.deterministic_timing_logits is None
                else self.deterministic_timing_logits
            )
            slot_log_prob = torch.log_softmax(
                (
                    self.action_type_logits[..., :NUM_HAND_SLOTS] / temperature
                ).masked_fill(~slot_mask, -1e9),
                dim=-1,
            ).masked_fill(~slot_mask, -1e9)
            location_log_prob = torch.log_softmax(
                (self.location_logits / temperature).masked_fill(
                    ~placement_mask, -1e9
                ),
                dim=-1,
            ).masked_fill(~placement_mask, -1e9)
            special_log_prob = torch.log_softmax(
                (timing_logits[..., NUM_HAND_SLOTS:] / temperature).masked_fill(
                    ~special_mask, -1e9
                ),
                dim=-1,
            ).masked_fill(~special_mask, -1e9)
            placement_log_prob = slot_log_prob.unsqueeze(-1) + location_log_prob
            gated_logits = torch.cat(
                [
                    placement_log_prob.reshape(
                        *self.joint_logits.shape[:-1], -1
                    ),
                    special_log_prob,
                ],
                dim=-1,
            )
            gated_mask = torch.where(
                force_play.unsqueeze(-1),
                torch.cat(
                    [
                        placement_mask.reshape(
                            *self.joint_logits.shape[:-1], -1
                        ),
                        torch.zeros_like(special_mask),
                    ],
                    dim=-1,
                ),
                torch.cat(
                    [
                        torch.zeros_like(
                            placement_mask.reshape(
                                *self.joint_logits.shape[:-1], -1
                            )
                        ),
                        special_mask,
                    ],
                    dim=-1,
                ),
            )
            return Categorical(logits=gated_logits.masked_fill(~gated_mask, -1e9))
        if temperature == 1.0:
            return Categorical(logits=self.joint_logits)

        # The joint policy is factorized as mode (play/wait/ability), card slot
        # conditional on play, and tile conditional on the slot.  Cooling the
        # already-flattened logits biases play probability by the number and
        # entropy of legal tiles.  Temper each factor independently instead so
        # temperature 1 preserves the exact historical distribution and the
        # zero-temperature limit agrees with hierarchical deterministic decode.
        placement_mask = self.joint_logits[
            ..., : NUM_HAND_SLOTS * NUM_TILES
        ].reshape(*self.joint_logits.shape[:-1], NUM_HAND_SLOTS, NUM_TILES) > -1e8
        slot_mask = placement_mask.any(dim=-1)
        special_mask = self.joint_logits[
            ..., NUM_HAND_SLOTS * NUM_TILES :
        ] > -1e8
        type_mask = torch.cat([slot_mask, special_mask], dim=-1)
        timing_logits = (
            self.action_type_logits
            if self.deterministic_timing_logits is None
            else self.deterministic_timing_logits
        )
        masked_timing_logits = timing_logits.masked_fill(~type_mask, -1e9)
        play_logit = torch.logsumexp(
            masked_timing_logits[..., :NUM_HAND_SLOTS], dim=-1, keepdim=True
        )
        mode_logits = torch.cat(
            [play_logit, masked_timing_logits[..., NUM_HAND_SLOTS:]], dim=-1
        )
        mode_mask = torch.cat(
            [slot_mask.any(dim=-1, keepdim=True), special_mask], dim=-1
        )
        mode_log_prob = torch.log_softmax(
            (mode_logits / temperature).masked_fill(~mode_mask, -1e9), dim=-1
        ).masked_fill(~mode_mask, -1e9)
        slot_log_prob = torch.log_softmax(
            (
                self.action_type_logits[..., :NUM_HAND_SLOTS] / temperature
            ).masked_fill(~slot_mask, -1e9),
            dim=-1,
        ).masked_fill(~slot_mask, -1e9)
        location_log_prob = torch.log_softmax(
            (self.location_logits / temperature).masked_fill(
                ~placement_mask, -1e9
            ),
            dim=-1,
        ).masked_fill(~placement_mask, -1e9)
        placement_log_prob = (
            mode_log_prob[..., :1].unsqueeze(-1)
            + slot_log_prob.unsqueeze(-1)
            + location_log_prob
        )
        joint_log_prob = torch.cat(
            [
                placement_log_prob.reshape(*self.joint_logits.shape[:-1], -1),
                mode_log_prob[..., 1:],
            ],
            dim=-1,
        )
        joint_mask = torch.cat(
            [
                placement_mask.reshape(*self.joint_logits.shape[:-1], -1),
                special_mask,
            ],
            dim=-1,
        )
        return Categorical(logits=joint_log_prob.masked_fill(~joint_mask, -1e9))

    def entropy_components(
        self,
        *,
        temperature: float = 1.0,
        force_play: Tensor | None = None,
    ) -> tuple[Tensor, Tensor]:
        """Return action-type and conditional-placement entropy separately.

        The two components sum to the entropy of the flattened joint action
        distribution.  Keeping them separate lets training encourage choosing
        among cards/wait/ability without necessarily making placement noisier.
        """
        distribution = self.distribution(
            temperature=temperature, force_play=force_play
        )
        joint_probabilities = distribution.probs
        joint_log_probabilities = distribution.logits
        placement_probabilities = joint_probabilities[
            ..., : NUM_HAND_SLOTS * NUM_TILES
        ].reshape(*joint_probabilities.shape[:-1], NUM_HAND_SLOTS, NUM_TILES)
        slot_probabilities = placement_probabilities.sum(dim=-1)
        special_probabilities = joint_probabilities[..., NUM_HAND_SLOTS * NUM_TILES :]
        type_probabilities = torch.cat(
            [slot_probabilities, special_probabilities], dim=-1
        )
        type_log_probabilities = type_probabilities.clamp_min(
            torch.finfo(type_probabilities.dtype).tiny
        ).log()
        type_entropy = -(type_probabilities * type_log_probabilities).sum(dim=-1)
        joint_entropy = -(joint_probabilities * joint_log_probabilities).sum(dim=-1)
        location_entropy = joint_entropy - type_entropy
        return type_entropy, location_entropy

    def conditional_slot_entropy(
        self,
        *,
        temperature: float = 1.0,
        force_play: Tensor | None = None,
    ) -> Tensor:
        """Return card-slot entropy conditional on choosing a placement action.

        Normalizing away total placement probability makes this independent of
        the play-versus-wait decision. Illegal slots have exactly zero mass via
        the joint action mask; states with fewer than two playable slots return
        zero without producing NaNs.
        """
        joint_probabilities = self.distribution(
            temperature=temperature, force_play=force_play
        ).probs
        placement_probabilities = joint_probabilities[
            ..., : NUM_HAND_SLOTS * NUM_TILES
        ].reshape(*joint_probabilities.shape[:-1], NUM_HAND_SLOTS, NUM_TILES)
        slot_probabilities = placement_probabilities.sum(dim=-1)
        placement_probability = slot_probabilities.sum(dim=-1, keepdim=True)
        safe_probability = placement_probability.clamp_min(
            torch.finfo(slot_probabilities.dtype).tiny
        )
        conditional_probabilities = slot_probabilities / safe_probability
        conditional_log_probabilities = conditional_probabilities.clamp_min(
            torch.finfo(conditional_probabilities.dtype).tiny
        ).log()
        entropy = -(conditional_probabilities * conditional_log_probabilities).sum(
            dim=-1
        )
        return torch.where(
            placement_probability.squeeze(-1) > 0,
            entropy,
            torch.zeros_like(entropy),
        )


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
        card_semantics_version: int,
        encoder_kind: str,
        card_input_mode: str,
        confidence_aware: bool = False,
        current_hand_slot_invariant: bool = False,
        level_aware: bool = False,
    ) -> None:
        super().__init__()
        if encoder_kind not in {"attention", "deepsets"}:
            raise ValueError(f"unknown encoder kind {encoder_kind!r}")
        if card_input_mode not in {
            "hybrid",
            "residual-hybrid",
            "id-only",
            "mechanics-only",
        }:
            raise ValueError(f"unknown card input mode {card_input_mode!r}")
        self.level_projection = nn.Linear(2, d_model, bias=False) if level_aware else None
        self.encoder_kind = encoder_kind
        self.card_input_mode = card_input_mode
        self.confidence_aware = confidence_aware
        self.d_model = d_model
        self.max_card_slots = max_card_slots
        self.current_hand_slot_invariant = current_hand_slot_invariant
        self.token_embedding: nn.Embedding | None = None
        if card_input_mode != "mechanics-only":
            self.token_embedding = nn.Embedding(num_tokens, d_model, padding_idx=0)
        self.card_stat_features: Tensor | None
        self.semantic_card_features: Tensor | None
        if card_input_mode == "id-only":
            self.card_stat_features = None
            self.semantic_card_features = None
        elif card_semantics_version in {3, 4}:
            if card_stat_features.shape[-1] <= 16:
                raise ValueError("semantic-v3/v4 requires base and semantic features")
            self.register_buffer(
                "card_stat_features",
                card_stat_features[:, :16].clone().float(),
            )
            self.register_buffer(
                "semantic_card_features",
                card_stat_features[:, 16:].clone().float(),
            )
        else:
            self.register_buffer(
                "card_stat_features", card_stat_features.clone().float()
            )
            self.semantic_card_features = None
        self.card_stat_projection: nn.Sequential | None = None
        if self.card_stat_features is not None:
            card_stat_output = nn.Linear(d_model, d_model)
            self.card_stat_projection = nn.Sequential(
                nn.Linear(self.card_stat_features.shape[-1], d_model),
                nn.GELU(),
                card_stat_output,
            )
            if card_input_mode == "residual-hybrid":
                nn.init.zeros_(card_stat_output.weight)
                nn.init.zeros_(card_stat_output.bias)
        self.semantic_card_projection: nn.Sequential | None = None
        if self.semantic_card_features is not None:
            semantic_output = nn.Linear(d_model, d_model)
            self.semantic_card_projection = nn.Sequential(
                nn.Linear(self.semantic_card_features.shape[-1], d_model),
                nn.GELU(),
                semantic_output,
            )
            nn.init.zeros_(semantic_output.weight)
            nn.init.zeros_(semantic_output.bias)
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
        self.entity_confidence_projection: nn.Sequential | None = None
        self.global_confidence_projection: nn.Sequential | None = None
        self.card_confidence_projection: nn.Sequential | None = None
        if confidence_aware:
            self.entity_confidence_projection = self._zero_residual_projection(
                entity_feature_size + 1,
                d_model,
            )
            self.global_confidence_projection = self._zero_residual_projection(
                global_size,
                d_model,
            )
            self.card_confidence_projection = self._zero_residual_projection(
                1,
                d_model,
            )
        self.slot_embedding = nn.Embedding(max_card_slots, d_model)
        self.kind_embedding = nn.Embedding(3, d_model)
        self.blocks = nn.ModuleList()
        self.set_pool_projection: nn.Sequential | None = None
        if encoder_kind == "attention":
            self.blocks.extend(
                TransformerBlock(d_model, num_heads, dropout) for _ in range(layers)
            )
        else:
            # A permutation-invariant, no-self-attention baseline. Mean and max
            # pooling preserve population and salient-entity signals without
            # assigning semantic meaning to arbitrary packed row indices.
            self.set_pool_projection = nn.Sequential(
                nn.Linear(4 * d_model, 2 * d_model),
                nn.GELU(),
                nn.Linear(2 * d_model, d_model),
            )
        self.final_norm = nn.LayerNorm(d_model)

    @staticmethod
    def _zero_residual_projection(input_size: int, d_model: int) -> nn.Sequential:
        output = nn.Linear(d_model, d_model)
        nn.init.zeros_(output.weight)
        nn.init.zeros_(output.bias)
        return nn.Sequential(
            nn.Linear(input_size, d_model),
            nn.GELU(),
            output,
        )

    @staticmethod
    def _require_confidence(
        value: Tensor | None,
        *,
        expected_shape: torch.Size,
        name: str,
    ) -> Tensor:
        if value is None:
            raise ValueError(f"confidence-aware encoder requires {name}")
        if value.shape != expected_shape:
            raise ValueError(
                f"{name} shape mismatch: expected {tuple(expected_shape)}, "
                f"got {tuple(value.shape)}"
            )
        if not bool(torch.isfinite(value).all()):
            raise ValueError(f"{name} must be finite")
        if bool(((value < 0.0) | (value > 1.0)).any()):
            raise ValueError(f"{name} must be in [0, 1]")
        return value

    def _card_identity_embedding(self, ids: Tensor) -> Tensor:
        if self.token_embedding is None:
            return torch.zeros((*ids.shape, self.d_model), device=ids.device)
        return cast(Tensor, self.token_embedding(ids))

    def _card_tokens(self, ids: Tensor, slot_count: int) -> Tensor:
        slots = torch.arange(slot_count, device=ids.device).view(1, slot_count)
        slot_embeddings = self.slot_embedding(slots)
        if self.current_hand_slot_invariant:
            if slot_count < NUM_HAND_SLOTS:
                raise ValueError(
                    "current-hand invariant encoder requires four visible slots"
                )
            shared_current_hand = self.slot_embedding.weight[:NUM_HAND_SLOTS].mean(
                dim=0,
                keepdim=True,
            )
            slot_embeddings = torch.cat(
                [
                    shared_current_hand.expand(1, NUM_HAND_SLOTS, -1),
                    slot_embeddings[:, NUM_HAND_SLOTS:],
                ],
                dim=1,
            )
        return cast(
            Tensor,
            self._card_identity_embedding(ids)
            + self._card_stat_embedding(ids)
            + slot_embeddings
            + self.kind_embedding.weight[1].view(1, 1, -1),
        )

    def _card_stat_embedding(self, ids: Tensor) -> Tensor:
        if self.card_stat_projection is None or self.card_stat_features is None:
            return torch.zeros((*ids.shape, self.d_model), device=ids.device)
        result = self.card_stat_projection(self.card_stat_features[ids])
        if self.semantic_card_projection is not None:
            assert self.semantic_card_features is not None
            result = result + self.semantic_card_projection(
                self.semantic_card_features[ids]
            )
        return cast(Tensor, result)

    def forward(
        self,
        entity_ids: Tensor,
        entity_features: Tensor,
        entity_mask: Tensor,
        card_ids: Tensor,
        global_features: Tensor,
        entity_id_confidence: Tensor | None = None,
        entity_feature_confidence: Tensor | None = None,
        card_id_confidence: Tensor | None = None,
        global_feature_confidence: Tensor | None = None,
        entity_level_features: Tensor | None = None,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        if card_ids.shape[-1] > self.max_card_slots:
            raise ValueError(
                f"received {card_ids.shape[-1]} card slots, capacity is "
                f"{self.max_card_slots}"
            )
        global_token = (
            self.global_projection(global_features)
            + self.kind_embedding.weight[0].view(1, -1)
        ).unsqueeze(1)
        card_tokens = self._card_tokens(card_ids, card_ids.shape[-1])
        entity_tokens = (
            self._card_identity_embedding(entity_ids)
            + self._card_stat_embedding(entity_ids)
            + self.entity_projection(entity_features)
            + self.kind_embedding.weight[2].view(1, 1, -1)
        )
        if self.level_projection is not None:
            if entity_level_features is None:
                raise ValueError('level-aware encoder requires public level features')
            entity_tokens = entity_tokens + self.level_projection(entity_level_features)
        elif entity_level_features is not None:
            raise ValueError('legacy encoder cannot consume entity levels')
        if self.confidence_aware:
            entity_id_confidence = self._require_confidence(
                entity_id_confidence,
                expected_shape=entity_ids.shape,
                name="entity_id_confidence",
            )
            entity_feature_confidence = self._require_confidence(
                entity_feature_confidence,
                expected_shape=entity_features.shape,
                name="entity_feature_confidence",
            )
            card_id_confidence = self._require_confidence(
                card_id_confidence,
                expected_shape=card_ids.shape,
                name="card_id_confidence",
            )
            global_feature_confidence = self._require_confidence(
                global_feature_confidence,
                expected_shape=global_features.shape,
                name="global_feature_confidence",
            )
            assert self.entity_confidence_projection is not None
            assert self.global_confidence_projection is not None
            assert self.card_confidence_projection is not None
            entity_uncertainty = 1.0 - torch.cat(
                [
                    entity_id_confidence.unsqueeze(-1),
                    entity_feature_confidence,
                ],
                dim=-1,
            )
            entity_tokens = entity_tokens + self.entity_confidence_projection(
                entity_uncertainty
            ) * entity_uncertainty.amax(dim=-1, keepdim=True)
            global_uncertainty = 1.0 - global_feature_confidence
            global_token = global_token + (
                self.global_confidence_projection(global_uncertainty)
                * global_uncertainty.amax(dim=-1, keepdim=True)
            ).unsqueeze(1)
            card_uncertainty = 1.0 - card_id_confidence.unsqueeze(-1)
            card_tokens = (
                card_tokens
                + self.card_confidence_projection(card_uncertainty) * card_uncertainty
            )
        tokens = torch.cat([global_token, card_tokens, entity_tokens], dim=1)
        valid_mask = torch.cat(
            [
                torch.ones(
                    (entity_ids.shape[0], 1),
                    dtype=torch.bool,
                    device=entity_ids.device,
                ),
                card_ids != 0,
                entity_mask,
            ],
            dim=1,
        )
        if self.encoder_kind == "attention":
            for block in self.blocks:
                tokens = block(tokens, valid_mask)
            tokens = self.final_norm(tokens)
        else:
            assert self.set_pool_projection is not None
            card_mask = card_ids != 0
            card_denominator = card_mask.sum(dim=1, keepdim=True).clamp_min(1)
            card_mean = (card_tokens * card_mask.unsqueeze(-1)).sum(dim=1)
            card_mean = card_mean / card_denominator
            entity_denominator = entity_mask.sum(dim=1, keepdim=True).clamp_min(1)
            entity_mean = (entity_tokens * entity_mask.unsqueeze(-1)).sum(dim=1)
            entity_mean = entity_mean / entity_denominator
            entity_max = entity_tokens.masked_fill(
                ~entity_mask.unsqueeze(-1), -torch.inf
            ).amax(dim=1)
            entity_max = torch.where(
                entity_mask.any(dim=1, keepdim=True),
                entity_max,
                torch.zeros_like(entity_max),
            )
            pooled_global = self.set_pool_projection(
                torch.cat(
                    [global_token.squeeze(1), card_mean, entity_mean, entity_max],
                    dim=-1,
                )
            )
            tokens = torch.cat(
                [pooled_global.unsqueeze(1), card_tokens, entity_tokens], dim=1
            )
            tokens = self.final_norm(tokens)
        global_context = tokens[:, 0]
        card_context = tokens[:, 1 : 1 + card_ids.shape[-1]]
        entity_context = tokens[:, 1 + card_ids.shape[-1] :]
        return global_context, card_context, entity_context, valid_mask


class PrototypeRepairAdapter(nn.Module):
    """Localized residual logits gated by similarity to verified policy states."""

    prototypes: Tensor
    _thresholds: Tensor
    linear_gate_weights: Tensor
    linear_gate_bias: Tensor

    def __init__(
        self,
        input_size: int,
        output_size: int,
        prototype_count: int,
        threshold: float,
        feature_size: int = 0,
        frozen_prefix_count: int = 0,
        frozen_prefix_threshold: float = 0.99999,
        guard_count: int = 0,
        guard_threshold: float = 0.99999,
        linear_gate_count: int = 0,
        hard_guard: bool = False,
    ) -> None:
        super().__init__()
        if prototype_count <= 0:
            raise ValueError("prototype_count must be positive")
        if not 0.0 <= threshold < 1.0:
            raise ValueError("prototype threshold must be in [0, 1)")
        if feature_size < 0 or feature_size > input_size:
            raise ValueError("prototype feature size must be in [0, input_size]")
        if frozen_prefix_count < 0 or frozen_prefix_count > prototype_count:
            raise ValueError("frozen prefix count must be in [0, prototype_count]")
        if not 0.0 <= frozen_prefix_threshold < 1.0:
            raise ValueError("frozen prefix threshold must be in [0, 1)")
        if guard_count < 0 or guard_count > frozen_prefix_count:
            raise ValueError("guard count must be in [0, frozen_prefix_count]")
        if not 0.0 <= guard_threshold < 1.0:
            raise ValueError("guard threshold must be in [0, 1)")
        suffix_count = prototype_count - frozen_prefix_count
        if linear_gate_count < 0 or linear_gate_count > suffix_count:
            raise ValueError("linear gate count must be in [0, suffix_count]")
        self.threshold = threshold
        self.feature_size = feature_size or input_size
        self.frozen_prefix_count = frozen_prefix_count
        self.guard_count = guard_count
        self.linear_gate_count = linear_gate_count
        self.hard_guard = hard_guard
        thresholds = torch.full((prototype_count,), threshold)
        thresholds[:frozen_prefix_count] = frozen_prefix_threshold
        thresholds[:guard_count] = guard_threshold
        self.register_buffer("_thresholds", thresholds, persistent=False)
        self.register_buffer(
            "prototypes",
            torch.zeros(prototype_count, input_size),
        )
        if linear_gate_count:
            self.register_buffer(
                "linear_gate_weights",
                torch.zeros(linear_gate_count, self.feature_size),
            )
            self.register_buffer(
                "linear_gate_bias",
                torch.zeros(linear_gate_count),
            )
        self.deltas = nn.Parameter(torch.zeros(prototype_count, output_size))

    @torch.no_grad()
    def set_prototypes(self, values: Tensor) -> None:
        if values.shape != self.prototypes.shape:
            raise ValueError(
                f"prototype shape mismatch: expected {tuple(self.prototypes.shape)}, "
                f"got {tuple(values.shape)}"
            )
        self.prototypes.copy_(values.to(self.prototypes))

    @torch.no_grad()
    def set_linear_gates(self, weights: Tensor, bias: Tensor) -> None:
        if not self.linear_gate_count:
            raise ValueError("adapter has no linear gates")
        if weights.shape != self.linear_gate_weights.shape:
            raise ValueError("linear gate weight shape mismatch")
        if bias.shape != self.linear_gate_bias.shape:
            raise ValueError("linear gate bias shape mismatch")
        self.linear_gate_weights.copy_(weights.to(self.linear_gate_weights))
        self.linear_gate_bias.copy_(bias.to(self.linear_gate_bias))

    def activation_weights(self, inputs: Tensor) -> Tensor:
        normalized_inputs = F.normalize(inputs[..., : self.feature_size], dim=-1)
        normalized_prototypes = F.normalize(
            self.prototypes[..., : self.feature_size], dim=-1
        )
        squared_distances = (
            (normalized_inputs[:, None, :] - normalized_prototypes[None, :, :])
            .square()
            .sum(dim=-1)
        )
        scaled = 1.0 - squared_distances / (2.0 * (1.0 - self._thresholds))
        weights = scaled.clamp(min=0.0, max=1.0).square()
        if self.guard_count:
            guard_weights = weights[..., : self.guard_count]
            guard_strength = (
                (guard_weights > 0.0).any(dim=-1, keepdim=True).to(weights.dtype)
                if self.hard_guard
                else guard_weights.amax(dim=-1, keepdim=True)
            )
            suffix = weights[..., self.frozen_prefix_count :] * (1.0 - guard_strength)
            weights = torch.cat(
                [weights[..., : self.frozen_prefix_count], suffix], dim=-1
            )
        if self.linear_gate_count:
            gate_inputs = normalized_inputs
            gate_logits = gate_inputs @ self.linear_gate_weights.T
            gate_logits = gate_logits + self.linear_gate_bias
            gates = (gate_logits > 0.0).to(weights.dtype)
            ungated = weights[..., : -self.linear_gate_count]
            gated = weights[..., -self.linear_gate_count :] * gates
            weights = torch.cat([ungated, gated], dim=-1)
        return weights

    def forward(self, inputs: Tensor) -> Tensor:
        return self.activation_weights(inputs) @ self.deltas


class ClasherPolicy(nn.Module):
    """Recurrent entity-spatial actor with a separate full-state critic."""

    def __init__(
        self,
        config: PolicyConfig,
        card_stat_features: np.ndarray | Tensor,
    ) -> None:
        super().__init__()
        self.config = config
        if config.deterministic_hierarchy not in {
            "slot",
            "play-gate",
            "hazard",
            "event",
        }:
            raise ValueError(
                "deterministic hierarchy must be 'slot', 'play-gate', 'hazard', "
                "or 'event'"
            )
        if config.equivariant_slot_choice:
            if not config.actor_current_hand_slot_invariant:
                raise ValueError(
                    "equivariant slot choice requires invariant current-hand tokens"
                )
            if not (
                config.semantic_slot_choice_replace_base
                or config.mechanics_slot_choice_replace_base
            ):
                raise ValueError(
                    "equivariant slot choice requires a replacement card query"
                )
            if config.safe_slot_choice_adapter_enabled:
                raise ValueError(
                    "equivariant slot choice is incompatible with fixed slot deltas"
                )
            if config.robust_action_type_adapter_size > 0:
                raise ValueError(
                    "equivariant slot choice is incompatible with ordered robust inputs"
                )
            if (
                config.repair_adapter_size > 0
                or config.repair_prototype_count > 0
                or config.repair_stage_sizes
            ):
                raise ValueError(
                    "equivariant slot choice is incompatible with dense slot repairs"
                )
            if config.equivariant_deterministic_timing_pool not in {
                "log-mass",
                "max",
            }:
                raise ValueError("unknown equivariant deterministic timing pool")
        elif config.equivariant_deterministic_timing_pool != "log-mass":
            raise ValueError(
                "equivariant deterministic timing pool requires equivariant slot choice"
            )
        if (
            config.equivariant_timing_query_enabled
            and not config.equivariant_slot_choice
        ):
            raise ValueError(
                "equivariant timing query requires equivariant slot choice"
            )
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
            card_semantics_version=config.card_semantics_version,
            encoder_kind=config.encoder_kind,
            card_input_mode=config.card_input_mode,
            confidence_aware=config.public_observation_confidence,
            current_hand_slot_invariant=config.actor_current_hand_slot_invariant,
            level_aware=config.public_contract_version == 3,
        )
        self.own_history_projection = (
            nn.Linear(d_model + 2, d_model)
            if config.public_contract_version >= 2 else None
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
            card_semantics_version=config.card_semantics_version,
            encoder_kind=config.encoder_kind,
            card_input_mode=config.card_input_mode,
            confidence_aware=False,
            current_hand_slot_invariant=False,
        )
        self.public_history_slot_embedding: nn.Embedding | None = None
        self.public_history_age_projection: nn.Sequential | None = None
        self.public_history_projection: nn.Sequential | None = None
        self.public_seen_card_slot_embedding: nn.Embedding | None = None
        self.public_belief_encoder: nn.Sequential | None = None
        self.public_belief_hand_head: nn.Linear | None = None
        self.public_belief_card_query: nn.Linear | None = None
        self.public_belief_timing_head: nn.Linear | None = None
        if config.public_history_slots > 0:
            self.public_history_slot_embedding = nn.Embedding(
                config.public_history_slots,
                d_model,
            )
            self.public_history_age_projection = nn.Sequential(
                nn.Linear(1, d_model),
                nn.GELU(),
            )
            self.public_history_projection = nn.Sequential(
                nn.Linear(d_model, d_model),
                nn.GELU(),
                nn.Linear(d_model, d_model),
            )
            history_output = self.public_history_projection[-1]
            assert isinstance(history_output, nn.Linear)
            nn.init.zeros_(history_output.weight)
            nn.init.zeros_(history_output.bias)
        if config.public_seen_card_slots > 0:
            if config.public_history_slots <= 0:
                raise ValueError("public seen-card memory requires public history")
            if config.public_belief_action_context not in {
                "belief-only",
                "belief-board-add",
                "belief-board-interaction",
            }:
                raise ValueError("unknown public belief action context")
            if not 0.0 < config.public_belief_enemy_y_gate <= 1.0:
                raise ValueError("public belief enemy-y gate must be in (0, 1]")
            self.public_seen_card_slot_embedding = nn.Embedding(
                config.public_seen_card_slots,
                d_model,
            )
            self.public_belief_encoder = nn.Sequential(
                nn.Linear(2 * d_model + 1, 2 * d_model),
                nn.GELU(),
                nn.Linear(2 * d_model, d_model),
                nn.GELU(),
            )
            self.public_belief_hand_head = nn.Linear(d_model, config.num_tokens)
            nn.init.zeros_(self.public_belief_hand_head.weight)
            nn.init.zeros_(self.public_belief_hand_head.bias)
            self.public_belief_card_query = nn.Linear(d_model, d_model)
            self.public_belief_timing_head = nn.Linear(d_model, 2)
            nn.init.zeros_(self.public_belief_card_query.weight)
            nn.init.zeros_(self.public_belief_card_query.bias)
            nn.init.zeros_(self.public_belief_timing_head.weight)
            nn.init.zeros_(self.public_belief_timing_head.bias)

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
        if config.memory_kind == "lstm":
            self.memory: nn.Module = nn.LSTMCell(config.memory_size, config.memory_size)
        elif config.memory_kind == "gru":
            self.memory = nn.GRUCell(config.memory_size, config.memory_size)
        elif config.memory_kind == "structured":
            self.memory = StructuredBeliefCell(
                config.memory_size,
                config.memory_size,
                clock_horizon_steps=config.structured_clock_horizon_steps,
                deterministic_resource=(
                    config.structured_deterministic_resource_enabled
                ),
            )
        elif config.memory_kind == "feedforward":
            self.memory = nn.Identity()
        else:
            raise ValueError(f"unknown memory kind {config.memory_kind!r}")
        self.structured_public_state: StructuredPublicStateTracker | None = None
        if config.structured_deterministic_resource_enabled:
            self.structured_public_state = StructuredPublicStateTracker(
                config.memory_size,
                clock_horizon_steps=config.structured_clock_horizon_steps,
            )

        # A newly trained resource estimator must not immediately perturb a
        # policy that learned while the resource channel was saturated at one.
        # The zero-initialized gate preserves that exact legacy input. A later
        # bounded training phase can gradually expose the internal belief to
        # the policy without changing how the belief itself is updated.
        self.structured_resource_policy_gate: nn.Parameter | None = None
        if config.structured_resource_policy_gate_enabled:
            self.structured_resource_policy_gate = nn.Parameter(torch.zeros(()))

        self.tile_projection = nn.Sequential(
            nn.Linear(tile_features.shape[-1], d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )
        self.memory_tile_film = nn.Linear(config.memory_size, 2 * d_model)
        self.tile_decoder: CrossAttentionBlock | None = None
        self.global_tile_decoder: nn.Sequential | None = None
        if config.decoder_kind == "attention":
            self.tile_decoder = CrossAttentionBlock(
                d_model, config.num_heads, config.dropout
            )
        elif config.decoder_kind == "global":
            self.global_tile_decoder = nn.Sequential(
                nn.LayerNorm(d_model),
                nn.Linear(d_model, 2 * d_model),
                nn.GELU(),
                nn.Linear(2 * d_model, d_model),
            )
        else:
            raise ValueError(f"unknown decoder kind {config.decoder_kind!r}")
        self.tile_key = nn.Linear(d_model, d_model, bias=False)
        self.card_query = nn.Sequential(
            nn.Linear(d_model + config.memory_size, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model, bias=False),
        )
        self.location_bias = nn.Linear(d_model, 1)
        self.placement_prior: nn.Embedding | None = None
        if config.placement_prior_enabled:
            self.placement_prior = nn.Embedding(config.num_tokens, NUM_TILES)
            nn.init.zeros_(self.placement_prior.weight)
        self.action_type_head = nn.Sequential(
            nn.Linear(d_model + config.memory_size, config.memory_size),
            nn.GELU(),
            nn.Linear(config.memory_size, NUM_HAND_SLOTS + 2),
        )
        self.hierarchical_mode_gate: nn.Sequential | None = None
        if config.hierarchical_mode_gate_enabled:
            self.hierarchical_mode_gate = nn.Sequential(
                nn.Linear(d_model + config.memory_size, config.memory_size),
                nn.GELU(),
                nn.Linear(config.memory_size, 3),
            )
        self.play_hazard_head: nn.Sequential | None = None
        self.play_hazard_adapter: nn.Sequential | None = None
        if config.play_hazard_enabled:
            self.play_hazard_head = nn.Sequential(
                nn.Linear(d_model + config.memory_size, config.memory_size),
                nn.GELU(),
                nn.Linear(config.memory_size, 1),
            )
            hazard_output = self.play_hazard_head[-1]
            assert isinstance(hazard_output, nn.Linear)
            nn.init.zeros_(hazard_output.weight)
            nn.init.constant_(
                hazard_output.bias,
                math.log(config.play_hazard_base_rate)
                - math.log1p(-config.play_hazard_base_rate)
                + math.log(config.play_hazard_positive_weight),
            )
            if config.play_hazard_adapter_size > 0:
                self.play_hazard_adapter = nn.Sequential(
                    nn.Linear(
                        d_model + config.memory_size,
                        config.play_hazard_adapter_size,
                    ),
                    nn.GELU(),
                    nn.Linear(config.play_hazard_adapter_size, 1),
                )
                adapter_output = self.play_hazard_adapter[-1]
                assert isinstance(adapter_output, nn.Linear)
                nn.init.zeros_(adapter_output.weight)
                nn.init.zeros_(adapter_output.bias)
        self.equivariant_timing_query: nn.Linear | None = None
        if config.equivariant_timing_query_enabled:
            self.equivariant_timing_query = nn.Linear(
                d_model + config.memory_size,
                3,
            )
            nn.init.zeros_(self.equivariant_timing_query.weight)
            nn.init.zeros_(self.equivariant_timing_query.bias)
        repair_input_size = d_model + config.memory_size
        self.action_value_head: FactorizedActionValueHead | None = None
        self.action_value_policy_gate: nn.Parameter | None = None
        if config.action_value_head_enabled:
            # Optional-module construction must not advance the global RNG and
            # silently change every later shared layer in a same-seed A/B.
            with torch.random.fork_rng(devices=[]):
                self.action_value_head = FactorizedActionValueHead(
                    repair_input_size,
                    d_model,
                )
            # Start as an exact behavior-preserving auxiliary head. PPO may
            # learn to use its centered action advantages only after the
            # return-regression objective has trained useful values.
            self.action_value_policy_gate = nn.Parameter(torch.zeros(()))
        self.action_type_adapter: nn.Linear | None = None
        if config.action_type_adapter_enabled:
            self.action_type_adapter = nn.Linear(
                repair_input_size,
                NUM_HAND_SLOTS + 2,
            )
            nn.init.zeros_(self.action_type_adapter.weight)
            nn.init.zeros_(self.action_type_adapter.bias)
        self.safe_slot_choice_adapter: nn.Linear | None = None
        if config.safe_slot_choice_adapter_enabled:
            self.safe_slot_choice_adapter = nn.Linear(
                repair_input_size,
                NUM_HAND_SLOTS,
            )
            nn.init.zeros_(self.safe_slot_choice_adapter.weight)
            nn.init.zeros_(self.safe_slot_choice_adapter.bias)
        self.semantic_slot_choice_query: nn.Linear | None = None
        if config.semantic_slot_choice_adapter_enabled:
            self.semantic_slot_choice_query = nn.Linear(
                repair_input_size,
                d_model,
                bias=False,
            )
            nn.init.zeros_(self.semantic_slot_choice_query.weight)
        elif config.semantic_slot_choice_replace_base:
            raise ValueError(
                "semantic slot replacement requires the semantic slot adapter"
            )
        self.mechanics_slot_card_stats: Tensor | None
        self.mechanics_slot_choice_query: nn.Linear | None = None
        if config.mechanics_slot_choice_adapter_enabled:
            if (
                not math.isfinite(config.mechanics_slot_choice_base_scale)
                or config.mechanics_slot_choice_base_scale < 0.0
            ):
                raise ValueError(
                    "mechanics slot base scale must be finite and nonnegative"
                )
            if (
                config.mechanics_slot_choice_replace_base
                and config.mechanics_slot_choice_base_scale != 1.0
            ):
                raise ValueError(
                    "mechanics slot replacement cannot also set a base scale"
                )
            if config.card_semantics_version not in {1, 3, 4}:
                raise ValueError(
                    "mechanics slot adapter requires the 16 base card features"
                )
            mechanics_card_stats = card_stats[:, :16].clone().float()
            if mechanics_card_stats.shape[-1] != 16:
                raise ValueError(
                    "mechanics slot adapter requires exactly 16 base card features"
                )
            self.register_buffer(
                "mechanics_slot_card_stats",
                mechanics_card_stats,
            )
            self.mechanics_slot_choice_query = nn.Linear(
                repair_input_size,
                16,
                bias=False,
            )
            nn.init.zeros_(self.mechanics_slot_choice_query.weight)
        else:
            self.mechanics_slot_card_stats = None
            if (
                config.mechanics_slot_choice_replace_base
                or config.mechanics_slot_choice_base_scale != 1.0
            ):
                raise ValueError(
                    "mechanics slot base controls require the mechanics slot adapter"
                )
        self.robust_action_card_stats: Tensor | None
        self.robust_action_type_adapter: nn.Sequential | None = None
        if config.robust_action_type_adapter_size > 0:
            if config.card_semantics_version not in {1, 3, 4}:
                raise ValueError(
                    "robust action adapter requires base public card features"
                )
            robust_card_stats = card_stats[:, :16].clone().float()
            if robust_card_stats.shape[-1] != 16:
                raise ValueError("robust action adapter requires 16 base card features")
            self.register_buffer("robust_action_card_stats", robust_card_stats)
            robust_feature_size = 6 + NUM_HAND_SLOTS * 16 + NUM_HAND_SLOTS + 18 + 6
            self.robust_action_type_adapter = nn.Sequential(
                nn.Linear(robust_feature_size, config.robust_action_type_adapter_size),
                nn.GELU(),
                nn.Linear(
                    config.robust_action_type_adapter_size,
                    NUM_HAND_SLOTS + 2,
                ),
            )
            robust_output = self.robust_action_type_adapter[-1]
            assert isinstance(robust_output, nn.Linear)
            nn.init.zeros_(robust_output.weight)
            nn.init.zeros_(robust_output.bias)
        else:
            self.robust_action_card_stats = None
        repair_output_size = NUM_HAND_SLOTS + 2 + NUM_HAND_SLOTS * NUM_TILES
        self.repair_adapter: nn.Sequential | None = None
        if config.repair_adapter_size > 0:
            self.repair_adapter = nn.Sequential(
                nn.Linear(
                    repair_input_size,
                    config.repair_adapter_size,
                ),
                nn.GELU(),
                nn.Linear(
                    config.repair_adapter_size,
                    repair_output_size,
                ),
            )
            final = self.repair_adapter[-1]
            assert isinstance(final, nn.Linear)
            nn.init.zeros_(final.weight)
            nn.init.zeros_(final.bias)
        self.prototype_repair_adapter: PrototypeRepairAdapter | None = None
        if config.repair_prototype_count > 0:
            self.prototype_repair_adapter = PrototypeRepairAdapter(
                repair_input_size,
                repair_output_size,
                config.repair_prototype_count,
                config.repair_prototype_threshold,
                config.repair_prototype_feature_size,
                config.repair_prototype_frozen_prefix_count,
                config.repair_prototype_frozen_prefix_threshold,
                config.repair_prototype_guard_count,
                config.repair_prototype_guard_threshold,
                config.repair_prototype_linear_gate_count,
            )
        if any(size <= 0 for size in config.repair_stage_sizes):
            raise ValueError("repair stage sizes must be positive")
        if len(config.repair_stage_prototype_counts) > len(config.repair_stage_sizes):
            raise ValueError("repair stage prototype counts exceed stage count")
        if len(config.repair_stage_prototype_thresholds) > len(
            config.repair_stage_sizes
        ):
            raise ValueError("repair stage prototype thresholds exceed stage count")
        if len(config.repair_stage_prototype_guard_counts) > len(
            config.repair_stage_sizes
        ):
            raise ValueError("repair stage guard counts exceed stage count")
        if len(config.repair_stage_prototype_guard_thresholds) > len(
            config.repair_stage_sizes
        ):
            raise ValueError("repair stage guard thresholds exceed stage count")
        if len(config.repair_stage_prototype_hard_guards) > len(
            config.repair_stage_sizes
        ):
            raise ValueError("repair stage hard-guard flags exceed stage count")
        if len(config.repair_stage_yield_to_prior) > len(config.repair_stage_sizes):
            raise ValueError("repair stage priority flags exceed stage count")
        stage_prototype_counts = config.repair_stage_prototype_counts + (0,) * (
            len(config.repair_stage_sizes) - len(config.repair_stage_prototype_counts)
        )
        stage_prototype_thresholds = config.repair_stage_prototype_thresholds + (
            config.repair_stage_prototype_threshold,
        ) * (
            len(config.repair_stage_sizes)
            - len(config.repair_stage_prototype_thresholds)
        )
        stage_guard_counts = config.repair_stage_prototype_guard_counts + (0,) * (
            len(config.repair_stage_sizes)
            - len(config.repair_stage_prototype_guard_counts)
        )
        stage_guard_thresholds = config.repair_stage_prototype_guard_thresholds + (
            config.repair_stage_prototype_threshold,
        ) * (
            len(config.repair_stage_sizes)
            - len(config.repair_stage_prototype_guard_thresholds)
        )
        stage_hard_guards = config.repair_stage_prototype_hard_guards + (False,) * (
            len(config.repair_stage_sizes)
            - len(config.repair_stage_prototype_hard_guards)
        )
        self.repair_stage_yield_to_prior = config.repair_stage_yield_to_prior + (
            False,
        ) * (len(config.repair_stage_sizes) - len(config.repair_stage_yield_to_prior))
        if any(count < 0 for count in stage_prototype_counts):
            raise ValueError("repair stage prototype counts must be non-negative")
        if any(count < 0 for count in stage_guard_counts):
            raise ValueError("repair stage guard counts must be non-negative")
        if any(
            guard_count > prototype_count
            for guard_count, prototype_count in zip(
                stage_guard_counts,
                stage_prototype_counts,
                strict=True,
            )
        ):
            raise ValueError("repair stage guard count exceeds prototype count")
        self.repair_stages = nn.ModuleList()
        self.repair_stage_prototype_adapters = nn.ModuleDict()
        for index, stage_size in enumerate(config.repair_stage_sizes):
            stage = nn.Sequential(
                nn.Linear(repair_input_size, stage_size),
                nn.GELU(),
                nn.Linear(stage_size, repair_output_size),
            )
            stage_final = stage[-1]
            assert isinstance(stage_final, nn.Linear)
            nn.init.zeros_(stage_final.weight)
            nn.init.zeros_(stage_final.bias)
            self.repair_stages.append(stage)
            prototype_count = stage_prototype_counts[index]
            if prototype_count:
                prototype_threshold = stage_prototype_thresholds[index]
                guard_count = stage_guard_counts[index]
                guard_threshold = stage_guard_thresholds[index]
                self.repair_stage_prototype_adapters[str(index)] = (
                    PrototypeRepairAdapter(
                        repair_input_size,
                        repair_output_size,
                        prototype_count,
                        prototype_threshold,
                        frozen_prefix_count=guard_count,
                        frozen_prefix_threshold=guard_threshold,
                        guard_count=guard_count,
                        guard_threshold=guard_threshold,
                        hard_guard=stage_hard_guards[index],
                    )
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
        return int(NUM_HAND_SLOTS * NUM_TILES + 2)

    def initial_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
    ) -> tuple[Tensor, Tensor]:
        parameter = next(self.parameters())
        target_device = parameter.device if device is None else torch.device(device)
        shape = (batch_size, self.config.memory_size)
        hidden = torch.zeros(shape, dtype=parameter.dtype, device=target_device)
        if self.config.memory_kind == "structured":
            assert isinstance(self.memory, StructuredBeliefCell)
            if self.structured_public_state is not None:
                hidden = self.structured_public_state.initial_state(
                    batch_size,
                    dtype=parameter.dtype,
                    device=target_device,
                )
            cell = self.memory.initial_state(
                batch_size,
                dtype=parameter.dtype,
                device=target_device,
            )
        else:
            cell = torch.zeros(shape, dtype=parameter.dtype, device=target_device)
        return hidden, cell

    def _previous_action_features(self, actions: Tensor, rewards: Tensor) -> Tensor:
        placement = actions < NUM_HAND_SLOTS * NUM_TILES
        action_types = torch.where(
            placement,
            actions // NUM_TILES,
            NUM_HAND_SLOTS + (actions == NUM_HAND_SLOTS * NUM_TILES + 1).long(),
        ).clamp(0, NUM_HAND_SLOTS + 1)
        tile_indices = torch.where(
            placement, actions % NUM_TILES, torch.zeros_like(actions)
        )
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

    def _structured_resource_regen(
        self,
        previous_clock: Tensor,
        current_clock: Tensor,
        episode_start: Tensor,
    ) -> Tensor:
        """Integrate exact normalized elixir regeneration between public clocks."""

        start_seconds = previous_clock * 300.0
        end_seconds = torch.maximum(current_clock, previous_clock) * 300.0

        def duration(lower: float, upper: float) -> Tensor:
            lower_tensor = torch.full_like(start_seconds, lower)
            upper_tensor = torch.full_like(start_seconds, upper)
            return (
                torch.minimum(end_seconds, upper_tensor)
                - torch.maximum(start_seconds, lower_tensor)
            ).clamp_min(0.0)

        single = duration(0.0, 120.0) / 2.8
        double = duration(120.0, 240.0) / 1.4
        triple = duration(240.0, 600.0) / 0.93
        normalized = ((single + double + triple) / 10.0).unsqueeze(-1)
        return normalized.masked_fill(episode_start.unsqueeze(-1), 0.0)

    def _run_memory(
        self,
        global_context: Tensor,
        previous_actions: Tensor,
        previous_rewards: Tensor,
        episode_starts: Tensor,
        state: tuple[Tensor, Tensor] | None,
        opponent_play_event_ids: Tensor | None = None,
        opponent_play_event_confidence: Tensor | None = None,
        public_clock_observations: Tensor | None = None,
        public_clock_confidence: Tensor | None = None,
    ) -> tuple[Tensor, tuple[Tensor, Tensor]]:
        batch_size, sequence_length, _ = global_context.shape
        if self.config.structured_deterministic_resource_enabled:
            if (
                opponent_play_event_ids is None
                or opponent_play_event_confidence is None
                or public_clock_observations is None
                or public_clock_confidence is None
            ):
                raise ValueError(
                    "structured deterministic resource requires current-frame public "
                    "event and clock observations"
                )
            expected_prefix = (batch_size, sequence_length)
            for name, value in (
                ("opponent play event IDs", opponent_play_event_ids),
                ("opponent play event confidence", opponent_play_event_confidence),
                ("public clock observations", public_clock_observations),
                ("public clock confidence", public_clock_confidence),
            ):
                if value.shape != expected_prefix:
                    raise ValueError(f"{name} shape does not match resource tracker")
        hidden, cell = (
            self.initial_state(batch_size, device=global_context.device)
            if state is None
            else state
        )
        outputs: list[Tensor] = []
        previous_context = self._previous_action_features(
            previous_actions, previous_rewards
        )
        recurrent_inputs = self.recurrent_input_projection(
            torch.cat([global_context, previous_context], dim=-1)
        )
        if self.config.memory_kind == "feedforward":
            # This ablation is deliberately stateless across decisions. It
            # retains the current public board plus the immediately preceding
            # own action/reward, but cannot silently reconstruct a longer
            # history in learned recurrent state.
            next_hidden = recurrent_inputs[:, -1]
            return recurrent_inputs, (next_hidden, torch.zeros_like(next_hidden))
        reset_hidden, reset_cell = self.initial_state(
            batch_size,
            device=global_context.device,
        )
        for index in range(sequence_length):
            keep = (~episode_starts[:, index]).to(global_context.dtype).unsqueeze(-1)
            hidden = hidden * keep + reset_hidden * (1.0 - keep)
            cell = cell * keep + reset_cell * (1.0 - keep)
            if self.config.memory_kind == "lstm":
                assert isinstance(self.memory, nn.LSTMCell)
                hidden, cell = self.memory(recurrent_inputs[:, index], (hidden, cell))
            elif self.config.memory_kind == "gru":
                assert isinstance(self.memory, nn.GRUCell)
                hidden = self.memory(recurrent_inputs[:, index], hidden)
                cell = torch.zeros_like(hidden)
            else:
                assert isinstance(self.memory, StructuredBeliefCell)
                if self.config.structured_deterministic_resource_enabled:
                    assert opponent_play_event_ids is not None
                    assert opponent_play_event_confidence is not None
                    assert public_clock_observations is not None
                    assert public_clock_confidence is not None
                    assert self.structured_public_state is not None
                    step_starts = episode_starts[:, index]
                    step_event_ids = torch.where(
                        step_starts,
                        torch.zeros_like(opponent_play_event_ids[:, index]),
                        opponent_play_event_ids[:, index],
                    )
                    step_event_confidence = torch.where(
                        step_starts,
                        torch.zeros_like(opponent_play_event_confidence[:, index]),
                        opponent_play_event_confidence[:, index],
                    )
                    hidden, new_event, previous_clock, current_clock = (
                        self.structured_public_state(
                            hidden,
                            step_event_ids,
                            step_event_confidence,
                            public_clock_observations[:, index],
                            public_clock_confidence[:, index],
                        )
                    )
                    current_id = step_event_ids
                    assert self.actor_encoder.card_stat_features is not None
                    costs = self.actor_encoder.card_stat_features[
                        current_id.clamp(0, self.config.num_tokens - 1), 0
                    ].unsqueeze(-1)
                    observed_spend = costs * new_event.unsqueeze(-1)
                    regen = self._structured_resource_regen(
                        previous_clock,
                        current_clock,
                        episode_starts[:, index],
                    )
                    cell = self.memory(
                        recurrent_inputs[:, index],
                        cell,
                        observed_spend,
                        regen,
                    )
                    output = cell
                else:
                    previous_hazard = hidden[:, -1:].clone()
                    cell = self.memory(recurrent_inputs[:, index], cell)
                    if self.config.play_hazard_enabled or (
                        self.config.deterministic_hierarchy == "event"
                    ):
                        hidden = torch.cat([cell[:, :-1], previous_hazard], dim=-1)
                        output = cell
                    else:
                        hidden = cell
                        output = hidden
            outputs.append(
                output if self.config.memory_kind == "structured" else hidden
            )
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
        placement_log_prob = (
            type_log_prob[..., :NUM_HAND_SLOTS].unsqueeze(-1) + location_log_prob
        )
        return torch.cat(
            [
                placement_log_prob.reshape(*action_mask.shape[:-1], -1),
                type_log_prob[..., NUM_HAND_SLOTS:],
            ],
            dim=-1,
        ).masked_fill(~action_mask, -1e9)

    def _mechanics_slot_choice_scores(
        self,
        repair_features: Tensor,
        hand_ids: Tensor,
    ) -> Tensor:
        """Score hand slots using only frozen public card mechanics."""

        if (
            self.mechanics_slot_choice_query is None
            or self.mechanics_slot_card_stats is None
        ):
            raise RuntimeError("mechanics slot-choice adapter is disabled")
        if hand_ids.shape[-1] != NUM_HAND_SLOTS:
            raise ValueError("mechanics slot scoring requires four hand slots")
        mechanics_query = self.mechanics_slot_choice_query(repair_features)
        mechanics_cards = self.mechanics_slot_card_stats[hand_ids]
        return torch.einsum(
            "bd,bsd->bs",
            mechanics_query,
            mechanics_cards,
        ) / math.sqrt(mechanics_cards.shape[-1])

    def _deterministic_actions(
        self,
        output: PolicyOutput,
        action_mask: Tensor,
        *,
        force_play: Tensor | None = None,
    ) -> Tensor:
        """Choose a legal action hierarchically without location-count bias."""
        placement_mask = action_mask[..., : NUM_HAND_SLOTS * NUM_TILES].reshape(
            *action_mask.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
        )
        slot_mask = placement_mask.any(dim=-1)
        special_mask = action_mask[..., NUM_HAND_SLOTS * NUM_TILES :]
        type_mask = torch.cat([slot_mask, special_mask], dim=-1)
        masked_type_logits = output.action_type_logits.masked_fill(~type_mask, -1e9)
        timing_logits = getattr(output, "deterministic_timing_logits", None)
        if timing_logits is None:
            timing_logits = output.action_type_logits
        masked_timing_logits = timing_logits.masked_fill(~type_mask, -1e9)
        timing_action_types = masked_timing_logits.argmax(dim=-1)
        best_slot = masked_type_logits[..., :NUM_HAND_SLOTS].argmax(dim=-1)
        action_types = torch.where(
            timing_action_types < NUM_HAND_SLOTS,
            best_slot,
            timing_action_types,
        )

        if self.config.deterministic_hierarchy == "play-gate":
            # Aggregate the mutually exclusive hand-slot probabilities before
            # comparing play against wait/ability. This preserves the exact
            # stochastic joint distribution; it changes only deterministic
            # decoding, avoiding a four-way probability-splitting bias against
            # playing any card.
            if output.deterministic_timing_logits is None:
                play_logit = torch.logsumexp(
                    masked_timing_logits[..., :NUM_HAND_SLOTS], dim=-1
                )
            else:
                # A hierarchical/equivariant timing head has already reduced
                # the mutually exclusive slots to one play-mode logit and
                # broadcasts it back across legal slots for the shared output
                # contract. Summing those copies again adds an artificial
                # log(number of legal slots) bonus and can force continuous
                # play. Max recovers the single pre-aggregated mode value.
                play_logit = masked_timing_logits[
                    ..., :NUM_HAND_SLOTS
                ].amax(dim=-1)
            top_level_logits = torch.stack(
                [
                    play_logit,
                    masked_timing_logits[..., NUM_HAND_SLOTS],
                    masked_timing_logits[..., NUM_HAND_SLOTS + 1],
                ],
                dim=-1,
            )
            top_level = top_level_logits.argmax(dim=-1)
            action_types = torch.where(
                top_level == 0,
                best_slot,
                NUM_HAND_SLOTS + top_level - 1,
            )
        elif self.config.deterministic_hierarchy in {"hazard", "event"}:
            if force_play is None or force_play.shape != action_types.shape:
                raise ValueError("event hierarchy requires a shaped force-play gate")
            can_play = slot_mask.any(dim=-1)
            play_now = force_play & can_play
            special_types = (
                masked_timing_logits[..., NUM_HAND_SLOTS:].argmax(dim=-1)
                + NUM_HAND_SLOTS
            )
            action_types = torch.where(play_now, best_slot, special_types)

        best_tiles = output.location_logits.masked_fill(~placement_mask, -1e9).argmax(
            dim=-1
        )
        selected_slots = action_types.clamp(max=NUM_HAND_SLOTS - 1)
        selected_tiles = best_tiles.gather(
            dim=-1, index=selected_slots.unsqueeze(-1)
        ).squeeze(-1)
        placement_actions = action_types * NUM_TILES + selected_tiles
        special_actions = NUM_HAND_SLOTS * NUM_TILES + (action_types - NUM_HAND_SLOTS)
        return torch.where(
            action_types < NUM_HAND_SLOTS,
            placement_actions,
            special_actions,
        )

    def _play_hazard_force_gate(
        self,
        output: PolicyOutput,
        action_mask: Tensor,
        initial_hazard: Tensor,
    ) -> tuple[Tensor, Tensor]:
        """Integrate calibrated event hazard and return forced-play decisions."""

        if output.play_hazard_logits is None:
            raise RuntimeError("play-hazard head did not emit logits")
        if output.play_hazard_logits.shape != action_mask.shape[:2]:
            raise ValueError("play-hazard logits do not match action sequence")
        if initial_hazard.shape != (action_mask.shape[0],):
            raise ValueError("initial play hazard does not match batch")
        probabilities = torch.sigmoid(
            output.play_hazard_logits
            - math.log(self.config.play_hazard_positive_weight)
        )
        can_play = action_mask[..., : NUM_HAND_SLOTS * NUM_TILES].any(dim=-1)
        accumulator = initial_hazard
        gates: list[Tensor] = []
        for index in range(action_mask.shape[1]):
            probability = probabilities[:, index]
            accumulator = 1.0 - (1.0 - accumulator) * (1.0 - probability)
            play_now = (
                accumulator >= self.config.play_hazard_threshold
            ) & can_play[:, index]
            gates.append(play_now)
            accumulator = torch.where(
                play_now,
                torch.zeros_like(accumulator),
                accumulator,
            )
        return torch.stack(gates, dim=1), accumulator

    def _event_mode_force_gate(
        self,
        output: PolicyOutput,
        action_mask: Tensor,
        initial_hazard: Tensor,
    ) -> tuple[Tensor, Tensor]:
        """Accumulate the factorized play-mode probability in model state."""

        if output.hierarchical_mode_logits is None:
            raise ValueError("event hierarchy did not expose raw mode logits")
        if output.hierarchical_mode_logits.shape != (*action_mask.shape[:2], 3):
            raise ValueError("event-mode logits do not match action sequence")
        if initial_hazard.shape != (action_mask.shape[0],):
            raise ValueError("initial event accumulator does not match batch")
        if bool(action_mask[..., NUM_HAND_SLOTS * NUM_TILES + 1].any()):
            raise ValueError("event accumulation does not yet support abilities")
        placement_mask = action_mask[..., : NUM_HAND_SLOTS * NUM_TILES].reshape(
            *action_mask.shape[:2], NUM_HAND_SLOTS, NUM_TILES
        )
        slot_mask = placement_mask.any(dim=-1)
        probabilities = torch.softmax(
            output.hierarchical_mode_logits[..., :2], dim=-1
        )[..., 0]
        can_play = slot_mask.any(dim=-1)
        accumulator = initial_hazard
        gates: list[Tensor] = []
        for index in range(action_mask.shape[1]):
            probability = probabilities[:, index]
            accumulator = 1.0 - (1.0 - accumulator) * (1.0 - probability)
            play_now = (
                accumulator >= self.config.play_hazard_threshold
            ) & can_play[:, index]
            gates.append(play_now)
            accumulator = torch.where(
                play_now,
                torch.zeros_like(accumulator),
                accumulator,
            )
        return torch.stack(gates, dim=1), accumulator

    def _robust_action_features(self, inputs: PolicyInputs) -> Tensor:
        """Return domain-stable public features for high-level card timing.

        The visual replay importer cannot recover exact HP, facing, attack
        clocks, or status effects. This summary therefore uses only official
        hand-card mechanics, public time/elixir, coarse troop geometry, and
        the immediately previous action type.
        """

        if self.robust_action_card_stats is None:
            raise RuntimeError("robust action features require registered card stats")
        flat_size = inputs.batch_size * inputs.sequence_length
        hand_ids = inputs.hand_ids.reshape(flat_size, -1)[:, :NUM_HAND_SLOTS]
        hand_stats = self.robust_action_card_stats[hand_ids].reshape(flat_size, -1)
        hand_known = (hand_ids != 0).to(dtype=hand_stats.dtype)
        globals_stable = inputs.global_features.reshape(flat_size, -1)[:, :6]

        entity_features = inputs.entity_features.reshape(
            flat_size, inputs.entity_features.shape[-2], -1
        )
        entity_ids = inputs.entity_ids.reshape(flat_size, -1)
        entity_card_stats = self.robust_action_card_stats[entity_ids]
        valid = inputs.entity_mask.reshape(flat_size, -1)
        own_troop = (
            valid & (entity_features[..., 2] > 0.5) & (entity_features[..., 4] > 0.5)
        )
        enemy_troop = (
            valid & (entity_features[..., 3] > 0.5) & (entity_features[..., 4] > 0.5)
        )
        non_tower_building = (
            (entity_features[..., 5] > 0.5)
            & (entity_card_stats[..., 2] > 0.5)
            & (entity_card_stats[..., 0] > 0.0)
        )
        own_building = valid & (entity_features[..., 2] > 0.5) & non_tower_building
        enemy_building = valid & (entity_features[..., 3] > 0.5) & non_tower_building
        x = entity_features[..., 0]
        y = entity_features[..., 1]
        left = x < 0.5

        def count(mask: Tensor, scale: float) -> Tensor:
            return mask.sum(dim=-1, dtype=entity_features.dtype) / scale

        def mean(value: Tensor, mask: Tensor) -> Tensor:
            weights = mask.to(dtype=entity_features.dtype)
            total = (value * weights).sum(dim=-1)
            denominator = weights.sum(dim=-1)
            return torch.where(
                denominator > 0,
                total / denominator.clamp_min(1.0),
                torch.full_like(total, 0.5),
            )

        def front(value: Tensor, mask: Tensor, *, enemy: bool) -> Tensor:
            fill = 1.0 if enemy else 0.0
            selected = value.masked_fill(~mask, fill)
            extreme = selected.amin(dim=-1) if enemy else selected.amax(dim=-1)
            return torch.where(mask.any(dim=-1), extreme, torch.full_like(extreme, 0.5))

        entity_summary = torch.stack(
            [
                count(own_troop, 8.0),
                count(enemy_troop, 8.0),
                count(own_building, 4.0),
                count(enemy_building, 4.0),
                count(own_troop & left, 4.0),
                count(own_troop & ~left, 4.0),
                count(enemy_troop & left, 4.0),
                count(enemy_troop & ~left, 4.0),
                count(enemy_troop & (y < 0.5), 4.0),
                count(own_troop & (y > 0.5), 4.0),
                mean(x, own_troop),
                mean(y, own_troop),
                mean(x, enemy_troop),
                mean(y, enemy_troop),
                front(y, own_troop & left, enemy=False),
                front(y, own_troop & ~left, enemy=False),
                front(y, enemy_troop & left, enemy=True),
                front(y, enemy_troop & ~left, enemy=True),
            ],
            dim=-1,
        )
        previous_actions = inputs.previous_actions.reshape(flat_size)
        previous_types = torch.where(
            previous_actions < NUM_HAND_SLOTS * NUM_TILES,
            torch.div(previous_actions, NUM_TILES, rounding_mode="floor"),
            NUM_HAND_SLOTS + previous_actions - NUM_HAND_SLOTS * NUM_TILES,
        ).clamp(0, NUM_HAND_SLOTS + 1)
        previous_one_hot = F.one_hot(previous_types, num_classes=NUM_HAND_SLOTS + 2).to(
            dtype=hand_stats.dtype
        )
        return torch.cat(
            [
                globals_stable,
                hand_stats,
                hand_known,
                entity_summary,
                previous_one_hot,
            ],
            dim=-1,
        )

    def _encode_public_history(
        self,
        history_ids: Tensor,
        history_ages: Tensor,
    ) -> Tensor:
        """Encode recent public opponent plays without using hidden state."""
        if self.config.public_history_slots <= 0:
            raise ValueError("policy has no public-history encoder")
        if history_ids.shape != history_ages.shape:
            raise ValueError("opponent history IDs and ages must have equal shapes")
        if history_ids.shape[-1] != self.config.public_history_slots:
            raise ValueError("opponent history slot count does not match config")
        assert self.public_history_slot_embedding is not None
        assert self.public_history_age_projection is not None
        history_valid = history_ids != 0
        history_slots = torch.arange(
            self.config.public_history_slots,
            device=history_ids.device,
        ).view(1, -1)
        history_tokens = (
            self.actor_encoder._card_identity_embedding(history_ids)
            + self.actor_encoder._card_stat_embedding(history_ids)
            + self.public_history_slot_embedding(history_slots)
            + self.public_history_age_projection(history_ages.unsqueeze(-1))
        )
        history_tokens = history_tokens * history_valid.unsqueeze(-1)
        history_summary = history_tokens.sum(dim=1)
        result: Tensor = history_summary / history_valid.sum(
            dim=1,
            keepdim=True,
        ).clamp_min(1)
        return result

    def encode_public_belief(
        self,
        history_ids: Tensor,
        history_ages: Tensor,
        seen_ids: Tensor,
    ) -> Tensor:
        """Encode the public recent-cycle and persistent discovered-deck state.

        This method is intentionally independent of the recurrent policy state so
        the belief path can be pretrained from leakage-free public replay traces.
        """
        if self.config.public_seen_card_slots <= 0:
            raise ValueError("policy has no persistent seen-card encoder")
        if seen_ids.shape[-1] != self.config.public_seen_card_slots:
            raise ValueError("opponent seen-card slot count does not match config")
        assert self.public_seen_card_slot_embedding is not None
        assert self.public_belief_encoder is not None
        history_summary = self._encode_public_history(history_ids, history_ages)
        seen_valid = seen_ids != 0
        seen_slots = torch.arange(
            self.config.public_seen_card_slots,
            device=seen_ids.device,
        ).view(1, -1)
        seen_tokens = (
            self.actor_encoder._card_identity_embedding(seen_ids)
            + self.actor_encoder._card_stat_embedding(seen_ids)
            + self.public_seen_card_slot_embedding(seen_slots)
        )
        seen_tokens = seen_tokens * seen_valid.unsqueeze(-1)
        seen_summary = seen_tokens.sum(dim=1)
        seen_summary = seen_summary / seen_valid.sum(
            dim=1,
            keepdim=True,
        ).clamp_min(1)
        seen_fraction = seen_valid.to(history_summary.dtype).mean(
            dim=1,
            keepdim=True,
        )
        result: Tensor = self.public_belief_encoder(
            torch.cat([history_summary, seen_summary, seen_fraction], dim=-1)
        )
        return result

    def forward(
        self,
        inputs: PolicyInputs,
        state: tuple[Tensor, Tensor] | None = None,
    ) -> PolicyOutput:
        batch_size = inputs.batch_size
        sequence_length = inputs.sequence_length
        flat_size = batch_size * sequence_length

        def flatten(value: Tensor) -> Tensor:
            return value.reshape(flat_size, *value.shape[2:])

        if self.config.public_contract_version >= 2:
            confidence_inputs = (
                inputs.entity_id_confidence, inputs.entity_feature_confidence,
                inputs.hand_id_confidence, inputs.global_feature_confidence,
            )
            present = [value is not None for value in confidence_inputs]
            if any(present) != all(present) or all(present) != self.config.public_observation_confidence:
                raise ValueError("public confidence inputs do not match the model contract")
        actor_global_features = inputs.global_features
        actor_global_confidence = inputs.global_feature_confidence
        if self.config.memory_kind == "structured":
            # The structured cell owns its match clock. Do not let exact or
            # OCR-derived progress/double/triple/overtime scalars bypass it.
            actor_global_features = torch.cat(
                [
                    torch.zeros_like(actor_global_features[..., :5]),
                    actor_global_features[..., 5:],
                ],
                dim=-1,
            )
            if actor_global_confidence is not None:
                actor_global_confidence = torch.cat(
                    [
                        torch.zeros_like(actor_global_confidence[..., :5]),
                        actor_global_confidence[..., 5:],
                    ],
                    dim=-1,
                )

        level_features = None
        if self.config.public_contract_version == 3:
            levels, confidence = inputs.entity_levels, inputs.entity_level_confidence
            if levels is None or confidence is None:
                raise ValueError('public contract v3 requires entity levels and confidence')
            if levels.dtype != torch.long or not confidence.is_floating_point() or levels.shape != inputs.entity_ids.shape or confidence.shape != levels.shape:
                raise ValueError('invalid public entity level shape or dtype')
            if (not torch.isfinite(confidence).all() or torch.any((confidence < 0) | (confidence > 1))
                or torch.any((levels < 0) | (levels > 127))
                or torch.any((levels == 0) != (confidence == 0))
                or torch.any((~inputs.entity_mask) & ((levels != 0) | (confidence != 0)))):
                raise ValueError('invalid public entity levels or confidence')
            level_features = torch.stack([levels.to(inputs.entity_features.dtype) / 16, confidence], dim=-1)
        elif inputs.entity_levels is not None or inputs.entity_level_confidence is not None:
            raise ValueError('entity levels require public contract v3')

        actor_global, actor_cards, actor_entities, actor_valid = self.actor_encoder(
            flatten(inputs.entity_ids),
            flatten(inputs.entity_features),
            flatten(inputs.entity_mask),
            flatten(inputs.hand_ids),
            flatten(actor_global_features),
            None
            if inputs.entity_id_confidence is None
            else flatten(inputs.entity_id_confidence),
            None
            if inputs.entity_feature_confidence is None
            else flatten(inputs.entity_feature_confidence),
            None
            if inputs.hand_id_confidence is None
            else flatten(inputs.hand_id_confidence),
            None
            if actor_global_confidence is None
            else flatten(actor_global_confidence),
            None if level_features is None else flatten(level_features),
        )
        if self.config.public_contract_version >= 2:
            if inputs.own_last_play_ids is None or inputs.own_last_play_features is None:
                raise ValueError("public contract v2 requires own accepted-play history")
            ids = flatten(inputs.own_last_play_ids)
            features = flatten(inputs.own_last_play_features)
            if ids.dtype != torch.long or ids.shape != (flat_size,) or features.shape != (flat_size, 2):
                raise ValueError("invalid own accepted-play history shape")
            known = features[:, 0]
            if (
                not torch.isfinite(features).all()
                or torch.any((features < 0) | (features > 1))
                or torch.any((known != 0) & (known != 1))
                or torch.any((ids >= 2) != (known == 1))
                or torch.any(ids == 1)
                or torch.any((known == 0) & (features[:, 1] != 0))
                or torch.any((ids < 0) | (ids >= self.config.num_tokens))
            ):
                raise ValueError("invalid own accepted-play history values")
            identity = self.actor_encoder._card_identity_embedding(ids)
            semantics = self.actor_encoder._card_stat_embedding(ids)
            history = (identity + semantics) * known.unsqueeze(-1)
            assert self.own_history_projection is not None
            actor_global = actor_global + self.own_history_projection(
                torch.cat([history, features], dim=-1)
            )
        elif inputs.own_last_play_ids is not None or inputs.own_last_play_features is not None:
            raise ValueError("own accepted-play history requires public contract v2")
        public_belief: Tensor | None = None
        if self.config.public_history_slots > 0:
            if (
                inputs.opponent_history_ids is None
                or inputs.opponent_history_ages is None
            ):
                raise ValueError(
                    "public-history model requires opponent history inputs"
                )
            assert self.public_history_projection is not None
            history_ids = flatten(inputs.opponent_history_ids)
            history_ages = flatten(inputs.opponent_history_ages)
            if history_ids.shape[-1] != self.config.public_history_slots:
                raise ValueError("opponent history slot count does not match config")
            if self.config.public_seen_card_slots > 0:
                if inputs.opponent_seen_card_ids is None:
                    raise ValueError(
                        "public seen-card model requires opponent seen-card inputs"
                    )
                seen_ids = flatten(inputs.opponent_seen_card_ids)
                public_belief = self.encode_public_belief(
                    history_ids,
                    history_ages,
                    seen_ids,
                )
                history_summary = public_belief
            else:
                history_summary = self._encode_public_history(
                    history_ids,
                    history_ages,
                )
            actor_global = actor_global + self.public_history_projection(
                history_summary
            )
        actor_tokens = torch.cat(
            [actor_global.unsqueeze(1), actor_cards, actor_entities], dim=1
        )
        actor_global_sequence = actor_global.reshape(batch_size, sequence_length, -1)
        actor_previous_rewards = inputs.previous_rewards
        if self.config.actor_observation_domain in {
            "causal-vision-v1",
            "causal-frame-v1",
        }:
            # Reward shaping is learner supervision, not a camera signal.
            # Enforce the deployment contract at the model boundary so eval,
            # viewers, and third-party controllers cannot accidentally leak it.
            actor_previous_rewards = torch.zeros_like(actor_previous_rewards)
        memory, next_state = self._run_memory(
            actor_global_sequence,
            inputs.previous_actions,
            actor_previous_rewards,
            inputs.episode_starts,
            state,
            inputs.opponent_play_event_ids,
            inputs.opponent_play_event_confidence,
            inputs.global_features[..., 0],
            (
                torch.ones_like(inputs.global_features[..., 0])
                if inputs.global_feature_confidence is None
                else inputs.global_feature_confidence[..., 0]
            ),
        )
        policy_memory = memory
        if self.structured_resource_policy_gate is not None:
            resource = memory[
                ...,
                StructuredBeliefCell.OPPONENT_ELIXIR_INDEX : StructuredBeliefCell.OPPONENT_ELIXIR_INDEX
                + 1,
            ]
            gate = torch.tanh(self.structured_resource_policy_gate)
            gated_resource = torch.ones_like(resource) + gate * (resource - 1.0)
            policy_memory = torch.cat(
                [
                    memory[..., : StructuredBeliefCell.OPPONENT_ELIXIR_INDEX],
                    gated_resource,
                    memory[..., StructuredBeliefCell.OPPONENT_ELIXIR_INDEX + 1 :],
                ],
                dim=-1,
            )
        flat_memory = policy_memory.reshape(flat_size, -1)

        tile_queries = (
            self.tile_projection(self.tile_features)
            .unsqueeze(0)
            .expand(flat_size, -1, -1)
        )
        scale, shift = self.memory_tile_film(flat_memory).chunk(2, dim=-1)
        tile_queries = tile_queries * (1.0 + 0.1 * torch.tanh(scale).unsqueeze(1))
        tile_queries = tile_queries + shift.unsqueeze(1)
        if self.tile_decoder is not None:
            tile_context = self.tile_decoder(tile_queries, actor_tokens, actor_valid)
        else:
            assert self.global_tile_decoder is not None
            tile_context = tile_queries + actor_global.unsqueeze(1)
            tile_context = tile_context + self.global_tile_decoder(tile_context)

        card_context = actor_cards[:, :NUM_HAND_SLOTS]
        card_memory = flat_memory.unsqueeze(1).expand(-1, NUM_HAND_SLOTS, -1)
        card_queries = self.card_query(torch.cat([card_context, card_memory], dim=-1))
        tile_keys = self.tile_key(tile_context)
        location_logits = torch.einsum(
            "bsd,btd->bst", card_queries, tile_keys
        ) / math.sqrt(self.config.d_model)
        location_logits = location_logits + self.location_bias(tile_context).transpose(
            1, 2
        )
        if self.placement_prior is not None:
            location_logits = location_logits + self.placement_prior(
                flatten(inputs.hand_ids)[:, :NUM_HAND_SLOTS]
            )
        action_type_logits = self.action_type_head(
            torch.cat([actor_global, flat_memory], dim=-1)
        )

        action_type_logits = action_type_logits.reshape(
            batch_size, sequence_length, NUM_HAND_SLOTS + 2
        )
        if public_belief is not None:
            assert self.public_belief_card_query is not None
            assert self.public_belief_timing_head is not None
            belief_action_context = public_belief
            if self.config.public_belief_action_context == "belief-board-add":
                belief_action_context = public_belief + actor_global
            elif self.config.public_belief_action_context == "belief-board-interaction":
                belief_action_context = torch.tanh(
                    public_belief + actor_global + public_belief * actor_global
                )
            belief_query = self.public_belief_card_query(belief_action_context)
            belief_card_logits = torch.einsum(
                "bd,bsd->bs",
                belief_query,
                card_context,
            ) / math.sqrt(self.config.d_model)
            belief_timing_logits = self.public_belief_timing_head(belief_action_context)
            belief_action_logits = torch.cat(
                [belief_card_logits, belief_timing_logits],
                dim=-1,
            ).reshape(batch_size, sequence_length, NUM_HAND_SLOTS + 2)
            if self.config.public_belief_enemy_y_gate < 1.0:
                entity_features = flatten(inputs.entity_features)
                entity_valid = flatten(inputs.entity_mask)
                enemy_near_towers = (
                    entity_valid
                    & (entity_features[..., 3] > 0.5)
                    & (entity_features[..., 1] < self.config.public_belief_enemy_y_gate)
                )
                tactical_gate = enemy_near_towers.any(dim=-1).reshape(
                    batch_size,
                    sequence_length,
                    1,
                )
                belief_action_logits = belief_action_logits * tactical_gate
            action_type_logits = action_type_logits + belief_action_logits
        location_logits = location_logits.reshape(
            batch_size, sequence_length, NUM_HAND_SLOTS, NUM_TILES
        )
        repair_features = torch.cat([actor_global, flat_memory], dim=-1)
        if self.action_type_adapter is not None:
            action_type_logits = action_type_logits + self.action_type_adapter(
                repair_features
            ).reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS + 2,
            )
        if self.robust_action_type_adapter is not None:
            action_type_logits = action_type_logits + self.robust_action_type_adapter(
                self._robust_action_features(inputs)
            ).reshape(batch_size, sequence_length, NUM_HAND_SLOTS + 2)
        repair_delta: Tensor | None = None
        if self.repair_adapter is not None:
            repair_delta = self.repair_adapter(repair_features)
        if self.prototype_repair_adapter is not None:
            prototype_weights = self.prototype_repair_adapter.activation_weights(
                repair_features
            )
            prototype_delta = self.prototype_repair_adapter(repair_features)
            if repair_delta is not None:
                repair_delta = repair_delta * (
                    1.0 - prototype_weights.amax(dim=-1, keepdim=True)
                )
            repair_delta = (
                prototype_delta
                if repair_delta is None
                else repair_delta + prototype_delta
            )
        prior_stage_activation: Tensor | None = None
        for index, stage in enumerate(self.repair_stages):
            stage_delta = stage(repair_features)
            stage_key = str(index)
            stage_activation: Tensor | None = None
            if stage_key in self.repair_stage_prototype_adapters:
                stage_prototypes = cast(
                    PrototypeRepairAdapter,
                    self.repair_stage_prototype_adapters[stage_key],
                )
                stage_weights = stage_prototypes.activation_weights(repair_features)
                stage_activation = stage_weights.amax(dim=-1, keepdim=True)
                stage_delta = stage_delta * (1.0 - stage_activation)
                stage_delta = stage_delta + stage_prototypes(repair_features)
            if (
                self.repair_stage_yield_to_prior[index]
                and prior_stage_activation is not None
            ):
                stage_delta = stage_delta * (1.0 - prior_stage_activation)
                if stage_activation is not None:
                    stage_activation = stage_activation * (1.0 - prior_stage_activation)
            repair_delta = (
                stage_delta if repair_delta is None else repair_delta + stage_delta
            )
            if stage_activation is not None:
                prior_stage_activation = (
                    stage_activation
                    if prior_stage_activation is None
                    else torch.maximum(prior_stage_activation, stage_activation)
                )
        if repair_delta is not None:
            action_type_delta = repair_delta[:, : NUM_HAND_SLOTS + 2].reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS + 2,
            )
            location_delta = repair_delta[:, NUM_HAND_SLOTS + 2 :].reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS,
                NUM_TILES,
            )
            action_type_logits = action_type_logits + action_type_delta
            location_logits = location_logits + location_delta
        deterministic_timing_logits: Tensor | None = None
        equivariant_timing_logits: Tensor | None = None
        if self.equivariant_timing_query is not None:
            equivariant_timing_logits = self.equivariant_timing_query(
                repair_features
            ).reshape(batch_size, sequence_length, 3)
        slot_delta: Tensor | None = None
        if self.safe_slot_choice_adapter is not None:
            slot_delta = self.safe_slot_choice_adapter(repair_features).reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS,
            )
        if self.semantic_slot_choice_query is not None:
            hand_ids = flatten(inputs.hand_ids)[:, :NUM_HAND_SLOTS]
            semantic_cards = self.actor_encoder._card_identity_embedding(hand_ids)
            semantic_cards = semantic_cards + self.actor_encoder._card_stat_embedding(
                hand_ids
            )
            semantic_query = self.semantic_slot_choice_query(repair_features)
            semantic_delta = torch.einsum(
                "bd,bsd->bs",
                semantic_query,
                semantic_cards,
            ) / math.sqrt(self.config.d_model)
            semantic_delta = semantic_delta.reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS,
            )
            slot_delta = (
                semantic_delta if slot_delta is None else slot_delta + semantic_delta
            )
        if self.mechanics_slot_choice_query is not None:
            hand_ids = flatten(inputs.hand_ids)[:, :NUM_HAND_SLOTS]
            mechanics_delta = self._mechanics_slot_choice_scores(
                repair_features,
                hand_ids,
            ).reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS,
            )
            slot_delta = (
                mechanics_delta if slot_delta is None else slot_delta + mechanics_delta
            )
        if slot_delta is not None:
            deterministic_timing_logits = action_type_logits
            base_slots = action_type_logits[..., :NUM_HAND_SLOTS]
            base_slot_scale = (
                self.config.mechanics_slot_choice_base_scale
                if self.mechanics_slot_choice_query is not None
                else 1.0
            )
            raw_slots = (
                slot_delta
                if (
                    self.config.semantic_slot_choice_replace_base
                    or self.config.mechanics_slot_choice_replace_base
                )
                else base_slot_scale * base_slots + slot_delta
            )
            placement_mask = inputs.action_mask[
                ..., : NUM_HAND_SLOTS * NUM_TILES
            ].reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS,
                NUM_TILES,
            )
            legal_slots = placement_mask.any(dim=-1)
            any_legal_slot = legal_slots.any(dim=-1, keepdim=True)
            masked_raw = raw_slots.masked_fill(~legal_slots, -torch.inf)
            if self.config.equivariant_slot_choice:
                legal_count = legal_slots.sum(dim=-1, keepdim=True).clamp_min(1)
                aggregate_play_logit = (
                    torch.logsumexp(base_slots, dim=-1, keepdim=True)
                    - math.log(NUM_HAND_SLOTS)
                    + torch.log(legal_count.to(base_slots.dtype))
                )
                special_logits = action_type_logits[..., NUM_HAND_SLOTS:]
                if equivariant_timing_logits is not None:
                    aggregate_play_logit = equivariant_timing_logits[..., :1]
                    special_logits = equivariant_timing_logits[..., 1:]
                normalized_slots = raw_slots - torch.logsumexp(
                    masked_raw,
                    dim=-1,
                    keepdim=True,
                )
                adjusted_slots = torch.where(
                    any_legal_slot,
                    normalized_slots + aggregate_play_logit,
                    raw_slots,
                )
                deterministic_play_logit = aggregate_play_logit
                if self.config.equivariant_deterministic_timing_pool == "max":
                    # The legacy deterministic decoder compares the strongest
                    # physical slot logit against wait/ability. Max-pooling all
                    # four inherited slot outputs preserves that scale while
                    # remaining invariant to which legal card occupies a slot.
                    # Stochastic play mass still uses the exact log-sum-exp
                    # aggregate above.
                    deterministic_play_logit = base_slots.amax(
                        dim=-1,
                        keepdim=True,
                    )
                deterministic_timing_logits = torch.cat(
                    [
                        deterministic_play_logit.expand_as(base_slots),
                        special_logits,
                    ],
                    dim=-1,
                )
            else:
                masked_base = base_slots.masked_fill(~legal_slots, -torch.inf)
                legal_log_mass_shift = torch.where(
                    any_legal_slot,
                    torch.logsumexp(masked_raw, dim=-1, keepdim=True)
                    - torch.logsumexp(masked_base, dim=-1, keepdim=True),
                    torch.zeros_like(base_slots[..., :1]),
                )
                adjusted_slots = raw_slots - legal_log_mass_shift
            action_type_logits = torch.cat(
                [
                    adjusted_slots,
                    (
                        equivariant_timing_logits[..., 1:]
                        if equivariant_timing_logits is not None
                        else action_type_logits[..., NUM_HAND_SLOTS:]
                    ),
                ],
                dim=-1,
            )
        hierarchical_mode_logits: Tensor | None = None
        if self.hierarchical_mode_gate is not None:
            hierarchical_mode_logits = self.hierarchical_mode_gate(
                repair_features
            ).reshape(
                batch_size,
                sequence_length,
                3,
            )
            placement_mask = inputs.action_mask[
                ..., : NUM_HAND_SLOTS * NUM_TILES
            ].reshape(
                batch_size,
                sequence_length,
                NUM_HAND_SLOTS,
                NUM_TILES,
            )
            legal_slots = placement_mask.any(dim=-1)
            special_mask = inputs.action_mask[..., NUM_HAND_SLOTS * NUM_TILES :]
            mode_mask = torch.cat(
                [legal_slots.any(dim=-1, keepdim=True), special_mask], dim=-1
            )
            mode_log_prob = self._masked_log_softmax(
                hierarchical_mode_logits,
                mode_mask,
                dim=-1,
            )
            slot_log_prob = self._masked_log_softmax(
                action_type_logits[..., :NUM_HAND_SLOTS],
                legal_slots,
                dim=-1,
            )
            action_type_logits = torch.cat(
                [
                    slot_log_prob + mode_log_prob[..., :1],
                    mode_log_prob[..., 1:],
                ],
                dim=-1,
            )
            deterministic_timing_logits = torch.cat(
                [
                    mode_log_prob[..., :1].expand_as(slot_log_prob),
                    mode_log_prob[..., 1:],
                ],
                dim=-1,
            )
        joint_logits = self._joint_action_logits(
            action_type_logits, location_logits, inputs.action_mask
        )
        action_values: Tensor | None = None
        if self.action_value_head is not None:
            flat_action_mask = flatten(inputs.action_mask)
            flat_action_values = self.action_value_head(
                repair_features,
                card_context,
                tile_context,
                flat_action_mask,
            )
            action_values = flat_action_values.reshape(
                batch_size,
                sequence_length,
                -1,
            )
            assert self.action_value_policy_gate is not None
            legal_values = torch.where(
                inputs.action_mask,
                action_values,
                torch.zeros_like(action_values),
            )
            legal_count = inputs.action_mask.sum(dim=-1, keepdim=True).clamp_min(1)
            centered_values = action_values - (
                legal_values.sum(dim=-1, keepdim=True)
                / legal_count.to(action_values.dtype)
            )
            policy_value_delta = torch.where(
                inputs.action_mask,
                centered_values,
                torch.zeros_like(centered_values),
            )
            joint_logits = joint_logits + torch.tanh(
                self.action_value_policy_gate
            ) * policy_value_delta

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

        opponent_hand_logits = self.opponent_hand_head(policy_memory)
        if public_belief is not None:
            assert self.public_belief_hand_head is not None
            opponent_hand_logits = opponent_hand_logits + self.public_belief_hand_head(
                public_belief
            ).reshape(batch_size, sequence_length, -1)

        if self.config.memory_kind == "structured":
            # Supervise the actual persistent accumulator rather than a
            # separate readout that could learn to ignore it.  The privileged
            # target is used only by the training loss; inference still updates
            # this channel solely from the current causal frame and prior
            # model-owned state.
            opponent_elixir = memory[..., StructuredBeliefCell.OPPONENT_ELIXIR_INDEX]
        else:
            opponent_elixir = self.opponent_elixir_head(memory).squeeze(-1)

        play_hazard_logits = (
            None
            if self.play_hazard_head is None
            else self.play_hazard_head(repair_features)
            .reshape(batch_size, sequence_length)
        )
        if play_hazard_logits is not None and self.play_hazard_adapter is not None:
            adapter_delta = self.play_hazard_adapter(
                repair_features
            ).reshape(batch_size, sequence_length)
            if self.config.play_hazard_adapter_enemy_y_gate < 1.0:
                entity_features = inputs.entity_features
                enemy_near_towers = (
                    inputs.entity_mask
                    & (entity_features[..., 3] > 0.5)
                    & (entity_features[..., 4] > 0.5)
                    & (
                        entity_features[..., 1]
                        < self.config.play_hazard_adapter_enemy_y_gate
                    )
                )
                adapter_delta = adapter_delta * enemy_near_towers.any(dim=-1)
            adapter_delta = adapter_delta * self.config.play_hazard_adapter_gain
            play_hazard_logits = play_hazard_logits + adapter_delta

        return PolicyOutput(
            joint_logits=joint_logits,
            values=values,
            opponent_hand_logits=opponent_hand_logits,
            opponent_elixir=opponent_elixir,
            next_state=next_state,
            action_type_logits=action_type_logits,
            location_logits=location_logits,
            repair_features=repair_features.reshape(
                batch_size,
                sequence_length,
                -1,
            ),
            deterministic_timing_logits=deterministic_timing_logits,
            play_hazard_logits=play_hazard_logits,
            hierarchical_mode_logits=hierarchical_mode_logits,
            action_values=action_values,
        )

    @torch.no_grad()
    def act(
        self,
        inputs: PolicyInputs,
        state: tuple[Tensor, Tensor] | None = None,
        *,
        deterministic: bool = False,
        sampling_temperature: float = 1.0,
    ) -> tuple[Tensor, Tensor, Tensor, tuple[Tensor, Tensor], PolicyOutput]:
        output = self.forward(inputs, state)
        hazard_gate: Tensor | None = None
        stored_hazard: Tensor | None = None
        if self.config.play_hazard_enabled:
            previous_hazard = output.next_state[0][:, -1]
            hazard_gate, stored_hazard = self._play_hazard_force_gate(
                output,
                inputs.action_mask,
                previous_hazard,
            )
        elif self.config.deterministic_hierarchy == "event":
            previous_hazard = output.next_state[0][:, -1]
            hazard_gate, stored_hazard = self._event_mode_force_gate(
                output,
                inputs.action_mask,
                previous_hazard,
            )
        distribution = output.distribution(
            temperature=sampling_temperature,
            force_play=hazard_gate,
        )
        if deterministic:
            actions = self._deterministic_actions(
                output,
                inputs.action_mask,
                force_play=hazard_gate,
            )
        else:
            actions = distribution.sample()
            if stored_hazard is not None:
                if inputs.sequence_length != 1:
                    raise ValueError(
                        "stochastic play-hazard action selection requires one step"
                    )
                placement = actions[:, 0] < NUM_HAND_SLOTS * NUM_TILES
                stored_hazard = torch.where(
                    placement,
                    torch.zeros_like(stored_hazard),
                    stored_hazard,
                )
        if stored_hazard is not None:
            next_hidden = output.next_state[0].clone()
            next_hidden[:, -1] = stored_hazard
            next_state = (next_hidden, output.next_state[1])
            output = replace(output, next_state=next_state)
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
