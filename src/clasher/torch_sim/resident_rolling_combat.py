"""Retained tensor lifecycle for serialized rolling combat projectiles.

These payloads are selected by the same serialized triplet as the scalar
runtime: a swept projectile radius, finite projectile range, and directional
pushback.  They are distinct from both homing one-impact projectiles and
vertical rolling spells.  Ordinary ticks retain every mutable plane here and
never step Python entities.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.gamedata_normalization import serialized_hit_planes
from clasher.unit_traits import is_above_ground_surface, is_knockback_immune

from .combat import CombatStepResult, StationaryCombatState
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase

_DIRECTION_SCALE = 1_000_000


def _trunc_div(numerator: torch.Tensor, denominator: torch.Tensor) -> torch.Tensor:
    denominator = denominator.clamp_min(1)
    return torch.sign(numerator) * torch.div(
        numerator.abs(), denominator, rounding_mode="floor"
    )


def _integer_sqrt(value: torch.Tensor) -> torch.Tensor:
    source = value.clamp_min(0).to(torch.int64)
    result = torch.sqrt(source.to(torch.float64)).to(torch.int64)
    result = torch.where((result + 1).square() <= source, result + 1, result)
    return torch.where(result.square() > source, result - 1, result)


def _scaled_direction_norm(dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    """Exact ``isqrt((dx*1e6)^2 + (dy*1e6)^2)`` without int64 overflow."""

    magnitude_sq = dx.square() + dy.square()
    whole = _integer_sqrt(magnitude_sq)
    remainder = magnitude_sq - whole.square()
    low = torch.zeros_like(whole)
    high = torch.full_like(whole, _DIRECTION_SCALE - 1)
    for _ in range(20):
        middle = torch.div(low + high + 1, 2, rounding_mode="floor")
        fits = 2 * whole * _DIRECTION_SCALE * middle + middle.square() <= remainder * (
            _DIRECTION_SCALE * _DIRECTION_SCALE
        )
        low = torch.where(fits, middle, low)
        high = torch.where(fits, high, middle - 1)
    return (whole * _DIRECTION_SCALE + low).clamp_min(1)


def _clear_entity_slots_(
    runtime: TensorBattleRuntime, rows: torch.Tensor, slots: torch.Tensor
) -> None:
    index = (rows, slots)
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == runtime.entity_pool.active.shape
                and not (owner is runtime.battle and descriptor.name == "entity_id")
            ):
                value[index] = 0
    runtime.phases.target_slot[index] = -1
    runtime.battle.entity_tower_slot[index] = -1
    runtime.battle.entity_id.copy_(runtime.entity_pool.entity_id)


def _copy_rows_(destination: object, source: object, rows: torch.Tensor) -> None:
    batch = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and left.ndim and left.shape[0] == batch:
            left[rows] = right[rows]


def _copy_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    for left, right in (
        (destination.battle, source.battle),
        (destination.battle.rng, source.battle.rng),
        (destination.status, source.status),
        (destination.phases, source.phases),
        (destination.events, source.events),
    ):
        _copy_rows_(left, right, rows)
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]


@dataclass(frozen=True)
class TensorRollingCombatCatalog:
    supported: torch.Tensor
    damage: torch.Tensor
    speed_units_per_tick: torch.Tensor
    rolling_radius_units: torch.Tensor
    impact_radius_units: torch.Tensor
    range_units: torch.Tensor
    start_radius_units: torch.Tensor
    pushback_units: torch.Tensor
    pushback_ignores_mass: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    crown_multiplier: torch.Tensor

    @classmethod
    def compile(
        cls, runtime: TensorBattleRuntime, battle: BattleState
    ) -> TensorRollingCombatCatalog:
        size = len(runtime.battle.card_names)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=runtime.device)

        supported = zeros(torch.bool)
        damage = zeros(torch.float64)
        speed = zeros(torch.int64)
        rolling_radius = zeros(torch.int64)
        impact_radius = zeros(torch.int64)
        range_units = zeros(torch.int64)
        start_radius = zeros(torch.int64)
        pushback = zeros(torch.int64)
        ignores_mass = zeros(torch.bool)
        hits_air = zeros(torch.bool)
        hits_ground = zeros(torch.bool)
        crown_multiplier = torch.ones(size, dtype=torch.float64, device=runtime.device)
        for card_id, name in enumerate(runtime.battle.card_names[1:], start=1):
            stats = battle.card_loader.get_card(name)
            if stats is None:
                continue
            operation = getattr(stats, "projectile_data", None)
            if not isinstance(operation, dict):
                continue
            rolling = bool(
                operation.get("projectileRadius")
                and operation.get("projectileRange")
                and operation.get("pushback")
            )
            if not rolling or operation.get("spawnProjectileData"):
                continue
            supported[card_id] = True
            damage[card_id] = float(stats.scaled_damage or stats.damage or 0)
            speed[card_id] = int(operation.get("speed", 0) or 0)
            rolling_radius[card_id] = int(operation.get("projectileRadius", 0) or 0)
            impact_radius[card_id] = int(operation.get("radius", 0) or 0)
            range_units[card_id] = int(operation.get("projectileRange", 0) or 0)
            start_radius[card_id] = round(
                float(getattr(stats, "projectile_start_radius", 0.0) or 0.0) * 1_000
            )
            pushback[card_id] = int(operation.get("pushback", 0) or 0)
            ignores_mass[card_id] = bool(
                operation.get("ignorePushbackResistance", False)
            )
            air, ground = serialized_hit_planes(operation)
            hits_air[card_id] = air
            hits_ground[card_id] = ground
            crown_multiplier[card_id] = max(
                0.0,
                1.0 + float(operation.get("crownTowerDamagePercent", 0) or 0) / 100.0,
            )
        return cls(
            supported,
            damage,
            speed,
            rolling_radius,
            impact_radius,
            range_units,
            start_radius,
            pushback,
            ignores_mass,
            hits_air,
            hits_ground,
            crown_multiplier,
        )


@dataclass
class TensorRollingCombatTargets:
    collision_radius_units: torch.Tensor
    airborne: torch.Tensor
    building: torch.Tensor
    crown: torch.Tensor
    area_receivable: torch.Tensor
    effect_receivable: torch.Tensor
    knockback_receivable: torch.Tensor
    knockback_immune: torch.Tensor
    death_payload_supported: torch.Tensor

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        catalog: TensorRollingCombatCatalog,
    ) -> TensorRollingCombatTargets:
        shape = runtime.battle.entity_id.shape
        size = len(runtime.battle.card_names)
        collision = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        airborne = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        building = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        crown = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        area = torch.ones((size, *shape), dtype=torch.bool, device=runtime.device)
        effect = torch.ones_like(area)
        knockback = torch.ones_like(area)
        immune = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        death_supported = torch.ones(shape, dtype=torch.bool, device=runtime.device)
        rolling_cards = torch.nonzero(catalog.supported).flatten().tolist()
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                collision[row, slot] = round(entity.get_collision_radius() * 1_000)
                airborne[row, slot] = is_above_ground_surface(entity)
                building[row, slot] = isinstance(entity, Building)
                crown[row, slot] = bool(
                    isinstance(entity, Building)
                    and getattr(entity.card_stats, "name", None)
                    in {"Tower", "KingTower"}
                )
                immune[row, slot] = is_knockback_immune(entity.card_stats)
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )
                for card in rolling_cards:
                    source_kind = runtime.battle.card_names[card]
                    area[card, row, slot] = entity.can_receive_area_damage(source_kind)
                    effect[card, row, slot] = entity.can_receive_effect(source_kind)
                    knockback[card, row, slot] = entity.can_receive_forced_movement(
                        source_kind, "knockback"
                    )
        return cls(
            collision,
            airborne,
            building,
            crown,
            area,
            effect,
            knockback,
            immune,
            death_supported,
        )

    def clone(self) -> TensorRollingCombatTargets:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )


@dataclass
class TensorRollingCombatState:
    active: torch.Tensor
    entity_slot: torch.Tensor
    entity_id: torch.Tensor
    source_id: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    direction_x_units: torch.Tensor
    direction_y_units: torch.Tensor
    distance_units: torch.Tensor
    hit_entity_ids: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        hit_capacity: int,
        *,
        device: str | torch.device,
    ) -> TensorRollingCombatState:
        shape = (batch_size, capacity)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=device)

        return cls(
            zeros(torch.bool),
            torch.full(shape, -1, dtype=torch.int64, device=device),
            zeros(torch.int64),
            zeros(torch.int64),
            zeros(torch.int64),
            zeros(torch.int8),
            zeros(torch.int32),
            zeros(torch.int32),
            zeros(torch.int64),
            zeros(torch.int64),
            zeros(torch.int64),
            torch.zeros((*shape, hit_capacity), dtype=torch.int64, device=device),
        )

    def clone(self) -> TensorRollingCombatState:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorRollingCombatState:
        index = torch.as_tensor(rows, dtype=torch.int64, device=self.active.device)
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name)
                .index_select(0, index)
                .clone()
                for descriptor in fields(self)
            }
        )

    def reset_(self, mask: torch.Tensor) -> None:
        selected = torch.as_tensor(mask, dtype=torch.bool, device=self.active.device)
        if selected.shape != self.active.shape:
            raise ValueError("rolling combat reset mask must match [batch, projectile]")
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            expanded = selected.reshape(*selected.shape, *((1,) * (value.ndim - 2)))
            if descriptor.name == "entity_slot":
                value.masked_fill_(expanded, -1)
            else:
                value.masked_fill_(expanded, 0)


@dataclass(frozen=True)
class RollingCombatMaterializeResult:
    committed: torch.Tensor
    selected_count: torch.Tensor


@dataclass(frozen=True)
class RollingCombatStepResult:
    committed: torch.Tensor
    hit: torch.Tensor
    damage: torch.Tensor
    died: torch.Tensor
    knockback: torch.Tensor
    knockback_source_id: torch.Tensor
    knockback_direction_units: torch.Tensor
    knockback_distance_units: torch.Tensor


class TensorResidentRollingCombatProjectiles:
    def __init__(
        self,
        catalog: TensorRollingCombatCatalog,
        state: TensorRollingCombatState,
        targets: TensorRollingCombatTargets,
    ) -> None:
        self.catalog = catalog
        self.state = state
        self.targets = targets

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        capacity: int = 8,
    ) -> TensorResidentRollingCombatProjectiles:
        catalog = TensorRollingCombatCatalog.compile(runtime, battles[0])
        state = TensorRollingCombatState.empty(
            runtime.batch_size,
            capacity,
            runtime.max_entities,
            device=runtime.device,
        )
        targets = TensorRollingCombatTargets.from_battles(runtime, battles, catalog)
        return cls(catalog, state, targets)

    def clone(self) -> TensorResidentRollingCombatProjectiles:
        return type(self)(self.catalog, self.state.clone(), self.targets.clone())

    def fork(
        self, rows: Sequence[int] | torch.Tensor
    ) -> TensorResidentRollingCombatProjectiles:
        index = torch.as_tensor(
            rows, dtype=torch.int64, device=self.state.active.device
        )
        return type(self)(
            self.catalog,
            self.state.fork(index),
            type(self.targets)(
                **{
                    descriptor.name: getattr(self.targets, descriptor.name)
                    .index_select(
                        1 if getattr(self.targets, descriptor.name).ndim == 3 else 0,
                        index,
                    )
                    .clone()
                    for descriptor in fields(self.targets)
                }
            ),
        )

    def materialize_combat_launches_(
        self,
        runtime: TensorBattleRuntime,
        combat: StationaryCombatState,
        result: CombatStepResult,
    ) -> RollingCombatMaterializeResult:
        launch = result.projectile_launched & combat.present & combat.alive
        identity = (
            combat.entity_id[:, :, None] == runtime.battle.entity_id[:, None, :]
        ) & runtime.entity_pool.active[:, None, :]
        found = identity.any(dim=2)
        runtime_slot = identity.to(torch.int64).argmax(dim=2)
        cards = torch.gather(runtime.battle.entity_card, 1, runtime_slot).clamp_min(0)
        selected = launch & found & self.catalog.supported[cards]
        invalid_target = selected & (
            (combat.target_slot < 0) | (combat.target_slot >= combat.max_entities)
        )
        counts = selected.sum(dim=1, dtype=torch.int64)
        capacity_ok = counts <= (~self.state.active).sum(dim=1)
        entity_ok = counts <= (~runtime.entity_pool.active).sum(dim=1)
        event_ok = (
            runtime.events.count.to(torch.int64) + counts <= runtime.events.capacity
        )
        committed = (
            runtime.supported
            & ~invalid_target.any(dim=1)
            & capacity_ok
            & entity_ok
            & event_ok
        )
        working = runtime.clone()
        working.battle.rng = runtime.battle.rng.clone()
        state = self.state.clone()
        effective = selected & committed[:, None]
        counts = effective.sum(dim=1, dtype=torch.int64)
        allocation = working.entity_pool.allocate(counts)
        source_order = torch.argsort(
            torch.where(
                effective,
                combat.entity_id,
                torch.full_like(combat.entity_id, torch.iinfo(torch.int64).max),
            ),
            dim=1,
            stable=True,
        )
        free_order = torch.argsort(
            torch.where(
                ~state.active,
                torch.arange(state.active.shape[1], device=runtime.device)[None, :],
                state.active.shape[1],
            ),
            dim=1,
            stable=True,
        )
        ordinal = torch.arange(allocation.valid.shape[1], device=runtime.device)[
            None, :
        ]
        install = allocation.valid & (ordinal < counts[:, None])
        rows, local = torch.where(install)
        source_slot = source_order[rows, local]
        projectile_slot = free_order[rows, local]
        entity_slot = allocation.slots[rows, local]
        entity_id = allocation.entity_ids[rows, local]
        card = cards[rows, source_slot]
        target_slot = combat.target_slot[rows, source_slot]
        dx = combat.x_units[rows, target_slot] - combat.x_units[rows, source_slot]
        dy = combat.y_units[rows, target_slot] - combat.y_units[rows, source_slot]
        norm = _integer_sqrt(dx.square() + dy.square()).clamp_min(1)
        muzzle_x = combat.x_units[rows, source_slot] + _trunc_div(
            dx * self.catalog.start_radius_units[card], norm
        )
        muzzle_y = combat.y_units[rows, source_slot] + _trunc_div(
            dy * self.catalog.start_radius_units[card], norm
        )
        index = (rows, projectile_slot)
        state.active[index] = True
        state.entity_slot[index] = entity_slot
        state.entity_id[index] = entity_id
        state.source_id[index] = combat.entity_id[rows, source_slot]
        state.card_id[index] = card
        state.player_id[index] = combat.owner[rows, source_slot]
        state.x_units[index] = muzzle_x.to(torch.int32)
        state.y_units[index] = muzzle_y.to(torch.int32)
        state.direction_x_units[index] = dx
        state.direction_y_units[index] = dy
        state.distance_units[index] = 0
        state.hit_entity_ids[index] = 0
        _clear_entity_slots_(working, rows, entity_slot)
        public = (rows, entity_slot)
        working.battle.entity_active[public] = True
        working.battle.entity_kind[public] = 2
        working.battle.entity_player[public] = combat.owner[rows, source_slot]
        working.battle.entity_card[public] = card
        working.battle.entity_x_units[public] = muzzle_x.to(torch.int32)
        working.battle.entity_y_units[public] = muzzle_y.to(torch.int32)
        working.battle.entity_hp[public] = 1.0
        working.battle.entity_hp_integer_kind[public] = True
        working.battle.entity_max_hp[public] = 1.0
        event_source = torch.zeros_like(allocation.entity_ids)
        event_x = torch.zeros_like(allocation.slots, dtype=torch.int32)
        event_y = torch.zeros_like(allocation.slots, dtype=torch.int32)
        event_payload = torch.zeros_like(allocation.entity_ids)
        event_source[rows, local] = combat.entity_id[rows, source_slot]
        event_x[rows, local] = muzzle_x.to(torch.int32)
        event_y[rows, local] = muzzle_y.to(torch.int32)
        event_payload[rows, local] = card
        working.events.append(
            phase=TickPhase.COMBAT,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=allocation.valid,
            source_id=event_source,
            target_id=allocation.entity_ids,
            x_units=event_x,
            y_units=event_y,
            payload=event_payload,
        )
        working.mark_dirty(committed & (counts > 0), phase=TickPhase.COMBAT)
        _copy_runtime_rows_(runtime, working, committed)
        _copy_rows_(self.state, state, committed)
        return RollingCombatMaterializeResult(committed, counts)

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: int | torch.Tensor = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> RollingCombatStepResult:
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=runtime.device)
        )
        if selected.shape != (runtime.batch_size,):
            raise ValueError("rolling combat battle_mask must have shape [batch]")
        dt = torch.as_tensor(dt_ms, dtype=torch.int64, device=runtime.device)
        if dt.ndim == 0:
            dt = dt.expand(runtime.batch_size)
        if dt.shape != (runtime.batch_size,) or bool((dt < 0).any().item()):
            raise ValueError("rolling combat dt_ms must be non-negative [batch]")
        working = runtime.clone()
        working.battle.rng = runtime.battle.rng.clone()
        state = self.state.clone()
        supported = selected.clone()
        hit_total = torch.zeros_like(runtime.battle.entity_active)
        damage_total = torch.zeros_like(runtime.battle.entity_hp)
        died_total = torch.zeros_like(runtime.battle.entity_active)
        knockback = torch.zeros_like(runtime.battle.entity_active)
        knockback_source = torch.zeros_like(runtime.battle.entity_id)
        knockback_direction = torch.zeros(
            (*runtime.battle.entity_id.shape, 2),
            dtype=torch.int64,
            device=runtime.device,
        )
        knockback_distance = torch.zeros_like(runtime.battle.entity_id)
        rows = torch.arange(runtime.batch_size, device=runtime.device)
        order = torch.argsort(
            torch.where(
                state.active,
                state.entity_id,
                torch.full_like(state.entity_id, torch.iinfo(torch.int64).max),
            ),
            dim=1,
            stable=True,
        )
        terminal = torch.zeros_like(state.active)
        for rank in range(state.active.shape[1]):
            projectile_slot = order[:, rank]
            active = state.active.gather(1, projectile_slot[:, None])[:, 0] & supported
            card = state.card_id.gather(1, projectile_slot[:, None])[:, 0].clamp_min(0)
            x = state.x_units.to(torch.int64).gather(1, projectile_slot[:, None])[:, 0]
            y = state.y_units.to(torch.int64).gather(1, projectile_slot[:, None])[:, 0]
            direction_x = state.direction_x_units.gather(1, projectile_slot[:, None])[
                :, 0
            ]
            direction_y = state.direction_y_units.gather(1, projectile_slot[:, None])[
                :, 0
            ]
            distance = state.distance_units.gather(1, projectile_slot[:, None])[:, 0]
            remaining = (self.catalog.range_units[card] - distance).clamp_min(0)
            work = torch.round(
                self.catalog.speed_units_per_tick[card].to(torch.float64)
                * dt.to(torch.float64)
                / 50.0
            ).to(torch.int64)
            move = torch.minimum(work, remaining)
            norm = _scaled_direction_norm(direction_x, direction_y)
            move_x = _trunc_div(direction_x * _DIRECTION_SCALE * move, norm)
            move_y = _trunc_div(direction_y * _DIRECTION_SCALE * move, norm)
            x += torch.where(active, move_x, 0)
            y += torch.where(active, move_y, 0)
            distance += torch.where(active, move, 0)
            state.x_units[rows[active], projectile_slot[active]] = x[active].to(
                torch.int32
            )
            state.y_units[rows[active], projectile_slot[active]] = y[active].to(
                torch.int32
            )
            state.distance_units[rows[active], projectile_slot[active]] = distance[
                active
            ]
            entity_slot = state.entity_slot.gather(1, projectile_slot[:, None])[:, 0]
            working.battle.entity_x_units[rows[active], entity_slot[active]] = x[
                active
            ].to(torch.int32)
            working.battle.entity_y_units[rows[active], entity_slot[active]] = y[
                active
            ].to(torch.int32)
            reached = active & (distance >= self.catalog.range_units[card])
            roller_id = state.entity_id.gather(1, projectile_slot[:, None])[:, 0]
            player = state.player_id.to(torch.int64).gather(
                1, projectile_slot[:, None]
            )[:, 0]
            for sample in range(2):
                radius = (
                    self.catalog.rolling_radius_units[card]
                    if sample == 0
                    else self.catalog.impact_radius_units[card]
                )
                sample_active = (
                    active
                    if sample == 0
                    else active
                    & (
                        reached
                        & (
                            self.catalog.impact_radius_units[card]
                            > self.catalog.rolling_radius_units[card]
                        )
                    )
                )
                target_order = working.entity_pool.id_order()
                target_slots = target_order.slots.clamp_min(0)
                target_ids = target_order.entity_ids
                already = (
                    state.hit_entity_ids[rows, projectile_slot, :, None]
                    == target_ids[:, None, :]
                ).any(dim=1)
                target_x = working.battle.entity_x_units.gather(1, target_slots)
                target_y = working.battle.entity_y_units.gather(1, target_slots)
                target_radius = self.targets.collision_radius_units.gather(
                    1, target_slots
                )
                dx = target_x.to(torch.int64) - x[:, None]
                dy = target_y.to(torch.int64) - y[:, None]
                combined = radius[:, None] + target_radius
                circle = dx.square() + dy.square() < combined.square()
                closest_x = torch.minimum(
                    target_x.to(torch.int64) + target_radius,
                    torch.maximum(target_x.to(torch.int64) - target_radius, x[:, None]),
                )
                closest_y = torch.minimum(
                    target_y.to(torch.int64) + target_radius,
                    torch.maximum(target_y.to(torch.int64) - target_radius, y[:, None]),
                )
                square = (closest_x - x[:, None]).square() + (
                    closest_y - y[:, None]
                ).square() < radius[:, None].square()
                building = self.targets.building.gather(1, target_slots)
                eligible = (
                    sample_active[:, None]
                    & target_order.valid
                    & working.battle.entity_active.gather(1, target_slots)
                    & (
                        working.battle.entity_player.gather(1, target_slots)
                        != player[:, None]
                    )
                    & (working.battle.entity_kind.gather(1, target_slots) < 2)
                    & ~self.targets.airborne.gather(1, target_slots)
                    & ~already
                    & self.targets.area_receivable[
                        card[:, None], rows[:, None], target_slots
                    ]
                    & self.targets.effect_receivable[
                        card[:, None], rows[:, None], target_slots
                    ]
                    & torch.where(building, square, circle)
                )
                unsupported_death = (
                    eligible
                    & (
                        working.battle.entity_hp.gather(1, target_slots)
                        <= self.catalog.damage[card, None]
                    )
                    & ~self.targets.death_payload_supported.gather(1, target_slots)
                )
                supported &= ~unsupported_death.any(dim=1)
                eligible &= supported[:, None]
                target_crown = self.targets.crown.gather(1, target_slots)
                crown_damage = torch.ceil(
                    torch.round(self.catalog.damage[card])[:, None]
                    * torch.round(self.catalog.crown_multiplier[card] * 100)[:, None]
                    / 100.0
                )
                amount = torch.where(
                    target_crown,
                    crown_damage,
                    self.catalog.damage[card, None],
                )
                before = working.battle.entity_hp.gather(1, target_slots)
                after = torch.where(eligible, (before - amount).clamp_min(0.0), before)
                died = eligible & (after <= 0.0)
                additions = eligible.sum(dim=1, dtype=torch.int64) + died.sum(
                    dim=1, dtype=torch.int64
                )
                overflow = supported & (
                    working.events.count.to(torch.int64) + additions
                    > working.events.capacity
                )
                supported &= ~overflow
                eligible &= supported[:, None]
                died &= supported[:, None]
                after = torch.where(eligible, after, before)
                applied = torch.where(eligible, before - after, 0.0)
                event_rows, event_order = torch.where(target_order.valid)
                physical = target_slots[event_rows, event_order]
                index = (event_rows, physical)
                working.battle.entity_hp[index] = after[event_rows, event_order]
                working.battle.entity_hp_integer_kind[index] &= ~(
                    eligible[event_rows, event_order]
                    & (amount[event_rows, event_order] > 0)
                )
                working.battle.entity_active[index] &= ~died[event_rows, event_order]
                working.phases.death_pending[index] |= died[event_rows, event_order]
                hit_total[index] |= eligible[event_rows, event_order]
                damage_total[index] += applied[event_rows, event_order]
                died_total[index] |= died[event_rows, event_order]
                count_before = (state.hit_entity_ids[rows, projectile_slot] > 0).sum(
                    dim=1
                )
                for target_ordinal in range(runtime.max_entities):
                    chosen = eligible[:, target_ordinal]
                    insertion = count_before + eligible[:, :target_ordinal].sum(dim=1)
                    state.hit_entity_ids[
                        rows[chosen], projectile_slot[chosen], insertion[chosen]
                    ] = target_ids[chosen, target_ordinal]
                event_valid = torch.stack((eligible, died), dim=2).flatten(1)
                event_target = torch.stack((target_ids, target_ids), dim=2).flatten(1)
                event_x = torch.stack((target_x, target_x), dim=2).flatten(1)
                event_y = torch.stack((target_y, target_y), dim=2).flatten(1)
                event_amount = torch.stack(
                    (applied, torch.zeros_like(applied)), dim=2
                ).flatten(1)
                event_payload = card[:, None].expand_as(target_ids)
                event_payload = torch.stack(
                    (event_payload, event_payload), dim=2
                ).flatten(1)
                working.events.append(
                    phase=TickPhase.OBJECTS,
                    opcode=torch.stack(
                        (
                            torch.full_like(target_ids, RuntimeEventOpcode.DAMAGE),
                            torch.full_like(target_ids, RuntimeEventOpcode.DEATH),
                        ),
                        dim=2,
                    ).flatten(1),
                    valid=event_valid,
                    source_id=roller_id[:, None],
                    target_id=event_target,
                    x_units=event_x,
                    y_units=event_y,
                    amount=event_amount,
                    payload=event_payload,
                )
                survivors = eligible & ~died
                can_push = (
                    survivors
                    & ~building
                    & self.targets.knockback_receivable[
                        card[:, None], rows[:, None], target_slots
                    ]
                    & (
                        self.catalog.pushback_ignores_mass[card, None]
                        | ~self.targets.knockback_immune.gather(1, target_slots)
                    )
                    & (self.catalog.pushback_units[card, None] > 0)
                    & ((direction_x != 0) | (direction_y != 0))[:, None]
                )
                knockback[index] |= can_push[event_rows, event_order]
                knockback_source[index] = torch.where(
                    can_push[event_rows, event_order],
                    roller_id[event_rows],
                    knockback_source[index],
                )
                knockback_direction[index] = torch.where(
                    can_push[event_rows, event_order, None],
                    torch.stack((direction_x, direction_y), dim=1)[event_rows],
                    knockback_direction[index],
                )
                knockback_distance[index] = torch.where(
                    can_push[event_rows, event_order],
                    self.catalog.pushback_units[card[event_rows]],
                    knockback_distance[index],
                )
            terminal[rows[reached], projectile_slot[reached]] = True
        terminal &= supported[:, None]
        dead_slots = torch.zeros_like(working.entity_pool.active)
        terminal_rows, terminal_projectiles = torch.where(terminal)
        terminal_entities = state.entity_slot[terminal_rows, terminal_projectiles]
        dead_slots[terminal_rows, terminal_entities] = True
        working.entity_pool.cleanup(dead_slots)
        _clear_entity_slots_(working, terminal_rows, terminal_entities)
        state.reset_(terminal)
        working.mark_dirty(
            selected & self.state.active.any(dim=1), phase=TickPhase.OBJECTS
        )
        _copy_runtime_rows_(runtime, working, supported)
        _copy_rows_(self.state, state, supported)
        return RollingCombatStepResult(
            committed=~selected | supported,
            hit=hit_total & supported[:, None],
            damage=torch.where(supported[:, None], damage_total, 0.0),
            died=died_total & supported[:, None],
            knockback=knockback & supported[:, None],
            knockback_source_id=torch.where(supported[:, None], knockback_source, 0),
            knockback_direction_units=torch.where(
                supported[:, None, None], knockback_direction, 0
            ),
            knockback_distance_units=torch.where(
                supported[:, None], knockback_distance, 0
            ),
        )


__all__ = [
    "RollingCombatMaterializeResult",
    "RollingCombatStepResult",
    "TensorResidentRollingCombatProjectiles",
    "TensorRollingCombatCatalog",
    "TensorRollingCombatState",
    "TensorRollingCombatTargets",
]
