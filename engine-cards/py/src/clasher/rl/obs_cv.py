from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
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
from clasher.kinematics import logic_time_milliseconds
from clasher.arena import TileGrid
from clasher.unit_traits import is_airborne_target

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

    # Base terrain/combat planes plus visible identity, shields, deployment,
    # building posture, status effects, and special movement animations.
    BOARD_CHANNELS = 33
    MAX_VISIBLE_STATUS_SECONDS = 6.0

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
        self._entity_name_to_value = self._build_entity_identity_map()
        self.spec = ObservationSpec(
            board_channels=self.BOARD_CHANNELS,
            hud_size=12 + (NUM_HAND_SLOTS + 1) * len(self.card_vocab),
            card_vocab=self.card_vocab,
        )

        # Static terrain planes are perspective-dependent when canonical view is enabled.
        self._terrain_planes = {
            0: self._build_terrain_planes(0),
            1: self._build_terrain_planes(1),
        }

    def _build_entity_identity_map(self) -> Dict[str, float]:
        """Map deck cards and their spawned descendants to stable visible IDs."""
        denominator = max(1, len(self.card_vocab))
        result: Dict[str, float] = {}
        for index, card_name in enumerate(self.card_vocab):
            value = float(index + 1) / float(denominator)
            result[card_name] = value
            result[resolve_card_name(card_name)] = value

        loader = CardDataLoader()

        def collect_names(value, identity_value: float) -> None:
            if isinstance(value, list):
                for item in value:
                    collect_names(item, identity_value)
                return
            if not isinstance(value, dict):
                return
            name = value.get("name")
            if isinstance(name, str):
                result.setdefault(name, identity_value)
                result.setdefault(resolve_card_name(name), identity_value)
            for key, child in value.items():
                # The gym's enabled decks use base cards only. Do not leak
                # alternate evolution or hero payload identities into them.
                if key in {"evolvedSpellsData", "heroData"}:
                    continue
                collect_names(child, identity_value)

        for index, card_name in enumerate(self.card_vocab):
            stats = loader.get_card(card_name)
            if stats is None:
                continue
            collect_names(
                getattr(stats, "_raw_entry", {}) or {},
                float(index + 1) / float(denominator),
            )
        return result

    def _world_to_canonical_tile(self, tile_x: int, tile_y: int, player_id: int) -> tuple[int, int]:
        if self.canonical_perspective and player_id == 1:
            return BOARD_WIDTH - 1 - tile_x, BOARD_HEIGHT - 1 - tile_y
        return tile_x, tile_y

    def _position_to_canonical_tile(self, position: Position, player_id: int) -> tuple[int, int] | None:
        if not (
            0.0 <= position.x < BOARD_WIDTH
            and 0.0 <= position.y < BOARD_HEIGHT
        ):
            return None
        if self.canonical_perspective and player_id == 1:
            # Rotate the continuous arena point before rasterizing it. Doing
            # this in the opposite order shifts every object exactly on an
            # integer coordinate one cell (the King Towers are the simplest
            # example), so two geometrically mirrored states produce
            # different canonical observations.
            canonical_x = BOARD_WIDTH - position.x
            canonical_y = BOARD_HEIGHT - position.y
            return (
                min(BOARD_WIDTH - 1, int(canonical_x)),
                min(BOARD_HEIGHT - 1, int(canonical_y)),
            )
        return int(position.x), int(position.y)

    @staticmethod
    def _visible_entity_name(entity) -> str:
        """Return the card/source name represented by a visible payload."""
        stats_name = getattr(getattr(entity, "card_stats", None), "name", "")
        if stats_name:
            return str(stats_name)
        spell_name = getattr(entity, "spell_name", "")
        if spell_name:
            return str(spell_name)
        source_name = getattr(entity, "source_name", "")
        return "" if source_name in {None, "", "Unknown"} else str(source_name)

    def _build_terrain_planes(self, player_id: int) -> np.ndarray:
        planes = np.zeros((3, BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        blocked_tiles = set(TileGrid.BLOCKED_TILES)

        # Build from canonical-space perspective.
        for world_x in range(BOARD_WIDTH):
            for world_y in range(BOARD_HEIGHT):
                x, y = self._world_to_canonical_tile(world_x, world_y, player_id)
                if (world_x, world_y) in blocked_tiles:
                    planes[0, y, x] = 1.0

                on_river = 15.0 <= (world_y + 0.5) < 17.0
                if on_river:
                    planes[1, y, x] = 1.0

                on_bridge = on_river and (
                    2.0 <= (world_x + 0.5) < 5.0 or 13.0 <= (world_x + 0.5) < 16.0
                )
                if on_bridge:
                    planes[2, y, x] = 1.0

        return planes

    def _encode_visible_card_slots(self, battle: BattleState, player_id: int) -> np.ndarray:
        """Encode the four hand cards and the player's public next-card preview."""
        card_vec = np.zeros(
            (NUM_HAND_SLOTS + 1) * len(self.card_vocab),
            dtype=np.float32,
        )
        player = battle.players[player_id]
        cards = list(player.hand[:NUM_HAND_SLOTS])
        cards.append(player.cycle_queue[0] if player.cycle_queue else None)
        for slot, card_name in enumerate(cards):
            if card_name is None:
                continue
            card_idx = self._card_to_idx.get(card_name)
            if card_idx is None:
                resolved = resolve_card_name(card_name)
                card_idx = self._card_to_idx.get(resolved)
            if card_idx is None:
                continue
            card_vec[slot * len(self.card_vocab) + card_idx] = 1.0
        return card_vec

    def _build_hud(self, battle: BattleState, player_id: int) -> np.ndarray:
        own = battle.players[player_id]
        opp = battle.players[1 - player_id]

        own_total_hp = own.king_tower_hp + own.left_tower_hp + own.right_tower_hp
        opp_total_hp = opp.king_tower_hp + opp.left_tower_hp + opp.right_tower_hp

        own_start_hp = float(battle._starting_total_tower_hp.get(player_id, max(1.0, own_total_hp)))
        opp_start_hp = float(battle._starting_total_tower_hp.get(1 - player_id, max(1.0, opp_total_hp)))

        ability_cooldown = 0.0
        ability_duration = 0.0
        found = battle._champion_ability_mechanic(player_id)
        if found is not None:
            entity, mechanic = found
            ability = mechanic.ability
            ability_cooldown = ability.get_cooldown_remaining(battle) / max(1.0, ability.cooldown_ms)
            ability_duration = ability.get_duration_remaining(battle) / max(1.0, ability.duration_ms)

        # Visible HUD only.
        scalars = np.array(
            [
                min(1.0, battle.time / battle.tiebreaker_time),
                1.0 if battle.double_elixir else 0.0,
                1.0 if battle.triple_elixir else 0.0,
                1.0 if battle.overtime else 0.0,
                own.elixir / max(1.0, own.max_elixir),
                battle.get_crown_count(player_id) / 3.0,
                battle.get_crown_count(1 - player_id) / 3.0,
                own_total_hp / max(1.0, own_start_hp),
                opp_total_hp / max(1.0, opp_start_hp),
                min(1.0, battle.time / battle.tiebreaker_time),
                float(np.clip(ability_cooldown, 0.0, 1.0)),
                float(np.clip(ability_duration, 0.0, 1.0)),
            ],
            dtype=np.float32,
        )

        return np.concatenate(
            [scalars, self._encode_visible_card_slots(battle, player_id)],
            dtype=np.float32,
        )

    def build(self, battle: BattleState, player_id: int) -> CvObservation:
        board = np.zeros((self.BOARD_CHANNELS, BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        board[:3] = self._terrain_planes[player_id]

        for entity in battle.entities.values():
            if not entity.is_alive:
                continue
            if not entity.is_visible_to(player_id):
                continue

            canonical_tile = self._position_to_canonical_tile(entity.position, player_id)
            if canonical_tile is None:
                continue
            x, y = canonical_tile

            own_entity = entity.player_id == player_id
            hp_norm = float(entity.hitpoints / max(1.0, entity.max_hitpoints))

            if isinstance(entity, Building):
                name = self._visible_entity_name(entity)
                if name in {"Tower", "KingTower"}:
                    channel = 3 if own_entity else 4
                else:
                    channel = 5 if own_entity else 6
            elif isinstance(entity, Troop):
                if is_airborne_target(entity):
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

            name = self._visible_entity_name(entity)
            identity = self._entity_name_to_value.get(name)
            if identity is None:
                identity = self._entity_name_to_value.get(resolve_card_name(name), 0.0)
            identity_channel = 15 if own_entity else 16
            board[identity_channel, y, x] = max(board[identity_channel, y, x], identity)

            shield_fraction = 0.0
            for mechanic in getattr(entity, "mechanics", ()):
                maximum = float(getattr(mechanic, "max_shield", 0) or 0)
                if maximum > 0:
                    shield_fraction = max(
                        shield_fraction,
                        float(getattr(mechanic, "current_shield", 0)) / maximum,
                    )
            shield_channel = 17 if own_entity else 18
            board[shield_channel, y, x] = max(board[shield_channel, y, x], shield_fraction)

            # A retracted Tesla is still visible as a trapdoor even though it
            # cannot be locked onto. Preserve that observable distinction so
            # the policy does not confuse a raised attacker with a dormant one.
            if isinstance(entity, Building) and getattr(entity, "_hidden_building", False):
                hidden_channel = 19 if own_entity else 20
                board[hidden_channel, y, x] = 1.0

            # Deployment is public from card placement. Pending characters
            # are already targetable, effectable, and collidable, but cannot
            # act themselves. Expose the remaining public countdown.
            if entity.placement_pending:
                total = float(getattr(entity, "placement_delay_total", 0.0) or 0.0)
                remaining = float(getattr(entity, "deploy_delay_remaining", 0.0) or 0.0)
                progress = min(1.0, remaining / total) if total > 0.0 else 1.0
                pending_channel = 21 if own_entity else 22
                board[pending_channel, y, x] = max(
                    board[pending_channel, y, x],
                    progress,
                )

            # These effects all have explicit, public animations in game.
            # Preserve their remaining durations: two otherwise identical
            # frames can require different decisions when Freeze, slow, or
            # Rage is about to expire.
            for timer, own_channel, enemy_channel in (
                (entity.stun_timer, 23, 24),
                (entity.slow_timer, 25, 26),
                (entity.haste_timer, 27, 28),
            ):
                if timer > 0.0:
                    channel = own_channel if own_entity else enemy_channel
                    board[channel, y, x] = max(
                        board[channel, y, x],
                        min(1.0, float(timer) / self.MAX_VISIBLE_STATUS_SECONDS),
                    )

            if (
                getattr(entity, "_special_move_active", False)
                or getattr(entity, "is_charging", False)
                or getattr(entity, "_river_jump_active", False)
            ):
                special_channel = 29 if own_entity else 30
                board[special_channel, y, x] = 1.0

            stealth_until = int(getattr(entity, "_stealth_until", 0) or 0)
            now_ms = logic_time_milliseconds(battle.time)
            if stealth_until > now_ms:
                stealth_channel = 31 if own_entity else 32
                board[stealth_channel, y, x] = 1.0

        hud = self._build_hud(battle, player_id)
        return CvObservation(board=board, hud=hud)
