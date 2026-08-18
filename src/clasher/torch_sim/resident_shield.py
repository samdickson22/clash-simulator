"""Retained whole-hit Shield lifecycle and stationary combat composition."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.battle import BattleState
from clasher.data import CardDataLoader

from .catalog import MECHANIC_OPCODE, TensorCardCatalog
from .combat import CombatStepResult, StationaryCombatState, step_stationary_combat_
from .combat_adapter import project_stationary_combat
from .runtime_mechanics import MechanicHitResult, TensorRuntimeMechanics
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


class ShieldLifecycleReason(IntEnum):
    NONE = 0
    UNSUPPORTED_PAYLOAD = 1
    EVENT_CAPACITY = 2


@dataclass(frozen=True)
class TensorResidentShieldCatalog:
    """Exact direct-only Shield payloads admitted by the resident engine."""

    supported: torch.Tensor
    initial_integer_kind: torch.Tensor

    @classmethod
    def compile(
        cls,
        cards: TensorCardCatalog,
        loader: CardDataLoader,
    ) -> TensorResidentShieldCatalog:
        supported = torch.zeros(len(cards.names), dtype=torch.bool, device=cards.device)
        integer_kind = torch.zeros_like(supported)
        definitions = loader.load_card_definitions()
        shield_opcode = MECHANIC_OPCODE["Shield"]
        for card_id, name in enumerate(cards.names[1:], start=1):
            definition = definitions.get(name)
            stats = loader.get_card(name)
            if definition is None or stats is None:
                continue
            operations = cards.mechanic_opcode[card_id]
            single_shield = bool(
                int(cards.mechanic_count[card_id].item()) == 1
                and int(operations[0].item()) == shield_opcode
                and int(cards.effect_count[card_id].item()) == 0
            )
            shield = next(
                (
                    mechanic
                    for mechanic in definition.mechanics
                    if type(mechanic).__name__ == "Shield"
                ),
                None,
            )
            direct_only = bool(
                not getattr(stats, "projectile_data", None)
                and not getattr(stats, "projectile_speed", 0)
                and float(getattr(stats, "area_damage_radius", 0.0) or 0.0) <= 0.0
                and int(getattr(stats, "charge_range", 0) or 0) <= 0
                and float(
                    getattr(stats, "scaled_damage_special", 0.0)
                    or getattr(stats, "damage_special", 0.0)
                    or 0.0
                )
                <= 0.0
            )
            supported[card_id] = single_shield and shield is not None and direct_only
            # Shield.on_attach always stores the scaled initial value as int.
            integer_kind[card_id] = shield is not None
        return cls(supported, integer_kind)


@dataclass(frozen=True)
class ShieldDamageInputs:
    valid: torch.Tensor
    source_slot: torch.Tensor
    target_slot: torch.Tensor
    amount: torch.Tensor
    area: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        width: int,
        *,
        device: str | torch.device = "cpu",
    ) -> ShieldDamageInputs:
        shape = (batch_size, width)
        return cls(
            torch.zeros(shape, dtype=torch.bool, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.float64, device=device),
            torch.zeros(shape, dtype=torch.bool, device=device),
        )


@dataclass
class TensorShieldLifecycleState:
    mechanics: TensorRuntimeMechanics
    combat: StationaryCombatState
    initialized_entity_id: torch.Tensor
    shield_integer_kind: torch.Tensor
    row_supported: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.initialized_entity_id.device

    @property
    def batch_size(self) -> int:
        return int(self.initialized_entity_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.initialized_entity_id.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorShieldLifecycleState:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match shield runtime")
        mechanics = TensorRuntimeMechanics.from_battles(runtime, battles)
        combat = project_stationary_combat(
            battles,
            runtime.catalog,
            capacity=runtime.max_entities,
            device=runtime.device,
        ).state
        combat.ordinary_combat_supported.fill_(True)
        integer_kind = torch.zeros_like(runtime.entity_pool.active)
        supported = torch.ones(
            runtime.batch_size, dtype=torch.bool, device=runtime.device
        )
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                operations = tuple(type(item).__name__ for item in entity.mechanics)
                supported[row] &= all(name == "Shield" for name in operations)
                shields = [
                    item for item in entity.mechanics if type(item).__name__ == "Shield"
                ]
                if shields:
                    integer_kind[row, slot] = (
                        type(vars(shields[0])["current_shield"]) is int
                    )
                # Projectile, area-attack, charge, and special movers remain
                # valid recipients but are not admitted as generated sources.
                generated_source = (
                    bool(getattr(entity.card_stats, "projectile_data", None))
                    or float(
                        getattr(entity.card_stats, "area_damage_radius", 0.0) or 0.0
                    )
                    > 0.0
                    or bool(getattr(entity.card_stats, "charge_range", 0))
                )
                if generated_source:
                    combat.combat_enabled[row, slot] = False
        return cls(
            mechanics,
            combat,
            runtime.battle.entity_id.clone(),
            integer_kind,
            supported,
        )

    def clone(self) -> TensorShieldLifecycleState:
        return type(self)(
            self.mechanics.clone(),
            _clone_combat(self.combat),
            self.initialized_entity_id.clone(),
            self.shield_integer_kind.clone(),
            self.row_supported.clone(),
        )

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorShieldLifecycleState:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        return type(self)(
            self.mechanics.fork(indices),
            _select_combat(self.combat, indices),
            self.initialized_entity_id.index_select(0, indices).clone(),
            self.shield_integer_kind.index_select(0, indices).clone(),
            self.row_supported.index_select(0, indices).clone(),
        )

    def reset_rows_(
        self,
        rows: torch.Tensor | Sequence[int],
        source: TensorShieldLifecycleState,
        source_rows: torch.Tensor | Sequence[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        selected = (
            destination
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        _copy_rows(self.mechanics, source.mechanics, destination, selected)
        _copy_rows(self.combat, source.combat, destination, selected)
        self.initialized_entity_id[destination] = source.initialized_entity_id[selected]
        self.shield_integer_kind[destination] = source.shield_integer_kind[selected]
        self.row_supported[destination] = source.row_supported[selected]


@dataclass(frozen=True)
class ShieldLifecycleStepResult:
    committed: torch.Tensor
    reason: torch.Tensor
    combat: CombatStepResult
    hits: MechanicHitResult
    generated_hits: torch.Tensor
    external_hits: torch.Tensor
    deployment_completed: torch.Tensor


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


def _copy_rows(
    destination: object,
    source: object,
    rows: torch.Tensor,
    source_rows: torch.Tensor,
) -> None:
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim
            and right.ndim
            and left.shape[0] > int(rows.max().item())
            and right.shape[0] > int(source_rows.max().item())
        ):
            left[rows] = right[source_rows]


def _copy_runtime_rows(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
    source_rows: torch.Tensor,
) -> None:
    for name in ("battle", "entity_pool", "status", "phases", "events"):
        _copy_rows(getattr(destination, name), getattr(source, name), rows, source_rows)
    destination.supported[rows] = source.supported[source_rows]
    destination.dirty[rows] = source.dirty[source_rows]


def _refresh(
    state: TensorShieldLifecycleState,
    runtime: TensorBattleRuntime,
) -> None:
    new = runtime.entity_pool.active & (
        state.initialized_entity_id != runtime.battle.entity_id
    )
    state.mechanics.refresh_new_entities_(runtime)
    state.shield_integer_kind.copy_(
        torch.where(new & state.mechanics.has_shield, True, state.shield_integer_kind)
    )
    state.initialized_entity_id.copy_(runtime.battle.entity_id)
    combat = state.combat
    character = runtime.entity_pool.active & (
        (runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1)
    )
    combat.present.copy_(character)
    combat.entity_id.copy_(runtime.battle.entity_id)
    combat.owner.copy_(runtime.battle.entity_player)
    combat.kind.copy_(runtime.battle.entity_kind)
    combat.x_units.copy_(runtime.battle.entity_x_units)
    combat.y_units.copy_(runtime.battle.entity_y_units)
    combat.hp.copy_(runtime.battle.entity_hp)
    combat.max_hp.copy_(runtime.battle.entity_max_hp)
    combat.alive.copy_(runtime.battle.entity_active & character)
    combat.deploy_remaining.copy_(runtime.battle.entity_deploy_delay)
    combat.stunned.copy_(runtime.status.stun_timer > 1e-9)
    combat.last_attack_time.copy_(runtime.battle.entity_last_attack_time)
    combat.ordinary_combat_supported.fill_(True)


def _empty_hit_result(
    batch: int, width: int, device: torch.device
) -> MechanicHitResult:
    shape = (batch, width)
    return MechanicHitResult(
        torch.zeros(shape, dtype=torch.float64, device=device),
        torch.zeros(shape, dtype=torch.bool, device=device),
        torch.zeros(shape, dtype=torch.bool, device=device),
        torch.zeros(shape, dtype=torch.bool, device=device),
        torch.zeros(shape, dtype=torch.bool, device=device),
    )


def step_shield_lifecycle_(
    state: TensorShieldLifecycleState,
    runtime: TensorBattleRuntime,
    incoming: ShieldDamageInputs | None = None,
    *,
    dt_ms: int = 50,
) -> ShieldLifecycleStepResult:
    if dt_ms != 50:
        raise ValueError("exact Shield lifecycle currently requires 50 ms")
    external_width = 0 if incoming is None else incoming.valid.shape[1]
    worst = state.max_entities + external_width
    event_free = runtime.events.capacity - runtime.events.count.to(torch.int64)
    reason = torch.zeros(state.batch_size, dtype=torch.int16, device=state.device)
    reason = torch.where(
        ~state.row_supported,
        torch.full_like(reason, ShieldLifecycleReason.UNSUPPORTED_PAYLOAD),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (2 * worst > event_free),
        torch.full_like(reason, ShieldLifecycleReason.EVENT_CAPACITY),
        reason,
    )
    committed = reason == 0
    selected = torch.nonzero(committed, as_tuple=False).flatten()
    empty_combat = CombatStepResult(
        attacked=torch.zeros_like(state.combat.present),
        projectile_launched=torch.zeros_like(state.combat.present),
        damage_received=torch.zeros_like(state.combat.hp),
        target_before=state.combat.target_slot.clone(),
        target_after=state.combat.target_slot.clone(),
    )
    if selected.numel() == 0:
        return ShieldLifecycleStepResult(
            committed,
            reason,
            empty_combat,
            _empty_hit_result(state.batch_size, worst, state.device),
            torch.zeros_like(state.combat.present),
            torch.zeros(
                (state.batch_size, external_width),
                dtype=torch.bool,
                device=state.device,
            ),
            torch.zeros_like(state.combat.present),
        )
    working = state.fork(selected)
    speculative = runtime.fork(selected)
    speculative.battle.time += dt_ms / 1_000.0
    speculative.battle.tick += 1
    speculative.battle.dt.fill_(dt_ms / 1_000.0)
    speculative.battle.tick_milliseconds.fill_(dt_ms)
    _refresh(working, speculative)
    hp_before = working.combat.hp.clone()
    alive_before = working.combat.alive.clone()
    combat_result = step_stationary_combat_(working.combat, dt_ms / 1_000.0)
    generated = (
        combat_result.attacked
        & ~combat_result.projectile_launched
        & (working.combat.target_slot >= 0)
    )
    working.combat.hp.copy_(hp_before)
    working.combat.alive.copy_(alive_before)
    speculative.battle.entity_hp.copy_(hp_before)
    speculative.battle.entity_active.copy_(alive_before)
    slots = torch.arange(working.max_entities, device=state.device)[None, :].expand(
        selected.numel(), -1
    )
    source = slots
    target = working.combat.target_slot.clamp_min(0)
    amount = working.combat.damage
    valid = generated
    external_valid = torch.zeros(
        (selected.numel(), external_width), dtype=torch.bool, device=state.device
    )
    if incoming is not None:
        external_valid = incoming.valid.index_select(0, selected)
        source = torch.cat((source, incoming.source_slot.index_select(0, selected)), 1)
        target = torch.cat((target, incoming.target_slot.index_select(0, selected)), 1)
        amount = torch.cat((amount, incoming.amount.index_select(0, selected)), 1)
        valid = torch.cat((valid, external_valid), 1)
    source_ids = speculative.battle.entity_id.gather(
        1, source.clamp(0, working.max_entities - 1)
    )
    lane = torch.arange(valid.shape[1], device=state.device)[None, :]
    order = torch.argsort(
        torch.where(
            valid,
            source_ids * (valid.shape[1] + 1) + lane,
            torch.full_like(source_ids, torch.iinfo(torch.int64).max),
        ),
        dim=1,
        stable=True,
    )
    source = source.gather(1, order)
    target = target.gather(1, order)
    amount = amount.gather(1, order)
    valid = valid.gather(1, order)
    hit = working.mechanics.resolve_attack_hits_(
        speculative,
        source_slot=source,
        target_slot=target,
        incoming_damage=amount,
        valid=valid,
        status_eligible=False,
    )
    rows = torch.arange(selected.numel(), device=state.device)[:, None]
    changed = torch.zeros_like(speculative.battle.entity_hp_integer_kind)
    changed.scatter_reduce_(
        1,
        target.clamp(0, working.max_entities - 1),
        valid & (hit.hitpoint_damage > 0.0),
        reduce="amax",
        include_self=True,
    )
    speculative.battle.entity_hp_integer_kind &= ~changed
    absorbed = torch.zeros_like(working.shield_integer_kind)
    absorbed.scatter_reduce_(
        1,
        target.clamp(0, working.max_entities - 1),
        hit.shield_absorbed,
        reduce="amax",
        include_self=True,
    )
    working.shield_integer_kind &= ~absorbed
    speculative.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.DEATH,
        valid=hit.target_died,
        source_id=speculative.battle.entity_id.gather(
            1, source.clamp(0, working.max_entities - 1)
        ),
        target_id=speculative.battle.entity_id.gather(
            1, target.clamp(0, working.max_entities - 1)
        ),
    )
    previous_delay = speculative.battle.entity_deploy_delay.clone()
    deploying = (
        speculative.entity_pool.active
        & speculative.battle.entity_active
        & (previous_delay > 0.0)
    )
    speculative.battle.entity_deploy_delay.copy_(
        torch.where(
            deploying,
            torch.clamp(previous_delay - dt_ms / 1_000.0, min=0.0),
            previous_delay,
        )
    )
    completed = deploying & (speculative.battle.entity_deploy_delay <= 1e-9)
    speculative.battle.entity_placement_pending &= ~completed
    speculative.battle.entity_spawn_hook_pending &= ~completed
    speculative.battle.entity_spawn_hook_fired |= completed
    working.combat.deploy_remaining.copy_(speculative.battle.entity_deploy_delay)
    working.combat.hp.copy_(speculative.battle.entity_hp)
    working.combat.alive.copy_(speculative.battle.entity_active)
    speculative.battle.entity_last_attack_time.copy_(working.combat.last_attack_time)
    speculative.phases.target_slot.copy_(working.combat.target_slot)
    dead = speculative.entity_pool.active & ~speculative.battle.entity_active
    speculative.entity_pool.cleanup(dead)
    for owner in (speculative.battle, speculative.status, speculative.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == dead.shape
            ):
                value[dead] = 0
    source_rows = torch.arange(selected.numel(), device=state.device)
    state.reset_rows_(selected, working, source_rows)
    _copy_runtime_rows(runtime, speculative, selected, source_rows)
    generated_full = torch.zeros_like(state.combat.present)
    generated_full[selected] = generated
    external_full = torch.zeros(
        (state.batch_size, external_width), dtype=torch.bool, device=state.device
    )
    external_full[selected] = external_valid
    completed_full = torch.zeros_like(state.combat.present)
    completed_full[selected] = completed
    # Return hit lanes in sorted transaction order; rejected rows are zero.
    hit_full = _empty_hit_result(state.batch_size, valid.shape[1], state.device)
    for name in (
        "hitpoint_damage",
        "shield_absorbed",
        "shield_broken",
        "status_dispatched",
        "target_died",
    ):
        getattr(hit_full, name)[selected] = getattr(hit, name)
    del rows
    return ShieldLifecycleStepResult(
        committed,
        reason,
        combat_result,
        hit_full,
        generated_full,
        external_full,
        completed_full,
    )


__all__ = [
    "ShieldDamageInputs",
    "ShieldLifecycleReason",
    "ShieldLifecycleStepResult",
    "TensorResidentShieldCatalog",
    "TensorShieldLifecycleState",
    "step_shield_lifecycle_",
]
