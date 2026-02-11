from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.spells import SPELL_REGISTRY

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES


@dataclass(frozen=True)
class ActionSelection:
    action_id: int
    slot: Optional[int]
    position: Optional[Position]
    is_no_op: bool


class DiscreteTileActionSpace:
    """Action space: (hand slot, tile) + no-op.

    Action IDs:
    - `slot * NUM_TILES + tile` for deployment actions.
    - `NUM_HAND_SLOTS * NUM_TILES` for no-op.
    """

    def __init__(self, canonical_perspective: bool = True) -> None:
        self.canonical_perspective = canonical_perspective
        self.num_actions = NUM_HAND_SLOTS * NUM_TILES + 1
        self.no_op_action = self.num_actions - 1

    def _canonical_to_world_tile(self, x: int, y: int, player_id: int) -> tuple[int, int]:
        if self.canonical_perspective and player_id == 1:
            return BOARD_WIDTH - 1 - x, BOARD_HEIGHT - 1 - y
        return x, y

    def _world_to_canonical_tile(self, x: int, y: int, player_id: int) -> tuple[int, int]:
        if self.canonical_perspective and player_id == 1:
            return BOARD_WIDTH - 1 - x, BOARD_HEIGHT - 1 - y
        return x, y

    def decode_action(self, action_id: int, player_id: int) -> ActionSelection:
        if action_id == self.no_op_action:
            return ActionSelection(action_id=action_id, slot=None, position=None, is_no_op=True)

        if action_id < 0 or action_id >= self.no_op_action:
            return ActionSelection(action_id=action_id, slot=None, position=None, is_no_op=True)

        slot = action_id // NUM_TILES
        tile = action_id % NUM_TILES
        cx = tile % BOARD_WIDTH
        cy = tile // BOARD_WIDTH
        wx, wy = self._canonical_to_world_tile(cx, cy, player_id)
        return ActionSelection(
            action_id=action_id,
            slot=slot,
            position=Position(wx + 0.5, wy + 0.5),
            is_no_op=False,
        )

    def encode_action(self, slot: int, world_x: int, world_y: int, player_id: int) -> int:
        cx, cy = self._world_to_canonical_tile(world_x, world_y, player_id)
        tile = cy * BOARD_WIDTH + cx
        return slot * NUM_TILES + tile

    def _is_legal_deploy(
        self,
        battle: BattleState,
        player_id: int,
        card_name: str,
        resolved_name: str,
        position: Position,
        is_spell: bool,
        spell_obj,
    ) -> bool:
        # Explicit special-case parity with BattleState.deploy_card.
        if resolved_name == "Miner":
            tile_pos = (int(position.x), int(position.y))
            if not battle.arena.is_valid_position(position):
                return False
            if tile_pos in battle.arena.BLOCKED_TILES:
                return False
            if battle.arena.is_tower_tile(position, battle):
                return False
        else:
            if not battle.arena.can_deploy_at(position, player_id, battle, is_spell, spell_obj):
                return False

        if resolved_name in {"RoyalRecruits", "RoyalRecruits_Chess"}:
            if not (6 <= position.x <= 11):
                return False

        if not is_spell:
            card_stats = battle.card_loader.get_card(card_name)
            probe_radius = getattr(card_stats, "collision_radius", 0.5) or 0.5
            if battle.is_position_occupied_by_building(position, probe_radius):
                return False

        return True

    def legal_action_mask(self, battle: BattleState, player_id: int) -> np.ndarray:
        mask = np.zeros(self.num_actions, dtype=np.bool_)
        mask[self.no_op_action] = True

        player = battle.players[player_id]
        for slot, card_name in enumerate(player.hand[:NUM_HAND_SLOTS]):
            card_stats = battle.card_loader.get_card(card_name)
            if card_stats is None:
                continue

            if not player.can_play_card(card_name, card_stats):
                continue

            resolved_name = resolve_card_name(card_name, battle.card_loader.load_card_definitions())
            is_spell = resolved_name in SPELL_REGISTRY
            spell_obj = SPELL_REGISTRY.get(resolved_name) if is_spell else None

            for cy in range(BOARD_HEIGHT):
                for cx in range(BOARD_WIDTH):
                    wx, wy = self._canonical_to_world_tile(cx, cy, player_id)
                    pos = Position(wx + 0.5, wy + 0.5)
                    if self._is_legal_deploy(
                        battle=battle,
                        player_id=player_id,
                        card_name=card_name,
                        resolved_name=resolved_name,
                        position=pos,
                        is_spell=is_spell,
                        spell_obj=spell_obj,
                    ):
                        action = slot * NUM_TILES + (cy * BOARD_WIDTH + cx)
                        mask[action] = True

        return mask

    def apply_action(self, battle: BattleState, player_id: int, action_id: int) -> bool:
        decoded = self.decode_action(action_id, player_id)
        if decoded.is_no_op:
            return True

        assert decoded.slot is not None
        assert decoded.position is not None

        hand = battle.players[player_id].hand
        if decoded.slot >= len(hand):
            return False

        card_name = hand[decoded.slot]
        return battle.deploy_card(player_id, card_name, decoded.position)

    def random_legal_action(self, battle: BattleState, player_id: int, rng: np.random.Generator) -> int:
        mask = self.legal_action_mask(battle, player_id)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            return self.no_op_action
        return int(rng.choice(legal))
