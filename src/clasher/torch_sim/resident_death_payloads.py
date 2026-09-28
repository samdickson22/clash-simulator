"""Transactional pre-cleanup DeathDamage and DeathAreaEffect composition."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.battle import BattleState

from .combat import StationaryCombatState
from .combat_adapter import project_stationary_combat
from .combat_mechanics import (
    CombatMechanicOpcode,
    TensorCombatMechanicCatalog,
    TensorMechanicWorld,
    targets_in_native_area,
)
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .shield_champion import apply_shield_damage_
from .special_movement import install_radial_knockback


class DeathPayloadReason(IntEnum):
    NONE = 0
    AREA_CAPACITY = 1
    EVENT_CAPACITY = 2
    UNSUPPORTED_AREA = 3


@dataclass
class TensorDeathAreaDescriptors:
    valid: torch.Tensor
    object_id: torch.Tensor
    source_id: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    radius_units: torch.Tensor
    duration_ms: torch.Tensor
    activation_delay_ms: torch.Tensor
    interval_ms: torch.Tensor
    buff_duration_ms: torch.Tensor
    damage: torch.Tensor
    movement_multiplier: torch.Tensor
    attack_multiplier: torch.Tensor
    spawn_multiplier: torch.Tensor
    affects_hidden: torch.Tensor


@dataclass
class TensorDeathPayloadState:
    catalog: TensorCombatMechanicCatalog
    combat: StationaryCombatState
    entity_card: torch.Tensor
    has_shield: torch.Tensor
    shield_current: torch.Tensor
    shield_break_count: torch.Tensor
    damage_receivable: torch.Tensor
    max_areas: int
    areas: TensorDeathAreaDescriptors

    @property
    def device(self) -> torch.device:
        return self.entity_card.device

    @property
    def batch_size(self) -> int:
        return int(self.entity_card.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.entity_card.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        max_areas: int = 16,
    ) -> TensorDeathPayloadState:
        if len(battles) != runtime.batch_size or max_areas < 1:
            raise ValueError("invalid death payload dimensions")
        catalog = TensorCombatMechanicCatalog.compile(
            battles[0].card_loader,
            runtime.catalog.names[1:],
            device=runtime.device,
        )
        mapping = torch.tensor(
            [
                catalog.name_to_id.get(name, 0) if name else 0
                for name in runtime.battle.card_names
            ],
            dtype=torch.int64,
            device=runtime.device,
        )
        entity_card = mapping[runtime.battle.entity_card]
        combat = project_stationary_combat(
            battles,
            runtime.catalog,
            capacity=runtime.max_entities,
            device=runtime.device,
        ).state
        shape = runtime.battle.entity_id.shape
        pair = (*shape, runtime.max_entities)
        has_shield = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        shield = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        breaks = torch.zeros(shape, dtype=torch.int32, device=runtime.device)
        receivable = torch.zeros(pair, dtype=torch.bool, device=runtime.device)
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                shield_mechanics = [
                    m for m in entity.mechanics if type(m).__name__ == "Shield"
                ]
                if len(shield_mechanics) > 1:
                    raise ValueError("multiple shields are not representable")
                if shield_mechanics:
                    has_shield[row, slot] = True
                    shield[row, slot] = float(
                        vars(shield_mechanics[0])["current_shield"]
                    )
                breaks[row, slot] = int(getattr(entity, "_shield_break_count", 0))
            for source_id, source in battle.entities.items():
                source_slot = slots[source_id]
                source_kind = getattr(source.card_stats, "name", None)
                for target_id, target in battle.entities.items():
                    receivable[row, source_slot, slots[target_id]] = (
                        target.can_receive_area_damage(
                            source_kind, source_entity=source
                        )
                    )
        area_shape = (runtime.batch_size, max_areas)
        zeros_i64 = torch.zeros(area_shape, dtype=torch.int64, device=runtime.device)
        zeros_i32 = torch.zeros(area_shape, dtype=torch.int32, device=runtime.device)
        zeros_f64 = torch.zeros(area_shape, dtype=torch.float64, device=runtime.device)
        areas = TensorDeathAreaDescriptors(
            valid=torch.zeros(area_shape, dtype=torch.bool, device=runtime.device),
            object_id=zeros_i64.clone(),
            source_id=zeros_i64.clone(),
            owner=torch.zeros(area_shape, dtype=torch.int8, device=runtime.device),
            x_units=zeros_i32.clone(),
            y_units=zeros_i32.clone(),
            radius_units=zeros_i32.clone(),
            duration_ms=zeros_i32.clone(),
            activation_delay_ms=zeros_i32.clone(),
            interval_ms=zeros_i32.clone(),
            buff_duration_ms=zeros_i32.clone(),
            damage=zeros_f64.clone(),
            movement_multiplier=torch.ones(
                area_shape, dtype=torch.float64, device=runtime.device
            ),
            attack_multiplier=torch.ones(
                area_shape, dtype=torch.float64, device=runtime.device
            ),
            spawn_multiplier=torch.ones(
                area_shape, dtype=torch.float64, device=runtime.device
            ),
            affects_hidden=torch.zeros(
                area_shape, dtype=torch.bool, device=runtime.device
            ),
        )
        return cls(
            catalog,
            combat,
            entity_card,
            has_shield,
            shield,
            breaks,
            receivable,
            max_areas,
            areas,
        )

    def clone(self) -> TensorDeathPayloadState:
        return type(self)(
            self.catalog,
            _clone_combat(self.combat),
            self.entity_card.clone(),
            self.has_shield.clone(),
            self.shield_current.clone(),
            self.shield_break_count.clone(),
            self.damage_receivable.clone(),
            self.max_areas,
            _clone_areas(self.areas),
        )

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorDeathPayloadState:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        cloned = self.clone()
        cloned.combat = _select_combat(self.combat, indices)
        for name in (
            "entity_card",
            "has_shield",
            "shield_current",
            "shield_break_count",
            "damage_receivable",
        ):
            setattr(cloned, name, getattr(self, name).index_select(0, indices).clone())
        cloned.areas = TensorDeathAreaDescriptors(
            **{
                f.name: getattr(self.areas, f.name).index_select(0, indices).clone()
                for f in fields(self.areas)
            }
        )
        return cloned

    def reset_rows_(
        self,
        rows: torch.Tensor | Sequence[int],
        source: TensorDeathPayloadState,
        source_rows: torch.Tensor | Sequence[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        selected = (
            destination
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        for f in fields(self.combat):
            getattr(self.combat, f.name)[destination] = getattr(source.combat, f.name)[
                selected
            ]
        for name in (
            "entity_card",
            "has_shield",
            "shield_current",
            "shield_break_count",
            "damage_receivable",
        ):
            getattr(self, name)[destination] = getattr(source, name)[selected]
        for f in fields(self.areas):
            getattr(self.areas, f.name)[destination] = getattr(source.areas, f.name)[
                selected
            ]


@dataclass(frozen=True)
class TensorDeathKnockbackDescriptors:
    valid: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor
    target_slot: torch.Tensor
    target_units: torch.Tensor
    velocity_work: torch.Tensor


@dataclass(frozen=True)
class DeathPayloadStepResult:
    committed: torch.Tensor
    reason: torch.Tensor
    terminal_dead: torch.Tensor
    newly_dead: torch.Tensor
    damage: torch.Tensor
    died: torch.Tensor
    areas: TensorDeathAreaDescriptors
    knockback: TensorDeathKnockbackDescriptors


def _clone_combat(value: StationaryCombatState) -> StationaryCombatState:
    return StationaryCombatState(
        **{f.name: getattr(value, f.name).clone() for f in fields(value)}
    )


def _select_combat(
    value: StationaryCombatState, rows: torch.Tensor
) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            f.name: getattr(value, f.name).index_select(0, rows).clone()
            for f in fields(value)
        }
    )


def _clone_areas(value: TensorDeathAreaDescriptors) -> TensorDeathAreaDescriptors:
    return TensorDeathAreaDescriptors(
        **{f.name: getattr(value, f.name).clone() for f in fields(value)}
    )


def _copy_rows(destination: object, source: object, mask: torch.Tensor) -> None:
    for f in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, f.name)
        right = getattr(source, f.name)
        if isinstance(left, torch.Tensor):
            left[mask] = right[mask]


def _world(
    state: TensorDeathPayloadState, source_slot: torch.Tensor
) -> TensorMechanicWorld:
    combat = state.combat
    rows = torch.arange(state.batch_size, device=state.device)
    return TensorMechanicWorld(
        present=combat.present,
        entity_id=combat.entity_id,
        owner=combat.owner,
        x_units=combat.x_units.to(torch.int32),
        y_units=combat.y_units.to(torch.int32),
        collision_radius_units=combat.collision_radius_units.to(torch.int32),
        distance_discount_sq_units=combat.target_distance_discount_sq_units,
        hp=combat.hp,
        alive=combat.alive,
        airborne=combat.airborne,
        building=combat.kind == 1,
        crown=combat.crown_slot >= 0,
        targetable=combat.targetable,
        effect_receivable=state.damage_receivable[rows, source_slot],
    )


def step_death_payloads_(
    runtime: TensorBattleRuntime, state: TensorDeathPayloadState, dead: torch.Tensor
) -> DeathPayloadStepResult:
    if dead.shape != runtime.battle.entity_id.shape or runtime.device != state.device:
        raise ValueError("death mask differs from retained state")
    working = state.clone()
    speculative = runtime.clone()
    combat = working.combat
    combat.hp.copy_(speculative.battle.entity_hp)
    combat.alive.copy_(speculative.battle.entity_active)
    combat.x_units.copy_(speculative.battle.entity_x_units.to(torch.int64))
    combat.y_units.copy_(speculative.battle.entity_y_units.to(torch.int64))
    batch, count = dead.shape
    rows = torch.arange(batch, device=state.device)
    pending = dead.clone()
    processed = torch.zeros_like(dead)
    damage_total = torch.zeros_like(combat.hp)
    died_total = torch.zeros_like(dead)
    area_overflow = torch.zeros(batch, dtype=torch.bool, device=state.device)
    unsupported_area = torch.zeros_like(area_overflow)
    ev_valid: list[torch.Tensor] = []
    ev_opcode: list[torch.Tensor] = []
    ev_source: list[torch.Tensor] = []
    ev_target: list[torch.Tensor] = []
    ev_amount: list[torch.Tensor] = []
    kb_valid: list[torch.Tensor] = []
    kb_source: list[torch.Tensor] = []
    kb_target: list[torch.Tensor] = []
    kb_slot: list[torch.Tensor] = []
    kb_units: list[torch.Tensor] = []
    kb_velocity: list[torch.Tensor] = []

    def event(
        valid: torch.Tensor,
        opcode: RuntimeEventOpcode,
        source: torch.Tensor,
        target: torch.Tensor,
        amount: torch.Tensor | None = None,
    ) -> None:
        ev_valid.append(valid)
        ev_opcode.append(torch.full_like(source, int(opcode)))
        ev_source.append(source)
        ev_target.append(target)
        ev_amount.append(
            torch.zeros(batch, dtype=torch.float64, device=state.device)
            if amount is None
            else amount
        )

    for _ in range(count):
        candidate = pending & ~processed
        key = torch.where(
            candidate,
            combat.entity_id,
            torch.full_like(combat.entity_id, torch.iinfo(torch.int64).max),
        )
        source_slot = key.argmin(dim=1)
        source_valid = candidate.any(dim=1) & runtime.supported
        processed[rows, source_slot] |= source_valid
        card = working.entity_card[rows, source_slot]
        source_id = combat.entity_id[rows, source_slot]
        for mechanic_index in range(working.catalog.max_mechanics):
            opcode = working.catalog.opcode[card, mechanic_index]
            death_damage = source_valid & (
                opcode == int(CombatMechanicOpcode.DEATH_DAMAGE)
            )
            if death_damage.any():
                targets = (
                    targets_in_native_area(
                        _world(working, source_slot),
                        owner=combat.owner[rows, source_slot],
                        center_x_units=combat.x_units[rows, source_slot],
                        center_y_units=combat.y_units[rows, source_slot],
                        radius_units=working.catalog.radius_units[
                            card, mechanic_index
                        ].to(torch.int64),
                        hits_air=working.catalog.hits_air[card, mechanic_index],
                        hits_ground=working.catalog.hits_ground[card, mechanic_index],
                    )
                    & death_damage[:, None]
                )
                order = torch.argsort(
                    torch.where(
                        targets,
                        combat.entity_id,
                        torch.full_like(combat.entity_id, torch.iinfo(torch.int64).max),
                    ),
                    dim=1,
                    stable=True,
                )
                for rank in range(count):
                    slot = order[:, rank]
                    valid = targets[rows, slot]
                    incoming = working.catalog.damage[card, mechanic_index]
                    shield = working.shield_current[rows, slot]
                    breaks = working.shield_break_count[rows, slot]
                    shield_result = apply_shield_damage_(
                        shield,
                        breaks,
                        torch.where(valid, incoming, 0.0),
                        working.has_shield[rows, slot] & valid,
                    )
                    working.shield_current[rows, slot] = shield
                    working.shield_break_count[rows, slot] = breaks
                    before = combat.hp[rows, slot]
                    after = torch.clamp(before - shield_result.hitpoint_damage, min=0.0)
                    combat.hp[rows, slot] = torch.where(valid, after, before)
                    dealt = torch.where(valid, before - after, 0.0)
                    died = valid & combat.alive[rows, slot] & (after <= 0)
                    combat.alive[rows, slot] &= ~died
                    pending[rows, slot] |= died
                    damage_total[rows, slot] += dealt
                    died_total[rows, slot] |= died
                    event(
                        valid,
                        RuntimeEventOpcode.DAMAGE,
                        source_id,
                        combat.entity_id[rows, slot],
                        dealt,
                    )
                    event(
                        died,
                        RuntimeEventOpcode.DEATH,
                        source_id,
                        combat.entity_id[rows, slot],
                    )
                    distance = working.catalog.knockback_units[card, mechanic_index].to(
                        torch.int64
                    )
                    eligible = (
                        valid & ~died & (distance > 0) & (combat.kind[rows, slot] != 1)
                    )
                    installed = install_radial_knockback(
                        torch.stack(
                            (combat.x_units[rows, slot], combat.y_units[rows, slot]),
                            dim=1,
                        ),
                        torch.stack(
                            (
                                combat.x_units[rows, source_slot],
                                combat.y_units[rows, source_slot],
                            ),
                            dim=1,
                        ),
                        distance,
                        player_id=combat.owner[rows, slot].to(torch.int64),
                        eligible=eligible,
                    )
                    kb_valid.append(installed.started)
                    kb_source.append(source_id)
                    kb_target.append(combat.entity_id[rows, slot])
                    kb_slot.append(slot)
                    kb_units.append(installed.target_units)
                    kb_velocity.append(installed.velocity_work)
            death_area = source_valid & (opcode == int(CombatMechanicOpcode.DEATH_AREA))
            if death_area.any():
                supported = working.catalog.area_payload_supported[card, mechanic_index]
                unsupported_area |= death_area & ~supported
                valid = death_area & supported
                free = ~working.areas.valid
                has_free = free.any(dim=1)
                area_overflow |= valid & ~has_free
                valid &= has_free
                area_slot = free.to(torch.int64).argmax(dim=1)
                index = (rows, area_slot)
                object_id = speculative.entity_pool.next_entity_id.clone()
                speculative.entity_pool.next_entity_id += valid.to(torch.int64)
                working.areas.valid[index] |= valid
                for name, value in (
                    ("object_id", object_id),
                    ("source_id", source_id),
                    ("owner", combat.owner[rows, source_slot]),
                    ("x_units", combat.x_units[rows, source_slot]),
                    ("y_units", combat.y_units[rows, source_slot]),
                    (
                        "radius_units",
                        working.catalog.radius_units[card, mechanic_index],
                    ),
                    (
                        "duration_ms",
                        working.catalog.area_duration_ms[card, mechanic_index],
                    ),
                    (
                        "activation_delay_ms",
                        working.catalog.area_delay_ms[card, mechanic_index],
                    ),
                    (
                        "interval_ms",
                        working.catalog.area_hit_interval_ms[card, mechanic_index],
                    ),
                    (
                        "buff_duration_ms",
                        working.catalog.area_buff_ms[card, mechanic_index],
                    ),
                    ("damage", working.catalog.area_damage[card, mechanic_index]),
                    (
                        "movement_multiplier",
                        working.catalog.area_movement_multiplier[card, mechanic_index],
                    ),
                    (
                        "attack_multiplier",
                        working.catalog.area_attack_multiplier[card, mechanic_index],
                    ),
                    (
                        "spawn_multiplier",
                        working.catalog.area_spawn_multiplier[card, mechanic_index],
                    ),
                    (
                        "affects_hidden",
                        working.catalog.area_affects_hidden[card, mechanic_index],
                    ),
                ):
                    destination = getattr(working.areas, name)
                    destination[index] = torch.where(
                        valid, value.to(destination.dtype), destination[index]
                    )
                event(
                    valid,
                    RuntimeEventOpcode.AREA,
                    source_id,
                    object_id,
                    working.catalog.area_damage[card, mechanic_index],
                )

    valid = (
        torch.stack(ev_valid, dim=1)
        if ev_valid
        else torch.zeros((batch, 0), dtype=torch.bool, device=state.device)
    )
    opcode = (
        torch.stack(ev_opcode, dim=1)
        if ev_opcode
        else torch.zeros((batch, 0), dtype=torch.int64, device=state.device)
    )
    source = torch.stack(ev_source, dim=1) if ev_source else torch.zeros_like(opcode)
    target = torch.stack(ev_target, dim=1) if ev_target else torch.zeros_like(opcode)
    amount = (
        torch.stack(ev_amount, dim=1)
        if ev_amount
        else torch.zeros((batch, 0), dtype=torch.float64, device=state.device)
    )
    event_overflow = (
        speculative.events.count.to(torch.int64) + valid.sum(dim=1)
        > speculative.events.capacity
    )
    committed = runtime.supported & ~area_overflow & ~event_overflow & ~unsupported_area
    reason = torch.where(
        area_overflow,
        int(DeathPayloadReason.AREA_CAPACITY),
        torch.where(
            event_overflow,
            int(DeathPayloadReason.EVENT_CAPACITY),
            torch.where(unsupported_area, int(DeathPayloadReason.UNSUPPORTED_AREA), 0),
        ),
    ).to(torch.int16)
    speculative.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=opcode,
        valid=valid & committed[:, None],
        source_id=source,
        target_id=target,
        amount=amount,
    )
    speculative.battle.entity_hp.copy_(combat.hp)
    speculative.battle.entity_active.copy_(combat.alive)
    speculative.battle.entity_hp_integer_kind &= ~(damage_total > 0)
    speculative.phases.death_pending |= pending
    _copy_rows(runtime.battle, speculative.battle, committed)
    _copy_rows(runtime.phases, speculative.phases, committed)
    _copy_rows(runtime.events, speculative.events, committed)
    runtime.entity_pool.next_entity_id[committed] = (
        speculative.entity_pool.next_entity_id[committed]
    )
    _copy_rows(state.combat, working.combat, committed)
    for name in ("shield_current", "shield_break_count"):
        getattr(state, name)[committed] = getattr(working, name)[committed]
    _copy_rows(state.areas, working.areas, committed)
    runtime.mark_dirty(
        committed & (dead | died_total).any(dim=1), phase=TickPhase.CLEANUP_AND_SPAWNS
    )
    if kb_valid:
        knockback = TensorDeathKnockbackDescriptors(
            torch.stack(kb_valid, 1) & committed[:, None],
            torch.stack(kb_source, 1),
            torch.stack(kb_target, 1),
            torch.stack(kb_slot, 1),
            torch.stack(kb_units, 1),
            torch.stack(kb_velocity, 1),
        )
    else:
        zero = torch.zeros((batch, 0), dtype=torch.int64, device=state.device)
        knockback = TensorDeathKnockbackDescriptors(
            zero.bool(),
            zero,
            zero,
            zero,
            torch.zeros((batch, 0, 2), dtype=torch.int64, device=state.device),
            zero,
        )
    return DeathPayloadStepResult(
        committed,
        reason,
        pending & committed[:, None],
        died_total & committed[:, None],
        torch.where(committed[:, None], damage_total, 0.0),
        died_total & committed[:, None],
        state.areas,
        knockback,
    )


__all__ = [
    "DeathPayloadReason",
    "DeathPayloadStepResult",
    "TensorDeathAreaDescriptors",
    "TensorDeathKnockbackDescriptors",
    "TensorDeathPayloadState",
    "step_death_payloads_",
]
