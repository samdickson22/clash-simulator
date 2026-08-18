"""Transactional retained dispatcher for generalized mechanic families.

The dispatcher composes existing family kernels behind one per-tick tensor
interface.  Serialized mechanic opcodes define support and dispatch; card
identity never selects behavior.  Supported rows execute on speculative forks
and are scattered back only after every requested family and event append
succeeds.  Unsupported or failed rows therefore preserve state, events, and
the resident CPython RNG bit-for-bit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.kinematics import tiles_to_logic_units
from clasher.unit_traits import is_airborne_target

from .catalog import MECHANIC_OPCODE
from .combat_mechanics import (
    CombatMechanicOpcode,
    TensorCombatMechanicCatalog,
    TensorDamageRampState,
    TensorMechanicWorld,
    apply_crown_tower_scaling,
    update_damage_ramp_,
)
from .passive_mechanics import (
    TensorPassiveCatalog,
    TensorPassiveEvents,
    TensorPassiveState,
    collect_souls_,
    step_passive_object_phase_,
)
from .runtime_mechanics import TensorRuntimeMechanics
from .runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)
from .special_movement import (
    SpecialMovementOpcode,
    TensorSpecialEvents,
    TensorSpecialMovementCatalog,
    dispatch_attack_commits,
)

SUPPORTED_DISPATCH_MECHANICS = frozenset(
    MECHANIC_OPCODE[name]
    for name in (
        "Shield",
        "SerializedOnHitBuff",
        "ArcherQueenCloak",
        "HideWhenIdle",
        "InvisibilityWhenNotAttacking",
        "SkeletonKingSoulCollector",
        "PeriodicSpawner",
        "DamageRamp",
        "CrownTowerScaling",
        "AttackRecoil",
        "BattleRamCharge",
        "WallBreakersDemolition",
    )
)


class DispatchReason(IntEnum):
    NONE = 0
    DEVICE = 1
    UNKNOWN_CARD = 2
    UNSUPPORTED_OPCODE = 3
    EVENT_CAPACITY = 4
    ATOMIC_FAILURE = 5
    INVALID_INPUT = 6


@dataclass(frozen=True)
class MechanicDispatchPreflight:
    supported: torch.Tensor
    reason: torch.Tensor
    unsupported_opcode: torch.Tensor


@dataclass
class MechanicTickInputs:
    dt_ms: torch.Tensor
    attack_source_slot: torch.Tensor
    attack_target_slot: torch.Tensor
    attack_damage: torch.Tensor
    attack_valid: torch.Tensor
    attack_damage_already_applied: torch.Tensor
    status_eligible: torch.Tensor
    special_source_slot: torch.Tensor
    special_target_slot: torch.Tensor
    special_valid: torch.Tensor
    attack_committed: torch.Tensor
    attack_hit: torch.Tensor
    connected_target_slot: torch.Tensor
    connected: torch.Tensor
    attack_rate: torch.Tensor
    champion_requested: torch.Tensor
    cloak_cancel_before_effect: torch.Tensor
    has_attack_target: torch.Tensor
    has_attack_range_target: torch.Tensor
    attack_started: torch.Tensor
    stunned: torch.Tensor
    slow_multiplier: torch.Tensor
    movement_speed_buff_multiplier: torch.Tensor
    spawn_rate: torch.Tensor

    @classmethod
    def empty(
        cls,
        dispatcher: TensorMechanicDispatcher,
        *,
        event_width: int = 1,
        dt_ms: int = 50,
    ) -> MechanicTickInputs:
        if event_width < 1:
            raise ValueError("event_width must be positive")
        batch = dispatcher.batch_size
        entities = dispatcher.max_entities
        device = dispatcher.device
        event_shape = (batch, event_width)
        entity_shape = (batch, entities)
        zeros_event = torch.zeros(event_shape, dtype=torch.int64, device=device)
        zeros_entity = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        spawn_rate = dispatcher._native_rate(
            dispatcher.runtime.status.spawn_speed_debuff_multiplier,
            dispatcher.runtime.status.spawn_speed_buff_multiplier,
        )
        return cls(
            dt_ms=torch.full((batch,), dt_ms, dtype=torch.int64, device=device),
            attack_source_slot=zeros_event.clone(),
            attack_target_slot=zeros_event.clone(),
            attack_damage=torch.zeros(event_shape, dtype=torch.float64, device=device),
            attack_valid=torch.zeros(event_shape, dtype=torch.bool, device=device),
            attack_damage_already_applied=torch.zeros(
                event_shape, dtype=torch.bool, device=device
            ),
            status_eligible=torch.zeros(event_shape, dtype=torch.bool, device=device),
            special_source_slot=zeros_event.clone(),
            special_target_slot=zeros_event.clone(),
            special_valid=torch.zeros(event_shape, dtype=torch.bool, device=device),
            attack_committed=torch.zeros(event_shape, dtype=torch.bool, device=device),
            attack_hit=torch.zeros(event_shape, dtype=torch.bool, device=device),
            connected_target_slot=torch.full(
                entity_shape, -1, dtype=torch.int64, device=device
            ),
            connected=zeros_entity.clone(),
            attack_rate=torch.ones(entity_shape, dtype=torch.float64, device=device),
            champion_requested=torch.zeros((batch, 2), dtype=torch.bool, device=device),
            cloak_cancel_before_effect=zeros_entity.clone(),
            has_attack_target=zeros_entity.clone(),
            has_attack_range_target=zeros_entity.clone(),
            attack_started=zeros_entity.clone(),
            stunned=dispatcher.runtime.status.stun_timer > 0.0,
            slow_multiplier=dispatcher.runtime.status.slow_multiplier.clone(),
            movement_speed_buff_multiplier=(
                dispatcher.runtime.status.movement_speed_buff_multiplier.clone()
            ),
            spawn_rate=spawn_rate,
        )

    def select(self, indices: torch.Tensor) -> MechanicTickInputs:
        return MechanicTickInputs(
            **{
                descriptor.name: getattr(self, descriptor.name)
                .index_select(0, indices)
                .clone()
                for descriptor in fields(self)
            }
        )

    def validate(self, dispatcher: TensorMechanicDispatcher) -> None:
        batch = dispatcher.batch_size
        entities = dispatcher.max_entities
        if self.dt_ms.shape != (batch,):
            raise ValueError("dt_ms must have shape [batch]")
        event_shape = self.attack_source_slot.shape
        if len(event_shape) != 2 or event_shape[0] != batch:
            raise ValueError("attack event planes must have shape [batch, event]")
        for name in (
            "attack_target_slot",
            "attack_damage",
            "attack_valid",
            "attack_damage_already_applied",
            "status_eligible",
            "special_source_slot",
            "special_target_slot",
            "special_valid",
            "attack_committed",
            "attack_hit",
        ):
            if getattr(self, name).shape != event_shape:
                raise ValueError(f"{name} shape differs from attack event planes")
        for name in (
            "connected_target_slot",
            "connected",
            "attack_rate",
            "cloak_cancel_before_effect",
            "has_attack_target",
            "has_attack_range_target",
            "attack_started",
            "stunned",
            "slow_multiplier",
            "movement_speed_buff_multiplier",
            "spawn_rate",
        ):
            if getattr(self, name).shape != (batch, entities):
                raise ValueError(f"{name} must have shape [batch, entity]")
        if self.champion_requested.shape != (batch, 2):
            raise ValueError("champion_requested must have shape [batch, 2]")


@dataclass(frozen=True)
class MechanicTickResult:
    preflight: MechanicDispatchPreflight
    committed: torch.Tensor
    ramp_damage: torch.Tensor
    adjusted_attack_damage: torch.Tensor
    event_count_delta: torch.Tensor


def _select_tensor_dataclass(value: object, indices: torch.Tensor) -> object:
    selected: dict[str, object] = {}
    for descriptor in fields(value):  # type: ignore[arg-type]
        item = getattr(value, descriptor.name)
        if isinstance(item, torch.Tensor) and item.ndim:
            selected[descriptor.name] = item.index_select(0, indices).clone()
        else:
            selected[descriptor.name] = item
    return type(value)(**selected)


def _copy_rows_(
    destination: object,
    source: object,
    rows: torch.Tensor,
    full_batch: int,
) -> None:
    selected_batch = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        target = getattr(destination, descriptor.name)
        value = getattr(source, descriptor.name)
        if (
            isinstance(target, torch.Tensor)
            and isinstance(value, torch.Tensor)
            and target.ndim
            and target.shape[0] == full_batch
            and value.shape[0] == selected_batch
            and target.shape[1:] == value.shape[1:]
        ):
            target[rows] = value


def _core_to_catalog(
    runtime: TensorBattleRuntime,
    names: tuple[str, ...],
    name_to_id: dict[str, int],
) -> torch.Tensor:
    result = torch.full(
        (len(runtime.battle.card_names),),
        -1,
        dtype=torch.int64,
        device=runtime.device,
    )
    result[0] = 0
    available = set(names)
    for core_id, name in enumerate(runtime.battle.card_names[1:], start=1):
        if name in available:
            result[core_id] = name_to_id[name]
    return result


@dataclass
class TensorMechanicDispatcher:
    runtime: TensorBattleRuntime
    mechanics: TensorRuntimeMechanics
    passive_catalog: TensorPassiveCatalog
    passive: TensorPassiveState
    combat_catalog: TensorCombatMechanicCatalog
    combat_world: TensorMechanicWorld
    damage_ramp: TensorDamageRampState
    special_catalog: TensorSpecialMovementCatalog
    core_to_passive_card: torch.Tensor
    core_to_combat_card: torch.Tensor
    core_to_special_card: torch.Tensor
    special_triggered: torch.Tensor
    forced_movement: torch.Tensor
    knockback_target_units: torch.Tensor
    knockback_velocity_work: torch.Tensor
    initialized_entity_id: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.runtime.device

    @property
    def batch_size(self) -> int:
        return self.runtime.batch_size

    @property
    def max_entities(self) -> int:
        return self.runtime.max_entities

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorMechanicDispatcher:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime batch")
        if runtime.device.type not in {"cpu", "cuda"}:
            raise ValueError("mechanic dispatcher supports CPU and CUDA only")
        names = runtime.catalog.names[1:]
        passive_catalog = TensorPassiveCatalog.compile(
            battles[0].card_loader, names, device=runtime.device
        )
        combat_catalog = TensorCombatMechanicCatalog.compile(
            battles[0].card_loader, names, device=runtime.device
        )
        special_catalog = TensorSpecialMovementCatalog.compile(
            battles[0].card_loader, names, device=runtime.device
        )
        commit_operation = torch.zeros_like(special_catalog.opcode, dtype=torch.bool)
        for operation in (
            SpecialMovementOpcode.ATTACK_RECOIL,
            SpecialMovementOpcode.BATTLE_RAM_CHARGE,
            SpecialMovementOpcode.WALL_BREAKERS_DEMOLITION,
        ):
            commit_operation |= special_catalog.opcode == int(operation)
        if bool((commit_operation.sum(dim=1) > 1).any().item()):
            raise ValueError("a card has multiple attack-commit movement operations")
        core_to_passive = _core_to_catalog(
            runtime, passive_catalog.names, passive_catalog.name_to_id
        )
        core_to_combat = _core_to_catalog(
            runtime, combat_catalog.names, combat_catalog.name_to_id
        )
        core_to_special = _core_to_catalog(
            runtime, special_catalog.names, special_catalog.name_to_id
        )
        passive_cards = core_to_passive[runtime.battle.entity_card].clamp_min(0)
        passive = TensorPassiveState.from_entities(
            passive_catalog,
            entity_id=runtime.battle.entity_id,
            card_id=passive_cards,
            player=runtime.battle.entity_player,
            x_units=runtime.battle.entity_x_units,
            y_units=runtime.battle.entity_y_units,
            active=runtime.entity_pool.active,
            alive=runtime.battle.entity_active,
            target_slot=runtime.phases.target_slot,
        )
        world = TensorMechanicWorld.empty(
            runtime.batch_size, runtime.max_entities, device=runtime.device
        )
        ramp = TensorDamageRampState.empty(
            runtime.battle.entity_id.shape, device=runtime.device
        )
        triggered = torch.zeros_like(runtime.battle.entity_active)
        forced = torch.zeros_like(runtime.battle.entity_active)
        knockback_target = torch.zeros(
            (*runtime.battle.entity_id.shape, 2),
            dtype=torch.int64,
            device=runtime.device,
        )
        knockback_velocity = torch.zeros_like(runtime.battle.entity_id)
        dispatcher = cls(
            runtime=runtime,
            mechanics=TensorRuntimeMechanics.from_battles(runtime, battles),
            passive_catalog=passive_catalog,
            passive=passive,
            combat_catalog=combat_catalog,
            combat_world=world,
            damage_ramp=ramp,
            special_catalog=special_catalog,
            core_to_passive_card=core_to_passive,
            core_to_combat_card=core_to_combat,
            core_to_special_card=core_to_special,
            special_triggered=triggered,
            forced_movement=forced,
            knockback_target_units=knockback_target,
            knockback_velocity_work=knockback_velocity,
            initialized_entity_id=torch.where(
                runtime.entity_pool.active,
                runtime.battle.entity_id,
                torch.zeros_like(runtime.battle.entity_id),
            ),
        )
        dispatcher._load_boundaries_(battles)
        dispatcher._refresh_dynamic_planes_()
        return dispatcher

    def _load_boundaries_(self, battles: Sequence[BattleState]) -> None:
        passive_names = {
            "HideWhenIdle",
            "InvisibilityWhenNotAttacking",
            "SkeletonKingSoulCollector",
            "PeriodicSpawner",
        }
        for batch_index, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(
                    self.runtime.battle.entity_id[batch_index].tolist()
                )
                if entity_id
            }
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                index = (batch_index, slot)
                self.combat_world.collision_radius_units[index] = tiles_to_logic_units(
                    entity.get_collision_radius()
                )
                self.combat_world.distance_discount_sq_units[index] = int(
                    entity._native_target_distance_discount_sq_units
                )
                self.combat_world.airborne[index] = is_airborne_target(entity)
                self.combat_world.building[index] = isinstance(entity, Building)
                self.combat_world.crown[index] = bool(
                    getattr(entity, "_crown_tower_slot", None)
                )
                self.combat_world.targetable[index] = entity.is_targetable_by(
                    1 - entity.player_id
                )
                self.combat_world.effect_receivable[index] = entity.can_receive_effect()
                self.special_triggered[index] = bool(
                    getattr(entity, "_wall_breaker_triggered", False)
                    or getattr(entity, "_battle_ram_triggered", False)
                )
                self.forced_movement[index] = entity.forced_movement_active
                target = entity._knockback_target
                if target is not None:
                    self.knockback_target_units[index] = torch.tensor(
                        [
                            tiles_to_logic_units(target.x),
                            tiles_to_logic_units(target.y),
                        ],
                        device=self.device,
                    )
                self.knockback_velocity_work[index] = int(
                    entity._knockback_velocity_work
                )
                for mechanic in entity.mechanics:
                    operation = type(mechanic).__name__
                    if operation == "DamageRamp":
                        self.damage_ramp.target_id[index] = int(
                            getattr(mechanic, "_current_target_id", 0) or 0
                        )
                        self.damage_ramp.target_time_ms[index] = float(
                            getattr(mechanic, "_current_target_ms", 0.0)
                        )
                        self.damage_ramp.damage[index] = entity.damage
                    elif operation in passive_names:
                        if operation == "HideWhenIdle":
                            self.passive.hide_phase_ms[index] = float(
                                getattr(mechanic, "_phase_ms")  # noqa: B009
                            )
                            self.passive.hidden_building[index] = bool(
                                getattr(entity, "_hidden_building", False)
                            )
                            self.passive.special_move_active[index] = bool(
                                getattr(entity, "_special_move_active", False)
                            )
                        elif operation == "InvisibilityWhenNotAttacking":
                            self.passive.fade_elapsed_ms[index] = float(
                                getattr(mechanic, "time_since_attack_ms")  # noqa: B009
                            )
                            self.passive.stealth_until_ms[index] = int(
                                getattr(entity, "_stealth_until", 0) or 0
                            )
                        elif operation == "SkeletonKingSoulCollector":
                            souls = int(
                                getattr(mechanic, "souls_collected")  # noqa: B009
                            )
                            self.passive.souls_collected[index] = souls
                            self.passive.soul_ability_cost[index] = int(
                                getattr(mechanic, "ability").elixir_cost  # noqa: B009
                            )
                        else:
                            self.passive.periodic_time_since_spawn_ms[index] = float(
                                getattr(mechanic, "time_since_spawn_ms")  # noqa: B009
                            )
                            self.passive.periodic_spawns_created[index] = int(
                                getattr(mechanic, "spawns_created")  # noqa: B009
                            )
                            self.passive.periodic_pending_units[index] = int(
                                getattr(mechanic, "pending_units")  # noqa: B009
                            )
                            self.passive.periodic_time_since_unit_spawn_ms[index] = (
                                float(
                                    getattr(mechanic, "time_since_unit_spawn_ms")  # noqa: B009
                                )
                            )
                            self.passive.periodic_current_wave_spawned[index] = int(
                                getattr(mechanic, "current_wave_spawned")  # noqa: B009
                            )

    def _refresh_dynamic_planes_(self) -> None:
        runtime = self.runtime
        current_identity = torch.where(
            runtime.entity_pool.active,
            runtime.battle.entity_id,
            torch.zeros_like(runtime.battle.entity_id),
        )
        new_entity = runtime.entity_pool.active & (
            current_identity != self.initialized_entity_id
        )
        self.passive.card_id.copy_(
            self.core_to_passive_card[runtime.battle.entity_card].clamp_min(0)
        )
        fresh = TensorPassiveState.from_entities(
            self.passive_catalog,
            entity_id=runtime.battle.entity_id,
            card_id=self.passive.card_id,
            player=runtime.battle.entity_player,
            x_units=runtime.battle.entity_x_units,
            y_units=runtime.battle.entity_y_units,
            active=runtime.entity_pool.active,
            alive=runtime.battle.entity_active,
            target_slot=runtime.phases.target_slot,
        )
        for descriptor in fields(self.passive):
            destination = getattr(self.passive, descriptor.name)
            source = getattr(fresh, descriptor.name)
            expanded = new_entity
            while expanded.ndim < destination.ndim:
                expanded = expanded.unsqueeze(-1)
            destination.copy_(torch.where(expanded, source, destination))
        for plane in (
            self.damage_ramp.target_id,
            self.damage_ramp.target_time_ms,
            self.damage_ramp.damage,
            self.special_triggered,
            self.forced_movement,
            self.knockback_velocity_work,
        ):
            plane.masked_fill_(new_entity, 0)
        self.knockback_target_units.masked_fill_(new_entity[..., None], 0)
        self.mechanics.refresh_new_entities_(runtime)
        core_card = self.runtime.card_catalog_index[
            runtime.battle.entity_card
        ].clamp_min(0)
        self.combat_world.collision_radius_units.copy_(
            torch.where(
                new_entity,
                self.runtime.catalog.collision_radius_units[core_card].to(torch.int32),
                self.combat_world.collision_radius_units,
            )
        )
        self.combat_world.airborne.copy_(
            torch.where(
                new_entity,
                self.runtime.catalog.is_air_unit[core_card],
                self.combat_world.airborne,
            )
        )
        self.combat_world.building.copy_(
            torch.where(
                new_entity,
                runtime.battle.entity_kind == 1,
                self.combat_world.building,
            )
        )
        self.combat_world.crown.copy_(
            torch.where(
                new_entity,
                runtime.battle.entity_tower_slot >= 0,
                self.combat_world.crown,
            )
        )
        self.combat_world.targetable |= new_entity
        self.combat_world.effect_receivable |= new_entity
        self.initialized_entity_id.copy_(current_identity)
        self.passive.entity_id.copy_(runtime.battle.entity_id)
        self.passive.player.copy_(runtime.battle.entity_player)
        self.passive.x_units.copy_(runtime.battle.entity_x_units)
        self.passive.y_units.copy_(runtime.battle.entity_y_units)
        self.passive.active.copy_(runtime.entity_pool.active)
        self.passive.alive.copy_(runtime.battle.entity_active)
        self.passive.target_slot.copy_(runtime.phases.target_slot)
        self.combat_world.present.copy_(runtime.entity_pool.active)
        self.combat_world.entity_id.copy_(runtime.battle.entity_id)
        self.combat_world.owner.copy_(runtime.battle.entity_player)
        self.combat_world.x_units.copy_(runtime.battle.entity_x_units)
        self.combat_world.y_units.copy_(runtime.battle.entity_y_units)
        self.combat_world.hp.copy_(runtime.battle.entity_hp)
        self.combat_world.alive.copy_(runtime.battle.entity_active)

    @staticmethod
    def _native_rate(debuff: torch.Tensor, buff: torch.Tensor) -> torch.Tensor:
        negative = torch.round(debuff * 100.0).to(torch.int64).clamp_min(0)
        positive = torch.round(buff * 100.0).to(torch.int64).clamp_min(0)
        return ((50 * positive // 100) * negative // 100).to(torch.float64) / 50.0

    def _invalid_input_rows(self, inputs: MechanicTickInputs) -> torch.Tensor:
        def invalid_slot(slot: torch.Tensor, valid: torch.Tensor) -> torch.Tensor:
            return valid & ((slot < 0) | (slot >= self.max_entities))

        invalid = invalid_slot(
            inputs.attack_source_slot, inputs.attack_valid
        ) | invalid_slot(inputs.attack_target_slot, inputs.attack_valid)
        invalid |= invalid_slot(
            inputs.special_source_slot, inputs.special_valid
        ) | invalid_slot(inputs.special_target_slot, inputs.special_valid)
        invalid_rows = invalid.any(dim=1)
        invalid_rows |= invalid_slot(
            inputs.connected_target_slot, inputs.connected
        ).any(dim=1)

        safe_source = inputs.special_source_slot.clamp(min=0, max=self.max_entities - 1)
        special_card = self._special_card_id_for_slots(safe_source)
        operations = self.special_catalog.opcode[special_card]
        has_commit_operation = torch.zeros_like(operations, dtype=torch.bool)
        for operation in (
            SpecialMovementOpcode.ATTACK_RECOIL,
            SpecialMovementOpcode.BATTLE_RAM_CHARGE,
            SpecialMovementOpcode.WALL_BREAKERS_DEMOLITION,
        ):
            has_commit_operation |= operations == int(operation)
        invalid_rows |= (inputs.special_valid & ~has_commit_operation.any(dim=2)).any(
            dim=1
        )
        return invalid_rows

    def preflight(
        self, inputs: MechanicTickInputs | None = None
    ) -> MechanicDispatchPreflight:
        if self.device.type not in {"cpu", "cuda"}:
            return MechanicDispatchPreflight(
                supported=torch.zeros(
                    self.batch_size, dtype=torch.bool, device=self.device
                ),
                reason=torch.full(
                    (self.batch_size,),
                    int(DispatchReason.DEVICE),
                    dtype=torch.int16,
                    device=self.device,
                ),
                unsupported_opcode=torch.zeros(
                    self.batch_size, dtype=torch.int16, device=self.device
                ),
            )
        catalog_id = self.runtime.card_catalog_index[self.runtime.battle.entity_card]
        character = self.runtime.entity_pool.active & (
            (self.runtime.battle.entity_kind == 0)
            | (self.runtime.battle.entity_kind == 1)
        )
        known = (catalog_id >= 0) | (self.runtime.battle.entity_tower_slot >= 0)
        unknown = (character & ~known).any(dim=1)
        safe = catalog_id.clamp_min(0)
        operations = self.runtime.catalog.mechanic_opcode[safe]
        operation_active = character[:, :, None] & (operations > 0)
        supported_table = torch.zeros(
            max(MECHANIC_OPCODE.values()) + 1,
            dtype=torch.bool,
            device=self.device,
        )
        supported_table[list(SUPPORTED_DISPATCH_MECHANICS)] = True
        unsupported = operation_active & ~supported_table[operations.to(torch.int64)]
        row_unsupported = unsupported.any(dim=(1, 2))
        sentinel = torch.iinfo(torch.int16).max
        first = torch.where(unsupported, operations, sentinel).amin(dim=(1, 2))
        first = torch.where(row_unsupported, first, 0).to(torch.int16)
        invalid_input = (
            self._invalid_input_rows(inputs)
            if inputs is not None
            else torch.zeros_like(unknown)
        )
        supported = (
            self.runtime.supported & ~unknown & ~row_unsupported & ~invalid_input
        )
        reason = torch.where(
            unknown,
            int(DispatchReason.UNKNOWN_CARD),
            torch.where(
                row_unsupported,
                int(DispatchReason.UNSUPPORTED_OPCODE),
                torch.where(
                    invalid_input,
                    int(DispatchReason.INVALID_INPUT),
                    int(DispatchReason.NONE),
                ),
            ),
        ).to(torch.int16)
        return MechanicDispatchPreflight(supported, reason, first)

    def _fork(self, indices: torch.Tensor) -> TensorMechanicDispatcher:
        runtime = self.runtime.fork(indices)
        runtime.battle.rng = self.runtime.battle.rng.fork(indices)
        return TensorMechanicDispatcher(
            runtime=runtime,
            mechanics=self.mechanics.fork(indices),
            passive_catalog=self.passive_catalog,
            passive=_select_tensor_dataclass(self.passive, indices),  # type: ignore[arg-type]
            combat_catalog=self.combat_catalog,
            combat_world=_select_tensor_dataclass(self.combat_world, indices),  # type: ignore[arg-type]
            damage_ramp=_select_tensor_dataclass(self.damage_ramp, indices),  # type: ignore[arg-type]
            special_catalog=self.special_catalog,
            core_to_passive_card=self.core_to_passive_card,
            core_to_combat_card=self.core_to_combat_card,
            core_to_special_card=self.core_to_special_card,
            special_triggered=self.special_triggered.index_select(0, indices).clone(),
            forced_movement=self.forced_movement.index_select(0, indices).clone(),
            knockback_target_units=(
                self.knockback_target_units.index_select(0, indices).clone()
            ),
            knockback_velocity_work=(
                self.knockback_velocity_work.index_select(0, indices).clone()
            ),
            initialized_entity_id=(
                self.initialized_entity_id.index_select(0, indices).clone()
            ),
        )

    def _commit_(self, candidate: TensorMechanicDispatcher, rows: torch.Tensor) -> None:
        for destination, source in (
            (self.runtime.battle, candidate.runtime.battle),
            (self.runtime.entity_pool, candidate.runtime.entity_pool),
            (self.runtime.status, candidate.runtime.status),
            (self.runtime.phases, candidate.runtime.phases),
            (self.runtime.events, candidate.runtime.events),
            (self.mechanics, candidate.mechanics),
            (self.passive, candidate.passive),
            (self.combat_world, candidate.combat_world),
            (self.damage_ramp, candidate.damage_ramp),
        ):
            _copy_rows_(destination, source, rows, self.batch_size)
        self.runtime.supported[rows] = candidate.runtime.supported
        self.runtime.dirty[rows] = candidate.runtime.dirty
        self.runtime.battle.rng.words[rows] = candidate.runtime.battle.rng.words
        self.runtime.battle.rng.index[rows] = candidate.runtime.battle.rng.index
        self.runtime.battle.rng.gauss_value[rows] = (
            candidate.runtime.battle.rng.gauss_value
        )
        self.runtime.battle.rng.gauss_cached[rows] = (
            candidate.runtime.battle.rng.gauss_cached
        )
        for name in (
            "special_triggered",
            "forced_movement",
            "knockback_target_units",
            "knockback_velocity_work",
            "initialized_entity_id",
        ):
            getattr(self, name)[rows] = getattr(candidate, name)

    def _combat_card_id(self) -> torch.Tensor:
        return self.core_to_combat_card[self.runtime.battle.entity_card].clamp_min(0)

    def _special_card_id_for_slots(self, slots: torch.Tensor) -> torch.Tensor:
        core = self.runtime.battle.entity_card.gather(1, slots)
        return self.core_to_special_card[core].clamp_min(0)

    def _append_passive_events_(
        self, events: TensorPassiveEvents, phase: TickPhase
    ) -> None:
        if not events.batch_index.numel():
            return
        counts = torch.bincount(events.batch_index, minlength=self.batch_size)
        width = events.batch_index.numel()
        valid = torch.zeros(
            (self.batch_size, width), dtype=torch.bool, device=self.device
        )
        source = torch.zeros(
            (self.batch_size, width), dtype=torch.int64, device=self.device
        )
        target = torch.zeros_like(source)
        payload = torch.zeros_like(source)
        amount = torch.zeros(
            (self.batch_size, width), dtype=torch.float64, device=self.device
        )
        starts = torch.cumsum(counts, dim=0) - counts
        local = torch.arange(width, device=self.device) - starts[events.batch_index]
        valid[events.batch_index, local] = True
        source[events.batch_index, local] = events.source_entity_id
        target[events.batch_index, local] = events.target_entity_id
        payload[events.batch_index, local] = events.opcode
        amount[events.batch_index, local] = events.amount
        self.runtime.events.append(
            phase=phase,
            opcode=RuntimeEventOpcode.STATUS,
            valid=valid,
            source_id=source,
            target_id=target,
            amount=amount,
            payload=payload,
        )

    def _append_special_events_(self, events: TensorSpecialEvents) -> None:
        self.runtime.events.append(
            phase=TickPhase.COMBAT,
            opcode=RuntimeEventOpcode.MOVEMENT,
            valid=events.valid,
            source_id=events.source_id,
            target_id=events.target_id,
            amount=events.amount,
            payload=events.opcode,
        )

    def _sort_new_phase_events_(
        self,
        start_count: torch.Tensor,
        phase: TickPhase,
    ) -> None:
        """Restore stable source/target order across independently run families."""

        capacity = self.runtime.events.capacity
        positions = torch.arange(capacity, device=self.device)[None, :]
        selected = (
            (positions >= start_count[:, None])
            & (positions < self.runtime.events.count[:, None])
            & (self.runtime.events.phase == int(phase))
        )
        count = selected.sum(dim=1, dtype=torch.int64)
        maximum_id = (
            torch.maximum(self.runtime.events.source_id, self.runtime.events.target_id)
            .amax()
            .to(torch.int64)
            + 2
        )
        key = (
            self.runtime.events.source_id * maximum_id + self.runtime.events.target_id
        ) * (capacity + 1) + positions
        sentinel = torch.iinfo(torch.int64).max
        source_order = torch.argsort(
            torch.where(selected, key, sentinel), dim=1, stable=True
        )
        destination_order = torch.argsort(
            torch.where(selected, positions, sentinel), dim=1, stable=True
        )
        ranks = torch.arange(capacity, device=self.device)[None, :]
        valid_rank = ranks < count[:, None]
        rows = torch.arange(self.batch_size, device=self.device)[:, None].expand(
            self.batch_size, capacity
        )
        row_index = rows[valid_rank]
        destination = destination_order[valid_rank]
        for descriptor in fields(self.runtime.events):
            if descriptor.name == "count":
                continue
            value = getattr(self.runtime.events, descriptor.name)
            ordered = value.gather(1, source_order)
            value[row_index, destination] = ordered[valid_rank]
        # Sequence is positional and must remain monotonic after reordering.
        self.runtime.events.sequence[row_index, destination] = destination.to(
            torch.int32
        )

    def _step_candidate_(
        self, inputs: MechanicTickInputs
    ) -> tuple[torch.Tensor, torch.Tensor]:
        self._refresh_dynamic_planes_()
        event_start = self.runtime.events.count.clone()
        self.mechanics.activate_(self.runtime, inputs.champion_requested)
        self.mechanics.tick_cloak_(
            self.runtime,
            cancel_before_effect=inputs.cloak_cancel_before_effect,
        )

        soul_events = collect_souls_(self.passive_catalog, self.passive)
        self._append_passive_events_(soul_events, TickPhase.COMBAT)

        card_ids = self._combat_card_id()
        safe_target = inputs.connected_target_slot.clamp(
            min=0, max=self.max_entities - 1
        )
        observed_target_id = self.runtime.battle.entity_id.gather(1, safe_target)
        ramp_damage = update_damage_ramp_(
            self.damage_ramp,
            self.combat_catalog,
            card_ids,
            observed_target_id,
            inputs.connected,
            inputs.attack_rate,
            dt_ms=inputs.dt_ms[:, None],  # type: ignore[arg-type]
        )

        attack_source = inputs.attack_source_slot.clamp(
            min=0, max=self.max_entities - 1
        )
        attack_target = inputs.attack_target_slot.clamp(
            min=0, max=self.max_entities - 1
        )
        source_card = card_ids.gather(1, attack_source)
        _, has_ramp = self.combat_catalog.mechanic_slot(
            source_card, CombatMechanicOpcode.DAMAGE_RAMP
        )
        source_ramp_damage = ramp_damage.gather(1, attack_source)
        damage = torch.where(has_ramp, source_ramp_damage, inputs.attack_damage)
        target_crown = self.combat_world.crown.gather(1, attack_target)
        damage, _ = apply_crown_tower_scaling(
            self.combat_catalog, source_card, damage, target_crown
        )
        mechanic_damage = torch.where(
            inputs.attack_damage_already_applied,
            torch.zeros_like(damage),
            damage,
        )
        self.mechanics.resolve_attack_hits_(
            self.runtime,
            source_slot=attack_source,
            target_slot=attack_target,
            incoming_damage=mechanic_damage,
            valid=inputs.attack_valid,
            status_eligible=inputs.status_eligible,
        )

        special_source = inputs.special_source_slot.clamp(
            min=0, max=self.max_entities - 1
        )
        special_target = inputs.special_target_slot.clamp(
            min=0, max=self.max_entities - 1
        )
        special_card = self._special_card_id_for_slots(special_source)
        operations = self.special_catalog.opcode[special_card]
        commit_operations = torch.zeros_like(operations, dtype=torch.bool)
        for operation in (
            SpecialMovementOpcode.ATTACK_RECOIL,
            SpecialMovementOpcode.BATTLE_RAM_CHARGE,
            SpecialMovementOpcode.WALL_BREAKERS_DEMOLITION,
        ):
            commit_operations |= operations == int(operation)
        special_opcode = torch.where(
            commit_operations,
            operations,
            torch.zeros_like(operations),
        ).amax(dim=2)
        operation_slot = commit_operations.to(torch.int64).argmax(dim=2)
        recoil = self.special_catalog.distance_units[special_card, operation_slot]
        rows = torch.arange(self.batch_size, device=self.device)[:, None]
        source_hp = self.runtime.battle.entity_hp[rows, special_source]
        source_alive = self.runtime.battle.entity_active[rows, special_source]
        result = dispatch_attack_commits(
            special_opcode,
            source_id=self.runtime.battle.entity_id[rows, special_source],
            target_id=self.runtime.battle.entity_id[rows, special_target],
            source_position_units=torch.stack(
                (
                    self.runtime.battle.entity_x_units[rows, special_source],
                    self.runtime.battle.entity_y_units[rows, special_source],
                ),
                dim=-1,
            ),
            target_position_units=torch.stack(
                (
                    self.runtime.battle.entity_x_units[rows, special_target],
                    self.runtime.battle.entity_y_units[rows, special_target],
                ),
                dim=-1,
            ),
            source_player=self.runtime.battle.entity_player[rows, special_source],
            source_hitpoints=source_hp,
            source_alive=source_alive,
            target_kind=self.runtime.battle.entity_kind[rows, special_target],
            attack_committed=inputs.attack_committed & inputs.special_valid,
            attack_hit=inputs.attack_hit & inputs.special_valid,
            triggered=self.special_triggered[rows, special_source],
            recoil_distance_units=recoil,
        )
        self.runtime.battle.entity_hp[rows, special_source] = result.hitpoints
        self.runtime.battle.entity_active[rows, special_source] = result.alive
        self.special_triggered[rows, special_source] = result.triggered
        self.forced_movement[rows, special_source] |= result.forced_movement
        self.knockback_target_units[rows, special_source] = torch.where(
            result.knockback.started[..., None],
            result.knockback.target_units,
            self.knockback_target_units[rows, special_source],
        )
        self.knockback_velocity_work[rows, special_source] = torch.where(
            result.knockback.started,
            result.knockback.velocity_work,
            self.knockback_velocity_work[rows, special_source],
        )
        self._append_special_events_(result.events)
        self._sort_new_phase_events_(event_start, TickPhase.COMBAT)

        passive_events = step_passive_object_phase_(
            self.passive_catalog,
            self.passive,
            inputs.dt_ms.to(torch.float64),
            has_attack_target=inputs.has_attack_target,
            has_attack_range_target=inputs.has_attack_range_target,
            attack_started=inputs.attack_started,
            stunned=inputs.stunned,
            slow_multiplier=inputs.slow_multiplier,
            movement_speed_buff_multiplier=(inputs.movement_speed_buff_multiplier),
            spawn_rate=inputs.spawn_rate,
            rng=self.runtime.battle.rng,
        )
        self._append_passive_events_(passive_events, TickPhase.OBJECTS)
        self.runtime.phases.target_slot.copy_(self.passive.target_slot)
        self.runtime.mark_dirty(
            torch.ones(self.batch_size, dtype=torch.bool, device=self.device)
        )
        return ramp_damage, damage

    def step(self, inputs: MechanicTickInputs) -> MechanicTickResult:
        inputs.validate(self)
        preflight = self.preflight(inputs)
        committed = torch.zeros_like(preflight.supported)
        ramp_output = torch.zeros_like(self.damage_ramp.damage)
        adjusted = torch.zeros_like(inputs.attack_damage)
        event_before = self.runtime.events.count.clone()
        indices = torch.nonzero(preflight.supported, as_tuple=False).flatten()
        if not indices.numel():
            return MechanicTickResult(
                preflight,
                committed,
                ramp_output,
                adjusted,
                torch.zeros_like(event_before),
            )
        candidate = self._fork(indices)
        candidate_inputs = inputs.select(indices)
        try:
            ramp, damage = candidate._step_candidate_(candidate_inputs)
        except (IndexError, OverflowError, RuntimeError, ValueError):
            reason = preflight.reason.clone()
            for row in indices.tolist():
                row_indices = torch.tensor([row], dtype=torch.int64, device=self.device)
                row_candidate = self._fork(row_indices)
                row_inputs = inputs.select(row_indices)
                try:
                    row_ramp, row_damage = row_candidate._step_candidate_(row_inputs)
                except OverflowError:
                    reason[row] = int(DispatchReason.EVENT_CAPACITY)
                    continue
                except (IndexError, RuntimeError, ValueError):
                    reason[row] = int(DispatchReason.ATOMIC_FAILURE)
                    continue
                self._commit_(row_candidate, row_indices)
                committed[row] = True
                ramp_output[row] = row_ramp[0]
                adjusted[row] = row_damage[0]
            supported_after = preflight.supported & (
                (reason == int(DispatchReason.NONE)) | committed
            )
            retried = MechanicDispatchPreflight(
                supported_after, reason, preflight.unsupported_opcode
            )
            return MechanicTickResult(
                retried,
                committed,
                ramp_output,
                adjusted,
                self.runtime.events.count - event_before,
            )
        self._commit_(candidate, indices)
        committed[indices] = True
        ramp_output[indices] = ramp
        adjusted[indices] = damage
        return MechanicTickResult(
            preflight,
            committed,
            ramp_output,
            adjusted,
            self.runtime.events.count - event_before,
        )
