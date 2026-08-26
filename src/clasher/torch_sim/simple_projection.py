"""Small policy projection for :mod:`clasher.torch_sim.simple_state`.

The projector consumes only fixed-shape tensors.  Internal ``stable_id``
values are intentionally absent from every returned observation: entity and
hand IDs come from explicit typed vocabulary lookups supplied by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH
from clasher.rl.structured_obs import (
    ACTOR_GLOBAL_SIZE,
    CRITIC_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
)

from .resident_outputs import (
    TensorPrivilegedCriticObservation,
    TensorPublicStructuredObservation,
)
from .simple_state import FastGymState


@dataclass(frozen=True)
class SimpleProjectionInputs:
    """Policy metadata and private player state kept outside the combat pool.

    ``hand_card_ids`` contains four ordered hand slots plus Next.  Typed
    variants must have distinct raw card IDs and lookup entries; the projector
    never resolves a variant to its base family.
    """

    entity_token_lookup: torch.Tensor
    hand_token_lookup: torch.Tensor
    hand_card_ids: torch.Tensor
    public_visibility: torch.Tensor
    elixir: torch.Tensor
    max_elixir: torch.Tensor
    tower_hp: torch.Tensor
    tower_max_hp: torch.Tensor
    double_elixir: torch.Tensor
    triple_elixir: torch.Tensor
    overtime: torch.Tensor
    ability_cooldown: torch.Tensor
    ability_duration: torch.Tensor
    refill_cooldown_ms: torch.Tensor
    max_ticks: int


@dataclass(frozen=True)
class SimpleProjectedObservation:
    actor: TensorPublicStructuredObservation
    critic: TensorPrivilegedCriticObservation | None
    legal_mask: torch.Tensor


class SimpleTensorProjector:
    """Project one fixed-shape Gym state into two canonical player views."""

    def __init__(
        self,
        state: FastGymState,
        inputs: SimpleProjectionInputs,
        *,
        include_privileged_critic: bool = False,
    ) -> None:
        self.state = state
        self.inputs = inputs
        self.include_privileged_critic = bool(include_privileged_critic)
        self._validate_metadata()
        self._perspectives = torch.arange(
            2, dtype=torch.int64, device=state.device
        ).view(1, 2, 1)

    def _validate_metadata(self) -> None:
        state = self.state
        inputs = self.inputs
        batch = state.batch_size
        entities = state.max_entities
        expected = {
            "hand_card_ids": (batch, 2, 5),
            "public_visibility": (batch, 2, entities),
            "elixir": (batch, 2),
            "max_elixir": (batch, 2),
            "tower_hp": (batch, 2, 3),
            "tower_max_hp": (batch, 2, 3),
            "double_elixir": (batch,),
            "triple_elixir": (batch,),
            "overtime": (batch,),
            "ability_cooldown": (batch, 2),
            "ability_duration": (batch, 2),
            "refill_cooldown_ms": (batch, 2),
        }
        for name, shape in expected.items():
            value = getattr(inputs, name)
            if tuple(value.shape) != shape:
                raise ValueError(f"{name} must have shape {shape}")
            if value.device != state.device:
                raise ValueError(f"{name} is on a different device")
        if inputs.entity_token_lookup.ndim != 2:
            raise ValueError("entity_token_lookup must have shape [kinds, cards]")
        if inputs.hand_token_lookup.ndim != 1:
            raise ValueError("hand_token_lookup must have shape [cards]")
        if inputs.entity_token_lookup.device != state.device:
            raise ValueError("entity_token_lookup is on a different device")
        if inputs.hand_token_lookup.device != state.device:
            raise ValueError("hand_token_lookup is on a different device")
        if inputs.entity_token_lookup.dtype != torch.int64:
            raise ValueError("entity_token_lookup must be int64")
        if inputs.hand_token_lookup.dtype != torch.int64:
            raise ValueError("hand_token_lookup must be int64")
        if inputs.hand_card_ids.dtype != torch.int64:
            raise ValueError("hand_card_ids must be int64")
        if inputs.public_visibility.dtype != torch.bool:
            raise ValueError("public_visibility must be bool")
        if inputs.max_ticks < 1:
            raise ValueError("max_ticks must be positive")

    def _typed_entity_tokens(self) -> tuple[torch.Tensor, torch.Tensor]:
        lookup = self.inputs.entity_token_lookup
        kind = self.state.kind.to(torch.int64)
        card = self.state.card_id
        known = (
            (kind >= 0)
            & (kind < lookup.shape[0])
            & (card >= 0)
            & (card < lookup.shape[1])
        )
        token = lookup[
            kind.clamp(0, lookup.shape[0] - 1),
            card.clamp(0, lookup.shape[1] - 1),
        ]
        return token[:, None, :].expand(-1, 2, -1), known

    def _hand_tokens(self) -> torch.Tensor:
        lookup = self.inputs.hand_token_lookup
        card = self.inputs.hand_card_ids
        known = (card >= 0) & (card < lookup.shape[0])
        token = lookup[card.clamp(0, lookup.shape[0] - 1)]
        return torch.where(known, token, torch.zeros_like(token))

    def _entity_features(self) -> torch.Tensor:
        state = self.state
        batch, entities = state.active.shape
        features = torch.zeros(
            (batch, 2, entities, ENTITY_FEATURE_SIZE),
            dtype=torch.float32,
            device=state.device,
        )
        x = state.x_units.to(torch.float32) / float(BOARD_WIDTH * 1000)
        y = state.y_units.to(torch.float32) / float(BOARD_HEIGHT * 1000)
        x = x[:, None, :].expand(-1, 2, -1)
        y = y[:, None, :].expand(-1, 2, -1)
        mirrored = self._perspectives == 1
        features[..., 0] = torch.where(mirrored, 1.0 - x, x).clamp(0.0, 1.0)
        features[..., 1] = torch.where(mirrored, 1.0 - y, y).clamp(0.0, 1.0)
        owner = state.owner.to(torch.int64)[:, None, :]
        own = owner == self._perspectives
        features[..., 2] = own
        features[..., 3] = ~own
        kind = state.kind.to(torch.int64)[:, None, :]
        for kind_id in range(5):
            features[..., 4 + kind_id] = kind == kind_id
        hp_fraction = state.hp / state.max_hp.clamp_min(1.0)
        features[..., 9] = hp_fraction[:, None, :].clamp(0.0, 1.0)
        features[..., 12] = (state.deploy_ticks > 0)[:, None, :]
        features[..., 13] = (
            state.deploy_ticks.to(torch.float32) / 20.0
        )[:, None, :].clamp(0.0, 1.0)
        return features

    def _globals(self) -> tuple[torch.Tensor, torch.Tensor]:
        state = self.state
        inputs = self.inputs
        batch = state.batch_size
        seat = torch.arange(2, device=state.device).view(1, 2)
        enemy = 1 - seat
        progress = (state.tick.to(torch.float32) / float(inputs.max_ticks)).clamp(
            0.0, 1.0
        )
        tower_fraction = (inputs.tower_hp / inputs.tower_max_hp.clamp_min(1.0)).clamp(
            0.0, 1.0
        )
        own_tower = tower_fraction.gather(1, seat[..., None].expand(batch, 2, 3))
        enemy_tower = tower_fraction.gather(
            1, enemy[..., None].expand(batch, 2, 3)
        )
        lanes = torch.tensor([1, 0, 2], dtype=torch.int64, device=state.device)
        own_tower = torch.where(
            (seat == 1)[..., None], own_tower.index_select(2, lanes), own_tower
        )
        enemy_tower = torch.where(
            (seat == 1)[..., None], enemy_tower.index_select(2, lanes), enemy_tower
        )
        own_elixir = inputs.elixir.gather(1, seat.expand(batch, 2))
        own_max = inputs.max_elixir.gather(1, seat.expand(batch, 2))
        enemy_elixir = inputs.elixir.gather(1, enemy.expand(batch, 2))
        enemy_max = inputs.max_elixir.gather(1, enemy.expand(batch, 2))
        own_refill = inputs.refill_cooldown_ms.gather(1, seat.expand(batch, 2))
        enemy_refill = inputs.refill_cooldown_ms.gather(1, enemy.expand(batch, 2))
        king_dead = inputs.tower_hp[:, :, 2] <= 0
        side_lost = (inputs.tower_hp[:, :, :2] <= 0).sum(dim=2)
        crowns = torch.where(king_dead, torch.full_like(side_lost, 3), side_lost)
        own_crowns = crowns.gather(1, enemy.expand(batch, 2))
        enemy_crowns = crowns.gather(1, seat.expand(batch, 2))

        actor = torch.zeros(
            (batch, 2, ACTOR_GLOBAL_SIZE),
            dtype=torch.float32,
            device=state.device,
        )
        actor[..., 0] = progress[:, None]
        actor[..., 1] = 1.0 - progress[:, None]
        actor[..., 2] = inputs.double_elixir[:, None]
        actor[..., 3] = inputs.triple_elixir[:, None]
        actor[..., 4] = inputs.overtime[:, None]
        actor[..., 5] = (own_elixir / own_max.clamp_min(1.0)).clamp(0.0, 1.0)
        actor[..., 6] = own_crowns.to(torch.float32) / 3.0
        actor[..., 7] = enemy_crowns.to(torch.float32) / 3.0
        actor[..., 8:11] = own_tower
        actor[..., 11:14] = enemy_tower
        actor[..., 14] = inputs.ability_cooldown.clamp(0.0, 1.0)
        actor[..., 15] = inputs.ability_duration.clamp(0.0, 1.0)
        actor[..., 16] = (own_refill / 1000.0).clamp(0.0, 1.0)
        actor[..., 17] = enemy_tower[..., 2] > 0

        critic = torch.zeros(
            (batch, 2, CRITIC_GLOBAL_SIZE),
            dtype=torch.float32,
            device=state.device,
        )
        critic[..., :ACTOR_GLOBAL_SIZE] = actor
        critic[..., 18] = (enemy_elixir / enemy_max.clamp_min(1.0)).clamp(0.0, 1.0)
        critic[..., 19] = (enemy_refill / 1000.0).clamp(0.0, 1.0)
        return actor, critic

    def project(self, legal_mask: torch.Tensor) -> SimpleProjectedObservation:
        """Return actor-safe views and an optional separate privileged critic."""

        if legal_mask.shape[:2] != (self.state.batch_size, 2):
            raise ValueError("legal_mask must begin with [batch, 2]")
        tokens, known = self._typed_entity_tokens()
        features = self._entity_features()
        alive = self.state.active & (self.state.hp > 0)
        public_mask = (
            alive[:, None, :]
            & known[:, None, :]
            & self.inputs.public_visibility
        )
        actor_globals, critic_globals = self._globals()
        hand_tokens = self._hand_tokens()
        actor = TensorPublicStructuredObservation(
            entity_ids=torch.where(public_mask, tokens, torch.zeros_like(tokens)),
            entity_features=torch.where(
                public_mask[..., None], features, torch.zeros_like(features)
            ),
            entity_mask=public_mask,
            hand_ids=hand_tokens,
            global_features=actor_globals,
        )
        critic: TensorPrivilegedCriticObservation | None = None
        if self.include_privileged_critic:
            critic_mask = (alive[:, None, :] & known[:, None, :]).expand(-1, 2, -1)
            enemy_hand = hand_tokens[:, [1, 0], :]
            critic = TensorPrivilegedCriticObservation(
                entity_ids=torch.where(critic_mask, tokens, torch.zeros_like(tokens)),
                entity_features=torch.where(
                    critic_mask[..., None], features, torch.zeros_like(features)
                ),
                entity_mask=critic_mask,
                card_ids=torch.cat((hand_tokens, enemy_hand), dim=2),
                global_features=critic_globals,
            )
        return SimpleProjectedObservation(
            actor=actor,
            critic=critic,
            legal_mask=legal_mask,
        )


__all__ = [
    "SimpleProjectedObservation",
    "SimpleProjectionInputs",
    "SimpleTensorProjector",
]
