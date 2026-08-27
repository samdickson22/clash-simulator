from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from clasher.arena import TileGrid
from clasher.card_aliases import resolve_card_name
from clasher.spells import SPELL_REGISTRY

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES

if TYPE_CHECKING:
    from .public_observation import ConfidenceAwareActorObservation
    from .structured_obs import StructuredObservation, StructuredObservationBuilder

PUBLIC_ACTION_MASK_CONTRACT_VERSION = 2


@dataclass(frozen=True)
class PublicActionMaskInput:
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    hand_ids: np.ndarray
    global_features: np.ndarray
    entity_id_confidence: np.ndarray | None
    hand_id_confidence: np.ndarray | None
    global_feature_confidence: np.ndarray | None

    @classmethod
    def from_confidence_observation(
        cls, source: ConfidenceAwareActorObservation
    ) -> PublicActionMaskInput:
        observation = source.observation
        return cls(
            entity_ids=observation.entity_ids,
            entity_features=observation.entity_features,
            entity_mask=observation.entity_mask,
            hand_ids=observation.hand_ids,
            global_features=observation.global_features,
            entity_id_confidence=source.entity_id_confidence,
            hand_id_confidence=source.hand_id_confidence,
            global_feature_confidence=source.global_feature_confidence,
        )


class PublicActionMaskBuilder:
    """Build deployability from causal actor state without simulator access."""

    def __init__(self, builder: StructuredObservationBuilder) -> None:
        self.builder = builder
        self._tile_grid = TileGrid()
        self.no_op_action = NUM_HAND_SLOTS * NUM_TILES
        self.ability_action = self.no_op_action + 1
        self.num_actions = self.ability_action + 1
        self._non_blocked = np.ones((NUM_TILES,), dtype=np.bool_)
        for x, y in TileGrid.BLOCKED_TILES:
            if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT:
                self._non_blocked[y * BOARD_WIDTH + x] = False

    def _deploy_zone(
        self, observation: StructuredObservation | PublicActionMaskInput
    ) -> np.ndarray:
        zones = [(0, 1, BOARD_WIDTH, 15), (6, 0, 12, 6)]
        confidence = observation.global_feature_confidence
        if (
            confidence is not None
            and confidence[11] > 0.0
            and observation.global_features[11] <= 1e-4
        ):
            zones.append((0, 17, 9, 21))
        if (
            confidence is not None
            and confidence[12] > 0.0
            and observation.global_features[12] <= 1e-4
        ):
            zones.append((9, 17, BOARD_WIDTH, 21))
        result = np.zeros((NUM_TILES,), dtype=np.bool_)
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                if any(x1 <= x + 0.5 < x2 and y1 <= y + 0.5 < y2 for x1, y1, x2, y2 in zones):
                    result[y * BOARD_WIDTH + x] = True
        return result

    def _building_blockers(
        self, observation: StructuredObservation | PublicActionMaskInput
    ) -> list[tuple[float, float, float, float]]:
        blockers: list[tuple[float, float, float, float]] = []
        identity_confidence = observation.entity_id_confidence
        for index in np.flatnonzero(observation.entity_mask).tolist():
            if observation.entity_features[index, 5] <= 0.5:
                continue
            if identity_confidence is not None and identity_confidence[index] <= 0.0:
                continue
            token = int(observation.entity_ids[index])
            if not 0 <= token < len(self.builder.token_names):
                continue
            radius = float(self.builder.card_stat_features[token, 12]) * 3.0
            footprint_size = max(1, math.ceil(max(0.0, radius) * 2.0) + 1)
            # The actor sees body centres, not the simulator's exact hitbox.
            # Preserve the data-derived native footprint and add half a tile
            # for localization uncertainty. This also safely covers Crown
            # Tower tiles without identifying towers by card name.
            footprint_half = footprint_size / 2.0 + 0.5
            blockers.append(
                (
                    float(observation.entity_features[index, 0]) * BOARD_WIDTH,
                    float(observation.entity_features[index, 1]) * BOARD_HEIGHT,
                    max(0.5, radius),
                    footprint_half,
                )
            )
        return blockers

    @staticmethod
    def _occupied(
        x: float,
        y: float,
        deploy_radius: float,
        blockers: list[tuple[float, float, float, float]],
        *,
        building_footprint_half: float | None,
    ) -> bool:
        for blocker_x, blocker_y, blocker_radius, blocker_half in blockers:
            if building_footprint_half is not None:
                if (
                    abs(x - blocker_x) < building_footprint_half + blocker_half
                    and abs(y - blocker_y)
                    < building_footprint_half + blocker_half
                ):
                    return True
                continue
            # Troop collision is circular. The square test additionally
            # excludes the visually measured building footprint, which is a
            # conservative guard against centre-localization error.
            if (x - blocker_x) ** 2 + (y - blocker_y) ** 2 < (
                deploy_radius + blocker_radius
            ) ** 2:
                return True
            if (
                abs(x - blocker_x) < blocker_half
                and abs(y - blocker_y) < blocker_half
            ):
                return True
        return False

    def build(
        self, observation: StructuredObservation | PublicActionMaskInput
    ) -> np.ndarray:
        mask = np.zeros((self.num_actions,), dtype=np.bool_)
        mask[self.no_op_action] = True
        # Ability state is not yet in the proven camera contract. Fail closed
        # instead of leaking the simulator's exact Champion mechanic state.
        mask[self.ability_action] = False
        hand_confidence = observation.hand_id_confidence
        global_confidence = observation.global_feature_confidence
        if global_confidence is None or global_confidence[5] <= 0.0:
            return mask
        elixir = float(observation.global_features[5]) * 10.0
        zone = self._deploy_zone(observation)
        blockers = self._building_blockers(observation)

        for slot in range(NUM_HAND_SLOTS):
            # The vision contract emits a nonzero token only after accepting
            # the identity. Confidence describes observation quality for the
            # policy; it must not independently erase an accepted public card.
            if (
                hand_confidence is not None
                and hand_confidence[slot] <= 0.0
            ):
                continue
            token = int(observation.hand_ids[slot])
            if not 0 < token < len(self.builder.token_names):
                continue
            card_name = self.builder.card_name_for_token_id(token)
            if card_name is None:
                continue
            stats = self.builder.loader.get_card(card_name)
            if stats is None:
                continue
            cost = float(getattr(stats, "mana_cost", 0.0) or 0.0)
            if not math.isfinite(cost) or cost > elixir + 1e-6:
                continue
            resolved = resolve_card_name(
                card_name, self.builder.loader.load_card_definitions()
            )
            is_spell = resolved in SPELL_REGISTRY
            spell = SPELL_REGISTRY.get(resolved) if is_spell else None
            non_rolling_spell = bool(
                is_spell
                and not self._tile_grid._requires_deploy_zone_spell(spell)
                and not getattr(spell, "requires_walkable_target", False)
            )
            card_type = str(getattr(stats, "card_type", "") or "").lower()
            is_building = not is_spell and card_type == "building"
            can_deploy_enemy_side = bool(
                not is_spell and getattr(stats, "can_deploy_on_enemy_side", False)
            )
            if non_rolling_spell or can_deploy_enemy_side:
                candidates = self._non_blocked.copy()
            else:
                candidates = zone & self._non_blocked
            deploy_margin = int(getattr(stats, "deploy_w_tile_margin", 0) or 0)
            base_radius = float(getattr(stats, "collision_radius", 0.5) or 0.5)
            building_footprint_half = (
                (max(1, math.ceil(max(0.0, base_radius) * 2.0) + 1) / 2.0)
                if is_building
                else None
            )
            for tile in np.flatnonzero(candidates).tolist():
                x = float(tile % BOARD_WIDTH) + 0.5
                y = float(tile // BOARD_WIDTH) + 0.5
                if deploy_margin and not (
                    deploy_margin <= x < BOARD_WIDTH - deploy_margin
                ):
                    continue
                if not is_spell and self._occupied(
                    x,
                    y,
                    base_radius,
                    blockers,
                    building_footprint_half=building_footprint_half,
                ):
                    continue
                mask[slot * NUM_TILES + tile] = True
        return mask
