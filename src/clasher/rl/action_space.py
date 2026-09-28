from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from clasher.arena import Position, TileGrid
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.placement import building_anchor
from clasher.spells import SPELL_REGISTRY
from clasher.unit_traits import is_air_unit_card

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES

# Reference switch used by parity and performance tests. The guarded path
# snapshots the exact capability-based set once per mask.
_USE_DEPLOYMENT_BLOCKER_GUARD = True


@dataclass(frozen=True)
class ActionSelection:
    action_id: int
    slot: int | None
    position: Position | None
    is_no_op: bool
    is_ability: bool = False


class DiscreteTileActionSpace:
    """Action space: (hand slot, tile) + no-op + champion ability.

    Action IDs:
    - `slot * NUM_TILES + tile` for deployment actions.
    - `NUM_HAND_SLOTS * NUM_TILES` for no-op.
    - `NUM_HAND_SLOTS * NUM_TILES + 1` for the active champion ability.
    """

    def __init__(self, canonical_perspective: bool = True) -> None:
        self.canonical_perspective = canonical_perspective
        placement_actions = NUM_HAND_SLOTS * NUM_TILES
        self.no_op_action = placement_actions
        self.ability_action = placement_actions + 1
        self.num_actions = placement_actions + 2
        self._positions_by_player: dict[int, list[Position]] = {0: [], 1: []}
        self._non_rolling_spell_tiles: dict[int, np.ndarray] = {}
        self._non_blocked_mask_by_player: dict[int, np.ndarray] = {}
        self._world_tile_xy_by_player: dict[int, np.ndarray] = {}
        self._card_meta_cache: dict[str, tuple[str, bool, object, bool]] = {}
        self._deploy_zone_mask_cache: dict[tuple[int, bool, bool], np.ndarray] = {}
        self._tower_mask_cache: dict[tuple[int, tuple[bool, bool, bool, bool, bool, bool]], np.ndarray] = {}
        blocked_tiles = set(TileGrid.BLOCKED_TILES)

        for player_id in (0, 1):
            positions: list[Position] = []
            spell_tiles: list[int] = []
            non_blocked_mask = np.zeros(NUM_TILES, dtype=np.bool_)
            world_xy = np.zeros((NUM_TILES, 2), dtype=np.int16)
            for cy in range(BOARD_HEIGHT):
                for cx in range(BOARD_WIDTH):
                    tile_idx = cy * BOARD_WIDTH + cx
                    wx, wy = self._canonical_to_world_tile(cx, cy, player_id)
                    pos = Position(wx + 0.5, wy + 0.5)
                    positions.append(pos)
                    world_xy[tile_idx] = (wx, wy)
                    tile_pos = (int(pos.x), int(pos.y))
                    if tile_pos not in blocked_tiles:
                        spell_tiles.append(tile_idx)
                        non_blocked_mask[tile_idx] = True
            self._positions_by_player[player_id] = positions
            self._non_rolling_spell_tiles[player_id] = np.asarray(spell_tiles, dtype=np.int64)
            self._non_blocked_mask_by_player[player_id] = non_blocked_mask
            self._world_tile_xy_by_player[player_id] = world_xy

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
        if action_id == self.ability_action:
            return ActionSelection(
                action_id=action_id,
                slot=None,
                position=None,
                is_no_op=False,
                is_ability=True,
            )

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
        card_stats,
        resolved_name: str,
        position: Position,
        is_spell: bool,
        spell_obj,
        probe_radius: float,
    ) -> bool:
        can_deploy_enemy_side = bool(
            not is_spell
            and getattr(card_stats, "can_deploy_on_enemy_side", False)
        )
        if can_deploy_enemy_side:
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

        deploy_w_margin = int(
            getattr(card_stats, "deploy_w_tile_margin", 0) or 0
        )
        if deploy_w_margin > 0:
            tile_x = int(position.x)
            if not (
                deploy_w_margin
                <= tile_x
                < battle.arena.width - deploy_w_margin
            ):
                return False

        if not is_spell:
            card_type = str(getattr(card_stats, "card_type", "") or "").lower()
            is_building_card = card_type == "building"
            if is_building_card:
                if battle.is_building_placement_occupied(
                    position, card_stats
                ) or battle.is_deployment_payload_occupied(
                    position,
                    card_stats=card_stats,
                ):
                    return False
            else:
                if battle.is_deployment_payload_occupied(
                    position,
                    mover_radius=probe_radius,
                ):
                    return False
                if not is_air_unit_card(card_stats):
                    return battle.resolve_ground_troop_anchor(position, player_id, card_stats) is not None
                if battle.is_position_occupied_by_building(position, probe_radius):
                    return False

        return True

    def _get_card_meta(self, battle: BattleState, card_name: str) -> tuple[str, bool, object, bool]:
        cached = self._card_meta_cache.get(card_name)
        if cached is not None:
            return cached
        resolved_name = resolve_card_name(card_name, battle.card_loader.load_card_definitions())
        is_spell = resolved_name in SPELL_REGISTRY
        spell_obj = SPELL_REGISTRY.get(resolved_name) if is_spell else None
        non_rolling_spell = bool(
            is_spell
            and not battle.arena._requires_deploy_zone_spell(spell_obj)
            and not getattr(spell_obj, "requires_walkable_target", False)
        )
        meta = (resolved_name, is_spell, spell_obj, non_rolling_spell)
        self._card_meta_cache[card_name] = meta
        return meta

    def _zone_key(self, battle: BattleState, player_id: int) -> tuple[int, bool, bool]:
        enemy_id = 1 - player_id
        enemy_left_dead = battle.players[enemy_id].left_tower_hp <= 0.0
        enemy_right_dead = battle.players[enemy_id].right_tower_hp <= 0.0
        return (player_id, enemy_left_dead, enemy_right_dead)

    def _zone_ranges_from_key(self, key: tuple[int, bool, bool]) -> list[tuple[int, int, int, int]]:
        player_id, enemy_left_dead, enemy_right_dead = key
        if player_id == 0:
            zones = [(0, 1, BOARD_WIDTH, 15), (6, 0, 12, 6)]
            if enemy_left_dead:
                zones.append((0, 17, 9, 21))
            if enemy_right_dead:
                zones.append((9, 17, BOARD_WIDTH, 21))
            return zones
        zones = [(0, 17, BOARD_WIDTH, 31), (6, 26, 12, 32)]
        if enemy_left_dead:
            zones.append((0, 11, 9, 15))
        if enemy_right_dead:
            zones.append((9, 11, BOARD_WIDTH, 15))
        return zones

    def _deploy_zone_mask(self, battle: BattleState, player_id: int) -> np.ndarray:
        key = self._zone_key(battle, player_id)
        cached = self._deploy_zone_mask_cache.get(key)
        if cached is not None:
            return cached
        mask = np.zeros(NUM_TILES, dtype=np.bool_)
        zones = self._zone_ranges_from_key(key)
        for tile_idx, pos in enumerate(self._positions_by_player[player_id]):
            x = pos.x
            y = pos.y
            for x1, y1, x2, y2 in zones:
                if x1 <= x < x2 and y1 <= y < y2:
                    mask[tile_idx] = True
                    break
        self._deploy_zone_mask_cache[key] = mask
        return mask

    def _tower_mask(self, battle: BattleState, player_id: int) -> np.ndarray:
        tower_state = battle._tower_alive_flags() if hasattr(battle, "_tower_alive_flags") else (
            battle.players[0].left_tower_hp > 0.0,
            battle.players[0].right_tower_hp > 0.0,
            battle.players[0].king_tower_hp > 0.0,
            battle.players[1].left_tower_hp > 0.0,
            battle.players[1].right_tower_hp > 0.0,
            battle.players[1].king_tower_hp > 0.0,
        )
        key = (player_id, tower_state)
        cached = self._tower_mask_cache.get(key)
        if cached is not None:
            return cached
        world_mask = battle.get_tower_tile_mask_world() if hasattr(battle, "get_tower_tile_mask_world") else None
        out = np.zeros(NUM_TILES, dtype=np.bool_)
        if world_mask is not None:
            world_xy = self._world_tile_xy_by_player[player_id]
            for tile_idx in range(NUM_TILES):
                wx = int(world_xy[tile_idx, 0])
                wy = int(world_xy[tile_idx, 1])
                out[tile_idx] = bool(world_mask[wy, wx])
        else:
            for tile_idx, pos in enumerate(self._positions_by_player[player_id]):
                out[tile_idx] = battle.arena.is_tower_tile(pos, battle)
        self._tower_mask_cache[key] = out
        return out

    def _building_placement_blocked_mask_canonical(
        self,
        battle: BattleState,
        player_id: int,
        size_tiles: int,
    ) -> np.ndarray:
        world_mask = battle.get_building_placement_blocked_mask_world(size_tiles)
        resolved = [
            building_anchor(p, size_tiles)
            for p in self._positions_by_player[player_id]
        ]
        world_xy = np.asarray([(int(p.x), int(p.y)) for p in resolved], dtype=np.int32)
        return np.asarray(
            world_mask[world_xy[:, 1], world_xy[:, 0]], dtype=np.bool_
        )

    def _troop_placement_blocked_mask_canonical(
        self,
        battle: BattleState,
        player_id: int,
        mover_radius: float,
    ) -> np.ndarray:
        world_mask = battle.get_troop_placement_blocked_mask_world(mover_radius)
        world_xy = self._world_tile_xy_by_player[player_id]
        return np.asarray(
            world_mask[world_xy[:, 1], world_xy[:, 0]], dtype=np.bool_
        )

    def _legal_action_mask_legacy(self, battle: BattleState, player_id: int) -> np.ndarray:
        mask = np.zeros(self.num_actions, dtype=np.bool_)
        mask[self.no_op_action] = True
        mask[self.ability_action] = battle.can_activate_champion_ability(player_id)

        player = battle.players[player_id]
        for slot, card_name in enumerate(player.hand[:NUM_HAND_SLOTS]):
            if card_name is None:
                continue
            play = battle.resolve_card_play(player_id, card_name)
            if play is None:
                continue
            effective_name, card_stats, _ = play

            if not player.can_play_card(card_name, card_stats):
                continue

            resolved_name, is_spell, spell_obj, non_rolling_spell = self._get_card_meta(
                battle, effective_name
            )
            slot_base = slot * NUM_TILES

            if non_rolling_spell:
                spell_tiles = self._non_rolling_spell_tiles[player_id]
                mask[slot_base + spell_tiles] = True
                continue

            probe_radius = float(getattr(card_stats, "collision_radius", 0.5) or 0.5)
            positions = self._positions_by_player[player_id]
            for tile_idx, pos in enumerate(positions):
                if self._is_legal_deploy(
                    battle=battle,
                    player_id=player_id,
                    card_stats=card_stats,
                    resolved_name=resolved_name,
                    position=pos,
                    is_spell=is_spell,
                    spell_obj=spell_obj,
                    probe_radius=probe_radius,
                ):
                    mask[slot_base + tile_idx] = True
        return mask

    def _legal_action_mask_fast(self, battle: BattleState, player_id: int) -> np.ndarray:
        mask = np.zeros(self.num_actions, dtype=np.bool_)
        mask[self.no_op_action] = True
        mask[self.ability_action] = battle.can_activate_champion_ability(player_id)

        non_blocked = self._non_blocked_mask_by_player[player_id]
        zone_mask = self._deploy_zone_mask(battle, player_id)
        tower_mask = self._tower_mask(battle, player_id)
        deploy_mask = zone_mask & non_blocked
        deploy_mask_no_tower = deploy_mask & (~tower_mask)
        deployment_blockers = (
            tuple(
                entity
                for entity in battle.entities.values()
                if entity.is_alive
                and bool(getattr(entity, "blocks_deployment", False))
            )
            if _USE_DEPLOYMENT_BLOCKER_GUARD
            else None
        )
        has_deployment_blockers = (
            bool(deployment_blockers)
            if deployment_blockers is not None
            else True
        )
        building_blocked_by_size: dict[int, np.ndarray] = {}
        troop_blocked_by_radius: dict[float, np.ndarray] = {}

        player = battle.players[player_id]
        for slot, card_name in enumerate(player.hand[:NUM_HAND_SLOTS]):
            if card_name is None:
                continue
            play = battle.resolve_card_play(player_id, card_name)
            if play is None:
                continue
            effective_name, card_stats, _ = play
            if not player.can_play_card(card_name, card_stats):
                continue

            resolved_name, is_spell, spell_obj, non_rolling_spell = self._get_card_meta(
                battle, effective_name
            )
            slot_base = slot * NUM_TILES
            if non_rolling_spell:
                spell_tiles = self._non_rolling_spell_tiles[player_id]
                mask[slot_base + spell_tiles] = True
                continue

            card_type = str(getattr(card_stats, "card_type", "") or "").lower()
            is_building_card = (not is_spell) and (card_type == "building")
            probe_radius = float(getattr(card_stats, "collision_radius", 0.5) or 0.5)
            can_deploy_enemy_side = bool(
                not is_spell
                and getattr(card_stats, "can_deploy_on_enemy_side", False)
            )
            if can_deploy_enemy_side:
                # Enemy-side troop cards still exclude blocked and live tower
                # tiles. Build this candidate set
                # before exact occupancy checks instead of intersecting it
                # with the ordinary friendly deployment zone.
                candidate_mask = non_blocked & (~tower_mask)
            else:
                if not is_spell:
                    candidate_mask = deploy_mask_no_tower
                elif (
                    getattr(spell_obj, "requires_walkable_target", False)
                    and not battle.arena._requires_deploy_zone_spell(spell_obj)
                ):
                    # Arena-wide payload spells start from every non-fence
                    # tile; their terrain capability is checked exactly below.
                    candidate_mask = non_blocked
                else:
                    candidate_mask = deploy_mask

            blocked_building_tiles = None
            if is_building_card:
                size_tiles = battle._building_footprint_size_tiles(card_stats)
                blocked_building_tiles = building_blocked_by_size.get(size_tiles)
                if blocked_building_tiles is None:
                    blocked_building_tiles = (
                        self._building_placement_blocked_mask_canonical(
                            battle, player_id, size_tiles
                        )
                    )
                    building_blocked_by_size[size_tiles] = blocked_building_tiles
                candidate_mask = candidate_mask & (~blocked_building_tiles)
            elif not is_spell and is_air_unit_card(card_stats):
                blocked_troop_tiles = troop_blocked_by_radius.get(probe_radius)
                if blocked_troop_tiles is None:
                    blocked_troop_tiles = self._troop_placement_blocked_mask_canonical(
                        battle, player_id, probe_radius
                    )
                    troop_blocked_by_radius[probe_radius] = blocked_troop_tiles
                candidate_mask = candidate_mask & (~blocked_troop_tiles)

            candidate_tiles = np.flatnonzero(candidate_mask)
            positions = self._positions_by_player[player_id]
            deploy_w_margin = int(
                getattr(card_stats, "deploy_w_tile_margin", 0) or 0
            )
            for tile_idx in candidate_tiles.tolist():
                pos = positions[tile_idx]
                if not is_spell and not is_building_card and not is_air_unit_card(card_stats):
                    if self._is_legal_deploy(
                        battle, player_id, card_stats, resolved_name, pos,
                        is_spell, spell_obj, probe_radius,
                    ):
                        mask[slot_base + tile_idx] = True
                    continue
                if deploy_w_margin > 0:
                    world_tile_x = int(pos.x)
                    if not (
                        deploy_w_margin
                        <= world_tile_x
                        < battle.arena.width - deploy_w_margin
                    ):
                        continue
                if can_deploy_enemy_side:
                    tile_pos = (int(pos.x), int(pos.y))
                    if tile_pos in battle.arena.BLOCKED_TILES:
                        continue
                    if battle.arena.is_tower_tile(pos, battle):
                        continue
                if (
                    is_building_card
                    and has_deployment_blockers
                    and battle.is_deployment_payload_occupied(
                        pos,
                        card_stats=card_stats,
                        deployment_blockers=deployment_blockers,
                    )
                ):
                    continue
                if (
                    not is_spell
                    and not is_building_card
                    and has_deployment_blockers
                    and battle.is_deployment_payload_occupied(
                        pos,
                        mover_radius=probe_radius,
                        deployment_blockers=deployment_blockers,
                    )
                ):
                    continue
                if (
                    is_spell
                    and (
                        battle.arena._requires_deploy_zone_spell(spell_obj)
                        or getattr(spell_obj, "requires_walkable_target", False)
                    )
                    and not battle.arena.can_deploy_at(pos, player_id, battle, True, spell_obj)
                ):
                    continue
                mask[slot_base + tile_idx] = True
        return mask

    def legal_action_mask(
        self,
        battle: BattleState,
        player_id: int,
        *,
        fast_path: bool | None = None,
    ) -> np.ndarray:
        use_fast = fast_path if fast_path is not None else bool(getattr(battle, "fast_path", False))
        if use_fast:
            return self._legal_action_mask_fast(battle, player_id)
        return self._legal_action_mask_legacy(battle, player_id)

    def apply_action(self, battle: BattleState, player_id: int, action_id: int) -> bool:
        # ``decode_action`` intentionally maps malformed IDs to a safe no-op
        # selection for callers that only need to inspect an action. Applying
        # one is different: an out-of-range policy output was not a successful
        # no-op and must remain visible to self-play's invalid-action handling.
        if action_id < 0 or action_id >= self.num_actions:
            return False
        decoded = self.decode_action(action_id, player_id)
        if decoded.is_no_op:
            return True
        if decoded.is_ability:
            return battle.activate_champion_ability(player_id)

        assert decoded.slot is not None
        assert decoded.position is not None

        hand = battle.players[player_id].hand
        if decoded.slot >= len(hand):
            return False

        card_name = hand[decoded.slot]
        if card_name is None:
            return False
        return battle.deploy_card(player_id, card_name, decoded.position)

    def random_legal_action(
        self,
        battle: BattleState,
        player_id: int,
        rng: np.random.Generator,
        *,
        fast_path: bool | None = None,
    ) -> int:
        mask = self.legal_action_mask(battle, player_id, fast_path=fast_path)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            return self.no_op_action
        return int(rng.choice(legal))
