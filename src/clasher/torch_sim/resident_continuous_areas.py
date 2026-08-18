"""Retained tensor owner for serialized continuous spell areas.

The owner is integration-neutral: delayed command handling calls
``materialize_due_spell_actions_`` only when the universal server deadline is
due, then ordinary status/object phases call ``step_status_`` and ``step_``.
Compilation is data driven from normalized :class:`AreaEffectSpell` fields;
unsupported payload shapes fail closed before allocation or RNG mutation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.entities import AreaEffect, Building
from clasher.kinematics import tiles_to_logic_units
from clasher.spells import SPELL_REGISTRY, AreaEffectSpell
from clasher.unit_traits import is_airborne_target

from .entity_pool import INVALID_SLOT
from .resident_spell_ingress import _copy_runtime_rows
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase

AREA_EPSILON_MS = 1e-6


@dataclass(frozen=True)
class TensorContinuousAreaCatalog:
    supported: torch.Tensor
    reason: tuple[str, ...]
    duration_ms: torch.Tensor
    radius_units: torch.Tensor
    damage: torch.Tensor
    damage_interval_ms: torch.Tensor
    initial_damage_ms: torch.Tensor
    max_damage_ticks: torch.Tensor
    freeze_snapshot: torch.Tensor
    movement_multiplier: torch.Tensor
    attack_multiplier: torch.Tensor
    spawn_multiplier: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    affects_hidden: torch.Tensor
    crown_multiplier: torch.Tensor
    crown_damage: torch.Tensor
    crown_damage_valid: torch.Tensor
    building_multiplier: torch.Tensor
    building_damage: torch.Tensor
    building_damage_valid: torch.Tensor
    effect_interval_ms: torch.Tensor
    slow_refresh_ms: torch.Tensor
    cap_slow_to_area: torch.Tensor
    target_local_damage: torch.Tensor
    periodic_duration_ms: torch.Tensor
    periodic_controlled_by_parent: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.supported.device

    @property
    def size(self) -> int:
        return int(self.supported.numel())

    @classmethod
    def compile(cls, runtime: TensorBattleRuntime) -> TensorContinuousAreaCatalog:
        count = len(runtime.battle.card_names)
        device = runtime.device

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(count, dtype=dtype, device=device)

        supported = zeros(torch.bool)
        duration = zeros(torch.int32)
        radius = zeros(torch.int32)
        damage = zeros(torch.float64)
        damage_interval = zeros(torch.int32)
        initial_damage = zeros(torch.int32)
        maximum_ticks = zeros(torch.int16)
        freeze = zeros(torch.bool)
        movement = torch.ones(count, dtype=torch.float64, device=device)
        attack = torch.ones_like(movement)
        spawn = torch.ones_like(movement)
        hits_air = zeros(torch.bool)
        hits_ground = zeros(torch.bool)
        affects_hidden = zeros(torch.bool)
        crown_multiplier = torch.ones_like(movement)
        crown_damage = zeros(torch.float64)
        crown_damage_valid = zeros(torch.bool)
        building_multiplier = torch.ones_like(movement)
        building_damage = zeros(torch.float64)
        building_damage_valid = zeros(torch.bool)
        effect_interval = zeros(torch.int32)
        slow_refresh = zeros(torch.int32)
        cap_slow = zeros(torch.bool)
        target_local = zeros(torch.bool)
        periodic_duration = zeros(torch.int32)
        periodic_parent = zeros(torch.bool)
        reasons = ["not a retained serialized continuous area"] * count

        for card_id, name in enumerate(runtime.battle.card_names):
            spell = SPELL_REGISTRY.get(name)
            if not isinstance(spell, AreaEffectSpell):
                continue
            timing_values = (
                spell.duration,
                spell.damage_tick_interval,
                spell.effect_tick_interval,
                spell.slow_refresh_duration,
                spell.periodic_damage_buff_duration,
            )
            if any(
                abs(value * 1_000 - round(value * 1_000)) > 1e-9
                for value in timing_values
            ):
                reasons[card_id] = "continuous-area timing is not integral milliseconds"
                continue
            if spell.duration <= 0 or spell.radius < 0:
                reasons[card_id] = "continuous-area lifetime or radius is invalid"
                continue
            if spell.target_local_damage and (
                spell.damage_tick_interval <= 0
                or spell.periodic_damage_buff_duration <= 0
            ):
                reasons[card_id] = "target-local periodic damage metadata is incomplete"
                continue
            supported[card_id] = True
            reasons[card_id] = ""
            duration[card_id] = round(spell.duration * 1_000)
            radius[card_id] = tiles_to_logic_units(spell.radius)
            damage[card_id] = spell.damage
            damage_interval[card_id] = round(spell.damage_tick_interval * 1_000)
            initial = spell.initial_damage_delay
            if initial is None:
                initial = 0.0 if spell.damage_on_spawn else spell.damage_tick_interval
            initial_damage[card_id] = round(initial * 1_000)
            maximum_ticks[card_id] = spell.max_damage_ticks
            freeze[card_id] = spell.freeze_effect
            movement[card_id] = spell.speed_multiplier
            attack[card_id] = (
                spell.speed_multiplier if spell.slows_attack_speed else 1.0
            )
            spawn[card_id] = spell.speed_multiplier if spell.slows_spawn_speed else 1.0
            hits_air[card_id] = spell.hits_air
            hits_ground[card_id] = spell.hits_ground
            affects_hidden[card_id] = spell.affects_hidden
            crown_multiplier[card_id] = spell.crown_tower_damage_multiplier
            if spell.crown_tower_damage is not None:
                crown_damage[card_id] = spell.crown_tower_damage
                crown_damage_valid[card_id] = True
            building_multiplier[card_id] = spell.building_damage_multiplier
            if spell.building_damage is not None:
                building_damage[card_id] = spell.building_damage
                building_damage_valid[card_id] = True
            effect_interval[card_id] = max(
                50, round(spell.effect_tick_interval * 1_000)
            )
            slow_refresh[card_id] = round(spell.slow_refresh_duration * 1_000)
            cap_slow[card_id] = spell.cap_buff_time_to_effect
            target_local[card_id] = spell.target_local_damage
            periodic_duration[card_id] = round(
                spell.periodic_damage_buff_duration * 1_000
            )
            periodic_parent[card_id] = spell.periodic_damage_controlled_by_parent

        return cls(
            supported=supported,
            reason=tuple(reasons),
            duration_ms=duration,
            radius_units=radius,
            damage=damage,
            damage_interval_ms=damage_interval,
            initial_damage_ms=initial_damage,
            max_damage_ticks=maximum_ticks,
            freeze_snapshot=freeze,
            movement_multiplier=movement,
            attack_multiplier=attack,
            spawn_multiplier=spawn,
            hits_air=hits_air,
            hits_ground=hits_ground,
            affects_hidden=affects_hidden,
            crown_multiplier=crown_multiplier,
            crown_damage=crown_damage,
            crown_damage_valid=crown_damage_valid,
            building_multiplier=building_multiplier,
            building_damage=building_damage,
            building_damage_valid=building_damage_valid,
            effect_interval_ms=effect_interval,
            slow_refresh_ms=slow_refresh,
            cap_slow_to_area=cap_slow,
            target_local_damage=target_local,
            periodic_duration_ms=periodic_duration,
            periodic_controlled_by_parent=periodic_parent,
        )


@dataclass
class TensorContinuousAreaTargets:
    entity_id: torch.Tensor
    collision_radius_units: torch.Tensor
    airborne: torch.Tensor
    building: torch.Tensor
    crown: torch.Tensor
    freeze_carrier: torch.Tensor
    damage_receivable: torch.Tensor
    effect_receivable: torch.Tensor

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        catalog: TensorContinuousAreaCatalog,
    ) -> TensorContinuousAreaTargets:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match continuous-area runtime")
        shape = (runtime.batch_size, runtime.max_entities)
        device = runtime.device
        entity_id = runtime.battle.entity_id.clone()
        radius = torch.zeros(shape, dtype=torch.int32, device=device)
        airborne = torch.zeros(shape, dtype=torch.bool, device=device)
        building = torch.zeros(shape, dtype=torch.bool, device=device)
        crown = torch.zeros(shape, dtype=torch.bool, device=device)
        freeze_carrier = torch.zeros(shape, dtype=torch.bool, device=device)
        damage = torch.zeros((*shape, catalog.size), dtype=torch.bool, device=device)
        effect = torch.zeros_like(damage)
        for row, battle in enumerate(battles):
            slot_by_id = {
                int(value): slot
                for slot, value in enumerate(runtime.battle.entity_id[row].tolist())
                if int(value) > 0
            }
            for object_id, entity in battle.entities.items():
                slot = slot_by_id[object_id]
                radius[row, slot] = tiles_to_logic_units(entity.get_collision_radius())
                airborne[row, slot] = is_airborne_target(entity)
                building[row, slot] = isinstance(entity, Building)
                crown[row, slot] = isinstance(entity, Building) and getattr(
                    entity.card_stats, "name", ""
                ) in {"Tower", "KingTower"}
                freeze_carrier[row, slot] = bool(
                    getattr(entity, "entity_kind", 4) in {2, 3}
                    and getattr(entity, "carries_freeze_to_children", False)
                )
                for card_id, name in enumerate(runtime.battle.card_names):
                    if not bool(catalog.supported[card_id].item()):
                        continue
                    hidden = bool(catalog.affects_hidden[card_id].item())
                    damage[row, slot, card_id] = entity.can_receive_area_damage(
                        name, affects_hidden=hidden
                    )
                    effect[row, slot, card_id] = entity.can_receive_effect(
                        name, affects_hidden=hidden
                    )
        return cls(
            entity_id,
            radius,
            airborne,
            building,
            crown,
            freeze_carrier,
            damage,
            effect,
        )

    def fork(self, rows: torch.Tensor) -> TensorContinuousAreaTargets:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name)[rows].clone()
                for descriptor in fields(self)
            }
        )


@dataclass(frozen=True)
class ContinuousAreaStepResult:
    committed: torch.Tensor
    damage: torch.Tensor
    died: torch.Tensor
    expired: torch.Tensor


@dataclass
class TensorResidentContinuousAreas:
    catalog: TensorContinuousAreaCatalog
    targets: TensorContinuousAreaTargets
    active: torch.Tensor
    area_id: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    age_ms: torch.Tensor
    next_damage_ms: torch.Tensor
    damage_ticks_applied: torch.Tensor
    next_effect_ms: torch.Tensor
    freeze_applied: torch.Tensor

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
        capacity: int = 8,
    ) -> TensorResidentContinuousAreas:
        if capacity < 1:
            raise ValueError("continuous-area capacity must be positive")
        catalog = TensorContinuousAreaCatalog.compile(runtime)
        targets = TensorContinuousAreaTargets.from_battles(runtime, battles, catalog)
        shape = (runtime.batch_size, capacity)
        kwargs: dict[str, torch.Tensor] = {
            "active": torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            "area_id": torch.zeros(shape, dtype=torch.int64, device=runtime.device),
            "card_id": torch.zeros(shape, dtype=torch.int64, device=runtime.device),
            "player_id": torch.zeros(shape, dtype=torch.int8, device=runtime.device),
            "x_units": torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            "y_units": torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            "age_ms": torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            "next_damage_ms": torch.zeros(
                shape, dtype=torch.int32, device=runtime.device
            ),
            "damage_ticks_applied": torch.zeros(
                shape, dtype=torch.int16, device=runtime.device
            ),
            "next_effect_ms": torch.zeros(
                shape, dtype=torch.int32, device=runtime.device
            ),
            "freeze_applied": torch.zeros(
                shape, dtype=torch.bool, device=runtime.device
            ),
        }
        owner = cls(catalog=catalog, targets=targets, **kwargs)
        for row, battle in enumerate(battles):
            areas = [
                entity
                for entity in battle.entities.values()
                if type(entity) is AreaEffect
            ]
            if len(areas) > capacity:
                raise ValueError("live continuous areas exceed retained capacity")
            for slot, area in enumerate(areas):
                card = runtime.battle.card_to_id.get(
                    str(getattr(area, "spell_name", "")), -1
                )
                if card < 0 or not bool(catalog.supported[card].item()):
                    raise ValueError("live area payload is outside retained coverage")
                owner.active[row, slot] = True
                owner.area_id[row, slot] = area.id
                owner.card_id[row, slot] = card
                owner.player_id[row, slot] = area.player_id
                owner.x_units[row, slot] = tiles_to_logic_units(area.position.x)
                owner.y_units[row, slot] = tiles_to_logic_units(area.position.y)
                owner.age_ms[row, slot] = round(area.time_alive * 1_000)
                owner.next_damage_ms[row, slot] = round(
                    (area.next_damage_time or 0.0) * 1_000
                )
                owner.damage_ticks_applied[row, slot] = area.damage_ticks_applied
                owner.next_effect_ms[row, slot] = round(
                    (area.next_effect_time or 0.0) * 1_000
                )
                owner.freeze_applied[row, slot] = area.freeze_targets_applied
        return owner

    def clone(self) -> TensorResidentContinuousAreas:
        rows = torch.arange(self.batch_size, dtype=torch.int64, device=self.device)
        return type(self)(
            catalog=self.catalog,
            targets=self.targets.fork(rows),
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
                if descriptor.name not in {"catalog", "targets"}
            },
        )

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentContinuousAreas:
        index = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        result = self.clone()
        result.targets = self.targets.fork(index)
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "targets"}:
                continue
            setattr(
                result, descriptor.name, getattr(self, descriptor.name)[index].clone()
            )
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentContinuousAreas,
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
            raise ValueError("continuous-area reset rows have unequal shapes")
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "targets"}:
                continue
            getattr(self, descriptor.name)[destination] = getattr(
                source, descriptor.name
            )[selected]
        for descriptor in fields(self.targets):
            getattr(self.targets, descriptor.name)[destination] = getattr(
                source.targets, descriptor.name
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
        """Materialize only commands already admitted by the server-delay owner."""

        if card_ids.shape != (self.batch_size,):
            raise ValueError("continuous-area due cards must have shape [batch]")
        if any(
            value.shape != (self.batch_size,)
            for value in (
                player_ids,
                target_x_units,
                target_y_units,
                valid,
            )
        ):
            raise ValueError(
                "continuous-area due command planes must have shape [batch]"
            )
        in_range = (card_ids >= 0) & (card_ids < self.catalog.size)
        valid_player = (player_ids == 0) | (player_ids == 1)
        safe = card_ids.clamp(0, self.catalog.size - 1)
        free_area = ~self.active
        supported = runtime.supported & ~(
            valid
            & (
                ~in_range
                | ~valid_player
                | ~self.catalog.supported[safe]
                | ~free_area.any(dim=1)
                | ~(~runtime.entity_pool.active).any(dim=1)
                | (runtime.events.count >= runtime.events.capacity)
            )
        )
        admitted = valid & supported
        counts = admitted.to(torch.int64)
        allocation = runtime.entity_pool.allocate(counts)
        area_slot = free_area.to(torch.int64).argmax(dim=1)
        rows = torch.where(admitted)[0]
        slots = area_slot[rows]
        entity_slots = allocation.slots[rows, 0]
        identifiers = allocation.entity_ids[rows, 0]
        cards = safe[rows]
        self.active[rows, slots] = True
        self.area_id[rows, slots] = identifiers
        self.card_id[rows, slots] = cards
        self.player_id[rows, slots] = player_ids[rows].to(torch.int8)
        self.x_units[rows, slots] = target_x_units[rows].to(torch.int32)
        self.y_units[rows, slots] = target_y_units[rows].to(torch.int32)
        self.age_ms[rows, slots] = 0
        self.next_damage_ms[rows, slots] = self.catalog.initial_damage_ms[cards]
        self.damage_ticks_applied[rows, slots] = 0
        self.next_effect_ms[rows, slots] = self.catalog.effect_interval_ms[cards]
        self.freeze_applied[rows, slots] = False
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
        runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.AREA,
            valid=allocation.valid,
            source_id=0,
            target_id=allocation.entity_ids,
            x_units=target_x_units[:, None],
            y_units=target_y_units[:, None],
            payload=safe[:, None],
        )
        return supported

    # The delayed pending-spell owner can use the same callable shape as the
    # projectile bridge while routing by catalog support.
    materialize_spell_actions_ = materialize_due_spell_actions_

    def _target_mask(
        self,
        runtime: TensorBattleRuntime,
        cards: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        owned_area = (
            runtime.battle.entity_id[:, :, None] == self.area_id[:, None, :]
        ) & self.active[:, None, :]
        identity = (
            (~runtime.entity_pool.active)
            | owned_area.any(dim=2)
            | (self.targets.entity_id == runtime.battle.entity_id)
        )
        identity_supported = identity.all(dim=1)
        x = runtime.battle.entity_x_units.to(torch.int64)[:, None, :]
        y = runtime.battle.entity_y_units.to(torch.int64)[:, None, :]
        center_x = self.x_units.to(torch.int64)[:, :, None]
        center_y = self.y_units.to(torch.int64)[:, :, None]
        radius = self.catalog.radius_units[cards].to(torch.int64)[:, :, None]
        object_radius = self.targets.collision_radius_units.to(torch.int64)[:, None, :]
        dx = x - center_x
        dy = y - center_y
        circular = dx.square() + dy.square() < (radius + object_radius).square()
        closest_x = torch.minimum(
            x + object_radius, torch.maximum(x - object_radius, center_x)
        )
        closest_y = torch.minimum(
            y + object_radius, torch.maximum(y - object_radius, center_y)
        )
        square = (closest_x - center_x).square() + (
            closest_y - center_y
        ).square() < radius.square()
        overlap = torch.where(self.targets.building[:, None, :], square, circular)
        player = runtime.battle.entity_player.to(torch.int64)[:, None, :]
        eligible = (
            self.active[:, :, None]
            & runtime.entity_pool.active[:, None, :]
            & runtime.battle.entity_active[:, None, :]
            & (player != self.player_id.to(torch.int64)[:, :, None])
            & (runtime.battle.entity_kind[:, None, :] != 2)
            & (runtime.battle.entity_kind[:, None, :] != 3)
            & overlap
        )
        air = self.targets.airborne[:, None, :]
        eligible &= torch.where(
            air,
            self.catalog.hits_air[cards][:, :, None],
            self.catalog.hits_ground[cards][:, :, None],
        )
        eligible &= identity_supported[:, None, None]
        carrier_overlap = (
            runtime.entity_pool.active[:, None, :]
            & self.targets.freeze_carrier[:, None, :]
            & (player != self.player_id.to(torch.int64)[:, :, None])
            & overlap
        )
        return eligible, identity_supported, carrier_overlap

    def step_status_(self, runtime: TensorBattleRuntime) -> ContinuousAreaStepResult:
        """Advance target-local periodic buffs before their source areas."""

        working = runtime.clone()
        schedule = working.status.tick(working.battle.dt)
        damage = (
            schedule.damage * schedule.hit_counts.to(torch.float64) * schedule.valid
        ).sum(dim=2)
        selected = (
            working.entity_pool.active & working.battle.entity_active & (damage > 0)
        )
        additions = selected.sum(dim=1, dtype=torch.int64) + (
            selected & (damage >= working.battle.entity_hp)
        ).sum(dim=1, dtype=torch.int64)
        supported = runtime.supported & (
            working.events.count.to(torch.int64) + additions <= working.events.capacity
        )
        selected &= supported[:, None]
        died = selected & (damage >= working.battle.entity_hp)
        working.battle.entity_hp_integer_kind &= ~selected
        working.battle.entity_hp.copy_(
            torch.where(
                selected,
                (working.battle.entity_hp - damage).clamp_min(0.0),
                working.battle.entity_hp,
            )
        )
        working.battle.entity_active &= ~died
        working.phases.death_pending |= died
        _append_damage_events(working, selected, damage, died)
        _copy_runtime_rows(runtime, working, supported)
        return ContinuousAreaStepResult(
            committed=supported,
            damage=torch.where(supported[:, None], damage, 0.0),
            died=died & supported[:, None],
            expired=torch.zeros_like(self.active),
        )

    def step_(self, runtime: TensorBattleRuntime) -> ContinuousAreaStepResult:
        """Advance every retained area as one transactional tensor worklist."""

        working = runtime.clone()
        owner = self.clone()
        cards = owner.card_id.clamp(0, owner.catalog.size - 1)
        selected = owner.active & runtime.supported[:, None]
        delta_ms = working.battle.tick_milliseconds.to(torch.int64)[:, None]
        age_before = owner.age_ms.to(torch.int64)
        age_after = age_before + delta_ms
        duration = owner.catalog.duration_ms[cards].to(torch.int64)
        deadline = torch.minimum(age_after, duration)
        maximum = owner.catalog.max_damage_ticks[cards].to(torch.int64)
        remaining_ticks = (
            maximum - owner.damage_ticks_applied.to(torch.int64)
        ).clamp_min(0)
        interval = owner.catalog.damage_interval_ms[cards].to(torch.int64)
        next_damage = owner.next_damage_ms.to(torch.int64)
        damage_due = selected & (remaining_ticks > 0) & (next_damage <= deadline)
        crossed = torch.where(
            damage_due,
            torch.where(
                interval > 0,
                torch.div(
                    (deadline - next_damage).clamp_min(0),
                    interval.clamp_min(1),
                    rounding_mode="floor",
                )
                + 1,
                torch.ones_like(interval),
            ),
            torch.zeros_like(interval),
        )
        hit_count = torch.minimum(crossed, remaining_ticks)
        targets, identity_supported, freeze_carrier = owner._target_mask(working, cards)
        supported = runtime.supported & identity_supported
        supported &= ~(
            freeze_carrier & owner.catalog.freeze_snapshot[cards][:, :, None]
        ).any(dim=(1, 2))
        card_index = cards[:, :, None, None].expand(
            self.batch_size, self.capacity, runtime.max_entities, 1
        )
        damage_receivable = torch.gather(
            owner.targets.damage_receivable[:, None, :, :].expand(
                self.batch_size, self.capacity, runtime.max_entities, -1
            ),
            3,
            card_index,
        )[:, :, :, 0]
        effect_receivable = torch.gather(
            owner.targets.effect_receivable[:, None, :, :].expand(
                self.batch_size, self.capacity, runtime.max_entities, -1
            ),
            3,
            card_index,
        )[:, :, :, 0]
        direct_targets = targets & damage_receivable & (hit_count[:, :, None] > 0)
        amount = owner.catalog.damage[cards][:, :, None] * hit_count[:, :, None]
        crown = (
            torch.where(
                owner.catalog.crown_damage_valid[cards],
                owner.catalog.crown_damage[cards],
                torch.ceil(
                    owner.catalog.damage[cards] * owner.catalog.crown_multiplier[cards]
                ),
            )[:, :, None]
            * hit_count[:, :, None]
        )
        building = (
            torch.where(
                owner.catalog.building_damage_valid[cards],
                owner.catalog.building_damage[cards],
                torch.ceil(
                    owner.catalog.damage[cards]
                    * owner.catalog.building_multiplier[cards]
                ),
            )[:, :, None]
            * hit_count[:, :, None]
        )
        actual = torch.where(owner.targets.crown[:, None, :], crown, amount)
        actual = torch.where(
            owner.targets.building[:, None, :] & ~owner.targets.crown[:, None, :],
            building,
            actual,
        )
        damage = torch.where(direct_targets, actual, 0.0).sum(dim=1)
        target_damage = damage > 0
        died = (
            target_damage
            & working.battle.entity_active
            & (damage >= working.battle.entity_hp)
        )
        # Death payloads and crown-win propagation belong to the terminal
        # pipeline. Keep this owner atomic until that integration is composed.
        supported &= ~died.any(dim=1)
        expired = selected & (age_after >= duration)
        additions = (
            target_damage.sum(dim=1, dtype=torch.int64)
            + died.sum(dim=1, dtype=torch.int64)
            + 2 * expired.sum(dim=1, dtype=torch.int64)
        )
        supported &= (
            working.events.count.to(torch.int64) + additions <= working.events.capacity
        )
        target_damage &= supported[:, None]
        died &= supported[:, None]
        working.battle.entity_hp_integer_kind &= ~target_damage
        working.battle.entity_hp.copy_(
            torch.where(
                target_damage,
                (working.battle.entity_hp - damage).clamp_min(0.0),
                working.battle.entity_hp,
            )
        )
        working.battle.entity_active &= ~died
        working.phases.death_pending |= died
        _append_damage_events(working, target_damage, damage, died)

        freeze_area = (
            selected
            & owner.catalog.freeze_snapshot[cards]
            & ~owner.freeze_applied
            & supported[:, None]
        )
        freeze_targets = targets & effect_receivable & freeze_area[:, :, None]
        freeze_targets &= working.battle.entity_active[:, None, :]
        freeze_matches = (
            working.status.slow_active
            & (working.status.slow_movement == 0.0)
            & (working.status.slow_attack == 0.0)
            & (working.status.slow_spawn == 0.0)
        ).any(dim=2)
        freeze_capacity = freeze_matches | (~working.status.slow_active).any(dim=2)
        supported &= ~(freeze_targets & ~freeze_capacity[:, None, :]).any(dim=(1, 2))
        freeze_targets &= supported[:, None, None]
        expiry = working.battle.time[:, None, None] + (
            owner.catalog.duration_ms[cards].to(torch.float64)[:, :, None] / 1_000
        )
        maximum_expiry = torch.where(freeze_targets, expiry, 0.0).amax(dim=1)
        working.status.apply_freeze_until(
            maximum_expiry,
            working.battle.time[:, None],
            mask=maximum_expiry > working.battle.time[:, None],
        )

        effect_due = (
            selected
            & ~owner.catalog.freeze_snapshot[cards]
            & (owner.next_effect_ms.to(torch.int64) <= deadline)
            & (owner.next_effect_ms.to(torch.int64) < duration)
            & supported[:, None]
        )
        for area_slot in range(self.capacity):
            area_cards = cards[:, area_slot]
            area_targets = (
                targets[:, area_slot]
                & effect_receivable[:, area_slot]
                & working.battle.entity_active
                & effect_due[:, area_slot, None]
            )
            local = owner.catalog.target_local_damage[area_cards]
            periodic_targets = (
                area_targets & local[:, None] & damage_receivable[:, area_slot]
            )
            source = owner.area_id[:, area_slot, None].expand_as(periodic_targets)
            source_kind = area_cards[:, None].expand_as(periodic_targets)
            periodic_matches = (
                working.status.periodic_active
                & (working.status.periodic_source_id == source[:, :, None])
            ).any(dim=2)
            periodic_capacity = periodic_matches | (
                ~working.status.periodic_active
            ).any(dim=2)
            supported &= ~(periodic_targets & ~periodic_capacity).any(dim=1)
            periodic_targets &= supported[:, None]
            periodic_damage = torch.where(
                owner.targets.crown,
                owner.catalog.crown_damage[area_cards][:, None],
                torch.where(
                    owner.targets.building,
                    owner.catalog.building_damage[area_cards][:, None],
                    owner.catalog.damage[area_cards][:, None],
                ),
            )
            duration_seconds = (
                owner.catalog.periodic_duration_ms[area_cards][:, None].to(
                    torch.float64
                )
                / 1_000
            )
            interval_seconds = (
                owner.catalog.damage_interval_ms[area_cards][:, None].to(torch.float64)
                / 1_000
            )
            hidden = owner.catalog.affects_hidden[area_cards][:, None]
            controlled = owner.catalog.periodic_controlled_by_parent[area_cards]
            working.status.apply_periodic_damage(
                source_id=source,
                source_kind=source_kind,
                duration=duration_seconds,
                hit_interval=interval_seconds,
                damage=periodic_damage,
                affects_hidden=hidden,
                mask=periodic_targets & ~controlled[:, None],
            )
            working.status.apply_periodic_damage(
                source_id=source,
                source_kind=source_kind,
                duration=duration_seconds,
                hit_interval=interval_seconds,
                damage=periodic_damage,
                hard_duration=(
                    duration[:, area_slot, None]
                    - owner.next_effect_ms[:, area_slot, None]
                )
                .clamp_min(0)
                .to(torch.float64)
                / 1_000,
                affects_hidden=hidden,
                mask=periodic_targets & controlled[:, None],
            )
            slow_targets = area_targets & (
                owner.catalog.movement_multiplier[area_cards][:, None] < 1.0
            )
            movement = owner.catalog.movement_multiplier[area_cards][:, None]
            attack = owner.catalog.attack_multiplier[area_cards][:, None]
            spawn = owner.catalog.spawn_multiplier[area_cards][:, None]
            slow_matches = (
                working.status.slow_active
                & (working.status.slow_movement == movement[:, :, None])
                & (working.status.slow_attack == attack[:, :, None])
                & (working.status.slow_spawn == spawn[:, :, None])
            ).any(dim=2)
            slow_capacity = slow_matches | (~working.status.slow_active).any(dim=2)
            supported &= ~(slow_targets & ~slow_capacity).any(dim=1)
            slow_targets &= supported[:, None]
            refresh = owner.catalog.slow_refresh_ms[area_cards].to(torch.int64)
            remaining = (
                duration[:, area_slot]
                - owner.next_effect_ms[:, area_slot].to(torch.int64)
            ).clamp_min(0)
            refresh = torch.where(
                owner.catalog.cap_slow_to_area[area_cards],
                torch.minimum(refresh, remaining),
                refresh,
            )
            working.status.apply_slow(
                refresh[:, None].to(torch.float64) / 1_000,
                movement,
                attack_speed_multiplier=attack,
                spawn_speed_multiplier=spawn,
                mask=slow_targets,
            )

        owner.age_ms.copy_(
            torch.where(
                selected & supported[:, None],
                age_after,
                owner.age_ms.to(torch.int64),
            ).to(torch.int32)
        )
        owner.damage_ticks_applied.copy_(
            torch.where(
                selected & supported[:, None],
                owner.damage_ticks_applied.to(torch.int64) + hit_count,
                owner.damage_ticks_applied.to(torch.int64),
            ).to(torch.int16)
        )
        owner.next_damage_ms.copy_(
            torch.where(
                selected & supported[:, None] & (hit_count > 0),
                torch.where(
                    interval > 0,
                    next_damage + hit_count * interval,
                    duration + 1,
                ),
                next_damage,
            ).to(torch.int32)
        )
        owner.next_effect_ms.copy_(
            torch.where(
                effect_due,
                owner.next_effect_ms.to(torch.int64)
                + owner.catalog.effect_interval_ms[cards].to(torch.int64),
                owner.next_effect_ms.to(torch.int64),
            ).to(torch.int32)
        )
        owner.freeze_applied |= freeze_area

        expired &= supported[:, None]
        area_slots = working.entity_pool.slots_for_ids(owner.area_id)
        valid_expired = expired & (area_slots >= 0)
        rows, lanes = torch.where(valid_expired)
        physical = area_slots[rows, lanes]
        expired_ids = owner.area_id.clone()
        working.battle.entity_active[rows, physical] = False
        death_valid = torch.stack((valid_expired, valid_expired), dim=2).flatten(1)
        death_ids = torch.stack((expired_ids, expired_ids), dim=2).flatten(1)
        working.events.append(
            phase=TickPhase.COMBAT,
            opcode=torch.stack(
                (
                    torch.full_like(expired_ids, RuntimeEventOpcode.DAMAGE),
                    torch.full_like(expired_ids, RuntimeEventOpcode.DEATH),
                ),
                dim=2,
            ).flatten(1),
            valid=death_valid,
            target_id=death_ids,
            amount=torch.stack(
                (
                    torch.ones_like(expired_ids, dtype=torch.float64),
                    torch.zeros_like(expired_ids, dtype=torch.float64),
                ),
                dim=2,
            ).flatten(1),
        )
        dead = torch.zeros_like(working.entity_pool.active)
        dead[rows, physical] = True
        working.entity_pool.cleanup(dead)
        _clear_entity_mask(working, dead)
        owner.active &= ~expired
        for name in (
            "area_id",
            "card_id",
            "player_id",
            "x_units",
            "y_units",
            "age_ms",
            "next_damage_ms",
            "damage_ticks_applied",
            "next_effect_ms",
            "freeze_applied",
        ):
            getattr(owner, name).masked_fill_(expired, 0)

        _copy_runtime_rows(runtime, working, supported)
        self.reset_rows_(torch.where(supported)[0], owner, torch.where(supported)[0])
        return ContinuousAreaStepResult(
            supported,
            torch.where(supported[:, None], damage, 0.0),
            died & supported[:, None],
            expired & supported[:, None],
        )


def _append_damage_events(
    runtime: TensorBattleRuntime,
    valid: torch.Tensor,
    damage: torch.Tensor,
    died: torch.Tensor,
) -> None:
    order = runtime.entity_pool.id_order(valid)
    slots = order.slots.clamp_min(0)
    amount = torch.gather(damage, 1, slots)
    ordered_died = torch.gather(died, 1, slots) & order.valid
    pair_valid = torch.stack((order.valid, ordered_died), dim=2).flatten(1)
    ids = torch.stack((order.entity_ids, order.entity_ids), dim=2).flatten(1)
    runtime.events.append(
        phase=TickPhase.COMBAT,
        opcode=torch.stack(
            (
                torch.full_like(order.entity_ids, RuntimeEventOpcode.DAMAGE),
                torch.full_like(order.entity_ids, RuntimeEventOpcode.DEATH),
            ),
            dim=2,
        ).flatten(1),
        valid=pair_valid,
        target_id=ids,
        amount=torch.stack((amount, torch.zeros_like(amount)), dim=2).flatten(1),
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
    "ContinuousAreaStepResult",
    "TensorContinuousAreaCatalog",
    "TensorContinuousAreaTargets",
    "TensorResidentContinuousAreas",
]
