"""Retained scheduled-spawn runtime for serialized Graveyard-style spells."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.entities import Graveyard, troop_from_character_data
from clasher.kinematics import tiles_to_logic_units
from clasher.spells import SPELL_REGISTRY, GraveyardSpell

from .entity_pool import INVALID_SLOT
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorGraveyardCatalog:
    supported: torch.Tensor
    reason: tuple[str, ...]
    duration_ms: torch.Tensor
    spawn_count: torch.Tensor
    deadlines_ms: torch.Tensor
    offsets_units: torch.Tensor
    mirror_x_at_center: torch.Tensor
    orient_y_by_player: torch.Tensor
    child_card_id: torch.Tensor
    child_hitpoints: torch.Tensor
    child_hp_integer_kind: torch.Tensor
    child_deploy_ms: torch.Tensor
    max_spawns: int

    @property
    def device(self) -> torch.device:
        return self.supported.device

    @property
    def size(self) -> int:
        return int(self.supported.numel())

    @classmethod
    def compile(cls, runtime: TensorBattleRuntime) -> TensorGraveyardCatalog:
        spells = [
            spell
            for name in runtime.battle.card_names
            if isinstance((spell := SPELL_REGISTRY.get(name)), GraveyardSpell)
        ]
        max_spawns = max((spell.max_skeletons for spell in spells), default=1)
        size = len(runtime.battle.card_names)
        device = runtime.device

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = zeros(torch.bool)
        duration = zeros(torch.int32)
        count = zeros(torch.int16)
        deadlines = torch.zeros((size, max_spawns), dtype=torch.int32, device=device)
        offsets = torch.zeros((size, max_spawns, 2), dtype=torch.int32, device=device)
        mirror = zeros(torch.bool)
        orient = zeros(torch.bool)
        child_card = torch.full((size,), -1, dtype=torch.int64, device=device)
        child_hp = zeros(torch.float64)
        child_hp_kind = zeros(torch.bool)
        child_deploy = zeros(torch.int32)
        reasons = ["not a retained serialized scheduled-spawn area"] * size

        for card_id, name in enumerate(runtime.battle.card_names):
            spell = SPELL_REGISTRY.get(name)
            if not isinstance(spell, GraveyardSpell):
                continue
            child = runtime.battle.card_to_id.get(spell.spawn_character)
            if child is None or int(runtime.card_catalog_index[child].item()) < 0:
                reasons[card_id] = "scheduled-spawn child is absent from core catalog"
                continue
            if not spell.skeleton_data or spell.max_skeletons < 1:
                reasons[card_id] = "scheduled-spawn child metadata is incomplete"
                continue
            if len(spell.spawn_offsets) < spell.max_skeletons:
                reasons[card_id] = "serialized fixed spawn pattern is incomplete"
                continue
            raw_deadlines = spell.spawn_deadlines or tuple(
                spell.initial_spawn_delay + index * spell.spawn_interval
                for index in range(spell.max_skeletons)
            )
            if len(raw_deadlines) < spell.max_skeletons:
                reasons[card_id] = "serialized spawn deadline schedule is incomplete"
                continue
            millisecond_values = (
                spell.duration,
                *(raw_deadlines[: spell.max_skeletons]),
                *(
                    coordinate
                    for offset in spell.spawn_offsets
                    for coordinate in offset
                ),
            )
            if any(
                abs(value * 1_000 - round(value * 1_000)) > 1e-9
                for value in millisecond_values
            ):
                reasons[card_id] = "scheduled-spawn timing or offset is off native grid"
                continue
            child_stats = troop_from_character_data(
                spell.spawn_character,
                spell.skeleton_data,
                elixir=0,
                rarity=spell.skeleton_data.get("rarity", "Common"),
            )
            hp = child_stats.scaled_hitpoints
            if hp is None:
                hp = child_stats.hitpoints
            if hp is None:
                reasons[card_id] = "scheduled-spawn child hitpoints are absent"
                continue
            supported[card_id] = True
            reasons[card_id] = ""
            duration[card_id] = round(spell.duration * 1_000)
            count[card_id] = spell.max_skeletons
            deadlines[card_id, : spell.max_skeletons] = torch.tensor(
                [
                    round(value * 1_000)
                    for value in raw_deadlines[: spell.max_skeletons]
                ],
                dtype=torch.int32,
                device=device,
            )
            offsets[card_id, : spell.max_skeletons] = torch.tensor(
                [
                    (tiles_to_logic_units(x), tiles_to_logic_units(y))
                    for x, y in spell.spawn_offsets[: spell.max_skeletons]
                ],
                dtype=torch.int32,
                device=device,
            )
            mirror[card_id] = spell.mirror_pattern_x_at_center
            orient[card_id] = spell.orient_pattern_y_by_player
            child_card[card_id] = child
            child_hp[card_id] = hp
            child_hp_kind[card_id] = type(hp) is int
            child_deploy[card_id] = round(
                max(0.0, spell.spawn_deploy_delay_override or 0.0) * 1_000
            )

        return cls(
            supported=supported,
            reason=tuple(reasons),
            duration_ms=duration,
            spawn_count=count,
            deadlines_ms=deadlines,
            offsets_units=offsets,
            mirror_x_at_center=mirror,
            orient_y_by_player=orient,
            child_card_id=child_card,
            child_hitpoints=child_hp,
            child_hp_integer_kind=child_hp_kind,
            child_deploy_ms=child_deploy,
            max_spawns=max_spawns,
        )


@dataclass(frozen=True)
class GraveyardStepResult:
    committed: torch.Tensor
    spawned: torch.Tensor
    spawned_ids: torch.Tensor
    expired: torch.Tensor


@dataclass
class TensorResidentGraveyards:
    catalog: TensorGraveyardCatalog
    active: torch.Tensor
    graveyard_id: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    age_ms: torch.Tensor
    next_spawn_index: torch.Tensor
    target_distance_discount_sq_units: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.active.device

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def capacity(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        capacity: int = 4,
    ) -> TensorResidentGraveyards:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match Graveyard runtime")
        if capacity < 1:
            raise ValueError("Graveyard capacity must be positive")
        catalog = TensorGraveyardCatalog.compile(runtime)
        shape = (runtime.batch_size, capacity)
        owner = cls(
            catalog=catalog,
            active=torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            graveyard_id=torch.zeros(shape, dtype=torch.int64, device=runtime.device),
            card_id=torch.zeros(shape, dtype=torch.int64, device=runtime.device),
            player_id=torch.zeros(shape, dtype=torch.int8, device=runtime.device),
            x_units=torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            y_units=torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            age_ms=torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            next_spawn_index=torch.zeros(
                shape, dtype=torch.int16, device=runtime.device
            ),
            target_distance_discount_sq_units=torch.zeros(
                (runtime.batch_size, runtime.max_entities),
                dtype=torch.int64,
                device=runtime.device,
            ),
        )
        for row, battle in enumerate(battles):
            live = [
                entity
                for entity in battle.entities.values()
                if type(entity) is Graveyard
            ]
            if len(live) > capacity:
                raise ValueError("live Graveyards exceed retained capacity")
            for slot, graveyard in enumerate(live):
                card = runtime.battle.card_to_id.get(
                    str(getattr(graveyard, "spell_name", "")), -1
                )
                if card < 0 or not bool(catalog.supported[card].item()):
                    raise ValueError(
                        "live Graveyard payload is outside retained coverage"
                    )
                owner.active[row, slot] = True
                owner.graveyard_id[row, slot] = graveyard.id
                owner.card_id[row, slot] = card
                owner.player_id[row, slot] = graveyard.player_id
                owner.x_units[row, slot] = tiles_to_logic_units(graveyard.position.x)
                owner.y_units[row, slot] = tiles_to_logic_units(graveyard.position.y)
                owner.age_ms[row, slot] = round(graveyard.time_alive * 1_000)
                owner.next_spawn_index[row, slot] = graveyard.skeletons_spawned
        return owner

    def clone(self) -> TensorResidentGraveyards:
        return type(self)(
            catalog=self.catalog,
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
                if descriptor.name != "catalog"
            },
        )

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentGraveyards:
        index = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if index.ndim != 1:
            raise ValueError("Graveyard fork rows must be one-dimensional")
        return type(self)(
            catalog=self.catalog,
            **{
                descriptor.name: getattr(self, descriptor.name)[index].clone()
                for descriptor in fields(self)
                if descriptor.name != "catalog"
            },
        )

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentGraveyards,
        source_rows: torch.Tensor | list[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(
            destination_rows, dtype=torch.int64, device=self.device
        )
        selected = (
            torch.arange(destination.numel(), dtype=torch.int64, device=self.device)
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        if destination.shape != selected.shape:
            raise ValueError("Graveyard reset rows have unequal shapes")
        for descriptor in fields(self):
            if descriptor.name == "catalog":
                continue
            getattr(self, descriptor.name)[destination] = getattr(
                source, descriptor.name
            )[selected]

    def materialize_due_spell_actions_(
        self,
        runtime: TensorBattleRuntime,
        *,
        card_ids: torch.Tensor,
        player_ids: torch.Tensor,
        target_x_units: torch.Tensor,
        target_y_units: torch.Tensor,
        valid: torch.Tensor,
    ) -> torch.Tensor:
        planes = (card_ids, player_ids, target_x_units, target_y_units, valid)
        if any(value.shape != (self.batch_size,) for value in planes):
            raise ValueError("Graveyard due command planes must have shape [batch]")
        in_range = (card_ids >= 0) & (card_ids < self.catalog.size)
        safe = card_ids.clamp(0, self.catalog.size - 1)
        free = ~self.active
        supported = runtime.supported & ~(
            valid
            & (
                ~in_range
                | ~((player_ids == 0) | (player_ids == 1))
                | ~self.catalog.supported[safe]
                | ~free.any(dim=1)
                | ~(~runtime.entity_pool.active).any(dim=1)
                | (runtime.events.count >= runtime.events.capacity)
            )
        )
        admitted = valid & supported
        allocation = runtime.entity_pool.allocate(admitted.to(torch.int64))
        owner_slot = free.to(torch.int64).argmax(dim=1)
        rows = torch.where(admitted)[0]
        lanes = owner_slot[rows]
        entity_slots = allocation.slots[rows, 0]
        identifiers = allocation.entity_ids[rows, 0]
        cards = safe[rows]
        self.active[rows, lanes] = True
        self.graveyard_id[rows, lanes] = identifiers
        self.card_id[rows, lanes] = cards
        self.player_id[rows, lanes] = player_ids[rows].to(torch.int8)
        self.x_units[rows, lanes] = target_x_units[rows].to(torch.int32)
        self.y_units[rows, lanes] = target_y_units[rows].to(torch.int32)
        self.age_ms[rows, lanes] = 0
        self.next_spawn_index[rows, lanes] = 0
        _clear_entity_slots(runtime, rows, entity_slots)
        runtime.entity_pool.active[rows, entity_slots] = True
        runtime.battle.entity_id[rows, entity_slots] = identifiers
        runtime.battle.entity_active[rows, entity_slots] = True
        runtime.battle.entity_kind[rows, entity_slots] = 3
        runtime.battle.entity_player[rows, entity_slots] = player_ids[rows].to(
            torch.int8
        )
        runtime.battle.entity_card[rows, entity_slots] = 0
        runtime.battle.entity_x_units[rows, entity_slots] = target_x_units[rows].to(
            torch.int32
        )
        runtime.battle.entity_y_units[rows, entity_slots] = target_y_units[rows].to(
            torch.int32
        )
        runtime.battle.entity_hp[rows, entity_slots] = 1
        runtime.battle.entity_hp_integer_kind[rows, entity_slots] = True
        runtime.battle.entity_max_hp[rows, entity_slots] = 1
        runtime.battle.entity_tower_slot[rows, entity_slots] = -1
        runtime.phases.target_slot[rows, entity_slots] = INVALID_SLOT
        self.target_distance_discount_sq_units[rows, entity_slots] = 0
        runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=allocation.valid,
            source_id=0,
            target_id=allocation.entity_ids,
            x_units=target_x_units[:, None],
            y_units=target_y_units[:, None],
            payload=safe[:, None],
        )
        return supported

    materialize_spell_actions_ = materialize_due_spell_actions_

    def step_(self, runtime: TensorBattleRuntime) -> GraveyardStepResult:
        """Advance all schedules and install due children in stable ID order."""

        owner = self.clone()
        cards = owner.card_id.clamp(0, owner.catalog.size - 1)
        selected = owner.active & runtime.supported[:, None]
        age_after = owner.age_ms.to(torch.int64) + runtime.battle.tick_milliseconds[
            :, None
        ].to(torch.int64)
        duration = owner.catalog.duration_ms[cards].to(torch.int64)
        deadline = torch.minimum(age_after, duration)
        spawn_index = torch.arange(
            owner.catalog.max_spawns, dtype=torch.int64, device=self.device
        )[None, None, :]
        count = owner.catalog.spawn_count[cards].to(torch.int64)[:, :, None]
        deadlines = owner.catalog.deadlines_ms[cards].to(torch.int64)
        due = (
            selected[:, :, None]
            & (spawn_index >= owner.next_spawn_index.to(torch.int64)[:, :, None])
            & (spawn_index < count)
            & (deadlines <= deadline[:, :, None])
        )
        due_count = due.flatten(1).sum(dim=1, dtype=torch.int64)
        expired = selected & (age_after >= duration)
        supported = (
            runtime.supported
            & (due_count <= (~runtime.entity_pool.active).sum(dim=1))
            & (
                runtime.events.count.to(torch.int64)
                + due_count
                + 2 * expired.sum(dim=1, dtype=torch.int64)
                <= runtime.events.capacity
            )
        )
        due &= supported[:, None, None]
        expired &= supported[:, None]
        due_count = due.flatten(1).sum(dim=1, dtype=torch.int64)
        allocation = runtime.entity_pool.allocate(due_count)
        maximum_key = torch.iinfo(torch.int64).max
        stable_key = (
            owner.graveyard_id[:, :, None] * (owner.catalog.max_spawns + 1)
            + spawn_index
        )
        flat_order = torch.argsort(
            torch.where(due, stable_key, maximum_key).flatten(1),
            dim=1,
            stable=True,
        )
        valid = allocation.valid
        rows, ordinal = torch.where(valid)
        flat = flat_order[rows, ordinal]
        area_lane = torch.div(flat, owner.catalog.max_spawns, rounding_mode="floor")
        child_index = torch.remainder(flat, owner.catalog.max_spawns)
        card = cards[rows, area_lane]
        player = owner.player_id[rows, area_lane].to(torch.int64)
        offset = owner.catalog.offsets_units[card, child_index].to(torch.int64)
        offset_x = offset[:, 0]
        offset_y = offset[:, 1]
        center_x = owner.x_units[rows, area_lane].to(torch.int64)
        center_y = owner.y_units[rows, area_lane].to(torch.int64)
        offset_x = torch.where(
            owner.catalog.mirror_x_at_center[card] & (center_x > 9_000),
            -offset_x,
            offset_x,
        )
        offset_y = torch.where(
            owner.catalog.orient_y_by_player[card] & (player == 1),
            -offset_y,
            offset_y,
        )
        legacy_flip = (
            ~owner.catalog.mirror_x_at_center[card]
            & ~owner.catalog.orient_y_by_player[card]
            & (player == 1)
        )
        offset_x = torch.where(legacy_flip, -offset_x, offset_x)
        offset_y = torch.where(legacy_flip, -offset_y, offset_y)
        spawn_x = (center_x + offset_x).clamp(250, 17_750).to(torch.int32)
        spawn_y = (center_y + offset_y).clamp(250, 31_750).to(torch.int32)
        entity_slots = allocation.slots[rows, ordinal]
        entity_ids = allocation.entity_ids[rows, ordinal]
        _clear_entity_slots(runtime, rows, entity_slots)
        runtime.entity_pool.active[rows, entity_slots] = True
        runtime.battle.entity_id[rows, entity_slots] = entity_ids
        runtime.battle.entity_active[rows, entity_slots] = True
        runtime.battle.entity_kind[rows, entity_slots] = 0
        runtime.battle.entity_player[rows, entity_slots] = player.to(torch.int8)
        child_card = owner.catalog.child_card_id[card]
        runtime.battle.entity_card[rows, entity_slots] = child_card
        runtime.battle.entity_x_units[rows, entity_slots] = spawn_x
        runtime.battle.entity_y_units[rows, entity_slots] = spawn_y
        hp = owner.catalog.child_hitpoints[card]
        runtime.battle.entity_hp[rows, entity_slots] = hp
        runtime.battle.entity_hp_integer_kind[rows, entity_slots] = (
            owner.catalog.child_hp_integer_kind[card]
        )
        runtime.battle.entity_max_hp[rows, entity_slots] = hp
        deploy_ms = owner.catalog.child_deploy_ms[card].to(torch.int64)
        runtime.battle.entity_deploy_delay[rows, entity_slots] = (
            deploy_ms.to(torch.float64) / 1_000
        )
        pending = deploy_ms > 0
        runtime.battle.entity_placement_pending[rows, entity_slots] = pending
        runtime.battle.entity_spawn_hook_pending[rows, entity_slots] = pending
        runtime.battle.entity_spawn_hook_fired[rows, entity_slots] = ~pending
        runtime.battle.entity_tower_slot[rows, entity_slots] = -1
        runtime.phases.target_slot[rows, entity_slots] = INVALID_SLOT
        owner.target_distance_discount_sq_units[rows, entity_slots] = 0

        spawn_source = torch.zeros_like(allocation.entity_ids)
        spawn_payload = torch.zeros_like(allocation.entity_ids)
        spawn_x_plane = torch.zeros_like(allocation.slots, dtype=torch.int32)
        spawn_y_plane = torch.zeros_like(allocation.slots, dtype=torch.int32)
        spawn_source[rows, ordinal] = entity_ids
        spawn_payload[rows, ordinal] = child_card
        spawn_x_plane[rows, ordinal] = spawn_x
        spawn_y_plane[rows, ordinal] = spawn_y
        runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=allocation.valid,
            source_id=spawn_source,
            x_units=spawn_x_plane,
            y_units=spawn_y_plane,
            payload=spawn_payload,
        )

        spawned_per_area = due.sum(dim=2, dtype=torch.int64)
        owner.next_spawn_index.copy_(
            torch.where(
                selected & supported[:, None],
                owner.next_spawn_index.to(torch.int64) + spawned_per_area,
                owner.next_spawn_index.to(torch.int64),
            ).to(torch.int16)
        )
        owner.age_ms.copy_(
            torch.where(
                selected & supported[:, None],
                age_after,
                owner.age_ms.to(torch.int64),
            ).to(torch.int32)
        )

        area_slots = runtime.entity_pool.slots_for_ids(owner.graveyard_id)
        valid_expired = expired & (area_slots >= 0)
        death_ids = owner.graveyard_id.clone()
        pair_valid = torch.stack((valid_expired, valid_expired), dim=2).flatten(1)
        pair_ids = torch.stack((death_ids, death_ids), dim=2).flatten(1)
        runtime.events.append(
            phase=TickPhase.COMBAT,
            opcode=torch.stack(
                (
                    torch.full_like(death_ids, RuntimeEventOpcode.DAMAGE),
                    torch.full_like(death_ids, RuntimeEventOpcode.DEATH),
                ),
                dim=2,
            ).flatten(1),
            valid=pair_valid,
            target_id=pair_ids,
            amount=torch.stack(
                (
                    torch.ones_like(death_ids, dtype=torch.float64),
                    torch.zeros_like(death_ids, dtype=torch.float64),
                ),
                dim=2,
            ).flatten(1),
        )
        expire_rows, expire_lanes = torch.where(valid_expired)
        physical = area_slots[expire_rows, expire_lanes]
        runtime.battle.entity_active[expire_rows, physical] = False
        dead = torch.zeros_like(runtime.entity_pool.active)
        dead[expire_rows, physical] = True
        runtime.entity_pool.cleanup(dead)
        _clear_entity_mask(runtime, dead)
        owner.active &= ~expired
        for name in (
            "graveyard_id",
            "card_id",
            "player_id",
            "x_units",
            "y_units",
            "age_ms",
            "next_spawn_index",
        ):
            getattr(owner, name).masked_fill_(expired, 0)
        self.reset_rows_(torch.where(supported)[0], owner, torch.where(supported)[0])
        return GraveyardStepResult(
            committed=supported,
            spawned=allocation.valid,
            spawned_ids=allocation.entity_ids,
            expired=expired,
        )


def _clear_entity_slots(
    runtime: TensorBattleRuntime, rows: torch.Tensor, slots: torch.Tensor
) -> None:
    mask = torch.zeros_like(runtime.entity_pool.active)
    mask[rows, slots] = True
    _clear_entity_mask(runtime, mask)


def _clear_entity_mask(runtime: TensorBattleRuntime, mask: torch.Tensor) -> None:
    for descriptor in fields(runtime.battle):
        value = getattr(runtime.battle, descriptor.name)
        if (
            descriptor.name.startswith("entity_")
            and descriptor.name != "entity_id"
            and isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[:2] == mask.shape
        ):
            expanded = mask.reshape(*mask.shape, *((1,) * (value.ndim - 2)))
            value.masked_fill_(
                expanded, -1 if descriptor.name == "entity_tower_slot" else 0
            )
    for owner in (runtime.status, runtime.phases):
        for descriptor in fields(owner):
            if owner is runtime.phases and descriptor.name in {
                "phase_cursor",
                "supported",
                "dirty",
            }:
                continue
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == mask.shape
            ):
                expanded = mask.reshape(*mask.shape, *((1,) * (value.ndim - 2)))
                value.masked_fill_(expanded, 0)
    runtime.phases.target_slot.masked_fill_(mask, INVALID_SLOT)


__all__ = [
    "GraveyardStepResult",
    "TensorGraveyardCatalog",
    "TensorResidentGraveyards",
]
