"""Composed retained state for complete batched PyTorch battle execution.

This module joins the independently tested tensor schemas at one ownership
boundary.  ``TensorBattleRuntime.entity_pool.entity_id`` is the *same tensor*
as ``battle.entity_id``; phase workspaces refer to physical slots and never
maintain a second mutable identity table.  The Python loops in
:meth:`from_battles` and :meth:`sync_to_battles` are boundary adapters only.
Ordinary tick kernels retain and mutate these tensors directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import ClassVar, TypeVar

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import PeriodicDamageEffect
from clasher.kinematics import logic_units_to_tiles
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.entity_pool import INVALID_SLOT, TensorEntityPool
from clasher.torch_sim.state import TensorBattleState
from clasher.torch_sim.status import TensorStatusState


class TickPhase(IntEnum):
    """Stable complete-tick phase indices in Python-oracle order."""

    CLOCKS_AND_PLAYERS = 0
    COMMANDS = 1
    PROJECTILE_RESERVATIONS = 2
    COMBAT = 3
    MOVEMENT = 4
    COLLISION = 5
    BUILDING_LIFETIME = 6
    STATUS = 7
    OBJECTS = 8
    CLEANUP_AND_SPAWNS = 9
    WIN_CONDITIONS = 10


PHASE_COUNT = len(TickPhase)

RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG = "exact_debug"
RESIDENT_EXECUTION_PROFILE_GYM_FAST = "gym_fast"
RESIDENT_EXECUTION_PROFILES = frozenset(
    (
        RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
        RESIDENT_EXECUTION_PROFILE_GYM_FAST,
    )
)


class RuntimeEventOpcode(IntEnum):
    """Cross-phase event types; payload interpretation is data driven."""

    COMMAND = 1
    DAMAGE = 2
    PROJECTILE = 3
    STATUS = 4
    MOVEMENT = 5
    SPAWN = 6
    DEATH = 7
    AREA = 8


@dataclass
class TensorPhaseState:
    """Retained phase workspaces aligned with the canonical entity slots."""

    phase_cursor: torch.Tensor
    supported: torch.Tensor
    dirty: torch.Tensor
    target_slot: torch.Tensor
    waypoint_units: torch.Tensor
    waypoint_valid: torch.Tensor
    movement_vector_units: torch.Tensor
    movement_vector_count: torch.Tensor
    movement_vector_bypasses_cap: torch.Tensor
    reserved_lethal: torch.Tensor
    pending_damage: torch.Tensor
    death_pending: torch.Tensor
    spawn_count: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.phase_cursor.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.target_slot.shape[1])

    @property
    def device(self) -> torch.device:
        return self.phase_cursor.device

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        device: str | torch.device = "cpu",
    ) -> TensorPhaseState:
        if batch_size < 1 or max_entities < 1:
            raise ValueError("phase dimensions must be positive")
        torch_device = torch.device(device)
        entity_shape = (batch_size, max_entities)
        return cls(
            phase_cursor=torch.zeros(batch_size, dtype=torch.int8, device=torch_device),
            supported=torch.ones(
                (batch_size, PHASE_COUNT), dtype=torch.bool, device=torch_device
            ),
            dirty=torch.zeros(
                (batch_size, PHASE_COUNT), dtype=torch.bool, device=torch_device
            ),
            target_slot=torch.full(
                entity_shape, INVALID_SLOT, dtype=torch.int64, device=torch_device
            ),
            waypoint_units=torch.zeros(
                (*entity_shape, 2), dtype=torch.int64, device=torch_device
            ),
            waypoint_valid=torch.zeros(
                entity_shape, dtype=torch.bool, device=torch_device
            ),
            movement_vector_units=torch.zeros(
                (*entity_shape, 2), dtype=torch.int64, device=torch_device
            ),
            movement_vector_count=torch.zeros(
                entity_shape, dtype=torch.int32, device=torch_device
            ),
            movement_vector_bypasses_cap=torch.zeros(
                entity_shape, dtype=torch.bool, device=torch_device
            ),
            reserved_lethal=torch.zeros(
                entity_shape, dtype=torch.bool, device=torch_device
            ),
            pending_damage=torch.zeros(
                entity_shape, dtype=torch.float64, device=torch_device
            ),
            death_pending=torch.zeros(
                entity_shape, dtype=torch.bool, device=torch_device
            ),
            spawn_count=torch.zeros(
                entity_shape, dtype=torch.int16, device=torch_device
            ),
        )


@dataclass
class TensorRuntimeEvents:
    """Fixed-capacity deterministic event streams, one stream per battle.

    Calls append their valid lanes in left-to-right order.  ``sequence`` is
    monotonically increasing within each battle even when rows append a
    different number of events.  Source/target IDs are immutable event
    references, not another live identity table.
    """

    count: torch.Tensor
    phase: torch.Tensor
    opcode: torch.Tensor
    sequence: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    amount: torch.Tensor
    payload: torch.Tensor

    execution_profile: ClassVar[str] = RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG

    @property
    def batch_size(self) -> int:
        return int(self.count.shape[0])

    @property
    def capacity(self) -> int:
        return int(self.opcode.shape[1])

    @property
    def device(self) -> torch.device:
        return self.count.device

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        *,
        device: str | torch.device = "cpu",
    ) -> TensorRuntimeEvents:
        if batch_size < 1 or capacity < 1:
            raise ValueError("event dimensions must be positive")
        torch_device = torch.device(device)
        shape = (batch_size, capacity)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=torch_device)

        return cls(
            count=torch.zeros(batch_size, dtype=torch.int32, device=torch_device),
            phase=zeros(torch.int8),
            opcode=zeros(torch.int16),
            sequence=zeros(torch.int32),
            source_id=zeros(torch.int64),
            target_id=zeros(torch.int64),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            amount=zeros(torch.float64),
            payload=zeros(torch.int64),
        )

    def clear(self, battle_mask: torch.Tensor | None = None) -> None:
        selected = (
            torch.ones(self.batch_size, dtype=torch.bool, device=self.device)
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("battle_mask must have shape [batch_size]")
        self.count[selected] = 0
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if descriptor.name != "count":
                value[selected] = 0

    def append(
        self,
        *,
        phase: int | torch.Tensor,
        opcode: int | torch.Tensor,
        valid: torch.Tensor,
        source_id: int | torch.Tensor = 0,
        target_id: int | torch.Tensor = 0,
        x_units: int | torch.Tensor = 0,
        y_units: int | torch.Tensor = 0,
        amount: float | torch.Tensor = 0.0,
        payload: int | torch.Tensor = 0,
    ) -> None:
        """Append padded ``[batch, event]`` lanes without Python row loops."""

        selected = torch.as_tensor(valid, dtype=torch.bool, device=self.device)
        if selected.ndim != 2 or selected.shape[0] != self.batch_size:
            raise ValueError("valid must have shape [batch_size, events]")
        width = selected.shape[1]

        def lanes(value: float | torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
            tensor = torch.as_tensor(value, dtype=dtype, device=self.device)
            try:
                return torch.broadcast_to(tensor, (self.batch_size, width))
            except RuntimeError as exc:
                raise ValueError("event value is not broadcastable to valid") from exc

        local = torch.cumsum(selected.to(torch.int64), dim=1) - 1
        destinations = self.count.to(torch.int64)[:, None] + local
        additions = selected.sum(dim=1, dtype=torch.int64)
        if bool(
            ((self.count.to(torch.int64) + additions) > self.capacity).any().item()
        ):
            raise OverflowError("runtime event capacity exhausted")
        rows = torch.arange(self.batch_size, device=self.device)[:, None].expand_as(
            selected
        )
        row_index = rows[selected]
        slot_index = destinations[selected]
        values = (
            (self.phase, lanes(phase, torch.int8)),
            (self.opcode, lanes(opcode, torch.int16)),
            (self.source_id, lanes(source_id, torch.int64)),
            (self.target_id, lanes(target_id, torch.int64)),
            (self.x_units, lanes(x_units, torch.int32)),
            (self.y_units, lanes(y_units, torch.int32)),
            (self.amount, lanes(amount, torch.float64)),
            (self.payload, lanes(payload, torch.int64)),
        )
        for destination, value in values:
            destination[row_index, slot_index] = value[selected]
        self.sequence[row_index, slot_index] = slot_index.to(torch.int32)
        self.count.add_(additions.to(torch.int32))


class TensorGymFastRuntimeEvents(TensorRuntimeEvents):
    """Gameplay scratch events without exact diagnostic ledger appends.

    Object-phase kernels may still write their compact gameplay handoff into
    these tensors directly.  General resident mechanics call ``append`` only
    to reproduce the scalar diagnostic ledger, which is deliberately omitted
    by the fast Gym profile.
    """

    execution_profile: ClassVar[str] = RESIDENT_EXECUTION_PROFILE_GYM_FAST

    def append(self, **_: object) -> None:
        return


_T = TypeVar("_T")


def _select_tensor_dataclass(value: _T, indices: torch.Tensor) -> _T:
    """Clone a mutable tensor dataclass while selecting its batch dimension."""

    selected: dict[str, object] = {}
    # Every retained state dataclass exposes its batch size from tensor shape.
    # Using that structural value avoids a device-to-host synchronization for
    # every nested owner selected during speculative forks.
    source_batch = next(
        int(item.shape[0])
        for descriptor in fields(value)  # type: ignore[arg-type]
        if isinstance((item := getattr(value, descriptor.name)), torch.Tensor)
        and item.ndim
    )
    for descriptor in fields(value):  # type: ignore[arg-type]
        item = getattr(value, descriptor.name)
        if (
            isinstance(item, torch.Tensor)
            and item.ndim
            and item.shape[0] >= source_batch
        ):
            selected[descriptor.name] = item.index_select(0, indices).clone()
        elif isinstance(item, dict):
            selected[descriptor.name] = dict(item)
        else:
            selected[descriptor.name] = item
    return type(value)(**selected)


@dataclass
class TensorBattleRuntime:
    """One retained, forkable owner for a batch of tensor battles."""

    battle: TensorBattleState
    entity_pool: TensorEntityPool
    catalog: TensorCardCatalog
    card_catalog_index: torch.Tensor
    status: TensorStatusState
    phases: TensorPhaseState
    events: TensorRuntimeEvents
    supported: torch.Tensor
    dirty: torch.Tensor
    status_source_kind_names: tuple[str | None, ...]

    @property
    def device(self) -> torch.device:
        return self.battle.device

    @property
    def batch_size(self) -> int:
        return self.battle.batch_size

    @property
    def max_entities(self) -> int:
        return self.battle.max_entities

    @classmethod
    def from_battles(
        cls,
        battles: Sequence[BattleState],
        *,
        device: str | torch.device = "cpu",
        max_entities: int = 128,
        max_cards: int = 16,
        max_status_sources: int = 8,
        event_capacity: int = 256,
        catalog: TensorCardCatalog | None = None,
        execution_profile: str = RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    ) -> TensorBattleRuntime:
        if not battles:
            raise ValueError("at least one battle is required")
        if execution_profile not in RESIDENT_EXECUTION_PROFILES:
            raise ValueError(
                "execution_profile must be one of "
                f"{sorted(RESIDENT_EXECUTION_PROFILES)!r}"
            )
        core = TensorBattleState.from_battles(
            battles,
            device=device,
            max_entities=max_entities,
            max_cards=max_cards,
        )
        definitions = battles[0].card_loader.load_card_definitions()
        serialized_names = tuple(
            name for name in core.card_names[1:] if name in definitions
        )
        compiled = catalog or TensorCardCatalog.compile(
            battles[0].card_loader,
            serialized_names,
            device=core.device,
        )
        if compiled.device != core.device:
            raise ValueError("catalog and runtime must use the same device")
        catalog_index = torch.full(
            (len(core.card_names),), -1, dtype=torch.int64, device=core.device
        )
        catalog_index[0] = 0
        for core_id, name in enumerate(core.card_names[1:], start=1):
            catalog_index[core_id] = compiled.name_to_id.get(name, -1)

        presence = core.entity_id != 0
        pool = TensorEntityPool(
            next_entity_id=torch.tensor(
                [battle.next_entity_id for battle in battles],
                dtype=torch.int64,
                device=core.device,
            ),
            active=presence,
            entity_id=core.entity_id,
        )
        pool.assert_invariants()

        maximum_slow = max(
            (
                len(entity._slow_effects)
                for battle in battles
                for entity in battle.entities.values()
            ),
            default=0,
        )
        maximum_haste = max(
            (
                len(entity._haste_effects)
                for battle in battles
                for entity in battle.entities.values()
            ),
            default=0,
        )
        maximum_periodic = max(
            (
                len(entity._periodic_damage_effects)
                for battle in battles
                for entity in battle.entities.values()
            ),
            default=0,
        )
        status = TensorStatusState.empty(
            len(battles),
            max_entities,
            max_slow_sources=max(max_status_sources, maximum_slow, 1),
            max_haste_sources=max(max_status_sources, maximum_haste, 1),
            max_periodic_sources=max(max_status_sources, maximum_periodic, 1),
            device=core.device,
        )
        source_kinds = tuple(
            sorted(
                {
                    effect.source_kind
                    for battle in battles
                    for entity in battle.entities.values()
                    for effect in entity._periodic_damage_effects.values()
                    if effect.source_kind is not None
                }
            )
        )
        status_kind_names: tuple[str | None, ...] = (None, *source_kinds)
        kind_to_id = {name: index for index, name in enumerate(status_kind_names)}
        phases = TensorPhaseState.empty(len(battles), max_entities, device=core.device)

        for batch_index, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(core.entity_id[batch_index].tolist())
                if entity_id
            }
            for entity_id, entity in sorted(battle.entities.items()):
                slot = slot_by_id[entity_id]
                index = (batch_index, slot)
                status.stun_timer[index] = entity.stun_timer
                status.freeze_expiry_time[index] = entity.freeze_expiry_time
                status.slow_timer[index] = entity.slow_timer
                status.slow_multiplier[index] = entity.slow_multiplier
                status.attack_speed_debuff_multiplier[index] = (
                    entity.attack_speed_debuff_multiplier
                )
                status.spawn_speed_debuff_multiplier[index] = (
                    entity.spawn_speed_debuff_multiplier
                )
                status.haste_timer[index] = entity.haste_timer
                status.movement_speed_buff_multiplier[index] = (
                    entity.movement_speed_buff_multiplier
                )
                status.attack_speed_buff_multiplier[index] = (
                    entity.attack_speed_buff_multiplier
                )
                status.spawn_speed_buff_multiplier[index] = (
                    entity.spawn_speed_buff_multiplier
                )
                for source_slot, values in enumerate(entity._slow_effects):
                    remaining, movement, attack, spawn = values
                    source_index = (batch_index, slot, source_slot)
                    status.slow_active[source_index] = True
                    status.slow_remaining[source_index] = remaining
                    status.slow_movement[source_index] = movement
                    status.slow_attack[source_index] = attack
                    status.slow_spawn[source_index] = spawn
                for source_slot, values in enumerate(entity._haste_effects):
                    remaining, movement, attack, spawn = values
                    source_index = (batch_index, slot, source_slot)
                    status.haste_active[source_index] = True
                    status.haste_remaining[source_index] = remaining
                    status.haste_movement[source_index] = movement
                    status.haste_attack[source_index] = attack
                    status.haste_spawn[source_index] = spawn
                for sequence, effect in enumerate(
                    entity._periodic_damage_effects.values()
                ):
                    periodic_index = (*index, sequence)
                    status.periodic_active[periodic_index] = True
                    status.periodic_source_id[periodic_index] = effect.source_id
                    status.periodic_source_kind[periodic_index] = kind_to_id[
                        effect.source_kind
                    ]
                    status.periodic_remaining[periodic_index] = effect.remaining
                    status.periodic_interval[periodic_index] = effect.hit_interval
                    status.periodic_next_hit[periodic_index] = effect.time_to_next_hit
                    status.periodic_damage[periodic_index] = effect.damage
                    status.periodic_hard_active[periodic_index] = (
                        effect.hard_remaining is not None
                    )
                    status.periodic_hard_remaining[periodic_index] = (
                        0.0 if effect.hard_remaining is None else effect.hard_remaining
                    )
                    status.periodic_affects_hidden[periodic_index] = (
                        effect.affects_hidden
                    )
                    status.periodic_sequence[periodic_index] = sequence
                status.next_periodic_sequence[index] = len(
                    entity._periodic_damage_effects
                )
                phases.target_slot[index] = (
                    INVALID_SLOT
                    if entity.target_id is None
                    else slot_by_id.get(entity.target_id, INVALID_SLOT)
                )
                phases.movement_vector_units[batch_index, slot, 0] = (
                    entity._movement_vector_x_units
                )
                phases.movement_vector_units[batch_index, slot, 1] = (
                    entity._movement_vector_y_units
                )
                phases.movement_vector_count[index] = entity._movement_vector_count
                phases.movement_vector_bypasses_cap[index] = (
                    entity._movement_vector_bypasses_cap
                )
                phases.death_pending[index] = not entity.is_alive

        return cls(
            battle=core,
            entity_pool=pool,
            catalog=compiled,
            card_catalog_index=catalog_index,
            status=status,
            phases=phases,
            events=(
                TensorRuntimeEvents
                if execution_profile == RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG
                else TensorGymFastRuntimeEvents
            ).empty(
                len(battles), event_capacity, device=core.device
            ),
            supported=torch.ones(len(battles), dtype=torch.bool, device=core.device),
            dirty=torch.zeros(len(battles), dtype=torch.bool, device=core.device),
            status_source_kind_names=status_kind_names,
        )

    def assert_invariants(self) -> None:
        if self.entity_pool.entity_id is not self.battle.entity_id:
            raise ValueError("battle and pool must share the canonical entity IDs")
        if self.entity_pool.active.shape != self.battle.entity_id.shape:
            raise ValueError("entity presence shape differs from battle entity shape")
        self.entity_pool.assert_invariants()
        if self.supported.shape != (self.batch_size,):
            raise ValueError("supported must have shape [batch_size]")
        if self.dirty.shape != (self.batch_size,):
            raise ValueError("dirty must have shape [batch_size]")
        if self.phases.supported.shape != (self.batch_size, PHASE_COUNT):
            raise ValueError("phase support shape differs from runtime batch")
        if self.phases.target_slot.shape != self.battle.entity_id.shape:
            raise ValueError("phase entity shape differs from canonical slots")
        if self.status.entity_shape != self.battle.entity_id.shape:
            raise ValueError("status entity shape differs from canonical slots")
        if self.events.batch_size != self.batch_size:
            raise ValueError("event batch differs from runtime batch")

    def mark_unsupported(
        self,
        battle_mask: torch.Tensor,
        *,
        phase: TickPhase | None = None,
    ) -> None:
        selected = torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        if selected.shape != (self.batch_size,):
            raise ValueError("battle_mask must have shape [batch_size]")
        self.supported[selected] = False
        if phase is None:
            self.phases.supported[selected] = False
        else:
            self.phases.supported[selected, int(phase)] = False

    def mark_dirty(
        self,
        battle_mask: torch.Tensor,
        *,
        phase: TickPhase | None = None,
    ) -> None:
        selected = torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        if selected.shape != (self.batch_size,):
            raise ValueError("battle_mask must have shape [batch_size]")
        self.dirty[selected] = True
        if phase is None:
            self.phases.dirty[selected] = True
        else:
            self.phases.dirty[selected, int(phase)] = True

    def clear_dirty(self, battle_mask: torch.Tensor | None = None) -> None:
        selected = (
            torch.ones(self.batch_size, dtype=torch.bool, device=self.device)
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("battle_mask must have shape [batch_size]")
        self.dirty[selected] = False
        self.phases.dirty[selected] = False

    def clone(self) -> TensorBattleRuntime:
        return self.fork()

    def fork(
        self,
        battle_indices: Sequence[int] | torch.Tensor | None = None,
        *,
        copies: int = 1,
    ) -> TensorBattleRuntime:
        """Create independent speculative branches while sharing the catalog."""

        if copies < 1:
            raise ValueError("copies must be positive")
        indices = (
            torch.arange(self.batch_size, dtype=torch.int64, device=self.device)
            if battle_indices is None
            else torch.as_tensor(battle_indices, dtype=torch.int64, device=self.device)
        )
        if indices.ndim != 1 or indices.numel() < 1:
            raise ValueError("battle_indices must be a non-empty vector")
        if bool(((indices < 0) | (indices >= self.batch_size)).any().item()):
            raise IndexError("battle index outside runtime batch")
        indices = torch.repeat_interleave(indices, copies)
        battle = _select_tensor_dataclass(self.battle, indices)
        presence = self.entity_pool.active.index_select(0, indices).clone()
        pool = TensorEntityPool(
            next_entity_id=self.entity_pool.next_entity_id.index_select(
                0, indices
            ).clone(),
            active=presence,
            entity_id=battle.entity_id,
        )
        forked = TensorBattleRuntime(
            battle=battle,
            entity_pool=pool,
            catalog=self.catalog,
            card_catalog_index=self.card_catalog_index.clone(),
            status=_select_tensor_dataclass(self.status, indices),
            phases=_select_tensor_dataclass(self.phases, indices),
            events=_select_tensor_dataclass(self.events, indices),
            supported=self.supported.index_select(0, indices).clone(),
            dirty=self.dirty.index_select(0, indices).clone(),
            status_source_kind_names=self.status_source_kind_names,
        )
        forked.assert_invariants()
        return forked

    def sync_to_battles(self, battles: Sequence[BattleState]) -> None:
        """Write represented mutable state back to existing oracle objects.

        Entity allocation is intentionally a separate transaction: this
        adapter requires exactly the same identity set and therefore cannot
        accidentally construct a card-specific Python object.
        """

        if len(battles) != self.batch_size:
            raise ValueError("battle count does not match runtime batch")
        self.assert_invariants()
        for batch_index, battle in enumerate(battles):
            tensor_ids = tuple(
                int(value)
                for value in self.battle.entity_id[batch_index][
                    self.entity_pool.active[batch_index]
                ].tolist()
            )
            if set(tensor_ids) != set(battle.entities):
                raise ValueError("runtime/oracle entity identity sets differ")
        self.battle.sync_to_battles(battles)

        for batch_index, battle in enumerate(battles):
            battle.next_entity_id = int(
                self.entity_pool.next_entity_id[batch_index].item()
            )
            for slot in range(self.max_entities):
                if not bool(self.entity_pool.active[batch_index, slot].item()):
                    continue
                entity_id = int(self.battle.entity_id[batch_index, slot].item())
                entity = battle.entities[entity_id]
                index = (batch_index, slot)
                x = logic_units_to_tiles(int(self.battle.entity_x_units[index].item()))
                y = logic_units_to_tiles(int(self.battle.entity_y_units[index].item()))
                if entity.position.x != x or entity.position.y != y:
                    entity.position = Position(x, y)
                hitpoints = float(self.battle.entity_hp[index].item())
                if entity.hitpoints != hitpoints:
                    entity.hitpoints = hitpoints
                maximum = float(self.battle.entity_max_hp[index].item())
                if entity.max_hitpoints != maximum:
                    entity.max_hitpoints = maximum
                entity.is_alive = bool(self.battle.entity_active[index].item())

                target_slot = int(self.phases.target_slot[index].item())
                target_id = (
                    None
                    if target_slot == INVALID_SLOT
                    else int(self.battle.entity_id[batch_index, target_slot].item())
                )
                if entity.target_id != target_id:
                    entity.target_id = target_id
                entity._movement_vector_x_units = int(
                    self.phases.movement_vector_units[batch_index, slot, 0].item()
                )
                entity._movement_vector_y_units = int(
                    self.phases.movement_vector_units[batch_index, slot, 1].item()
                )
                entity._movement_vector_count = int(
                    self.phases.movement_vector_count[index].item()
                )
                entity._movement_vector_bypasses_cap = bool(
                    self.phases.movement_vector_bypasses_cap[index].item()
                )

                entity.stun_timer = float(self.status.stun_timer[index].item())
                entity.freeze_expiry_time = float(
                    self.status.freeze_expiry_time[index].item()
                )
                entity.slow_timer = float(self.status.slow_timer[index].item())
                entity.slow_multiplier = float(
                    self.status.slow_multiplier[index].item()
                )
                entity.attack_speed_debuff_multiplier = float(
                    self.status.attack_speed_debuff_multiplier[index].item()
                )
                entity.spawn_speed_debuff_multiplier = float(
                    self.status.spawn_speed_debuff_multiplier[index].item()
                )
                entity.haste_timer = float(self.status.haste_timer[index].item())
                entity.movement_speed_buff_multiplier = float(
                    self.status.movement_speed_buff_multiplier[index].item()
                )
                entity.attack_speed_buff_multiplier = float(
                    self.status.attack_speed_buff_multiplier[index].item()
                )
                entity.spawn_speed_buff_multiplier = float(
                    self.status.spawn_speed_buff_multiplier[index].item()
                )
                entity._slow_effects = [
                    (
                        float(
                            self.status.slow_remaining[batch_index, slot, source].item()
                        ),
                        float(
                            self.status.slow_movement[batch_index, slot, source].item()
                        ),
                        float(
                            self.status.slow_attack[batch_index, slot, source].item()
                        ),
                        float(self.status.slow_spawn[batch_index, slot, source].item()),
                    )
                    for source in range(self.status.max_slow_sources)
                    if bool(self.status.slow_active[batch_index, slot, source].item())
                ]
                entity._haste_effects = [
                    (
                        float(
                            self.status.haste_remaining[
                                batch_index, slot, source
                            ].item()
                        ),
                        float(
                            self.status.haste_movement[batch_index, slot, source].item()
                        ),
                        float(
                            self.status.haste_attack[batch_index, slot, source].item()
                        ),
                        float(
                            self.status.haste_spawn[batch_index, slot, source].item()
                        ),
                    )
                    for source in range(self.status.max_haste_sources)
                    if bool(self.status.haste_active[batch_index, slot, source].item())
                ]
                rebuilt: dict[int, PeriodicDamageEffect] = {}
                order = torch.argsort(
                    self.status.periodic_sequence[index], stable=True
                ).tolist()
                for source in order:
                    periodic_index = (batch_index, slot, source)
                    if not bool(self.status.periodic_active[periodic_index].item()):
                        continue
                    source_id = int(
                        self.status.periodic_source_id[periodic_index].item()
                    )
                    kind_id = int(
                        self.status.periodic_source_kind[periodic_index].item()
                    )
                    rebuilt[source_id] = PeriodicDamageEffect(
                        source_id=source_id,
                        source_kind=self.status_source_kind_names[kind_id],
                        remaining=float(
                            self.status.periodic_remaining[periodic_index].item()
                        ),
                        hit_interval=float(
                            self.status.periodic_interval[periodic_index].item()
                        ),
                        time_to_next_hit=float(
                            self.status.periodic_next_hit[periodic_index].item()
                        ),
                        damage=float(
                            self.status.periodic_damage[periodic_index].item()
                        ),
                        hard_remaining=(
                            float(
                                self.status.periodic_hard_remaining[
                                    periodic_index
                                ].item()
                            )
                            if bool(
                                self.status.periodic_hard_active[periodic_index].item()
                            )
                            else None
                        ),
                        affects_hidden=bool(
                            self.status.periodic_affects_hidden[periodic_index].item()
                        ),
                    )
                entity._periodic_damage_effects = rebuilt
        self.clear_dirty()
