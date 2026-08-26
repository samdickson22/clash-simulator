"""Retained tensor lifecycle for launch-and-burst combat projectiles.

Catalog rows are selected by serialized ``AttackRecoil`` plus a projectile
whose impact creates piercing child projectiles.  The runtime retains recoil,
carrier travel, child scatter, one-hit identity sets, and shield/HP scalar
kinds without stepping Python entities or branching on card names.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.kinematics import tiles_to_logic_units
from clasher.logic_math import logic_sin, logic_vector_angle
from clasher.unit_traits import is_airborne_target

from .movement import (
    integer_sqrt_tensor,
    movement_component_vector_units,
    normalized_vector_units,
    trunc_div_tensor,
)
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .special_movement import install_radial_knockback

_SIN_1024 = tuple(logic_sin(angle, 1_024) for angle in range(360))
_ATAN = tuple(logic_vector_angle(128, value) for value in range(129))


@dataclass(frozen=True)
class TensorBurstProjectileCatalog:
    supported: torch.Tensor
    recoil_distance_units: torch.Tensor
    muzzle_radius_units: torch.Tensor
    parent_speed_units: torch.Tensor
    child_count: torch.Tensor
    child_damage: torch.Tensor
    child_damage_integer_kind: torch.Tensor
    child_speed_units: torch.Tensor
    child_range_units: torch.Tensor
    child_radius_units: torch.Tensor
    child_start_extra_radius_units: torch.Tensor
    child_spawn_radius_degrees: torch.Tensor
    child_hits_air: torch.Tensor
    child_hits_ground: torch.Tensor


@dataclass(frozen=True)
class BurstCommitResult:
    committed: torch.Tensor
    accepted: torch.Tensor
    unsupported: torch.Tensor
    capacity_rejected: torch.Tensor
    parent_entity_ids: torch.Tensor
    recoil_started: torch.Tensor


@dataclass(frozen=True)
class BurstStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    parent_impacted: torch.Tensor
    spawned_children: torch.Tensor
    damage: torch.Tensor
    deaths: torch.Tensor
    recoil_active: torch.Tensor


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


def _vector_angle(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    table = torch.tensor(_ATAN, dtype=torch.int64, device=x.device)
    x = x.to(torch.int64)
    y = y.to(torch.int64)
    ax = x.abs()
    ay = y.abs()
    y_over_x = trunc_div_tensor(ay * 128, ax.clamp_min(1)).clamp(0, 128)
    x_over_y = trunc_div_tensor(ax * 128, ay.clamp_min(1)).clamp(0, 128)
    q1 = torch.where(ay < ax, table[y_over_x], 90 - table[x_over_y])
    q2 = torch.where(ax < ay, 90 + table[x_over_y], 180 - table[y_over_x])
    q3 = torch.where(ay < ax, 180 + table[y_over_x], 270 - table[x_over_y])
    q4 = torch.where(ax < ay, 270 + table[x_over_y], 360 - table[y_over_x])
    angle = torch.where(
        (x > 0) & (y >= 0),
        q1,
        torch.where((x <= 0) & (y > 0), q2, torch.where(x < 0, q3, q4)),
    )
    return torch.where((x == 0) & (y == 0), 0, angle % 360)


def _rotate(
    x: torch.Tensor,
    y: torch.Tensor,
    degrees: torch.Tensor,
) -> torch.Tensor:
    sine_table = torch.tensor(_SIN_1024, dtype=torch.int64, device=x.device)
    angle = torch.remainder(degrees.to(torch.int64), 360)
    sine = sine_table[angle]
    cosine = sine_table[torch.remainder(angle + 90, 360)]
    return torch.stack(
        (
            torch.bitwise_right_shift(cosine * x - sine * y, 10),
            torch.bitwise_right_shift(sine * x + cosine * y, 10),
        ),
        dim=-1,
    )


def _serialized_planes(data: dict[str, object]) -> tuple[bool, bool]:
    target = str(data.get("tidTarget", ""))
    if "AIR_AND_GROUND" in target:
        return True, True
    if "AIR" in target:
        return True, False
    if "GROUND" in target:
        return False, True
    return bool(data.get("hitsAir", True)), bool(data.get("hitsGround", True))


@dataclass
class TensorResidentBurstProjectiles:
    catalog: TensorBurstProjectileCatalog
    parent_active: torch.Tensor
    parent_entity_slot: torch.Tensor
    parent_entity_id: torch.Tensor
    parent_source_slot: torch.Tensor
    parent_source_id: torch.Tensor
    parent_target_slot: torch.Tensor
    parent_target_id: torch.Tensor
    parent_card_id: torch.Tensor
    parent_player_id: torch.Tensor
    parent_position_units: torch.Tensor
    parent_launch_units: torch.Tensor
    parent_target_units: torch.Tensor
    child_active: torch.Tensor
    child_entity_slot: torch.Tensor
    child_entity_id: torch.Tensor
    child_source_id: torch.Tensor
    child_card_id: torch.Tensor
    child_player_id: torch.Tensor
    child_position_units: torch.Tensor
    child_launch_units: torch.Tensor
    child_target_units: torch.Tensor
    child_hit_entity_ids: torch.Tensor
    recoil_active: torch.Tensor
    recoil_entity_id: torch.Tensor
    recoil_target_units: torch.Tensor
    recoil_velocity_work: torch.Tensor
    target_area_receivable: torch.Tensor
    target_airborne: torch.Tensor
    target_has_shield: torch.Tensor
    target_shield: torch.Tensor
    target_shield_integer_kind: torch.Tensor
    target_shield_break_count: torch.Tensor
    target_death_payload_supported: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.parent_active.device

    @property
    def batch_size(self) -> int:
        return int(self.parent_active.shape[0])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        parent_capacity: int = 8,
        child_capacity: int = 40,
    ) -> TensorResidentBurstProjectiles:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match burst runtime")
        if parent_capacity < 1 or child_capacity < 1:
            raise ValueError("burst projectile capacities must be positive")
        device = runtime.device
        size = len(runtime.battle.card_names)

        def cards(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = cards(torch.bool)
        recoil = cards(torch.int64)
        muzzle = cards(torch.int64)
        parent_speed = cards(torch.int64)
        count = cards(torch.int64)
        damage = cards(torch.float64)
        damage_kind = cards(torch.bool)
        child_speed = cards(torch.int64)
        child_range = cards(torch.int64)
        child_radius = cards(torch.int64)
        child_extra = cards(torch.int64)
        child_scatter = cards(torch.int64)
        hits_air = cards(torch.bool)
        hits_ground = cards(torch.bool)
        definitions = battles[0].card_loader.load_card_definitions()
        for card_id, name in enumerate(runtime.battle.card_names):
            stats = battles[0].card_loader.get_card(name) if name else None
            definition = definitions.get(name)
            if stats is None or definition is None:
                continue
            has_recoil = any(
                type(mechanic).__name__ == "AttackRecoil"
                for mechanic in definition.mechanics
            )
            parent = stats.projectile_data or {}
            child = parent.get("spawnProjectileData") or {}
            if not has_recoil or not child:
                continue
            child_count = int(child.get("spawnCount", 0) or 0)
            child_distance = int(child.get("projectileRange", 0) or 0)
            child_velocity = int(child.get("speed", 0) or 0)
            if child_count <= 0 or child_distance <= 0 or child_velocity <= 0:
                continue
            scaled_damage = stats.get_scaled_stat(child.get("damage", 0) or 0)
            if scaled_damage is None or float(scaled_damage) <= 0:
                continue
            air, ground = _serialized_planes(child)
            supported[card_id] = True
            recoil[card_id] = tiles_to_logic_units(stats.attack_pushback or 0.0)
            muzzle[card_id] = tiles_to_logic_units(stats.projectile_start_radius or 0.0)
            parent_speed[card_id] = int(parent.get("speed", 0) or 0)
            count[card_id] = child_count
            damage[card_id] = float(scaled_damage)
            # Projectile construction casts the scaled payload through float.
            damage_kind[card_id] = False
            child_speed[card_id] = child_velocity
            child_range[card_id] = child_distance
            child_radius[card_id] = int(
                child.get("projectileRadius", child.get("radius", 0)) or 0
            )
            child_extra[card_id] = int(child.get("projectileStartExtraRadius", 0) or 0)
            child_scatter[card_id] = int(child.get("spawnRadius", 0) or 0)
            hits_air[card_id] = air
            hits_ground[card_id] = ground

        entity_shape = runtime.battle.entity_id.shape
        area = torch.ones(
            (runtime.batch_size, size, runtime.max_entities),
            dtype=torch.bool,
            device=device,
        )
        airborne = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        has_shield = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        shield = torch.zeros(entity_shape, dtype=torch.float64, device=device)
        shield_kind = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        shield_break = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        death_supported = torch.ones(entity_shape, dtype=torch.bool, device=device)
        for row, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                for source_card in torch.nonzero(supported).flatten().tolist():
                    area[row, source_card, slot] = entity.can_receive_area_damage(
                        runtime.battle.card_names[source_card]
                    )
                airborne[row, slot] = is_airborne_target(entity)
                shield_mechanics = [
                    mechanic
                    for mechanic in entity.mechanics
                    if type(mechanic).__name__ == "Shield"
                ]
                if shield_mechanics:
                    current = getattr(shield_mechanics[0], "current_shield", 0)
                    has_shield[row, slot] = True
                    shield[row, slot] = float(current)
                    shield_kind[row, slot] = type(current) is int
                    shield_break[row, slot] = int(
                        getattr(entity, "_shield_break_count", 0)
                    )
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )

        parent_shape = (runtime.batch_size, parent_capacity)
        child_shape = (runtime.batch_size, child_capacity)
        return cls(
            TensorBurstProjectileCatalog(
                supported,
                recoil,
                muzzle,
                parent_speed,
                count,
                damage,
                damage_kind,
                child_speed,
                child_range,
                child_radius,
                child_extra,
                child_scatter,
                hits_air,
                hits_ground,
            ),
            torch.zeros(parent_shape, dtype=torch.bool, device=device),
            torch.full(parent_shape, -1, dtype=torch.int64, device=device),
            torch.zeros(parent_shape, dtype=torch.int64, device=device),
            torch.full(parent_shape, -1, dtype=torch.int64, device=device),
            torch.zeros(parent_shape, dtype=torch.int64, device=device),
            torch.full(parent_shape, -1, dtype=torch.int64, device=device),
            torch.zeros(parent_shape, dtype=torch.int64, device=device),
            torch.zeros(parent_shape, dtype=torch.int64, device=device),
            torch.zeros(parent_shape, dtype=torch.int8, device=device),
            torch.zeros((*parent_shape, 2), dtype=torch.int64, device=device),
            torch.zeros((*parent_shape, 2), dtype=torch.int64, device=device),
            torch.zeros((*parent_shape, 2), dtype=torch.int64, device=device),
            torch.zeros(child_shape, dtype=torch.bool, device=device),
            torch.full(child_shape, -1, dtype=torch.int64, device=device),
            torch.zeros(child_shape, dtype=torch.int64, device=device),
            torch.zeros(child_shape, dtype=torch.int64, device=device),
            torch.zeros(child_shape, dtype=torch.int64, device=device),
            torch.zeros(child_shape, dtype=torch.int8, device=device),
            torch.zeros((*child_shape, 2), dtype=torch.int64, device=device),
            torch.zeros((*child_shape, 2), dtype=torch.int64, device=device),
            torch.zeros((*child_shape, 2), dtype=torch.int64, device=device),
            torch.zeros(
                (*child_shape, runtime.max_entities),
                dtype=torch.int64,
                device=device,
            ),
            torch.zeros(entity_shape, dtype=torch.bool, device=device),
            torch.zeros(entity_shape, dtype=torch.int64, device=device),
            torch.zeros((*entity_shape, 2), dtype=torch.int64, device=device),
            torch.zeros(entity_shape, dtype=torch.int64, device=device),
            area,
            airborne,
            has_shield,
            shield,
            shield_kind,
            shield_break,
            death_supported,
        )

    def clone(self) -> TensorResidentBurstProjectiles:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentBurstProjectiles:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("burst fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentBurstProjectiles,
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
        if selected.shape != destination.shape or source.device != self.device:
            raise ValueError("burst reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(
        self, source: TensorResidentBurstProjectiles, rows: torch.Tensor
    ) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def commit_attacks_(
        self,
        runtime: TensorBattleRuntime,
        *,
        source_slots: torch.Tensor,
        target_slots: torch.Tensor,
        valid: torch.Tensor,
    ) -> BurstCommitResult:
        if not (source_slots.shape == target_slots.shape == valid.shape):
            raise ValueError("burst attack planes must share [batch, lane]")
        if valid.ndim != 2 or valid.shape[0] != self.batch_size:
            raise ValueError("burst attack planes must have shape [batch, lane]")
        if valid.shape[1] > runtime.max_entities:
            raise ValueError("burst attack lane count exceeds entity capacity")
        core = runtime.battle
        source = source_slots.to(self.device, torch.int64).clamp(
            0, runtime.max_entities - 1
        )
        target = target_slots.to(self.device, torch.int64).clamp(
            0, runtime.max_entities - 1
        )
        requested = valid.to(self.device, torch.bool)
        cards = core.entity_card.gather(1, source)
        live = (
            runtime.entity_pool.active.gather(1, source)
            & core.entity_active.gather(1, source)
            & runtime.entity_pool.active.gather(1, target)
            & core.entity_active.gather(1, target)
        )
        eligible = requested & live & self.catalog.supported[cards]
        unsupported_lanes = requested & ~eligible
        unsupported = unsupported_lanes.any(dim=1)
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
        ordered_valid = eligible.gather(1, order)
        ordered_source = source.gather(1, order)
        ordered_target = target.gather(1, order)
        counts = ordered_valid.sum(dim=1, dtype=torch.int64)
        capacity_rejected = ~unsupported & (
            (counts > (~self.parent_active).sum(dim=1))
            | (counts > (~runtime.entity_pool.active).sum(dim=1))
            | (runtime.events.count.to(torch.int64) + counts > runtime.events.capacity)
        )
        accepted_rows = runtime.supported & ~unsupported & ~capacity_rejected
        accepted_lanes = ordered_valid & accepted_rows[:, None]
        accepted_counts = accepted_lanes.sum(dim=1, dtype=torch.int64)
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        allocation = working_runtime.entity_pool.allocate(accepted_counts)
        allocated_mask = torch.zeros_like(working_runtime.entity_pool.active)
        allocated_mask.scatter_(1, allocation.slots.clamp_min(0), allocation.valid)
        _clear_slots_(working_runtime, allocated_mask)
        free_key = torch.where(
            ~working.parent_active,
            torch.arange(working.parent_active.shape[1], device=self.device)[None, :],
            working.parent_active.shape[1],
        )
        parent_slots = torch.sort(free_key, dim=1).values
        rows = torch.arange(self.batch_size, device=self.device)
        recoil_started = torch.zeros_like(valid, dtype=torch.bool)
        # The combat plane is entity-wide while this owner retains only its
        # bounded number of simultaneous parents. Capacity admission above
        # guarantees every requested launch fits, so ranks beyond the owner
        # width are necessarily inactive and need no indexing.
        for rank in range(min(valid.shape[1], self.parent_active.shape[1])):
            selected = accepted_lanes[:, rank]
            source_slot = ordered_source[:, rank]
            target_slot = ordered_target[:, rank]
            parent_slot = parent_slots[:, rank]
            entity_slot = allocation.slots[:, rank].clamp_min(0)
            entity_id = allocation.entity_ids[:, rank]
            card = core.entity_card.gather(1, source_slot[:, None])[:, 0]
            player = core.entity_player.gather(1, source_slot[:, None])[:, 0]
            source_position = torch.stack(
                (
                    core.entity_x_units.gather(1, source_slot[:, None])[:, 0],
                    core.entity_y_units.gather(1, source_slot[:, None])[:, 0],
                ),
                dim=-1,
            ).to(torch.int64)
            target_position = torch.stack(
                (
                    core.entity_x_units.gather(1, target_slot[:, None])[:, 0],
                    core.entity_y_units.gather(1, target_slot[:, None])[:, 0],
                ),
                dim=-1,
            ).to(torch.int64)
            muzzle = source_position + normalized_vector_units(
                target_position - source_position,
                self.catalog.muzzle_radius_units[card],
            )
            index = (rows[selected], parent_slot[selected])
            working.parent_active[index] = True
            working.parent_entity_slot[index] = entity_slot[selected]
            working.parent_entity_id[index] = entity_id[selected]
            working.parent_source_slot[index] = source_slot[selected]
            working.parent_source_id[index] = core.entity_id[
                rows[selected], source_slot[selected]
            ]
            working.parent_target_slot[index] = target_slot[selected]
            working.parent_target_id[index] = core.entity_id[
                rows[selected], target_slot[selected]
            ]
            working.parent_card_id[index] = card[selected]
            working.parent_player_id[index] = player[selected]
            working.parent_position_units[index] = muzzle[selected]
            working.parent_launch_units[index] = muzzle[selected]
            working.parent_target_units[index] = target_position[selected]
            runtime_index = (rows[selected], entity_slot[selected])
            work_core = working_runtime.battle
            work_core.entity_active[runtime_index] = True
            work_core.entity_kind[runtime_index] = 2
            work_core.entity_player[runtime_index] = player[selected]
            work_core.entity_card[runtime_index] = card[selected]
            work_core.entity_x_units[runtime_index] = muzzle[selected, 0].to(
                torch.int32
            )
            work_core.entity_y_units[runtime_index] = muzzle[selected, 1].to(
                torch.int32
            )
            work_core.entity_hp[runtime_index] = 1.0
            work_core.entity_hp_integer_kind[runtime_index] = True
            work_core.entity_max_hp[runtime_index] = 1.0
            working_runtime.phases.target_slot[runtime_index] = target_slot[selected]

            already = working.recoil_active[rows, source_slot]
            identity = (
                working.recoil_entity_id[rows, source_slot]
                == core.entity_id[rows, source_slot]
            )
            can_recoil = selected & (~already | ~identity)
            install = install_radial_knockback(
                source_position,
                target_position,
                self.catalog.recoil_distance_units[card],
                player_id=player.to(torch.int64),
                eligible=can_recoil,
            )
            recoil_index = (rows[install.started], source_slot[install.started])
            working.recoil_active[recoil_index] = True
            working.recoil_entity_id[recoil_index] = core.entity_id[
                rows[install.started], source_slot[install.started]
            ]
            working.recoil_target_units[recoil_index] = install.target_units[
                install.started
            ]
            working.recoil_velocity_work[recoil_index] = install.velocity_work[
                install.started
            ]
            recoil_started[:, rank] = install.started
        working_runtime.events.append(
            phase=TickPhase.COMBAT,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=allocation.valid,
            source_id=working_runtime.battle.entity_id.gather(
                1, allocation.slots.clamp_min(0)
            ),
            target_id=torch.nn.functional.pad(
                core.entity_id.gather(1, ordered_target),
                (0, runtime.max_entities - valid.shape[1]),
            ),
            x_units=working_runtime.battle.entity_x_units.gather(
                1, allocation.slots.clamp_min(0)
            ),
            y_units=working_runtime.battle.entity_y_units.gather(
                1, allocation.slots.clamp_min(0)
            ),
            payload=working_runtime.battle.entity_card.gather(
                1, allocation.slots.clamp_min(0)
            ),
        )
        working_runtime.mark_dirty(accepted_rows, phase=TickPhase.COMBAT)
        _copy_runtime_rows_(runtime, working_runtime, accepted_rows)
        self._copy_rows_(working, accepted_rows)
        return BurstCommitResult(
            committed=~runtime.supported | accepted_rows,
            accepted=accepted_rows & (counts > 0),
            unsupported=unsupported,
            capacity_rejected=capacity_rejected,
            parent_entity_ids=allocation.entity_ids,
            recoil_started=recoil_started,
        )

    def _apply_child_damage_(
        self,
        runtime: TensorBattleRuntime,
        child_slot: torch.Tensor,
        valid_child: torch.Tensor,
        radius_units: torch.Tensor,
        damage_result: torch.Tensor,
        death_result: torch.Tensor,
    ) -> torch.Tensor:
        """Resolve one child lane's ID-ordered sample and return unsupported rows."""

        rows = torch.arange(self.batch_size, device=self.device)
        core = runtime.battle
        player = self.child_player_id.gather(1, child_slot[:, None])[:, 0]
        card = self.child_card_id.gather(1, child_slot[:, None])[:, 0]
        child_id = self.child_entity_id.gather(1, child_slot[:, None])[:, 0]
        position = self.child_position_units.gather(
            1, child_slot[:, None, None].expand(-1, 1, 2)
        )[:, 0]
        catalog_index = runtime.card_catalog_index[core.entity_card].clamp_min(0)
        collision = runtime.catalog.collision_radius_units[catalog_index].to(
            torch.int64
        )
        airborne = self.target_airborne
        dx = core.entity_x_units.to(torch.int64) - position[:, 0, None]
        dy = core.entity_y_units.to(torch.int64) - position[:, 1, None]
        reach = radius_units[:, None] + collision
        previous = self.child_hit_entity_ids.gather(
            1,
            child_slot[:, None, None].expand(-1, 1, runtime.max_entities),
        )[:, 0]
        eligible = (
            valid_child[:, None]
            & runtime.entity_pool.active
            & core.entity_active
            & (core.entity_player != player[:, None])
            & ((core.entity_kind == 0) | (core.entity_kind == 1))
            & self.target_area_receivable[rows, card]
            & torch.where(
                airborne,
                self.catalog.child_hits_air[card, None],
                self.catalog.child_hits_ground[card, None],
            )
            & (previous != core.entity_id)
            & (dx * dx + dy * dy < reach * reach)
        )
        ordered = runtime.entity_pool.id_order(eligible)
        unsupported = torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
        for target_rank in range(runtime.max_entities):
            target_valid = ordered.valid[:, target_rank]
            target_slot = ordered.slots[:, target_rank].clamp_min(0)
            target_id = ordered.entity_ids[:, target_rank]
            amount = self.catalog.child_damage[card]
            absorbs = (
                target_valid
                & self.target_has_shield[rows, target_slot]
                & (self.target_shield[rows, target_slot] > 0)
            )
            shield_index = (rows[absorbs], target_slot[absorbs])
            next_shield = torch.clamp(
                self.target_shield[rows, target_slot] - amount,
                min=0.0,
            )
            broken = absorbs & (next_shield <= 0)
            self.target_shield[shield_index] = next_shield[absorbs]
            self.target_shield_integer_kind[shield_index] = False
            self.target_shield_break_count[rows[broken], target_slot[broken]] += 1
            hp_hit = target_valid & ~absorbs
            hp_index = (rows[hp_hit], target_slot[hp_hit])
            old_hp = core.entity_hp[rows, target_slot]
            hp_damage = torch.minimum(old_hp, amount)
            new_hp = torch.clamp(old_hp - amount, min=0.0)
            core.entity_hp[hp_index] = new_hp[hp_hit]
            core.entity_hp_integer_kind[hp_index] = False
            killed = hp_hit & (new_hp <= 0)
            core.entity_active[rows[killed], target_slot[killed]] = False
            damage_result[hp_index] += hp_damage[hp_hit]
            death_result[rows[killed], target_slot[killed]] = True
            self.child_hit_entity_ids[
                rows[target_valid], child_slot[target_valid], target_slot[target_valid]
            ] = target_id[target_valid]
            runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.DAMAGE,
                valid=target_valid[:, None],
                source_id=child_id[:, None],
                target_id=target_id[:, None],
                x_units=core.entity_x_units[rows, target_slot][:, None],
                y_units=core.entity_y_units[rows, target_slot][:, None],
                amount=torch.where(hp_hit, hp_damage, 0.0)[:, None],
                payload=card[:, None],
            )
            runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.DEATH,
                valid=killed[:, None],
                source_id=child_id[:, None],
                target_id=target_id[:, None],
                x_units=core.entity_x_units[rows, target_slot][:, None],
                y_units=core.entity_y_units[rows, target_slot][:, None],
                payload=card[:, None],
            )
            unsupported |= (
                killed & ~self.target_death_payload_supported[rows, target_slot]
            )
        return unsupported

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> BurstStepResult:
        if dt_ms < 0 or dt_ms % 50:
            raise ValueError("burst dt_ms must be a non-negative 50ms multiple")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("burst battle_mask must have shape [batch]")
        ticks = dt_ms // 50
        if ticks != 1:
            raise ValueError(
                "retained burst lifecycle currently requires one logic tick"
            )
        parent_delta = self.parent_target_units - self.parent_position_units
        parent_remaining = integer_sqrt_tensor(
            (parent_delta * parent_delta).sum(dim=-1)
        )
        parent_speed = self.catalog.parent_speed_units[self.parent_card_id.clamp_min(0)]
        parent_due = (
            self.parent_active & selected[:, None] & (parent_remaining <= parent_speed)
        )
        child_needed = (
            parent_due.to(torch.int64)
            * self.catalog.child_count[self.parent_card_id.clamp_min(0)]
        ).sum(dim=1)
        maximum_hit_events = (
            (self.child_active.sum(dim=1, dtype=torch.int64) + child_needed)
            * runtime.max_entities
            * 2
        )
        free_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = selected & (
            (child_needed > (~self.child_active).sum(dim=1))
            | (child_needed > (~runtime.entity_pool.active).sum(dim=1))
            | (child_needed + maximum_hit_events > free_events)
        )
        supported = selected & ~capacity_rejected
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        rows = torch.arange(self.batch_size, device=self.device)
        core = working_runtime.battle
        damage = torch.zeros_like(core.entity_hp)
        deaths = torch.zeros_like(core.entity_active)
        spawned = torch.zeros(self.batch_size, dtype=torch.int64, device=self.device)
        impacted = torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
        unsupported = torch.zeros_like(supported)

        identity = (
            (working.recoil_entity_id == core.entity_id)
            & working_runtime.entity_pool.active
            & core.entity_active
        )
        working.recoil_active &= identity
        moving = working.recoil_active & supported[:, None]
        next_velocity = working.recoil_velocity_work - 25
        delta = working.recoil_target_units - torch.stack(
            (core.entity_x_units, core.entity_y_units), dim=-1
        ).to(torch.int64)
        remaining = integer_sqrt_tensor((delta * delta).sum(dim=-1))
        movement = torch.minimum(torch.clamp(next_velocity, min=0, max=250), remaining)
        displacement = movement_component_vector_units(delta, movement)
        moved = torch.stack((core.entity_x_units, core.entity_y_units), dim=-1).to(
            torch.int64
        ) + torch.where(moving[..., None], displacement, 0)
        core.entity_x_units.copy_(moved[..., 0].to(torch.int32))
        core.entity_y_units.copy_(moved[..., 1].to(torch.int32))
        working.recoil_velocity_work.copy_(
            torch.where(
                moving, torch.clamp(next_velocity, min=0), working.recoil_velocity_work
            )
        )
        recoil_finished = moving & (next_velocity < 0)
        working.recoil_active &= ~recoil_finished
        working.recoil_entity_id.masked_fill_(recoil_finished, 0)
        working.recoil_target_units.masked_fill_(recoil_finished[..., None], 0)

        children_at_start = working.child_active.clone()
        parent_order = torch.argsort(
            torch.where(
                working.parent_active,
                working.parent_entity_id,
                torch.iinfo(torch.int64).max,
            ),
            dim=1,
            stable=True,
        )
        parent_cleanup = torch.zeros_like(working_runtime.entity_pool.active)
        for rank in range(working.parent_active.shape[1]):
            slot = parent_order[:, rank]
            active = working.parent_active.gather(1, slot[:, None])[:, 0] & supported
            position = working.parent_position_units.gather(
                1, slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            endpoint = working.parent_target_units.gather(
                1, slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            card = working.parent_card_id.gather(1, slot[:, None])[:, 0]
            player = working.parent_player_id.gather(1, slot[:, None])[:, 0]
            entity_slot = working.parent_entity_slot.gather(1, slot[:, None])[
                :, 0
            ].clamp_min(0)
            delta = endpoint - position
            remaining = integer_sqrt_tensor((delta * delta).sum(dim=-1))
            speed = self.catalog.parent_speed_units[card]
            due = active & (remaining <= speed)
            move = normalized_vector_units(delta, torch.minimum(remaining, speed))
            next_position = torch.where(due[:, None], endpoint, position + move)
            working.parent_position_units[rows[active], slot[active]] = next_position[
                active
            ]
            core.entity_x_units[rows[active], entity_slot[active]] = next_position[
                active, 0
            ].to(torch.int32)
            core.entity_y_units[rows[active], entity_slot[active]] = next_position[
                active, 1
            ].to(torch.int32)
            counts = due.to(torch.int64) * self.catalog.child_count[card]
            allocation = working_runtime.entity_pool.allocate(counts)
            allocated_mask = torch.zeros_like(working_runtime.entity_pool.active)
            allocated_mask.scatter_(1, allocation.slots.clamp_min(0), allocation.valid)
            _clear_slots_(working_runtime, allocated_mask)
            free_key = torch.where(
                ~working.child_active,
                torch.arange(working.child_active.shape[1], device=self.device)[
                    None, :
                ],
                working.child_active.shape[1],
            )
            child_slots = torch.sort(free_key, dim=1).values
            parent_launch = working.parent_launch_units.gather(
                1, slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            base_angle = _vector_angle(
                endpoint[:, 0] - parent_launch[:, 0],
                endpoint[:, 1] - parent_launch[:, 1],
            )
            child_count = self.catalog.child_count[card]
            for child_index in range(
                min(allocation.valid.shape[1], working.child_active.shape[1])
            ):
                child_valid = allocation.valid[:, child_index]
                child_slot = child_slots[:, child_index].clamp_max(
                    working.child_active.shape[1] - 1
                )
                child_entity_slot = allocation.slots[:, child_index].clamp_min(0)
                offset = trunc_div_tensor(
                    (child_index - torch.div(child_count, 2, rounding_mode="floor"))
                    * self.catalog.child_spawn_radius_degrees[card],
                    child_count.clamp_min(1),
                )
                ray = _rotate(
                    self.catalog.child_range_units[card],
                    torch.zeros_like(card),
                    base_angle + offset,
                )
                child_endpoint = endpoint + ray
                child_owner_index = (rows[child_valid], child_slot[child_valid])
                working.child_active[child_owner_index] = True
                working.child_entity_slot[child_owner_index] = child_entity_slot[
                    child_valid
                ]
                working.child_entity_id[child_owner_index] = allocation.entity_ids[
                    child_valid, child_index
                ]
                working.child_source_id[child_owner_index] = working.parent_source_id[
                    rows[child_valid], slot[child_valid]
                ]
                working.child_card_id[child_owner_index] = card[child_valid]
                working.child_player_id[child_owner_index] = player[child_valid]
                working.child_position_units[child_owner_index] = endpoint[child_valid]
                working.child_launch_units[child_owner_index] = endpoint[child_valid]
                working.child_target_units[child_owner_index] = child_endpoint[
                    child_valid
                ]
                runtime_index = (rows[child_valid], child_entity_slot[child_valid])
                core.entity_active[runtime_index] = True
                core.entity_kind[runtime_index] = 2
                core.entity_player[runtime_index] = player[child_valid]
                core.entity_card[runtime_index] = card[child_valid]
                core.entity_x_units[runtime_index] = endpoint[child_valid, 0].to(
                    torch.int32
                )
                core.entity_y_units[runtime_index] = endpoint[child_valid, 1].to(
                    torch.int32
                )
                core.entity_hp[runtime_index] = 1.0
                core.entity_hp_integer_kind[runtime_index] = True
                core.entity_max_hp[runtime_index] = 1.0
                working_runtime.phases.target_slot[runtime_index] = -1
                working_runtime.events.append(
                    phase=TickPhase.OBJECTS,
                    opcode=RuntimeEventOpcode.SPAWN,
                    valid=child_valid[:, None],
                    source_id=allocation.entity_ids[:, child_index, None],
                    x_units=endpoint[:, 0, None],
                    y_units=endpoint[:, 1, None],
                    payload=card[:, None],
                )
                start_radius = (
                    self.catalog.child_radius_units[card]
                    + self.catalog.child_start_extra_radius_units[card]
                )
                unsupported |= working._apply_child_damage_(
                    working_runtime,
                    child_slot,
                    child_valid,
                    start_radius,
                    damage,
                    deaths,
                )
            spawned += counts
            impacted |= due
            parent_cleanup[rows[due], entity_slot[due]] = True
            working.parent_active[rows[due], slot[due]] = False

        child_order = torch.argsort(
            torch.where(
                children_at_start,
                working.child_entity_id,
                torch.iinfo(torch.int64).max,
            ),
            dim=1,
            stable=True,
        )
        child_cleanup = torch.zeros_like(working_runtime.entity_pool.active)
        for rank in range(working.child_active.shape[1]):
            slot = child_order[:, rank]
            active = children_at_start.gather(1, slot[:, None])[:, 0] & supported
            position = working.child_position_units.gather(
                1, slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            endpoint = working.child_target_units.gather(
                1, slot[:, None, None].expand(-1, 1, 2)
            )[:, 0]
            card = working.child_card_id.gather(1, slot[:, None])[:, 0]
            entity_slot = working.child_entity_slot.gather(1, slot[:, None])[
                :, 0
            ].clamp_min(0)
            delta = endpoint - position
            remaining = integer_sqrt_tensor((delta * delta).sum(dim=-1))
            speed = self.catalog.child_speed_units[card]
            reached = active & (remaining <= speed)
            displacement = normalized_vector_units(
                delta, torch.minimum(remaining, speed)
            )
            next_position = position + displacement
            working.child_position_units[rows[active], slot[active]] = next_position[
                active
            ]
            core.entity_x_units[rows[active], entity_slot[active]] = next_position[
                active, 0
            ].to(torch.int32)
            core.entity_y_units[rows[active], entity_slot[active]] = next_position[
                active, 1
            ].to(torch.int32)
            unsupported |= working._apply_child_damage_(
                working_runtime,
                slot,
                active,
                self.catalog.child_radius_units[card],
                damage,
                deaths,
            )
            child_cleanup[rows[reached], entity_slot[reached]] = True
            working.child_active[rows[reached], slot[reached]] = False

        projectile_cleanup = parent_cleanup | child_cleanup
        working_runtime.entity_pool.cleanup(projectile_cleanup)
        _clear_slots_(working_runtime, projectile_cleanup)
        commit = supported & ~unsupported
        working_runtime.mark_dirty(commit, phase=TickPhase.OBJECTS)
        _copy_runtime_rows_(runtime, working_runtime, commit)
        self._copy_rows_(working, commit)
        return BurstStepResult(
            committed=~selected | commit,
            capacity_rejected=capacity_rejected,
            parent_impacted=impacted & commit,
            spawned_children=torch.where(commit, spawned, 0),
            damage=torch.where(commit[:, None], damage, 0.0),
            deaths=deaths & commit[:, None],
            recoil_active=self.recoil_active.clone(),
        )


__all__ = [
    "BurstCommitResult",
    "BurstStepResult",
    "TensorBurstProjectileCatalog",
    "TensorResidentBurstProjectiles",
]
