"""Small policy projection for :mod:`clasher.torch_sim.simple_state`.

The projector consumes only fixed-shape tensors.  Internal ``stable_id``
values are intentionally absent from every returned observation: entity and
hand IDs come from explicit typed vocabulary lookups supplied by the caller.
"""

from __future__ import annotations

import math
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
from .simple_catalog import FAST_STATUS_SLOW, FAST_STATUS_STUN
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
    entity_special: torch.Tensor
    entity_invisible: torch.Tensor
    entity_hidden: torch.Tensor
    max_ticks: int
    tower_token_lookup: torch.Tensor | None = None
    canonical_entity_order: bool = False
    entity_collision_radius_lookup: torch.Tensor | None = None
    entity_collision_radius_override: torch.Tensor | None = None
    entity_airborne: torch.Tensor | None = None
    entity_shield: torch.Tensor | None = None
    entity_max_shield: torch.Tensor | None = None
    entity_status_kind: torch.Tensor | None = None
    entity_status_ticks: torch.Tensor | None = None
    entity_haste_ticks: torch.Tensor | None = None
    entity_charge_ready: torch.Tensor | None = None


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
        self._seats = self._perspectives[..., 0]
        self._canonical_tower_order = torch.tensor(
            (1, 0, 2), dtype=torch.int64, device=state.device
        )
        self._entity_slots = torch.arange(
            state.max_entities, dtype=torch.int64, device=state.device
        ).view(1, 1, -1)

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
            "entity_special": (batch, entities),
            "entity_invisible": (batch, entities),
            "entity_hidden": (batch, entities),
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
        if inputs.tower_token_lookup is not None:
            if inputs.tower_token_lookup.shape != (2,):
                raise ValueError(
                    "tower_token_lookup must contain [king, princess] tokens"
                )
            if inputs.tower_token_lookup.device != state.device:
                raise ValueError("tower_token_lookup is on a different device")
            if inputs.tower_token_lookup.dtype != torch.int64:
                raise ValueError("tower_token_lookup must be int64")
            if bool((inputs.tower_token_lookup <= 0).any()):
                raise ValueError("tower_token_lookup tokens must be positive")
        entity_optional = (
            "entity_collision_radius_override",
            "entity_airborne",
            "entity_shield",
            "entity_max_shield",
            "entity_status_kind",
            "entity_status_ticks",
            "entity_haste_ticks",
            "entity_charge_ready",
        )
        for name in entity_optional:
            value = getattr(inputs, name)
            if value is not None:
                if value.shape != (batch, entities):
                    raise ValueError(f"{name} must have shape [batch, entities]")
                if value.device != state.device:
                    raise ValueError(f"{name} is on a different device")
        collision_lookup = inputs.entity_collision_radius_lookup
        if collision_lookup is not None:
            if collision_lookup.ndim != 1:
                raise ValueError(
                    "entity_collision_radius_lookup must be one-dimensional"
                )
            if collision_lookup.device != state.device:
                raise ValueError(
                    "entity_collision_radius_lookup is on a different device"
                )
        if (inputs.entity_shield is None) != (inputs.entity_max_shield is None):
            raise ValueError("entity shield and maximum must be supplied together")
        if inputs.hand_card_ids.dtype != torch.int64:
            raise ValueError("hand_card_ids must be int64")
        if inputs.public_visibility.dtype != torch.bool:
            raise ValueError("public_visibility must be bool")
        if inputs.canonical_entity_order and not bool(inputs.public_visibility.all()):
            raise ValueError(
                "canonical entity ordering requires fully public entity rows"
            )
        for name in ("entity_special", "entity_invisible", "entity_hidden"):
            if getattr(inputs, name).dtype != torch.bool:
                raise ValueError(f"{name} must be bool")
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
        tower_lookup = self.inputs.tower_token_lookup
        if tower_lookup is not None:
            slots = self._entity_slots[:, 0]
            tower_slot = slots < 6
            king_slot = (slots == 2) | (slots == 5)
            tower_token = torch.where(
                king_slot,
                tower_lookup[0],
                tower_lookup[1],
            )
            token = torch.where(tower_slot, tower_token, token)
            known = known | tower_slot
        return token[:, None, :].expand(-1, 2, -1), known

    def _canonical_order(
        self,
        tokens: torch.Tensor,
        features: torch.Tensor,
        included: torch.Tensor,
    ) -> torch.Tensor:
        """Match the Python structured builder's public semantic ordering.

        The scalar builder sorts by entity kind, ownership relative to the
        viewer, typed token, canonical y/x, and finally retains insertion order
        for exact ties. Stable IDs are the tensor runtime's insertion
        generation, so sorting by them first provides the same final tie rule.
        """

        batch, seats, entities = tokens.shape
        stable_id = self.state.stable_id[:, None, :].expand(-1, seats, -1)
        maximum = torch.iinfo(torch.int64).max
        insertion_key = torch.where(
            included,
            stable_id,
            torch.full_like(stable_id, maximum),
        )
        insertion_order = torch.argsort(insertion_key, dim=2, stable=True)

        kind = self.state.kind.to(torch.int64)[:, None, :].expand(-1, seats, -1)
        owner = self.state.owner.to(torch.int64)[:, None, :]
        enemy = (owner != self._perspectives).to(torch.int64)
        # Python rounds float32 normalized positions to five decimal places in
        # its sort key. Torch uses the same ties-to-even rounding convention.
        y_key = torch.round(features[..., 1] * 100_000.0).to(torch.int64)
        x_key = torch.round(features[..., 0] * 100_000.0).to(torch.int64)
        semantic_key = kind * 2 + enemy
        semantic_key = semantic_key * 1_000_000 + tokens
        semantic_key = semantic_key * 100_001 + y_key
        semantic_key = semantic_key * 100_001 + x_key
        semantic_key = torch.where(
            included,
            semantic_key,
            torch.full_like(semantic_key, maximum),
        )
        ordered_key = semantic_key.gather(2, insertion_order)
        semantic_order = torch.argsort(ordered_key, dim=2, stable=True)
        return insertion_order.gather(2, semantic_order).reshape(batch, seats, entities)

    @staticmethod
    def _gather_entities(value: torch.Tensor, order: torch.Tensor) -> torch.Tensor:
        if value.ndim == 3:
            return value.gather(2, order)
        if value.ndim == 4:
            return value.gather(
                2, order[..., None].expand(*order.shape, value.shape[3])
            )
        raise ValueError("entity projection tensors must have rank 3 or 4")

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
        x_units = state.x_units.to(torch.float32)[:, None, :]
        y_units = state.y_units.to(torch.float32)[:, None, :]
        mirrored = self._perspectives == 1
        canonical_x = torch.where(
            mirrored,
            float(BOARD_WIDTH * 1000) - x_units,
            x_units,
        )
        canonical_y = torch.where(
            mirrored,
            float(BOARD_HEIGHT * 1000) - y_units,
            y_units,
        )
        features[..., 0] = (canonical_x / float(BOARD_WIDTH * 1000)).clamp(0.0, 1.0)
        features[..., 1] = (canonical_y / float(BOARD_HEIGHT * 1000)).clamp(0.0, 1.0)
        owner = state.owner.to(torch.int64)[:, None, :]
        own = owner == self._perspectives
        features[..., 2] = own
        features[..., 3] = ~own
        kind = state.kind.to(torch.int64)[:, None, :]
        for kind_id in range(5):
            features[..., 4 + kind_id] = kind == kind_id
        hp_fraction = state.hp / state.max_hp.clamp_min(1.0)
        features[..., 9] = hp_fraction[:, None, :].clamp(0.0, 1.0)
        if self.inputs.entity_shield is not None:
            assert self.inputs.entity_max_shield is not None
            shield = (
                self.inputs.entity_shield / self.inputs.entity_max_shield.clamp_min(1.0)
            )
            features[..., 10] = shield[:, None, :].clamp(0.0, 1.0)
        if self.inputs.entity_airborne is not None:
            features[..., 11] = self.inputs.entity_airborne[:, None, :]
        features[..., 12] = (state.deploy_ticks > 0)[:, None, :]
        features[..., 13] = (state.deploy_ticks.to(torch.float32) / 20.0)[
            :, None, :
        ].clamp(0.0, 1.0)
        features[..., 17] = self.inputs.entity_special[:, None, :]
        features[..., 18] = self.inputs.entity_invisible[:, None, :]
        features[..., 19] = self.inputs.entity_hidden[:, None, :]
        if (
            self.inputs.entity_status_kind is not None
            and self.inputs.entity_status_ticks is not None
        ):
            status_seconds = (
                self.inputs.entity_status_ticks.to(torch.float32) * 0.05 / 6.0
            ).clamp(0.0, 1.0)
            features[..., 14] = torch.where(
                self.inputs.entity_status_kind == FAST_STATUS_STUN,
                status_seconds,
                0.0,
            )[:, None, :]
            features[..., 15] = torch.where(
                self.inputs.entity_status_kind == FAST_STATUS_SLOW,
                status_seconds,
                0.0,
            )[:, None, :]
        if self.inputs.entity_haste_ticks is not None:
            features[..., 16] = (
                self.inputs.entity_haste_ticks.to(torch.float32) * 0.05 / 6.0
            )[:, None, :].clamp(0.0, 1.0)
        if self.inputs.entity_charge_ready is not None:
            features[..., 22] = self.inputs.entity_charge_ready[:, None, :]
        features[..., 23] = (
            torch.log1p(state.speed_units_per_tick.abs().to(torch.float32))
            / math.log(1_001.0)
        )[:, None, :].clamp(0.0, 1.0)
        features[..., 24] = (state.range_units.to(torch.float32) / 12_000.0)[
            :, None, :
        ].clamp(0.0, 1.0)
        features[..., 25] = (state.sight_range_units.to(torch.float32) / 12_000.0)[
            :, None, :
        ].clamp(0.0, 1.0)
        collision_lookup = self.inputs.entity_collision_radius_lookup
        if collision_lookup is not None:
            safe_card = state.card_id.clamp(0, collision_lookup.shape[0] - 1)
            collision = collision_lookup[safe_card]
            if self.inputs.entity_collision_radius_override is not None:
                collision = collision.maximum(
                    self.inputs.entity_collision_radius_override
                )
            features[..., 26] = (collision.to(torch.float32) / 3_000.0)[
                :, None, :
            ].clamp(0.0, 1.0)
        tower_slots = (
            self._entity_slots < 6
            if self.inputs.tower_token_lookup is not None
            else torch.zeros_like(self._entity_slots, dtype=torch.bool)
        )
        tower_facing_y = torch.where(
            state.owner.to(torch.int64)[:, None, :] == self._perspectives,
            1.0,
            -1.0,
        )
        features[..., 28] = torch.where(tower_slots, tower_facing_y, 0.0)
        features[..., 30] = (torch.log1p(state.damage.clamp_min(0.0)) / 8.0)[
            :, None, :
        ].clamp(0.0, 1.0)
        building = state.kind.to(torch.int64) == 1
        king_slot = tower_slots[:, 0] & (
            (self._entity_slots[:, 0] == 2) | (self._entity_slots[:, 0] == 5)
        )
        owner = state.owner.to(torch.int64).clamp(0, 1)
        king_active = state.king_active.gather(1, owner)
        active_building = building & (~king_slot | king_active)
        features[..., 31] = active_building[:, None, :]
        return features

    def _globals(self) -> tuple[torch.Tensor, torch.Tensor]:
        state = self.state
        inputs = self.inputs
        batch = state.batch_size
        seat = self._seats
        enemy = 1 - seat
        progress = (state.tick.to(torch.float32) / float(inputs.max_ticks)).clamp(
            0.0, 1.0
        )
        tower_fraction = (inputs.tower_hp / inputs.tower_max_hp.clamp_min(1.0)).clamp(
            0.0, 1.0
        )
        own_tower = tower_fraction.gather(1, seat[..., None].expand(batch, 2, 3))
        enemy_tower = tower_fraction.gather(1, enemy[..., None].expand(batch, 2, 3))
        own_tower = torch.where(
            (seat == 1)[..., None],
            own_tower.index_select(2, self._canonical_tower_order),
            own_tower,
        )
        enemy_tower = torch.where(
            (seat == 1)[..., None],
            enemy_tower.index_select(2, self._canonical_tower_order),
            enemy_tower,
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
            alive[:, None, :] & known[:, None, :] & self.inputs.public_visibility
        )
        critic_mask = (alive[:, None, :] & known[:, None, :]).expand(-1, 2, -1)
        public_tokens = tokens
        public_features = features
        critic_tokens = tokens
        critic_features = features
        if self.inputs.canonical_entity_order:
            entity_order = self._canonical_order(tokens, features, critic_mask)
            public_tokens = self._gather_entities(tokens, entity_order)
            public_features = self._gather_entities(features, entity_order)
            public_mask = self._gather_entities(public_mask, entity_order)
            critic_tokens = public_tokens
            critic_features = public_features
            critic_mask = self._gather_entities(critic_mask, entity_order)
        actor_globals, critic_globals = self._globals()
        hand_tokens = self._hand_tokens()
        actor = TensorPublicStructuredObservation(
            entity_ids=torch.where(
                public_mask, public_tokens, torch.zeros_like(public_tokens)
            ),
            entity_features=torch.where(
                public_mask[..., None],
                public_features,
                torch.zeros_like(public_features),
            ),
            entity_mask=public_mask,
            hand_ids=hand_tokens,
            global_features=actor_globals,
        )
        critic: TensorPrivilegedCriticObservation | None = None
        if self.include_privileged_critic:
            # Keep the fixed two-player swap device-native and capturable.
            enemy_hand = hand_tokens.flip(1)
            critic = TensorPrivilegedCriticObservation(
                entity_ids=torch.where(
                    critic_mask, critic_tokens, torch.zeros_like(critic_tokens)
                ),
                entity_features=torch.where(
                    critic_mask[..., None],
                    critic_features,
                    torch.zeros_like(critic_features),
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
