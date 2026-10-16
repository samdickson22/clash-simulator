"""Retained multi-tick chain impacts for serialized electric mechanics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.battle import BattleState

from .combat import StationaryCombatState
from .combat_adapter import project_stationary_combat
from .combat_clock_transitions import TensorCombatClockPlanes, apply_stun_interrupt_
from .combat_mechanics import (
    CombatMechanicOpcode,
    TensorCombatMechanicCatalog,
    TensorMechanicWorld,
    select_chain_targets,
)
from .movement import integer_sqrt_tensor, normalized_vector_units, trunc_div_tensor
from .runtime_state import (
    RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


class ChainImpactReason(IntEnum):
    NONE = 0
    OBJECT_CAPACITY = 1
    EVENT_CAPACITY = 2
    UNSUPPORTED_DEATH_PAYLOAD = 3


@dataclass(frozen=True)
class ChainImpactInputs:
    valid: torch.Tensor
    source_slot: torch.Tensor
    primary_slot: torch.Tensor
    primary_damage_applied: torch.Tensor
    source_death_applied: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        width: int,
        *,
        device: str | torch.device = "cpu",
    ) -> ChainImpactInputs:
        shape = (batch_size, width)
        return cls(
            valid=torch.zeros(shape, dtype=torch.bool, device=device),
            source_slot=torch.zeros(shape, dtype=torch.int64, device=device),
            primary_slot=torch.zeros(shape, dtype=torch.int64, device=device),
            primary_damage_applied=torch.zeros(shape, dtype=torch.bool, device=device),
            source_death_applied=torch.zeros(shape, dtype=torch.bool, device=device),
        )


@dataclass
class TensorChainImpactState:
    catalog: TensorCombatMechanicCatalog
    combat: StationaryCombatState
    entity_card: torch.Tensor
    active: torch.Tensor
    object_id: torch.Tensor
    source_id: torch.Tensor
    owner: torch.Tensor
    mechanic_opcode: torch.Tensor
    position_units: torch.Tensor
    origin_units: torch.Tensor
    current_target_id: torch.Tensor
    remaining_bounces: torch.Tensor
    hop_remaining_ms: torch.Tensor
    fixed_hop_ms: torch.Tensor
    speed_units_per_tick: torch.Tensor
    chain_range_units: torch.Tensor
    damage: torch.Tensor
    stun_duration_ms: torch.Tensor
    visited: torch.Tensor
    effect_receivable: torch.Tensor
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

    @property
    def max_chains(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        max_chains: int = 16,
    ) -> TensorChainImpactState:
        if len(battles) != runtime.batch_size or max_chains < 1:
            raise ValueError("invalid chain runtime dimensions")
        catalog = TensorCombatMechanicCatalog.compile(
            battles[0].card_loader,
            runtime.catalog.names[1:],
            device=runtime.device,
        )
        definitions = battles[0].card_loader.load_card_definitions()
        for name, card_id in catalog.name_to_id.items():
            if not name:
                continue
            stats = battles[0].card_loader.get_card(name)
            if stats is None:
                continue
            projectile = getattr(stats, "projectile_data", {}) or {}
            for operation in definitions[name].mechanics:
                mechanic_name = type(operation).__name__
                if mechanic_name not in {
                    "ElectroDragonChainLightning",
                    "ElectroSpiritChain",
                }:
                    continue
                opcode = (
                    CombatMechanicOpcode.ELECTRO_DRAGON_CHAIN
                    if mechanic_name == "ElectroDragonChainLightning"
                    else CombatMechanicOpcode.ELECTRO_SPIRIT_CHAIN
                )
                slot, present = catalog.mechanic_slot(
                    torch.tensor([card_id], device=runtime.device), opcode
                )
                if not bool(present[0].item()):
                    continue
                mechanic_slot = int(slot[0].item())
                total = int(
                    projectile.get(
                        "chainedHitCount",
                        getattr(operation, "max_targets", 0)
                        or getattr(operation, "max_bounces", 0) + 1,
                    )
                    or 1
                )
                catalog.chain_count[card_id, mechanic_slot] = max(0, total - 1)
                catalog.chain_range_units[card_id, mechanic_slot] = int(
                    projectile.get("chainedHitRadius", 4_000) or 4_000
                )
                catalog.chain_stun_ms[card_id, mechanic_slot] = int(
                    projectile.get(
                        "buffTime", getattr(operation, "stun_duration_ms", 0)
                    )
                    or 0
                )
                catalog.chain_speed_units[card_id, mechanic_slot] = int(
                    projectile.get("speed", 2_000) or 2_000
                )
        combat = project_stationary_combat(
            battles,
            runtime.catalog,
            capacity=runtime.max_entities,
            device=runtime.device,
        ).state
        name_to_chain = torch.tensor(
            [
                catalog.name_to_id.get(name, 0) if name else 0
                for name in runtime.battle.card_names
            ],
            dtype=torch.int64,
            device=runtime.device,
        )
        entity_card = name_to_chain[runtime.battle.entity_card]
        batch = runtime.batch_size
        entity_shape = runtime.battle.entity_id.shape
        chain_shape = (batch, max_chains)
        effect = torch.zeros(
            (*entity_shape, runtime.max_entities),
            dtype=torch.bool,
            device=runtime.device,
        )
        death_supported = torch.ones(
            entity_shape, dtype=torch.bool, device=runtime.device
        )
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                entity_slot = slots[entity_id]
                death_supported[row, entity_slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )
            for source_id, source in battle.entities.items():
                source_slot = slots[source_id]
                source_kind = getattr(source.card_stats, "name", None)
                for target_id, target in battle.entities.items():
                    effect[row, source_slot, slots[target_id]] = (
                        target.can_receive_effect(source_kind)
                    )
        zeros_i64 = torch.zeros(chain_shape, dtype=torch.int64, device=runtime.device)
        return cls(
            catalog=catalog,
            combat=combat,
            entity_card=entity_card,
            active=torch.zeros(chain_shape, dtype=torch.bool, device=runtime.device),
            object_id=zeros_i64.clone(),
            source_id=zeros_i64.clone(),
            owner=torch.zeros(chain_shape, dtype=torch.int8, device=runtime.device),
            mechanic_opcode=torch.zeros(
                chain_shape, dtype=torch.int16, device=runtime.device
            ),
            position_units=torch.zeros(
                (*chain_shape, 2), dtype=torch.int64, device=runtime.device
            ),
            origin_units=torch.zeros(
                (*chain_shape, 2), dtype=torch.int64, device=runtime.device
            ),
            current_target_id=zeros_i64.clone(),
            remaining_bounces=torch.zeros(
                chain_shape, dtype=torch.int16, device=runtime.device
            ),
            hop_remaining_ms=zeros_i64.clone(),
            fixed_hop_ms=zeros_i64.clone(),
            speed_units_per_tick=zeros_i64.clone(),
            chain_range_units=zeros_i64.clone(),
            damage=torch.zeros(chain_shape, dtype=torch.float64, device=runtime.device),
            stun_duration_ms=zeros_i64.clone(),
            visited=torch.zeros(
                (*chain_shape, runtime.max_entities),
                dtype=torch.bool,
                device=runtime.device,
            ),
            effect_receivable=effect,
            death_payload_supported=death_supported,
        )

    def clone(self) -> TensorChainImpactState:
        cloned = object.__new__(type(self))
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if descriptor.name == "catalog":
                setattr(cloned, descriptor.name, value)
            elif descriptor.name == "combat":
                setattr(cloned, descriptor.name, _clone_tensor_dataclass(value))
            else:
                setattr(cloned, descriptor.name, value.clone())
        return cloned

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorChainImpactState:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        cloned = self.clone()
        for descriptor in fields(self):
            if descriptor.name == "catalog":
                continue
            value = getattr(self, descriptor.name)
            if descriptor.name == "combat":
                setattr(
                    cloned, descriptor.name, _select_tensor_dataclass(value, indices)
                )
            else:
                setattr(cloned, descriptor.name, value.index_select(0, indices).clone())
        return cloned

    def reset_rows_(
        self,
        rows: torch.Tensor | Sequence[int],
        source: TensorChainImpactState,
        source_rows: torch.Tensor | Sequence[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        selected = (
            destination
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        for descriptor in fields(self):
            if descriptor.name == "catalog":
                continue
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if descriptor.name == "combat":
                for item in fields(left):
                    getattr(left, item.name)[destination] = getattr(right, item.name)[
                        selected
                    ]
            else:
                left[destination] = right[selected]


@dataclass(frozen=True)
class ChainImpactStepResult:
    committed: torch.Tensor
    reason: torch.Tensor
    materialized: torch.Tensor
    impacted: torch.Tensor
    damage: torch.Tensor
    died: torch.Tensor
    stunned: torch.Tensor
    self_died: torch.Tensor


def _clone_tensor_dataclass(
    value: StationaryCombatState,
) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            descriptor.name: getattr(value, descriptor.name).clone()
            for descriptor in fields(value)  # type: ignore[arg-type]
        }
    )


def _select_tensor_dataclass(
    value: StationaryCombatState, rows: torch.Tensor
) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            descriptor.name: getattr(value, descriptor.name)
            .index_select(0, rows)
            .clone()
            for descriptor in fields(value)  # type: ignore[arg-type]
        }
    )


def _copy_rows(destination: object, source: object, mask: torch.Tensor) -> None:
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor):
            left[mask] = right[mask]


def _world(
    state: TensorChainImpactState, source_slot: torch.Tensor
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
        effect_receivable=state.effect_receivable[rows, source_slot],
    )


def step_chain_impacts_(
    runtime: TensorBattleRuntime,
    state: TensorChainImpactState,
    impacts: ChainImpactInputs | None = None,
    *,
    dt_ms: torch.Tensor | int = 50,
) -> ChainImpactStepResult:
    """Materialize committed primary impacts, then advance every chain object."""

    if runtime.device != state.device:
        raise ValueError("chain runtime device mismatch")
    working = state.clone()
    speculative = runtime.clone()
    combat = working.combat
    combat.hp.copy_(speculative.battle.entity_hp)
    combat.alive.copy_(speculative.battle.entity_active)
    combat.x_units.copy_(speculative.battle.entity_x_units.to(torch.int64))
    combat.y_units.copy_(speculative.battle.entity_y_units.to(torch.int64))
    batch = state.batch_size
    entities = state.max_entities
    chains = state.max_chains
    device = state.device
    rows = torch.arange(batch, device=device)
    delta_ms = torch.broadcast_to(
        torch.as_tensor(dt_ms, dtype=torch.int64, device=device), (batch,)
    )
    materialized = torch.zeros((batch, chains), dtype=torch.bool, device=device)
    impacted = torch.zeros_like(materialized)
    damage_total = torch.zeros_like(combat.hp)
    died_total = torch.zeros_like(combat.alive)
    stunned_total = torch.zeros_like(combat.alive)
    self_died = torch.zeros_like(combat.alive)
    unsupported_death = torch.zeros(batch, dtype=torch.bool, device=device)
    object_overflow = torch.zeros(batch, dtype=torch.bool, device=device)
    ev_valid: list[torch.Tensor] = []
    ev_opcode: list[torch.Tensor] = []
    ev_source: list[torch.Tensor] = []
    ev_target: list[torch.Tensor] = []
    ev_amount: list[torch.Tensor] = []

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
            torch.zeros(batch, dtype=torch.float64, device=device)
            if amount is None
            else amount
        )

    if impacts is not None and impacts.valid.numel():
        width = impacts.valid.shape[1]
        for lane in range(width):
            source_slot = impacts.source_slot[:, lane].clamp(0, entities - 1)
            primary_slot = impacts.primary_slot[:, lane].clamp(0, entities - 1)
            card = working.entity_card[rows, source_slot]
            dragon_slot, dragon = working.catalog.mechanic_slot(
                card, CombatMechanicOpcode.ELECTRO_DRAGON_CHAIN
            )
            spirit_slot, spirit = working.catalog.mechanic_slot(
                card, CombatMechanicOpcode.ELECTRO_SPIRIT_CHAIN
            )
            valid = impacts.valid[:, lane] & (dragon | spirit) & runtime.supported
            free = ~working.active
            has_free = free.any(dim=1)
            object_overflow |= valid & ~has_free
            valid &= has_free
            chain_slot = free.to(torch.int64).argmax(dim=1)
            mechanic_slot = torch.where(spirit, spirit_slot, dragon_slot)
            primary_id = combat.entity_id[rows, primary_slot]
            source_id = combat.entity_id[rows, source_slot]
            primary_valid = valid & combat.alive[rows, primary_slot]
            spirit_primary = (
                primary_valid & spirit & ~impacts.primary_damage_applied[:, lane]
            )
            before = combat.hp[rows, primary_slot]
            after = torch.clamp(before - combat.damage[rows, source_slot], min=0.0)
            combat.hp[rows, primary_slot] = torch.where(spirit_primary, after, before)
            dealt = torch.where(spirit_primary, before - after, 0.0)
            died = spirit_primary & combat.alive[rows, primary_slot] & (after <= 0.0)
            combat.alive[rows, primary_slot] &= ~died
            damage_total[rows, primary_slot] += dealt
            died_total[rows, primary_slot] |= died
            unsupported_death |= (
                died & ~working.death_payload_supported[rows, primary_slot]
            )
            event(
                spirit_primary, RuntimeEventOpcode.DAMAGE, source_id, primary_id, dealt
            )
            event(died, RuntimeEventOpcode.DEATH, source_id, primary_id)
            primary_stun = spirit_primary & ~died
            duration = (
                working.catalog.chain_stun_ms[card, mechanic_slot].to(torch.float64)
                / 1_000.0
            )
            speculative.status.stun_timer[rows, primary_slot] = torch.where(
                primary_stun,
                torch.maximum(
                    speculative.status.stun_timer[rows, primary_slot], duration
                ),
                speculative.status.stun_timer[rows, primary_slot],
            )
            stun_mask = torch.zeros_like(combat.alive)
            stun_mask[rows, primary_slot] = primary_stun
            apply_stun_interrupt_(
                TensorCombatClockPlanes(
                    combat.attack_cooldown,
                    combat.target_slot,
                    combat.attack_windup_active,
                    combat.attack_preload_blocked,
                    combat.has_attacked_once,
                ),
                status_applied=stun_mask,
                hit_speed_ms=combat.hit_speed_ms,
            )
            stunned_total[rows, primary_slot] |= primary_stun
            event(
                primary_stun, RuntimeEventOpcode.STATUS, source_id, primary_id, duration
            )

            self_kill = valid & spirit & ~impacts.source_death_applied[:, lane]
            self_amount = combat.hp[rows, source_slot].clone()
            combat.hp[rows, source_slot] = torch.where(
                self_kill, 0.0, combat.hp[rows, source_slot]
            )
            combat.alive[rows, source_slot] &= ~self_kill
            self_died[rows, source_slot] |= self_kill
            event(
                self_kill, RuntimeEventOpcode.DAMAGE, source_id, source_id, self_amount
            )
            event(self_kill, RuntimeEventOpcode.DEATH, source_id, source_id)

            slot_index = (rows, chain_slot)
            new_id = speculative.entity_pool.next_entity_id.clone()
            speculative.entity_pool.next_entity_id += valid.to(torch.int64)
            working.active[slot_index] |= valid
            working.object_id[slot_index] = torch.where(
                valid, new_id, working.object_id[slot_index]
            )
            working.source_id[slot_index] = torch.where(
                valid, source_id, working.source_id[slot_index]
            )
            working.owner[slot_index] = torch.where(
                valid, combat.owner[rows, source_slot], working.owner[slot_index]
            )
            opcode = torch.where(
                spirit,
                int(CombatMechanicOpcode.ELECTRO_SPIRIT_CHAIN),
                int(CombatMechanicOpcode.ELECTRO_DRAGON_CHAIN),
            ).to(torch.int16)
            working.mechanic_opcode[slot_index] = torch.where(
                valid, opcode, working.mechanic_opcode[slot_index]
            )
            primary_position = torch.stack(
                (
                    combat.x_units[rows, primary_slot],
                    combat.y_units[rows, primary_slot],
                ),
                dim=1,
            )
            working.position_units[slot_index] = torch.where(
                valid[:, None], primary_position, working.position_units[slot_index]
            )
            working.origin_units[slot_index] = torch.where(
                valid[:, None], primary_position, working.origin_units[slot_index]
            )
            working.remaining_bounces[slot_index] = torch.where(
                valid,
                working.catalog.chain_count[card, mechanic_slot],
                working.remaining_bounces[slot_index],
            )
            working.fixed_hop_ms[slot_index] = torch.where(
                valid,
                working.catalog.chain_interval_ms[card, mechanic_slot],
                working.fixed_hop_ms[slot_index],
            )
            working.speed_units_per_tick[slot_index] = torch.where(
                valid,
                working.catalog.chain_speed_units[card, mechanic_slot],
                working.speed_units_per_tick[slot_index],
            )
            working.chain_range_units[slot_index] = torch.where(
                valid,
                working.catalog.chain_range_units[card, mechanic_slot],
                working.chain_range_units[slot_index],
            )
            working.damage[slot_index] = torch.where(
                valid,
                combat.damage[rows, source_slot]
                * working.catalog.chain_damage_decay[card, mechanic_slot],
                working.damage[slot_index],
            )
            working.stun_duration_ms[slot_index] = torch.where(
                valid,
                working.catalog.chain_stun_ms[card, mechanic_slot].to(torch.int64),
                working.stun_duration_ms[slot_index],
            )
            working.visited[rows, chain_slot, primary_slot] |= valid
            materialized[rows, chain_slot] |= valid
            event(valid, RuntimeEventOpcode.PROJECTILE, source_id, new_id)

    object_order = torch.argsort(
        torch.where(
            working.active,
            working.object_id,
            torch.full_like(working.object_id, torch.iinfo(torch.int64).max),
        ),
        dim=1,
        stable=True,
    )
    for rank in range(chains):
        slot = object_order[:, rank]
        index = (rows, slot)
        active = working.active[index] & runtime.supported
        source_match = combat.entity_id == working.source_id[index][:, None]
        source_slot = source_match.to(torch.int64).argmax(dim=1)
        current_id = working.current_target_id[index]
        current_match = combat.entity_id == current_id[:, None]
        current_slot = current_match.to(torch.int64).argmax(dim=1)
        current_found = current_match.any(dim=1)
        current_valid = (
            active
            & (current_id > 0)
            & current_found
            & combat.alive[rows, current_slot]
            & combat.targetable[rows, current_slot]
        )
        need_target = (
            active & (current_id == 0) & (working.remaining_bounces[index] > 0)
        )
        selected, selected_valid = select_chain_targets(
            _world(working, source_slot),
            owner=working.owner[index],
            origin_x_units=working.origin_units[index][:, 0],
            origin_y_units=working.origin_units[index][:, 1],
            visited=working.visited[index],
            chain_range_units=working.chain_range_units[index],
            maximum_targets=1,
        )
        acquired = need_target & selected_valid[:, 0]
        selected_id = selected[:, 0]
        selected_match = combat.entity_id == selected_id[:, None]
        selected_slot = selected_match.to(torch.int64).argmax(dim=1)
        working.current_target_id[index] = torch.where(
            acquired, selected_id, current_id
        )
        fixed = working.fixed_hop_ms[index]
        working.hop_remaining_ms[index] = torch.where(
            acquired & (fixed > 0), fixed, working.hop_remaining_ms[index]
        )
        target_slot = torch.where(acquired, selected_slot, current_slot)
        branch_valid = active & ((current_id == 0) | current_valid)
        no_target = need_target & ~acquired
        invalid_flight = active & (current_id > 0) & ~current_valid
        terminate = no_target | invalid_flight
        working.active[index] &= ~terminate
        event(
            terminate,
            RuntimeEventOpcode.DEATH,
            working.object_id[index],
            working.object_id[index],
        )
        moving = branch_valid & (working.current_target_id[index] > 0) & ~terminate
        target_position = torch.stack(
            (combat.x_units[rows, target_slot], combat.y_units[rows, target_slot]),
            dim=1,
        )
        delta = target_position - working.position_units[index]
        distance = integer_sqrt_tensor((delta * delta).sum(dim=1))
        fixed_remaining = working.hop_remaining_ms[index]
        variable_time = trunc_div_tensor(
            distance * 50, working.speed_units_per_tick[index].clamp_min(1)
        )
        time_to_impact = torch.where(fixed > 0, fixed_remaining, variable_time)
        impact = moving & (delta_ms >= time_to_impact)
        partial = moving & ~impact
        fixed_move = trunc_div_tensor(
            delta * delta_ms[:, None], fixed_remaining.clamp_min(1)[:, None]
        )
        variable_work = torch.round(
            working.speed_units_per_tick[index].to(torch.float64)
            * delta_ms.to(torch.float64)
            / 50.0
        ).to(torch.int64)
        variable_move = normalized_vector_units(
            delta, torch.minimum(variable_work, distance)
        )
        move = torch.where((fixed > 0)[:, None], fixed_move, variable_move)
        working.position_units[index] = torch.where(
            impact[:, None],
            target_position,
            torch.where(
                partial[:, None],
                working.position_units[index] + move,
                working.position_units[index],
            ),
        )
        working.hop_remaining_ms[index] = torch.where(
            partial & (fixed > 0),
            torch.clamp(fixed_remaining - delta_ms, min=0),
            working.hop_remaining_ms[index],
        )
        target_id = combat.entity_id[rows, target_slot]
        before = combat.hp[rows, target_slot]
        after = torch.clamp(before - working.damage[index], min=0.0)
        combat.hp[rows, target_slot] = torch.where(impact, after, before)
        dealt = torch.where(impact, before - after, 0.0)
        died = impact & combat.alive[rows, target_slot] & (after <= 0.0)
        combat.alive[rows, target_slot] &= ~died
        damage_total[rows, target_slot] += dealt
        died_total[rows, target_slot] |= died
        unsupported_death |= died & ~working.death_payload_supported[rows, target_slot]
        event(
            impact,
            RuntimeEventOpcode.DAMAGE,
            working.object_id[index],
            target_id,
            dealt,
        )
        event(died, RuntimeEventOpcode.DEATH, working.object_id[index], target_id)
        # ChainLightning applies its status call after damage; retain it even on a lethal hit.
        status = impact
        duration = working.stun_duration_ms[index].to(torch.float64) / 1_000.0
        speculative.status.stun_timer[rows, target_slot] = torch.where(
            status,
            torch.maximum(speculative.status.stun_timer[rows, target_slot], duration),
            speculative.status.stun_timer[rows, target_slot],
        )
        status_mask = torch.zeros_like(combat.alive)
        status_mask[rows, target_slot] = status
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
        stunned_total[rows, target_slot] |= status
        event(
            status,
            RuntimeEventOpcode.STATUS,
            working.object_id[index],
            target_id,
            duration,
        )
        working.visited[rows, slot, target_slot] |= impact
        working.origin_units[index] = torch.where(
            impact[:, None], target_position, working.origin_units[index]
        )
        working.remaining_bounces[index] -= impact.to(torch.int16)
        working.current_target_id[index] = torch.where(
            impact, 0, working.current_target_id[index]
        )
        working.hop_remaining_ms[index] = torch.where(
            impact, 0, working.hop_remaining_ms[index]
        )
        finished = impact & (working.remaining_bounces[index] <= 0)
        working.active[index] &= ~finished
        impacted[rows, slot] |= impact
        event(
            finished,
            RuntimeEventOpcode.DEATH,
            working.object_id[index],
            working.object_id[index],
        )

    valid = (
        torch.stack(ev_valid, dim=1)
        if ev_valid
        else torch.zeros((batch, 0), dtype=torch.bool, device=device)
    )
    opcode = (
        torch.stack(ev_opcode, dim=1)
        if ev_opcode
        else torch.zeros((batch, 0), dtype=torch.int64, device=device)
    )
    source = torch.stack(ev_source, dim=1) if ev_source else torch.zeros_like(opcode)
    target = torch.stack(ev_target, dim=1) if ev_target else torch.zeros_like(opcode)
    amount = (
        torch.stack(ev_amount, dim=1)
        if ev_amount
        else torch.zeros((batch, 0), dtype=torch.float64, device=device)
    )
    overflow = (
        speculative.events.count.to(torch.int64) + valid.sum(dim=1)
        > speculative.events.capacity
    ) & (
        speculative.events.execution_profile
        == RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG
    )
    committed = runtime.supported & ~object_overflow & ~unsupported_death & ~overflow
    reason = torch.where(
        object_overflow,
        int(ChainImpactReason.OBJECT_CAPACITY),
        torch.where(
            unsupported_death,
            int(ChainImpactReason.UNSUPPORTED_DEATH_PAYLOAD),
            torch.where(overflow, int(ChainImpactReason.EVENT_CAPACITY), 0),
        ),
    ).to(torch.int16)
    speculative.events.append(
        phase=TickPhase.OBJECTS,
        opcode=opcode,
        valid=valid & committed[:, None],
        source_id=source,
        target_id=target,
        amount=amount,
    )
    speculative.battle.entity_hp.copy_(combat.hp)
    speculative.battle.entity_active.copy_(combat.alive)
    speculative.battle.entity_hp_integer_kind &= ~(damage_total > 0)
    speculative.phases.target_slot.copy_(combat.target_slot)
    speculative.phases.death_pending |= speculative.entity_pool.active & ~combat.alive
    _copy_rows(runtime.battle, speculative.battle, committed)
    _copy_rows(runtime.status, speculative.status, committed)
    _copy_rows(runtime.phases, speculative.phases, committed)
    _copy_rows(runtime.events, speculative.events, committed)
    runtime.entity_pool.next_entity_id[committed] = (
        speculative.entity_pool.next_entity_id[committed]
    )
    _copy_rows(state.combat, working.combat, committed)
    for descriptor in fields(state):
        if descriptor.name in {"catalog", "combat"}:
            continue
        getattr(state, descriptor.name)[committed] = getattr(working, descriptor.name)[
            committed
        ]
    runtime.mark_dirty(
        committed & (materialized | impacted).any(dim=1), phase=TickPhase.OBJECTS
    )
    return ChainImpactStepResult(
        committed,
        reason,
        materialized & committed[:, None],
        impacted & committed[:, None],
        torch.where(committed[:, None], damage_total, 0.0),
        died_total & committed[:, None],
        stunned_total & committed[:, None],
        self_died & committed[:, None],
    )


__all__ = [
    "ChainImpactInputs",
    "ChainImpactReason",
    "ChainImpactStepResult",
    "TensorChainImpactState",
    "step_chain_impacts_",
]
