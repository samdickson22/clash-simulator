from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.entities import (
    AreaEffect,
    Building,
    Graveyard,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
    TimedExplosive,
    Troop,
)
from clasher.arena import TileGrid

from .common import BOARD_HEIGHT, BOARD_WIDTH, CvObservation, NUM_HAND_SLOTS
from .deck_pool import load_deck_pool, unique_cards_from_decks


@dataclass(frozen=True)
class ObservationSpec:
    board_channels: int
    hud_size: int
    card_vocab: Sequence[str]


class CvObservationBuilder:
    """Build CV-equivalent observations from battle state.

    The builder intentionally excludes hidden simulator internals (enemy hand,
    enemy cycle queue, enemy elixir, internal cooldowns, target IDs, etc.).
    """

    BOARD_CHANNELS = 15

    def __init__(
        self,
        card_vocab: Sequence[str] | None = None,
        decks_path: str | Path = "decks.json",
        canonical_perspective: bool = True,
    ) -> None:
        self.canonical_perspective = canonical_perspective

        if card_vocab is None:
            decks = load_deck_pool(decks_path)
            card_vocab = unique_cards_from_decks(decks)

        self.card_vocab = list(card_vocab)
        self._card_to_idx: Dict[str, int] = {name: idx for idx, name in enumerate(self.card_vocab)}
        self.spec = ObservationSpec(
            board_channels=self.BOARD_CHANNELS,
            hud_size=10 + NUM_HAND_SLOTS * len(self.card_vocab),
            card_vocab=self.card_vocab,
        )

        # Static terrain planes are perspective-dependent when canonical view is enabled.
        self._terrain_planes = {
            0: self._build_terrain_planes(0),
            1: self._build_terrain_planes(1),
        }

    def _world_to_canonical_tile(self, tile_x: int, tile_y: int, player_id: int) -> tuple[int, int]:
        if self.canonical_perspective and player_id == 1:
            return BOARD_WIDTH - 1 - tile_x, BOARD_HEIGHT - 1 - tile_y
        return tile_x, tile_y

    def _position_to_canonical_tile(self, position: Position, player_id: int) -> tuple[int, int] | None:
        tile_x = int(position.x)
        tile_y = int(position.y)
        if not (0 <= tile_x < BOARD_WIDTH and 0 <= tile_y < BOARD_HEIGHT):
            return None
        return self._world_to_canonical_tile(tile_x, tile_y, player_id)

    def _build_terrain_planes(self, player_id: int) -> np.ndarray:
        planes = np.zeros((3, BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        blocked_tiles = set(TileGrid.BLOCKED_TILES)

        # Build from canonical-space perspective.
        for world_x in range(BOARD_WIDTH):
            for world_y in range(BOARD_HEIGHT):
                x, y = self._world_to_canonical_tile(world_x, world_y, player_id)
                if (world_x, world_y) in blocked_tiles:
                    planes[0, y, x] = 1.0

                on_river = 15.0 <= (world_y + 0.5) <= 16.0
                if on_river:
                    planes[1, y, x] = 1.0

                on_bridge = on_river and (
                    2.0 <= (world_x + 0.5) < 5.0 or 13.0 <= (world_x + 0.5) < 16.0
                )
                if on_bridge:
                    planes[2, y, x] = 1.0

        return planes

    def _encode_hand(self, battle: BattleState, player_id: int) -> np.ndarray:
        hand_vec = np.zeros(NUM_HAND_SLOTS * len(self.card_vocab), dtype=np.float32)
        hand = battle.players[player_id].hand[:NUM_HAND_SLOTS]
        for slot, card_name in enumerate(hand):
            resolved = resolve_card_name(card_name)
            card_idx = self._card_to_idx.get(resolved)
            if card_idx is None:
                continue
            hand_vec[slot * len(self.card_vocab) + card_idx] = 1.0
        return hand_vec

    def _build_hud(self, battle: BattleState, player_id: int) -> np.ndarray:
        own = battle.players[player_id]
        opp = battle.players[1 - player_id]

        own_total_hp = own.king_tower_hp + own.left_tower_hp + own.right_tower_hp
        opp_total_hp = opp.king_tower_hp + opp.left_tower_hp + opp.right_tower_hp

        own_start_hp = float(battle._starting_total_tower_hp.get(player_id, max(1.0, own_total_hp)))
        opp_start_hp = float(battle._starting_total_tower_hp.get(1 - player_id, max(1.0, opp_total_hp)))

        # Visible HUD only.
        scalars = np.array(
            [
                min(1.0, battle.time / 360.0),
                1.0 if battle.double_elixir else 0.0,
                1.0 if battle.triple_elixir else 0.0,
                1.0 if battle.overtime else 0.0,
                own.elixir / max(1.0, own.max_elixir),
                own.get_crown_count() / 3.0,
                opp.get_crown_count() / 3.0,
                own_total_hp / max(1.0, own_start_hp),
                opp_total_hp / max(1.0, opp_start_hp),
                min(1.0, battle.tick / 9090.0),
            ],
            dtype=np.float32,
        )

        return np.concatenate([scalars, self._encode_hand(battle, player_id)], dtype=np.float32)

    def build(self, battle: BattleState, player_id: int) -> CvObservation:
        board = np.zeros((self.BOARD_CHANNELS, BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        board[:3] = self._terrain_planes[player_id]

        for entity in battle.entities.values():
            if not entity.is_alive:
                continue

            canonical_tile = self._position_to_canonical_tile(entity.position, player_id)
            if canonical_tile is None:
                continue
            x, y = canonical_tile

            own_entity = entity.player_id == player_id
            hp_norm = float(entity.hitpoints / max(1.0, entity.max_hitpoints))

            if isinstance(entity, Building):
                name = getattr(getattr(entity, "card_stats", None), "name", "")
                if name in {"Tower", "KingTower"}:
                    channel = 3 if own_entity else 4
                else:
                    channel = 5 if own_entity else 6
            elif isinstance(entity, Troop):
                if entity.is_air_unit:
                    channel = 9 if own_entity else 10
                else:
                    channel = 7 if own_entity else 8
            elif isinstance(
                entity,
                (Projectile, SpawnProjectile, RollingProjectile, AreaEffect, TimedExplosive, Graveyard),
            ):
                channel = 13 if own_entity else 14
            else:
                channel = 13 if own_entity else 14

            board[channel, y, x] = min(1.0, board[channel, y, x] + 1.0)
            hp_channel = 11 if own_entity else 12
            board[hp_channel, y, x] = min(3.0, board[hp_channel, y, x] + hp_norm)

        hud = self._build_hud(battle, player_id)
        return CvObservation(board=board, hud=hud)
