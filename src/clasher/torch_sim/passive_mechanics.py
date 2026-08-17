"""Generalized retained kernels for serialized passive mechanic families.

The four operations in this module are selected by mechanic opcode and
compiled serialized parameters.  Card identity never controls behavior.
Mutable state is entity-slot aligned; event streams are sorted by battle,
stable source entity ID, serialized mechanic slot, and local event index.

These passive mechanics consume no randomness.  The object-phase API accepts
the resident CPython-compatible RNG explicitly to make that zero-consumption
contract auditable before later RNG-consuming phases are integrated.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import IntEnum

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.kinematics import tiles_to_logic_units

from .catalog import MECHANIC_OPCODE
from .rng import TensorPythonRandom
from .spawn import (
    TensorPeriodicSpawnerState,
    TensorSpawnCatalog,
    step_periodic_spawners,
)

STEALTH_FOREVER_MS = 2**31 - 1


class UnsupportedPassiveDeviceError(RuntimeError):
    """Raised before mutation for devices outside the CPU/CUDA exact path."""


class PassiveEventOpcode(IntEnum):
    HIDDEN = 1
    REVEALED = 2
    INVISIBLE = 3
    VISIBLE = 4
    SOUL_COLLECTED = 5
    SOULS_CONSUMED = 6
    SOUL_DROP = 7
    PERIODIC_SPAWN = 8


def validate_passive_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type not in {"cpu", "cuda"}:
        raise UnsupportedPassiveDeviceError(
            f"passive mechanics require CPU or CUDA, got {result.type!r}"
        )
    return result


@dataclass(frozen=True)
class TensorPassiveCatalog:
    device: torch.device
    names: tuple[str, ...]
    name_to_id: dict[str, int]
    mechanic_opcode: torch.Tensor
    mechanic_count: torch.Tensor
    hide_delay_ms: torch.Tensor
    rise_time_ms: torch.Tensor
    fade_delay_ms: torch.Tensor
    fade_use_attack_range: torch.Tensor
    soul_radius_units: torch.Tensor
    souls_per_activation: torch.Tensor
    max_souls: torch.Tensor
    mechanic_slot: torch.Tensor
    periodic_operation_row: torch.Tensor
    spawn_catalog: TensorSpawnCatalog

    @property
    def max_mechanics(self) -> int:
        return int(self.mechanic_opcode.shape[1])

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        card_names: Iterable[str],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorPassiveCatalog:
        torch_device = validate_passive_device(device)
        definitions = loader.load_card_definitions()
        resolved = tuple(
            sorted({resolve_card_name(name, definitions) for name in card_names})
        )
        missing = [name for name in resolved if name not in definitions]
        if missing:
            raise ValueError(f"missing card definitions: {missing}")
        names = ("", *resolved)
        name_to_id = {name: index for index, name in enumerate(names)}
        max_mechanics = max(
            1, max((len(definitions[name].mechanics) for name in resolved), default=0)
        )
        shape = (len(names), max_mechanics)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=torch_device)

        opcode = zeros(torch.int16)
        mechanic_count = torch.zeros(len(names), dtype=torch.int8, device=torch_device)
        hide_delay = zeros(torch.int64)
        rise_time = zeros(torch.int64)
        fade_delay = zeros(torch.int64)
        fade_use_range = zeros(torch.bool)
        soul_radius = zeros(torch.int64)
        souls_per_activation = zeros(torch.int64)
        max_souls = zeros(torch.int64)
        mechanic_slot = (
            torch.arange(max_mechanics, dtype=torch.int16, device=torch_device)[None, :]
            .expand(len(names), -1)
            .clone()
        )
        periodic_row = torch.full(shape, -1, dtype=torch.int64, device=torch_device)
        spawn_catalog = TensorSpawnCatalog.compile(
            loader, resolved, device=torch_device
        )
        periodic_lookup = {
            (
                spawn_catalog.source_names[row],
                int(spawn_catalog.source_mechanic_slot[row]),
            ): row
            for row in spawn_catalog.periodic_rows().tolist()
        }

        relevant = {
            "HideWhenIdle",
            "InvisibilityWhenNotAttacking",
            "SkeletonKingSoulCollector",
            "PeriodicSpawner",
        }
        for card_id, name in enumerate(resolved, start=1):
            stats = loader.get_card(name)
            if stats is None:
                raise ValueError(f"could not materialize card {name!r}")
            raw = getattr(stats, "_raw_entry", {}) or {}
            character = raw.get("summonCharacterData", {}) or {}
            passive_count = 0
            for slot, mechanic in enumerate(definitions[name].mechanics):
                operation = type(mechanic).__name__
                if operation not in relevant:
                    continue
                passive_count += 1
                opcode[card_id, slot] = MECHANIC_OPCODE[operation]
                if operation == "HideWhenIdle":
                    serialized_hide = character.get("hideTimeMS")
                    if serialized_hide is None:
                        serialized_hide = character.get("hideTimeMs")
                    serialized_rise = character.get("upTimeMS")
                    if serialized_rise is None:
                        serialized_rise = character.get("upTimeMs")
                    hide_delay[card_id, slot] = max(
                        0,
                        int(
                            getattr(mechanic, "hide_delay_ms", 1000)
                            if serialized_hide is None
                            else serialized_hide
                        ),
                    )
                    rise_time[card_id, slot] = max(
                        0,
                        int(
                            getattr(mechanic, "rise_time_ms", 1000)
                            if serialized_rise is None
                            else serialized_rise
                        ),
                    )
                elif operation == "InvisibilityWhenNotAttacking":
                    fade_delay[card_id, slot] = max(
                        0,
                        int(
                            character.get(
                                "buffWhenNotAttackingTime",
                                getattr(mechanic, "fade_delay_ms", 2000),
                            )
                            or 0
                        ),
                    )
                    fade_use_range[card_id, slot] = bool(
                        character.get("buffWhenNotAttackingUseAttackRange", False)
                    )
                elif operation == "SkeletonKingSoulCollector":
                    soul_radius[card_id, slot] = tiles_to_logic_units(
                        float(getattr(mechanic, "soul_collection_radius"))
                    )
                    souls_per_activation[card_id, slot] = int(
                        getattr(mechanic, "souls_per_activation")
                    )
                    max_souls[card_id, slot] = int(getattr(mechanic, "max_souls"))
                else:
                    try:
                        periodic_row[card_id, slot] = periodic_lookup[(name, slot)]
                    except KeyError as exc:
                        raise ValueError(
                            f"periodic operation {name!r} slot {slot} is absent "
                            "from the spawn catalog"
                        ) from exc
            mechanic_count[card_id] = passive_count
        return cls(
            device=torch_device,
            names=names,
            name_to_id=name_to_id,
            mechanic_opcode=opcode,
            mechanic_count=mechanic_count,
            hide_delay_ms=hide_delay,
            rise_time_ms=rise_time,
            fade_delay_ms=fade_delay,
            fade_use_attack_range=fade_use_range,
            soul_radius_units=soul_radius,
            souls_per_activation=souls_per_activation,
            max_souls=max_souls,
            mechanic_slot=mechanic_slot,
            periodic_operation_row=periodic_row,
            spawn_catalog=spawn_catalog,
        )


@dataclass
class TensorPassiveState:
    entity_id: torch.Tensor
    card_id: torch.Tensor
    player: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    active: torch.Tensor
    alive: torch.Tensor
    target_slot: torch.Tensor
    hide_phase_ms: torch.Tensor
    hidden_building: torch.Tensor
    special_move_active: torch.Tensor
    fade_elapsed_ms: torch.Tensor
    stealth_until_ms: torch.Tensor
    souls_collected: torch.Tensor
    soul_ability_cost: torch.Tensor
    periodic_time_since_spawn_ms: torch.Tensor
    periodic_spawns_created: torch.Tensor
    periodic_pending_units: torch.Tensor
    periodic_time_since_unit_spawn_ms: torch.Tensor
    periodic_current_wave_spawned: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.entity_id.device

    @property
    def shape(self) -> torch.Size:
        return self.entity_id.shape

    @classmethod
    def from_entities(
        cls,
        catalog: TensorPassiveCatalog,
        *,
        entity_id: torch.Tensor,
        card_id: torch.Tensor,
        player: torch.Tensor,
        x_units: torch.Tensor,
        y_units: torch.Tensor,
        active: torch.Tensor | bool = True,
        alive: torch.Tensor | bool = True,
        target_slot: torch.Tensor | int = -1,
    ) -> TensorPassiveState:
        validate_passive_device(entity_id.device)
        ids = torch.as_tensor(entity_id, dtype=torch.int64, device=catalog.device)
        if ids.ndim != 2:
            raise ValueError("entity_id must have shape [batch, entity]")
        shape = ids.shape

        def plane(value: torch.Tensor | int | bool, dtype: torch.dtype) -> torch.Tensor:
            tensor = torch.as_tensor(value, dtype=dtype, device=catalog.device)
            try:
                return torch.broadcast_to(tensor, shape).clone()
            except RuntimeError as exc:
                raise ValueError("entity plane is not broadcastable") from exc

        cards = plane(card_id, torch.int64)
        if bool(((cards < 0) | (cards >= len(catalog.names))).any().item()):
            raise ValueError("card_id contains an out-of-range catalog ID")
        owners = plane(player, torch.int8)
        x = plane(x_units, torch.int64)
        y = plane(y_units, torch.int64)
        present = plane(active, torch.bool)
        living = plane(alive, torch.bool)
        targets = plane(target_slot, torch.int64)
        operations = catalog.mechanic_opcode[cards]
        fade_mask = (operations == MECHANIC_OPCODE["InvisibilityWhenNotAttacking"]).any(
            dim=2
        )
        fade_delay = torch.where(
            operations == MECHANIC_OPCODE["InvisibilityWhenNotAttacking"],
            catalog.fade_delay_ms[cards],
            0,
        ).sum(dim=2)
        zeros_f64 = torch.zeros(shape, dtype=torch.float64, device=catalog.device)
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=catalog.device)
        return cls(
            entity_id=ids,
            card_id=cards,
            player=owners,
            x_units=x,
            y_units=y,
            active=present,
            alive=living,
            target_slot=targets,
            hide_phase_ms=zeros_f64.clone(),
            hidden_building=torch.zeros(shape, dtype=torch.bool, device=catalog.device),
            special_move_active=torch.zeros(
                shape, dtype=torch.bool, device=catalog.device
            ),
            fade_elapsed_ms=fade_delay.to(torch.float64),
            stealth_until_ms=torch.where(
                fade_mask,
                torch.full(
                    shape, STEALTH_FOREVER_MS, dtype=torch.int64, device=catalog.device
                ),
                zeros_i64,
            ),
            souls_collected=zeros_i64.clone(),
            soul_ability_cost=torch.full(
                shape, 3, dtype=torch.int64, device=catalog.device
            ),
            periodic_time_since_spawn_ms=zeros_f64.clone(),
            periodic_spawns_created=zeros_i64.clone(),
            periodic_pending_units=zeros_i64.clone(),
            periodic_time_since_unit_spawn_ms=zeros_f64.clone(),
            periodic_current_wave_spawned=zeros_i64.clone(),
        )

    def clone(self) -> TensorPassiveState:
        return TensorPassiveState(
            **{name: getattr(self, name).clone() for name in self.__dataclass_fields__}
        )


@dataclass(frozen=True)
class TensorPassiveEvents:
    batch_index: torch.Tensor
    source_entity_id: torch.Tensor
    target_entity_id: torch.Tensor
    mechanic_slot: torch.Tensor
    local_sequence: torch.Tensor
    opcode: torch.Tensor
    amount: torch.Tensor
    payload: torch.Tensor
    formation_index: torch.Tensor
    wave_size: torch.Tensor

    @classmethod
    def empty(cls, device: torch.device) -> TensorPassiveEvents:
        integer = torch.empty((0,), dtype=torch.int64, device=device)
        return cls(
            integer,
            integer.clone(),
            integer.clone(),
            integer.clone(),
            integer.clone(),
            integer.clone(),
            torch.empty((0,), dtype=torch.float64, device=device),
            integer.clone(),
            integer.clone(),
            integer.clone(),
        )

    @classmethod
    def merge(
        cls,
        events: Iterable[TensorPassiveEvents],
        device: torch.device,
    ) -> TensorPassiveEvents:
        parts = [event for event in events if event.batch_index.numel()]
        if not parts:
            return cls.empty(device)
        values = [
            torch.cat([getattr(event, field) for event in parts])
            for field in cls.__dataclass_fields__
        ]
        result = cls(*values)
        order = torch.arange(result.batch_index.numel(), device=device)
        for key in (
            result.local_sequence,
            result.mechanic_slot,
            result.source_entity_id,
            result.batch_index,
        ):
            selected = key.index_select(0, order)
            order = order.index_select(0, torch.argsort(selected, stable=True))
        return cls(
            **{
                field: getattr(result, field).index_select(0, order)
                for field in cls.__dataclass_fields__
            }
        )


def _operation_plane(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
    opcode: int,
    values: torch.Tensor,
    *,
    default: int | float | bool = 0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    operations = catalog.mechanic_opcode[state.card_id]
    mask = operations == opcode
    if bool((mask.sum(dim=2) > 1).any().item()):
        raise ValueError("multiple same-family passive mechanics are not representable")
    selected_values = torch.where(
        mask, values[state.card_id], torch.zeros_like(values[state.card_id])
    ).sum(dim=2)
    selected = torch.where(mask.any(dim=2), selected_values, default)
    slot = torch.where(
        mask,
        catalog.mechanic_slot[state.card_id].to(torch.int64),
        torch.full_like(catalog.mechanic_slot[state.card_id], -1, dtype=torch.int64),
    ).amax(dim=2)
    return mask.any(dim=2) & state.active, selected, slot


def _transition_events(
    state: TensorPassiveState,
    mask: torch.Tensor,
    slot: torch.Tensor,
    opcode: PassiveEventOpcode,
) -> TensorPassiveEvents:
    coordinates = torch.nonzero(mask, as_tuple=False)
    if not coordinates.numel():
        return TensorPassiveEvents.empty(state.device)
    batch = coordinates[:, 0]
    entity = coordinates[:, 1]
    order = torch.arange(batch.numel(), device=state.device)
    for key in (state.entity_id[batch, entity], batch):
        order = order.index_select(
            0, torch.argsort(key.index_select(0, order), stable=True)
        )
    batch = batch.index_select(0, order)
    entity = entity.index_select(0, order)
    count = batch.numel()
    zeros = torch.zeros(count, dtype=torch.int64, device=state.device)
    return TensorPassiveEvents(
        batch_index=batch,
        source_entity_id=state.entity_id[batch, entity],
        target_entity_id=zeros,
        mechanic_slot=slot[batch, entity],
        local_sequence=zeros.clone(),
        opcode=torch.full_like(zeros, int(opcode)),
        amount=torch.zeros(count, dtype=torch.float64, device=state.device),
        payload=zeros.clone(),
        formation_index=zeros.clone(),
        wave_size=zeros.clone(),
    )


def step_hide_when_idle_(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
    dt_ms: float | torch.Tensor,
    *,
    has_attack_target: torch.Tensor,
    stunned: torch.Tensor,
    slow_multiplier: torch.Tensor,
    movement_speed_buff_multiplier: torch.Tensor,
) -> TensorPassiveEvents:
    mask, hide_delay, slot = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["HideWhenIdle"],
        catalog.hide_delay_ms,
    )
    _, rise_time, _ = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["HideWhenIdle"],
        catalog.rise_time_ms,
    )
    shape = state.shape
    target = torch.as_tensor(has_attack_target, dtype=torch.bool, device=state.device)
    frozen = torch.as_tensor(stunned, dtype=torch.bool, device=state.device)
    slow = torch.as_tensor(slow_multiplier, dtype=torch.float64, device=state.device)
    buff = torch.as_tensor(
        movement_speed_buff_multiplier, dtype=torch.float64, device=state.device
    )
    try:
        target, frozen, slow, buff = (
            torch.broadcast_to(value, shape).clone()
            for value in (target, frozen, slow, buff)
        )
    except RuntimeError as exc:
        raise ValueError("hide input is not entity-broadcastable") from exc
    dt = torch.as_tensor(dt_ms, dtype=torch.float64, device=state.device)
    if dt.ndim == 1:
        dt = dt[:, None]
    base = torch.full(shape, 50, dtype=torch.int64, device=state.device)
    buff_percent = torch.round(buff * 100.0).to(torch.int64).clamp_min(0)
    slow_percent = torch.round(slow * 100.0).to(torch.int64).clamp_min(0)
    native_work = (base * buff_percent // 100) * slow_percent // 100
    work = torch.clamp(dt, min=0.0) * native_work.to(torch.float64) / 50.0
    advancing = mask & state.alive & ~frozen
    old = state.hide_phase_ms
    next_phase = old + work
    cycle = hide_delay + rise_time
    no_target = advancing & ~target
    exact_hide = no_target & (next_phase >= hide_delay) & (old <= hide_delay)
    safe_cycle = torch.where(cycle > 0, cycle, 1)
    no_target_phase = torch.where(
        exact_hide,
        hide_delay.to(torch.float64),
        torch.where(
            cycle > 0,
            torch.remainder(next_phase, safe_cycle),
            old,
        ),
    )
    reverse = target & (old < hide_delay)
    target_next = torch.where(reverse, torch.clamp(old - work, min=0.0), next_phase)
    fully_up = target & ((target_next > cycle) | (old == 0.0))
    target_phase = torch.where(
        fully_up,
        0.0,
        torch.where(
            cycle > 0,
            torch.remainder(target_next, safe_cycle),
            old,
        ),
    )
    updated = torch.where(target, target_phase, no_target_phase)
    state.hide_phase_ms.copy_(torch.where(advancing, updated, old))
    before_hidden = state.hidden_building.clone()
    hidden = mask & (
        torch.abs(state.hide_phase_ms - hide_delay.to(torch.float64)) <= 1e-9
    )
    state.hidden_building.copy_(torch.where(mask, hidden, state.hidden_building))
    state.special_move_active.copy_(
        torch.where(mask, hidden, state.special_move_active)
    )
    state.target_slot.copy_(torch.where(hidden, -1, state.target_slot))
    return TensorPassiveEvents.merge(
        (
            _transition_events(
                state, mask & ~before_hidden & hidden, slot, PassiveEventOpcode.HIDDEN
            ),
            _transition_events(
                state, mask & before_hidden & ~hidden, slot, PassiveEventOpcode.REVEALED
            ),
        ),
        state.device,
    )


def step_invisibility_when_not_attacking_(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
    dt_ms: float | torch.Tensor,
    *,
    attack_started: torch.Tensor,
    has_attack_range_target: torch.Tensor,
) -> TensorPassiveEvents:
    mask, fade_delay, slot = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["InvisibilityWhenNotAttacking"],
        catalog.fade_delay_ms,
    )
    _, use_range_value, _ = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["InvisibilityWhenNotAttacking"],
        catalog.fade_use_attack_range,
    )
    shape = state.shape
    attack = torch.broadcast_to(
        torch.as_tensor(attack_started, dtype=torch.bool, device=state.device), shape
    ).clone()
    in_range = torch.broadcast_to(
        torch.as_tensor(has_attack_range_target, dtype=torch.bool, device=state.device),
        shape,
    ).clone()
    dt = torch.as_tensor(dt_ms, dtype=torch.float64, device=state.device)
    if dt.ndim == 1:
        dt = dt[:, None]
    before_invisible = state.stealth_until_ms == STEALTH_FOREVER_MS
    started = mask & state.alive & attack
    state.fade_elapsed_ms.copy_(torch.where(started, 0.0, state.fade_elapsed_ms))
    state.stealth_until_ms.copy_(torch.where(started, 0, state.stealth_until_ms))
    held_in_melee = mask & state.alive & use_range_value.to(torch.bool) & in_range
    state.fade_elapsed_ms.copy_(torch.where(held_in_melee, 0.0, state.fade_elapsed_ms))
    advancing = mask & state.alive & ~held_in_melee
    elapsed = state.fade_elapsed_ms + torch.clamp(dt, min=0.0)
    state.fade_elapsed_ms.copy_(torch.where(advancing, elapsed, state.fade_elapsed_ms))
    fade_complete = advancing & (state.fade_elapsed_ms >= fade_delay)
    state.stealth_until_ms.copy_(
        torch.where(fade_complete, STEALTH_FOREVER_MS, state.stealth_until_ms)
    )
    invisible = state.stealth_until_ms == STEALTH_FOREVER_MS
    return TensorPassiveEvents.merge(
        (
            _transition_events(
                state,
                mask & before_invisible & ~invisible,
                slot,
                PassiveEventOpcode.VISIBLE,
            ),
            _transition_events(
                state,
                mask & ~before_invisible & invisible,
                slot,
                PassiveEventOpcode.INVISIBLE,
            ),
        ),
        state.device,
    )


def collect_souls_(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
) -> TensorPassiveEvents:
    mask, radius, slot = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["SkeletonKingSoulCollector"],
        catalog.soul_radius_units,
    )
    _, threshold, _ = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["SkeletonKingSoulCollector"],
        catalog.souls_per_activation,
    )
    _, maximum, _ = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["SkeletonKingSoulCollector"],
        catalog.max_souls,
    )
    maximum_id = torch.iinfo(torch.int64).max
    collector_order = torch.argsort(
        torch.where(mask & state.alive, state.entity_id, maximum_id), dim=1
    )
    dead_order = torch.argsort(
        torch.where(state.active & ~state.alive, state.entity_id, maximum_id), dim=1
    )
    rows = torch.arange(state.shape[0], device=state.device)
    event_parts: list[TensorPassiveEvents] = []
    local_sequence = torch.zeros(state.shape[0], dtype=torch.int64, device=state.device)
    for collector_rank in range(state.shape[1]):
        collector = collector_order[:, collector_rank]
        collector_valid = mask[rows, collector] & state.alive[rows, collector]
        for dead_rank in range(state.shape[1]):
            target = dead_order[:, dead_rank]
            target_valid = state.active[rows, target] & ~state.alive[rows, target]
            dx = state.x_units[rows, target] - state.x_units[rows, collector]
            dy = state.y_units[rows, target] - state.y_units[rows, collector]
            in_radius = dx * dx + dy * dy <= radius[rows, collector] ** 2
            enemy = state.player[rows, target] != state.player[rows, collector]
            can_increment = (
                collector_valid
                & target_valid
                & enemy
                & (state.entity_id[rows, target] != state.entity_id[rows, collector])
                & in_radius
                & (state.souls_collected[rows, collector] < maximum[rows, collector])
            )
            state.souls_collected[rows, collector] += can_increment.to(torch.int64)
            coordinates = torch.nonzero(can_increment, as_tuple=False).flatten()
            if coordinates.numel():
                count = coordinates.numel()
                zeros = torch.zeros(count, dtype=torch.int64, device=state.device)
                event_parts.append(
                    TensorPassiveEvents(
                        batch_index=coordinates,
                        source_entity_id=state.entity_id[
                            coordinates, collector[coordinates]
                        ],
                        target_entity_id=state.entity_id[
                            coordinates, target[coordinates]
                        ],
                        mechanic_slot=slot[coordinates, collector[coordinates]],
                        local_sequence=local_sequence[coordinates],
                        opcode=torch.full_like(
                            zeros, int(PassiveEventOpcode.SOUL_COLLECTED)
                        ),
                        amount=torch.ones(
                            count, dtype=torch.float64, device=state.device
                        ),
                        payload=state.souls_collected[
                            coordinates, collector[coordinates]
                        ],
                        formation_index=zeros.clone(),
                        wave_size=zeros.clone(),
                    )
                )
                local_sequence[coordinates] += 1
    ready = state.souls_collected >= threshold
    discounted = torch.clamp(3 - state.souls_collected // 10, min=1)
    state.soul_ability_cost.copy_(torch.where(mask & ready, discounted, 3))
    return TensorPassiveEvents.merge(event_parts, state.device)


def consume_souls_(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
    activated: torch.Tensor,
) -> TensorPassiveEvents:
    mask, threshold, slot = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["SkeletonKingSoulCollector"],
        catalog.souls_per_activation,
    )
    requested = torch.broadcast_to(
        torch.as_tensor(activated, dtype=torch.bool, device=state.device), state.shape
    ).clone()
    consumed = mask & requested & (state.souls_collected >= threshold)
    state.souls_collected.copy_(
        torch.where(
            consumed,
            torch.clamp(state.souls_collected - threshold, min=0),
            state.souls_collected,
        )
    )
    state.soul_ability_cost.copy_(
        torch.where(
            mask & (state.souls_collected >= threshold),
            torch.clamp(3 - state.souls_collected // 10, min=1),
            3,
        )
    )
    events = _transition_events(
        state, consumed, slot, PassiveEventOpcode.SOULS_CONSUMED
    )
    if events.amount.numel():
        source_matches = (
            state.entity_id.index_select(0, events.batch_index)
            == events.source_entity_id[:, None]
        )
        source_slot = source_matches.to(torch.int64).argmax(dim=1)
        amount = threshold[events.batch_index, source_slot].to(torch.float64)
        events = replace(events, amount=amount)
    return events


def plan_soul_drops(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
    died: torch.Tensor,
) -> TensorPassiveEvents:
    mask, _, slot = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["SkeletonKingSoulCollector"],
        catalog.max_souls,
    )
    selected = mask & torch.broadcast_to(
        torch.as_tensor(died, dtype=torch.bool, device=state.device), state.shape
    )
    drop_count = torch.clamp(state.souls_collected // 2, min=0, max=10)
    eligible = selected & (drop_count > 0)
    maximum_id = torch.iinfo(torch.int64).max
    order = torch.argsort(torch.where(eligible, state.entity_id, maximum_id), dim=1)
    ordered = eligible.gather(1, order)
    ranked_coordinates = torch.nonzero(ordered, as_tuple=False)
    if not ranked_coordinates.numel():
        return TensorPassiveEvents.empty(state.device)
    coordinates = torch.stack(
        (
            ranked_coordinates[:, 0],
            order[ranked_coordinates[:, 0], ranked_coordinates[:, 1]],
        ),
        dim=1,
    )
    counts = drop_count[coordinates[:, 0], coordinates[:, 1]]
    repeated = coordinates.repeat_interleave(counts, dim=0)
    local = torch.cat(
        [torch.arange(int(count), device=state.device) for count in counts.tolist()]
    )
    batch = repeated[:, 0]
    entity = repeated[:, 1]
    total = batch.numel()
    zeros = torch.zeros(total, dtype=torch.int64, device=state.device)
    return TensorPassiveEvents(
        batch_index=batch,
        source_entity_id=state.entity_id[batch, entity],
        target_entity_id=zeros,
        mechanic_slot=slot[batch, entity],
        local_sequence=local,
        opcode=torch.full_like(zeros, int(PassiveEventOpcode.SOUL_DROP)),
        amount=torch.ones(total, dtype=torch.float64, device=state.device),
        payload=zeros.clone(),
        formation_index=local,
        wave_size=counts.repeat_interleave(counts),
    )


def step_periodic_spawner_passives_(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
    dt_ms: float | torch.Tensor,
    *,
    stunned: torch.Tensor,
    spawn_rate: torch.Tensor,
) -> TensorPassiveEvents:
    mask, operation_row, slot = _operation_plane(
        catalog,
        state,
        MECHANIC_OPCODE["PeriodicSpawner"],
        catalog.periodic_operation_row,
        default=-1,
    )
    periodic_rows = catalog.spawn_catalog.periodic_rows()
    if periodic_rows.numel() == 0:
        return TensorPassiveEvents.empty(state.device)
    maximum_id = torch.iinfo(torch.int64).max
    order = torch.argsort(torch.where(mask, state.entity_id, maximum_id), dim=1)
    gathered_rows = operation_row.gather(1, order)
    gathered_mask = mask.gather(1, order)
    gathered_rows = torch.where(
        gathered_mask,
        gathered_rows,
        torch.full_like(gathered_rows, int(periodic_rows[0].item())),
    )
    compact = TensorPeriodicSpawnerState(
        time_since_spawn_ms=state.periodic_time_since_spawn_ms.gather(1, order).clone(),
        spawns_created=state.periodic_spawns_created.gather(1, order).clone(),
        pending_units=state.periodic_pending_units.gather(1, order).clone(),
        time_since_unit_spawn_ms=(
            state.periodic_time_since_unit_spawn_ms.gather(1, order).clone()
        ),
        current_wave_spawned=(
            state.periodic_current_wave_spawned.gather(1, order).clone()
        ),
    )
    frozen = torch.broadcast_to(
        torch.as_tensor(stunned, dtype=torch.bool, device=state.device), state.shape
    ).gather(1, order)
    rate = torch.broadcast_to(
        torch.as_tensor(spawn_rate, dtype=torch.float64, device=state.device),
        state.shape,
    ).gather(1, order)
    active = gathered_mask & state.alive.gather(1, order) & ~frozen
    dt = torch.as_tensor(dt_ms, dtype=torch.float64, device=state.device)
    if dt.ndim == 1:
        dt = dt[:, None]
    spawned = step_periodic_spawners(
        catalog.spawn_catalog,
        compact,
        dt,
        operation_rows=gathered_rows,
        active=active,
        spawn_rate=rate,
    )
    state.periodic_time_since_spawn_ms.scatter_(1, order, compact.time_since_spawn_ms)
    state.periodic_spawns_created.scatter_(1, order, compact.spawns_created)
    state.periodic_pending_units.scatter_(1, order, compact.pending_units)
    state.periodic_time_since_unit_spawn_ms.scatter_(
        1, order, compact.time_since_unit_spawn_ms
    )
    state.periodic_current_wave_spawned.scatter_(1, order, compact.current_wave_spawned)
    if not spawned.batch_index.numel():
        return TensorPassiveEvents.empty(state.device)
    source_slot = order[spawned.batch_index, spawned.source_column]
    total = source_slot.numel()
    zeros = torch.zeros(total, dtype=torch.int64, device=state.device)
    return TensorPassiveEvents(
        batch_index=spawned.batch_index,
        source_entity_id=state.entity_id[spawned.batch_index, source_slot],
        target_entity_id=zeros,
        mechanic_slot=slot[spawned.batch_index, source_slot],
        local_sequence=torch.arange(total, device=state.device),
        opcode=torch.full_like(zeros, int(PassiveEventOpcode.PERIODIC_SPAWN)),
        amount=torch.ones(total, dtype=torch.float64, device=state.device),
        payload=spawned.catalog_row,
        formation_index=spawned.formation_index,
        wave_size=spawned.wave_size,
    )


def step_passive_object_phase_(
    catalog: TensorPassiveCatalog,
    state: TensorPassiveState,
    dt_ms: float | torch.Tensor,
    *,
    has_attack_target: torch.Tensor,
    has_attack_range_target: torch.Tensor,
    attack_started: torch.Tensor,
    stunned: torch.Tensor,
    slow_multiplier: torch.Tensor,
    movement_speed_buff_multiplier: torch.Tensor,
    spawn_rate: torch.Tensor,
    rng: TensorPythonRandom | None = None,
) -> TensorPassiveEvents:
    """Advance object hooks; ``rng`` is intentionally retained unchanged."""

    if rng is not None and (
        rng.device != state.device or rng.batch_size != state.shape[0]
    ):
        raise ValueError("RNG and passive state batches differ")
    return TensorPassiveEvents.merge(
        (
            step_hide_when_idle_(
                catalog,
                state,
                dt_ms,
                has_attack_target=has_attack_target,
                stunned=stunned,
                slow_multiplier=slow_multiplier,
                movement_speed_buff_multiplier=movement_speed_buff_multiplier,
            ),
            step_invisibility_when_not_attacking_(
                catalog,
                state,
                dt_ms,
                attack_started=attack_started,
                has_attack_range_target=has_attack_range_target,
            ),
            step_periodic_spawner_passives_(
                catalog,
                state,
                dt_ms,
                stunned=stunned,
                spawn_rate=spawn_rate,
            ),
        ),
        state.device,
    )
