"""Retained underground deployment and surfaced combat lifecycle."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.cards.miner import UndergroundDeployment
from clasher.gamedata_normalization import serialized_hit_planes

from .movement import integer_sqrt_tensor, movement_component_vector_units
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .special_movement import step_underground_deployment


@dataclass(frozen=True)
class TensorMinerCatalog:
    supported: torch.Tensor
    underground_speed_units: torch.Tensor
    surfaced_speed_units: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    damage: torch.Tensor
    crown_damage: torch.Tensor
    hit_speed_ms: torch.Tensor
    first_hit_ms: torch.Tensor
    retarget_ms: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor


@dataclass(frozen=True)
class MinerDeploymentHandoff:
    spawn_mask: torch.Tensor
    entity_id: torch.Tensor
    destination_units: torch.Tensor
    travel_duration_seconds: torch.Tensor


@dataclass(frozen=True)
class MinerConsumeResult:
    committed: torch.Tensor
    accepted: torch.Tensor
    unsupported: torch.Tensor
    capacity_rejected: torch.Tensor


@dataclass(frozen=True)
class MinerStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    underground_active: torch.Tensor
    targetable: torch.Tensor
    effect_immune: torch.Tensor
    reached_destination: torch.Tensor
    surfaced: torch.Tensor
    target_id: torch.Tensor
    moved: torch.Tensor
    fired: torch.Tensor
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


@dataclass
class TensorResidentMiner:
    catalog: TensorMinerCatalog
    tracked_entity_id: torch.Tensor
    destination_units: torch.Tensor
    total_delay_seconds: torch.Tensor
    travel_duration_seconds: torch.Tensor
    underground_active: torch.Tensor
    reached_destination: torch.Tensor
    target_slot: torch.Tensor
    public_target_id: torch.Tensor
    attack_cooldown: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_airborne: torch.Tensor
    target_crown: torch.Tensor
    target_effect_receivable: torch.Tensor
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
    ) -> TensorResidentMiner:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match Miner runtime")
        device = runtime.device
        size = len(runtime.battle.card_names)

        def card_plane(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = card_plane(torch.bool)
        underground_speed = card_plane(torch.int64)
        surfaced_speed = card_plane(torch.int64)
        attack_range = card_plane(torch.int64)
        sight = card_plane(torch.int64)
        damage = card_plane(torch.float64)
        crown_damage = card_plane(torch.float64)
        hit_speed = card_plane(torch.int64)
        first_hit = card_plane(torch.int64)
        retarget = card_plane(torch.int64)
        hits_air = card_plane(torch.bool)
        hits_ground = card_plane(torch.bool)
        definitions = battles[0].card_loader.load_card_definitions()
        for card_id, name in enumerate(runtime.battle.card_names):
            stats = battles[0].card_loader.get_card(name) if name else None
            definition = definitions.get(name)
            if stats is None or definition is None:
                continue
            mechanics = [
                mechanic
                for mechanic in definition.mechanics
                if isinstance(mechanic, UndergroundDeployment)
            ]
            if len(mechanics) != 1:
                continue
            raw = getattr(stats, "_raw_entry", {}) or {}
            character = raw.get("summonCharacterData", {}) or {}
            air, ground = serialized_hit_planes(character)
            full_damage = float(stats.scaled_damage or stats.damage or 0)
            crown_mechanics = [
                mechanic
                for mechanic in definition.mechanics
                if type(mechanic).__name__ == "CrownTowerScaling"
            ]
            explicit_crown = (
                getattr(crown_mechanics[0], "crown_tower_damage", None)
                if crown_mechanics
                else None
            )
            supported[card_id] = True
            underground_speed[card_id] = round(
                float(mechanics[0].travel_speed_logic_units_per_tick)
            )
            surfaced_speed[card_id] = round(float(stats.speed or 0))
            attack_range[card_id] = round(float(stats.range or 0) * 1_000)
            sight[card_id] = round(float(stats.sight_range or 0) * 1_000)
            damage[card_id] = full_damage
            crown_damage[card_id] = (
                float(explicit_crown)
                if explicit_crown is not None
                else float(
                    (
                        round(full_damage)
                        * max(
                            0,
                            round(
                                100
                                + float(
                                    character.get("crownTowerDamagePercent", 0) or 0
                                )
                            ),
                        )
                        + 99
                    )
                    // 100
                )
            )
            hit_speed[card_id] = round(float(stats.hit_speed or 0))
            first_hit[card_id] = round(float(stats.first_hit_time or 0))
            retarget[card_id] = round(float(stats.retarget_time or 0))
            hits_air[card_id] = air
            hits_ground[card_id] = ground

        shape = runtime.battle.entity_id.shape
        cooldown = torch.zeros(shape, dtype=torch.float64, device=device)
        collision = torch.zeros(shape, dtype=torch.int64, device=device)
        airborne = torch.zeros(shape, dtype=torch.bool, device=device)
        crown = torch.zeros(shape, dtype=torch.bool, device=device)
        effect_receivable = torch.ones(
            (runtime.batch_size, size, runtime.max_entities),
            dtype=torch.bool,
            device=device,
        )
        death_supported = torch.ones(shape, dtype=torch.bool, device=device)
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
                crown[row, slot] = bool(
                    entity.entity_kind == 1
                    and getattr(entity.card_stats, "name", None)
                    in {"Tower", "KingTower"}
                )
                for source_card in supported_cards:
                    effect_receivable[row, source_card, slot] = (
                        entity.can_receive_effect(
                            runtime.battle.card_names[source_card]
                        )
                    )
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )

        return cls(
            TensorMinerCatalog(
                supported,
                underground_speed,
                surfaced_speed,
                attack_range,
                sight,
                damage,
                crown_damage,
                hit_speed,
                first_hit,
                retarget,
                hits_air,
                hits_ground,
            ),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros((*shape, 2), dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.float64, device=device),
            torch.zeros(shape, dtype=torch.float64, device=device),
            torch.zeros(shape, dtype=torch.bool, device=device),
            torch.zeros(shape, dtype=torch.bool, device=device),
            torch.full(shape, -1, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            cooldown,
            collision,
            airborne,
            crown,
            effect_receivable,
            death_supported,
        )

    def clone(self) -> TensorResidentMiner:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentMiner:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("Miner fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentMiner,
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
            raise ValueError("Miner reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(self, source: TensorResidentMiner, rows: torch.Tensor) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def consume_handoff_(
        self,
        runtime: TensorBattleRuntime,
        handoff: MinerDeploymentHandoff,
    ) -> MinerConsumeResult:
        shape = runtime.battle.entity_id.shape
        if (
            handoff.spawn_mask.shape != shape
            or handoff.entity_id.shape != shape
            or handoff.destination_units.shape != (*shape, 2)
            or handoff.travel_duration_seconds.shape != shape
        ):
            raise ValueError("Miner handoff layout differs from runtime")
        core = runtime.battle
        cards = core.entity_card.clamp(0, len(self.catalog.supported) - 1)
        requested = handoff.spawn_mask.to(self.device, torch.bool)
        identity = (
            runtime.entity_pool.active
            & core.entity_active
            & (core.entity_id == handoff.entity_id)
        )
        accepted_mask = requested & identity & self.catalog.supported[cards]
        unsupported = (requested & ~accepted_mask).any(dim=1)
        event_need = accepted_mask.sum(dim=1, dtype=torch.int64)
        event_free = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = ~unsupported & (event_need > event_free)
        committed = runtime.supported & ~unsupported & ~capacity_rejected
        effective = accepted_mask & committed[:, None]
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        working.tracked_entity_id.copy_(
            torch.where(effective, core.entity_id, working.tracked_entity_id)
        )
        working.destination_units.copy_(
            torch.where(
                effective[..., None],
                handoff.destination_units.to(self.device, torch.int64),
                working.destination_units,
            )
        )
        working.travel_duration_seconds.copy_(
            torch.where(
                effective,
                handoff.travel_duration_seconds.to(self.device, torch.float64),
                working.travel_duration_seconds,
            )
        )
        working.total_delay_seconds.copy_(
            torch.where(
                effective,
                core.entity_deploy_delay,
                working.total_delay_seconds,
            )
        )
        working.underground_active |= effective
        working.reached_destination &= ~effective
        working.target_slot.masked_fill_(effective, -1)
        working.public_target_id.masked_fill_(effective, 0)
        working_runtime.events.append(
            phase=TickPhase.MOVEMENT,
            opcode=RuntimeEventOpcode.MOVEMENT,
            valid=effective,
            source_id=core.entity_id,
            x_units=core.entity_x_units,
            y_units=core.entity_y_units,
            payload=cards,
        )
        working_runtime.mark_dirty(committed, phase=TickPhase.MOVEMENT)
        _copy_runtime_rows_(runtime, working_runtime, committed)
        self._copy_rows_(working, committed)
        return MinerConsumeResult(
            committed=~runtime.supported | committed,
            accepted=committed & effective.any(dim=1),
            unsupported=unsupported,
            capacity_rejected=capacity_rejected,
        )

    def effect_eligible(self, requested: torch.Tensor) -> torch.Tensor:
        mask = torch.as_tensor(requested, dtype=torch.bool, device=self.device)
        if mask.shape != self.underground_active.shape:
            raise ValueError("Miner effect request layout differs")
        return mask & ~self.underground_active

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        ordinary_waypoint_units: torch.Tensor | None = None,
        ordinary_waypoint_valid: torch.Tensor | None = None,
        dt_ms: int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> MinerStepResult:
        if dt_ms != 50:
            raise ValueError("Miner runtime requires one 50ms logic tick")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("Miner battle_mask must have shape [batch]")
        shape = runtime.battle.entity_id.shape
        waypoints = (
            torch.zeros((*shape, 2), dtype=torch.int64, device=self.device)
            if ordinary_waypoint_units is None
            else torch.as_tensor(
                ordinary_waypoint_units, dtype=torch.int64, device=self.device
            )
        )
        waypoint_valid = (
            torch.zeros(shape, dtype=torch.bool, device=self.device)
            if ordinary_waypoint_valid is None
            else torch.as_tensor(
                ordinary_waypoint_valid, dtype=torch.bool, device=self.device
            )
        )
        if waypoints.shape != (*shape, 2) or waypoint_valid.shape != shape:
            raise ValueError("Miner ordinary waypoint layout differs")
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        core = working_runtime.battle
        rows = torch.arange(self.batch_size, device=self.device)
        cards = core.entity_card.clamp(0, len(self.catalog.supported) - 1)
        identity = (
            working_runtime.entity_pool.active
            & core.entity_active
            & (working.tracked_entity_id == core.entity_id)
        )
        stale = (working.tracked_entity_id > 0) & ~identity
        working.tracked_entity_id.masked_fill_(stale, 0)
        working.underground_active &= identity
        underground_before = working.underground_active & selected[:, None]
        positions = torch.stack((core.entity_x_units, core.entity_y_units), dim=-1).to(
            torch.int64
        )
        transport = step_underground_deployment(
            positions,
            working.destination_units,
            underground_active=underground_before,
            total_delay_seconds=working.total_delay_seconds,
            remaining_delay_seconds=core.entity_deploy_delay,
            travel_duration_seconds=working.travel_duration_seconds,
            speed_units=working.catalog.underground_speed_units[cards],
            dt_ms=dt_ms,
        )
        core.entity_x_units.copy_(transport.position_units[..., 0].to(torch.int32))
        core.entity_y_units.copy_(transport.position_units[..., 1].to(torch.int32))
        newly_reached = transport.reached_destination & ~working.reached_destination
        working.reached_destination |= transport.reached_destination
        deploy_after = torch.clamp(
            core.entity_deploy_delay - dt_ms / 1_000.0,
            min=0.0,
        )
        surfaced = underground_before & (deploy_after <= 1e-9)
        working.underground_active.copy_(transport.underground_active & ~surfaced)
        core.entity_deploy_delay.copy_(
            torch.where(underground_before, deploy_after, core.entity_deploy_delay)
        )
        core.entity_placement_pending &= ~surfaced
        core.entity_spawn_hook_pending &= ~surfaced
        core.entity_spawn_hook_fired |= surfaced
        transition = newly_reached | surfaced

        surfaced_before = identity & ~underground_before & selected[:, None]
        order = working_runtime.entity_pool.id_order(surfaced_before)
        moved = torch.zeros_like(identity)
        fire_plane = torch.zeros_like(identity)
        fire_target = torch.zeros_like(core.entity_id)
        previous_target = working.public_target_id.clone()
        for rank in range(runtime.max_entities):
            valid_source = order.valid[:, rank]
            source_slot = order.slots[:, rank].clamp_min(0)
            card = cards[rows, source_slot]
            player = core.entity_player[rows, source_slot]
            sx = core.entity_x_units[rows, source_slot].to(torch.int64)
            sy = core.entity_y_units[rows, source_slot].to(torch.int64)
            dx = core.entity_x_units.to(torch.int64) - sx[:, None]
            dy = core.entity_y_units.to(torch.int64) - sy[:, None]
            distance_sq = dx * dx + dy * dy
            candidates = (
                working_runtime.entity_pool.active
                & core.entity_active
                & (core.entity_player != player[:, None])
                & ((core.entity_kind == 0) | (core.entity_kind == 1))
                & working.target_effect_receivable[rows, card]
                & torch.where(
                    working.target_airborne,
                    working.catalog.hits_air[card, None],
                    working.catalog.hits_ground[card, None],
                )
                & (
                    distance_sq
                    <= (
                        working.catalog.sight_range_units[card, None]
                        + working.target_collision_radius_units
                    )
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
                & candidates[rows, retained_safe]
                & (
                    core.entity_id[rows, retained_safe]
                    == working.public_target_id[rows, source_slot]
                )
            )
            target_slot = torch.where(retained_valid, retained_safe, acquired)
            target_valid = valid_source & (retained_valid | candidates.any(dim=1))
            target_id = core.entity_id[rows, target_slot]
            working.target_slot[rows[target_valid], source_slot[target_valid]] = (
                target_slot[target_valid]
            )
            working.public_target_id[rows[target_valid], source_slot[target_valid]] = (
                target_id[target_valid]
            )
            distance = integer_sqrt_tensor(distance_sq[rows, target_slot])
            reach = (
                working.catalog.range_units[card]
                + working.target_collision_radius_units[rows, target_slot]
            )
            in_reach = target_valid & (distance <= reach)
            changed = previous_target[rows, source_slot] != target_id
            retarget = target_valid & changed & (previous_target[rows, source_slot] > 0)
            working.attack_cooldown[rows[retarget], source_slot[retarget]] = (
                torch.maximum(
                    working.attack_cooldown[rows[retarget], source_slot[retarget]],
                    working.catalog.retarget_ms[card[retarget]].to(torch.float64)
                    / 1_000,
                )
            )
            next_cooldown = torch.clamp(
                working.attack_cooldown[rows, source_slot] - dt_ms / 1_000.0,
                min=0.0,
            )
            working.attack_cooldown[rows[target_valid], source_slot[target_valid]] = (
                next_cooldown[target_valid]
            )
            fire = in_reach & (next_cooldown <= 1e-9)
            working.attack_cooldown[rows[fire], source_slot[fire]] = (
                working.catalog.hit_speed_ms[card[fire]].to(torch.float64) / 1_000
            )
            fire_plane[rows[fire], source_slot[fire]] = True
            fire_target[rows[fire], source_slot[fire]] = target_slot[fire]
            can_move = target_valid & ~in_reach & waypoint_valid[rows, source_slot]
            source_position = torch.stack((sx, sy), dim=-1)
            delta = waypoints[rows, source_slot] - source_position
            remaining = integer_sqrt_tensor((delta * delta).sum(dim=-1))
            work = torch.minimum(working.catalog.surfaced_speed_units[card], remaining)
            displacement = movement_component_vector_units(delta, work)
            core.entity_x_units[rows[can_move], source_slot[can_move]] += displacement[
                can_move, 0
            ].to(torch.int32)
            core.entity_y_units[rows[can_move], source_slot[can_move]] += displacement[
                can_move, 1
            ].to(torch.int32)
            moved[rows[can_move], source_slot[can_move]] = True

        fire_count = fire_plane.sum(dim=1, dtype=torch.int64)
        transition_count = transition.sum(dim=1, dtype=torch.int64)
        event_free = working_runtime.events.capacity - working_runtime.events.count.to(
            torch.int64
        )
        capacity_rejected = selected & (fire_count * 2 + transition_count > event_free)
        supported = selected & ~capacity_rejected
        working_runtime.events.append(
            phase=TickPhase.MOVEMENT,
            opcode=RuntimeEventOpcode.MOVEMENT,
            valid=transition & supported[:, None],
            source_id=core.entity_id,
            x_units=core.entity_x_units,
            y_units=core.entity_y_units,
            payload=cards,
        )
        damage_result = torch.zeros_like(core.entity_hp)
        death_result = torch.zeros_like(core.entity_active)
        unsupported_rows = torch.zeros_like(supported)
        fire_order = working_runtime.entity_pool.id_order(
            fire_plane & supported[:, None]
        )
        for rank in range(runtime.max_entities):
            fire = fire_order.valid[:, rank]
            source_slot = fire_order.slots[:, rank].clamp_min(0)
            target_slot = fire_target[rows, source_slot]
            card = cards[rows, source_slot]
            amount = torch.where(
                working.target_crown[rows, target_slot],
                working.catalog.crown_damage[card],
                working.catalog.damage[card],
            )
            old_hp = core.entity_hp[rows, target_slot]
            applied = torch.minimum(old_hp, amount)
            next_hp = torch.clamp(old_hp - amount, min=0.0)
            core.entity_hp[rows[fire], target_slot[fire]] = next_hp[fire]
            core.entity_hp_integer_kind[rows[fire], target_slot[fire]] = False
            killed = fire & (next_hp <= 0)
            core.entity_active[rows[killed], target_slot[killed]] = False
            damage_result[rows[fire], target_slot[fire]] += applied[fire]
            death_result[rows[killed], target_slot[killed]] = True
            unsupported_rows |= (
                killed & ~working.target_death_payload_supported[rows, target_slot]
            )
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.DAMAGE,
                valid=fire[:, None],
                source_id=core.entity_id[rows, source_slot, None],
                target_id=core.entity_id[rows, target_slot, None],
                x_units=core.entity_x_units[rows, target_slot, None],
                y_units=core.entity_y_units[rows, target_slot, None],
                amount=applied[:, None],
                payload=card[:, None],
            )
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.DEATH,
                valid=killed[:, None],
                source_id=core.entity_id[rows, source_slot, None],
                target_id=core.entity_id[rows, target_slot, None],
                payload=card[:, None],
            )

        supported &= ~unsupported_rows
        working_runtime.mark_dirty(supported, phase=TickPhase.MOVEMENT)
        _copy_runtime_rows_(runtime, working_runtime, supported)
        self._copy_rows_(working, supported)
        return MinerStepResult(
            committed=~selected | supported,
            capacity_rejected=capacity_rejected,
            underground_active=self.underground_active.clone(),
            targetable=(self.tracked_entity_id > 0) & ~self.underground_active,
            effect_immune=self.underground_active.clone(),
            reached_destination=newly_reached & supported[:, None],
            surfaced=surfaced & supported[:, None],
            target_id=torch.where(supported[:, None], self.public_target_id, 0),
            moved=moved & supported[:, None],
            fired=fire_plane & supported[:, None],
            damage=torch.where(supported[:, None], damage_result, 0.0),
            deaths=death_result & supported[:, None],
        )


__all__ = [
    "MinerConsumeResult",
    "MinerDeploymentHandoff",
    "MinerStepResult",
    "TensorMinerCatalog",
    "TensorResidentMiner",
]
