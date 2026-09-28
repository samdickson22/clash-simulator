"""Retained Skeleton King soul, Champion, and summon lifecycle.

Cards are selected solely through the serialized
``SkeletonKingSoulCollector`` opcode.  The Python boundary compiles its
``ActiveAbility``/``SpawnUnits`` payload once; retained ticks operate on
batched tensors and fail closed for any additional child or death mechanic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Any, cast

import torch

from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.effects import SpawnUnits
from clasher.formations import formation_offset
from clasher.native_tilemap import (
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_ROWS,
    STANDARD_PATH_WIDTH,
)

from .catalog import MECHANIC_OPCODE
from .passive_mechanics import (
    TensorPassiveCatalog,
    TensorPassiveEvents,
    TensorPassiveState,
    collect_souls_,
    consume_souls_,
    plan_soul_drops,
)
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .shield_champion import (
    NEVER_USED_TIME_MS,
    champion_button_owner_mask,
    champion_owner_mask,
    refresh_champion_ownership_,
)


class SkeletonKingReason(IntEnum):
    NONE = 0
    UNSUPPORTED_PAYLOAD = 1
    ENTITY_CAPACITY = 2
    EVENT_CAPACITY = 3
    BATCH_ROLLBACK = 4


class SkeletonKingEventPayload(IntEnum):
    OWNERSHIP_TRANSFERRED = 1
    ABILITY_ACTIVATED = 2
    ABILITY_ENDED = 3
    SOUL_DROP_SPAWN = 4
    ABILITY_SPAWN = 5


@dataclass(frozen=True)
class TensorSkeletonKingCatalog:
    passive: TensorPassiveCatalog
    supported: torch.Tensor
    ability_cost: torch.Tensor
    ability_cooldown_ms: torch.Tensor
    ability_duration_ms: torch.Tensor
    soul_threshold: torch.Tensor
    spawn_count: torch.Tensor
    spawn_radius_units: torch.Tensor
    child_name: tuple[str | None, ...]
    child_hitpoints: torch.Tensor
    child_hp_integer_kind: torch.Tensor
    child_deploy_ms: torch.Tensor
    child_lifetime_ms: torch.Tensor
    child_is_air: torch.Tensor
    child_summon_count: torch.Tensor
    child_formation_offsets: torch.Tensor

    @classmethod
    def compile(
        cls,
        runtime: TensorBattleRuntime,
        loader: Any,
    ) -> TensorSkeletonKingCatalog:
        passive = TensorPassiveCatalog.compile(
            loader, runtime.catalog.names[1:], device=runtime.device
        )
        size = len(passive.names)
        device = runtime.device

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = zeros(torch.bool)
        cost = zeros(torch.int64)
        cooldown = zeros(torch.int64)
        duration = zeros(torch.int64)
        threshold = zeros(torch.int64)
        count = zeros(torch.int64)
        radius = zeros(torch.int64)
        child_hp = zeros(torch.float64)
        child_integer = zeros(torch.bool)
        child_deploy = zeros(torch.int64)
        child_lifetime = zeros(torch.int64)
        child_air = zeros(torch.bool)
        child_summon = torch.ones(size, dtype=torch.int64, device=device)
        maximum_summon = max(
            1,
            max(
                int(loader.get_card(name).summon_count or 1)
                for name in loader.load_card_definitions()
                if loader.get_card(name) is not None
            ),
        )
        child_offsets = torch.zeros(
            (size, 2, 3, maximum_summon, 2),
            dtype=torch.int64,
            device=device,
        )
        child_names: list[str | None] = [None] * size
        definitions = loader.load_card_definitions()
        opcode = MECHANIC_OPCODE["SkeletonKingSoulCollector"]
        for card_id, name in enumerate(passive.names[1:], start=1):
            definition = definitions[resolve_card_name(name, definitions)]
            matches = [
                operation
                for operation in definition.mechanics
                if type(operation).__name__ == "SkeletonKingSoulCollector"
            ]
            if len(matches) != 1 or len(definition.mechanics) != 1:
                continue
            operation = matches[0]
            ability = getattr(operation, "ability", None)
            effects = tuple(getattr(ability, "effects", ()))
            if len(effects) != 1 or not isinstance(effects[0], SpawnUnits):
                continue
            effect = effects[0]
            child = loader.get_card(effect.unit_name)
            if child is None:
                continue
            child_definition = definitions.get(
                resolve_card_name(effect.unit_name, definitions)
            )
            if (
                child_definition is None
                or child_definition.mechanics
                or child_definition.effects
            ):
                continue
            typed_ability = cast(Any, ability)
            operation_rows = passive.mechanic_opcode[card_id] == opcode
            operation_slot = int(
                torch.nonzero(operation_rows, as_tuple=False).flatten()[0].item()
            )
            supported[card_id] = True
            cost[card_id] = int(typed_ability.elixir_cost)
            cooldown[card_id] = int(typed_ability.cooldown_ms)
            duration[card_id] = int(typed_ability.duration_ms)
            threshold[card_id] = passive.souls_per_activation[card_id, operation_slot]
            count[card_id] = int(effect.count)
            radius[card_id] = round(float(effect.radius_tiles) * 1_000)
            child_names[card_id] = str(effect.unit_name)
            raw_hp = child.scaled_hitpoints or child.hitpoints or 100
            child_hp[card_id] = float(raw_hp)
            child_integer[card_id] = type(raw_hp) is int
            child_deploy[card_id] = int(child.deploy_time or 0)
            child_lifetime[card_id] = int(child.lifetime_ms or 0)
            child_air[card_id] = bool(getattr(child, "is_air_unit", False))
            summon = int(child.summon_count or 1)
            child_summon[card_id] = summon
            summon_radius = float(
                child.summon_radius
                if child.summon_radius is not None
                else child.collision_radius or 0.5
            )
            for owner in range(2):
                for lane in (1, 2):
                    for member in range(summon):
                        offset = formation_offset(
                            member,
                            summon,
                            summon_radius,
                            owner,
                            angle_shift_degrees=float(child.spawn_angle_shift or 0),
                            lane_id=lane,
                        )
                        child_offsets[card_id, owner, lane, member] = torch.tensor(
                            [round(offset[0] * 1_000), round(offset[1] * 1_000)],
                            dtype=torch.int64,
                            device=device,
                        )
        return cls(
            passive,
            supported,
            cost,
            cooldown,
            duration,
            threshold,
            count,
            radius,
            tuple(child_names),
            child_hp,
            child_integer,
            child_deploy,
            child_lifetime,
            child_air,
            child_summon,
            child_offsets,
        )


@dataclass
class TensorSkeletonKingState:
    catalog: TensorSkeletonKingCatalog
    passive: TensorPassiveState
    entity_card: torch.Tensor
    initialized_entity_id: torch.Tensor
    has_ability: torch.Tensor
    ability_key: torch.Tensor
    last_use_time_ms: torch.Tensor
    ability_active: torch.Tensor
    activation_time_ms: torch.Tensor
    recorded_owner_id: torch.Tensor
    child_core_card_id: torch.Tensor
    row_supported: torch.Tensor

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
    ) -> TensorSkeletonKingState:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime")
        catalog = TensorSkeletonKingCatalog.compile(runtime, battles[0].card_loader)
        core_to_passive = torch.tensor(
            [
                catalog.passive.name_to_id.get(name, 0) if name else 0
                for name in runtime.battle.card_names
            ],
            dtype=torch.int64,
            device=runtime.device,
        )
        entity_card = core_to_passive[runtime.battle.entity_card]
        passive = TensorPassiveState.from_entities(
            catalog.passive,
            entity_id=runtime.battle.entity_id,
            card_id=entity_card,
            player=runtime.battle.entity_player,
            x_units=runtime.battle.entity_x_units,
            y_units=runtime.battle.entity_y_units,
            active=runtime.entity_pool.active,
            alive=runtime.battle.entity_active,
            target_slot=runtime.phases.target_slot,
        )
        last_use = torch.full_like(runtime.battle.entity_id, NEVER_USED_TIME_MS)
        ability_active = torch.zeros_like(runtime.entity_pool.active)
        activation_time = torch.zeros_like(runtime.battle.entity_id)
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                for mechanic in entity.mechanics:
                    if type(mechanic).__name__ != "SkeletonKingSoulCollector":
                        continue
                    typed_mechanic = cast(Any, mechanic)
                    passive.souls_collected[row, slot] = int(
                        typed_mechanic.souls_collected
                    )
                    ability = typed_mechanic.ability
                    passive.soul_ability_cost[row, slot] = int(ability.elixir_cost)
                    last_use[row, slot] = int(ability.last_use_time)
                    ability_active[row, slot] = bool(ability.is_active)
                    activation_time[row, slot] = int(ability.activation_time)
        has_ability = catalog.supported[entity_card] & runtime.entity_pool.active
        ability_key = torch.where(has_ability, entity_card, 0)
        recorded = torch.zeros(
            (runtime.batch_size, 2, len(catalog.passive.names)),
            dtype=torch.int64,
            device=runtime.device,
        )
        owners = champion_owner_mask(
            runtime.battle.entity_id,
            runtime.battle.entity_player,
            ability_key,
            runtime.battle.entity_active,
            has_ability,
        )
        group = (
            runtime.battle.entity_player.to(torch.int64) * len(catalog.passive.names)
            + ability_key
        ).clamp(0, recorded.shape[1] * recorded.shape[2] - 1)
        selected = torch.zeros(
            (runtime.batch_size, 2 * len(catalog.passive.names)),
            dtype=torch.int64,
            device=runtime.device,
        )
        selected.scatter_reduce_(
            1,
            group,
            torch.where(owners, runtime.battle.entity_id, 0),
            reduce="amax",
            include_self=True,
        )
        recorded.copy_(selected.reshape_as(recorded))
        child_core = _ensure_child_cards_(runtime, catalog)
        operations = catalog.passive.mechanic_opcode[entity_card]
        soul_present = (operations == MECHANIC_OPCODE["SkeletonKingSoulCollector"]).any(
            dim=2
        )
        row_supported = (~soul_present | catalog.supported[entity_card]).all(dim=1)
        for row, battle in enumerate(battles):
            row_supported[row] &= all(
                not entity.mechanics
                or (
                    len(entity.mechanics) == 1
                    and type(entity.mechanics[0]).__name__
                    == "SkeletonKingSoulCollector"
                )
                for entity in battle.entities.values()
            )
        return cls(
            catalog,
            passive,
            entity_card,
            runtime.battle.entity_id.clone(),
            has_ability,
            ability_key,
            last_use,
            ability_active,
            activation_time,
            recorded,
            child_core,
            row_supported,
        )

    def clone(self) -> TensorSkeletonKingState:
        return type(self)(
            catalog=self.catalog,
            passive=self.passive.clone(),
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
                if descriptor.name not in {"catalog", "passive"}
            },
        )

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorSkeletonKingState:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        result = self.clone()
        result.passive = TensorPassiveState(
            **{
                name: getattr(self.passive, name).index_select(0, indices).clone()
                for name in self.passive.__dataclass_fields__
            }
        )
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "passive"}:
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
        source: TensorSkeletonKingState,
        source_rows: torch.Tensor | Sequence[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        selected = (
            destination
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        for name in self.passive.__dataclass_fields__:
            getattr(self.passive, name)[destination] = getattr(source.passive, name)[
                selected
            ]
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "passive"}:
                continue
            getattr(self, descriptor.name)[destination] = getattr(
                source, descriptor.name
            )[selected]


@dataclass(frozen=True)
class SkeletonKingActivationResult:
    committed: torch.Tensor
    reason: torch.Tensor
    owner: torch.Tensor
    transferred: torch.Tensor
    activated: torch.Tensor
    spawned: torch.Tensor


@dataclass(frozen=True)
class SkeletonKingStepResult:
    committed: torch.Tensor
    reason: torch.Tensor
    collected: TensorPassiveEvents
    dropped: TensorPassiveEvents
    spawned: torch.Tensor
    ability_ended: torch.Tensor


def _ensure_child_cards_(
    runtime: TensorBattleRuntime,
    catalog: TensorSkeletonKingCatalog,
) -> torch.Tensor:
    result = torch.zeros(
        len(catalog.passive.names), dtype=torch.int64, device=runtime.device
    )
    names = list(runtime.battle.card_names)
    changed = False
    for card_id, child in enumerate(catalog.child_name):
        if child is None:
            continue
        if child not in runtime.battle.card_to_id:
            runtime.battle.card_to_id[child] = len(names)
            names.append(child)
            runtime.card_catalog_index = torch.cat(
                (
                    runtime.card_catalog_index,
                    torch.tensor([-1], dtype=torch.int64, device=runtime.device),
                )
            )
            changed = True
        result[card_id] = runtime.battle.card_to_id[child]
    if changed:
        runtime.battle.card_names = tuple(names)
    return result


def _refresh_(
    state: TensorSkeletonKingState,
    runtime: TensorBattleRuntime,
) -> None:
    core_to_passive = torch.tensor(
        [
            state.catalog.passive.name_to_id.get(name, 0) if name else 0
            for name in runtime.battle.card_names
        ],
        dtype=torch.int64,
        device=state.device,
    )
    cards = core_to_passive[runtime.battle.entity_card]
    same = runtime.entity_pool.active & (
        state.initialized_entity_id == runtime.battle.entity_id
    )
    new = runtime.entity_pool.active & ~same
    state.entity_card.copy_(cards)
    state.passive.entity_id.copy_(runtime.battle.entity_id)
    state.passive.card_id.copy_(cards)
    state.passive.player.copy_(runtime.battle.entity_player)
    state.passive.x_units.copy_(runtime.battle.entity_x_units)
    state.passive.y_units.copy_(runtime.battle.entity_y_units)
    state.passive.active.copy_(runtime.entity_pool.active)
    state.passive.alive.copy_(runtime.battle.entity_active)
    state.passive.target_slot.copy_(runtime.phases.target_slot)
    state.passive.souls_collected.masked_fill_(new, 0)
    state.passive.soul_ability_cost.masked_fill_(new, 3)
    state.last_use_time_ms.masked_fill_(new, NEVER_USED_TIME_MS)
    state.ability_active.masked_fill_(new, False)
    state.activation_time_ms.masked_fill_(new, 0)
    state.has_ability.copy_(state.catalog.supported[cards] & runtime.entity_pool.active)
    state.ability_key.copy_(torch.where(state.has_ability, cards, 0))
    state.initialized_entity_id.copy_(runtime.battle.entity_id)


def _append_passive_events_(
    runtime: TensorBattleRuntime,
    events: TensorPassiveEvents,
    phase: TickPhase,
) -> None:
    count = int(events.batch_index.numel())
    if count == 0:
        return
    width = count
    lanes = torch.zeros(
        (runtime.batch_size, width), dtype=torch.bool, device=runtime.device
    )
    ordinal = torch.arange(count, device=runtime.device)
    prior = (events.batch_index[:, None] == events.batch_index[None, :]) & (
        ordinal[None, :] < ordinal[:, None]
    )
    local = prior.sum(dim=1, dtype=torch.int64)
    lanes[events.batch_index, local] = True

    def packed(value: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
        result = torch.zeros(
            (runtime.batch_size, width), dtype=dtype, device=runtime.device
        )
        result[events.batch_index, local] = value.to(dtype)
        return result

    runtime.events.append(
        phase=phase,
        opcode=RuntimeEventOpcode.STATUS,
        valid=lanes,
        source_id=packed(events.source_entity_id, torch.int64),
        target_id=packed(events.target_entity_id, torch.int64),
        amount=packed(events.amount, torch.float64),
        payload=packed(events.opcode, torch.int64),
    )


def _spawn_children_(
    state: TensorSkeletonKingState,
    runtime: TensorBattleRuntime,
    source_slots: torch.Tensor,
    counts: torch.Tensor,
    radius_units: torch.Tensor,
    payload: SkeletonKingEventPayload,
    phase: TickPhase,
) -> torch.Tensor:
    source_cards = state.entity_card.gather(1, source_slots)
    swarm = state.catalog.child_summon_count[source_cards]
    child_counts = counts * swarm
    total = child_counts.sum(dim=1, dtype=torch.int64)
    allocation = runtime.entity_pool.allocate(total)
    width = runtime.max_entities
    ordinal = torch.arange(width, device=state.device)[None, :]
    valid = ordinal < total[:, None]
    cumulative = child_counts.cumsum(dim=1)
    belongs = ordinal[:, :, None] < cumulative[:, None, :]
    source_ordinal = belongs.to(torch.int64).argmax(dim=2)
    prior = torch.cat((torch.zeros_like(counts[:, :1]), cumulative[:, :-1]), dim=1)
    local = ordinal - prior.gather(1, source_ordinal)
    rows, ranks = torch.where(valid)
    source_slot = source_slots[rows, source_ordinal[rows, ranks]]
    entity_slot = allocation.slots[rows, ranks]
    entity_id = allocation.entity_ids[rows, ranks]
    card = state.entity_card[rows, source_slot]
    selected_swarm = swarm[rows, source_ordinal[rows, ranks]].clamp_min(1)
    anchor = torch.div(local[rows, ranks], selected_swarm, rounding_mode="floor")
    member = torch.remainder(local[rows, ranks], selected_swarm)
    wave = counts[rows, source_ordinal[rows, ranks]].clamp_min(1)
    angle = anchor.to(torch.float64) * (2.0 * math.pi) / wave
    radius = radius_units[rows, source_ordinal[rows, ranks]].to(torch.float64)
    child_core = state.child_core_card_id[card]
    anchor_x = state.passive.x_units[rows, source_slot].to(torch.float64) + (
        radius * torch.cos(angle)
    )
    anchor_y = state.passive.y_units[rows, source_slot].to(torch.float64) + (
        radius * torch.sin(angle)
    )
    lane = _lane_id(
        torch.stack((torch.round(anchor_x), torch.round(anchor_y)), dim=1).to(
            torch.int64
        )
    )
    owner = runtime.battle.entity_player[rows, source_slot].to(torch.int64)
    offset = state.catalog.child_formation_offsets[card, owner, lane, member]
    x = torch.round(anchor_x + offset[:, 0]).to(torch.int64)
    y = torch.round(anchor_y + offset[:, 1]).to(torch.int64)
    battle = runtime.battle
    battle.entity_active[rows, entity_slot] = True
    battle.entity_kind[rows, entity_slot] = 0
    battle.entity_player[rows, entity_slot] = battle.entity_player[rows, source_slot]
    battle.entity_card[rows, entity_slot] = child_core
    battle.entity_x_units[rows, entity_slot] = x.to(torch.int32)
    battle.entity_y_units[rows, entity_slot] = y.to(torch.int32)
    battle.entity_hp[rows, entity_slot] = state.catalog.child_hitpoints[card]
    battle.entity_hp_integer_kind[rows, entity_slot] = (
        state.catalog.child_hp_integer_kind[card]
    )
    battle.entity_max_hp[rows, entity_slot] = state.catalog.child_hitpoints[card]
    deploy_ms = state.catalog.child_deploy_ms[card]
    battle.entity_deploy_delay[rows, entity_slot] = (
        deploy_ms.to(torch.float64) / 1_000.0
    )
    battle.entity_placement_pending[rows, entity_slot] = deploy_ms > 0
    battle.entity_spawn_hook_pending[rows, entity_slot] = deploy_ms > 0
    battle.entity_spawn_hook_fired[rows, entity_slot] = deploy_ms <= 0
    battle.entity_lifetime_ms[rows, entity_slot] = state.catalog.child_lifetime_ms[card]
    event_id = torch.zeros_like(allocation.entity_ids)
    event_source = torch.zeros_like(allocation.entity_ids)
    event_x = torch.zeros_like(allocation.entity_ids)
    event_y = torch.zeros_like(allocation.entity_ids)
    event_id[rows, ranks] = entity_id
    event_source[rows, ranks] = runtime.battle.entity_id[rows, source_slot]
    event_x[rows, ranks] = x
    event_y[rows, ranks] = y
    runtime.events.append(
        phase=phase,
        opcode=RuntimeEventOpcode.SPAWN,
        valid=valid,
        source_id=event_source,
        target_id=event_id,
        x_units=event_x,
        y_units=event_y,
        payload=payload,
    )
    return valid


def _lane_id(position: torch.Tensor) -> torch.Tensor:
    x = torch.div(position[:, 0], 500, rounding_mode="trunc")
    y = torch.div(position[:, 1], 500, rounding_mode="trunc")
    cell_x = torch.arange(
        STANDARD_PATH_WIDTH, device=position.device
    ).repeat_interleave(STANDARD_PATH_HEIGHT)
    cell_y = torch.arange(STANDARD_PATH_HEIGHT, device=position.device).repeat(
        STANDARD_PATH_WIDTH
    )
    lane = torch.tensor(
        [
            ord(STANDARD_PATH_ROWS[j][i]) - ord("0")
            for i in range(STANDARD_PATH_WIDTH)
            for j in range(STANDARD_PATH_HEIGHT)
        ],
        dtype=torch.int64,
        device=position.device,
    )
    distance = (cell_x - x[:, None]).square() + (cell_y - y[:, None]).square()
    selected = torch.argmin(
        torch.where(lane > 0, distance, torch.iinfo(torch.int64).max), dim=1
    )
    return lane[selected]


def _ownership_(
    state: TensorSkeletonKingState,
    runtime: TensorBattleRuntime,
) -> tuple[torch.Tensor, torch.Tensor]:
    result = refresh_champion_ownership_(
        entity_id=runtime.battle.entity_id,
        entity_player=runtime.battle.entity_player,
        ability_key=state.ability_key,
        alive=runtime.battle.entity_active,
        has_ability=state.has_ability,
        recorded_owner_id=state.recorded_owner_id,
        last_use_time_ms=state.last_use_time_ms,
    )
    return result.owner, result.transferred


def activate_skeleton_king_(
    state: TensorSkeletonKingState,
    runtime: TensorBattleRuntime,
    requested_players: torch.Tensor,
) -> SkeletonKingActivationResult:
    before = state.clone()
    requested = torch.as_tensor(
        requested_players, dtype=torch.bool, device=state.device
    )
    if requested.shape != (state.batch_size, 2):
        raise ValueError("requested_players must have shape [batch, 2]")
    _refresh_(state, runtime)
    owner_preview = champion_owner_mask(
        runtime.battle.entity_id,
        runtime.battle.entity_player,
        state.ability_key,
        runtime.battle.entity_active,
        state.has_ability,
    )
    button = champion_button_owner_mask(
        owner_preview, runtime.battle.entity_id, runtime.battle.entity_player
    )
    card = state.entity_card.clamp_min(0)
    now = torch.round(runtime.battle.time * 1_000).to(torch.int64)[:, None]
    never = state.last_use_time_ms <= -(10**11)
    cooldown_ready = never | (
        now
        >= state.activation_time_ms
        + state.catalog.ability_duration_ms[card]
        + state.catalog.ability_cooldown_ms[card]
    )
    cost = state.passive.soul_ability_cost
    elixir_ready = (
        runtime.battle.elixir.gather(1, runtime.battle.entity_player.to(torch.int64))
        >= cost
    )
    soul_ready = state.passive.souls_collected >= state.catalog.soul_threshold[card]
    request_entity = requested.gather(1, runtime.battle.entity_player.to(torch.int64))
    activated = (
        button
        & request_entity
        & cooldown_ready
        & elixir_ready
        & soul_ready
        & ~state.ability_active
        & ~runtime.battle.entity_placement_pending
        & (runtime.battle.entity_deploy_delay <= 1e-9)
    )
    spawn_counts = torch.where(activated, state.catalog.spawn_count[card], 0)
    total = (spawn_counts * state.catalog.child_summon_count[card]).sum(
        dim=1, dtype=torch.int64
    )
    free = (~runtime.entity_pool.active).sum(dim=1, dtype=torch.int64)
    remaining_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
    worst_events = total + 2 * activated.sum(dim=1) + state.has_ability.sum(dim=1)
    reason = torch.zeros(state.batch_size, dtype=torch.int16, device=state.device)
    reason = torch.where(
        ~state.row_supported,
        torch.full_like(reason, SkeletonKingReason.UNSUPPORTED_PAYLOAD),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (total > free),
        torch.full_like(reason, SkeletonKingReason.ENTITY_CAPACITY),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (worst_events > remaining_events),
        torch.full_like(reason, SkeletonKingReason.EVENT_CAPACITY),
        reason,
    )
    committed = reason == 0
    activated &= committed[:, None]
    if not bool(committed.all().item()):
        reason = torch.where(
            committed,
            torch.full_like(reason, SkeletonKingReason.BATCH_ROLLBACK),
            reason,
        )
        committed.zero_()
        state.reset_rows_(torch.arange(state.batch_size, device=state.device), before)
        return SkeletonKingActivationResult(
            committed,
            reason,
            owner_preview,
            torch.zeros_like(owner_preview),
            torch.zeros_like(activated),
            torch.zeros_like(runtime.entity_pool.active),
        )
    owner, transferred = _ownership_(state, runtime)
    transferred &= committed[:, None]
    rows = torch.arange(state.batch_size, device=state.device)
    spent = torch.zeros_like(runtime.battle.elixir)
    spent.scatter_add_(
        1,
        runtime.battle.entity_player.to(torch.int64),
        torch.where(activated, cost, 0).to(torch.float64),
    )
    runtime.battle.elixir -= spent
    state.last_use_time_ms.copy_(torch.where(activated, now, state.last_use_time_ms))
    state.activation_time_ms.copy_(
        torch.where(activated, now, state.activation_time_ms)
    )
    state.ability_active |= activated
    runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.STATUS,
        valid=transferred,
        source_id=runtime.battle.entity_id,
        target_id=runtime.battle.entity_id,
        payload=SkeletonKingEventPayload.OWNERSHIP_TRANSFERRED,
    )
    runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.COMMAND,
        valid=activated,
        source_id=runtime.battle.entity_id,
        amount=cost.to(torch.float64),
        payload=SkeletonKingEventPayload.ABILITY_ACTIVATED,
    )
    source_slots = torch.arange(state.max_entities, device=state.device)[
        None, :
    ].expand(state.batch_size, -1)
    spawned = _spawn_children_(
        state,
        runtime,
        source_slots,
        torch.where(activated, state.catalog.spawn_count[card], 0),
        state.catalog.spawn_radius_units[card],
        SkeletonKingEventPayload.ABILITY_SPAWN,
        TickPhase.COMMANDS,
    )
    consumed = consume_souls_(state.catalog.passive, state.passive, activated)
    _append_passive_events_(runtime, consumed, TickPhase.COMMANDS)
    del rows
    return SkeletonKingActivationResult(
        committed, reason, owner, transferred, activated, spawned
    )


def step_skeleton_king_(
    state: TensorSkeletonKingState,
    runtime: TensorBattleRuntime,
    *,
    dt_ms: int = 50,
) -> SkeletonKingStepResult:
    if dt_ms != 50:
        raise ValueError("exact Skeleton King lifecycle currently requires 50 ms")
    before = state.clone()
    _refresh_(state, runtime)
    present_at_start = runtime.entity_pool.active.clone()
    dying = runtime.entity_pool.active & ~runtime.battle.entity_active
    drops = plan_soul_drops(state.catalog.passive, state.passive, dying)
    drop_counts = torch.zeros_like(runtime.battle.entity_id)
    if drops.batch_index.numel():
        source_matches = (
            runtime.battle.entity_id[drops.batch_index]
            == drops.source_entity_id[:, None]
        )
        slots = source_matches.to(torch.int64).argmax(dim=1)
        drop_counts.index_put_(
            (drops.batch_index, slots),
            torch.ones_like(slots),
            accumulate=True,
        )
    free = (~runtime.entity_pool.active).sum(dim=1, dtype=torch.int64)
    total_drop = (
        drop_counts * state.catalog.child_summon_count[state.entity_card]
    ).sum(dim=1, dtype=torch.int64)
    remaining_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
    collection_preview = collect_souls_(state.catalog.passive, state.passive.clone())
    passive_counts = torch.zeros(
        state.batch_size, dtype=torch.int64, device=state.device
    )
    passive_counts.scatter_add_(
        0,
        collection_preview.batch_index,
        torch.ones_like(collection_preview.batch_index),
    )
    passive_counts.scatter_add_(
        0,
        drops.batch_index,
        torch.ones_like(drops.batch_index),
    )
    worst = (
        total_drop
        + passive_counts
        + dying.sum(dim=1)
        + 2 * state.has_ability.sum(dim=1)
    )
    reason = torch.zeros(state.batch_size, dtype=torch.int16, device=state.device)
    reason = torch.where(
        ~state.row_supported,
        torch.full_like(reason, SkeletonKingReason.UNSUPPORTED_PAYLOAD),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (total_drop > free),
        torch.full_like(reason, SkeletonKingReason.ENTITY_CAPACITY),
        reason,
    )
    reason = torch.where(
        (reason == 0) & (worst > remaining_events),
        torch.full_like(reason, SkeletonKingReason.EVENT_CAPACITY),
        reason,
    )
    committed = reason == 0
    if not bool(committed.all().item()):
        # This standalone owner uses whole-batch transactional admission. No
        # state has mutated before this return except boundary refresh planes.
        reason = torch.where(
            committed,
            torch.full_like(reason, SkeletonKingReason.BATCH_ROLLBACK),
            reason,
        )
        committed.zero_()
        state.reset_rows_(torch.arange(state.batch_size, device=state.device), before)
        return SkeletonKingStepResult(
            committed,
            reason,
            TensorPassiveEvents.empty(state.device),
            TensorPassiveEvents.empty(state.device),
            torch.zeros_like(runtime.entity_pool.active),
            torch.zeros_like(runtime.entity_pool.active),
        )
    runtime.battle.time += dt_ms / 1_000.0
    runtime.battle.tick += 1
    runtime.battle.dt.fill_(dt_ms / 1_000.0)
    runtime.battle.tick_milliseconds.fill_(dt_ms)
    now = torch.round(runtime.battle.time * 1_000).to(torch.int64)[:, None]
    ended = state.ability_active & (
        now - state.activation_time_ms
        >= state.catalog.ability_duration_ms[state.entity_card]
    )
    state.ability_active &= ~ended
    runtime.events.append(
        phase=TickPhase.COMBAT,
        opcode=RuntimeEventOpcode.STATUS,
        valid=ended,
        source_id=runtime.battle.entity_id,
        payload=SkeletonKingEventPayload.ABILITY_ENDED,
    )
    collected = collect_souls_(state.catalog.passive, state.passive)
    _append_passive_events_(runtime, collected, TickPhase.COMBAT)
    source_slots = torch.arange(state.max_entities, device=state.device)[
        None, :
    ].expand(state.batch_size, -1)
    radius = torch.full_like(drop_counts, 1_500)
    spawned = _spawn_children_(
        state,
        runtime,
        source_slots,
        drop_counts,
        radius,
        SkeletonKingEventPayload.SOUL_DROP_SPAWN,
        TickPhase.CLEANUP_AND_SPAWNS,
    )
    _append_passive_events_(runtime, drops, TickPhase.CLEANUP_AND_SPAWNS)
    runtime.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.DEATH,
        valid=dying,
        source_id=runtime.battle.entity_id,
        target_id=runtime.battle.entity_id,
    )
    runtime.entity_pool.cleanup(dying)
    for descriptor in fields(runtime.battle):
        value = getattr(runtime.battle, descriptor.name)
        if (
            isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[:2] == runtime.battle.entity_id.shape
        ):
            value[dying] = 0
    _refresh_(state, runtime)
    _, transferred = _ownership_(state, runtime)
    runtime.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.STATUS,
        valid=transferred,
        source_id=runtime.battle.entity_id,
        target_id=runtime.battle.entity_id,
        payload=SkeletonKingEventPayload.OWNERSHIP_TRANSFERRED,
    )
    # Only characters present at the start of this object phase age. Drop
    # children were appended during cleanup and begin next frame.
    start_character = present_at_start & runtime.entity_pool.active
    runtime.battle.entity_deploy_delay.copy_(
        torch.where(
            start_character,
            torch.clamp(runtime.battle.entity_deploy_delay - dt_ms / 1_000.0, min=0.0),
            runtime.battle.entity_deploy_delay,
        )
    )
    runtime.battle.entity_placement_pending &= runtime.battle.entity_deploy_delay > 1e-9
    completed_deploy = start_character & (runtime.battle.entity_deploy_delay <= 1e-9)
    runtime.battle.entity_spawn_hook_pending &= ~completed_deploy
    runtime.battle.entity_spawn_hook_fired |= completed_deploy
    return SkeletonKingStepResult(committed, reason, collected, drops, spawned, ended)


__all__ = [
    "SkeletonKingActivationResult",
    "SkeletonKingEventPayload",
    "SkeletonKingReason",
    "SkeletonKingStepResult",
    "TensorSkeletonKingCatalog",
    "TensorSkeletonKingState",
    "activate_skeleton_king_",
    "step_skeleton_king_",
]
