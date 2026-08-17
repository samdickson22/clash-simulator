"""Batched, data-driven action decoding and deployment legality kernels.

This module deliberately separates synchronization from execution.  Python
``BattleState`` objects can be projected into :class:`TensorActionState` for
differential checking, while the legality and ingress operations themselves
only read dense tensors.  A future fully tensor-native battle state can fill
the same schema without entering Python's object graph.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch

from clasher.card_aliases import resolve_card_name
from clasher.entities import Building
from clasher.kinematics import LOGIC_UNITS_PER_TILE, tiles_to_logic_units
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from clasher.spells import SPELL_REGISTRY, RollingProjectileSpell

from .catalog import CardKindOpcode, TensorCardCatalog

if TYPE_CHECKING:
    from clasher.battle import BattleState


NO_OP_ACTION = NUM_HAND_SLOTS * NUM_TILES
ABILITY_ACTION = NO_OP_ACTION + 1
NUM_ACTIONS = NO_OP_ACTION + 2


def _device_tensor(
    values: object,
    *,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    return torch.as_tensor(values, dtype=dtype, device=device)


@dataclass(frozen=True)
class TensorActionCatalog:
    """Placement-specific card metadata derived from serialized definitions."""

    cards: TensorCardCatalog
    is_spell: torch.Tensor
    spell_requires_territory: torch.Tensor
    spell_requires_walkable_target: torch.Tensor
    building_footprint_half_units: torch.Tensor

    @classmethod
    def compile(cls, cards: TensorCardCatalog) -> TensorActionCatalog:
        device = cards.device
        size = len(cards.names)
        is_spell = torch.zeros(size, dtype=torch.bool, device=device)
        requires_territory = torch.zeros(size, dtype=torch.bool, device=device)
        requires_walkable = torch.zeros(size, dtype=torch.bool, device=device)
        footprint_half = torch.zeros(size, dtype=torch.int32, device=device)

        for card_id, name in enumerate(cards.names[1:], start=1):
            spell = SPELL_REGISTRY.get(name)
            if spell is not None:
                is_spell[card_id] = True
                requires_territory[card_id] = bool(
                    getattr(spell, "requires_territory", False)
                    or isinstance(spell, RollingProjectileSpell)
                )
                requires_walkable[card_id] = bool(
                    getattr(spell, "requires_walkable_target", False)
                )
            if int(cards.kind[card_id].item()) == int(CardKindOpcode.BUILDING):
                radius = max(
                    0.0,
                    float(cards.collision_radius_units[card_id].item())
                    / LOGIC_UNITS_PER_TILE,
                )
                footprint_tiles = max(1, math.ceil(radius * 2.0) + 1)
                footprint_half[card_id] = footprint_tiles * LOGIC_UNITS_PER_TILE // 2

        return cls(
            cards=cards,
            is_spell=is_spell,
            spell_requires_territory=requires_territory,
            spell_requires_walkable_target=requires_walkable,
            building_footprint_half_units=footprint_half,
        )


@dataclass
class TensorActionState:
    """Mutable batched inputs needed by deployment legality and card cycling."""

    hand_ids: torch.Tensor
    cycle_ids: torch.Tensor
    cycle_length: torch.Tensor
    elixir: torch.Tensor
    player_alive: torch.Tensor
    tower_alive: torch.Tensor
    ability_legal: torch.Tensor
    building_alive: torch.Tensor
    building_x_units: torch.Tensor
    building_y_units: torch.Tensor
    building_collision_radius_units: torch.Tensor
    building_footprint_half_units: torch.Tensor
    blocker_alive: torch.Tensor
    blocker_x_units: torch.Tensor
    blocker_y_units: torch.Tensor
    blocker_radius_units: torch.Tensor
    supported: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.hand_ids.device

    @property
    def batch_size(self) -> int:
        return int(self.hand_ids.shape[0])

    @classmethod
    def from_battles(
        cls,
        battles: Sequence[BattleState],
        catalog: TensorActionCatalog,
    ) -> TensorActionState:
        """Project oracle states into the tensor schema.

        Unsupported hand/cycle cards are represented by padding and mark only
        that player unsupported, so the caller can fail closed to Python.
        """

        device = catalog.cards.device
        batch_size = len(battles)
        max_cycle = max(
            1,
            max(
                (
                    len(player.cycle_queue)
                    for battle in battles
                    for player in battle.players
                ),
                default=0,
            )
            + 1,
        )
        max_buildings = max(
            1,
            max(
                (
                    sum(
                        isinstance(entity, Building) and entity.is_alive
                        for entity in battle.entities.values()
                    )
                    for battle in battles
                ),
                default=0,
            ),
        )
        max_blockers = max(
            1,
            max(
                (
                    sum(
                        entity.is_alive
                        and bool(getattr(entity, "blocks_deployment", False))
                        for entity in battle.entities.values()
                    )
                    for battle in battles
                ),
                default=0,
            ),
        )

        shape_players = (batch_size, 2)
        hand_ids = torch.zeros(
            (*shape_players, NUM_HAND_SLOTS), dtype=torch.int64, device=device
        )
        cycle_ids = torch.zeros(
            (*shape_players, max_cycle), dtype=torch.int64, device=device
        )
        cycle_length = torch.zeros(shape_players, dtype=torch.int64, device=device)
        elixir = torch.zeros(shape_players, dtype=torch.float64, device=device)
        player_alive = torch.zeros(shape_players, dtype=torch.bool, device=device)
        tower_alive = torch.zeros((*shape_players, 3), dtype=torch.bool, device=device)
        ability_legal = torch.zeros(shape_players, dtype=torch.bool, device=device)
        supported = torch.ones(shape_players, dtype=torch.bool, device=device)

        entity_shape = (batch_size, max_buildings)
        building_alive = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        building_x = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        building_y = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        building_radius = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        building_half = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        blocker_shape = (batch_size, max_blockers)
        blocker_alive = torch.zeros(blocker_shape, dtype=torch.bool, device=device)
        blocker_x = torch.zeros(blocker_shape, dtype=torch.int32, device=device)
        blocker_y = torch.zeros(blocker_shape, dtype=torch.int32, device=device)
        blocker_radius = torch.zeros(blocker_shape, dtype=torch.int32, device=device)

        definitions = battles[0].card_loader.load_card_definitions() if battles else {}
        for battle_index, battle in enumerate(battles):
            standard_arena = (
                battle.arena.width == BOARD_WIDTH
                and battle.arena.height == BOARD_HEIGHT
            )
            for player_id, player in enumerate(battle.players):
                if not standard_arena:
                    supported[battle_index, player_id] = False
                elixir[battle_index, player_id] = float(player.elixir)
                player_alive[battle_index, player_id] = player.king_tower_hp > 0.0
                tower_alive[battle_index, player_id] = _device_tensor(
                    (
                        player.left_tower_hp > 0.0,
                        player.right_tower_hp > 0.0,
                        player.king_tower_hp > 0.0,
                    ),
                    dtype=torch.bool,
                    device=device,
                )
                ability_legal[battle_index, player_id] = bool(
                    battle.can_activate_champion_ability(player_id)
                )
                for slot, card_name in enumerate(player.hand[:NUM_HAND_SLOTS]):
                    if card_name is None:
                        continue
                    resolved = resolve_card_name(card_name, definitions)
                    card_id = catalog.cards.name_to_id.get(resolved)
                    if card_id is None:
                        supported[battle_index, player_id] = False
                    else:
                        hand_ids[battle_index, player_id, slot] = card_id
                cycle_length[battle_index, player_id] = len(player.cycle_queue)
                for slot, card_name in enumerate(player.cycle_queue):
                    resolved = resolve_card_name(card_name, definitions)
                    card_id = catalog.cards.name_to_id.get(resolved)
                    if card_id is None:
                        supported[battle_index, player_id] = False
                    else:
                        cycle_ids[battle_index, player_id, slot] = card_id

            building_slot = 0
            blocker_slot = 0
            for entity in battle.entities.values():
                if not entity.is_alive:
                    continue
                if isinstance(entity, Building):
                    building_alive[battle_index, building_slot] = True
                    building_x[battle_index, building_slot] = tiles_to_logic_units(
                        entity.position.x
                    )
                    building_y[battle_index, building_slot] = tiles_to_logic_units(
                        entity.position.y
                    )
                    radius = max(
                        0.0,
                        float(
                            getattr(entity.card_stats, "collision_radius", 1.0) or 1.0
                        ),
                    )
                    building_radius[battle_index, building_slot] = tiles_to_logic_units(
                        radius
                    )
                    size_tiles = max(1, math.ceil(radius * 2.0) + 1)
                    building_half[battle_index, building_slot] = (
                        size_tiles * LOGIC_UNITS_PER_TILE // 2
                    )
                    building_slot += 1
                if bool(getattr(entity, "blocks_deployment", False)):
                    blocker_alive[battle_index, blocker_slot] = True
                    blocker_x[battle_index, blocker_slot] = tiles_to_logic_units(
                        entity.position.x
                    )
                    blocker_y[battle_index, blocker_slot] = tiles_to_logic_units(
                        entity.position.y
                    )
                    blocker_radius[battle_index, blocker_slot] = tiles_to_logic_units(
                        float(
                            getattr(entity, "deployment_collision_radius", 0.5) or 0.5
                        )
                    )
                    blocker_slot += 1

        return cls(
            hand_ids=hand_ids,
            cycle_ids=cycle_ids,
            cycle_length=cycle_length,
            elixir=elixir,
            player_alive=player_alive,
            tower_alive=tower_alive,
            ability_legal=ability_legal,
            building_alive=building_alive,
            building_x_units=building_x,
            building_y_units=building_y,
            building_collision_radius_units=building_radius,
            building_footprint_half_units=building_half,
            blocker_alive=blocker_alive,
            blocker_x_units=blocker_x,
            blocker_y_units=blocker_y,
            blocker_radius_units=blocker_radius,
            supported=supported,
        )


@dataclass(frozen=True)
class TensorActionSelection:
    action_ids: torch.Tensor
    valid_input: torch.Tensor
    is_no_op: torch.Tensor
    is_ability: torch.Tensor
    slot: torch.Tensor
    tile: torch.Tensor
    world_x_units: torch.Tensor
    world_y_units: torch.Tensor


@dataclass(frozen=True)
class TensorCommandQueue:
    """Accepted commands in stable battle-major, player-minor order."""

    sequence: torch.Tensor
    battle_index: torch.Tensor
    player_id: torch.Tensor
    action_id: torch.Tensor
    card_id: torch.Tensor
    card_kind: torch.Tensor
    slot: torch.Tensor
    world_x_units: torch.Tensor
    world_y_units: torch.Tensor
    is_ability: torch.Tensor


@dataclass(frozen=True)
class TensorIngressResult:
    accepted: torch.Tensor
    selection: TensorActionSelection
    commands: TensorCommandQueue
    hand_ids: torch.Tensor
    cycle_ids: torch.Tensor
    cycle_length: torch.Tensor
    elixir: torch.Tensor


class TensorActionKernel:
    """Pure tensor action-mask, decode, and ingress implementation."""

    def __init__(
        self,
        catalog: TensorActionCatalog,
        *,
        canonical_perspective: bool = True,
    ) -> None:
        self.catalog = catalog
        self.canonical_perspective = canonical_perspective
        self.device = catalog.cards.device
        canonical_x = torch.arange(NUM_TILES, device=self.device) % BOARD_WIDTH
        canonical_y = torch.arange(NUM_TILES, device=self.device) // BOARD_WIDTH
        player = torch.arange(2, device=self.device)[:, None]
        if canonical_perspective:
            flip = player == 1
            world_x = torch.where(flip, BOARD_WIDTH - 1 - canonical_x, canonical_x)
            world_y = torch.where(flip, BOARD_HEIGHT - 1 - canonical_y, canonical_y)
        else:
            world_x = canonical_x.expand(2, -1)
            world_y = canonical_y.expand(2, -1)
        self.world_x = world_x.to(torch.int64)
        self.world_y = world_y.to(torch.int64)
        self.world_x_units = self.world_x * LOGIC_UNITS_PER_TILE + 500
        self.world_y_units = self.world_y * LOGIC_UNITS_PER_TILE + 500

        blocked = torch.zeros(
            (BOARD_HEIGHT, BOARD_WIDTH), dtype=torch.bool, device=self.device
        )
        blocked_xy = (
            (0, 14),
            (0, 17),
            (17, 14),
            (17, 17),
            *((x, 0) for x in (*range(6), *range(12, 18))),
            *((x, 31) for x in (*range(6), *range(12, 18))),
        )
        for x, y in blocked_xy:
            blocked[y, x] = True
        self.non_blocked = ~blocked[self.world_y, self.world_x]
        in_river = (self.world_y_units >= 15_000) & (self.world_y_units <= 17_000)
        on_bridge = ((self.world_x_units >= 2_000) & (self.world_x_units <= 5_000)) | (
            (self.world_x_units >= 13_000) & (self.world_x_units <= 16_000)
        )
        self.walkable = self.non_blocked & (~in_river | on_bridge)

    def decode(self, action_ids: torch.Tensor) -> TensorActionSelection:
        action_ids = action_ids.to(device=self.device, dtype=torch.int64)
        valid = (action_ids >= 0) & (action_ids < NUM_ACTIONS)
        placement = valid & (action_ids < NO_OP_ACTION)
        safe_action = torch.where(placement, action_ids, torch.zeros_like(action_ids))
        slot = safe_action // NUM_TILES
        tile = safe_action % NUM_TILES
        player = torch.arange(2, device=self.device).view(1, 2).expand_as(action_ids)
        world_x = self.world_x[player, tile]
        world_y = self.world_y[player, tile]
        return TensorActionSelection(
            action_ids=action_ids,
            valid_input=valid,
            is_no_op=(action_ids == NO_OP_ACTION) | ~valid,
            is_ability=action_ids == ABILITY_ACTION,
            slot=torch.where(placement, slot, torch.full_like(slot, -1)),
            tile=torch.where(placement, tile, torch.full_like(tile, -1)),
            world_x_units=torch.where(
                placement,
                world_x * LOGIC_UNITS_PER_TILE + 500,
                torch.zeros_like(world_x),
            ),
            world_y_units=torch.where(
                placement,
                world_y * LOGIC_UNITS_PER_TILE + 500,
                torch.zeros_like(world_y),
            ),
        )

    def _deploy_zone(self, state: TensorActionState) -> torch.Tensor:
        x = self.world_x.view(1, 2, NUM_TILES)
        y = self.world_y.view(1, 2, NUM_TILES)
        player = torch.arange(2, device=self.device).view(1, 2, 1)
        base_blue = ((y >= 1) & (y < 15)) | ((x >= 6) & (x < 12) & (y >= 0) & (y < 6))
        base_red = ((y >= 17) & (y < 31)) | ((x >= 6) & (x < 12) & (y >= 26) & (y < 32))
        base = torch.where(player == 0, base_blue, base_red)
        enemy = 1 - player.expand(state.batch_size, 2, 1)
        tower = state.tower_alive.gather(1, enemy.expand(-1, -1, 3))
        enemy_left_dead = ~tower[:, :, 0:1]
        enemy_right_dead = ~tower[:, :, 1:2]
        extra_blue = (enemy_left_dead & (x < 9) & (y >= 17) & (y < 21)) | (
            enemy_right_dead & (x >= 9) & (y >= 17) & (y < 21)
        )
        extra_red = (enemy_left_dead & (x < 9) & (y >= 11) & (y < 15)) | (
            enemy_right_dead & (x >= 9) & (y >= 11) & (y < 15)
        )
        return base | torch.where(player == 0, extra_blue, extra_red)

    def _tower_blocked(self, state: TensorActionState) -> torch.Tensor:
        centers = _device_tensor(
            (
                (3_500, 6_500, 1_500),
                (14_500, 6_500, 1_500),
                (9_000, 2_500, 2_000),
                (3_500, 25_500, 1_500),
                (14_500, 25_500, 1_500),
                (9_000, 29_500, 2_000),
            ),
            dtype=torch.int64,
            device=self.device,
        )
        x = self.world_x_units.view(1, 2, NUM_TILES, 1)
        y = self.world_y_units.view(1, 2, NUM_TILES, 1)
        cx = centers[:, 0].view(1, 1, 1, 6)
        cy = centers[:, 1].view(1, 1, 1, 6)
        radius = centers[:, 2].view(1, 1, 1, 6)
        covered = (torch.abs(x - cx) <= radius) & (torch.abs(y - cy) <= radius)
        alive = state.tower_alive.reshape(state.batch_size, 1, 1, 6)
        # Every player's deployment candidates are blocked by both sides' towers.
        return (covered & alive).any(dim=-1)

    def _building_occupancy(
        self,
        state: TensorActionState,
        card_ids: torch.Tensor,
        is_building: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        batch_size = state.batch_size
        tile_x = self.world_x_units.view(1, 2, 1, NUM_TILES, 1)
        tile_y = self.world_y_units.view(1, 2, 1, NUM_TILES, 1)
        existing_x = state.building_x_units.view(batch_size, 1, 1, 1, -1)
        existing_y = state.building_y_units.view(batch_size, 1, 1, 1, -1)
        existing_half = state.building_footprint_half_units.view(
            batch_size, 1, 1, 1, -1
        )
        existing_radius = state.building_collision_radius_units.view(
            batch_size, 1, 1, 1, -1
        )
        existing_alive = state.building_alive.view(batch_size, 1, 1, 1, -1)

        new_half = self.catalog.building_footprint_half_units[card_ids].view(
            batch_size, 2, NUM_HAND_SLOTS, 1, 1
        )
        footprint_overlap = (
            existing_alive
            & (torch.abs(tile_x - existing_x) < new_half + existing_half)
            & (torch.abs(tile_y - existing_y) < new_half + existing_half)
        ).any(dim=-1)

        radius = self.catalog.cards.collision_radius_units[card_ids].to(torch.int64)
        radius = torch.where(radius > 0, radius, torch.full_like(radius, 500)).view(
            batch_size, 2, NUM_HAND_SLOTS, 1, 1
        )
        dx = tile_x - existing_x
        dy = tile_y - existing_y
        combined = radius + existing_radius
        # Existing buildings use circular movement collision, not their AABB.
        troop_overlap = (
            existing_alive & (dx * dx + dy * dy < combined * combined)
        ).any(dim=-1)
        return footprint_overlap & is_building[..., None], troop_overlap

    def _payload_occupancy(
        self,
        state: TensorActionState,
        card_ids: torch.Tensor,
        is_building: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        batch_size = state.batch_size
        tile_x = self.world_x_units.view(1, 2, 1, NUM_TILES, 1)
        tile_y = self.world_y_units.view(1, 2, 1, NUM_TILES, 1)
        blocker_x = state.blocker_x_units.view(batch_size, 1, 1, 1, -1)
        blocker_y = state.blocker_y_units.view(batch_size, 1, 1, 1, -1)
        blocker_radius = state.blocker_radius_units.view(batch_size, 1, 1, 1, -1)
        alive = state.blocker_alive.view(batch_size, 1, 1, 1, -1)

        troop_radius = self.catalog.cards.collision_radius_units[card_ids].to(
            torch.int64
        )
        troop_radius = torch.where(
            troop_radius > 0, troop_radius, torch.full_like(troop_radius, 500)
        ).view(batch_size, 2, NUM_HAND_SLOTS, 1, 1)
        dx = tile_x - blocker_x
        dy = tile_y - blocker_y
        combined = troop_radius + blocker_radius
        troop_overlap = (alive & (dx * dx + dy * dy <= combined * combined)).any(dim=-1)

        half = self.catalog.building_footprint_half_units[card_ids].to(torch.int64)
        half = half.view(batch_size, 2, NUM_HAND_SLOTS, 1, 1)
        outside_x = torch.clamp(torch.abs(dx) - half, min=0)
        outside_y = torch.clamp(torch.abs(dy) - half, min=0)
        building_overlap = (
            alive
            & (
                outside_x * outside_x + outside_y * outside_y
                <= blocker_radius * blocker_radius
            )
        ).any(dim=-1)
        return building_overlap & is_building[..., None], troop_overlap

    def legal_action_mask(self, state: TensorActionState) -> torch.Tensor:
        if state.hand_ids.shape != (state.batch_size, 2, NUM_HAND_SLOTS):
            raise ValueError("hand_ids must have shape [batch, 2, 4]")
        card_ids = state.hand_ids
        cards = self.catalog.cards
        kind = cards.kind[card_ids]
        is_spell = self.catalog.is_spell[card_ids]
        is_building = kind == int(CardKindOpcode.BUILDING)
        is_unit = (card_ids != 0) & ~is_spell
        affordable = state.elixir[..., None] >= cards.elixir[card_ids]
        playable = (
            (card_ids != 0)
            & affordable
            & state.player_alive[..., None]
            & state.supported[..., None]
        )

        non_blocked = self.non_blocked.view(1, 2, 1, NUM_TILES)
        walkable = self.walkable.view(1, 2, 1, NUM_TILES)
        zone = self._deploy_zone(state).unsqueeze(2)
        tower_blocked = self._tower_blocked(state).unsqueeze(2)
        enemy_side = cards.can_deploy_on_enemy_side[card_ids][..., None]
        requires_territory = self.catalog.spell_requires_territory[card_ids][..., None]
        requires_walkable = self.catalog.spell_requires_walkable_target[card_ids][
            ..., None
        ]

        ordinary_unit = zone & non_blocked & ~tower_blocked
        anywhere_unit = non_blocked & ~tower_blocked
        spell_candidates = (
            non_blocked
            & torch.where(
                requires_territory,
                zone,
                torch.ones_like(zone),
            )
            & torch.where(
                requires_walkable,
                walkable,
                torch.ones_like(walkable),
            )
        )
        candidates = torch.where(
            is_spell[..., None],
            spell_candidates,
            torch.where(enemy_side, anywhere_unit, ordinary_unit),
        )

        margin = cards.deploy_w_tile_margin[card_ids].to(torch.int64)[..., None]
        world_x = self.world_x.view(1, 2, 1, NUM_TILES)
        candidates &= (world_x >= margin) & (world_x < BOARD_WIDTH - margin)

        building_overlap, troop_overlap = self._building_occupancy(
            state, card_ids, is_building
        )
        payload_building, payload_troop = self._payload_occupancy(
            state, card_ids, is_building
        )
        candidates &= ~torch.where(
            is_building[..., None],
            building_overlap | payload_building,
            torch.where(
                is_unit[..., None],
                troop_overlap | payload_troop,
                torch.zeros_like(troop_overlap),
            ),
        )
        placements = candidates & playable[..., None]
        mask = torch.zeros(
            (state.batch_size, 2, NUM_ACTIONS),
            dtype=torch.bool,
            device=self.device,
        )
        mask[:, :, :NO_OP_ACTION] = placements.reshape(
            state.batch_size, 2, NO_OP_ACTION
        )
        mask[:, :, NO_OP_ACTION] = True
        mask[:, :, ABILITY_ACTION] = state.ability_legal & state.supported
        return mask

    def ingress(
        self,
        state: TensorActionState,
        action_ids: torch.Tensor,
        *,
        legal_mask: torch.Tensor | None = None,
    ) -> TensorIngressResult:
        """Validate actions and emit deterministic commands plus card transitions.

        Accepted placement commands update elixir/hand/cycle tensors. Ability
        commands are emitted but deliberately do not mutate those tensors;
        their mechanic-owned cost/cooldown transition is resolved downstream.
        Multiple deployments are emitted against the same pre-action snapshot
        and therefore require sequential downstream placement revalidation.
        """

        selection = self.decode(action_ids)
        if legal_mask is None:
            legal_mask = self.legal_action_mask(state)
        safe_action = selection.action_ids.clamp(0, NUM_ACTIONS - 1)
        selected_legal = legal_mask.gather(2, safe_action.unsqueeze(-1)).squeeze(-1)
        accepted = selection.valid_input & selected_legal
        placement = accepted & (selection.action_ids < NO_OP_ACTION)

        safe_slot = selection.slot.clamp(min=0)
        card_ids = state.hand_ids.gather(2, safe_slot.unsqueeze(-1)).squeeze(-1)
        hand = state.hand_ids.clone()
        cycle = state.cycle_ids.clone()
        cycle_length = state.cycle_length.clone()
        elixir = state.elixir.clone()

        # Oracle PlayerState.play_card clears the first matching card name,
        # which is observably different from clearing the decoded slot when a
        # synthetic hand contains duplicates.
        matches = hand == card_ids.unsqueeze(-1)
        slots = torch.arange(NUM_HAND_SLOTS, device=self.device).view(1, 1, -1)
        first_slot = torch.where(matches, slots, NUM_HAND_SLOTS).amin(dim=-1)
        clear = placement.unsqueeze(-1) & (slots == first_slot.unsqueeze(-1))
        hand = torch.where(clear, torch.zeros_like(hand), hand)
        cost = self.catalog.cards.elixir[card_ids].to(torch.float64)
        elixir = elixir - torch.where(placement, cost, torch.zeros_like(cost))

        append_index = cycle_length.clamp(max=cycle.shape[-1] - 1)
        append_mask = placement & (cycle_length < cycle.shape[-1])
        cycle.scatter_(
            2,
            append_index.unsqueeze(-1),
            torch.where(
                append_mask,
                card_ids,
                cycle.gather(2, append_index.unsqueeze(-1)).squeeze(-1),
            ).unsqueeze(-1),
        )
        cycle_length = cycle_length + append_mask.to(torch.int64)

        command_mask = placement | (accepted & selection.is_ability)
        flat_indices = torch.nonzero(command_mask.reshape(-1), as_tuple=False).squeeze(
            -1
        )
        batch_index = flat_indices // 2
        player_id = flat_indices % 2
        flat_action = selection.action_ids.reshape(-1)[flat_indices]
        flat_card = card_ids.reshape(-1)[flat_indices]
        ability = selection.is_ability.reshape(-1)[flat_indices]
        flat_card = torch.where(ability, torch.zeros_like(flat_card), flat_card)
        commands = TensorCommandQueue(
            sequence=torch.arange(flat_indices.numel(), device=self.device),
            battle_index=batch_index,
            player_id=player_id,
            action_id=flat_action,
            card_id=flat_card,
            card_kind=self.catalog.cards.kind[flat_card],
            slot=selection.slot.reshape(-1)[flat_indices],
            world_x_units=selection.world_x_units.reshape(-1)[flat_indices],
            world_y_units=selection.world_y_units.reshape(-1)[flat_indices],
            is_ability=ability,
        )
        return TensorIngressResult(
            accepted=accepted,
            selection=selection,
            commands=commands,
            hand_ids=hand,
            cycle_ids=cycle,
            cycle_length=cycle_length,
            elixir=elixir,
        )
