"""Retained generalized mechanic composition for :class:`TensorBattleRuntime`.

This module owns mutable planes for mechanics whose component hooks cross the
ordinary combat/status boundary: whole-hit shields, serialized on-hit status
payloads, and serialized Champion cloak abilities.  Selection is exclusively
by mechanic opcode/capability; card identities never control behavior.

Python entities are consulted only by :meth:`from_battles` and
:meth:`sync_to_battles`.  Production phase methods operate on dense tensors,
batch every battle together, and loop only over fixed event lanes to preserve
the oracle's committed-hit order.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.balance import LOGIC_CHAMPION_CAN_EXECUTE_ABILITY_FROZEN
from clasher.battle import BattleState

from .catalog import MECHANIC_OPCODE
from .runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TensorRuntimeEvents,
    TickPhase,
)
from .shield_champion import (
    NEVER_USED_TIME_MS,
    ChampionTickResult,
    TensorShieldChampionCatalog,
    activate_champion_abilities_,
    apply_shield_damage_,
    champion_button_owner_mask,
    champion_can_activate,
    champion_owner_mask,
    refresh_champion_ownership_,
    tick_champion_abilities_,
)
from .status import TensorStatusState
from .status_payloads import (
    StatusTriggerOpcode,
    TensorStatusPayloadCatalog,
    apply_status_payloads,
)


class UnsupportedMechanicDeviceError(RuntimeError):
    """Raised before mutation when exact mechanic state cannot use a device."""


class MechanicEventPayload(IntEnum):
    SHIELD_ABSORBED = 1
    SHIELD_BROKEN = 2
    SERIALIZED_ON_HIT_STATUS = 3
    CHAMPION_OWNERSHIP_TRANSFERRED = 4
    CHAMPION_ACTIVATED = 5
    CLOAK_STARTED = 6
    CLOAK_ENDED = 7
    CAST_LOCK_ENDED = 8
    ABILITY_CANCELLED = 9
    CHAMPION_DIED = 10


@dataclass(frozen=True)
class MechanicHitResult:
    hitpoint_damage: torch.Tensor
    shield_absorbed: torch.Tensor
    shield_broken: torch.Tensor
    status_dispatched: torch.Tensor
    target_died: torch.Tensor


@dataclass(frozen=True)
class MechanicActivationResult:
    owner: torch.Tensor
    transferred: torch.Tensor
    can_activate: torch.Tensor
    activated: torch.Tensor


def validate_mechanic_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type == "mps":
        raise UnsupportedMechanicDeviceError(
            "exact runtime mechanics require float64 and fail closed on MPS"
        )
    if result.type not in {"cpu", "cuda"}:
        raise UnsupportedMechanicDeviceError(
            f"runtime mechanics do not support device type {result.type!r}"
        )
    return result


def _clone_status(state: TensorStatusState) -> TensorStatusState:
    return TensorStatusState(
        **{
            descriptor.name: getattr(state, descriptor.name).clone()
            for descriptor in fields(state)
        }
    )


def _copy_status_(destination: TensorStatusState, source: TensorStatusState) -> None:
    for descriptor in fields(destination):
        getattr(destination, descriptor.name).copy_(getattr(source, descriptor.name))


def _ensure_event_capacity(
    events: TensorRuntimeEvents,
    additions: torch.Tensor,
) -> None:
    added = additions.to(device=events.device, dtype=torch.int64)
    if added.shape != (events.batch_size,):
        raise ValueError("event additions must have shape [batch]")
    if bool(((events.count.to(torch.int64) + added) > events.capacity).any().item()):
        raise OverflowError("runtime event capacity exhausted")


def _masked_status_catalog(
    catalog: TensorStatusPayloadCatalog,
    battles: Sequence[BattleState],
) -> TensorStatusPayloadCatalog:
    """Retain only SerializedOnHitBuff hooks in the shared status catalog."""

    definitions = battles[0].card_loader.load_card_definitions()
    trigger = catalog.trigger.clone()
    for card_id, name in enumerate(catalog.names[1:], start=1):
        payload_slot = 0
        for mechanic in definitions[name].mechanics:
            mechanic_name = type(mechanic).__name__
            if mechanic_name not in {"SerializedOnHitBuff", "Stun", "FreezeDebuff"}:
                continue
            if mechanic_name != "SerializedOnHitBuff":
                trigger[card_id, payload_slot] = int(StatusTriggerOpcode.PADDING)
            payload_slot += 1
    return TensorStatusPayloadCatalog(
        device=catalog.device,
        names=catalog.names,
        name_to_id=catalog.name_to_id,
        trigger=trigger,
        effect=catalog.effect,
        count=catalog.count,
        duration_ms=catalog.duration_ms,
        duration_from_tick=catalog.duration_from_tick,
        movement_multiplier=catalog.movement_multiplier,
        attack_multiplier=catalog.attack_multiplier,
        spawn_multiplier=catalog.spawn_multiplier,
        chance=catalog.chance,
        radius_units=catalog.radius_units,
    )


@dataclass
class TensorRuntimeMechanics:
    """Mutable mechanic planes aligned with the canonical runtime slots."""

    catalog: TensorShieldChampionCatalog
    on_hit_catalog: TensorStatusPayloadCatalog
    core_card_to_mechanic_card: torch.Tensor
    entity_mechanic_card: torch.Tensor
    initialized: torch.Tensor
    initialized_entity_id: torch.Tensor
    has_shield: torch.Tensor
    shield_current: torch.Tensor
    shield_max: torch.Tensor
    shield_break_count: torch.Tensor
    has_ability: torch.Tensor
    ability_key: torch.Tensor
    cloak_mask: torch.Tensor
    ability_elixir_cost: torch.Tensor
    ability_cooldown_ms: torch.Tensor
    ability_duration_ms: torch.Tensor
    attack_speed_multiplier: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    cast_time_ms: torch.Tensor
    trigger_delay_ms: torch.Tensor
    last_use_time_ms: torch.Tensor
    ability_active: torch.Tensor
    activation_time_ms: torch.Tensor
    cloak_pending_until_ms: torch.Tensor
    cast_lock_until_ms: torch.Tensor
    attack_mode_multiplier: torch.Tensor
    movement_mode_multiplier: torch.Tensor
    original_movement_mode_multiplier: torch.Tensor
    stealth_until_ms: torch.Tensor
    recorded_owner_id: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.entity_mechanic_card.device

    @property
    def batch_size(self) -> int:
        return int(self.entity_mechanic_card.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.entity_mechanic_card.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorRuntimeMechanics:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime batch")
        validate_mechanic_device(runtime.device)
        names = runtime.catalog.names[1:]
        catalog = TensorShieldChampionCatalog.compile(
            battles[0].card_loader, names, device=runtime.device
        )
        raw_status = TensorStatusPayloadCatalog.compile(
            battles[0].card_loader, names, device=runtime.device
        )
        on_hit_catalog = _masked_status_catalog(raw_status, battles)
        core_map = torch.full(
            (len(runtime.battle.card_names),),
            -1,
            dtype=torch.int64,
            device=runtime.device,
        )
        core_map[0] = 0
        for core_id, name in enumerate(runtime.battle.card_names[1:], start=1):
            core_map[core_id] = catalog.name_to_id.get(name, -1)
        entity_card = core_map[runtime.battle.entity_card]
        shape = runtime.battle.entity_id.shape
        zeros_f64 = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        phase = cls(
            catalog=catalog,
            on_hit_catalog=on_hit_catalog,
            core_card_to_mechanic_card=core_map,
            entity_mechanic_card=entity_card.clone(),
            initialized=runtime.entity_pool.active.clone(),
            initialized_entity_id=torch.where(
                runtime.entity_pool.active,
                runtime.battle.entity_id,
                torch.zeros_like(runtime.battle.entity_id),
            ),
            has_shield=torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            shield_current=zeros_f64.clone(),
            shield_max=zeros_f64.clone(),
            shield_break_count=zeros_i64.clone(),
            has_ability=torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            ability_key=zeros_i64.clone(),
            cloak_mask=torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            ability_elixir_cost=zeros_i64.clone(),
            ability_cooldown_ms=zeros_i64.clone(),
            ability_duration_ms=zeros_i64.clone(),
            attack_speed_multiplier=torch.ones_like(zeros_f64),
            movement_speed_multiplier=torch.ones_like(zeros_f64),
            cast_time_ms=zeros_i64.clone(),
            trigger_delay_ms=zeros_i64.clone(),
            last_use_time_ms=torch.full_like(zeros_i64, NEVER_USED_TIME_MS),
            ability_active=torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            activation_time_ms=zeros_i64.clone(),
            cloak_pending_until_ms=torch.full_like(zeros_i64, -1),
            cast_lock_until_ms=torch.full_like(zeros_i64, -1),
            attack_mode_multiplier=torch.ones_like(zeros_f64),
            movement_mode_multiplier=torch.ones_like(zeros_f64),
            original_movement_mode_multiplier=torch.full_like(zeros_f64, math.nan),
            stealth_until_ms=zeros_i64.clone(),
            recorded_owner_id=torch.zeros(
                (runtime.batch_size, 2, len(catalog.names)),
                dtype=torch.int64,
                device=runtime.device,
            ),
        )
        phase._refresh_compiled_planes_(runtime, initialize_new=False)

        shield_opcode = MECHANIC_OPCODE["Shield"]
        cloak_opcode = MECHANIC_OPCODE["ArcherQueenCloak"]
        for batch_index, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(
                    runtime.battle.entity_id[batch_index].tolist()
                )
                if entity_id
            }
            if set(slot_by_id) != set(battle.entities):
                raise ValueError("runtime/oracle entity identity sets differ")
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                index = (batch_index, slot)
                seen_shield = 0
                seen_cloak = 0
                for mechanic in entity.mechanics:
                    opcode = MECHANIC_OPCODE.get(type(mechanic).__name__, 0)
                    if opcode == shield_opcode:
                        seen_shield += 1
                        phase.shield_current[index] = float(
                            getattr(mechanic, "current_shield")
                        )
                        phase.shield_max[index] = float(getattr(mechanic, "max_shield"))
                    elif opcode == cloak_opcode:
                        seen_cloak += 1
                        ability = getattr(mechanic, "ability")
                        phase.last_use_time_ms[index] = int(ability.last_use_time)
                        phase.ability_active[index] = bool(ability.is_active)
                        phase.activation_time_ms[index] = int(ability.activation_time)
                        phase.cloak_pending_until_ms[index] = (
                            -1
                            if getattr(mechanic, "_cloak_pending_until") is None
                            else int(getattr(mechanic, "_cloak_pending_until"))
                        )
                        phase.cast_lock_until_ms[index] = (
                            -1
                            if getattr(mechanic, "_cast_lock_until") is None
                            else int(getattr(mechanic, "_cast_lock_until"))
                        )
                        original = getattr(
                            mechanic, "_original_movement_mode_multiplier"
                        )
                        phase.original_movement_mode_multiplier[index] = (
                            math.nan if original is None else float(original)
                        )
                if seen_shield > 1 or seen_cloak > 1:
                    raise ValueError(
                        "multiple same-lane mechanics are not representable"
                    )
                phase.shield_break_count[index] = int(
                    getattr(entity, "_shield_break_count", 0)
                )
                phase.attack_mode_multiplier[index] = float(
                    getattr(entity, "attack_mode_multiplier", 1.0)
                )
                phase.movement_mode_multiplier[index] = float(
                    getattr(entity, "movement_mode_multiplier", 1.0)
                )
                phase.stealth_until_ms[index] = int(
                    getattr(entity, "_stealth_until", 0) or 0
                )
        phase._initialize_recorded_owners_(runtime)
        phase.assert_invariants(runtime)
        return phase

    def _refresh_compiled_planes_(
        self,
        runtime: TensorBattleRuntime,
        *,
        initialize_new: bool,
    ) -> torch.Tensor:
        self.entity_mechanic_card.copy_(
            self.core_card_to_mechanic_card[runtime.battle.entity_card]
        )
        safe_card = self.entity_mechanic_card.clamp(min=0)
        operations = self.catalog.mechanic_opcode[safe_card]
        shield_slots = operations == MECHANIC_OPCODE["Shield"]
        cloak_slots = operations == MECHANIC_OPCODE["ArcherQueenCloak"]
        if bool((shield_slots.sum(dim=2) > 1).any().item()) or bool(
            (cloak_slots.sum(dim=2) > 1).any().item()
        ):
            raise ValueError("multiple same-lane mechanics are not representable")
        present = runtime.entity_pool.active & (self.entity_mechanic_card >= 0)
        self.has_shield.copy_(present & shield_slots.any(dim=2))
        self.has_ability.copy_(present & cloak_slots.any(dim=2))
        self.cloak_mask.copy_(self.has_ability)
        self.ability_key.copy_(
            torch.where(
                self.has_ability,
                self.entity_mechanic_card,
                torch.zeros_like(self.ability_key),
            )
        )

        def selected(table: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
            values = table[safe_card]
            return torch.where(mask, values, torch.zeros_like(values)).sum(dim=2)

        same_entity = (
            self.initialized
            & runtime.entity_pool.active
            & (self.initialized_entity_id == runtime.battle.entity_id)
        )
        compiled_shield = selected(self.catalog.shield_hitpoints, shield_slots)
        self.shield_max.copy_(
            torch.where(same_entity, self.shield_max, compiled_shield)
        )
        for destination, table in (
            (self.ability_elixir_cost, self.catalog.ability_elixir_cost),
            (self.ability_cooldown_ms, self.catalog.ability_cooldown_ms),
            (self.ability_duration_ms, self.catalog.ability_duration_ms),
            (self.cast_time_ms, self.catalog.cast_time_ms),
            (self.trigger_delay_ms, self.catalog.trigger_delay_ms),
        ):
            destination.copy_(selected(table, cloak_slots).to(destination.dtype))
        attack = selected(self.catalog.attack_speed_multiplier, cloak_slots)
        movement = selected(self.catalog.movement_speed_multiplier, cloak_slots)
        self.attack_speed_multiplier.copy_(torch.where(self.cloak_mask, attack, 1.0))
        self.movement_speed_multiplier.copy_(
            torch.where(self.cloak_mask, movement, 1.0)
        )
        new = runtime.entity_pool.active & ~same_entity
        if initialize_new:
            self.shield_current.copy_(
                torch.where(new & self.has_shield, compiled_shield, self.shield_current)
            )
            self.shield_max.copy_(
                torch.where(new & self.has_shield, compiled_shield, self.shield_max)
            )
            self.shield_break_count.copy_(torch.where(new, 0, self.shield_break_count))
            self.last_use_time_ms.copy_(
                torch.where(new, NEVER_USED_TIME_MS, self.last_use_time_ms)
            )
            self.ability_active &= ~new
            self.activation_time_ms.copy_(torch.where(new, 0, self.activation_time_ms))
            self.cloak_pending_until_ms.copy_(
                torch.where(new, -1, self.cloak_pending_until_ms)
            )
            self.cast_lock_until_ms.copy_(torch.where(new, -1, self.cast_lock_until_ms))
            self.attack_mode_multiplier.copy_(
                torch.where(new, 1.0, self.attack_mode_multiplier)
            )
            self.movement_mode_multiplier.copy_(
                torch.where(new, 1.0, self.movement_mode_multiplier)
            )
            self.original_movement_mode_multiplier.copy_(
                torch.where(
                    new,
                    torch.full_like(self.original_movement_mode_multiplier, math.nan),
                    self.original_movement_mode_multiplier,
                )
            )
            self.stealth_until_ms.copy_(torch.where(new, 0, self.stealth_until_ms))
            self.initialized.copy_(runtime.entity_pool.active)
            self.initialized_entity_id.copy_(
                torch.where(
                    runtime.entity_pool.active,
                    runtime.battle.entity_id,
                    torch.zeros_like(runtime.battle.entity_id),
                )
            )
        return new

    def refresh_new_entities_(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        self._assert_runtime(runtime)
        new = self._refresh_compiled_planes_(runtime, initialize_new=True)
        if bool(new.any().item()):
            runtime.mark_dirty(new.any(dim=1), phase=TickPhase.CLEANUP_AND_SPAWNS)
        return new

    def _initialize_recorded_owners_(self, runtime: TensorBattleRuntime) -> None:
        owners = champion_owner_mask(
            runtime.battle.entity_id,
            runtime.battle.entity_player,
            self.ability_key,
            runtime.battle.entity_active,
            self.has_ability,
        )
        key_count = self.recorded_owner_id.shape[2]
        group = (
            runtime.battle.entity_player.to(torch.int64) * key_count + self.ability_key
        ).clamp(min=0, max=2 * key_count - 1)
        selected = torch.zeros(
            (self.batch_size, 2 * key_count),
            dtype=torch.int64,
            device=self.device,
        )
        selected.scatter_reduce_(
            1,
            group,
            torch.where(owners, runtime.battle.entity_id, 0),
            reduce="amax",
            include_self=True,
        )
        self.recorded_owner_id.copy_(selected.reshape_as(self.recorded_owner_id))

    def _assert_runtime(self, runtime: TensorBattleRuntime) -> None:
        validate_mechanic_device(runtime.device)
        if runtime.device != self.device:
            raise ValueError("runtime and mechanic planes use different devices")
        if runtime.battle.entity_id.shape != self.entity_mechanic_card.shape:
            raise ValueError("runtime and mechanic entity shapes differ")

    def assert_invariants(self, runtime: TensorBattleRuntime) -> None:
        self._assert_runtime(runtime)
        expected = runtime.battle.entity_id.shape
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and descriptor.name not in {
                "core_card_to_mechanic_card",
                "recorded_owner_id",
            }:
                if value.shape != expected:
                    raise ValueError(
                        f"mechanic plane {descriptor.name} has shape {value.shape}"
                    )
                if value.device != self.device:
                    raise ValueError("mechanic planes use different devices")

    def clone(self) -> TensorRuntimeMechanics:
        return self.fork()

    def fork(
        self,
        battle_indices: Sequence[int] | torch.Tensor | None = None,
        *,
        copies: int = 1,
    ) -> TensorRuntimeMechanics:
        """Fork selected battle rows while sharing immutable mechanic catalogs."""

        if copies < 1:
            raise ValueError("copies must be positive")
        indices = (
            torch.arange(self.batch_size, dtype=torch.int64, device=self.device)
            if battle_indices is None
            else torch.as_tensor(battle_indices, dtype=torch.int64, device=self.device)
        )
        if indices.ndim != 1 or indices.numel() < 1:
            raise ValueError("battle_indices must be a non-empty vector")
        if bool(((indices < 0) | (indices >= self.batch_size)).any().item()):
            raise IndexError("battle index outside mechanic batch")
        indices = torch.repeat_interleave(indices, copies)
        values: dict[str, object] = {}
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if descriptor.name == "core_card_to_mechanic_card":
                values[descriptor.name] = value.clone()
            elif isinstance(value, torch.Tensor):
                values[descriptor.name] = value.index_select(0, indices).clone()
            else:
                values[descriptor.name] = value
        return TensorRuntimeMechanics(**values)  # type: ignore[arg-type]

    def _source_has_on_hit(self, source_card: torch.Tensor) -> torch.Tensor:
        trigger = self.on_hit_catalog.trigger[source_card.clamp(min=0)]
        duration = self.on_hit_catalog.duration_ms[source_card.clamp(min=0)]
        return ((trigger == int(StatusTriggerOpcode.ATTACK_HIT)) & (duration > 0)).any(
            dim=2
        )

    def resolve_attack_hits_(
        self,
        runtime: TensorBattleRuntime,
        *,
        source_slot: torch.Tensor,
        target_slot: torch.Tensor,
        incoming_damage: torch.Tensor,
        valid: torch.Tensor | bool = True,
        status_eligible: torch.Tensor | bool | None = None,
    ) -> MechanicHitResult:
        """Resolve ordered committed hits through shield, HP, and on-hit hooks."""

        self._assert_runtime(runtime)
        source = torch.as_tensor(source_slot, dtype=torch.int64, device=self.device)
        target = torch.as_tensor(target_slot, dtype=torch.int64, device=self.device)
        damage = torch.as_tensor(
            incoming_damage, dtype=torch.float64, device=self.device
        )
        if source.ndim != 2 or source.shape[0] != self.batch_size:
            raise ValueError("source_slot must have shape [batch, event]")
        if target.shape != source.shape or damage.shape != source.shape:
            raise ValueError("hit tensors must have identical shapes")
        selected = torch.as_tensor(valid, dtype=torch.bool, device=self.device)
        try:
            selected = torch.broadcast_to(selected, source.shape).clone()
        except RuntimeError as exc:
            raise ValueError("valid is not broadcastable to hit shape") from exc
        status_selected = (
            selected.clone()
            if status_eligible is None
            else torch.as_tensor(status_eligible, dtype=torch.bool, device=self.device)
        )
        try:
            status_selected = torch.broadcast_to(status_selected, source.shape).clone()
        except RuntimeError as exc:
            raise ValueError(
                "status_eligible is not broadcastable to hit shape"
            ) from exc
        status_selected &= selected
        in_bounds = (
            (source >= 0)
            & (source < self.max_entities)
            & (target >= 0)
            & (target < self.max_entities)
        )
        if bool((selected & ~in_bounds).any().item()):
            raise IndexError("valid hit references an entity slot outside the runtime")
        safe_source = source.clamp(min=0, max=self.max_entities - 1)
        safe_target = target.clamp(min=0, max=self.max_entities - 1)
        active_source = runtime.entity_pool.active.gather(1, safe_source)
        active_target = runtime.entity_pool.active.gather(1, safe_target)
        if bool((selected & ~(active_source & active_target)).any().item()):
            raise ValueError("valid hit references an inactive entity slot")
        source_card = self.entity_mechanic_card.gather(1, safe_source)
        has_on_hit = self._source_has_on_hit(source_card)
        positive = selected & (damage > 0.0)
        status_valid = status_selected & has_on_hit
        _ensure_event_capacity(
            runtime.events,
            positive.sum(dim=1, dtype=torch.int64)
            + status_valid.sum(dim=1, dtype=torch.int64),
        )

        shield = self.shield_current.clone()
        break_count = self.shield_break_count.clone()
        hitpoints = runtime.battle.entity_hp.clone()
        alive = runtime.battle.entity_active.clone()
        status = _clone_status(runtime.status)
        width = source.shape[1]
        hp_damage = torch.zeros_like(damage)
        absorbed = torch.zeros_like(selected)
        broken = torch.zeros_like(selected)
        died = torch.zeros_like(selected)
        rows = torch.arange(self.batch_size, device=self.device)

        for lane in range(width):
            lane_valid = selected[:, lane]
            target_index = safe_target[:, lane]
            lane_damage = torch.where(
                lane_valid, damage[:, lane], torch.zeros_like(damage[:, lane])
            )
            prior_shield = shield[rows, target_index]
            lane_has_shield = self.has_shield[rows, target_index] & lane_valid
            lane_count = break_count[rows, target_index]
            shield_result = apply_shield_damage_(
                prior_shield,
                lane_count,
                lane_damage,
                lane_has_shield,
            )
            shield[rows, target_index] = prior_shield
            break_count[rows, target_index] = lane_count
            lane_absorbed = (
                lane_has_shield
                & (lane_damage > 0.0)
                & (prior_shield + lane_damage > 0.0)
                & (shield_result.hitpoint_damage <= 0.0)
            )
            # ``prior_shield`` is post-hit; the pre-hit shield was positive iff
            # the hit was absorbed, which the kernel exposes as zero HP damage.
            absorbed[:, lane] = lane_absorbed
            broken[:, lane] = shield_result.shield_broken & lane_valid
            before_hp = hitpoints[rows, target_index]
            after_hp = torch.clamp(before_hp - shield_result.hitpoint_damage, min=0.0)
            hitpoints[rows, target_index] = torch.where(lane_valid, after_hp, before_hp)
            hp_damage[:, lane] = torch.where(lane_valid, before_hp - after_hp, 0.0)
            lane_died = lane_valid & alive[rows, target_index] & (after_hp <= 0.0)
            died[:, lane] = lane_died
            alive[rows, target_index] &= ~lane_died

            lane_status = status_valid[:, lane]
            if bool(lane_status.any().item()):
                source_cards = torch.zeros(
                    (self.batch_size, self.max_entities),
                    dtype=torch.int64,
                    device=self.device,
                )
                eligible = torch.zeros_like(source_cards, dtype=torch.bool)
                source_cards[rows, target_index] = source_card[:, lane]
                eligible[rows, target_index] = lane_status
                apply_status_payloads(
                    status,
                    self.on_hit_catalog,
                    source_cards,
                    trigger=StatusTriggerOpcode.ATTACK_HIT,
                    eligible=eligible,
                )

        self.shield_current.copy_(shield)
        self.shield_break_count.copy_(break_count)
        runtime.battle.entity_hp.copy_(hitpoints)
        runtime.battle.entity_active.copy_(alive)
        runtime.phases.death_pending |= runtime.entity_pool.active & ~alive
        _copy_status_(runtime.status, status)

        source_id = runtime.battle.entity_id.gather(1, safe_source)
        target_id = runtime.battle.entity_id.gather(1, safe_target)
        for lane in range(width):
            damage_valid = positive[:, lane]
            shield_payload = torch.where(
                broken[:, lane],
                int(MechanicEventPayload.SHIELD_BROKEN),
                int(MechanicEventPayload.SHIELD_ABSORBED),
            )
            event_payload = torch.where(
                absorbed[:, lane], shield_payload, torch.zeros_like(shield_payload)
            )
            event_opcode = torch.where(
                absorbed[:, lane],
                int(RuntimeEventOpcode.STATUS),
                int(RuntimeEventOpcode.DAMAGE),
            )
            event_amount = torch.where(
                absorbed[:, lane], damage[:, lane], hp_damage[:, lane]
            )
            runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=event_opcode[:, None],
                valid=damage_valid[:, None],
                source_id=source_id[:, lane : lane + 1],
                target_id=target_id[:, lane : lane + 1],
                amount=event_amount[:, None],
                payload=event_payload[:, None],
            )
            runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=RuntimeEventOpcode.STATUS,
                valid=status_valid[:, lane : lane + 1],
                source_id=source_id[:, lane : lane + 1],
                target_id=target_id[:, lane : lane + 1],
                payload=MechanicEventPayload.SERIALIZED_ON_HIT_STATUS,
            )
        changed = positive.any(dim=1) | status_valid.any(dim=1)
        if bool(changed.any().item()):
            runtime.mark_dirty(changed, phase=TickPhase.COMBAT)
        return MechanicHitResult(
            hitpoint_damage=hp_damage,
            shield_absorbed=absorbed,
            shield_broken=broken,
            status_dispatched=status_valid,
            target_died=died,
        )

    def _ownership_preview(
        self, runtime: TensorBattleRuntime
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        owner = champion_owner_mask(
            runtime.battle.entity_id,
            runtime.battle.entity_player,
            self.ability_key,
            runtime.battle.entity_active,
            self.has_ability,
        )
        key_count = self.recorded_owner_id.shape[2]
        group = (
            runtime.battle.entity_player.to(torch.int64) * key_count + self.ability_key
        ).clamp(min=0, max=2 * key_count - 1)
        previous = self.recorded_owner_id.reshape(self.batch_size, -1).gather(1, group)
        transferred = owner & (previous != runtime.battle.entity_id)
        effective_last_use = torch.where(
            transferred,
            torch.full_like(self.last_use_time_ms, NEVER_USED_TIME_MS),
            self.last_use_time_ms,
        )
        return owner, transferred, effective_last_use

    def can_activate(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        self._assert_runtime(runtime)
        owner, _, effective_last_use = self._ownership_preview(runtime)
        button = champion_button_owner_mask(
            owner, runtime.battle.entity_id, runtime.battle.entity_player
        )
        return champion_can_activate(
            now_ms=torch.round(runtime.battle.time * 1000.0).to(torch.int64),
            player_elixir=runtime.battle.elixir,
            entity_player=runtime.battle.entity_player,
            button_owner=button,
            alive=runtime.battle.entity_active,
            placement_pending=runtime.battle.entity_placement_pending,
            deploy_delay_seconds=runtime.battle.entity_deploy_delay,
            stunned=runtime.status.stun_timer > 0.0,
            can_execute_while_frozen=LOGIC_CHAMPION_CAN_EXECUTE_ABILITY_FROZEN,
            last_use_time_ms=effective_last_use,
            is_active=self.ability_active,
            activation_time_ms=self.activation_time_ms,
            elixir_cost=self.ability_elixir_cost,
            cooldown_ms=self.ability_cooldown_ms,
            duration_ms=self.ability_duration_ms,
        )

    def activate_(
        self,
        runtime: TensorBattleRuntime,
        requested_players: torch.Tensor,
    ) -> MechanicActivationResult:
        self._assert_runtime(runtime)
        requested = torch.as_tensor(
            requested_players, dtype=torch.bool, device=self.device
        )
        if requested.shape != (self.batch_size, 2):
            raise ValueError("requested_players must have shape [batch, 2]")
        owner, transferred, _ = self._ownership_preview(runtime)
        can_activate = self.can_activate(runtime)
        requested_entity = requested.gather(
            1, runtime.battle.entity_player.to(torch.int64)
        )
        will_activate = requested_entity & can_activate
        _ensure_event_capacity(
            runtime.events,
            transferred.sum(dim=1, dtype=torch.int64)
            + will_activate.sum(dim=1, dtype=torch.int64),
        )
        ownership = refresh_champion_ownership_(
            entity_id=runtime.battle.entity_id,
            entity_player=runtime.battle.entity_player,
            ability_key=self.ability_key,
            alive=runtime.battle.entity_active,
            has_ability=self.has_ability,
            recorded_owner_id=self.recorded_owner_id,
            last_use_time_ms=self.last_use_time_ms,
        )
        now_ms = torch.round(runtime.battle.time * 1000.0).to(torch.int64)
        activated = activate_champion_abilities_(
            requested_players=requested,
            can_activate=can_activate,
            now_ms=now_ms,
            player_elixir=runtime.battle.elixir,
            entity_player=runtime.battle.entity_player,
            last_use_time_ms=self.last_use_time_ms,
            is_active=self.ability_active,
            activation_time_ms=self.activation_time_ms,
            elixir_cost=self.ability_elixir_cost,
            cloak_mask=self.cloak_mask,
            trigger_delay_ms=self.trigger_delay_ms,
            cast_time_ms=self.cast_time_ms,
            cloak_pending_until_ms=self.cloak_pending_until_ms,
            cast_lock_until_ms=self.cast_lock_until_ms,
        )
        runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.STATUS,
            valid=ownership.transferred,
            source_id=runtime.battle.entity_id,
            target_id=runtime.battle.entity_id,
            payload=MechanicEventPayload.CHAMPION_OWNERSHIP_TRANSFERRED,
        )
        runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.COMMAND,
            valid=activated,
            source_id=runtime.battle.entity_id,
            target_id=runtime.battle.entity_id,
            amount=self.ability_elixir_cost.to(torch.float64),
            payload=MechanicEventPayload.CHAMPION_ACTIVATED,
        )
        changed = ownership.transferred.any(dim=1) | activated.any(dim=1)
        if bool(changed.any().item()):
            runtime.mark_dirty(changed, phase=TickPhase.COMMANDS)
        return MechanicActivationResult(
            owner=owner,
            transferred=ownership.transferred,
            can_activate=can_activate,
            activated=activated,
        )

    def tick_cloak_(
        self,
        runtime: TensorBattleRuntime,
        *,
        cancel_before_effect: torch.Tensor | bool = False,
    ) -> ChampionTickResult:
        self._assert_runtime(runtime)
        cancel = torch.as_tensor(
            cancel_before_effect, dtype=torch.bool, device=self.device
        )
        try:
            cancel = torch.broadcast_to(cancel, self.ability_active.shape).clone()
        except RuntimeError as exc:
            raise ValueError(
                "cancel_before_effect is not entity-broadcastable"
            ) from exc
        mutable = {
            "last_use_time_ms": self.last_use_time_ms.clone(),
            "is_active": self.ability_active.clone(),
            "activation_time_ms": self.activation_time_ms.clone(),
            "cloak_pending_until_ms": self.cloak_pending_until_ms.clone(),
            "cast_lock_until_ms": self.cast_lock_until_ms.clone(),
            "attack_mode_multiplier": self.attack_mode_multiplier.clone(),
            "movement_mode_multiplier": self.movement_mode_multiplier.clone(),
            "original_movement_mode_multiplier": (
                self.original_movement_mode_multiplier.clone()
            ),
            "stealth_until_ms": self.stealth_until_ms.clone(),
        }
        result = tick_champion_abilities_(
            now_ms=torch.round(runtime.battle.time * 1000.0).to(torch.int64),
            alive=runtime.battle.entity_active,
            cancel_before_effect=cancel,
            last_use_time_ms=mutable["last_use_time_ms"],
            is_active=mutable["is_active"],
            activation_time_ms=mutable["activation_time_ms"],
            duration_ms=self.ability_duration_ms,
            cloak_mask=self.cloak_mask,
            cloak_pending_until_ms=mutable["cloak_pending_until_ms"],
            cast_lock_until_ms=mutable["cast_lock_until_ms"],
            attack_speed_multiplier=self.attack_speed_multiplier,
            movement_speed_multiplier=self.movement_speed_multiplier,
            attack_mode_multiplier=mutable["attack_mode_multiplier"],
            movement_mode_multiplier=mutable["movement_mode_multiplier"],
            original_movement_mode_multiplier=(
                mutable["original_movement_mode_multiplier"]
            ),
            stealth_until_ms=mutable["stealth_until_ms"],
        )
        event_masks = torch.stack(
            (
                result.died,
                result.cancelled_before_effect,
                result.cloak_started,
                result.cast_lock_ended,
                result.cloak_ended,
            ),
            dim=2,
        ).flatten(1)
        _ensure_event_capacity(
            runtime.events, event_masks.sum(dim=1, dtype=torch.int64)
        )
        for name, value in mutable.items():
            destination = (
                self.ability_active if name == "is_active" else getattr(self, name)
            )
            destination.copy_(value)
        payload = (
            torch.tensor(
                [
                    int(MechanicEventPayload.CHAMPION_DIED),
                    int(MechanicEventPayload.ABILITY_CANCELLED),
                    int(MechanicEventPayload.CLOAK_STARTED),
                    int(MechanicEventPayload.CAST_LOCK_ENDED),
                    int(MechanicEventPayload.CLOAK_ENDED),
                ],
                dtype=torch.int64,
                device=self.device,
            )
            .view(1, 1, 5)
            .expand(self.batch_size, self.max_entities, 5)
            .flatten(1)
        )
        entity_id = (
            runtime.battle.entity_id[:, :, None]
            .expand(self.batch_size, self.max_entities, 5)
            .flatten(1)
        )
        runtime.events.append(
            phase=TickPhase.COMBAT,
            opcode=RuntimeEventOpcode.STATUS,
            valid=event_masks,
            source_id=entity_id,
            target_id=entity_id,
            payload=payload,
        )
        changed = event_masks.any(dim=1)
        if bool(changed.any().item()):
            runtime.mark_dirty(changed, phase=TickPhase.COMBAT)
        return result

    def combat_blocked(self) -> torch.Tensor:
        return self.cloak_mask & (self.cast_lock_until_ms >= 0)

    def hidden_from_enemies(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        self._assert_runtime(runtime)
        now = torch.round(runtime.battle.time * 1000.0).to(torch.int64)[:, None]
        return self.cloak_mask & (self.stealth_until_ms > now)

    def attack_rate_multiplier(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        """Return the oracle's integer-quantized composed combat tick rate."""

        self._assert_runtime(runtime)
        debuff = (
            torch.round(runtime.status.attack_speed_debuff_multiplier * 100.0)
            .to(torch.int64)
            .clamp_min(0)
        )
        positive = torch.maximum(
            runtime.status.attack_speed_buff_multiplier,
            self.attack_mode_multiplier,
        )
        buff = torch.round(positive * 100.0).to(torch.int64).clamp_min(0)
        buffed = 50 * buff // 100
        return (buffed * debuff // 100).to(torch.float64) / 50.0

    def sync_to_battles(
        self,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> None:
        """Publish mechanic-owned mutable state after runtime core/status sync."""

        self._assert_runtime(runtime)
        if len(battles) != self.batch_size:
            raise ValueError("battle count does not match mechanic batch")
        shield_opcode = MECHANIC_OPCODE["Shield"]
        cloak_opcode = MECHANIC_OPCODE["ArcherQueenCloak"]
        for batch_index, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(
                    runtime.battle.entity_id[batch_index].tolist()
                )
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                index = (batch_index, slot)
                for mechanic in entity.mechanics:
                    opcode = MECHANIC_OPCODE.get(type(mechanic).__name__, 0)
                    if opcode == shield_opcode:
                        setattr(
                            mechanic,
                            "current_shield",
                            float(self.shield_current[index].item()),
                        )
                        setattr(
                            mechanic,
                            "max_shield",
                            float(self.shield_max[index].item()),
                        )
                    elif opcode == cloak_opcode:
                        ability = getattr(mechanic, "ability")
                        ability.last_use_time = int(self.last_use_time_ms[index].item())
                        ability.is_active = bool(self.ability_active[index].item())
                        ability.activation_time = int(
                            self.activation_time_ms[index].item()
                        )
                        pending = int(self.cloak_pending_until_ms[index].item())
                        cast_lock = int(self.cast_lock_until_ms[index].item())
                        setattr(
                            mechanic,
                            "_cloak_pending_until",
                            None if pending < 0 else pending,
                        )
                        setattr(
                            mechanic,
                            "_cast_lock_until",
                            None if cast_lock < 0 else cast_lock,
                        )
                        original = float(
                            self.original_movement_mode_multiplier[index].item()
                        )
                        setattr(
                            mechanic,
                            "_original_movement_mode_multiplier",
                            None if math.isnan(original) else original,
                        )
                setattr(
                    entity,
                    "_shield_break_count",
                    int(self.shield_break_count[index].item()),
                )
                entity.attack_mode_multiplier = float(
                    self.attack_mode_multiplier[index].item()
                )
                movement_mode = float(self.movement_mode_multiplier[index].item())
                set_movement_mode = getattr(
                    entity, "set_movement_mode_multiplier", None
                )
                if callable(set_movement_mode):
                    set_movement_mode(movement_mode)
                else:
                    entity.movement_mode_multiplier = movement_mode
                setattr(
                    entity,
                    "_stealth_until",
                    int(self.stealth_until_ms[index].item()),
                )

            scoped_keys = {
                (
                    int(runtime.battle.entity_player[batch_index, slot].item()),
                    battle._champion_ability_key(entity),
                )
                for entity_id, entity in battle.entities.items()
                if self.has_ability[batch_index, slot_by_id[entity_id]]
                for slot in (slot_by_id[entity_id],)
            }
            for key in scoped_keys:
                battle._champion_ability_owner_ids.pop(key, None)
            for slot in range(self.max_entities):
                if not bool(self.has_ability[batch_index, slot].item()):
                    continue
                player = int(runtime.battle.entity_player[batch_index, slot].item())
                ability_key = int(self.ability_key[batch_index, slot].item())
                owner_id = int(
                    self.recorded_owner_id[batch_index, player, ability_key].item()
                )
                if owner_id <= 0:
                    continue
                entity = battle.entities[owner_id]
                key = (player, battle._champion_ability_key(entity))
                battle._champion_ability_owner_ids[key] = owner_id
