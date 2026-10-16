"""Retained full lifecycle for serialized FishermanHook mechanics.

The owner composes the generalized hook kernel with resident target
acquisition, muzzle geometry, combat/object phase ordering, forced-movement
clock interruption, and transactional row publication.  The production path
uses retained tensors only and never steps Python mechanic objects.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Any, cast

import torch

from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.entities import Building
from clasher.kinematics import tiles_to_logic_units
from clasher.unit_traits import is_airborne_target

from .combat import StationaryCombatState
from .combat_adapter import project_stationary_combat
from .combat_clock_transitions import (
    TensorCombatClockPlanes,
    apply_forced_movement_interrupt_,
)
from .movement import normalized_vector_units
from .runtime_state import TensorBattleRuntime
from .special_movement import (
    HookPhase,
    HookState,
    SpecialMovementOpcode,
    TensorSpecialMovementCatalog,
    step_fisherman_hook,
)


class HookLifecycleEventOpcode(IntEnum):
    WINDUP_STARTED = 1
    PROJECTILE_LAUNCHED = 2
    TARGET_ATTACHED = 3
    FINISHED = 4
    CANCELLED = 5


@dataclass(frozen=True)
class TensorHookLifecycleEvents:
    valid: torch.Tensor
    opcode: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor


@dataclass(frozen=True)
class TensorFishermanHookCatalog:
    special: TensorSpecialMovementCatalog
    core_to_special: torch.Tensor
    operation_slot: torch.Tensor
    supported_core: torch.Tensor
    muzzle_radius_units: torch.Tensor
    owner_y_offset_units: torch.Tensor


@dataclass(frozen=True)
class FishermanHookStepResult:
    committed: torch.Tensor
    combat_events: TensorHookLifecycleEvents
    object_events: TensorHookLifecycleEvents
    forced_movement_started: torch.Tensor
    charge_reset: torch.Tensor
    damage: torch.Tensor


def _clone_combat(value: StationaryCombatState) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            descriptor.name: getattr(value, descriptor.name).clone()
            for descriptor in fields(value)
        }
    )


def _empty_events(reference: torch.Tensor) -> TensorHookLifecycleEvents:
    return TensorHookLifecycleEvents(
        valid=torch.zeros_like(reference),
        opcode=torch.zeros_like(reference, dtype=torch.int16),
        source_id=torch.zeros_like(reference, dtype=torch.int64),
        target_id=torch.zeros_like(reference, dtype=torch.int64),
    )


def _events(
    mask: torch.Tensor,
    opcode: HookLifecycleEventOpcode,
    source_id: torch.Tensor,
    target_id: torch.Tensor,
) -> TensorHookLifecycleEvents:
    return TensorHookLifecycleEvents(
        valid=mask,
        opcode=torch.where(
            mask,
            torch.full_like(mask, int(opcode), dtype=torch.int16),
            torch.zeros_like(mask, dtype=torch.int16),
        ),
        source_id=torch.where(mask, source_id, 0),
        target_id=torch.where(mask, target_id, 0),
    )


@dataclass
class TensorResidentFishermanHooks:
    catalog: TensorFishermanHookCatalog
    state: HookState
    combat: StationaryCombatState
    combat_target_entity_id: torch.Tensor
    source_entity_id: torch.Tensor
    target_entity_id: torch.Tensor
    target_targetable: torch.Tensor
    target_airborne: torch.Tensor
    target_building: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_forced_movement_allowed: torch.Tensor
    target_special_forced_movement_supported: torch.Tensor
    source_attack_mode_multiplier: torch.Tensor
    charge_ready: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.state.phase.device

    @property
    def batch_size(self) -> int:
        return int(self.state.phase.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.state.phase.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorResidentFishermanHooks:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match Fisherman hook runtime")
        loader = battles[0].card_loader
        definitions = loader.load_card_definitions()
        core_names = runtime.battle.card_names
        special = TensorSpecialMovementCatalog.compile(
            loader,
            (name for name in core_names if name),
            device=runtime.device,
        )
        core_to_special = torch.zeros(
            len(core_names), dtype=torch.int64, device=runtime.device
        )
        operation_slot = torch.full(
            (len(core_names),), -1, dtype=torch.int64, device=runtime.device
        )
        supported = torch.zeros(
            len(core_names), dtype=torch.bool, device=runtime.device
        )
        muzzle = torch.zeros(len(core_names), dtype=torch.int64, device=runtime.device)
        y_offset = torch.zeros_like(muzzle)
        for core_id, name in enumerate(core_names):
            if not name:
                continue
            resolved = resolve_card_name(name, definitions)
            special_id = special.name_to_id[resolved]
            core_to_special[core_id] = special_id
            hook_slots = torch.where(
                special.opcode[special_id] == int(SpecialMovementOpcode.FISHERMAN_HOOK)
            )[0]
            if hook_slots.numel() != 1:
                continue
            operation_slot[core_id] = hook_slots[0]
            supported[core_id] = True
            stats = loader.get_card(name)
            if stats is not None:
                muzzle[core_id] = tiles_to_logic_units(
                    float(stats.projectile_start_radius or 0.0)
                )
                y_offset[core_id] = tiles_to_logic_units(
                    float(stats.projectile_y_offset or 0.0)
                )

        shape = runtime.battle.entity_id.shape
        positions = torch.stack(
            (
                runtime.battle.entity_x_units,
                runtime.battle.entity_y_units,
            ),
            dim=2,
        ).to(torch.int64)
        state = HookState(
            phase=torch.zeros(shape, dtype=torch.int8, device=runtime.device),
            source_position_units=positions.clone(),
            target_position_units=positions.clone(),
            hook_position_units=torch.zeros(
                (*shape, 2), dtype=torch.int64, device=runtime.device
            ),
            target_id=torch.full(shape, -1, dtype=torch.int64, device=runtime.device),
            windup_remaining_ms=torch.zeros(
                shape, dtype=torch.float64, device=runtime.device
            ),
            target_forced=torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            special_active=torch.zeros(shape, dtype=torch.bool, device=runtime.device),
            special_consumed=torch.zeros(
                shape, dtype=torch.bool, device=runtime.device
            ),
        )
        combat = project_stationary_combat(
            battles,
            runtime.catalog,
            capacity=runtime.max_entities,
            device=runtime.device,
        ).state
        combat_ids = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        targetable = torch.ones(shape, dtype=torch.bool, device=runtime.device)
        airborne = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        building = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        collision = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        forced_allowed = torch.ones(shape, dtype=torch.bool, device=runtime.device)
        forced_special = torch.ones(shape, dtype=torch.bool, device=runtime.device)
        attack_mode = torch.ones(shape, dtype=torch.float64, device=runtime.device)
        charge = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if int(entity_id) > 0
            }
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                target = getattr(entity, "target_id", None)
                combat_ids[row, slot] = 0 if target is None else int(target)
                targetable[row, slot] = entity.is_targetable_by(1 - entity.player_id)
                airborne[row, slot] = is_airborne_target(entity)
                building[row, slot] = isinstance(entity, Building)
                collision[row, slot] = tiles_to_logic_units(
                    entity.get_collision_radius()
                )
                forced_allowed[row, slot] = entity.can_receive_forced_movement(
                    None, "hook"
                )
                forced_special[row, slot] = not any(
                    callable(getattr(mechanic, "on_forced_movement", None))
                    for mechanic in entity.mechanics
                )
                attack_mode[row, slot] = float(
                    getattr(entity, "attack_mode_multiplier", 1.0)
                )
                charge[row, slot] = bool(getattr(entity, "is_charging", False))
                if not bool(supported[runtime.battle.entity_card[row, slot]].item()):
                    continue
                mechanics = [
                    mechanic
                    for mechanic in entity.mechanics
                    if type(mechanic).__name__ == "FishermanHook"
                ]
                if len(mechanics) != 1:
                    continue
                mechanic = cast(Any, mechanics[0])
                phase = {
                    "idle": HookPhase.IDLE,
                    "windup": HookPhase.WINDUP,
                    "flight": HookPhase.FLIGHT,
                    "drag": HookPhase.DRAG,
                }[mechanic.state]
                hook_target = battle.entities.get(mechanic.hook_target_id)
                state.phase[row, slot] = int(phase)
                state.target_id[row, slot] = int(mechanic.hook_target_id or -1)
                state.windup_remaining_ms[row, slot] = float(
                    mechanic.windup_remaining_ms
                )
                state.special_active[row, slot] = bool(
                    getattr(entity, "_special_move_active", False)
                )
                if hook_target is not None:
                    state.target_position_units[row, slot] = torch.tensor(
                        (
                            tiles_to_logic_units(hook_target.position.x),
                            tiles_to_logic_units(hook_target.position.y),
                        ),
                        dtype=torch.int64,
                        device=runtime.device,
                    )
                    state.target_forced[row, slot] = bool(
                        hook_target.forced_movement_active
                    )
                if mechanic.hook_position is not None:
                    state.hook_position_units[row, slot] = torch.tensor(
                        (
                            tiles_to_logic_units(mechanic.hook_position.x),
                            tiles_to_logic_units(mechanic.hook_position.y),
                        ),
                        dtype=torch.int64,
                        device=runtime.device,
                    )
        return cls(
            TensorFishermanHookCatalog(
                special,
                core_to_special,
                operation_slot,
                supported,
                muzzle,
                y_offset,
            ),
            state,
            combat,
            combat_ids,
            runtime.battle.entity_id.clone(),
            runtime.battle.entity_id.clone(),
            targetable,
            airborne,
            building,
            collision,
            forced_allowed,
            forced_special,
            attack_mode,
            charge,
        )

    def clone(self) -> TensorResidentFishermanHooks:
        result = copy.copy(self)
        result.state = HookState(
            **{
                descriptor.name: getattr(self.state, descriptor.name).clone()
                for descriptor in fields(self.state)
            }
        )
        result.combat = _clone_combat(self.combat)
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "state", "combat"}:
                continue
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorResidentFishermanHooks:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("hook fork rows must be one-dimensional")
        result = self.clone()
        result.state = HookState(
            **{
                descriptor.name: getattr(self.state, descriptor.name)[selected].clone()
                for descriptor in fields(self.state)
            }
        )
        result.combat = StationaryCombatState(
            **{
                descriptor.name: getattr(self.combat, descriptor.name)[selected].clone()
                for descriptor in fields(self.combat)
            }
        )
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "state", "combat"}:
                continue
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | Sequence[int],
        source: TensorResidentFishermanHooks,
        source_rows: torch.Tensor | Sequence[int] | None = None,
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
            raise ValueError("hook reset row layout differs")
        for descriptor in fields(self.state):
            getattr(self.state, descriptor.name)[destination] = getattr(
                source.state, descriptor.name
            )[selected]
        for descriptor in fields(self.combat):
            getattr(self.combat, descriptor.name)[destination] = getattr(
                source.combat, descriptor.name
            )[selected]
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "state", "combat"}:
                continue
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _source_mask(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        cards = runtime.battle.entity_card.clamp(
            0, self.catalog.supported_core.numel() - 1
        )
        return (
            runtime.entity_pool.active
            & runtime.battle.entity_active
            & self.catalog.supported_core[cards]
        )

    def _parameters(self, runtime: TensorBattleRuntime) -> tuple[torch.Tensor, ...]:
        cards = runtime.battle.entity_card.clamp(
            0, self.catalog.supported_core.numel() - 1
        )
        special_card = self.catalog.core_to_special[cards]
        operation = self.catalog.operation_slot[cards].clamp_min(0)
        index = (special_card, operation)
        catalog = self.catalog.special
        return (
            catalog.min_range_units[index],
            catalog.max_range_units[index],
            catalog.windup_ms[index],
            catalog.speed_units[index],
            catalog.secondary_speed_units[index],
            catalog.tertiary_speed_units[index],
            catalog.margin_units[index],
            catalog.as_attractor[index],
        )

    def _target_geometry(
        self,
        runtime: TensorBattleRuntime,
        state: HookState,
        source_mask: torch.Tensor,
        plane_override: torch.Tensor | None,
    ) -> tuple[torch.Tensor, ...]:
        core = runtime.battle
        rows = torch.arange(self.batch_size, device=self.device)[:, None]
        source_slots = torch.arange(self.max_entities, device=self.device)[None, :]
        min_range, max_range, *_ = self._parameters(runtime)
        source_x = core.entity_x_units.to(torch.int64)[:, :, None]
        source_y = core.entity_y_units.to(torch.int64)[:, :, None]
        target_x = core.entity_x_units.to(torch.int64)[:, None, :]
        target_y = core.entity_y_units.to(torch.int64)[:, None, :]
        distance_sq = (target_x - source_x).square() + (target_y - source_y).square()
        target_radius = self.target_collision_radius_units[:, None, :]
        source_cards = core.entity_card.clamp(
            0, self.catalog.supported_core.numel() - 1
        )
        special_cards = self.catalog.core_to_special[source_cards]
        operation = self.catalog.operation_slot[source_cards].clamp_min(0)
        special = self.catalog.special
        can_air = special.hits_air[special_cards, operation]
        can_ground = special.hits_ground[special_cards, operation]
        # Fisherman's ordinary target plane is ground in current serialized
        # data; the fallback to the runtime combat projection keeps aliases
        # and future rows data driven when the special payload omits planes.
        serialized_planes = can_air | can_ground
        can_air = torch.where(serialized_planes, can_air, self.combat.can_attack_air)
        can_ground = torch.where(
            serialized_planes, can_ground, self.combat.can_attack_ground
        )
        plane = torch.where(
            self.target_airborne[:, None, :],
            can_air[:, :, None],
            can_ground[:, :, None],
        )
        if plane_override is not None:
            override = torch.as_tensor(
                plane_override, dtype=torch.bool, device=self.device
            )
            if override.shape != core.entity_id.shape:
                raise ValueError("target_plane_valid must have shape [batch, entity]")
            plane &= override[:, None, :]
        candidates = (
            source_mask[:, :, None]
            & runtime.entity_pool.active[:, None, :]
            & core.entity_active[:, None, :]
            & self.target_targetable[:, None, :]
            & (core.entity_player[:, :, None] != core.entity_player[:, None, :])
            & plane
            & (distance_sq > min_range[:, :, None].square())
            & (distance_sq <= (max_range[:, :, None] + target_radius).square())
        )
        slots = torch.arange(self.max_entities, device=self.device)[None, None, :]
        target_ids = core.entity_id[:, None, :]
        direction = torch.where(core.entity_player[:, :, None] == 0, 1, -1)
        relative_x = direction * (
            core.entity_x_units[:, None, :].to(torch.int64) - 9_000
        )
        relative_y = direction * (
            core.entity_y_units[:, None, :].to(torch.int64) - 16_000
        )
        order = slots.expand(self.batch_size, self.max_entities, -1)
        candidate_distance = torch.where(
            candidates,
            distance_sq,
            torch.full_like(distance_sq, torch.iinfo(torch.int64).max),
        )
        for key in (target_ids, relative_y, relative_x, candidate_distance):
            gathered = torch.gather(key.expand_as(order), 2, order)
            local = torch.argsort(gathered, dim=2, stable=True)
            order = torch.gather(order, 2, local)
        ordered_valid = torch.gather(candidates, 2, order)
        acquired_slot = order[:, :, 0]
        acquired_valid = ordered_valid[:, :, 0]
        acquired_id = torch.gather(core.entity_id, 1, acquired_slot)

        retained = runtime.entity_pool.active[:, None, :] & (
            core.entity_id[:, None, :] == state.target_id[:, :, None]
        )
        retained_slot = retained.to(torch.int64).argmax(dim=2)
        retained_found = retained.any(dim=2)
        idle = state.phase == int(HookPhase.IDLE)
        target_slot = torch.where(idle, acquired_slot, retained_slot)
        target_valid = torch.where(idle, acquired_valid, retained_found)
        target_position = torch.stack(
            (
                torch.gather(core.entity_x_units, 1, target_slot),
                torch.gather(core.entity_y_units, 1, target_slot),
            ),
            dim=2,
        ).to(torch.int64)
        current_distance_sq = (
            target_position[..., 0] - core.entity_x_units.to(torch.int64)
        ).square() + (
            target_position[..., 1] - core.entity_y_units.to(torch.int64)
        ).square()
        current_radius = torch.gather(
            self.target_collision_radius_units, 1, target_slot
        )
        current_targetable = torch.gather(self.target_targetable, 1, target_slot)
        current_plane = torch.gather(
            plane,
            2,
            target_slot[:, :, None],
        )[:, :, 0]
        target_in_range = (
            target_valid
            & current_targetable
            & current_plane
            & (current_distance_sq > min_range.square())
            & (current_distance_sq <= (max_range + current_radius).square())
        )
        forced = torch.gather(self.target_forced_movement_allowed, 1, target_slot)
        forced &= torch.gather(
            self.target_special_forced_movement_supported, 1, target_slot
        )
        target_building = torch.gather(self.target_building, 1, target_slot)
        target_radius = current_radius
        del rows, source_slots
        return (
            torch.where(idle, acquired_id, state.target_id),
            target_slot,
            target_position,
            target_valid,
            target_in_range,
            current_plane,
            forced,
            target_building,
            target_radius,
        )

    def _launch_positions(
        self,
        runtime: TensorBattleRuntime,
        target_position: torch.Tensor,
    ) -> torch.Tensor:
        core = runtime.battle
        cards = core.entity_card.clamp(0, self.catalog.supported_core.numel() - 1)
        source = torch.stack((core.entity_x_units, core.entity_y_units), dim=2).to(
            torch.int64
        )
        direction = target_position - source
        muzzle = normalized_vector_units(
            direction, self.catalog.muzzle_radius_units[cards]
        )
        result = source + muzzle
        result[..., 1] += torch.where(
            core.entity_player == 0,
            self.catalog.owner_y_offset_units[cards],
            -self.catalog.owner_y_offset_units[cards],
        )
        return result

    def _clocks(self, combat: StationaryCombatState) -> TensorCombatClockPlanes:
        return TensorCombatClockPlanes(
            attack_cooldown=combat.attack_cooldown,
            target_slot=combat.target_slot,
            attack_windup_active=combat.attack_windup_active,
            attack_preload_blocked=combat.attack_preload_blocked,
            has_attacked_once=combat.has_attacked_once,
        )

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        target_plane_valid: torch.Tensor | None = None,
        battle_mask: torch.Tensor | None = None,
    ) -> FishermanHookStepResult:
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("hook battle_mask must have shape [batch]")
        source_mask = self._source_mask(runtime)
        character = runtime.entity_pool.active & (
            (runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1)
        )
        identity = (~character) | (self.target_entity_id == runtime.battle.entity_id)
        source_identity = (~source_mask) | (
            self.source_entity_id == runtime.battle.entity_id
        )
        supported = selected & identity.all(dim=1) & source_identity.all(dim=1)
        speculative = runtime.clone()
        speculative.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        working.combat.attack_cooldown.copy_(self.combat.attack_cooldown)
        positions = torch.stack(
            (
                speculative.battle.entity_x_units,
                speculative.battle.entity_y_units,
            ),
            dim=2,
        ).to(torch.int64)
        working.state = HookState(
            phase=working.state.phase,
            source_position_units=positions.clone(),
            target_position_units=working.state.target_position_units,
            hook_position_units=working.state.hook_position_units,
            target_id=working.state.target_id,
            windup_remaining_ms=working.state.windup_remaining_ms,
            target_forced=working.state.target_forced,
            special_active=working.state.special_active,
            special_consumed=torch.zeros_like(working.state.special_consumed),
        )
        prior_phase = working.state.phase.clone()
        (
            acquired_id,
            target_slot,
            target_position,
            target_valid,
            target_in_range,
            target_plane,
            target_forced_allowed,
            target_building,
            target_radius,
        ) = working._target_geometry(
            speculative, working.state, source_mask, target_plane_valid
        )
        working.state = HookState(
            **{
                **{
                    descriptor.name: getattr(working.state, descriptor.name)
                    for descriptor in fields(working.state)
                },
                "target_position_units": target_position,
            }
        )
        (
            _,
            _,
            windup_ms,
            projectile_speed,
            drag_back_speed,
            drag_self_speed,
            drag_margin,
            attractor,
        ) = working._parameters(speculative)
        target_building &= attractor
        attack_rate = (
            speculative.status.attack_speed_buff_multiplier
            * speculative.status.attack_speed_debuff_multiplier
            * working.source_attack_mode_multiplier
        )
        launch_position = working._launch_positions(speculative, target_position)
        combat_result = step_fisherman_hook(
            working.state,
            acquired_target_id=acquired_id,
            launch_position_units=launch_position,
            target_valid=target_valid,
            target_in_range=target_in_range,
            target_plane_valid=target_plane,
            target_can_forced_move=target_forced_allowed,
            target_is_building=target_building,
            move_allowed=torch.ones_like(source_mask),
            attack_rate=attack_rate,
            windup_ms=windup_ms,
            projectile_speed_units=projectile_speed,
            drag_back_speed_units=drag_back_speed,
            drag_self_speed_units=drag_self_speed,
            drag_margin_units=drag_margin,
            source_radius_units=working.combat.collision_radius_units,
            target_radius_units=target_radius,
            stunned=speculative.status.stun_timer > 1e-9,
            dt_ms=50,
        )
        combat_owned = source_mask & (
            (prior_phase == int(HookPhase.IDLE))
            | (prior_phase == int(HookPhase.WINDUP))
        )
        merged: dict[str, torch.Tensor] = {}
        for descriptor in fields(working.state):
            before = getattr(working.state, descriptor.name)
            after = getattr(combat_result.state, descriptor.name)
            mask = combat_owned.reshape(
                *combat_owned.shape, *((1,) * (before.ndim - combat_owned.ndim))
            )
            merged[descriptor.name] = torch.where(mask, after, before)
        working.state = HookState(**merged)
        combat_phase = working.state.phase.clone()
        started = (
            combat_owned
            & (prior_phase == int(HookPhase.IDLE))
            & (combat_phase == int(HookPhase.WINDUP))
        )
        launched = (
            combat_owned
            & (prior_phase == int(HookPhase.WINDUP))
            & (combat_phase == int(HookPhase.FLIGHT))
        )
        abnormal_combat_cancel = (
            combat_owned
            & (prior_phase != int(HookPhase.IDLE))
            & (combat_phase == int(HookPhase.IDLE))
        )
        working.combat_target_entity_id.copy_(
            torch.where(started, acquired_id, working.combat_target_entity_id)
        )
        working.combat.target_slot.copy_(
            torch.where(started, target_slot, working.combat.target_slot)
        )
        working.combat_target_entity_id.masked_fill_(abnormal_combat_cancel, 0)
        working.combat.target_slot.masked_fill_(abnormal_combat_cancel, -1)

        # A launch from combat advances once in this same frame's object phase.
        object_prior = working.state.phase.clone()
        (
            acquired_id,
            target_slot,
            target_position,
            target_valid,
            target_in_range,
            target_plane,
            target_forced_allowed,
            target_building,
            target_radius,
        ) = working._target_geometry(
            speculative, working.state, source_mask, target_plane_valid
        )
        working.state = HookState(
            **{
                **{
                    descriptor.name: getattr(working.state, descriptor.name)
                    for descriptor in fields(working.state)
                },
                "target_position_units": target_position,
            }
        )
        object_result = step_fisherman_hook(
            working.state,
            acquired_target_id=acquired_id,
            launch_position_units=launch_position,
            target_valid=target_valid,
            target_in_range=target_in_range,
            target_plane_valid=target_plane,
            target_can_forced_move=target_forced_allowed,
            target_is_building=target_building & attractor,
            move_allowed=torch.ones_like(source_mask),
            attack_rate=attack_rate,
            windup_ms=windup_ms,
            projectile_speed_units=projectile_speed,
            drag_back_speed_units=drag_back_speed,
            drag_self_speed_units=drag_self_speed,
            drag_margin_units=drag_margin,
            source_radius_units=working.combat.collision_radius_units,
            target_radius_units=target_radius,
            stunned=torch.zeros_like(source_mask),
            dt_ms=50,
        )
        object_owned = source_mask & (
            (object_prior == int(HookPhase.FLIGHT))
            | (object_prior == int(HookPhase.DRAG))
        )
        merged = {}
        for descriptor in fields(working.state):
            before = getattr(working.state, descriptor.name)
            after = getattr(object_result.state, descriptor.name)
            mask = object_owned.reshape(
                *object_owned.shape, *((1,) * (before.ndim - object_owned.ndim))
            )
            merged[descriptor.name] = torch.where(mask, after, before)
        working.state = HookState(**merged)
        object_phase = working.state.phase
        attached = (
            object_owned
            & (object_prior == int(HookPhase.FLIGHT))
            & (object_phase == int(HookPhase.DRAG))
        )
        ended = object_owned & (object_phase == int(HookPhase.IDLE))
        normal_finish = ended & (object_prior == int(HookPhase.DRAG)) & target_valid
        abnormal_cancel = ended & ~normal_finish
        working.combat_target_entity_id.masked_fill_(abnormal_cancel, 0)
        working.combat.target_slot.masked_fill_(abnormal_cancel, -1)

        target_forced_started = attached & ~target_building
        target_forced_mask = torch.zeros_like(source_mask)
        forced_rows, forced_sources = torch.where(target_forced_started)
        target_forced_mask[forced_rows, target_slot[forced_rows, forced_sources]] = True
        transition = apply_forced_movement_interrupt_(
            working._clocks(working.combat),
            movement_started=target_forced_mask,
            hit_speed_ms=working.combat.hit_speed_ms,
            first_hit_ms=working.combat.first_hit_ms,
            charged_attack_ready=working.charge_ready,
        )
        forced_values = working.state.target_forced
        forced_rows = torch.arange(self.batch_size, device=self.device)[
            :, None
        ].expand_as(target_slot)[object_owned]
        forced_slots = target_slot[object_owned]
        working.combat.forced_movement[forced_rows, forced_slots] = forced_values[
            object_owned
        ]
        # Publish the hook-owned source and target movement.
        source_positions = working.state.source_position_units
        speculative.battle.entity_x_units.copy_(
            torch.where(
                source_mask,
                source_positions[..., 0].to(torch.int32),
                speculative.battle.entity_x_units,
            )
        )
        speculative.battle.entity_y_units.copy_(
            torch.where(
                source_mask,
                source_positions[..., 1].to(torch.int32),
                speculative.battle.entity_y_units,
            )
        )
        moved_target = object_owned & ~target_building
        rows = torch.arange(self.batch_size, device=self.device)[:, None].expand_as(
            target_slot
        )
        moved_rows = rows[moved_target]
        moved_slots = target_slot[moved_target]
        speculative.battle.entity_x_units[moved_rows, moved_slots] = (
            working.state.target_position_units[..., 0][moved_target].to(torch.int32)
        )
        speculative.battle.entity_y_units[moved_rows, moved_slots] = (
            working.state.target_position_units[..., 1][moved_target].to(torch.int32)
        )
        commit = supported
        committed_rows = torch.where(commit)[0]
        self.reset_rows_(committed_rows, working, committed_rows)
        for descriptor in fields(speculative.battle):
            left = getattr(runtime.battle, descriptor.name)
            right = getattr(speculative.battle, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[commit] = right[commit]
        runtime.phases.target_slot[commit] = working.combat.target_slot[commit]
        source_ids = runtime.battle.entity_id
        targets = torch.where(
            working.state.target_id > 0,
            working.state.target_id,
            self.combat_target_entity_id,
        )
        combat_event = _empty_events(source_mask)
        combat_event = _events(
            started | launched | abnormal_combat_cancel,
            HookLifecycleEventOpcode.WINDUP_STARTED,
            source_ids,
            targets,
        )
        combat_event = TensorHookLifecycleEvents(
            combat_event.valid,
            torch.where(
                launched,
                int(HookLifecycleEventOpcode.PROJECTILE_LAUNCHED),
                torch.where(
                    abnormal_combat_cancel,
                    int(HookLifecycleEventOpcode.CANCELLED),
                    combat_event.opcode,
                ),
            ).to(torch.int16),
            combat_event.source_id,
            combat_event.target_id,
        )
        object_event = _events(
            attached | ended,
            HookLifecycleEventOpcode.TARGET_ATTACHED,
            source_ids,
            targets,
        )
        object_event = TensorHookLifecycleEvents(
            object_event.valid,
            torch.where(
                normal_finish,
                int(HookLifecycleEventOpcode.FINISHED),
                torch.where(
                    abnormal_cancel,
                    int(HookLifecycleEventOpcode.CANCELLED),
                    object_event.opcode,
                ),
            ).to(torch.int16),
            object_event.source_id,
            object_event.target_id,
        )
        event_rows = commit[:, None]
        combat_event = TensorHookLifecycleEvents(
            combat_event.valid & event_rows,
            combat_event.opcode,
            combat_event.source_id,
            combat_event.target_id,
        )
        object_event = TensorHookLifecycleEvents(
            object_event.valid & event_rows,
            object_event.opcode,
            object_event.source_id,
            object_event.target_id,
        )
        return FishermanHookStepResult(
            committed=~selected | commit,
            combat_events=combat_event,
            object_events=object_event,
            forced_movement_started=target_forced_mask & commit[:, None],
            charge_reset=transition.charge_reset & commit[:, None],
            damage=torch.zeros_like(runtime.battle.entity_hp),
        )


__all__ = [
    "FishermanHookStepResult",
    "HookLifecycleEventOpcode",
    "TensorFishermanHookCatalog",
    "TensorHookLifecycleEvents",
    "TensorResidentFishermanHooks",
]
