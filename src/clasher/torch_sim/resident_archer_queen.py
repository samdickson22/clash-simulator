"""Retained Champion cloak and direct-projectile lifecycle composition.

The runtime selects cards only through the serialized ``ArcherQueenCloak``
opcode.  It deliberately admits only the radius-zero homing projectile shape
whose complete launch, travel, direct impact, and cloak callbacks are modeled
here.  Other mechanic, effect, splash, piercing, status, or death payloads are
rejected before a row mutates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Any

import torch

from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name

from .catalog import MECHANIC_OPCODE
from .combat import (
    CombatStepResult,
    StationaryCombatState,
    step_stationary_combat_,
)
from .combat_adapter import project_stationary_combat
from .movement import integer_sqrt_tensor, normalized_vector_units
from .runtime_mechanics import TensorRuntimeMechanics
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


class ArcherQueenReason(IntEnum):
    NONE = 0
    UNSUPPORTED_PAYLOAD = 1
    ENTITY_CAPACITY = 2
    PROJECTILE_CAPACITY = 3
    EVENT_CAPACITY = 4


class ArcherQueenEventPayload(IntEnum):
    PROJECTILE_LAUNCHED = 1
    PROJECTILE_IMPACT = 2


@dataclass(frozen=True)
class TensorArcherQueenCatalog:
    supported: torch.Tensor
    projectile_speed_units: torch.Tensor
    projectile_start_radius_units: torch.Tensor
    projectile_y_offset_units: torch.Tensor
    projectile_damage: torch.Tensor

    @classmethod
    def compile(
        cls,
        runtime: TensorBattleRuntime,
        loader: Any,
    ) -> TensorArcherQueenCatalog:
        size = len(runtime.catalog.names)
        device = runtime.device
        supported = torch.zeros(size, dtype=torch.bool, device=device)
        speed = torch.zeros(size, dtype=torch.int64, device=device)
        radius = torch.zeros(size, dtype=torch.int64, device=device)
        y_offset = torch.zeros(size, dtype=torch.int64, device=device)
        damage = torch.zeros(size, dtype=torch.float64, device=device)
        definitions = loader.load_card_definitions()
        cloak_opcode = MECHANIC_OPCODE["ArcherQueenCloak"]
        for card_id, name in enumerate(runtime.catalog.names[1:], start=1):
            resolved = resolve_card_name(name, definitions)
            definition = definitions.get(resolved)
            stats = loader.get_card(name)
            if definition is None or stats is None:
                continue
            operations = runtime.catalog.mechanic_opcode[card_id]
            single_cloak = bool(
                int(runtime.catalog.mechanic_count[card_id].item()) == 1
                and int(operations[0].item()) == cloak_opcode
                and int(runtime.catalog.effect_count[card_id].item()) == 0
            )
            projectile = getattr(stats, "projectile_data", None) or {}
            simple_direct = bool(
                projectile
                and int(projectile.get("speed", 0) or 0) > 0
                and int(projectile.get("radius", 0) or 0) == 0
                and bool(projectile.get("homing", True))
                and not projectile.get("spawnProjectileData")
                and not projectile.get("projectileRange")
                and not projectile.get("targetBuffData")
                and not projectile.get("buffTime")
                and not projectile.get("pushback")
            )
            supported[card_id] = single_cloak and simple_direct
            speed[card_id] = int(projectile.get("speed", 0) or 0)
            radius[card_id] = round(
                float(getattr(stats, "projectile_start_radius", 0.0) or 0.0) * 1_000
            )
            y_offset[card_id] = round(
                float(getattr(stats, "projectile_y_offset", 0.0) or 0.0) * 1_000
            )
            damage[card_id] = float(stats.scaled_damage or stats.damage or 0.0)
        return cls(supported, speed, radius, y_offset, damage)


@dataclass
class TensorArcherQueenState:
    catalog: TensorArcherQueenCatalog
    mechanics: TensorRuntimeMechanics
    combat: StationaryCombatState
    entity_card: torch.Tensor
    row_supported: torch.Tensor
    projectile_active: torch.Tensor
    projectile_id: torch.Tensor
    projectile_runtime_slot: torch.Tensor
    projectile_source_id: torch.Tensor
    projectile_target_id: torch.Tensor
    projectile_player: torch.Tensor
    projectile_x_units: torch.Tensor
    projectile_y_units: torch.Tensor
    projectile_speed_units: torch.Tensor
    projectile_damage: torch.Tensor

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
    def max_projectiles(self) -> int:
        return int(self.projectile_active.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        max_projectiles: int = 32,
    ) -> TensorArcherQueenState:
        if len(battles) != runtime.batch_size or max_projectiles < 1:
            raise ValueError("invalid Archer Queen runtime dimensions")
        catalog = TensorArcherQueenCatalog.compile(runtime, battles[0].card_loader)
        mechanics = TensorRuntimeMechanics.from_battles(runtime, battles)
        combat = project_stationary_combat(
            battles,
            runtime.catalog,
            capacity=runtime.max_entities,
            device=runtime.device,
        ).state
        entity_card = runtime.card_catalog_index[runtime.battle.entity_card].clamp_min(
            0
        )
        source = catalog.supported[entity_card] & runtime.entity_pool.active
        row_supported = torch.ones(
            runtime.batch_size, dtype=torch.bool, device=runtime.device
        )
        definitions = battles[0].card_loader.load_card_definitions()
        for row, battle in enumerate(battles):
            for entity in battle.entities.values():
                name = str(getattr(entity.card_stats, "name", "") or "")
                resolved = resolve_card_name(name, definitions)
                definition = definitions.get(resolved)
                operations = () if definition is None else definition.mechanics
                source_owned = any(
                    type(operation).__name__ == "ArcherQueenCloak"
                    for operation in operations
                )
                if source_owned:
                    card_id = runtime.catalog.name_to_id.get(resolved, 0)
                    row_supported[row] &= bool(catalog.supported[card_id].item())
                elif operations or (definition is not None and definition.effects):
                    row_supported[row] = False
                if any(
                    type(operation).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for operation in operations
                ):
                    row_supported[row] = False
        combat.ordinary_combat_supported.fill_(True)
        combat.combat_enabled.copy_(source)
        shape = (runtime.batch_size, max_projectiles)
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        return cls(
            catalog=catalog,
            mechanics=mechanics,
            combat=combat,
            entity_card=entity_card,
            row_supported=row_supported,
            projectile_active=torch.zeros(
                shape, dtype=torch.bool, device=runtime.device
            ),
            projectile_id=zeros_i64.clone(),
            projectile_runtime_slot=torch.full_like(zeros_i64, -1),
            projectile_source_id=zeros_i64.clone(),
            projectile_target_id=zeros_i64.clone(),
            projectile_player=torch.zeros(
                shape, dtype=torch.int8, device=runtime.device
            ),
            projectile_x_units=zeros_i64.clone(),
            projectile_y_units=zeros_i64.clone(),
            projectile_speed_units=zeros_i64.clone(),
            projectile_damage=torch.zeros(
                shape, dtype=torch.float64, device=runtime.device
            ),
        )

    def clone(self) -> TensorArcherQueenState:
        return type(self)(
            catalog=self.catalog,
            mechanics=self.mechanics.clone(),
            combat=_clone_combat(self.combat),
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
                if descriptor.name not in {"catalog", "mechanics", "combat"}
            },
        )

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorArcherQueenState:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        result = self.clone()
        result.mechanics = self.mechanics.fork(indices)
        result.combat = _select_combat(self.combat, indices)
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "mechanics", "combat"}:
                continue
            setattr(
                result,
                descriptor.name,
                getattr(self, descriptor.name).index_select(0, indices).clone(),
            )
        return result

    def reset_rows_(
        self,
        rows: torch.Tensor | Sequence[int],
        source: TensorArcherQueenState,
        source_rows: torch.Tensor | Sequence[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        selected = (
            destination
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        _copy_tensor_rows(self.mechanics, source.mechanics, destination, selected)
        _copy_tensor_rows(self.combat, source.combat, destination, selected)
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "mechanics", "combat"}:
                continue
            getattr(self, descriptor.name)[destination] = getattr(
                source, descriptor.name
            )[selected]


@dataclass(frozen=True)
class ArcherQueenStepResult:
    committed: torch.Tensor
    reason: torch.Tensor
    attacked: torch.Tensor
    launched: torch.Tensor
    impacted: torch.Tensor
    damage: torch.Tensor
    died: torch.Tensor


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


def _copy_tensor_rows(
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
            and left.shape[0] >= int(rows.max().item()) + 1
            and right.shape[0] >= int(source_rows.max().item()) + 1
        ):
            left[rows] = right[source_rows]


def _muzzle_position(
    source_x: torch.Tensor,
    source_y: torch.Tensor,
    target_x: torch.Tensor,
    target_y: torch.Tensor,
    radius: torch.Tensor,
    y_offset: torch.Tensor,
    owner: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    delta = torch.stack((target_x - source_x, target_y - source_y), dim=-1)
    move = normalized_vector_units(delta, radius)
    owner_offset = torch.where(owner == 0, y_offset, -y_offset)
    return source_x + move[:, 0], source_y + move[:, 1] + owner_offset


def _refresh_combat_(
    state: TensorArcherQueenState,
    runtime: TensorBattleRuntime,
) -> None:
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
    hidden = state.mechanics.hidden_from_enemies(runtime)
    combat.targetable.copy_(combat.alive & ~hidden)
    combat.deploy_remaining.copy_(runtime.battle.entity_deploy_delay)
    combat.stunned.copy_(runtime.status.stun_timer > 0.0)
    combat.combat_blocked.copy_(state.mechanics.combat_blocked())
    source = state.catalog.supported[state.entity_card] & character
    combat.combat_enabled.copy_(source)
    combat.attack_rate_multiplier.copy_(state.mechanics.attack_rate_multiplier(runtime))
    combat.last_attack_time.copy_(runtime.battle.entity_last_attack_time)
    combat.ordinary_combat_supported.fill_(True)


def _install_launches_(
    state: TensorArcherQueenState,
    runtime: TensorBattleRuntime,
    combat_result: CombatStepResult,
) -> torch.Tensor:
    launch = combat_result.projectile_launched
    counts = launch.sum(dim=1, dtype=torch.int64)
    allocation = runtime.entity_pool.allocate(counts)
    free_keys = torch.where(
        ~state.projectile_active,
        torch.arange(state.max_projectiles, device=state.device)[None, :],
        state.max_projectiles,
    )
    free_projectiles = torch.sort(free_keys, dim=1).values
    source_keys = torch.where(
        launch,
        runtime.battle.entity_id,
        torch.full_like(runtime.battle.entity_id, torch.iinfo(torch.int64).max),
    )
    source_order = torch.argsort(source_keys, dim=1, stable=True)
    ordinal = torch.arange(runtime.max_entities, device=state.device)[None, :]
    valid = ordinal < counts[:, None]
    rows, ranks = torch.where(valid)
    source_slot = source_order[rows, ranks]
    projectile_slot = free_projectiles[rows, ranks]
    runtime_slot = allocation.slots[rows, ranks]
    projectile_id = allocation.entity_ids[rows, ranks]
    target_slot = state.combat.target_slot[rows, source_slot]
    cards = state.entity_card[rows, source_slot]
    source_x = state.combat.x_units[rows, source_slot]
    source_y = state.combat.y_units[rows, source_slot]
    target_x = state.combat.x_units[rows, target_slot]
    target_y = state.combat.y_units[rows, target_slot]
    owner = state.combat.owner[rows, source_slot]
    muzzle_x, muzzle_y = _muzzle_position(
        source_x,
        source_y,
        target_x,
        target_y,
        state.catalog.projectile_start_radius_units[cards],
        state.catalog.projectile_y_offset_units[cards],
        owner,
    )
    state.projectile_active[rows, projectile_slot] = True
    state.projectile_id[rows, projectile_slot] = projectile_id
    state.projectile_runtime_slot[rows, projectile_slot] = runtime_slot
    state.projectile_source_id[rows, projectile_slot] = runtime.battle.entity_id[
        rows, source_slot
    ]
    state.projectile_target_id[rows, projectile_slot] = runtime.battle.entity_id[
        rows, target_slot
    ]
    state.projectile_player[rows, projectile_slot] = owner
    state.projectile_x_units[rows, projectile_slot] = muzzle_x
    state.projectile_y_units[rows, projectile_slot] = muzzle_y
    state.projectile_speed_units[rows, projectile_slot] = (
        state.catalog.projectile_speed_units[cards]
    )
    state.projectile_damage[rows, projectile_slot] = state.combat.damage[
        rows, source_slot
    ]
    battle = runtime.battle
    battle.entity_active[rows, runtime_slot] = True
    battle.entity_kind[rows, runtime_slot] = 2
    battle.entity_player[rows, runtime_slot] = owner
    battle.entity_card[rows, runtime_slot] = 0
    battle.entity_x_units[rows, runtime_slot] = muzzle_x.to(torch.int32)
    battle.entity_y_units[rows, runtime_slot] = muzzle_y.to(torch.int32)
    battle.entity_hp[rows, runtime_slot] = 1.0
    battle.entity_hp_integer_kind[rows, runtime_slot] = True
    battle.entity_max_hp[rows, runtime_slot] = 1.0
    event_id = torch.zeros_like(allocation.entity_ids)
    event_target = torch.zeros_like(allocation.entity_ids)
    event_x = torch.zeros_like(allocation.entity_ids)
    event_y = torch.zeros_like(allocation.entity_ids)
    event_id[rows, ranks] = projectile_id
    event_target[rows, ranks] = state.projectile_target_id[rows, projectile_slot]
    event_x[rows, ranks] = muzzle_x
    event_y[rows, ranks] = muzzle_y
    runtime.events.append(
        phase=TickPhase.COMBAT,
        opcode=RuntimeEventOpcode.PROJECTILE,
        valid=valid,
        source_id=event_id,
        target_id=event_target,
        x_units=event_x,
        y_units=event_y,
        payload=ArcherQueenEventPayload.PROJECTILE_LAUNCHED,
    )
    return launch


def _clear_projectiles_(
    state: TensorArcherQueenState,
    runtime: TensorBattleRuntime,
    terminal: torch.Tensor,
) -> None:
    rows, projectile_slots = torch.where(terminal)
    if rows.numel() == 0:
        return
    runtime_slots = state.projectile_runtime_slot[rows, projectile_slots]
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[rows, runtime_slots] = True
    runtime.entity_pool.cleanup(dead)
    for descriptor in fields(runtime.battle):
        value = getattr(runtime.battle, descriptor.name)
        if (
            isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[:2] == runtime.battle.entity_id.shape
        ):
            value[dead] = 0
    state.projectile_active[terminal] = False
    for name in (
        "projectile_id",
        "projectile_source_id",
        "projectile_target_id",
        "projectile_x_units",
        "projectile_y_units",
        "projectile_speed_units",
        "projectile_damage",
    ):
        getattr(state, name)[terminal] = 0
    state.projectile_runtime_slot[terminal] = -1
    state.projectile_player[terminal] = 0


def _clear_dead_characters_(runtime: TensorBattleRuntime) -> None:
    dead = (
        runtime.entity_pool.active
        & ~runtime.battle.entity_active
        & ((runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1))
    )
    if not bool(dead.any().item()):
        return
    runtime.entity_pool.cleanup(dead)
    for owner_name in ("battle", "status", "phases"):
        owner = getattr(runtime, owner_name)
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == runtime.battle.entity_id.shape
            ):
                value[dead] = 0


def _advance_projectiles_(
    state: TensorArcherQueenState,
    runtime: TensorBattleRuntime,
    active_at_start: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    requested_ids = state.projectile_target_id
    target_slots = runtime.entity_pool.slots_for_ids(requested_ids)
    target_valid = target_slots >= 0
    safe_target = target_slots.clamp_min(0)
    target_x = runtime.battle.entity_x_units.gather(1, safe_target).to(torch.int64)
    target_y = runtime.battle.entity_y_units.gather(1, safe_target).to(torch.int64)
    dx = target_x - state.projectile_x_units
    dy = target_y - state.projectile_y_units
    distance = integer_sqrt_tensor(dx.square() + dy.square())
    impact = active_at_start & target_valid & (distance <= state.projectile_speed_units)
    orphan = active_at_start & ~target_valid
    moving = active_at_start & target_valid & ~impact
    movement = normalized_vector_units(
        torch.stack((dx, dy), dim=-1), state.projectile_speed_units
    )
    state.projectile_x_units += torch.where(
        moving[..., None], movement, torch.zeros_like(movement)
    )[..., 0]
    state.projectile_y_units += torch.where(
        moving[..., None], movement, torch.zeros_like(movement)
    )[..., 1]
    live_rows, live_projectiles = torch.where(active_at_start)
    live_runtime_slots = state.projectile_runtime_slot[live_rows, live_projectiles]
    runtime.battle.entity_x_units[live_rows, live_runtime_slots] = (
        state.projectile_x_units[live_rows, live_projectiles].to(torch.int32)
    )
    runtime.battle.entity_y_units[live_rows, live_runtime_slots] = (
        state.projectile_y_units[live_rows, live_projectiles].to(torch.int32)
    )
    damage_done = torch.zeros_like(state.projectile_damage)
    died = torch.zeros_like(impact)
    order = torch.argsort(
        torch.where(
            impact,
            state.projectile_id,
            torch.full_like(state.projectile_id, torch.iinfo(torch.int64).max),
        ),
        dim=1,
        stable=True,
    )
    rows = torch.arange(state.batch_size, device=state.device)
    for rank in range(state.max_projectiles):
        projectile_slot = order[:, rank]
        selected = impact[rows, projectile_slot]
        target_slot = safe_target[rows, projectile_slot]
        eligible = (
            selected
            & runtime.entity_pool.active[rows, target_slot]
            & runtime.battle.entity_active[rows, target_slot]
            & (
                runtime.battle.entity_player[rows, target_slot]
                != state.projectile_player[rows, projectile_slot]
            )
            & (
                (runtime.battle.entity_kind[rows, target_slot] == 0)
                | (runtime.battle.entity_kind[rows, target_slot] == 1)
            )
        )
        before = runtime.battle.entity_hp[rows, target_slot]
        amount = torch.where(
            eligible, state.projectile_damage[rows, projectile_slot], 0.0
        )
        after = torch.clamp(before - amount, min=0.0)
        runtime.battle.entity_hp[rows, target_slot] = torch.where(
            eligible, after, before
        )
        runtime.battle.entity_hp_integer_kind[rows, target_slot] &= ~eligible
        lane_died = (
            eligible & runtime.battle.entity_active[rows, target_slot] & (after <= 0.0)
        )
        runtime.battle.entity_active[rows, target_slot] &= ~lane_died
        runtime.phases.death_pending[rows, target_slot] |= lane_died
        damage_done[rows, projectile_slot] = before - after
        died[rows, projectile_slot] = lane_died
    runtime.events.append(
        phase=TickPhase.OBJECTS,
        opcode=RuntimeEventOpcode.PROJECTILE,
        valid=impact,
        source_id=state.projectile_id,
        target_id=state.projectile_target_id,
        amount=damage_done,
        payload=ArcherQueenEventPayload.PROJECTILE_IMPACT,
    )
    runtime.events.append(
        phase=TickPhase.OBJECTS,
        opcode=RuntimeEventOpcode.DAMAGE,
        valid=impact & (damage_done > 0.0),
        source_id=state.projectile_source_id,
        target_id=state.projectile_target_id,
        amount=damage_done,
    )
    runtime.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.DEATH,
        valid=died,
        source_id=state.projectile_source_id,
        target_id=state.projectile_target_id,
    )
    _clear_projectiles_(state, runtime, impact | orphan)
    return impact, damage_done, died


def _copy_combat_to_runtime_(
    state: TensorArcherQueenState,
    runtime: TensorBattleRuntime,
) -> None:
    character = state.combat.present
    runtime.battle.entity_hp.copy_(
        torch.where(character, state.combat.hp, runtime.battle.entity_hp)
    )
    runtime.battle.entity_active.copy_(
        torch.where(character, state.combat.alive, runtime.battle.entity_active)
    )
    runtime.battle.entity_last_attack_time.copy_(
        torch.where(
            character,
            state.combat.last_attack_time,
            runtime.battle.entity_last_attack_time,
        )
    )
    runtime.phases.target_slot.copy_(
        torch.where(character, state.combat.target_slot, runtime.phases.target_slot)
    )


def activate_archer_queen_(
    state: TensorArcherQueenState,
    runtime: TensorBattleRuntime,
    requested_players: torch.Tensor,
) -> torch.Tensor:
    """Atomically pay and schedule the serialized Champion ability."""

    before_state = state.clone()
    before_runtime = runtime.clone()
    try:
        result = state.mechanics.activate_(runtime, requested_players)
    except (OverflowError, ValueError):
        state.reset_rows_(
            torch.arange(state.batch_size, device=state.device), before_state
        )
        _copy_runtime_rows_(
            runtime,
            before_runtime,
            torch.arange(state.batch_size, device=state.device),
            torch.arange(state.batch_size, device=state.device),
        )
        raise
    return result.activated


def step_archer_queen_(
    state: TensorArcherQueenState,
    runtime: TensorBattleRuntime,
    *,
    dt_ms: int = 50,
    cancel_before_effect: torch.Tensor | bool = False,
) -> ArcherQueenStepResult:
    """Advance one retained combat/object frame with row-atomic admission."""

    if dt_ms != 50:
        raise ValueError("exact Archer Queen lifecycle currently requires 50 ms")
    active_sources = (
        state.catalog.supported[state.entity_card] & runtime.entity_pool.active
    )
    source_count = active_sources.sum(dim=1, dtype=torch.int64)
    free_entities = (~runtime.entity_pool.active).sum(dim=1, dtype=torch.int64)
    free_projectiles = (~state.projectile_active).sum(dim=1, dtype=torch.int64)
    remaining_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
    worst_events = (
        6 * source_count
        + source_count
        + 3 * state.projectile_active.sum(dim=1, dtype=torch.int64)
    )
    reason = torch.zeros(state.batch_size, dtype=torch.int16, device=state.device)
    reason = torch.where(
        ~state.row_supported,
        torch.full_like(reason, ArcherQueenReason.UNSUPPORTED_PAYLOAD),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (source_count > free_entities),
        torch.full_like(reason, ArcherQueenReason.ENTITY_CAPACITY),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (source_count > free_projectiles),
        torch.full_like(reason, ArcherQueenReason.PROJECTILE_CAPACITY),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (worst_events > remaining_events),
        torch.full_like(reason, ArcherQueenReason.EVENT_CAPACITY),
        reason,
    )
    committed = reason == 0
    attacked = torch.zeros_like(runtime.entity_pool.active)
    launched = torch.zeros_like(attacked)
    impacted = torch.zeros_like(state.projectile_active)
    damage = torch.zeros_like(state.projectile_damage)
    died = torch.zeros_like(state.projectile_active)
    selected = torch.nonzero(committed, as_tuple=False).flatten()
    if selected.numel() == 0:
        return ArcherQueenStepResult(
            committed, reason, attacked, launched, impacted, damage, died
        )
    scratch_runtime = runtime.fork(selected)
    scratch = state.fork(selected)
    scratch_runtime.battle.time += dt_ms / 1_000.0
    scratch_runtime.battle.tick += 1
    scratch_runtime.battle.dt.fill_(dt_ms / 1_000.0)
    scratch_runtime.battle.tick_milliseconds.fill_(dt_ms)
    scratch.entity_card.copy_(
        scratch_runtime.card_catalog_index[
            scratch_runtime.battle.entity_card
        ].clamp_min(0)
    )
    scratch.mechanics.refresh_new_entities_(scratch_runtime)
    no_request = torch.zeros(
        (selected.numel(), 2), dtype=torch.bool, device=state.device
    )
    scratch.mechanics.activate_(scratch_runtime, no_request)
    scratch.mechanics.tick_cloak_(
        scratch_runtime,
        cancel_before_effect=torch.as_tensor(
            cancel_before_effect, dtype=torch.bool, device=state.device
        )
        .expand_as(state.mechanics.ability_active)
        .index_select(0, selected),
    )
    _refresh_combat_(scratch, scratch_runtime)
    combat_result = step_stationary_combat_(scratch.combat, dt_ms / 1_000.0)
    _copy_combat_to_runtime_(scratch, scratch_runtime)
    launch_mask = _install_launches_(scratch, scratch_runtime, combat_result)
    impact_mask, damage_done, died_mask = _advance_projectiles_(
        # The native object manager grows its ID-ordered worklist during the
        # phase, so a combat-created projectile moves later in this frame.
        scratch,
        scratch_runtime,
        scratch.projectile_active.clone(),
    )
    # Object-phase deaths synchronously cancel or remove an applied cloak.
    scratch.mechanics.tick_cloak_(scratch_runtime)
    _clear_dead_characters_(scratch_runtime)
    scratch.combat.hp.copy_(scratch_runtime.battle.entity_hp)
    scratch.combat.alive.copy_(scratch_runtime.battle.entity_active)
    source_rows = torch.arange(selected.numel(), device=state.device)
    state.reset_rows_(selected, scratch, source_rows)
    _copy_runtime_rows_(runtime, scratch_runtime, selected, source_rows)
    attacked[selected] = combat_result.attacked
    launched[selected] = launch_mask
    impacted[selected] = impact_mask
    damage[selected] = damage_done
    died[selected] = died_mask
    return ArcherQueenStepResult(
        committed, reason, attacked, launched, impacted, damage, died
    )


def _copy_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
    source_rows: torch.Tensor,
) -> None:
    for name in ("battle", "entity_pool", "status", "phases", "events"):
        _copy_tensor_rows(
            getattr(destination, name), getattr(source, name), rows, source_rows
        )
    destination.supported[rows] = source.supported[source_rows]
    destination.dirty[rows] = source.dirty[source_rows]


__all__ = [
    "ArcherQueenEventPayload",
    "ArcherQueenReason",
    "ArcherQueenStepResult",
    "TensorArcherQueenCatalog",
    "TensorArcherQueenState",
    "activate_archer_queen_",
    "step_archer_queen_",
]
