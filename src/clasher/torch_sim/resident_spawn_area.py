"""Retained tensor owner for serialized character spawn-area payloads."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields
from numbers import Real

import torch

from clasher.battle import BattleState
from clasher.kinematics import tiles_to_logic_units
from clasher.mechanics.shared.spawn_area import SpawnAreaEffect
from clasher.unit_traits import is_airborne_target, is_knockback_immune

from .combat_mechanics import TensorMechanicWorld, targets_in_native_area
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .special_movement import install_radial_knockback


@dataclass(frozen=True)
class TensorSpawnAreaCatalog:
    supported: torch.Tensor
    radius_units: torch.Tensor
    damage: torch.Tensor
    damage_integer_kind: torch.Tensor
    duration_ms: torch.Tensor
    status_duration: torch.Tensor
    movement_multiplier: torch.Tensor
    attack_multiplier: torch.Tensor
    spawn_multiplier: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    affects_hidden: torch.Tensor
    crown_multiplier: torch.Tensor
    knockback_units: torch.Tensor


@dataclass(frozen=True)
class SpawnAreaMaterializeResult:
    committed: torch.Tensor
    accepted: torch.Tensor
    unsupported: torch.Tensor
    capacity_rejected: torch.Tensor
    area_entity_ids: torch.Tensor


@dataclass(frozen=True)
class SpawnAreaStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    damage_targets: torch.Tensor
    status_targets: torch.Tensor
    damage: torch.Tensor
    deaths: torch.Tensor
    knockback_started: torch.Tensor


def _copy_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    batch = destination.batch_size
    for left_owner, right_owner in (
        (destination.battle, source.battle),
        (destination.battle.rng, source.battle.rng),
        (destination.status, source.status),
        (destination.phases, source.phases),
        (destination.events, source.events),
    ):
        for descriptor in fields(left_owner):  # type: ignore[arg-type]
            left = getattr(left_owner, descriptor.name)
            right = getattr(right_owner, descriptor.name)
            if (
                isinstance(left, torch.Tensor)
                and isinstance(right, torch.Tensor)
                and left.shape == right.shape
                and left.ndim > 0
                and left.shape[0] == batch
            ):
                left[rows] = right[rows]
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]


def _clear_slots_(runtime: TensorBattleRuntime, mask: torch.Tensor) -> None:
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == mask.shape
                and not (owner is runtime.battle and descriptor.name == "entity_id")
            ):
                expanded = mask.reshape(*mask.shape, *((1,) * (value.ndim - 2)))
                value.masked_fill_(expanded, 0)
    runtime.phases.target_slot.masked_fill_(mask, -1)
    runtime.battle.entity_tower_slot.masked_fill_(mask, -1)


def _serialized_multiplier(value: object) -> float:
    if value is None:
        return 1.0
    if not isinstance(value, Real):
        raise TypeError("serialized spawn-area multiplier must be numeric")
    number = float(value)
    return max(0.0, 1.0 + number / 100.0) if number <= 0 else number / 100.0


def _native_percent(amount: torch.Tensor, multiplier: torch.Tensor) -> torch.Tensor:
    base = torch.round(amount).to(torch.int64).clamp_min(0)
    percent = torch.round(multiplier * 100.0).to(torch.int64).clamp_min(0)
    return torch.where(
        (base > 0) & (percent > 0),
        torch.div(base * percent + 99, 100, rounding_mode="floor"),
        0,
    ).to(torch.float64)


@dataclass
class TensorResidentSpawnAreas:
    catalog: TensorSpawnAreaCatalog
    active: torch.Tensor
    area_entity_slot: torch.Tensor
    area_entity_id: torch.Tensor
    source_slot: torch.Tensor
    source_entity_id: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    center_units: torch.Tensor
    damage_snapshot_entity_ids: torch.Tensor
    applied_source_entity_id: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_airborne: torch.Tensor
    target_building: torch.Tensor
    target_crown: torch.Tensor
    target_damage_receivable: torch.Tensor
    target_effect_receivable: torch.Tensor
    target_has_shield: torch.Tensor
    target_shield: torch.Tensor
    target_shield_integer_kind: torch.Tensor
    target_shield_break_count: torch.Tensor
    target_knockback_receivable: torch.Tensor
    target_knockback_immune: torch.Tensor
    target_death_payload_supported: torch.Tensor
    knockback_active: torch.Tensor
    knockback_target_units: torch.Tensor
    knockback_velocity_work: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.active.device

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        capacity: int = 4,
    ) -> TensorResidentSpawnAreas:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match spawn-area runtime")
        if capacity < 1:
            raise ValueError("spawn-area capacity must be positive")
        device = runtime.device
        size = len(runtime.battle.card_names)

        def card_plane(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = card_plane(torch.bool)
        radius = card_plane(torch.int64)
        damage = card_plane(torch.float64)
        damage_kind = card_plane(torch.bool)
        duration = card_plane(torch.int64)
        status_duration = card_plane(torch.float64)
        movement = torch.ones(size, dtype=torch.float64, device=device)
        attack = torch.ones_like(movement)
        spawn = torch.ones_like(movement)
        hits_air = card_plane(torch.bool)
        hits_ground = card_plane(torch.bool)
        hidden = card_plane(torch.bool)
        crown = torch.ones(size, dtype=torch.float64, device=device)
        knockback = card_plane(torch.int64)
        definitions = battles[0].card_loader.load_card_definitions()
        for card_id, name in enumerate(runtime.battle.card_names):
            stats = battles[0].card_loader.get_card(name) if name else None
            definition = definitions.get(name)
            if stats is None or definition is None:
                continue
            mechanics = [
                mechanic
                for mechanic in definition.mechanics
                if isinstance(mechanic, SpawnAreaEffect)
            ]
            if len(mechanics) != 1:
                continue
            raw = mechanics[0].area_data
            scaled = stats.get_scaled_stat(raw.get("damage", 0) or 0)
            buff = raw.get("buffData") or {}
            supported[card_id] = True
            radius[card_id] = int(raw.get("radius", 0) or 0)
            damage[card_id] = float(0 if scaled is None else scaled)
            # SpawnAreaEffect explicitly casts the scaled payload through float.
            damage_kind[card_id] = False
            duration[card_id] = max(1, int(raw.get("lifeDuration", 0) or 0))
            status_duration[card_id] = float(raw.get("buffTime", 0) or 0) / 1_000
            if isinstance(buff, dict):
                movement[card_id] = _serialized_multiplier(buff.get("speedMultiplier"))
                attack[card_id] = _serialized_multiplier(buff.get("hitSpeedMultiplier"))
                spawn[card_id] = _serialized_multiplier(
                    buff.get("spawnSpeedMultiplier")
                )
            hits_air[card_id] = bool(raw.get("hitsAir", True))
            hits_ground[card_id] = bool(raw.get("hitsGround", True))
            hidden[card_id] = bool(raw.get("affectsHidden", False))
            crown[card_id] = max(
                0.0,
                1.0 + float(raw.get("crownTowerDamagePercent", 0) or 0) / 100.0,
            )
            # The scalar SpawnAreaEffect does not install displacement.
            knockback[card_id] = 0

        entity_shape = runtime.battle.entity_id.shape
        collision = torch.zeros(entity_shape, dtype=torch.int64, device=device)
        airborne = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        building = torch.zeros_like(airborne)
        is_crown = torch.zeros_like(airborne)
        damage_receivable = torch.ones(
            (runtime.batch_size, size, runtime.max_entities),
            dtype=torch.bool,
            device=device,
        )
        effect_receivable = torch.ones_like(damage_receivable)
        has_shield = torch.zeros_like(airborne)
        shield = torch.zeros(entity_shape, dtype=torch.float64, device=device)
        shield_kind = torch.zeros_like(airborne)
        shield_break = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        knock_receivable = torch.ones_like(airborne)
        immune = torch.zeros_like(airborne)
        death_supported = torch.ones_like(airborne)
        supported_cards = torch.nonzero(supported).flatten().tolist()
        for row, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                collision[row, slot] = tiles_to_logic_units(
                    entity.get_collision_radius()
                )
                airborne[row, slot] = is_airborne_target(entity)
                building[row, slot] = entity.entity_kind == 1
                is_crown[row, slot] = bool(
                    entity.entity_kind == 1
                    and getattr(entity.card_stats, "name", None)
                    in {"Tower", "KingTower"}
                )
                for source_card in supported_cards:
                    source_kind = runtime.battle.card_names[source_card]
                    affects = bool(hidden[source_card].item())
                    damage_receivable[row, source_card, slot] = (
                        entity.can_receive_area_damage(
                            source_kind, affects_hidden=affects
                        )
                    )
                    effect_receivable[row, source_card, slot] = (
                        entity.can_receive_effect(source_kind, affects_hidden=affects)
                    )
                shields = [
                    mechanic
                    for mechanic in entity.mechanics
                    if type(mechanic).__name__ == "Shield"
                ]
                if shields:
                    current = getattr(shields[0], "current_shield", 0)
                    has_shield[row, slot] = True
                    shield[row, slot] = float(current)
                    shield_kind[row, slot] = type(current) is int
                    shield_break[row, slot] = int(
                        getattr(entity, "_shield_break_count", 0)
                    )
                immune[row, slot] = is_knockback_immune(entity.card_stats)
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )

        shape = (runtime.batch_size, capacity)
        return cls(
            TensorSpawnAreaCatalog(
                supported,
                radius,
                damage,
                damage_kind,
                duration,
                status_duration,
                movement,
                attack,
                spawn,
                hits_air,
                hits_ground,
                hidden,
                crown,
                knockback,
            ),
            torch.zeros(shape, dtype=torch.bool, device=device),
            torch.full(shape, -1, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.full(shape, -1, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int8, device=device),
            torch.zeros((*shape, 2), dtype=torch.int64, device=device),
            torch.zeros(
                (*shape, runtime.max_entities), dtype=torch.int64, device=device
            ),
            torch.zeros(entity_shape, dtype=torch.int64, device=device),
            collision,
            airborne,
            building,
            is_crown,
            damage_receivable,
            effect_receivable,
            has_shield,
            shield,
            shield_kind,
            shield_break,
            knock_receivable,
            immune,
            death_supported,
            torch.zeros(entity_shape, dtype=torch.bool, device=device),
            torch.zeros((*entity_shape, 2), dtype=torch.int64, device=device),
            torch.zeros(entity_shape, dtype=torch.int64, device=device),
        )

    def clone(self) -> TensorResidentSpawnAreas:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentSpawnAreas:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("spawn-area fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentSpawnAreas,
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
        if destination.shape != selected.shape or source.device != self.device:
            raise ValueError("spawn-area reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(self, source: TensorResidentSpawnAreas, rows: torch.Tensor) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def _world(
        self,
        runtime: TensorBattleRuntime,
        effect_receivable: torch.Tensor,
    ) -> TensorMechanicWorld:
        core = runtime.battle
        return TensorMechanicWorld(
            present=runtime.entity_pool.active,
            entity_id=core.entity_id,
            owner=core.entity_player.to(torch.int64),
            x_units=core.entity_x_units.to(torch.int64),
            y_units=core.entity_y_units.to(torch.int64),
            collision_radius_units=self.target_collision_radius_units,
            distance_discount_sq_units=torch.zeros_like(core.entity_id),
            hp=core.entity_hp,
            alive=core.entity_active,
            airborne=self.target_airborne,
            building=self.target_building,
            crown=self.target_crown,
            targetable=torch.ones_like(core.entity_active),
            effect_receivable=effect_receivable,
        )

    def materialize_spawns_(
        self,
        runtime: TensorBattleRuntime,
        *,
        source_slots: torch.Tensor,
        valid: torch.Tensor,
    ) -> SpawnAreaMaterializeResult:
        if source_slots.shape != valid.shape or valid.ndim != 2:
            raise ValueError("spawn-area source planes must share [batch, lane]")
        if valid.shape[0] != self.batch_size or valid.shape[1] > runtime.max_entities:
            raise ValueError("spawn-area source lane layout differs")
        core = runtime.battle
        raw_source = source_slots.to(self.device, torch.int64)
        in_range = (raw_source >= 0) & (raw_source < runtime.max_entities)
        source = raw_source.clamp(0, runtime.max_entities - 1)
        requested = valid.to(self.device, torch.bool)
        cards = core.entity_card.gather(1, source)
        source_ids = core.entity_id.gather(1, source)
        already = self.applied_source_entity_id.gather(1, source) == source_ids
        live = runtime.entity_pool.active.gather(1, source) & core.entity_active.gather(
            1, source
        )
        eligible = (
            requested & in_range & live & self.catalog.supported[cards] & ~already
        )
        unsupported = (requested & ~eligible & ~already).any(dim=1)
        key = torch.where(eligible, source_ids, torch.iinfo(torch.int64).max)
        order = torch.argsort(key, dim=1, stable=True)
        ordered_valid = eligible.gather(1, order)
        ordered_source = source.gather(1, order)
        counts = ordered_valid.sum(dim=1, dtype=torch.int64)
        capacity_rejected = ~unsupported & (
            (counts > (~self.active).sum(dim=1))
            | (counts > (~runtime.entity_pool.active).sum(dim=1))
            | (runtime.events.count.to(torch.int64) + counts > runtime.events.capacity)
        )
        accepted_rows = runtime.supported & ~unsupported & ~capacity_rejected
        accepted = ordered_valid & accepted_rows[:, None]
        allocation = runtime.clone()
        allocation.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        entity_allocation = allocation.entity_pool.allocate(
            accepted.sum(dim=1, dtype=torch.int64)
        )
        allocated_mask = torch.zeros_like(allocation.entity_pool.active)
        allocated_mask.scatter_(
            1, entity_allocation.slots.clamp_min(0), entity_allocation.valid
        )
        _clear_slots_(allocation, allocated_mask)
        free_key = torch.where(
            ~working.active,
            torch.arange(working.active.shape[1], device=self.device)[None, :],
            working.active.shape[1],
        )
        owner_slots = torch.sort(free_key, dim=1).values
        rows = torch.arange(self.batch_size, device=self.device)
        event_targets = torch.zeros_like(entity_allocation.entity_ids)
        for rank in range(valid.shape[1]):
            selected = accepted[:, rank]
            source_slot = ordered_source[:, rank]
            owner_slot = owner_slots[:, rank].clamp_max(working.active.shape[1] - 1)
            entity_slot = entity_allocation.slots[:, rank].clamp_min(0)
            card = core.entity_card.gather(1, source_slot[:, None])[:, 0]
            player = core.entity_player.gather(1, source_slot[:, None])[:, 0]
            center = torch.stack(
                (
                    core.entity_x_units.gather(1, source_slot[:, None])[:, 0],
                    core.entity_y_units.gather(1, source_slot[:, None])[:, 0],
                ),
                dim=-1,
            ).to(torch.int64)
            world = working._world(
                allocation,
                working.target_damage_receivable[rows, card],
            )
            targets = (
                targets_in_native_area(
                    world,
                    owner=player.to(torch.int64),
                    center_x_units=center[:, 0],
                    center_y_units=center[:, 1],
                    radius_units=working.catalog.radius_units[card],
                    hits_air=working.catalog.hits_air[card],
                    hits_ground=working.catalog.hits_ground[card],
                )
                & selected[:, None]
            )
            target_order = allocation.entity_pool.id_order(targets)
            owner_index = (rows[selected], owner_slot[selected])
            working.active[owner_index] = True
            working.area_entity_slot[owner_index] = entity_slot[selected]
            working.area_entity_id[owner_index] = entity_allocation.entity_ids[
                selected, rank
            ]
            working.source_slot[owner_index] = source_slot[selected]
            working.source_entity_id[owner_index] = core.entity_id[
                rows[selected], source_slot[selected]
            ]
            working.card_id[owner_index] = card[selected]
            working.player_id[owner_index] = player[selected]
            working.center_units[owner_index] = center[selected]
            working.damage_snapshot_entity_ids[owner_index] = target_order.entity_ids[
                selected
            ]
            working.applied_source_entity_id[rows[selected], source_slot[selected]] = (
                core.entity_id[rows[selected], source_slot[selected]]
            )
            runtime_index = (rows[selected], entity_slot[selected])
            allocation.battle.entity_active[runtime_index] = True
            allocation.battle.entity_kind[runtime_index] = 3
            allocation.battle.entity_player[runtime_index] = player[selected]
            allocation.battle.entity_card[runtime_index] = card[selected]
            allocation.battle.entity_x_units[runtime_index] = center[selected, 0].to(
                torch.int32
            )
            allocation.battle.entity_y_units[runtime_index] = center[selected, 1].to(
                torch.int32
            )
            allocation.battle.entity_hp[runtime_index] = 1.0
            allocation.battle.entity_hp_integer_kind[runtime_index] = True
            allocation.battle.entity_max_hp[runtime_index] = 1.0
            event_targets[:, rank] = core.entity_id.gather(1, source_slot[:, None])[
                :, 0
            ]
        allocation.events.append(
            phase=TickPhase.OBJECTS,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=entity_allocation.valid,
            source_id=entity_allocation.entity_ids,
            target_id=event_targets,
            x_units=allocation.battle.entity_x_units.gather(
                1, entity_allocation.slots.clamp_min(0)
            ),
            y_units=allocation.battle.entity_y_units.gather(
                1, entity_allocation.slots.clamp_min(0)
            ),
            payload=allocation.battle.entity_card.gather(
                1, entity_allocation.slots.clamp_min(0)
            ),
        )
        allocation.mark_dirty(accepted_rows, phase=TickPhase.OBJECTS)
        _copy_runtime_rows_(runtime, allocation, accepted_rows)
        self._copy_rows_(working, accepted_rows)
        return SpawnAreaMaterializeResult(
            committed=~runtime.supported | accepted_rows,
            accepted=accepted_rows & (counts > 0),
            unsupported=unsupported,
            capacity_rejected=capacity_rejected,
            area_entity_ids=entity_allocation.entity_ids,
        )

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        battle_mask: torch.Tensor | None = None,
    ) -> SpawnAreaStepResult:
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("spawn-area battle_mask must have shape [batch]")
        snapshot_count = (self.damage_snapshot_entity_ids > 0).sum(
            dim=(1, 2), dtype=torch.int64
        )
        event_free = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = selected & (snapshot_count * 2 > event_free)
        supported = selected & ~capacity_rejected
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        rows = torch.arange(self.batch_size, device=self.device)
        core = working_runtime.battle
        damage_result = torch.zeros_like(core.entity_hp)
        death_result = torch.zeros_like(core.entity_active)
        damage_targets = torch.zeros_like(core.entity_active)
        status_targets = torch.zeros_like(core.entity_active)
        knock_started = torch.zeros_like(core.entity_active)
        unsupported = torch.zeros_like(supported)
        cleanup = torch.zeros_like(working_runtime.entity_pool.active)
        order = torch.argsort(
            torch.where(
                working.active,
                working.area_entity_id,
                torch.iinfo(torch.int64).max,
            ),
            dim=1,
            stable=True,
        )
        for rank in range(working.active.shape[1]):
            slot = order[:, rank]
            active = working.active.gather(1, slot[:, None])[:, 0] & supported
            card = working.card_id.gather(1, slot[:, None])[:, 0]
            player = working.player_id.gather(1, slot[:, None])[:, 0]
            area_id = working.area_entity_id.gather(1, slot[:, None])[:, 0]
            area_slot = working.area_entity_slot.gather(1, slot[:, None])[
                :, 0
            ].clamp_min(0)
            center = working.center_units.gather(
                1, slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            snapshot_ids = working.damage_snapshot_entity_ids.gather(
                1, slot[:, None, None].expand(-1, 1, runtime.max_entities)
            )[:, 0]
            target_slots = working_runtime.entity_pool.slots_for_ids(snapshot_ids)
            snapshot_valid = active[:, None] & (target_slots >= 0)
            for target_rank in range(runtime.max_entities):
                target_valid = snapshot_valid[:, target_rank]
                target_slot = target_slots[:, target_rank].clamp_min(0)
                amount = torch.where(
                    working.target_crown[rows, target_slot],
                    _native_percent(
                        working.catalog.damage[card],
                        working.catalog.crown_multiplier[card],
                    ),
                    working.catalog.damage[card],
                )
                absorbs = (
                    target_valid
                    & working.target_has_shield[rows, target_slot]
                    & (working.target_shield[rows, target_slot] > 0)
                    & (amount > 0)
                )
                next_shield = torch.clamp(
                    working.target_shield[rows, target_slot] - amount, min=0.0
                )
                shield_index = (rows[absorbs], target_slot[absorbs])
                broken = absorbs & (next_shield <= 0)
                working.target_shield[shield_index] = next_shield[absorbs]
                working.target_shield_integer_kind[shield_index] = False
                working.target_shield_break_count[
                    rows[broken], target_slot[broken]
                ] += 1
                hp_hit = target_valid & ~absorbs & (amount > 0)
                old_hp = core.entity_hp[rows, target_slot]
                hp_damage = torch.minimum(old_hp, amount)
                new_hp = torch.clamp(old_hp - amount, min=0.0)
                hp_index = (rows[hp_hit], target_slot[hp_hit])
                core.entity_hp[hp_index] = new_hp[hp_hit]
                core.entity_hp_integer_kind[hp_index] = False
                killed = hp_hit & (new_hp <= 0)
                core.entity_active[rows[killed], target_slot[killed]] = False
                damage_result[hp_index] += hp_damage[hp_hit]
                death_result[rows[killed], target_slot[killed]] = True
                damage_targets[rows[target_valid], target_slot[target_valid]] = True
                working_runtime.events.append(
                    phase=TickPhase.OBJECTS,
                    opcode=RuntimeEventOpcode.DAMAGE,
                    valid=target_valid[:, None],
                    source_id=area_id[:, None],
                    target_id=snapshot_ids[:, target_rank, None],
                    x_units=core.entity_x_units[rows, target_slot][:, None],
                    y_units=core.entity_y_units[rows, target_slot][:, None],
                    amount=torch.where(hp_hit, hp_damage, 0.0)[:, None],
                    payload=card[:, None],
                )
                working_runtime.events.append(
                    phase=TickPhase.OBJECTS,
                    opcode=RuntimeEventOpcode.DEATH,
                    valid=killed[:, None],
                    source_id=area_id[:, None],
                    target_id=snapshot_ids[:, target_rank, None],
                    payload=card[:, None],
                )
                unsupported |= (
                    killed & ~working.target_death_payload_supported[rows, target_slot]
                )

            world = working._world(
                working_runtime,
                working.target_effect_receivable[rows, card],
            )
            status = (
                targets_in_native_area(
                    world,
                    owner=player.to(torch.int64),
                    center_x_units=center[:, 0],
                    center_y_units=center[:, 1],
                    radius_units=working.catalog.radius_units[card],
                    hits_air=working.catalog.hits_air[card],
                    hits_ground=working.catalog.hits_ground[card],
                )
                & active[:, None]
            )
            status_targets |= status
            stun = status & (
                (working.catalog.movement_multiplier[card] == 0)[:, None]
                & (working.catalog.attack_multiplier[card] == 0)[:, None]
                & (working.catalog.spawn_multiplier[card] == 0)[:, None]
            )
            slow = (
                status
                & ~stun
                & (
                    torch.minimum(
                        working.catalog.movement_multiplier[card],
                        torch.minimum(
                            working.catalog.attack_multiplier[card],
                            working.catalog.spawn_multiplier[card],
                        ),
                    )
                    < 1.0
                )[:, None]
            )
            working_runtime.status.apply_stun(
                working.catalog.status_duration[card, None], mask=stun
            )
            working_runtime.status.apply_slow(
                working.catalog.status_duration[card, None],
                working.catalog.movement_multiplier[card, None],
                attack_speed_multiplier=working.catalog.attack_multiplier[card, None],
                spawn_speed_multiplier=working.catalog.spawn_multiplier[card, None],
                mask=slow,
            )
            distance = working.catalog.knockback_units[card]
            knock = (
                status
                & (distance[:, None] > 0)
                & ~working.target_building
                & working.target_knockback_receivable
                & ~working.target_knockback_immune
            )
            positions = torch.stack(
                (core.entity_x_units, core.entity_y_units), dim=-1
            ).to(torch.int64)
            install = install_radial_knockback(
                positions,
                center[:, None, :].expand_as(positions),
                distance[:, None].expand_as(core.entity_id),
                player_id=core.entity_player.to(torch.int64),
                eligible=knock,
            )
            working.knockback_active |= install.started
            working.knockback_target_units.copy_(
                torch.where(
                    install.started[..., None],
                    install.target_units,
                    working.knockback_target_units,
                )
            )
            working.knockback_velocity_work.copy_(
                torch.where(
                    install.started,
                    install.velocity_work,
                    working.knockback_velocity_work,
                )
            )
            knock_started |= install.started
            cleanup[rows[active], area_slot[active]] = True
            working.active[rows[active], slot[active]] = False

        working_runtime.entity_pool.cleanup(cleanup)
        _clear_slots_(working_runtime, cleanup)
        committed = supported & ~unsupported
        working_runtime.mark_dirty(committed, phase=TickPhase.OBJECTS)
        _copy_runtime_rows_(runtime, working_runtime, committed)
        self._copy_rows_(working, committed)
        return SpawnAreaStepResult(
            committed=~selected | committed,
            capacity_rejected=capacity_rejected,
            damage_targets=damage_targets & committed[:, None],
            status_targets=status_targets & committed[:, None],
            damage=torch.where(committed[:, None], damage_result, 0.0),
            deaths=death_result & committed[:, None],
            knockback_started=knock_started & committed[:, None],
        )


__all__ = [
    "SpawnAreaMaterializeResult",
    "SpawnAreaStepResult",
    "TensorResidentSpawnAreas",
    "TensorSpawnAreaCatalog",
]
