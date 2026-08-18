"""Retained serialized Tornado area, attraction, and periodic-damage runtime."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.entities import AreaEffect, Building
from clasher.kinematics import tiles_to_logic_units
from clasher.spells import SPELL_REGISTRY, TornadoSpell
from clasher.unit_traits import is_airborne_target, is_in_transit

from .entity_pool import INVALID_SLOT
from .objects import _integer_sqrt, _trunc_div
from .resident_spell_ingress import _copy_runtime_rows
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorTornadoCatalog:
    supported: torch.Tensor
    reason: tuple[str, ...]
    duration_ms: torch.Tensor
    radius_units: torch.Tensor
    attract_percentage: torch.Tensor
    push_speed_factor: torch.Tensor
    damage: torch.Tensor
    damage_interval_ms: torch.Tensor
    effect_interval_ms: torch.Tensor
    buff_duration_ms: torch.Tensor
    controlled_by_parent: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    affects_hidden: torch.Tensor
    crown_damage: torch.Tensor
    crown_damage_valid: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.supported.numel())

    @classmethod
    def compile(cls, runtime: TensorBattleRuntime) -> TensorTornadoCatalog:
        size = len(runtime.battle.card_names)
        device = runtime.device

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = zeros(torch.bool)
        duration = zeros(torch.int32)
        radius = zeros(torch.int32)
        attract = zeros(torch.float64)
        push = zeros(torch.float64)
        damage = zeros(torch.float64)
        damage_interval = zeros(torch.int32)
        effect_interval = zeros(torch.int32)
        buff_duration = zeros(torch.int32)
        controlled = zeros(torch.bool)
        hits_air = zeros(torch.bool)
        hits_ground = zeros(torch.bool)
        hidden = zeros(torch.bool)
        crown_damage = zeros(torch.float64)
        crown_valid = zeros(torch.bool)
        reasons = ["not a retained serialized attraction area"] * size

        for card_id, name in enumerate(runtime.battle.card_names):
            spell = SPELL_REGISTRY.get(name)
            if not isinstance(spell, TornadoSpell):
                continue
            timing = (
                spell.duration,
                spell.damage_tick_interval,
                spell.effect_tick_interval,
                spell.buff_duration,
            )
            if any(
                abs(value * 1_000 - round(value * 1_000)) > 1e-9 for value in timing
            ):
                reasons[card_id] = "attraction-area timing is off integral milliseconds"
                continue
            if (
                spell.duration <= 0
                or spell.radius < 0
                or spell.effect_tick_interval <= 0
                or spell.damage_tick_interval <= 0
                or spell.buff_duration <= 0
                or spell.attract_percentage < 0
                or spell.push_speed_factor < 0
                or round(spell.effect_tick_interval * 1_000) % 50 != 0
            ):
                reasons[card_id] = "attraction-area serialized payload is incomplete"
                continue
            supported[card_id] = True
            reasons[card_id] = ""
            duration[card_id] = round(spell.duration * 1_000)
            radius[card_id] = tiles_to_logic_units(spell.radius)
            attract[card_id] = spell.attract_percentage
            push[card_id] = spell.push_speed_factor
            damage[card_id] = spell.damage_per_hit
            damage_interval[card_id] = round(spell.damage_tick_interval * 1_000)
            effect_interval[card_id] = round(spell.effect_tick_interval * 1_000)
            buff_duration[card_id] = round(spell.buff_duration * 1_000)
            controlled[card_id] = spell.controlled_by_parent
            hits_air[card_id] = spell.hits_air
            hits_ground[card_id] = spell.hits_ground
            hidden[card_id] = spell.affects_hidden
            if spell.crown_tower_damage is not None:
                crown_damage[card_id] = spell.crown_tower_damage
                crown_valid[card_id] = True

        return cls(
            supported,
            tuple(reasons),
            duration,
            radius,
            attract,
            push,
            damage,
            damage_interval,
            effect_interval,
            buff_duration,
            controlled,
            hits_air,
            hits_ground,
            hidden,
            crown_damage,
            crown_valid,
        )


@dataclass
class TensorTornadoTargets:
    entity_id: torch.Tensor
    collision_radius_units: torch.Tensor
    airborne: torch.Tensor
    building: torch.Tensor
    crown: torch.Tensor
    base_speed: torch.Tensor
    area_displaceable: torch.Tensor
    transit_supported: torch.Tensor
    effect_receivable: torch.Tensor
    damage_receivable: torch.Tensor

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        catalog: TensorTornadoCatalog,
    ) -> TensorTornadoTargets:
        shape = (runtime.batch_size, runtime.max_entities)
        device = runtime.device
        entity_id = runtime.battle.entity_id.clone()
        radius = torch.zeros(shape, dtype=torch.int32, device=device)
        airborne = torch.zeros(shape, dtype=torch.bool, device=device)
        building = torch.zeros(shape, dtype=torch.bool, device=device)
        crown = torch.zeros(shape, dtype=torch.bool, device=device)
        speed = torch.zeros(shape, dtype=torch.int64, device=device)
        displaceable = torch.zeros(shape, dtype=torch.bool, device=device)
        transit = torch.ones(shape, dtype=torch.bool, device=device)
        effect = torch.zeros((*shape, catalog.size), dtype=torch.bool, device=device)
        damage = torch.zeros_like(effect)
        for row, battle in enumerate(battles):
            slots = {
                int(value): slot
                for slot, value in enumerate(runtime.battle.entity_id[row].tolist())
                if int(value) > 0
            }
            for entity_id_value, entity in battle.entities.items():
                slot = slots[entity_id_value]
                radius[row, slot] = tiles_to_logic_units(entity.get_collision_radius())
                airborne[row, slot] = is_airborne_target(entity)
                building[row, slot] = isinstance(entity, Building)
                crown[row, slot] = isinstance(entity, Building) and getattr(
                    entity.card_stats, "name", ""
                ) in {"Tower", "KingTower"}
                speed[row, slot] = round(
                    float(getattr(entity.card_stats, "speed", 0) or 0)
                )
                displaceable[row, slot] = bool(
                    getattr(entity, "area_displaceable", False)
                )
                transit[row, slot] = not is_in_transit(entity) or bool(
                    getattr(entity, "_river_jump_active", False)
                )
                for card_id, name in enumerate(runtime.battle.card_names):
                    if not bool(catalog.supported[card_id].item()):
                        continue
                    hidden = bool(catalog.affects_hidden[card_id].item())
                    effect[row, slot, card_id] = entity.can_receive_effect(
                        name, affects_hidden=hidden
                    )
                    damage[row, slot, card_id] = entity.can_receive_area_damage(
                        name, affects_hidden=hidden
                    )
        return cls(
            entity_id,
            radius,
            airborne,
            building,
            crown,
            speed,
            displaceable,
            transit,
            effect,
            damage,
        )

    def fork(self, rows: torch.Tensor) -> TensorTornadoTargets:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name)[rows].clone()
                for descriptor in fields(self)
            }
        )


@dataclass(frozen=True)
class TornadoStepResult:
    committed: torch.Tensor
    attraction_vector_units: torch.Tensor
    attraction_count: torch.Tensor
    periodic_installed: torch.Tensor
    damage: torch.Tensor
    expired: torch.Tensor


@dataclass
class TensorResidentTornadoes:
    catalog: TensorTornadoCatalog
    targets: TensorTornadoTargets
    active: torch.Tensor
    tornado_id: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    age_ms: torch.Tensor
    next_effect_ms: torch.Tensor

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
    ) -> TensorResidentTornadoes:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match Tornado runtime")
        if capacity < 1:
            raise ValueError("Tornado capacity must be positive")
        catalog = TensorTornadoCatalog.compile(runtime)
        targets = TensorTornadoTargets.from_battles(runtime, battles, catalog)
        shape = (runtime.batch_size, capacity)
        owner = cls(
            catalog,
            targets,
            torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            torch.zeros(shape, dtype=torch.int64, device=runtime.device),
            torch.zeros(shape, dtype=torch.int64, device=runtime.device),
            torch.zeros(shape, dtype=torch.int8, device=runtime.device),
            torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            torch.zeros(shape, dtype=torch.int32, device=runtime.device),
            torch.zeros(shape, dtype=torch.int32, device=runtime.device),
        )
        for row, battle in enumerate(battles):
            live = [
                entity
                for entity in battle.entities.values()
                if type(entity) is AreaEffect and entity.is_tornado
            ]
            if len(live) > capacity:
                raise ValueError("live Tornadoes exceed retained capacity")
            for lane, tornado in enumerate(live):
                card = runtime.battle.card_to_id.get(
                    str(getattr(tornado, "spell_name", "")), -1
                )
                if card < 0 or not bool(catalog.supported[card].item()):
                    raise ValueError("live Tornado is outside retained coverage")
                owner.active[row, lane] = True
                owner.tornado_id[row, lane] = tornado.id
                owner.card_id[row, lane] = card
                owner.player_id[row, lane] = tornado.player_id
                owner.x_units[row, lane] = tiles_to_logic_units(tornado.position.x)
                owner.y_units[row, lane] = tiles_to_logic_units(tornado.position.y)
                owner.age_ms[row, lane] = round(tornado.time_alive * 1_000)
                owner.next_effect_ms[row, lane] = round(
                    (tornado.next_effect_time or tornado.effect_tick_interval) * 1_000
                )
        return owner

    def clone(self) -> TensorResidentTornadoes:
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

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentTornadoes:
        index = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        return type(self)(
            catalog=self.catalog,
            targets=self.targets.fork(index),
            **{
                descriptor.name: getattr(self, descriptor.name)[index].clone()
                for descriptor in fields(self)
                if descriptor.name not in {"catalog", "targets"}
            },
        )

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentTornadoes,
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
            raise ValueError("Tornado reset rows have unequal shapes")
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
        planes = (card_ids, player_ids, target_x_units, target_y_units, valid)
        if any(value.shape != (self.batch_size,) for value in planes):
            raise ValueError("Tornado due command planes must have shape [batch]")
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
        self.tornado_id[rows, lanes] = identifiers
        self.card_id[rows, lanes] = cards
        self.player_id[rows, lanes] = player_ids[rows].to(torch.int8)
        self.x_units[rows, lanes] = target_x_units[rows].to(torch.int32)
        self.y_units[rows, lanes] = target_y_units[rows].to(torch.int32)
        self.age_ms[rows, lanes] = 0
        self.next_effect_ms[rows, lanes] = self.catalog.effect_interval_ms[cards]
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

    materialize_spell_actions_ = materialize_due_spell_actions_

    def _target_planes(
        self,
        runtime: TensorBattleRuntime,
        cards: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        owned = (
            runtime.battle.entity_id[:, :, None] == self.tornado_id[:, None, :]
        ) & self.active[:, None, :]
        identity = (
            (~runtime.entity_pool.active)
            | owned.any(dim=2)
            | (runtime.battle.entity_id == self.targets.entity_id)
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
        opponent = (
            runtime.battle.entity_player.to(torch.int64)[:, None, :]
            != (self.player_id.to(torch.int64)[:, :, None])
        )
        air = self.targets.airborne[:, None, :]
        hit_plane = torch.where(
            air,
            self.catalog.hits_air[cards][:, :, None],
            self.catalog.hits_ground[cards][:, :, None],
        )
        base = (
            self.active[:, :, None]
            & runtime.entity_pool.active[:, None, :]
            & runtime.battle.entity_active[:, None, :]
            & opponent
            & overlap
            & hit_plane
            & self.targets.transit_supported[:, None, :]
            & identity_supported[:, None, None]
        )
        effect_container = (runtime.battle.entity_kind == 2) | (
            runtime.battle.entity_kind == 3
        )
        pull = base & (
            ~effect_container[:, None, :] | self.targets.area_displaceable[:, None, :]
        )
        periodic = base & ~effect_container[:, None, :]
        card_index = cards[:, :, None, None].expand(
            self.batch_size, self.capacity, runtime.max_entities, 1
        )
        effect = torch.gather(
            self.targets.effect_receivable[:, None, :, :].expand(
                self.batch_size, self.capacity, runtime.max_entities, -1
            ),
            3,
            card_index,
        )[:, :, :, 0]
        damage = torch.gather(
            self.targets.damage_receivable[:, None, :, :].expand(
                self.batch_size, self.capacity, runtime.max_entities, -1
            ),
            3,
            card_index,
        )[:, :, :, 0]
        return pull & effect, periodic & effect & damage, identity_supported, overlap

    def step_status_(self, runtime: TensorBattleRuntime) -> TornadoStepResult:
        working = runtime.clone()
        schedule = working.status.tick(working.battle.dt)
        damage = (
            schedule.damage * schedule.hit_counts.to(torch.float64) * schedule.valid
        ).sum(dim=2)
        selected = (
            working.entity_pool.active & working.battle.entity_active & (damage > 0)
        )
        died = selected & (damage >= working.battle.entity_hp)
        additions = selected.sum(dim=1, dtype=torch.int64) + died.sum(
            dim=1, dtype=torch.int64
        )
        supported = (
            runtime.supported
            & ~died.any(dim=1)
            & (
                working.events.count.to(torch.int64) + additions
                <= working.events.capacity
            )
        )
        selected &= supported[:, None]
        working.battle.entity_hp_integer_kind &= ~selected
        working.battle.entity_hp.copy_(
            torch.where(
                selected,
                (working.battle.entity_hp - damage).clamp_min(0.0),
                working.battle.entity_hp,
            )
        )
        _append_damage_events(working, selected, damage)
        _copy_runtime_rows(runtime, working, supported)
        zeros = torch.zeros(
            (self.batch_size, runtime.max_entities),
            dtype=torch.int64,
            device=self.device,
        )
        return TornadoStepResult(
            supported,
            torch.zeros(
                (self.batch_size, runtime.max_entities, 2),
                dtype=torch.int64,
                device=self.device,
            ),
            zeros,
            torch.zeros_like(zeros, dtype=torch.bool),
            torch.where(supported[:, None], damage, 0.0),
            torch.zeros_like(self.active),
        )

    def step_(self, runtime: TensorBattleRuntime) -> TornadoStepResult:
        working = runtime.clone()
        owner = self.clone()
        cards = owner.card_id.clamp(0, owner.catalog.size - 1)
        selected = owner.active & runtime.supported[:, None]
        age_after = owner.age_ms.to(torch.int64) + working.battle.tick_milliseconds[
            :, None
        ].to(torch.int64)
        duration = owner.catalog.duration_ms[cards].to(torch.int64)
        deadline = torch.minimum(age_after, duration)
        next_effect = owner.next_effect_ms.to(torch.int64)
        interval = owner.catalog.effect_interval_ms[cards].to(torch.int64)
        due = selected & (next_effect <= deadline) & (next_effect < duration)
        scan_count = torch.where(
            due,
            torch.div(
                (deadline - next_effect).clamp_min(0),
                interval.clamp_min(1),
                rounding_mode="floor",
            )
            + 1,
            torch.zeros_like(interval),
        )
        pull_targets, periodic_targets, identity_supported, _ = owner._target_planes(
            working, cards
        )
        pull_targets &= scan_count[:, :, None] > 0
        periodic_targets &= scan_count[:, :, None] > 0
        supported = runtime.supported & identity_supported
        expired = selected & (age_after >= duration)

        total_vector = torch.zeros(
            (self.batch_size, runtime.max_entities, 2),
            dtype=torch.int64,
            device=self.device,
        )
        total_count = torch.zeros(
            (self.batch_size, runtime.max_entities),
            dtype=torch.int64,
            device=self.device,
        )
        periodic_installed = torch.zeros_like(total_count, dtype=torch.bool)
        for lane in range(self.capacity):
            lane_cards = cards[:, lane]
            lane_pull = pull_targets[:, lane] & supported[:, None]
            dx = owner.x_units[:, lane, None].to(
                torch.int64
            ) - working.battle.entity_x_units.to(torch.int64)
            dy = owner.y_units[:, lane, None].to(
                torch.int64
            ) - working.battle.entity_y_units.to(torch.int64)
            distance = _integer_sqrt(dx.square() + dy.square()).clamp_min(1)
            per_tick = torch.trunc(
                torch.trunc(
                    self.targets.base_speed.to(torch.float64)
                    * owner.catalog.push_speed_factor[lane_cards][:, None]
                    / 100.0
                )
                * owner.catalog.attract_percentage[lane_cards][:, None]
                / 100.0
            ).to(torch.int64)
            work_per_scan = (
                per_tick * owner.catalog.effect_interval_ms[lane_cards][:, None] // 50
            )
            nonzero = lane_pull & ((dx != 0) | (dy != 0)) & (work_per_scan > 0)
            move_x = torch.where(
                nonzero,
                _trunc_div(dx * work_per_scan, distance) * scan_count[:, lane, None],
                0,
            )
            move_y = torch.where(
                nonzero,
                _trunc_div(dy * work_per_scan, distance) * scan_count[:, lane, None],
                0,
            )
            total_vector[:, :, 0] += move_x
            total_vector[:, :, 1] += move_y
            total_count += nonzero.to(torch.int64) * scan_count[:, lane, None]

            lane_periodic = periodic_targets[:, lane] & supported[:, None]
            source = owner.tornado_id[:, lane, None].expand_as(lane_periodic)
            source_kind = lane_cards[:, None].expand_as(lane_periodic)
            matches = (
                working.status.periodic_active
                & (working.status.periodic_source_id == source[:, :, None])
            ).any(dim=2)
            capacity = matches | (~working.status.periodic_active).any(dim=2)
            supported &= ~(lane_periodic & ~capacity).any(dim=1)
            lane_periodic &= supported[:, None]
            latest_scan = (
                next_effect[:, lane]
                + (scan_count[:, lane] - 1).clamp_min(0) * interval[:, lane]
            )
            hard = (duration[:, lane] - latest_scan).clamp_min(0).to(
                torch.float64
            ) / 1_000
            damage = torch.where(
                owner.targets.crown,
                owner.catalog.crown_damage[lane_cards][:, None],
                owner.catalog.damage[lane_cards][:, None],
            )
            controlled = owner.catalog.controlled_by_parent[lane_cards]
            common = {
                "source_id": source,
                "source_kind": source_kind,
                "duration": owner.catalog.buff_duration_ms[lane_cards][:, None].to(
                    torch.float64
                )
                / 1_000,
                "hit_interval": owner.catalog.damage_interval_ms[lane_cards][
                    :, None
                ].to(torch.float64)
                / 1_000,
                "damage": damage,
                "affects_hidden": owner.catalog.affects_hidden[lane_cards][:, None],
            }
            working.status.apply_periodic_damage(
                **common,
                mask=lane_periodic & ~controlled[:, None],
            )
            working.status.apply_periodic_damage(
                **common,
                hard_duration=hard[:, None],
                mask=lane_periodic & controlled[:, None],
            )
            periodic_installed |= lane_periodic

        total_vector = torch.where(supported[:, None, None], total_vector, 0)
        total_count = torch.where(supported[:, None], total_count, 0)
        working.phases.movement_vector_units.add_(total_vector)
        working.phases.movement_vector_count.add_(total_count.to(torch.int32))
        working.phases.movement_vector_bypasses_cap |= total_count > 0
        owner.age_ms.copy_(
            torch.where(
                selected & supported[:, None],
                age_after,
                owner.age_ms.to(torch.int64),
            ).to(torch.int32)
        )
        owner.next_effect_ms.copy_(
            torch.where(
                selected & supported[:, None] & (scan_count > 0),
                next_effect + scan_count * interval,
                next_effect,
            ).to(torch.int32)
        )

        expired &= supported[:, None]
        area_slots = working.entity_pool.slots_for_ids(owner.tornado_id)
        valid_expired = expired & (area_slots >= 0)
        rows, lanes = torch.where(valid_expired)
        physical = area_slots[rows, lanes]
        working.battle.entity_active[rows, physical] = False
        dead = torch.zeros_like(working.entity_pool.active)
        dead[rows, physical] = True
        working.entity_pool.cleanup(dead)
        _clear_entity_mask(working, dead)
        owner.active &= ~expired
        for name in (
            "tornado_id",
            "card_id",
            "player_id",
            "x_units",
            "y_units",
            "age_ms",
            "next_effect_ms",
        ):
            getattr(owner, name).masked_fill_(expired, 0)

        _copy_runtime_rows(runtime, working, supported)
        rows = torch.where(supported)[0]
        self.reset_rows_(rows, owner, rows)
        return TornadoStepResult(
            supported,
            total_vector,
            total_count,
            periodic_installed & supported[:, None],
            torch.zeros_like(total_count, dtype=torch.float64),
            expired,
        )


def _append_damage_events(
    runtime: TensorBattleRuntime,
    valid: torch.Tensor,
    damage: torch.Tensor,
) -> None:
    order = runtime.entity_pool.id_order(valid)
    slots = order.slots.clamp_min(0)
    runtime.events.append(
        phase=TickPhase.STATUS,
        opcode=RuntimeEventOpcode.DAMAGE,
        valid=order.valid,
        source_id=order.entity_ids,
        target_id=order.entity_ids,
        x_units=torch.gather(runtime.battle.entity_x_units, 1, slots),
        y_units=torch.gather(runtime.battle.entity_y_units, 1, slots),
        amount=torch.gather(damage, 1, slots),
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
    "TensorResidentTornadoes",
    "TensorTornadoCatalog",
    "TensorTornadoTargets",
    "TornadoStepResult",
]
