"""Retained tensor lifecycle for serialized projectile-backed demolition troops."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.cards.wallbreakers import WallBreakersDemolition
from clasher.gamedata_normalization import serialized_hit_planes

from .movement import (
    integer_sqrt_tensor,
    movement_component_vector_units,
    normalized_vector_units,
)
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorDemolitionCatalog:
    supported: torch.Tensor
    deployment_count: torch.Tensor
    deployment_radius_units: torch.Tensor
    deployment_delay_ms: torch.Tensor
    speed_units: torch.Tensor
    sight_range_units: torch.Tensor
    attack_range_units: torch.Tensor
    damage: torch.Tensor
    projectile_range_units: torch.Tensor
    projectile_speed_units: torch.Tensor
    splash_radius_units: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    prime_delay_ms: torch.Tensor


@dataclass(frozen=True)
class DemolitionStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    acquired_target_id: torch.Tensor
    moved: torch.Tensor
    primed: torch.Tensor
    detonated: torch.Tensor
    projectile_entity_ids: torch.Tensor
    damage: torch.Tensor
    deaths: torch.Tensor


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


@dataclass
class TensorResidentDemolition:
    catalog: TensorDemolitionCatalog
    tracked_entity_id: torch.Tensor
    target_slot: torch.Tensor
    target_entity_id: torch.Tensor
    attack_cooldown: torch.Tensor
    primed: torch.Tensor
    prime_remaining_ms: torch.Tensor
    triggered: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_airborne: torch.Tensor
    target_damage_receivable: torch.Tensor
    target_death_payload_supported: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.tracked_entity_id.device

    @property
    def batch_size(self) -> int:
        return int(self.tracked_entity_id.shape[0])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorResidentDemolition:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match demolition runtime")
        device = runtime.device
        size = len(runtime.battle.card_names)

        def card_plane(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = card_plane(torch.bool)
        count = card_plane(torch.int64)
        formation_radius = card_plane(torch.int64)
        deploy_delay = card_plane(torch.int64)
        speed = card_plane(torch.int64)
        sight = card_plane(torch.int64)
        attack_range = card_plane(torch.int64)
        damage = card_plane(torch.float64)
        projectile_range = card_plane(torch.int64)
        projectile_speed = card_plane(torch.int64)
        splash = card_plane(torch.int64)
        hits_air = card_plane(torch.bool)
        hits_ground = card_plane(torch.bool)
        prime_delay = card_plane(torch.int64)
        definitions = battles[0].card_loader.load_card_definitions()
        for card_id, name in enumerate(runtime.battle.card_names):
            stats = battles[0].card_loader.get_card(name) if name else None
            definition = definitions.get(name)
            if stats is None or definition is None:
                continue
            mechanics = [
                mechanic
                for mechanic in definition.mechanics
                if isinstance(mechanic, WallBreakersDemolition)
            ]
            projectile = stats.projectile_data or {}
            if len(mechanics) != 1 or not projectile:
                continue
            air, ground = serialized_hit_planes(projectile)
            raw = getattr(stats, "_raw_entry", {}) or {}
            supported[card_id] = True
            count[card_id] = int(raw.get("summonNumber", 1) or 1)
            formation_radius[card_id] = int(raw.get("summonRadius", 0) or 0)
            deploy_delay[card_id] = int(raw.get("summonDeployDelay", 0) or 0)
            speed[card_id] = round(float(stats.speed or 0))
            sight[card_id] = round(float(stats.sight_range or 0) * 1_000)
            attack_range[card_id] = round(float(stats.range or 0) * 1_000)
            damage[card_id] = float(stats.scaled_damage or stats.damage or 0)
            projectile_range[card_id] = int(projectile.get("projectileRange", 0) or 0)
            projectile_speed[card_id] = int(projectile.get("speed", 0) or 0)
            splash[card_id] = int(
                projectile.get("radius", getattr(stats, "area_damage_radius", 0)) or 0
            )
            hits_air[card_id] = air
            hits_ground[card_id] = ground
            character = raw.get("summonCharacterData", {}) or {}
            prime_delay[card_id] = int(character.get("kamikazeTime", 0) or 0)

        entity_shape = runtime.battle.entity_id.shape
        collision = torch.zeros(entity_shape, dtype=torch.int64, device=device)
        airborne = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        receivable = torch.ones(
            (runtime.batch_size, size, runtime.max_entities),
            dtype=torch.bool,
            device=device,
        )
        death_supported = torch.ones(entity_shape, dtype=torch.bool, device=device)
        cooldown = torch.zeros(entity_shape, dtype=torch.float64, device=device)
        supported_cards = torch.nonzero(supported).flatten().tolist()
        for row, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                cooldown[row, slot] = float(getattr(entity, "attack_cooldown", 0.0))
                collision[row, slot] = round(entity.get_collision_radius() * 1_000)
                airborne[row, slot] = bool(getattr(entity, "is_air_unit", False))
                for source_card in supported_cards:
                    receivable[row, source_card, slot] = entity.can_receive_area_damage(
                        runtime.battle.card_names[source_card]
                    )
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )

        core = runtime.battle
        cards = core.entity_card.clamp(0, size - 1)
        tracked = torch.where(
            runtime.entity_pool.active & core.entity_active & supported[cards],
            core.entity_id,
            0,
        )
        return cls(
            TensorDemolitionCatalog(
                supported,
                count,
                formation_radius,
                deploy_delay,
                speed,
                sight,
                attack_range,
                damage,
                projectile_range,
                projectile_speed,
                splash,
                hits_air,
                hits_ground,
                prime_delay,
            ),
            tracked,
            torch.full(entity_shape, -1, dtype=torch.int64, device=device),
            torch.zeros(entity_shape, dtype=torch.int64, device=device),
            cooldown,
            torch.zeros(entity_shape, dtype=torch.bool, device=device),
            torch.zeros(entity_shape, dtype=torch.int64, device=device),
            torch.zeros(entity_shape, dtype=torch.bool, device=device),
            collision,
            airborne,
            receivable,
            death_supported,
        )

    def clone(self) -> TensorResidentDemolition:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentDemolition:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("demolition fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentDemolition,
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
            raise ValueError("demolition reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(self, source: TensorResidentDemolition, rows: torch.Tensor) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        waypoint_units: torch.Tensor | None = None,
        waypoint_valid: torch.Tensor | None = None,
        entity_actionable: torch.Tensor | None = None,
        dt_ms: int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> DemolitionStepResult:
        if dt_ms != 50:
            raise ValueError("demolition runtime requires one 50ms logic tick")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("demolition battle_mask must have shape [batch]")
        shape = runtime.battle.entity_id.shape
        waypoints = (
            torch.zeros((*shape, 2), dtype=torch.int64, device=self.device)
            if waypoint_units is None
            else torch.as_tensor(waypoint_units, dtype=torch.int64, device=self.device)
        )
        waypoint_mask = (
            torch.zeros(shape, dtype=torch.bool, device=self.device)
            if waypoint_valid is None
            else torch.as_tensor(waypoint_valid, dtype=torch.bool, device=self.device)
        )
        if waypoints.shape != (*shape, 2) or waypoint_mask.shape != shape:
            raise ValueError("demolition waypoint planes differ from entity layout")
        entity_mask = (
            torch.ones(shape, dtype=torch.bool, device=self.device)
            if entity_actionable is None
            else torch.as_tensor(
                entity_actionable, dtype=torch.bool, device=self.device
            )
        )
        if entity_mask.shape != shape:
            raise ValueError("demolition entity_actionable must match entity layout")
        capacity_rejected = torch.zeros_like(selected)
        supported = selected.clone()
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        core = working_runtime.battle
        rows = torch.arange(self.batch_size, device=self.device)
        cards = core.entity_card.clamp(0, len(self.catalog.supported) - 1)
        live = (
            working_runtime.entity_pool.active
            & core.entity_active
            & working.catalog.supported[cards]
        )
        deployed = (core.entity_deploy_delay <= 1e-9) & (
            ~core.entity_placement_pending
        )
        identity = working.tracked_entity_id == core.entity_id
        stale = (working.tracked_entity_id > 0) & ~(live & identity)
        new = live & ((working.tracked_entity_id == 0) | ~identity)
        working.tracked_entity_id.masked_fill_(stale, 0)
        working.target_slot.masked_fill_(stale, -1)
        working.target_entity_id.masked_fill_(stale, 0)
        working.attack_cooldown.masked_fill_(stale, 0.0)
        working.primed.masked_fill_(stale, False)
        working.prime_remaining_ms.masked_fill_(stale, 0)
        working.triggered.masked_fill_(stale, False)
        working.tracked_entity_id.copy_(
            torch.where(new, core.entity_id, working.tracked_entity_id)
        )
        actionable = live & deployed & entity_mask & supported[:, None]
        working.attack_cooldown.copy_(
            torch.where(
                actionable,
                torch.clamp(working.attack_cooldown - dt_ms / 1_000.0, min=0.0),
                working.attack_cooldown,
            )
        )
        # Deployment clocks are advanced by the engine's shared character
        # object phase.  This owner must still remain inert until that phase
        # makes a bomber actionable: direct owner use and future phase-order
        # refactors must never let a deploying Wall Breaker acquire, move, or
        # detonate early.
        order = working_runtime.entity_pool.id_order(actionable)
        moved = torch.zeros_like(core.entity_active)
        primed_now = torch.zeros_like(core.entity_active)
        detonated = torch.zeros_like(core.entity_active)
        damage_result = torch.zeros_like(core.entity_hp)
        death_result = torch.zeros_like(core.entity_active)
        unsupported_rows = torch.zeros_like(supported)
        commit_mask = torch.zeros_like(core.entity_active)
        commit_target = torch.zeros_like(core.entity_id)
        projectile_endpoint = torch.zeros(
            (*shape, 2), dtype=torch.int64, device=self.device
        )
        for rank in range(runtime.max_entities):
            valid_carrier = order.valid[:, rank]
            source_slot = order.slots[:, rank].clamp_min(0)
            card = cards.gather(1, source_slot[:, None])[:, 0]
            player = core.entity_player.gather(1, source_slot[:, None])[:, 0]
            source_x = core.entity_x_units[rows, source_slot].to(torch.int64)
            source_y = core.entity_y_units[rows, source_slot].to(torch.int64)
            dx = core.entity_x_units.to(torch.int64) - source_x[:, None]
            dy = core.entity_y_units.to(torch.int64) - source_y[:, None]
            distance_sq = dx * dx + dy * dy
            target_catalog = working_runtime.card_catalog_index[
                core.entity_card
            ].clamp_min(0)
            target_radius = working_runtime.catalog.collision_radius_units[
                target_catalog
            ].to(torch.int64)
            candidates = (
                working_runtime.entity_pool.active
                & core.entity_active
                & (core.entity_player != player[:, None])
                & (core.entity_kind == 1)
                & (
                    distance_sq
                    <= (working.catalog.sight_range_units[card, None] + target_radius)
                    ** 2
                )
            )
            key = torch.where(
                candidates,
                distance_sq * (core.entity_id.amax().clamp_min(1) + 1) + core.entity_id,
                torch.iinfo(torch.int64).max,
            )
            acquired = key.argmin(dim=1)
            retained = working.target_slot[rows, source_slot]
            retained_safe = retained.clamp(0, runtime.max_entities - 1)
            retained_valid = (
                (retained >= 0)
                & working_runtime.entity_pool.active[rows, retained_safe]
                & core.entity_active[rows, retained_safe]
                & (
                    core.entity_id[rows, retained_safe]
                    == working.target_entity_id[rows, source_slot]
                )
                & (core.entity_kind[rows, retained_safe] == 1)
            )
            target_slot = torch.where(retained_valid, retained_safe, acquired)
            target_valid = valid_carrier & (retained_valid | candidates.any(dim=1))
            working.target_slot[rows[target_valid], source_slot[target_valid]] = (
                target_slot[target_valid]
            )
            working.target_entity_id[rows[target_valid], source_slot[target_valid]] = (
                core.entity_id[rows[target_valid], target_slot[target_valid]]
            )
            target_position = torch.stack(
                (
                    core.entity_x_units[rows, target_slot],
                    core.entity_y_units[rows, target_slot],
                ),
                dim=-1,
            ).to(torch.int64)
            source_position = torch.stack((source_x, source_y), dim=-1)
            delta = target_position - source_position
            distance = integer_sqrt_tensor((delta * delta).sum(dim=-1))
            reach = (
                working.catalog.attack_range_units[card]
                + target_radius[rows, target_slot]
            )
            in_reach = target_valid & (distance <= reach)
            ready = working.attack_cooldown[rows, source_slot] <= 1e-9
            prime = in_reach & ready & ~working.primed[rows, source_slot]
            working.primed[rows[prime], source_slot[prime]] = True
            working.prime_remaining_ms[rows[prime], source_slot[prime]] = (
                working.catalog.prime_delay_ms[card[prime]]
            )
            primed_now[rows[prime], source_slot[prime]] = True
            ticking = in_reach & working.primed[rows, source_slot] & ~prime
            remaining = working.prime_remaining_ms[rows, source_slot] - dt_ms
            working.prime_remaining_ms[rows[ticking], source_slot[ticking]] = remaining[
                ticking
            ].clamp_min(0)
            fire = (
                (prime & (working.catalog.prime_delay_ms[card] == 0))
                | (ticking & (remaining <= 0))
            ) & ~working.triggered[rows, source_slot]
            working.triggered[rows[fire], source_slot[fire]] = True
            commit_mask[rows[fire], source_slot[fire]] = True
            commit_target[rows[fire], source_slot[fire]] = target_slot[fire]
            endpoint = source_position + normalized_vector_units(
                delta, working.catalog.projectile_range_units[card]
            )
            projectile_endpoint[rows[fire], source_slot[fire]] = endpoint[fire]
            can_move = target_valid & ~in_reach & waypoint_mask[rows, source_slot]
            movement_delta = waypoints[rows, source_slot] - source_position
            movement_distance = integer_sqrt_tensor(
                (movement_delta * movement_delta).sum(dim=-1)
            )
            work = torch.minimum(working.catalog.speed_units[card], movement_distance)
            displacement = movement_component_vector_units(movement_delta, work)
            core.entity_x_units[rows[can_move], source_slot[can_move]] += displacement[
                can_move, 0
            ].to(torch.int32)
            core.entity_y_units[rows[can_move], source_slot[can_move]] += displacement[
                can_move, 1
            ].to(torch.int32)
            moved[rows[can_move], source_slot[can_move]] = True

        counts = commit_mask.sum(dim=1, dtype=torch.int64)
        free_entities = (~runtime.entity_pool.active).sum(dim=1, dtype=torch.int64)
        free_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = selected & (
            (counts > free_entities)
            | (counts * (2 + runtime.max_entities * 2) > free_events)
        )
        supported &= ~capacity_rejected
        commit_mask &= supported[:, None]
        counts = commit_mask.sum(dim=1, dtype=torch.int64)
        allocation = working_runtime.entity_pool.allocate(counts)
        allocated_mask = torch.zeros_like(working_runtime.entity_pool.active)
        allocated_mask.scatter_(1, allocation.slots.clamp_min(0), allocation.valid)
        _clear_slots_(working_runtime, allocated_mask)
        committed_sources = working_runtime.entity_pool.id_order(commit_mask)
        projectile_ids_by_source = torch.zeros_like(core.entity_id)
        projectile_cleanup = torch.zeros_like(working_runtime.entity_pool.active)
        for rank in range(runtime.max_entities):
            valid_projectile = allocation.valid[:, rank]
            source_slot = committed_sources.slots[:, rank].clamp_min(0)
            projectile_slot = allocation.slots[:, rank].clamp_min(0)
            projectile_id = allocation.entity_ids[:, rank]
            card = cards[rows, source_slot]
            player = core.entity_player[rows, source_slot]
            endpoint = projectile_endpoint[rows, source_slot]
            projectile_ids_by_source[
                rows[valid_projectile], source_slot[valid_projectile]
            ] = projectile_id[valid_projectile]
            runtime_index = (rows[valid_projectile], projectile_slot[valid_projectile])
            core.entity_active[runtime_index] = True
            core.entity_kind[runtime_index] = 2
            core.entity_player[runtime_index] = player[valid_projectile]
            core.entity_card[runtime_index] = card[valid_projectile]
            core.entity_x_units[runtime_index] = endpoint[valid_projectile, 0].to(
                torch.int32
            )
            core.entity_y_units[runtime_index] = endpoint[valid_projectile, 1].to(
                torch.int32
            )
            core.entity_hp[runtime_index] = 1.0
            core.entity_hp_integer_kind[runtime_index] = True
            core.entity_max_hp[runtime_index] = 1.0
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.SPAWN,
                valid=valid_projectile[:, None],
                source_id=projectile_id[:, None],
                target_id=core.entity_id[rows, commit_target[rows, source_slot]][
                    :, None
                ],
                x_units=endpoint[:, 0, None],
                y_units=endpoint[:, 1, None],
                payload=card[:, None],
            )
            core.entity_hp[rows[valid_projectile], source_slot[valid_projectile]] = 0.0
            core.entity_hp_integer_kind[
                rows[valid_projectile], source_slot[valid_projectile]
            ] = False
            core.entity_active[
                rows[valid_projectile], source_slot[valid_projectile]
            ] = False
            working_runtime.phases.death_pending[
                rows[valid_projectile], source_slot[valid_projectile]
            ] = True
            detonated[rows[valid_projectile], source_slot[valid_projectile]] = True
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.DEATH,
                valid=valid_projectile[:, None],
                source_id=core.entity_id[rows, source_slot, None],
                target_id=core.entity_id[rows, source_slot, None],
                x_units=core.entity_x_units[rows, source_slot, None],
                y_units=core.entity_y_units[rows, source_slot, None],
                payload=card[:, None],
            )
            catalog_index = working_runtime.card_catalog_index[
                core.entity_card
            ].clamp_min(0)
            collision = working_runtime.catalog.collision_radius_units[
                catalog_index
            ].to(torch.int64)
            dx = core.entity_x_units.to(torch.int64) - endpoint[:, 0, None]
            dy = core.entity_y_units.to(torch.int64) - endpoint[:, 1, None]
            radius = working.catalog.splash_radius_units[card, None] + collision
            targets = (
                valid_projectile[:, None]
                & working_runtime.entity_pool.active
                & core.entity_active
                & (core.entity_player != player[:, None])
                & ((core.entity_kind == 0) | (core.entity_kind == 1))
                & working.target_damage_receivable[rows, card]
                & torch.where(
                    working.target_airborne,
                    working.catalog.hits_air[card, None],
                    working.catalog.hits_ground[card, None],
                )
                & (dx * dx + dy * dy < radius * radius)
            )
            target_order = working_runtime.entity_pool.id_order(targets)
            for target_rank in range(runtime.max_entities):
                target_valid = target_order.valid[:, target_rank]
                target_slot = target_order.slots[:, target_rank].clamp_min(0)
                amount = working.catalog.damage[card]
                old_hp = core.entity_hp[rows, target_slot]
                applied = torch.minimum(old_hp, amount)
                next_hp = torch.clamp(old_hp - amount, min=0.0)
                core.entity_hp[rows[target_valid], target_slot[target_valid]] = next_hp[
                    target_valid
                ]
                core.entity_hp_integer_kind[
                    rows[target_valid], target_slot[target_valid]
                ] = False
                killed = target_valid & (next_hp <= 0)
                core.entity_active[rows[killed], target_slot[killed]] = False
                damage_result[rows[target_valid], target_slot[target_valid]] += applied[
                    target_valid
                ]
                death_result[rows[killed], target_slot[killed]] = True
                unsupported_rows |= (
                    killed & ~working.target_death_payload_supported[rows, target_slot]
                )
                working_runtime.events.append(
                    phase=TickPhase.OBJECTS,
                    opcode=RuntimeEventOpcode.DAMAGE,
                    valid=target_valid[:, None],
                    source_id=projectile_id[:, None],
                    target_id=target_order.entity_ids[:, target_rank, None],
                    amount=applied[:, None],
                    payload=card[:, None],
                )
                working_runtime.events.append(
                    phase=TickPhase.OBJECTS,
                    opcode=RuntimeEventOpcode.DEATH,
                    valid=killed[:, None],
                    source_id=projectile_id[:, None],
                    target_id=target_order.entity_ids[:, target_rank, None],
                    payload=card[:, None],
                )
            projectile_cleanup[
                rows[valid_projectile], projectile_slot[valid_projectile]
            ] = True

        working_runtime.entity_pool.cleanup(projectile_cleanup)
        _clear_slots_(working_runtime, projectile_cleanup)
        supported &= ~unsupported_rows
        working_runtime.mark_dirty(supported, phase=TickPhase.OBJECTS)
        _copy_runtime_rows_(runtime, working_runtime, supported)
        self._copy_rows_(working, supported)
        return DemolitionStepResult(
            committed=~selected | supported,
            capacity_rejected=capacity_rejected,
            acquired_target_id=torch.where(
                supported[:, None], self.target_entity_id, 0
            ),
            moved=moved & supported[:, None],
            primed=primed_now & supported[:, None],
            detonated=detonated & supported[:, None],
            projectile_entity_ids=projectile_ids_by_source,
            damage=torch.where(supported[:, None], damage_result, 0.0),
            deaths=death_result & supported[:, None],
        )


__all__ = [
    "DemolitionStepResult",
    "TensorDemolitionCatalog",
    "TensorResidentDemolition",
]
