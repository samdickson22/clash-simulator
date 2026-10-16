"""Retained tensor lifecycle for serialized finite piercing projectiles.

Rows are selected only from projectile metadata: a positive finite
``projectileRange`` and speed, with no child, area, status, knockback, or
source-mechanic payload.  Runtime ticks retain launch geometry, temporary
homing, point-sampled collision, one-hit identity sets, damage, and cleanup
without stepping Python projectile objects.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.entities import Building, Projectile
from clasher.kinematics import tiles_to_logic_units
from clasher.logic_math import native_percent_damage
from clasher.unit_traits import is_airborne_target

from .movement import integer_sqrt_tensor, normalized_vector_units
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorPiercingProjectileCatalog:
    supported: torch.Tensor
    reason: tuple[str, ...]
    muzzle_radius_units: torch.Tensor
    owner_y_offset_units: torch.Tensor
    speed_units: torch.Tensor
    range_units: torch.Tensor
    radius_units: torch.Tensor
    start_extra_radius_units: torch.Tensor
    homing_time_ms: torch.Tensor
    homing_min_distance_units: torch.Tensor
    damage: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    crown_damage: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.supported.numel())


@dataclass(frozen=True)
class PiercingLaunchResult:
    committed: torch.Tensor
    accepted: torch.Tensor
    unsupported: torch.Tensor
    capacity_rejected: torch.Tensor
    projectile_entity_ids: torch.Tensor
    damage: torch.Tensor
    deaths: torch.Tensor


@dataclass(frozen=True)
class PiercingStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    expired: torch.Tensor
    damage: torch.Tensor
    deaths: torch.Tensor


def _serialized_planes(data: dict[str, object]) -> tuple[bool, bool]:
    target = str(data.get("tidTarget", ""))
    if "AIR_AND_GROUND" in target:
        return True, True
    if "AIR" in target:
        return True, False
    if "GROUND" in target:
        return False, True
    return bool(data.get("hitsAir", True)), bool(data.get("hitsGround", True))


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


def _clear_entity_slots_(runtime: TensorBattleRuntime, mask: torch.Tensor) -> None:
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


def _first_free_slot(mask: torch.Tensor) -> torch.Tensor:
    width = mask.shape[1]
    indices = torch.arange(width, dtype=torch.int64, device=mask.device)[None, :]
    return torch.where(mask, indices, width).amin(dim=1)


@dataclass
class TensorResidentPiercingProjectiles:
    catalog: TensorPiercingProjectileCatalog
    active: torch.Tensor
    entity_slot: torch.Tensor
    entity_id: torch.Tensor
    source_id: torch.Tensor
    primary_target_id: torch.Tensor
    primary_target_units: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    position_units: torch.Tensor
    launch_units: torch.Tensor
    endpoint_units: torch.Tensor
    temporary_homing_remaining_ms: torch.Tensor
    hit_entity_ids: torch.Tensor
    hit_count: torch.Tensor
    target_entity_id: torch.Tensor
    target_area_receivable: torch.Tensor
    target_airborne: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_building: torch.Tensor
    target_crown: torch.Tensor
    target_has_shield: torch.Tensor
    target_shield: torch.Tensor
    target_shield_integer_kind: torch.Tensor
    target_shield_break_count: torch.Tensor
    target_death_payload_supported: torch.Tensor

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
        capacity: int = 16,
    ) -> TensorResidentPiercingProjectiles:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match piercing runtime")
        if capacity < 1:
            raise ValueError("piercing projectile capacity must be positive")
        device = runtime.device
        size = len(runtime.battle.card_names)

        def card_plane(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = card_plane(torch.bool)
        reasons = ["not a finite serialized piercing projectile"] * size
        muzzle = card_plane(torch.int64)
        y_offset = card_plane(torch.int64)
        speed = card_plane(torch.int64)
        distance = card_plane(torch.int64)
        radius = card_plane(torch.int64)
        extra = card_plane(torch.int64)
        homing_time = card_plane(torch.int64)
        homing_min = card_plane(torch.int64)
        damage = card_plane(torch.float64)
        hits_air = card_plane(torch.bool)
        hits_ground = card_plane(torch.bool)
        crown_damage = card_plane(torch.float64)
        definitions = battles[0].card_loader.load_card_definitions()
        for card, name in enumerate(runtime.battle.card_names):
            stats = battles[0].card_loader.get_card(name) if name else None
            definition = definitions.get(name)
            if stats is None or definition is None:
                continue
            projectile = stats.projectile_data or {}
            projectile_range = int(projectile.get("projectileRange", 0) or 0)
            projectile_speed = int(projectile.get("speed", 0) or 0)
            if projectile_range <= 0 or projectile_speed <= 0:
                continue
            unsupported_payloads = (
                "spawnProjectileData",
                "spawnAreaEffectObjectData",
                "targetBuffData",
            )
            if any(projectile.get(field) for field in unsupported_payloads):
                reasons[card] = "piercing projectile has an additional payload"
                continue
            if (
                projectile.get("pushback")
                or projectile.get("buffTime")
                or definition.mechanics
            ):
                reasons[card] = "piercing projectile source effects are not retained"
                continue
            scaled_damage = stats.scaled_damage or stats.damage
            if scaled_damage is None or float(scaled_damage) <= 0:
                reasons[card] = "piercing projectile damage is not positive"
                continue
            air, ground = _serialized_planes(projectile)
            multiplier = max(
                0.0,
                1.0 + float(projectile.get("crownTowerDamagePercent", 0) or 0) / 100.0,
            )
            supported[card] = True
            reasons[card] = ""
            muzzle[card] = tiles_to_logic_units(
                float(stats.projectile_start_radius or 0.0)
            )
            y_offset[card] = tiles_to_logic_units(
                float(stats.projectile_y_offset or 0.0)
            )
            speed[card] = projectile_speed
            distance[card] = projectile_range
            radius[card] = int(
                projectile.get("projectileRadius", projectile.get("radius", 0)) or 0
            )
            extra[card] = int(projectile.get("projectileStartExtraRadius", 0) or 0)
            homing_time[card] = int(projectile.get("homingTime", 0) or 0)
            homing_min[card] = int(projectile.get("homingMinDistance", 0) or 0)
            damage[card] = float(scaled_damage)
            hits_air[card] = air
            hits_ground[card] = ground
            crown_damage[card] = float(native_percent_damage(scaled_damage, multiplier))

        projectile_shape = (runtime.batch_size, capacity)
        entity_shape = runtime.battle.entity_id.shape
        area_receivable = torch.ones(
            (runtime.batch_size, size, runtime.max_entities),
            dtype=torch.bool,
            device=device,
        )
        airborne = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        collision = torch.zeros(entity_shape, dtype=torch.int64, device=device)
        building = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        crown = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        has_shield = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        shield = torch.zeros(entity_shape, dtype=torch.float64, device=device)
        shield_kind = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        shield_break = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        death_supported = torch.ones(entity_shape, dtype=torch.bool, device=device)
        active = torch.zeros(projectile_shape, dtype=torch.bool, device=device)
        entity_slot = torch.full(projectile_shape, -1, dtype=torch.int64, device=device)
        entity_id = torch.zeros(projectile_shape, dtype=torch.int64, device=device)
        source_id = torch.zeros(projectile_shape, dtype=torch.int64, device=device)
        primary_id = torch.zeros(projectile_shape, dtype=torch.int64, device=device)
        card_id = torch.zeros(projectile_shape, dtype=torch.int64, device=device)
        player = torch.zeros(projectile_shape, dtype=torch.int8, device=device)
        position = torch.zeros((*projectile_shape, 2), dtype=torch.int64, device=device)
        primary_units = torch.zeros_like(position)
        launch = torch.zeros_like(position)
        endpoint = torch.zeros_like(position)
        temporary_homing = torch.zeros(
            projectile_shape, dtype=torch.int64, device=device
        )
        hit_ids = torch.zeros(
            (*projectile_shape, runtime.max_entities),
            dtype=torch.int64,
            device=device,
        )
        hit_count = torch.zeros(projectile_shape, dtype=torch.int64, device=device)

        for row_index, battle in enumerate(battles):
            slot_by_id = {
                int(value): slot
                for slot, value in enumerate(
                    runtime.battle.entity_id[row_index].tolist()
                )
                if int(value) > 0
            }
            source_by_card: dict[int, object] = {}
            for object_id, entity in battle.entities.items():
                slot = slot_by_id[object_id]
                core_card = int(runtime.battle.entity_card[row_index, slot].item())
                source_by_card.setdefault(core_card, entity)
                airborne[row_index, slot] = is_airborne_target(entity)
                collision[row_index, slot] = tiles_to_logic_units(
                    entity.get_collision_radius()
                )
                building[row_index, slot] = isinstance(entity, Building)
                crown[row_index, slot] = isinstance(entity, Building) and getattr(
                    entity.card_stats, "name", ""
                ) in {"Tower", "KingTower"}
                shields = [
                    mechanic
                    for mechanic in entity.mechanics
                    if type(mechanic).__name__ == "Shield"
                ]
                if shields:
                    current = getattr(shields[0], "current_shield", 0)
                    has_shield[row_index, slot] = True
                    shield[row_index, slot] = float(current)
                    shield_kind[row_index, slot] = type(current) is int
                    shield_break[row_index, slot] = int(
                        getattr(entity, "_shield_break_count", 0)
                    )
                death_supported[row_index, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )
            for source_card in torch.nonzero(supported).flatten().tolist():
                source = source_by_card.get(source_card)
                source_name = runtime.battle.card_names[source_card]
                for object_id, entity in battle.entities.items():
                    area_receivable[row_index, source_card, slot_by_id[object_id]] = (
                        entity.can_receive_area_damage(
                            source_name,
                            source_entity=source,  # type: ignore[arg-type]
                        )
                    )
            live = sorted(
                (
                    entity
                    for entity in battle.entities.values()
                    if isinstance(entity, Projectile) and entity.pierces
                ),
                key=lambda candidate: candidate.id,
            )
            if len(live) > capacity:
                raise ValueError("live piercing projectiles exceed retained capacity")
            for lane, projectile in enumerate(live):
                slot = slot_by_id[projectile.id]
                core_card = int(runtime.battle.entity_card[row_index, slot].item())
                if core_card <= 0 or not bool(supported[core_card].item()):
                    continue
                active[row_index, lane] = projectile.is_alive
                entity_slot[row_index, lane] = slot
                entity_id[row_index, lane] = projectile.id
                source_id[row_index, lane] = int(
                    getattr(projectile.source_entity, "id", 0) or 0
                )
                primary_id[row_index, lane] = int(
                    getattr(projectile.primary_target, "id", 0) or 0
                )
                primary = projectile.primary_target
                if primary is not None:
                    primary_units[row_index, lane] = torch.tensor(
                        (
                            tiles_to_logic_units(primary.position.x),
                            tiles_to_logic_units(primary.position.y),
                        ),
                        dtype=torch.int64,
                        device=device,
                    )
                card_id[row_index, lane] = core_card
                player[row_index, lane] = projectile.player_id
                position[row_index, lane] = torch.tensor(
                    (
                        tiles_to_logic_units(projectile.position.x),
                        tiles_to_logic_units(projectile.position.y),
                    ),
                    dtype=torch.int64,
                    device=device,
                )
                projectile_launch = projectile.launch_position or projectile.position
                launch[row_index, lane] = torch.tensor(
                    (
                        tiles_to_logic_units(projectile_launch.x),
                        tiles_to_logic_units(projectile_launch.y),
                    ),
                    dtype=torch.int64,
                    device=device,
                )
                endpoint[row_index, lane] = torch.tensor(
                    (
                        tiles_to_logic_units(projectile.target_position.x),
                        tiles_to_logic_units(projectile.target_position.y),
                    ),
                    dtype=torch.int64,
                    device=device,
                )
                temporary_homing[row_index, lane] = int(
                    projectile._temporary_homing_remaining_ms
                )
                ordered_hits = sorted(projectile.hit_entity_ids)
                hit_count[row_index, lane] = len(ordered_hits)
                if ordered_hits:
                    hit_ids[row_index, lane, : len(ordered_hits)] = torch.tensor(
                        ordered_hits, dtype=torch.int64, device=device
                    )

        return cls(
            TensorPiercingProjectileCatalog(
                supported,
                tuple(reasons),
                muzzle,
                y_offset,
                speed,
                distance,
                radius,
                extra,
                homing_time,
                homing_min,
                damage,
                hits_air,
                hits_ground,
                crown_damage,
            ),
            active,
            entity_slot,
            entity_id,
            source_id,
            primary_id,
            primary_units,
            card_id,
            player,
            position,
            launch,
            endpoint,
            temporary_homing,
            hit_ids,
            hit_count,
            runtime.battle.entity_id.clone(),
            area_receivable,
            airborne,
            collision,
            building,
            crown,
            has_shield,
            shield,
            shield_kind,
            shield_break,
            death_supported,
        )

    def clone(self) -> TensorResidentPiercingProjectiles:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentPiercingProjectiles:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("piercing fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentPiercingProjectiles,
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
            raise ValueError("piercing reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(
        self, source: TensorResidentPiercingProjectiles, rows: torch.Tensor
    ) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def _refresh_reused_target_slots_(self, runtime: TensorBattleRuntime) -> None:
        replaced = self.target_entity_id != runtime.battle.entity_id
        self.target_entity_id.copy_(runtime.battle.entity_id)
        safe_card = runtime.card_catalog_index[runtime.battle.entity_card].clamp_min(0)
        self.target_collision_radius_units.copy_(
            runtime.catalog.collision_radius_units[safe_card].to(torch.int64)
        )
        self.target_airborne.copy_(runtime.catalog.is_air_unit[safe_card])
        self.target_building.copy_(runtime.battle.entity_kind == 1)
        self.target_crown &= ~replaced
        self.target_has_shield &= ~replaced
        self.target_shield.masked_fill_(replaced, 0.0)
        self.target_shield_integer_kind.masked_fill_(replaced, False)
        self.target_shield_break_count.masked_fill_(replaced, 0)
        self.target_death_payload_supported.masked_fill_(replaced, True)
        self.target_area_receivable.masked_fill_(replaced[:, None, :], True)

    def _apply_sample_damage_(
        self,
        runtime: TensorBattleRuntime,
        projectile_slot: torch.Tensor,
        valid_projectile: torch.Tensor,
        radius_units: torch.Tensor,
        damage_result: torch.Tensor,
        death_result: torch.Tensor,
        phase: TickPhase = TickPhase.OBJECTS,
    ) -> torch.Tensor:
        """Resolve one projectile sample in stable entity-ID order."""

        rows = torch.arange(self.batch_size, device=self.device)
        core = runtime.battle
        slot_index = projectile_slot[:, None]
        player = self.player_id.gather(1, slot_index)[:, 0]
        card = self.card_id.gather(1, slot_index)[:, 0]
        projectile_id = self.entity_id.gather(1, slot_index)[:, 0]
        position = self.position_units.gather(
            1, slot_index[:, :, None].expand(-1, 1, 2)
        )[:, 0]
        previous = self.hit_entity_ids.gather(
            1,
            slot_index[:, :, None].expand(-1, 1, runtime.max_entities),
        )[:, 0]
        already_hit = (previous[:, :, None] == core.entity_id[:, None, :]).any(dim=1)
        dx = core.entity_x_units.to(torch.int64) - position[:, 0, None]
        dy = core.entity_y_units.to(torch.int64) - position[:, 1, None]
        reach = radius_units[:, None] + self.target_collision_radius_units
        circular = dx.square() + dy.square() < reach.square()
        closest_x = torch.minimum(
            core.entity_x_units.to(torch.int64) + self.target_collision_radius_units,
            torch.maximum(
                core.entity_x_units.to(torch.int64)
                - self.target_collision_radius_units,
                position[:, 0, None],
            ),
        )
        closest_y = torch.minimum(
            core.entity_y_units.to(torch.int64) + self.target_collision_radius_units,
            torch.maximum(
                core.entity_y_units.to(torch.int64)
                - self.target_collision_radius_units,
                position[:, 1, None],
            ),
        )
        square = (closest_x - position[:, 0, None]).square() + (
            closest_y - position[:, 1, None]
        ).square() < radius_units[:, None].square()
        overlap = torch.where(self.target_building, square, circular)
        eligible = (
            valid_projectile[:, None]
            & runtime.entity_pool.active
            & core.entity_active
            & (core.entity_player != player[:, None])
            & ((core.entity_kind == 0) | (core.entity_kind == 1))
            & self.target_area_receivable[rows, card]
            & torch.where(
                self.target_airborne,
                self.catalog.hits_air[card, None],
                self.catalog.hits_ground[card, None],
            )
            & ~already_hit
            & overlap
        )
        ordered = runtime.entity_pool.id_order(eligible)
        unsupported = torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
        for target_rank in range(runtime.max_entities):
            target_valid = ordered.valid[:, target_rank]
            target_slot = ordered.slots[:, target_rank].clamp_min(0)
            target_id = ordered.entity_ids[:, target_rank]
            amount = torch.where(
                self.target_crown[rows, target_slot],
                self.catalog.crown_damage[card],
                self.catalog.damage[card],
            )
            shielded = (
                target_valid
                & self.target_has_shield[rows, target_slot]
                & (self.target_shield[rows, target_slot] > 0.0)
            )
            next_shield = torch.clamp(
                self.target_shield[rows, target_slot] - amount, min=0.0
            )
            shield_index = (rows[shielded], target_slot[shielded])
            self.target_shield[shield_index] = next_shield[shielded]
            self.target_shield_integer_kind[shield_index] = False
            broken = shielded & (next_shield <= 0.0)
            self.target_shield_break_count[rows[broken], target_slot[broken]] += 1
            hp_damage = torch.where(shielded, 0.0, amount)
            old_hp = core.entity_hp[rows, target_slot]
            applied = torch.minimum(old_hp, hp_damage)
            new_hp = torch.clamp(old_hp - hp_damage, min=0.0)
            hit_index = (rows[target_valid], target_slot[target_valid])
            core.entity_hp[hit_index] = new_hp[target_valid]
            hp_mutated = target_valid & ~shielded & (hp_damage > 0.0)
            core.entity_hp_integer_kind[rows[hp_mutated], target_slot[hp_mutated]] = (
                False
            )
            killed = target_valid & (new_hp <= 0.0)
            core.entity_active[rows[killed], target_slot[killed]] = False
            runtime.phases.death_pending[rows[killed], target_slot[killed]] = True
            damage_result[hit_index] += applied[target_valid]
            death_result[rows[killed], target_slot[killed]] = True
            count = self.hit_count.gather(1, slot_index)[:, 0]
            hit_capacity = count < runtime.max_entities
            unsupported |= target_valid & ~hit_capacity
            write = target_valid & hit_capacity
            self.hit_entity_ids[rows[write], projectile_slot[write], count[write]] = (
                target_id[write]
            )
            self.hit_count[rows[write], projectile_slot[write]] += 1
            runtime.events.append(
                phase=phase,
                opcode=RuntimeEventOpcode.DAMAGE,
                valid=(target_valid & ~shielded & (applied > 0.0))[:, None],
                source_id=projectile_id[:, None],
                target_id=target_id[:, None],
                x_units=core.entity_x_units[rows, target_slot][:, None],
                y_units=core.entity_y_units[rows, target_slot][:, None],
                amount=applied[:, None],
                payload=card[:, None],
            )
            runtime.events.append(
                phase=phase,
                opcode=RuntimeEventOpcode.DEATH,
                valid=killed[:, None],
                source_id=projectile_id[:, None],
                target_id=target_id[:, None],
                x_units=core.entity_x_units[rows, target_slot][:, None],
                y_units=core.entity_y_units[rows, target_slot][:, None],
                payload=card[:, None],
            )
            unsupported |= (
                killed & ~self.target_death_payload_supported[rows, target_slot]
            )
        return unsupported

    def commit_attacks_(
        self,
        runtime: TensorBattleRuntime,
        *,
        source_slots: torch.Tensor,
        target_slots: torch.Tensor,
        valid: torch.Tensor,
    ) -> PiercingLaunchResult:
        if not (source_slots.shape == target_slots.shape == valid.shape):
            raise ValueError("piercing attack planes must share [batch, lane]")
        if valid.ndim != 2 or valid.shape[0] != self.batch_size:
            raise ValueError("piercing attack planes must have shape [batch, lane]")
        requested = valid.to(self.device, torch.bool)
        if not bool(requested.any().item()):
            return PiercingLaunchResult(
                committed=torch.ones(
                    self.batch_size, dtype=torch.bool, device=self.device
                ),
                accepted=torch.zeros(
                    self.batch_size, dtype=torch.bool, device=self.device
                ),
                unsupported=torch.zeros(
                    self.batch_size, dtype=torch.bool, device=self.device
                ),
                capacity_rejected=torch.zeros(
                    self.batch_size, dtype=torch.bool, device=self.device
                ),
                projectile_entity_ids=torch.zeros_like(requested, dtype=torch.int64),
                damage=torch.zeros_like(runtime.battle.entity_hp),
                deaths=torch.zeros_like(runtime.battle.entity_active),
            )
        core = runtime.battle
        source = source_slots.to(self.device, torch.int64).clamp(
            0, runtime.max_entities - 1
        )
        target = target_slots.to(self.device, torch.int64).clamp(
            0, runtime.max_entities - 1
        )
        cards = core.entity_card.gather(1, source)
        eligible = (
            requested
            & runtime.entity_pool.active.gather(1, source)
            & core.entity_active.gather(1, source)
            & runtime.entity_pool.active.gather(1, target)
            & core.entity_active.gather(1, target)
            & self.catalog.supported[cards]
        )
        unsupported = (requested & ~eligible).any(dim=1)
        source_ids = core.entity_id.gather(1, source)
        target_ids = core.entity_id.gather(1, target)
        lane = torch.arange(valid.shape[1], device=self.device)[None, :]
        maximum = torch.maximum(source_ids, target_ids).amax().clamp_min(1) + 1
        key = (source_ids * maximum + target_ids) * (valid.shape[1] + 1) + lane
        order = torch.argsort(
            torch.where(eligible, key, torch.iinfo(torch.int64).max),
            dim=1,
            stable=True,
        )
        ordered_valid = torch.gather(eligible, 1, order)
        counts = ordered_valid.sum(dim=1, dtype=torch.int64)
        worst_events = counts * (1 + 2 * runtime.max_entities)
        free_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = (
            (counts > (~self.active).sum(dim=1))
            | (counts > (~runtime.entity_pool.active).sum(dim=1))
            | (worst_events > free_events)
        )
        selected = requested.any(dim=1)
        supported_rows = selected & ~unsupported & ~capacity_rejected
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        working._refresh_reused_target_slots_(working_runtime)
        allocation = working_runtime.entity_pool.allocate(
            torch.where(supported_rows, counts, 0)
        )
        allocated_mask = torch.zeros_like(working_runtime.entity_pool.active)
        allocated_mask.scatter_(1, allocation.slots.clamp_min(0), allocation.valid)
        _clear_entity_slots_(working_runtime, allocated_mask)
        rows = torch.arange(self.batch_size, device=self.device)
        damage = torch.zeros_like(core.entity_hp)
        deaths = torch.zeros_like(core.entity_active)
        projectile_ids = torch.zeros_like(valid, dtype=torch.int64)
        object_free = ~working.active
        unsupported_after = torch.zeros_like(supported_rows)
        allocation_rank = torch.zeros(
            self.batch_size, dtype=torch.int64, device=self.device
        )
        for rank in range(valid.shape[1]):
            ordered_lane = order[:, rank]
            attack_valid = ordered_valid[:, rank] & supported_rows
            source_slot = source.gather(1, ordered_lane[:, None])[:, 0]
            target_slot = target.gather(1, ordered_lane[:, None])[:, 0]
            card = cards.gather(1, ordered_lane[:, None])[:, 0]
            object_slot = _first_free_slot(object_free).clamp_max(self.capacity - 1)
            entity_rank = allocation_rank.clamp_max(runtime.max_entities - 1)
            entity_slot = allocation.slots.gather(1, entity_rank[:, None])[:, 0]
            entity_id = allocation.entity_ids.gather(1, entity_rank[:, None])[:, 0]
            source_position = torch.stack(
                (
                    core.entity_x_units[rows, source_slot],
                    core.entity_y_units[rows, source_slot],
                ),
                dim=1,
            ).to(torch.int64)
            target_position = torch.stack(
                (
                    core.entity_x_units[rows, target_slot],
                    core.entity_y_units[rows, target_slot],
                ),
                dim=1,
            ).to(torch.int64)
            direction = target_position - source_position
            muzzle_vector = normalized_vector_units(
                direction, self.catalog.muzzle_radius_units[card]
            )
            launch = source_position + muzzle_vector
            launch[:, 1] += torch.where(
                core.entity_player[rows, source_slot] == 0,
                self.catalog.owner_y_offset_units[card],
                -self.catalog.owner_y_offset_units[card],
            )
            ray = normalized_vector_units(direction, self.catalog.range_units[card])
            endpoint = launch + ray
            launch_delta = target_position - launch
            launch_distance = integer_sqrt_tensor(
                (launch_delta * launch_delta).sum(dim=1)
            )
            homing = torch.where(
                launch_distance > self.catalog.homing_min_distance_units[card],
                self.catalog.homing_time_ms[card],
                0,
            )
            index = (rows[attack_valid], object_slot[attack_valid])
            working.active[index] = True
            working.entity_slot[index] = entity_slot[attack_valid]
            working.entity_id[index] = entity_id[attack_valid]
            working.source_id[index] = core.entity_id[rows, source_slot][attack_valid]
            working.primary_target_id[index] = core.entity_id[rows, target_slot][
                attack_valid
            ]
            working.primary_target_units[index] = target_position[attack_valid]
            working.card_id[index] = card[attack_valid]
            working.player_id[index] = core.entity_player[rows, source_slot][
                attack_valid
            ]
            working.position_units[index] = launch[attack_valid]
            working.launch_units[index] = launch[attack_valid]
            working.endpoint_units[index] = endpoint[attack_valid]
            working.temporary_homing_remaining_ms[index] = homing[attack_valid]
            working.hit_entity_ids[index] = 0
            working.hit_count[index] = 0
            runtime_index = (rows[attack_valid], entity_slot[attack_valid])
            work_core = working_runtime.battle
            work_core.entity_active[runtime_index] = True
            work_core.entity_kind[runtime_index] = 2
            work_core.entity_player[runtime_index] = core.entity_player[
                rows, source_slot
            ][attack_valid]
            work_core.entity_card[runtime_index] = card[attack_valid]
            work_core.entity_x_units[runtime_index] = launch[attack_valid, 0].to(
                torch.int32
            )
            work_core.entity_y_units[runtime_index] = launch[attack_valid, 1].to(
                torch.int32
            )
            work_core.entity_hp[runtime_index] = 1.0
            work_core.entity_hp_integer_kind[runtime_index] = True
            work_core.entity_max_hp[runtime_index] = 1.0
            working_runtime.phases.target_slot[runtime_index] = target_slot[
                attack_valid
            ]
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.PROJECTILE,
                valid=attack_valid[:, None],
                source_id=core.entity_id[rows, source_slot][:, None],
                target_id=entity_id[:, None],
                x_units=launch[:, 0, None],
                y_units=launch[:, 1, None],
                payload=card[:, None],
            )
            start_radius = (
                self.catalog.radius_units[card]
                + self.catalog.start_extra_radius_units[card]
            )
            unsupported_after |= working._apply_sample_damage_(
                working_runtime,
                object_slot,
                attack_valid
                & (self.catalog.radius_units[card] > 0)
                & (self.catalog.start_extra_radius_units[card] > 0),
                start_radius,
                damage,
                deaths,
                phase=TickPhase.COMBAT,
            )
            object_free[rows[attack_valid], object_slot[attack_valid]] = False
            allocation_rank += attack_valid.to(torch.int64)
            projectile_ids.scatter_(
                1,
                ordered_lane[:, None],
                torch.where(attack_valid, entity_id, 0)[:, None],
            )
        commit = supported_rows & ~unsupported_after
        working_runtime.mark_dirty(commit, phase=TickPhase.OBJECTS)
        _copy_runtime_rows_(runtime, working_runtime, commit)
        self._copy_rows_(working, commit)
        return PiercingLaunchResult(
            committed=~selected | commit,
            accepted=commit & (counts > 0),
            unsupported=unsupported | unsupported_after,
            capacity_rejected=capacity_rejected,
            projectile_entity_ids=projectile_ids,
            damage=torch.where(commit[:, None], damage, 0.0),
            deaths=deaths & commit[:, None],
        )

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> PiercingStepResult:
        if dt_ms != 50:
            raise ValueError("retained piercing lifecycle requires one 50ms tick")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("piercing battle_mask must have shape [batch]")
        retained_activity = self.active.any(dim=1) & selected
        if not bool(retained_activity.any().item()):
            return PiercingStepResult(
                committed=torch.ones_like(selected),
                capacity_rejected=torch.zeros_like(selected),
                expired=torch.zeros_like(self.active),
                damage=torch.zeros_like(runtime.battle.entity_hp),
                deaths=torch.zeros_like(runtime.battle.entity_active),
            )
        maximum_events = (
            self.active.sum(dim=1, dtype=torch.int64) * runtime.max_entities * 2
        )
        free_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = selected & (maximum_events > free_events)
        supported = selected & ~capacity_rejected
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        working._refresh_reused_target_slots_(working_runtime)
        rows = torch.arange(self.batch_size, device=self.device)
        core = working_runtime.battle
        damage = torch.zeros_like(core.entity_hp)
        deaths = torch.zeros_like(core.entity_active)
        expired = torch.zeros_like(working.active)
        unsupported = torch.zeros_like(supported)
        order = torch.argsort(
            torch.where(
                working.active,
                working.entity_id,
                torch.iinfo(torch.int64).max,
            ),
            dim=1,
            stable=True,
        )
        cleanup = torch.zeros_like(working_runtime.entity_pool.active)
        for rank in range(self.capacity):
            projectile_slot = order[:, rank]
            active = working.active.gather(1, projectile_slot[:, None])[:, 0]
            active &= supported
            entity_slot = working.entity_slot.gather(1, projectile_slot[:, None])[
                :, 0
            ].clamp_min(0)
            entity_id = working.entity_id.gather(1, projectile_slot[:, None])[:, 0]
            identity = working_runtime.entity_pool.active[rows, entity_slot] & (
                core.entity_id[rows, entity_slot] == entity_id
            )
            unsupported |= active & ~identity
            active &= identity
            card = working.card_id.gather(1, projectile_slot[:, None])[:, 0]
            position = working.position_units.gather(
                1, projectile_slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            endpoint = working.endpoint_units.gather(
                1, projectile_slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            homing = working.temporary_homing_remaining_ms.gather(
                1, projectile_slot[:, None]
            )[:, 0]
            primary_id = working.primary_target_id.gather(1, projectile_slot[:, None])[
                :, 0
            ]
            cached_target_position = working.primary_target_units.gather(
                1, projectile_slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            target_match = working_runtime.entity_pool.active & (
                core.entity_id == primary_id[:, None]
            )
            target_found = target_match.any(dim=1)
            target_slot = torch.argmax(target_match.to(torch.int64), dim=1)
            temporary = active & (homing > 0)
            live_target_position = torch.stack(
                (
                    core.entity_x_units[rows, target_slot],
                    core.entity_y_units[rows, target_slot],
                ),
                dim=1,
            ).to(torch.int64)
            target_position = torch.where(
                target_found[:, None], live_target_position, cached_target_position
            )
            working.primary_target_units[
                rows[active & target_found], projectile_slot[active & target_found]
            ] = live_target_position[active & target_found]
            temporary_delta = target_position - position
            temporary_ray = normalized_vector_units(
                temporary_delta, self.catalog.range_units[card]
            )
            endpoint = torch.where(
                temporary[:, None], position + temporary_ray, endpoint
            )
            homing = torch.where(temporary, homing - 50, homing)
            index = (rows[active], projectile_slot[active])
            working.endpoint_units[index] = endpoint[active]
            working.temporary_homing_remaining_ms[index] = homing[active]
            delta = endpoint - position
            remaining = integer_sqrt_tensor((delta * delta).sum(dim=1))
            speed = self.catalog.speed_units[card]
            reached = active & (remaining <= speed)
            displacement = normalized_vector_units(
                delta, torch.minimum(remaining, speed)
            )
            next_position = position + displacement
            working.position_units[index] = next_position[active]
            core.entity_x_units[rows[active], entity_slot[active]] = next_position[
                active, 0
            ].to(torch.int32)
            core.entity_y_units[rows[active], entity_slot[active]] = next_position[
                active, 1
            ].to(torch.int32)
            unsupported |= working._apply_sample_damage_(
                working_runtime,
                projectile_slot,
                active,
                self.catalog.radius_units[card],
                damage,
                deaths,
            )
            cleanup[rows[reached], entity_slot[reached]] = True
            working.active[rows[reached], projectile_slot[reached]] = False
            expired[rows[reached], projectile_slot[reached]] = True
        working_runtime.entity_pool.cleanup(cleanup)
        _clear_entity_slots_(working_runtime, cleanup)
        for name in (
            "entity_slot",
            "entity_id",
            "source_id",
            "primary_target_id",
            "primary_target_units",
            "card_id",
            "player_id",
            "position_units",
            "launch_units",
            "endpoint_units",
            "temporary_homing_remaining_ms",
            "hit_entity_ids",
            "hit_count",
        ):
            value = getattr(working, name)
            mask = expired.reshape(
                *expired.shape, *((1,) * (value.ndim - expired.ndim))
            )
            value.masked_fill_(mask, -1 if name == "entity_slot" else 0)
        commit = supported & ~unsupported
        working_runtime.mark_dirty(commit, phase=TickPhase.OBJECTS)
        _copy_runtime_rows_(runtime, working_runtime, commit)
        self._copy_rows_(working, commit)
        return PiercingStepResult(
            committed=~selected | commit,
            capacity_rejected=capacity_rejected,
            expired=expired & commit[:, None],
            damage=torch.where(commit[:, None], damage, 0.0),
            deaths=deaths & commit[:, None],
        )


__all__ = [
    "PiercingLaunchResult",
    "PiercingStepResult",
    "TensorPiercingProjectileCatalog",
    "TensorResidentPiercingProjectiles",
]
