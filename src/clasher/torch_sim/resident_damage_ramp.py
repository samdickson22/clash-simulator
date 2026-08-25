"""Retained stationary combat lifecycle for serialized variable-damage beams."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.gamedata_normalization import serialized_hit_planes
from clasher.mechanics.shared import DamageRamp

from .combat_mechanics import (
    TensorCombatMechanicCatalog,
    TensorDamageRampState,
    update_damage_ramp_,
)
from .movement import integer_sqrt_tensor
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorResidentRampCatalog:
    combat: TensorCombatMechanicCatalog
    core_to_combat: torch.Tensor
    supported: torch.Tensor
    direct_building_supported: torch.Tensor
    hit_speed_ms: torch.Tensor
    retarget_ms: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    uses_projectile: torch.Tensor


@dataclass(frozen=True)
class RampAttackStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    target_id: torch.Tensor
    connected: torch.Tensor
    stage_damage: torch.Tensor
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
class TensorResidentDamageRamp:
    catalog: TensorResidentRampCatalog
    tracked_entity_id: torch.Tensor
    target_slot: torch.Tensor
    public_target_id: torch.Tensor
    attack_cooldown: torch.Tensor
    ramp: TensorDamageRampState
    target_collision_radius_units: torch.Tensor
    target_airborne: torch.Tensor
    target_effect_receivable: torch.Tensor
    target_has_shield: torch.Tensor
    target_shield: torch.Tensor
    target_shield_integer_kind: torch.Tensor
    target_shield_break_count: torch.Tensor
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
    ) -> TensorResidentDamageRamp:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match damage-ramp runtime")
        device = runtime.device
        names = runtime.battle.card_names
        definitions = battles[0].card_loader.load_card_definitions()
        combat = TensorCombatMechanicCatalog.compile(
            battles[0].card_loader,
            (name for name in names[1:] if name in definitions),
            device=device,
        )
        core_to_combat = torch.tensor(
            [combat.name_to_id.get(name, 0) for name in names],
            dtype=torch.int64,
            device=device,
        )
        size = len(names)

        def plane(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = plane(torch.bool)
        direct_building_supported = plane(torch.bool)
        hit_speed = plane(torch.int64)
        retarget = plane(torch.int64)
        attack_range = plane(torch.int64)
        sight = plane(torch.int64)
        hits_air = plane(torch.bool)
        hits_ground = plane(torch.bool)
        projectile = plane(torch.bool)
        for core_id, name in enumerate(names):
            stats = battles[0].card_loader.get_card(name) if name else None
            definition = definitions.get(name)
            if stats is None or definition is None:
                continue
            ramps = [
                mechanic
                for mechanic in definition.mechanics
                if isinstance(mechanic, DamageRamp)
            ]
            if len(ramps) != 1:
                continue
            raw = getattr(stats, "_raw_entry", {}) or {}
            character = raw.get("summonCharacterData", {}) or {}
            air, ground = serialized_hit_planes(character)
            supported[core_id] = True
            hit_speed[core_id] = round(float(stats.hit_speed or 0))
            retarget[core_id] = round(float(stats.retarget_time or 0))
            attack_range[core_id] = round(float(stats.range or 0) * 1_000)
            sight[core_id] = round(float(stats.sight_range or 0) * 1_000)
            hits_air[core_id] = air
            hits_ground[core_id] = ground
            projectile[core_id] = bool(stats.projectile_data)
            direct_building_supported[core_id] = bool(
                str(stats.card_type).lower() == "building"
                and not stats.projectile_data
                and len(definition.mechanics) == 1
                and len(ramps[0].stages) == 3
                and tuple(int(stage[0]) for stage in ramps[0].stages)
                == (0, 2_000, 4_000)
            )

        shape = runtime.battle.entity_id.shape
        core = runtime.battle
        cards = core.entity_card.clamp(0, size - 1)
        tracked = torch.where(
            runtime.entity_pool.active & core.entity_active & supported[cards],
            core.entity_id,
            0,
        )
        cooldown = torch.zeros(shape, dtype=torch.float64, device=device)
        collision = torch.zeros(shape, dtype=torch.int64, device=device)
        airborne = torch.zeros(shape, dtype=torch.bool, device=device)
        effect_receivable = torch.ones(
            (runtime.batch_size, size, runtime.max_entities),
            dtype=torch.bool,
            device=device,
        )
        has_shield = torch.zeros(shape, dtype=torch.bool, device=device)
        shield = torch.zeros(shape, dtype=torch.float64, device=device)
        shield_kind = torch.zeros(shape, dtype=torch.bool, device=device)
        shield_break = torch.zeros(shape, dtype=torch.int32, device=device)
        death_supported = torch.ones(shape, dtype=torch.bool, device=device)
        supported_cards = torch.nonzero(supported).flatten().tolist()
        ramp_state = TensorDamageRampState.empty(shape, device=device)
        target_slot = torch.full(shape, -1, dtype=torch.int64, device=device)
        public_target = torch.zeros(shape, dtype=torch.int64, device=device)
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
                    effect_receivable[row, source_card, slot] = (
                        entity.can_receive_effect(names[source_card])
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
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )
                target_id = getattr(entity, "target_id", None)
                if target_id in slot_by_id:
                    target_slot[row, slot] = slot_by_id[target_id]
                    public_target[row, slot] = int(target_id)
                ramp_mechanics = [
                    mechanic
                    for mechanic in entity.mechanics
                    if isinstance(mechanic, DamageRamp)
                ]
                if ramp_mechanics:
                    ramp_state.target_id[row, slot] = int(
                        ramp_mechanics[0]._current_target_id or 0
                    )
                    ramp_state.target_time_ms[row, slot] = float(
                        ramp_mechanics[0]._current_target_ms
                    )
                    ramp_state.damage[row, slot] = float(entity.damage)

        return cls(
            TensorResidentRampCatalog(
                combat,
                core_to_combat,
                supported,
                direct_building_supported,
                hit_speed,
                retarget,
                attack_range,
                sight,
                hits_air,
                hits_ground,
                projectile,
            ),
            tracked,
            target_slot,
            public_target,
            cooldown,
            ramp_state,
            collision,
            airborne,
            effect_receivable,
            has_shield,
            shield,
            shield_kind,
            shield_break,
            death_supported,
        )

    def clone(self) -> TensorResidentDamageRamp:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        result.ramp = TensorDamageRampState(
            self.ramp.target_id.clone(),
            self.ramp.target_time_ms.clone(),
            self.ramp.damage.clone(),
        )
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentDamageRamp:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("damage-ramp fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        result.ramp = TensorDamageRampState(
            self.ramp.target_id[selected].clone(),
            self.ramp.target_time_ms[selected].clone(),
            self.ramp.damage[selected].clone(),
        )
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentDamageRamp,
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
            raise ValueError("damage-ramp reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]
        self.ramp.target_id[destination] = source.ramp.target_id[selected]
        self.ramp.target_time_ms[destination] = source.ramp.target_time_ms[selected]
        self.ramp.damage[destination] = source.ramp.damage[selected]

    def _copy_rows_(self, source: TensorResidentDamageRamp, rows: torch.Tensor) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]
        self.ramp.target_id[rows] = source.ramp.target_id[rows]
        self.ramp.target_time_ms[rows] = source.ramp.target_time_ms[rows]
        self.ramp.damage[rows] = source.ramp.damage[rows]

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> RampAttackStepResult:
        if dt_ms != 50:
            raise ValueError("damage-ramp runtime requires one 50ms logic tick")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("damage-ramp battle_mask must have shape [batch]")
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
        identity = working.tracked_entity_id == core.entity_id
        stale = (working.tracked_entity_id > 0) & ~(live & identity)
        new = live & ((working.tracked_entity_id == 0) | ~identity)
        working.tracked_entity_id.masked_fill_(stale, 0)
        working.target_slot.masked_fill_(stale, -1)
        working.public_target_id.masked_fill_(stale, 0)
        working.attack_cooldown.masked_fill_(stale, 0.0)
        working.ramp.target_id.masked_fill_(stale, 0)
        working.ramp.target_time_ms.masked_fill_(stale, 0.0)
        working.ramp.damage.masked_fill_(stale, 0.0)
        working.tracked_entity_id.copy_(
            torch.where(new, core.entity_id, working.tracked_entity_id)
        )
        order = working_runtime.entity_pool.id_order(live & selected[:, None])
        connected_plane = torch.zeros_like(live)
        observed_target = torch.zeros_like(core.entity_id)
        fire_plane = torch.zeros_like(live)
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
            working.target_slot[
                rows[valid_source & ~target_valid],
                source_slot[valid_source & ~target_valid],
            ] = -1
            working.public_target_id[
                rows[valid_source & ~target_valid],
                source_slot[valid_source & ~target_valid],
            ] = 0
            distance = integer_sqrt_tensor(distance_sq[rows, target_slot])
            reach = (
                working.catalog.range_units[card]
                + working.target_collision_radius_units[rows, target_slot]
            )
            connected = (
                target_valid
                & (distance <= reach)
                & (working_runtime.status.stun_timer[rows, source_slot] <= 1e-9)
            )
            connected_plane[rows[valid_source], source_slot[valid_source]] = connected[
                valid_source
            ]
            observed_target[rows[valid_source], source_slot[valid_source]] = (
                torch.where(target_valid[valid_source], target_id[valid_source], 0)
            )
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
            working.attack_cooldown[rows[connected], source_slot[connected]] = (
                next_cooldown[connected]
            )
            fire = connected & (next_cooldown <= 1e-9)
            working.attack_cooldown[rows[fire], source_slot[fire]] = (
                working.catalog.hit_speed_ms[card[fire]].to(torch.float64) / 1_000
            )
            fire_plane[rows[fire], source_slot[fire]] = True
            fire_target[rows[fire], source_slot[fire]] = target_slot[fire]

        combat_cards = working.catalog.core_to_combat[cards]
        stage_damage = update_damage_ramp_(
            working.ramp,
            working.catalog.combat,
            combat_cards,
            observed_target,
            connected_plane,
            torch.ones_like(working.ramp.target_time_ms),
            dt_ms=dt_ms,
        )
        fire_count = fire_plane.sum(dim=1, dtype=torch.int64)
        event_free = working_runtime.events.capacity - working_runtime.events.count.to(
            torch.int64
        )
        capacity_rejected = selected & (fire_count * 2 > event_free)
        supported = selected & ~capacity_rejected
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
            source_id = core.entity_id[rows, source_slot]
            target_id = core.entity_id[rows, target_slot]
            amount = stage_damage[rows, source_slot]
            absorbs = (
                fire
                & working.target_has_shield[rows, target_slot]
                & (working.target_shield[rows, target_slot] > 0)
            )
            next_shield = torch.clamp(
                working.target_shield[rows, target_slot] - amount, min=0.0
            )
            broken = absorbs & (next_shield <= 0)
            shield_index = (rows[absorbs], target_slot[absorbs])
            working.target_shield[shield_index] = next_shield[absorbs]
            working.target_shield_integer_kind[shield_index] = False
            working.target_shield_break_count[rows[broken], target_slot[broken]] += 1
            hp_hit = fire & ~absorbs
            old_hp = core.entity_hp[rows, target_slot]
            applied = torch.minimum(old_hp, amount)
            next_hp = torch.clamp(old_hp - amount, min=0.0)
            core.entity_hp[rows[hp_hit], target_slot[hp_hit]] = next_hp[hp_hit]
            core.entity_hp_integer_kind[rows[hp_hit], target_slot[hp_hit]] = False
            killed = hp_hit & (next_hp <= 0)
            core.entity_active[rows[killed], target_slot[killed]] = False
            damage_result[rows[hp_hit], target_slot[hp_hit]] += applied[hp_hit]
            death_result[rows[killed], target_slot[killed]] = True
            unsupported_rows |= (
                killed & ~working.target_death_payload_supported[rows, target_slot]
            )
            # Native shield-loss broadcast resets the connected source ramp.
            working.ramp.target_time_ms[rows[broken], source_slot[broken]] = 0.0
            working.ramp.damage[rows[broken], source_slot[broken]] = (
                working.catalog.combat.ramp_stage_damage[
                    combat_cards[rows[broken], source_slot[broken]], 0, 0
                ]
            )
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.DAMAGE,
                valid=fire[:, None],
                source_id=source_id[:, None],
                target_id=target_id[:, None],
                x_units=core.entity_x_units[rows, target_slot, None],
                y_units=core.entity_y_units[rows, target_slot, None],
                amount=torch.where(hp_hit, applied, 0.0)[:, None],
                payload=cards[rows, source_slot, None],
            )
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.DEATH,
                valid=killed[:, None],
                source_id=source_id[:, None],
                target_id=target_id[:, None],
                payload=cards[rows, source_slot, None],
            )

        supported &= ~unsupported_rows
        working_runtime.mark_dirty(supported, phase=TickPhase.COMBAT)
        _copy_runtime_rows_(runtime, working_runtime, supported)
        self._copy_rows_(working, supported)
        return RampAttackStepResult(
            committed=~selected | supported,
            capacity_rejected=capacity_rejected,
            target_id=torch.where(supported[:, None], self.public_target_id, 0),
            connected=connected_plane & supported[:, None],
            stage_damage=torch.where(supported[:, None], self.ramp.damage, 0.0),
            fired=fire_plane & supported[:, None],
            damage=torch.where(supported[:, None], damage_result, 0.0),
            deaths=death_result & supported[:, None],
        )


__all__ = [
    "RampAttackStepResult",
    "TensorResidentDamageRamp",
    "TensorResidentRampCatalog",
]
