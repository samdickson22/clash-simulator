"""Retained, transactional Ice Spirit attack and jump lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Any

import torch

from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.kinematics import LOGIC_TICK_MILLISECONDS, tiles_to_logic_units

from .catalog import MECHANIC_OPCODE, TensorCardCatalog
from .combat import StationaryCombatState, select_stationary_targets
from .combat_adapter import project_stationary_combat
from .combat_clock_transitions import (
    TensorCombatClockPlanes,
    apply_stun_interrupt_,
)
from .movement import integer_sqrt_tensor, normalized_vector_units
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


class IceSpiritReason(IntEnum):
    NONE = 0
    EVENT_CAPACITY = 1
    UNSUPPORTED_DEATH_PAYLOAD = 2


@dataclass(frozen=True)
class TensorIceSpiritCatalog:
    supported: torch.Tensor
    radius_units: torch.Tensor
    freeze_duration_ms: torch.Tensor
    jump_speed_units_per_tick: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor

    @classmethod
    def compile(
        cls,
        loader: Any,
        cards: TensorCardCatalog,
    ) -> TensorIceSpiritCatalog:
        size = len(cards.names)
        supported = torch.zeros(size, dtype=torch.bool, device=cards.device)
        radius = torch.zeros(size, dtype=torch.int64, device=cards.device)
        freeze = torch.zeros(size, dtype=torch.int64, device=cards.device)
        speed = torch.zeros(size, dtype=torch.int64, device=cards.device)
        hits_air = torch.zeros(size, dtype=torch.bool, device=cards.device)
        hits_ground = torch.zeros(size, dtype=torch.bool, device=cards.device)
        definitions = loader.load_card_definitions()
        for card_id, name in enumerate(cards.names[1:], start=1):
            resolved = resolve_card_name(name, definitions)
            definition = definitions.get(resolved)
            if definition is None:
                continue
            mechanics = [
                mechanic
                for mechanic in definition.mechanics
                if type(mechanic).__name__ == "IceSpiritFreeze"
            ]
            if len(mechanics) != 1:
                continue
            operation = mechanics[0]
            stats = loader.get_card(name)
            if stats is None:
                continue
            projectile = getattr(stats, "projectile_data", {}) or {}
            radius[card_id] = int(
                projectile.get(
                    "radius",
                    tiles_to_logic_units(float(operation.freeze_radius)),
                )
            )
            freeze[card_id] = int(
                projectile.get("buffTime", operation.freeze_duration_ms)
            )
            speed[card_id] = int(
                projectile.get("speed", operation.jump_speed_logic_units_per_tick)
                or operation.jump_speed_logic_units_per_tick
            )
            hits_air[card_id] = bool(cards.attacks_air[card_id])
            hits_ground[card_id] = bool(cards.attacks_ground[card_id])
            supported[card_id] = bool(
                radius[card_id] > 0
                and freeze[card_id] >= 0
                and speed[card_id] > 0
                and int(cards.mechanic_count[card_id]) == 1
                and bool(
                    (
                        cards.mechanic_opcode[card_id]
                        == MECHANIC_OPCODE["IceSpiritFreeze"]
                    ).any()
                )
            )
        return cls(supported, radius, freeze, speed, hits_air, hits_ground)


@dataclass
class TensorIceSpiritState:
    catalog: TensorIceSpiritCatalog
    combat: StationaryCombatState
    entity_card: torch.Tensor
    initialized_entity_id: torch.Tensor
    jump_active: torch.Tensor
    jump_target_id: torch.Tensor
    destination_units: torch.Tensor
    elapsed_ms: torch.Tensor
    detonated: torch.Tensor
    damage_receivable: torch.Tensor
    status_receivable: torch.Tensor
    death_payload_supported: torch.Tensor

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
    ) -> TensorIceSpiritState:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime")
        catalog = TensorIceSpiritCatalog.compile(
            battles[0].card_loader, runtime.catalog
        )
        combat = project_stationary_combat(
            battles,
            runtime.catalog,
            capacity=runtime.max_entities,
            device=runtime.device,
        ).state
        card = runtime.card_catalog_index[runtime.battle.entity_card].clamp_min(0)
        shape = runtime.battle.entity_id.shape
        pair_shape = (*shape, runtime.max_entities)
        initialized = runtime.battle.entity_id.clone()
        jump_active = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        target = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        destination = torch.zeros((*shape, 2), dtype=torch.int64, device=runtime.device)
        elapsed = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        detonated = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        damage_receivable = torch.zeros(
            pair_shape, dtype=torch.bool, device=runtime.device
        )
        status_receivable = torch.zeros_like(damage_receivable)
        death_supported = torch.ones(shape, dtype=torch.bool, device=runtime.device)
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                jump_id = getattr(entity, "_ice_spirit_jump_target", None)
                jump_active[row, slot] = jump_id is not None
                target[row, slot] = 0 if jump_id is None else int(jump_id)
                raw_destination = getattr(entity, "_ice_spirit_jump_destination", None)
                if raw_destination is not None:
                    destination[row, slot] = torch.tensor(
                        [
                            tiles_to_logic_units(raw_destination[0]),
                            tiles_to_logic_units(raw_destination[1]),
                        ],
                        device=runtime.device,
                    )
                elapsed[row, slot] = round(
                    float(getattr(entity, "_ice_spirit_jump_timer", 0.0) or 0.0)
                )
                detonated[row, slot] = bool(
                    getattr(entity, "_ice_spirit_detonated", False)
                )
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )
            for source_id, source in battle.entities.items():
                source_slot = slots[source_id]
                if not bool(catalog.supported[card[row, source_slot]].item()):
                    continue
                source_kind = getattr(source.card_stats, "name", None)
                for target_id, other in battle.entities.items():
                    target_slot = slots[target_id]
                    damage_receivable[row, source_slot, target_slot] = (
                        other.can_receive_area_damage(
                            source_kind,
                            source_entity=source,
                        )
                    )
                    status_receivable[row, source_slot, target_slot] = (
                        other.can_receive_effect(source_kind)
                    )
        return cls(
            catalog,
            combat,
            card,
            initialized,
            jump_active,
            target,
            destination,
            elapsed,
            detonated,
            damage_receivable,
            status_receivable,
            death_supported,
        )

    def clone(self) -> TensorIceSpiritState:
        return type(self)(
            catalog=self.catalog,
            combat=_clone_combat(self.combat),
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
                if descriptor.name not in {"catalog", "combat"}
            },
        )

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorIceSpiritState:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        cloned = self.clone()
        cloned.combat = _select_combat(self.combat, indices)
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "combat"}:
                continue
            setattr(
                cloned,
                descriptor.name,
                getattr(self, descriptor.name).index_select(0, indices).clone(),
            )
        return cloned

    def reset_rows_(
        self,
        rows: torch.Tensor | Sequence[int],
        source: TensorIceSpiritState,
        source_rows: torch.Tensor | Sequence[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        selected = (
            destination
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        for descriptor in fields(self.combat):
            getattr(self.combat, descriptor.name)[destination] = getattr(
                source.combat, descriptor.name
            )[selected]
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "combat"}:
                continue
            getattr(self, descriptor.name)[destination] = getattr(
                source, descriptor.name
            )[selected]


@dataclass(frozen=True)
class IceSpiritStepResult:
    committed: torch.Tensor
    reason: torch.Tensor
    acquired: torch.Tensor
    jumped: torch.Tensor
    landed: torch.Tensor
    immune: torch.Tensor
    damage: torch.Tensor
    died: torch.Tensor
    stunned: torch.Tensor
    self_died: torch.Tensor


def _clone_combat(value: StationaryCombatState) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            descriptor.name: getattr(value, descriptor.name).clone()
            for descriptor in fields(value)
        }
    )


def _select_combat(
    value: StationaryCombatState, rows: torch.Tensor
) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            descriptor.name: getattr(value, descriptor.name)
            .index_select(0, rows)
            .clone()
            for descriptor in fields(value)
        }
    )


def _copy_rows(destination: object, source: object, rows: torch.Tensor) -> None:
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
            left[rows] = right[rows]


def _overlap(
    combat: StationaryCombatState,
    source_slot: torch.Tensor,
    radius: torch.Tensor,
) -> torch.Tensor:
    rows = torch.arange(combat.batch_size, device=combat.device)
    center_x = combat.x_units[rows, source_slot][:, None]
    center_y = combat.y_units[rows, source_slot][:, None]
    dx = combat.x_units - center_x
    dy = combat.y_units - center_y
    object_radius = combat.collision_radius_units
    circular = dx.square() + dy.square() < (radius[:, None] + object_radius).square()
    closest_x = torch.minimum(
        combat.x_units + object_radius,
        torch.maximum(combat.x_units - object_radius, center_x),
    )
    closest_y = torch.minimum(
        combat.y_units + object_radius,
        torch.maximum(combat.y_units - object_radius, center_y),
    )
    square = (closest_x - center_x).square() + (closest_y - center_y).square() < radius[
        :, None
    ].square()
    return torch.where(combat.kind == 1, square, circular)


def step_ice_spirit_lifecycle_(
    runtime: TensorBattleRuntime,
    state: TensorIceSpiritState,
    *,
    dt_ms: torch.Tensor | int = LOGIC_TICK_MILLISECONDS,
) -> IceSpiritStepResult:
    """Advance one combat+movement lifecycle transaction."""

    if runtime.device != state.device or runtime.batch_size != state.batch_size:
        raise ValueError("runtime and Ice Spirit state differ")
    batch, count = state.entity_card.shape
    device = state.device
    working = state.clone()
    speculative = runtime.clone()
    combat = working.combat
    combat.hp.copy_(speculative.battle.entity_hp)
    combat.alive.copy_(speculative.battle.entity_active)
    combat.x_units.copy_(speculative.battle.entity_x_units.to(torch.int64))
    combat.y_units.copy_(speculative.battle.entity_y_units.to(torch.int64))
    delta_ms = torch.broadcast_to(
        torch.as_tensor(dt_ms, dtype=torch.int64, device=device), (batch,)
    )
    source_mask = (
        combat.present
        & combat.alive
        & working.catalog.supported[working.entity_card]
        & (working.initialized_entity_id == combat.entity_id)
    )
    acquired = torch.zeros_like(source_mask)
    jumped = torch.zeros_like(source_mask)
    landed = torch.zeros_like(source_mask)
    damage_total = torch.zeros_like(combat.hp)
    died_total = torch.zeros_like(source_mask)
    stunned_total = torch.zeros_like(source_mask)
    self_died = torch.zeros_like(source_mask)
    unsupported_death = torch.zeros(batch, dtype=torch.bool, device=device)
    event_valid: list[torch.Tensor] = []
    event_opcode: list[torch.Tensor] = []
    event_source: list[torch.Tensor] = []
    event_target: list[torch.Tensor] = []
    event_amount: list[torch.Tensor] = []
    rows = torch.arange(batch, device=device)

    def event(
        valid: torch.Tensor,
        opcode: RuntimeEventOpcode,
        source: torch.Tensor,
        target: torch.Tensor,
        amount: torch.Tensor | None = None,
    ) -> None:
        event_valid.append(valid)
        event_opcode.append(torch.full_like(source, int(opcode)))
        event_source.append(source)
        event_target.append(target)
        event_amount.append(
            torch.zeros(batch, dtype=torch.float64, device=device)
            if amount is None
            else amount
        )

    order = speculative.entity_pool.id_order(source_mask)
    for rank in range(count):
        source_slot = order.slots[:, rank].clamp_min(0)
        source_valid = order.valid[:, rank] & runtime.supported
        card = working.entity_card[rows, source_slot]
        current_target_id = working.jump_target_id[rows, source_slot]
        current_match = (
            combat.present
            & combat.alive
            & (combat.entity_id == current_target_id[:, None])
        )
        current_found = current_match.any(dim=1)
        current_slot = current_match.to(torch.int64).argmax(dim=1)
        selected, _ = select_stationary_targets(combat, source_slot)
        selected_valid = selected >= 0
        has_target = current_found | selected_valid
        target_slot = torch.where(current_found, current_slot, selected.clamp_min(0))
        acquired_now = (
            source_valid
            & ~working.jump_active[rows, source_slot]
            & ~current_found
            & selected_valid
        )
        acquired[rows, source_slot] |= acquired_now
        combat.target_slot[rows, source_slot] = torch.where(
            acquired_now, selected, combat.target_slot[rows, source_slot]
        )
        target_slot = torch.where(acquired_now, selected.clamp_min(0), target_slot)
        target_id = combat.entity_id[rows, target_slot]
        dx = combat.x_units[rows, target_slot] - combat.x_units[rows, source_slot]
        dy = combat.y_units[rows, target_slot] - combat.y_units[rows, source_slot]
        reach = (
            combat.range_units[rows, source_slot]
            + combat.collision_radius_units[rows, target_slot]
        )
        in_range = dx.square() + dy.square() <= reach.square()
        ordinary = (
            source_valid
            & ~working.jump_active[rows, source_slot]
            & has_target
            & (combat.deploy_remaining[rows, source_slot] <= 1e-9)
            & ~combat.stunned[rows, source_slot]
            & in_range
        )
        cooldown = combat.attack_cooldown[rows, source_slot]
        work = (
            delta_ms.to(torch.float64)
            / 1_000.0
            * combat.attack_rate_multiplier[rows, source_slot]
        )
        cooldown = torch.where(
            ordinary, torch.clamp(cooldown - work, min=0.0), cooldown
        )
        combat.attack_cooldown[rows, source_slot] = cooldown
        jump_now = ordinary & (cooldown <= 1e-9)
        working.jump_active[rows, source_slot] |= jump_now
        working.jump_target_id[rows, source_slot] = torch.where(
            jump_now, target_id, working.jump_target_id[rows, source_slot]
        )
        working.destination_units[rows, source_slot] = torch.where(
            jump_now[:, None],
            torch.stack(
                (
                    combat.x_units[rows, target_slot],
                    combat.y_units[rows, target_slot],
                ),
                dim=1,
            ),
            working.destination_units[rows, source_slot],
        )
        jumped[rows, source_slot] |= jump_now
        event(
            jump_now,
            RuntimeEventOpcode.MOVEMENT,
            combat.entity_id[rows, source_slot],
            target_id,
        )

        active_jump = source_valid & working.jump_active[rows, source_slot]
        live_target = (
            combat.present
            & combat.alive
            & (combat.entity_id == working.jump_target_id[rows, source_slot, None])
        )
        live_found = live_target.any(dim=1)
        live_slot = live_target.to(torch.int64).argmax(dim=1)
        live_destination = torch.stack(
            (
                combat.x_units[rows, live_slot],
                combat.y_units[rows, live_slot],
            ),
            dim=1,
        )
        working.destination_units[rows, source_slot] = torch.where(
            (active_jump & live_found)[:, None],
            live_destination,
            working.destination_units[rows, source_slot],
        )
        position = torch.stack(
            (
                combat.x_units[rows, source_slot],
                combat.y_units[rows, source_slot],
            ),
            dim=1,
        )
        delta = working.destination_units[rows, source_slot] - position
        remaining = integer_sqrt_tensor((delta * delta).sum(dim=1))
        travel = torch.round(
            working.catalog.jump_speed_units_per_tick[card].to(torch.float64)
            * delta_ms.to(torch.float64)
            / LOGIC_TICK_MILLISECONDS
        ).to(torch.int64)
        movement = normalized_vector_units(delta, torch.minimum(travel, remaining))
        next_position = torch.where(
            (travel >= remaining)[:, None],
            working.destination_units[rows, source_slot],
            position + movement,
        )
        combat.x_units[rows, source_slot] = torch.where(
            active_jump, next_position[:, 0], combat.x_units[rows, source_slot]
        )
        combat.y_units[rows, source_slot] = torch.where(
            active_jump, next_position[:, 1], combat.y_units[rows, source_slot]
        )
        working.elapsed_ms[rows, source_slot] += torch.where(active_jump, delta_ms, 0)
        land_now = active_jump & (remaining <= travel)
        landed[rows, source_slot] |= land_now

        radius = working.catalog.radius_units[card]
        overlap = _overlap(combat, source_slot, radius)
        plane = torch.where(
            combat.airborne,
            working.catalog.hits_air[card][:, None],
            working.catalog.hits_ground[card][:, None],
        )
        recipients = (
            land_now[:, None]
            & combat.present
            & combat.alive
            & ((combat.kind == 0) | (combat.kind == 1))
            & (combat.owner != combat.owner[rows, source_slot, None])
            & plane
            & overlap
            & working.damage_receivable[rows, source_slot]
        )
        target_order = torch.argsort(
            torch.where(
                recipients,
                combat.entity_id,
                torch.full_like(combat.entity_id, torch.iinfo(torch.int64).max),
            ),
            dim=1,
            stable=True,
        )
        for target_rank in range(count):
            slot = target_order[:, target_rank]
            valid = recipients[rows, slot]
            before = combat.hp[rows, slot]
            after = torch.clamp(before - combat.damage[rows, source_slot], min=0.0)
            combat.hp[rows, slot] = torch.where(valid, after, before)
            dealt = torch.where(valid, before - after, 0.0)
            died = valid & combat.alive[rows, slot] & (after <= 0.0)
            combat.alive[rows, slot] &= ~died
            damage_total[rows, slot] += dealt
            died_total[rows, slot] |= died
            unsupported_death |= died & ~working.death_payload_supported[rows, slot]
            event(
                valid,
                RuntimeEventOpcode.DAMAGE,
                combat.entity_id[rows, source_slot],
                combat.entity_id[rows, slot],
                dealt,
            )
            event(
                died,
                RuntimeEventOpcode.DEATH,
                combat.entity_id[rows, source_slot],
                combat.entity_id[rows, slot],
            )

        survivors = (
            land_now[:, None]
            & combat.present
            & combat.alive
            & ((combat.kind == 0) | (combat.kind == 1))
            & (combat.owner != combat.owner[rows, source_slot, None])
            & plane
            & overlap
            & working.status_receivable[rows, source_slot]
        )
        status_order = torch.argsort(
            torch.where(
                survivors,
                combat.entity_id,
                torch.full_like(combat.entity_id, torch.iinfo(torch.int64).max),
            ),
            dim=1,
            stable=True,
        )
        duration = working.catalog.freeze_duration_ms[card].to(torch.float64) / 1_000.0
        status_mask = torch.zeros_like(survivors)
        for target_rank in range(count):
            slot = status_order[:, target_rank]
            valid = survivors[rows, slot]
            speculative.status.stun_timer[rows, slot] = torch.where(
                valid,
                torch.maximum(speculative.status.stun_timer[rows, slot], duration),
                speculative.status.stun_timer[rows, slot],
            )
            status_mask[rows, slot] |= valid
            stunned_total[rows, slot] |= valid
            event(
                valid,
                RuntimeEventOpcode.STATUS,
                combat.entity_id[rows, source_slot],
                combat.entity_id[rows, slot],
                duration,
            )
        apply_stun_interrupt_(
            TensorCombatClockPlanes(
                combat.attack_cooldown,
                combat.target_slot,
                combat.attack_windup_active,
                combat.attack_preload_blocked,
                combat.has_attacked_once,
            ),
            status_applied=status_mask,
            hit_speed_ms=combat.hit_speed_ms,
        )
        source_id = combat.entity_id[rows, source_slot]
        self_amount = combat.hp[rows, source_slot].clone()
        event(land_now, RuntimeEventOpcode.DAMAGE, source_id, source_id, self_amount)
        event(land_now, RuntimeEventOpcode.DEATH, source_id, source_id)
        combat.hp[rows, source_slot] = torch.where(
            land_now, 0.0, combat.hp[rows, source_slot]
        )
        combat.alive[rows, source_slot] &= ~land_now
        combat.target_slot[rows, source_slot] = torch.where(
            land_now, -1, combat.target_slot[rows, source_slot]
        )
        working.jump_active[rows, source_slot] &= ~land_now
        working.jump_target_id[rows, source_slot] = torch.where(
            land_now, 0, working.jump_target_id[rows, source_slot]
        )
        working.detonated[rows, source_slot] |= land_now
        self_died[rows, source_slot] |= land_now

    if event_valid:
        valid = torch.stack(event_valid, dim=1)
        opcode = torch.stack(event_opcode, dim=1)
        source = torch.stack(event_source, dim=1)
        target = torch.stack(event_target, dim=1)
        amount = torch.stack(event_amount, dim=1)
    else:
        valid = torch.zeros((batch, 0), dtype=torch.bool, device=device)
        opcode = source = target = torch.zeros(
            (batch, 0), dtype=torch.int64, device=device
        )
        amount = torch.zeros((batch, 0), dtype=torch.float64, device=device)
    additions = valid.sum(dim=1, dtype=torch.int64)
    overflow = (
        speculative.events.count.to(torch.int64) + additions
        > speculative.events.capacity
    )
    committed = runtime.supported & ~unsupported_death & ~overflow
    reason = torch.where(
        unsupported_death,
        int(IceSpiritReason.UNSUPPORTED_DEATH_PAYLOAD),
        torch.where(overflow, int(IceSpiritReason.EVENT_CAPACITY), 0),
    ).to(torch.int16)
    speculative.events.append(
        phase=TickPhase.MOVEMENT,
        opcode=opcode,
        valid=valid & committed[:, None],
        source_id=source,
        target_id=target,
        amount=amount,
    )
    speculative.battle.entity_x_units.copy_(combat.x_units.to(torch.int32))
    speculative.battle.entity_y_units.copy_(combat.y_units.to(torch.int32))
    speculative.battle.entity_hp.copy_(combat.hp)
    speculative.battle.entity_active.copy_(combat.alive)
    speculative.battle.entity_hp_integer_kind &= ~(damage_total > 0.0)
    speculative.phases.target_slot.copy_(combat.target_slot)
    speculative.phases.death_pending |= speculative.entity_pool.active & ~combat.alive
    _copy_rows(runtime.battle, speculative.battle, committed)
    _copy_rows(runtime.status, speculative.status, committed)
    _copy_rows(runtime.phases, speculative.phases, committed)
    _copy_rows(runtime.events, speculative.events, committed)
    _copy_rows(state.combat, working.combat, committed)
    for descriptor in fields(state):
        if descriptor.name in {"catalog", "combat"}:
            continue
        getattr(state, descriptor.name)[committed] = getattr(working, descriptor.name)[
            committed
        ]
    runtime.mark_dirty(
        committed & (jumped | landed).any(dim=1), phase=TickPhase.MOVEMENT
    )
    return IceSpiritStepResult(
        committed,
        reason,
        acquired & committed[:, None],
        jumped & committed[:, None],
        landed & committed[:, None],
        state.jump_active & source_mask,
        torch.where(committed[:, None], damage_total, 0.0),
        died_total & committed[:, None],
        stunned_total & committed[:, None],
        self_died & committed[:, None],
    )


__all__ = [
    "IceSpiritReason",
    "IceSpiritStepResult",
    "TensorIceSpiritCatalog",
    "TensorIceSpiritState",
    "step_ice_spirit_lifecycle_",
]
