"""Tensor-native materialization of accepted deployment commands.

Serialized card metadata is compiled once into dense formation tables. The
ordinary materialization path consumes :class:`TensorCommandQueue` data,
allocates stable entity IDs/slots, writes retained battle state, and commits
the tensor action kernel's hand/cycle/elixir transition without calling
``BattleState.deploy_card`` or constructing Python entities.

Spells, abilities, non-admitted attached mechanics, and nested mixed-character
payloads are reported explicitly and fail closed at battle-row granularity.
Mechanic admission is an opt-in opcode-family contract; the default admits no
mechanics. This keeps a later Python fallback atomic: no supported command from
the same simultaneous decision is partially committed before the unsupported
operation is known.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, fields

import torch

from clasher.balance import LOGIC_SYMMETRICAL_DEPLOY_SNAP
from clasher.data import CardDataLoader
from clasher.formations import formation_offset, horizontal_line_offset
from clasher.kinematics import LOGIC_UNITS_PER_TILE, tiles_to_logic_units

from .actions import TensorCommandQueue, TensorIngressResult
from .catalog import MECHANIC_OPCODE, CardKindOpcode, TensorCardCatalog
from .entity_pool import EntityAllocation
from .runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)
from .tensor_ops import scatter_any_


@dataclass(frozen=True)
class TensorDeploymentCatalog:
    """Dense deployment-only metadata indexed by ``TensorCardCatalog`` ID."""

    cards: TensorCardCatalog
    summon_count: torch.Tensor
    offset_x_units: torch.Tensor
    offset_y_units: torch.Tensor
    deploy_delay_seconds: torch.Tensor
    symmetric_snap: torch.Tensor
    building_footprint_half_units: torch.Tensor
    supported_payload: torch.Tensor
    hitpoints_integer_kind: torch.Tensor
    spawned_card_names: tuple[tuple[str, ...], ...]
    spawned_kind: torch.Tensor
    spawned_hitpoints: torch.Tensor
    spawned_hitpoints_integer_kind: torch.Tensor
    spawned_lifetime_ms: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.cards.device

    @property
    def max_summons(self) -> int:
        return int(self.offset_x_units.shape[-1])

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        cards: TensorCardCatalog,
    ) -> TensorDeploymentCatalog:
        """Compile generalized formation tables from serialized card data."""

        size = len(cards.names)
        stats_by_id = [
            None if card_id == 0 else loader.get_card(name)
            for card_id, name in enumerate(cards.names)
        ]
        if any(stats is None for stats in stats_by_id[1:]):
            raise ValueError("could not materialize deployment metadata")
        maximum = max(
            1,
            max(
                int(getattr(stats, "summon_count", None) or 1)
                + int(getattr(stats, "summon_character_second_count", None) or 0)
                for stats in stats_by_id[1:]
                if stats is not None
            ),
        )
        summon_count = torch.zeros(size, dtype=torch.int16, device=cards.device)
        offsets_x = torch.zeros(
            (size, 2, 2, maximum), dtype=torch.int32, device=cards.device
        )
        offsets_y = torch.zeros_like(offsets_x)
        delays = torch.zeros((size, maximum), dtype=torch.float64, device=cards.device)
        symmetric_snap = torch.zeros(size, dtype=torch.bool, device=cards.device)
        footprint_half = torch.zeros(size, dtype=torch.int32, device=cards.device)
        supported_payload = torch.zeros(size, dtype=torch.bool, device=cards.device)
        hp_integer = torch.zeros(size, dtype=torch.bool, device=cards.device)
        spawned_names = [[""] * maximum for _ in range(size)]
        spawned_kind = torch.zeros(
            (size, maximum), dtype=torch.int8, device=cards.device
        )
        spawned_hp = torch.zeros(
            (size, maximum), dtype=torch.float64, device=cards.device
        )
        spawned_hp_integer = torch.zeros(
            (size, maximum), dtype=torch.bool, device=cards.device
        )
        spawned_lifetime_ms = torch.zeros(
            (size, maximum), dtype=torch.int32, device=cards.device
        )

        for card_id, stats in enumerate(stats_by_id[1:], start=1):
            assert stats is not None
            kind = int(cards.kind[card_id])
            is_troop = kind in {
                int(CardKindOpcode.TROOP),
                int(CardKindOpcode.CHAMPION),
            }
            is_building = kind == int(CardKindOpcode.BUILDING)
            primary_count = 1 if is_building else int(stats.summon_count or 1)
            second_count = int(
                getattr(stats, "summon_character_second_count", None) or 0
            )
            count = primary_count + second_count
            hp_value = stats.scaled_hitpoints
            if hp_value is None and is_troop:
                hp_value = stats.hitpoints
            if hp_value is None:
                hp_value = 100
            hp_integer[card_id] = type(hp_value) is int
            summon_count[card_id] = count
            supported_payload[card_id] = is_troop or is_building

            primary_data = getattr(stats, "summon_character_data", None)
            primary_raw_hp = (
                primary_data.get("hitpoints")
                if isinstance(primary_data, dict)
                else None
            )
            level_scale = (
                float(hp_value) / float(primary_raw_hp)
                if isinstance(primary_raw_hp, (int, float)) and primary_raw_hp != 0
                else 1.0
            )

            collision_radius = float(stats.collision_radius or 0.5)
            serialized_radius = getattr(stats, "summon_radius", None)
            radius = (
                collision_radius
                if serialized_radius is None
                else float(serialized_radius)
            )
            width = float(getattr(stats, "summon_width", 0.0) or 0.0)
            angle_shift = float(getattr(stats, "spawn_angle_shift", 0.0) or 0.0)
            stagger_ms = float(getattr(stats, "summon_deploy_delay", 0.0) or 0.0)
            for spawn_index in range(count):
                child_name = str(stats.name or cards.names[card_id])
                child_data = primary_data
                if second_count > 0:
                    child_data = (
                        primary_data
                        if spawn_index < primary_count
                        else getattr(stats, "summon_character_second_data", None)
                    )
                    if isinstance(child_data, dict):
                        child_name = str(child_data.get("name", "") or child_name)
                spawned_names[card_id][spawn_index] = child_name
                supported_payload[card_id] &= bool(child_name)
                child_raw_hp = (
                    child_data.get("hitpoints")
                    if isinstance(child_data, dict)
                    else None
                )
                child_hp = (
                    round(float(child_raw_hp) * level_scale)
                    if second_count > 0 and child_raw_hp is not None
                    else hp_value
                )
                child_deploy_ms = (
                    child_data.get("deployTime")
                    if isinstance(child_data, dict)
                    else None
                )
                spawned_kind[card_id, spawn_index] = kind
                spawned_hp[card_id, spawn_index] = float(child_hp)
                spawned_hp_integer[card_id, spawn_index] = type(child_hp) is int
                spawned_lifetime_ms[card_id, spawn_index] = round(
                    float(getattr(stats, "lifetime_ms", None) or 0.0)
                )
                base_delay = max(
                    0.0,
                    float(child_deploy_ms or stats.deploy_time or 0.0) / 1000.0,
                )
                delays[card_id, spawn_index] = (
                    base_delay + spawn_index * stagger_ms / 1000.0
                )
                if count == 1:
                    offset = (0.0, 0.0)
                    for player_id in (0, 1):
                        for lane_index in (0, 1):
                            offsets_x[card_id, player_id, lane_index, spawn_index] = 0
                            offsets_y[card_id, player_id, lane_index, spawn_index] = 0
                    continue
                for player_id in (0, 1):
                    for lane_index, lane_id in enumerate((1, 2)):
                        if second_count > 0:
                            offset = formation_offset(
                                spawn_index,
                                primary_count,
                                radius,
                                player_id,
                                angle_shift_degrees=angle_shift,
                                secondary_count=second_count,
                                lane_id=lane_id,
                            )
                        elif width > 0.0:
                            offset = horizontal_line_offset(
                                spawn_index,
                                count,
                                width,
                                radius,
                                player_id,
                                lane_id=lane_id,
                            )
                        else:
                            offset = formation_offset(
                                spawn_index,
                                count,
                                radius,
                                player_id,
                                angle_shift_degrees=angle_shift,
                                lane_id=lane_id,
                            )
                        offsets_x[card_id, player_id, lane_index, spawn_index] = (
                            tiles_to_logic_units(offset[0])
                        )
                        offsets_y[card_id, player_id, lane_index, spawn_index] = (
                            tiles_to_logic_units(offset[1])
                        )

            character_data = getattr(stats, "summon_character_data", None) or {}
            symmetric_snap[card_id] = bool(
                LOGIC_SYMMETRICAL_DEPLOY_SNAP
                and is_troop
                and not bool(cards.is_air_unit[card_id])
                and float(stats.speed or 0.0) > 0.0
                and int(character_data.get("dashCooldown", 0) or 0) == 0
            )
            if is_building:
                footprint_tiles = max(1, math.ceil(collision_radius * 2.0) + 1)
                footprint_half[card_id] = footprint_tiles * LOGIC_UNITS_PER_TILE // 2

        return cls(
            cards=cards,
            summon_count=summon_count,
            offset_x_units=offsets_x,
            offset_y_units=offsets_y,
            deploy_delay_seconds=delays,
            symmetric_snap=symmetric_snap,
            building_footprint_half_units=footprint_half,
            supported_payload=supported_payload,
            hitpoints_integer_kind=hp_integer,
            spawned_card_names=tuple(tuple(row) for row in spawned_names),
            spawned_kind=spawned_kind,
            spawned_hitpoints=spawned_hp,
            spawned_hitpoints_integer_kind=spawned_hp_integer,
            spawned_lifetime_ms=spawned_lifetime_ms,
        )


@dataclass(frozen=True)
class TensorDeploymentResult:
    """Allocation plus explicit support diagnostics aligned to input commands."""

    player_order: torch.Tensor
    allocation: EntityAllocation
    command_supported: torch.Tensor
    battle_supported: torch.Tensor
    unsupported_spell: torch.Tensor
    unsupported_mechanic: torch.Tensor
    unsupported_payload: torch.Tensor
    unsupported_ability: torch.Tensor
    unsupported_conflict: torch.Tensor
    spawned_command_index: torch.Tensor
    spawned_card_id: torch.Tensor


class TensorCommandMaterializer:
    """Materialize deployment queues into one retained tensor runtime."""

    def __init__(
        self,
        catalog: TensorDeploymentCatalog,
        *,
        admitted_mechanic_opcodes: Iterable[int] = (),
    ) -> None:
        self.catalog = catalog
        self.device = catalog.device
        admitted = torch.zeros(
            len(MECHANIC_OPCODE) + 1,
            dtype=torch.bool,
            device=self.device,
        )
        for opcode in admitted_mechanic_opcodes:
            code = int(opcode)
            if code <= 0 or code >= admitted.shape[0]:
                raise ValueError(f"unknown deployment mechanic opcode {code}")
            admitted[code] = True
        # This is an operation-family contract, not a card allowlist. The
        # default remains fail-closed for every attached mechanic.
        self.admitted_mechanic_opcode = admitted
        self._required_spawn_names = tuple(
            sorted({name for row in catalog.spawned_card_names for name in row if name})
        )
        self._mapping_key: tuple[str, ...] | None = None
        self._catalog_to_core_cache: torch.Tensor | None = None
        self._spawned_to_core_cache: torch.Tensor | None = None
        self._slot_numbers: dict[int, torch.Tensor] = {}
        self._batch_slot_rows: dict[tuple[int, int], torch.Tensor] = {}
        self._summon_lane = torch.arange(
            catalog.max_summons, dtype=torch.int64, device=self.device
        )

    def prepare_runtime(self, runtime: TensorBattleRuntime) -> None:
        """Install a stable spawned-character card-name namespace once.

        Some serialized playable cards materialize a character whose stats
        name differs from the wrapper card name. Expanding this internal name
        table before ordinary command execution prevents the resulting entity
        IDs from depending on deployment order. No Python battle object is
        inspected or stepped here.
        """

        current = runtime.battle.card_names
        new_names = ("", *sorted(set(current[1:]) | set(self._required_spawn_names)))
        if new_names == current:
            return
        new_to_id = {name: index for index, name in enumerate(new_names)}
        old_to_new = torch.tensor(
            [new_to_id[name] for name in current],
            dtype=torch.int64,
            device=self.device,
        )
        for name in ("hand", "deck", "cycle_queue", "entity_card"):
            value = getattr(runtime.battle, name)
            value.copy_(old_to_new[value])
        runtime.battle.card_names = new_names
        runtime.battle.card_to_id = new_to_id
        runtime.card_catalog_index = torch.tensor(
            [
                self.catalog.cards.name_to_id.get(name, -1) if name else 0
                for name in new_names
            ],
            dtype=torch.int64,
            device=self.device,
        )

    def _player_order(
        self,
        runtime: TensorBattleRuntime,
        player_order: torch.Tensor | None,
        *,
        prevalidated: bool = False,
    ) -> torch.Tensor:
        if player_order is not None:
            order = torch.as_tensor(player_order, dtype=torch.int64, device=self.device)
            if order.shape != (runtime.batch_size, 2):
                raise ValueError("player_order must have shape [batch, 2]")
            if not prevalidated:
                expected = torch.tensor([0, 1], dtype=torch.int64, device=self.device)
                torch._assert_async(
                    (torch.sort(order, dim=1).values == expected).all(),
                    "each player_order row must contain players 0 and 1",
                )
            return order

        # random.shuffle([0, 1]) performs exactly one _randbelow(2) draw.
        choice = runtime.battle.rng.randrange(2)
        return torch.stack((1 - choice, choice), dim=1)

    def _validate_commands(
        self,
        runtime: TensorBattleRuntime,
        commands: TensorCommandQueue,
    ) -> None:
        command_count = int(commands.battle_index.numel())
        for state in fields(commands):
            value = getattr(commands, state.name)
            if value.shape != (command_count,):
                raise ValueError("every command field must be one-dimensional")
            if value.device != self.device:
                raise ValueError("commands and runtime must use the same device")
        if command_count and bool(
            (
                (commands.battle_index < 0)
                | (commands.battle_index >= runtime.batch_size)
                | (commands.player_id < 0)
                | (commands.player_id > 1)
                | (commands.card_id < 0)
                | (commands.card_id >= len(self.catalog.cards.names))
            )
            .any()
            .item()
        ):
            raise ValueError("command index is outside the runtime/catalog")

    def _catalog_mappings(
        self,
        runtime: TensorBattleRuntime,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        key = runtime.battle.card_names
        if (
            key == self._mapping_key
            and self._catalog_to_core_cache is not None
            and self._spawned_to_core_cache is not None
        ):
            return self._catalog_to_core_cache, self._spawned_to_core_cache

        reverse = torch.full(
            (len(self.catalog.cards.names),),
            -1,
            dtype=torch.int64,
            device=self.device,
        )
        core_ids = torch.arange(
            runtime.card_catalog_index.numel(),
            dtype=torch.int64,
            device=self.device,
        )
        present = runtime.card_catalog_index >= 0
        reverse[runtime.card_catalog_index[present]] = core_ids[present]
        spawned = torch.tensor(
            [
                [runtime.battle.card_to_id.get(name, -1) if name else 0 for name in row]
                for row in self.catalog.spawned_card_names
            ],
            dtype=torch.int64,
            device=self.device,
        )
        self._mapping_key = key
        self._catalog_to_core_cache = reverse
        self._spawned_to_core_cache = spawned
        return reverse, spawned

    def _unsupported_mechanics(self, card_ids: torch.Tensor) -> torch.Tensor:
        """Reject cards containing any non-admitted serialized operation."""

        opcodes = self.catalog.cards.mechanic_opcode[card_ids].to(torch.int64)
        present = opcodes > 0
        in_range = opcodes < self.admitted_mechanic_opcode.shape[0]
        admitted = self.admitted_mechanic_opcode[
            opcodes.clamp(0, self.admitted_mechanic_opcode.shape[0] - 1)
        ]
        return (present & (~in_range | ~admitted)).any(dim=1)

    def _allocate_prevalidated(
        self,
        runtime: TensorBattleRuntime,
        counts: torch.Tensor,
    ) -> EntityAllocation:
        """Allocate after the runtime driver has proven row capacity."""

        pool = runtime.entity_pool
        capacity = pool.capacity
        slot_numbers = self._slot_numbers.get(capacity)
        if slot_numbers is None:
            slot_numbers = torch.arange(capacity, dtype=torch.int64, device=self.device)
            self._slot_numbers[capacity] = slot_numbers
        row_key = (pool.batch_size, capacity)
        batch_rows = self._batch_slot_rows.get(row_key)
        if batch_rows is None:
            batch_rows = torch.arange(
                pool.batch_size, dtype=torch.int64, device=self.device
            )[:, None].expand(pool.batch_size, capacity)
            self._batch_slot_rows[row_key] = batch_rows

        available_keys = torch.where(
            ~pool.active,
            slot_numbers[None, :],
            torch.full_like(pool.entity_id, capacity),
        )
        slots = torch.sort(available_keys, dim=1).values
        ordinal = slot_numbers[None, :].expand(pool.batch_size, -1)
        valid = ordinal < counts[:, None]
        entity_ids = pool.next_entity_id[:, None] + ordinal
        rows = batch_rows[valid]
        selected_slots = slots[valid]
        pool.active[rows, selected_slots] = True
        pool.entity_id[rows, selected_slots] = entity_ids[valid]
        pool.next_entity_id.add_(counts)
        return EntityAllocation(
            slots=torch.where(valid, slots, torch.full_like(slots, -1)),
            entity_ids=torch.where(valid, entity_ids, torch.zeros_like(entity_ids)),
            valid=valid,
        )

    def _append_spawn_events_prevalidated(
        self,
        runtime: TensorBattleRuntime,
        allocation: EntityAllocation,
    ) -> None:
        """Append spawn lanes after the driver has proven event capacity."""

        events = runtime.events
        valid = allocation.valid
        local = torch.cumsum(valid.to(torch.int64), dim=1) - 1
        destinations = events.count.to(torch.int64)[:, None] + local
        row_key = (runtime.batch_size, runtime.max_entities)
        rows = self._batch_slot_rows.get(row_key)
        if rows is None:
            rows = torch.arange(
                runtime.batch_size, dtype=torch.int64, device=self.device
            )[:, None].expand_as(valid)
            self._batch_slot_rows[row_key] = rows
        row_index = rows[valid]
        event_index = destinations[valid]
        safe_slots = allocation.slots.clamp_min(0)
        x_units = runtime.battle.entity_x_units.gather(1, safe_slots)
        y_units = runtime.battle.entity_y_units.gather(1, safe_slots)
        payload = runtime.battle.entity_card.gather(1, safe_slots)
        events.phase[row_index, event_index] = int(TickPhase.COMMANDS)
        events.opcode[row_index, event_index] = int(RuntimeEventOpcode.SPAWN)
        events.source_id[row_index, event_index] = allocation.entity_ids[valid]
        events.target_id[row_index, event_index] = 0
        events.x_units[row_index, event_index] = x_units[valid]
        events.y_units[row_index, event_index] = y_units[valid]
        events.amount[row_index, event_index] = 0.0
        events.payload[row_index, event_index] = payload[valid]
        events.count.add_(valid.sum(dim=1, dtype=events.count.dtype))

    def _ordered_commands(
        self,
        commands: TensorCommandQueue,
        player_order: torch.Tensor,
    ) -> torch.Tensor:
        if commands.battle_index.numel() == 0:
            return torch.empty(0, dtype=torch.int64, device=self.device)
        first = player_order[commands.battle_index, 0]
        rank = (commands.player_id != first).to(torch.int64)
        width = max(1, int(commands.sequence.numel()))
        key = commands.battle_index * (2 * width) + rank * width + commands.sequence
        return torch.argsort(key, stable=True)

    def _conflicts(
        self,
        commands: TensorCommandQueue,
        order: torch.Tensor,
    ) -> torch.Tensor:
        """Mark later commands whose oracle placement sees a new building."""

        count = int(order.numel())
        result = torch.zeros(
            int(commands.battle_index.numel()), dtype=torch.bool, device=self.device
        )
        if count < 2:
            return result
        card = commands.card_id[order]
        kind = self.catalog.cards.kind[card]
        is_building = kind == int(CardKindOpcode.BUILDING)
        same_battle = (
            commands.battle_index[order][:, None]
            == commands.battle_index[order][None, :]
        )
        ordinal = torch.arange(count, device=self.device)
        earlier = ordinal[:, None] < ordinal[None, :]
        earlier_building = is_building[:, None]
        dx = (
            commands.world_x_units[order][:, None]
            - commands.world_x_units[order][None, :]
        ).to(torch.int64)
        dy = (
            commands.world_y_units[order][:, None]
            - commands.world_y_units[order][None, :]
        ).to(torch.int64)
        later_building = is_building[None, :]
        half = self.catalog.building_footprint_half_units[card].to(torch.int64)
        building_overlap = (
            (torch.abs(dx) < half[:, None] + half[None, :])
            & (torch.abs(dy) < half[:, None] + half[None, :])
            & later_building
        )
        radius = self.catalog.cards.collision_radius_units[card].to(torch.int64)
        radius = torch.where(radius > 0, radius, torch.full_like(radius, 500))
        circle_overlap = (
            dx * dx + dy * dy < (radius[:, None] + radius[None, :]) ** 2
        ) & ~later_building
        invalid_pair = (
            same_battle
            & earlier
            & earlier_building
            & (building_overlap | circle_overlap)
        )
        later_invalid = invalid_pair.any(dim=0)
        result[order] = later_invalid
        return result

    def _reset_spawn_slots(
        self,
        runtime: TensorBattleRuntime,
        spawn_mask: torch.Tensor,
    ) -> None:
        battle = runtime.battle
        battle.entity_active[spawn_mask] = True
        battle.entity_kind[spawn_mask] = 0
        battle.entity_player[spawn_mask] = 0
        battle.entity_card[spawn_mask] = 0
        battle.entity_x_units[spawn_mask] = 0
        battle.entity_y_units[spawn_mask] = 0
        battle.entity_hp[spawn_mask] = 0.0
        battle.entity_hp_integer_kind[spawn_mask] = False
        battle.entity_max_hp[spawn_mask] = 0.0
        battle.entity_last_attack_time[spawn_mask] = 0.0
        battle.entity_deploy_delay[spawn_mask] = 0.0
        battle.entity_placement_pending[spawn_mask] = False
        battle.entity_spawn_hook_pending[spawn_mask] = False
        battle.entity_spawn_hook_fired[spawn_mask] = False
        battle.entity_lifetime_ms[spawn_mask] = 0
        battle.entity_lifetime_decay_rate[spawn_mask] = 0
        battle.entity_lifetime_elapsed[spawn_mask] = 0.0
        battle.entity_lifetime_decay_work[spawn_mask] = 0
        battle.entity_lifetime_tick_carry_ms[spawn_mask] = 0.0
        battle.entity_tower_slot[spawn_mask] = -1
        battle.entity_tower_active[spawn_mask] = False

        one_fields = {
            "slow_movement",
            "slow_attack",
            "slow_spawn",
            "slow_multiplier",
            "attack_speed_debuff_multiplier",
            "spawn_speed_debuff_multiplier",
            "haste_movement",
            "haste_attack",
            "haste_spawn",
            "movement_speed_buff_multiplier",
            "attack_speed_buff_multiplier",
            "spawn_speed_buff_multiplier",
        }
        for state in fields(runtime.status):
            value = getattr(runtime.status, state.name)
            value[spawn_mask] = 1 if state.name in one_fields else 0

        for state in fields(runtime.phases):
            value = getattr(runtime.phases, state.name)
            if value.ndim < 2 or value.shape[:2] != spawn_mask.shape:
                continue
            value[spawn_mask] = -1 if state.name == "target_slot" else 0

    def _commit_card_transition(
        self,
        runtime: TensorBattleRuntime,
        ingress: TensorIngressResult,
        battle_supported: torch.Tensor,
        catalog_to_core: torch.Tensor,
    ) -> None:
        mapped_hand = catalog_to_core[ingress.hand_ids]
        mapped_cycle = catalog_to_core[ingress.cycle_ids]
        rows = battle_supported[:, None, None]
        runtime.battle.hand.copy_(torch.where(rows, mapped_hand, runtime.battle.hand))
        cycle_width = ingress.cycle_ids.shape[2]
        if cycle_width > runtime.battle.cycle_queue.shape[2]:
            raise OverflowError("runtime card-cycle capacity exhausted")
        candidate_cycle = torch.zeros_like(runtime.battle.cycle_queue)
        candidate_cycle[:, :, :cycle_width] = mapped_cycle
        runtime.battle.cycle_queue.copy_(
            torch.where(rows, candidate_cycle, runtime.battle.cycle_queue)
        )
        runtime.battle.cycle_queue_length.copy_(
            torch.where(
                battle_supported[:, None],
                ingress.cycle_length.to(runtime.battle.cycle_queue_length.dtype),
                runtime.battle.cycle_queue_length,
            )
        )
        runtime.battle.elixir.copy_(
            torch.where(
                battle_supported[:, None], ingress.elixir, runtime.battle.elixir
            )
        )

    def materialize(
        self,
        runtime: TensorBattleRuntime,
        ingress: TensorIngressResult,
        *,
        player_order: torch.Tensor | None = None,
        _prevalidated: bool = False,
        _prevalidated_order: bool = False,
    ) -> TensorDeploymentResult:
        """Commit supported battle rows without any Python entity stepping."""

        if runtime.device != self.device or runtime.catalog is not self.catalog.cards:
            raise ValueError("runtime and deployment catalog must share card metadata")
        self.prepare_runtime(runtime)
        commands = ingress.commands
        if not _prevalidated:
            self._validate_commands(runtime, commands)
        chosen_order = self._player_order(
            runtime,
            player_order,
            prevalidated=_prevalidated_order,
        )
        command_order = self._ordered_commands(commands, chosen_order)
        card = commands.card_id
        kind = self.catalog.cards.kind[card]
        unsupported_spell = kind == int(CardKindOpcode.SPELL)
        unsupported_mechanic = self._unsupported_mechanics(card)
        unsupported_payload = ~self.catalog.supported_payload[card]
        unsupported_ability = commands.is_ability
        unsupported_conflict = self._conflicts(commands, command_order)
        command_supported = ~(
            unsupported_spell
            | unsupported_mechanic
            | unsupported_payload
            | unsupported_ability
            | unsupported_conflict
        )

        bad_battle = torch.zeros(
            runtime.batch_size, dtype=torch.bool, device=self.device
        )
        if commands.battle_index.numel():
            scatter_any_(
                bad_battle,
                0,
                commands.battle_index,
                ~command_supported,
            )
        battle_supported = runtime.supported & ~bad_battle
        command_supported &= battle_supported[commands.battle_index]

        catalog_to_core, spawned_catalog_to_core = self._catalog_mappings(runtime)
        if not _prevalidated and (
            bool((catalog_to_core[ingress.hand_ids] < 0).any().item())
            or bool((catalog_to_core[ingress.cycle_ids] < 0).any().item())
        ):
            raise ValueError("action transition contains a card absent from runtime")
        if _prevalidated:
            transition_known = (catalog_to_core[ingress.hand_ids] >= 0).all(
                dim=(1, 2)
            ) & (catalog_to_core[ingress.cycle_ids] >= 0).all(dim=(1, 2))
            battle_supported &= transition_known
            command_supported &= battle_supported[commands.battle_index]

        ordered_cards = card[command_order]
        ordered_battles = commands.battle_index[command_order]
        ordered_supported = command_supported[command_order]
        spawn_counts = torch.where(
            ordered_supported,
            self.catalog.summon_count[ordered_cards].to(torch.int64),
            torch.zeros_like(ordered_cards),
        )
        counts_by_battle = torch.zeros(
            runtime.batch_size, dtype=torch.int64, device=self.device
        )
        if ordered_battles.numel():
            counts_by_battle.scatter_add_(0, ordered_battles, spawn_counts)
        if not _prevalidated and bool(
            (
                runtime.events.count.to(torch.int64) + counts_by_battle
                > runtime.events.capacity
            )
            .any()
            .item()
        ):
            raise OverflowError("runtime event capacity exhausted")

        allocation = (
            self._allocate_prevalidated(runtime, counts_by_battle)
            if _prevalidated
            else runtime.entity_pool.allocate(counts_by_battle)
        )
        spawn_mask = torch.zeros_like(runtime.entity_pool.active)
        scatter_any_(
            spawn_mask,
            1,
            allocation.slots.clamp_min(0),
            allocation.valid,
        )
        self._reset_spawn_slots(runtime, spawn_mask)

        command_count = int(command_order.numel())
        summon_lane = self._summon_lane
        lane_valid = summon_lane[None, :] < spawn_counts[:, None]
        same_battle_earlier = (ordered_battles[:, None] == ordered_battles[None, :]) & (
            torch.arange(command_count, device=self.device)[:, None]
            > torch.arange(command_count, device=self.device)[None, :]
        )
        prefix = (same_battle_earlier * spawn_counts[None, :]).sum(
            dim=1, dtype=torch.int64
        )
        ordinal = prefix[:, None] + summon_lane[None, :]
        safe_ordinal = ordinal.clamp(0, runtime.max_entities - 1)
        entity_slots = allocation.slots[ordered_battles[:, None], safe_ordinal]

        ordered_players = commands.player_id[command_order]
        anchor_x = commands.world_x_units[command_order].to(torch.int32)
        anchor_y = commands.world_y_units[command_order].to(torch.int32)
        snap = self.catalog.symmetric_snap[ordered_cards]
        anchor_x = anchor_x - (snap & (anchor_x < 9 * LOGIC_UNITS_PER_TILE)).to(
            torch.int32
        )
        anchor_y = anchor_y - (snap & (ordered_players != 0)).to(torch.int32)
        lane_index = (anchor_x >= 9 * LOGIC_UNITS_PER_TILE).to(torch.int64)
        x = (
            anchor_x[:, None]
            + self.catalog.offset_x_units[ordered_cards, ordered_players, lane_index]
        )
        y = (
            anchor_y[:, None]
            + self.catalog.offset_y_units[ordered_cards, ordered_players, lane_index]
        )
        is_troop = (
            (self.catalog.cards.kind[ordered_cards] == int(CardKindOpcode.TROOP))
            | (self.catalog.cards.kind[ordered_cards] == int(CardKindOpcode.CHAMPION))
        )
        x = torch.where(is_troop[:, None], x.clamp(250, 17_750), x)
        y = torch.where(is_troop[:, None], y.clamp(250, 31_750), y)
        delays = self.catalog.deploy_delay_seconds[ordered_cards]

        rows = ordered_battles[:, None].expand_as(entity_slots)[lane_valid]
        slots = entity_slots[lane_valid]
        card_lanes = ordered_cards[:, None].expand_as(entity_slots)[lane_valid]
        spawned_core_lanes = spawned_catalog_to_core[ordered_cards]
        player_lanes = ordered_players[:, None].expand_as(entity_slots)[lane_valid]
        index = (rows, slots)
        core_card = spawned_core_lanes[lane_valid]
        spawned_kind = self.catalog.spawned_kind[ordered_cards][lane_valid]
        building = spawned_kind == int(CardKindOpcode.BUILDING)
        runtime.battle.entity_kind[index] = building.to(torch.int8)
        runtime.battle.entity_player[index] = player_lanes.to(torch.int8)
        runtime.battle.entity_card[index] = core_card
        runtime.battle.entity_x_units[index] = x[lane_valid]
        runtime.battle.entity_y_units[index] = y[lane_valid]
        lane_hitpoints = self.catalog.spawned_hitpoints[ordered_cards][lane_valid]
        runtime.battle.entity_hp[index] = lane_hitpoints
        runtime.battle.entity_hp_integer_kind[index] = (
            self.catalog.spawned_hitpoints_integer_kind[ordered_cards][lane_valid]
        )
        runtime.battle.entity_max_hp[index] = lane_hitpoints
        runtime.battle.entity_deploy_delay[index] = delays[lane_valid]
        pending = delays[lane_valid] > 1e-9
        runtime.battle.entity_placement_pending[index] = pending
        runtime.battle.entity_spawn_hook_pending[index] = pending
        runtime.battle.entity_spawn_hook_fired[index] = ~pending
        runtime.battle.entity_tower_active[index] = building
        lifetime_ms = self.catalog.spawned_lifetime_ms[ordered_cards][lane_valid].to(
            torch.int64
        )
        runtime.battle.entity_lifetime_ms[index] = torch.where(
            building, lifetime_ms, torch.zeros_like(lifetime_ms)
        )
        runtime.battle.entity_lifetime_decay_rate[index] = torch.where(
            building & (lifetime_ms > 0),
            5000
            * torch.round(lane_hitpoints).to(torch.int64)
            // lifetime_ms.clamp_min(1).to(torch.int64),
            torch.zeros_like(lifetime_ms, dtype=torch.int64),
        ).to(runtime.battle.entity_lifetime_decay_rate.dtype)

        self._commit_card_transition(
            runtime, ingress, battle_supported, catalog_to_core
        )
        if _prevalidated:
            self._append_spawn_events_prevalidated(runtime, allocation)
        else:
            runtime.events.append(
                phase=TickPhase.COMMANDS,
                opcode=RuntimeEventOpcode.SPAWN,
                valid=allocation.valid,
                source_id=allocation.entity_ids,
                x_units=runtime.battle.entity_x_units.gather(
                    1, allocation.slots.clamp_min(0)
                ),
                y_units=runtime.battle.entity_y_units.gather(
                    1, allocation.slots.clamp_min(0)
                ),
                payload=runtime.battle.entity_card.gather(
                    1, allocation.slots.clamp_min(0)
                ),
            )
        runtime.mark_dirty(counts_by_battle > 0, phase=TickPhase.COMMANDS)
        if not _prevalidated:
            runtime.assert_invariants()

        spawned_command = torch.full_like(allocation.slots, -1)
        spawned_card = torch.zeros_like(allocation.slots)
        command_ids = command_order[:, None].expand_as(entity_slots)
        spawned_command[rows, slots] = command_ids[lane_valid]
        spawned_card[rows, slots] = card_lanes
        return TensorDeploymentResult(
            player_order=chosen_order,
            allocation=allocation,
            command_supported=command_supported,
            battle_supported=battle_supported,
            unsupported_spell=unsupported_spell,
            unsupported_mechanic=unsupported_mechanic,
            unsupported_payload=unsupported_payload,
            unsupported_ability=unsupported_ability,
            unsupported_conflict=unsupported_conflict,
            spawned_command_index=spawned_command,
            spawned_card_id=spawned_card,
        )


__all__ = [
    "TensorCommandMaterializer",
    "TensorDeploymentCatalog",
    "TensorDeploymentResult",
]
