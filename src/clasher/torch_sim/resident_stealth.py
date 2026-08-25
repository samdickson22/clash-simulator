"""Retained lifecycle for serialized idle-hide and inactivity stealth.

This owner composes the existing data-driven passive kernels with resident
entity identity, target reach, visibility, effect eligibility, lock
cancellation, and transactional row publication.  Ordinary steps operate on
tensors only; Python entities are inspected solely by ``from_battles``.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any, cast

import torch

from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.kinematics import tiles_to_logic_units

from .catalog import MECHANIC_OPCODE
from .passive_mechanics import (
    TensorPassiveCatalog,
    TensorPassiveEvents,
    TensorPassiveState,
    step_hide_when_idle_,
    step_invisibility_when_not_attacking_,
)
from .runtime_state import TensorBattleRuntime


@dataclass(frozen=True)
class TensorStealthCatalog:
    passive: TensorPassiveCatalog
    core_to_passive: torch.Tensor
    hide_supported_core: torch.Tensor
    fade_supported_core: torch.Tensor
    attack_range_units: torch.Tensor
    can_attack_air: torch.Tensor
    can_attack_ground: torch.Tensor
    allow_area_damage_when_invisible: torch.Tensor


@dataclass(frozen=True)
class ResidentStealthStepResult:
    committed: torch.Tensor
    combat_events: TensorPassiveEvents
    object_events: TensorPassiveEvents
    hidden_building: torch.Tensor
    invisible: torch.Tensor
    targetable: torch.Tensor
    secondary_targetable: torch.Tensor
    effect_receivable: torch.Tensor
    area_receivable: torch.Tensor
    area_receivable_affects_hidden: torch.Tensor
    combat_blocked: torch.Tensor
    movement_blocked: torch.Tensor
    target_cancelled: torch.Tensor


@dataclass(frozen=True)
class ResidentStealthLockResult:
    committed: torch.Tensor
    target_cancelled: torch.Tensor


def _empty_events(device: torch.device) -> TensorPassiveEvents:
    return TensorPassiveEvents.empty(device)


def _select_event_rows(
    events: TensorPassiveEvents,
    rows: torch.Tensor,
) -> TensorPassiveEvents:
    if not events.batch_index.numel():
        return events
    selected = rows[events.batch_index]
    return TensorPassiveEvents(
        **{
            name: getattr(events, name)[selected]
            for name in events.__dataclass_fields__
        }
    )


def _merge_events(
    first: TensorPassiveEvents,
    second: TensorPassiveEvents,
    device: torch.device,
) -> TensorPassiveEvents:
    return TensorPassiveEvents.merge((first, second), device)


@dataclass
class TensorResidentStealth:
    catalog: TensorStealthCatalog
    state: TensorPassiveState
    combat_target_entity_id: torch.Tensor
    target_entity_id: torch.Tensor
    target_base_targetable: torch.Tensor
    target_blocks_secondary: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_distance_discount_sq_units: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.state.device

    @property
    def batch_size(self) -> int:
        return int(self.state.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.state.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorResidentStealth:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match stealth runtime")
        device = runtime.device
        loader = battles[0].card_loader
        definitions = loader.load_card_definitions()
        core_names = runtime.battle.card_names
        passive_names = tuple(
            name
            for name in core_names
            if name and resolve_card_name(name, definitions) in definitions
        )
        passive = TensorPassiveCatalog.compile(
            loader,
            passive_names,
            device=device,
        )
        core_to_passive = torch.zeros(len(core_names), dtype=torch.int64, device=device)
        hide = torch.zeros(len(core_names), dtype=torch.bool, device=device)
        fade = torch.zeros_like(hide)
        attack_range = torch.zeros(len(core_names), dtype=torch.int64, device=device)
        can_air = torch.zeros_like(hide)
        can_ground = torch.zeros_like(hide)
        allow_area = torch.zeros_like(hide)
        for core_id, name in enumerate(core_names):
            if not name:
                continue
            resolved = resolve_card_name(name, definitions)
            passive_id = passive.name_to_id.get(resolved, 0)
            core_to_passive[core_id] = passive_id
            operations = passive.mechanic_opcode[passive_id]
            hide[core_id] = bool(
                (operations == MECHANIC_OPCODE["HideWhenIdle"]).any().item()
            )
            fade[core_id] = bool(
                (operations == MECHANIC_OPCODE["InvisibilityWhenNotAttacking"])
                .any()
                .item()
            )
            stats = loader.get_card(name)
            if stats is None:
                continue
            attack_range[core_id] = tiles_to_logic_units(float(stats.range or 0.0))
            target_type = str(stats.target_type or "")
            can_air[core_id] = target_type in {
                "TID_TARGETS_AIR",
                "TID_TARGETS_AIR_AND_GROUND",
            } or bool(getattr(stats, "attacks_air", False))
            can_ground[core_id] = target_type in {
                "TID_TARGETS_GROUND",
                "TID_TARGETS_AIR_AND_GROUND",
                "TID_TARGETS_BUILDINGS",
                "TID_TARGETS_GROUND_AND_BUILDINGS",
                "TID_TARGETS_BUILDINGS_AND_GROUND",
            } or bool(getattr(stats, "attacks_ground", True))
            allow_area[core_id] = bool(stats.allow_area_damage_when_invisible)

        core_card = runtime.battle.entity_card.clamp(0, len(core_names) - 1)
        state = TensorPassiveState.from_entities(
            passive,
            entity_id=runtime.battle.entity_id.clone(),
            card_id=core_to_passive[core_card],
            player=runtime.battle.entity_player,
            x_units=runtime.battle.entity_x_units,
            y_units=runtime.battle.entity_y_units,
            active=runtime.entity_pool.active,
            alive=runtime.battle.entity_active,
            target_slot=runtime.phases.target_slot,
        )
        entity_shape = runtime.battle.entity_id.shape
        target_ids = torch.zeros(entity_shape, dtype=torch.int64, device=device)
        base_targetable = torch.ones(entity_shape, dtype=torch.bool, device=device)
        blocks_secondary = torch.zeros_like(base_targetable)
        collision = torch.zeros(entity_shape, dtype=torch.int64, device=device)
        discount = torch.zeros(entity_shape, dtype=torch.int64, device=device)
        for row, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if int(entity_id) > 0
            }
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                target = getattr(entity, "target_id", None)
                target_ids[row, slot] = 0 if target is None else int(target)
                collision[row, slot] = tiles_to_logic_units(
                    entity.get_collision_radius()
                )
                discount[row, slot] = max(
                    0,
                    int(
                        getattr(
                            entity,
                            "_native_target_distance_discount_sq_units",
                            0,
                        )
                        or 0
                    ),
                )
                base_targetable[row, slot] = (
                    getattr(entity, "entity_kind", 4) in {0, 1}
                    and not entity._has_death_spawn_target_immunity()
                )
                blocks_secondary[row, slot] = any(
                    callable(
                        blocker := getattr(
                            cast(Any, mechanic), "blocks_targeting", None
                        )
                    )
                    and bool(blocker(entity))
                    for mechanic in entity.mechanics
                )
                for mechanic in entity.mechanics:
                    operation = type(mechanic).__name__
                    mechanic_value = cast(Any, mechanic)
                    if operation == "HideWhenIdle":
                        state.hide_phase_ms[row, slot] = float(mechanic_value._phase_ms)
                        state.hidden_building[row, slot] = bool(
                            getattr(entity, "_hidden_building", False)
                        )
                        state.special_move_active[row, slot] = bool(
                            getattr(entity, "_special_move_active", False)
                        )
                    elif operation == "InvisibilityWhenNotAttacking":
                        state.fade_elapsed_ms[row, slot] = float(
                            mechanic_value.time_since_attack_ms
                        )
                        state.stealth_until_ms[row, slot] = int(
                            getattr(entity, "_stealth_until", 0) or 0
                        )
        return cls(
            TensorStealthCatalog(
                passive,
                core_to_passive,
                hide,
                fade,
                attack_range,
                can_air,
                can_ground,
                allow_area,
            ),
            state,
            target_ids,
            runtime.battle.entity_id.clone(),
            base_targetable,
            blocks_secondary,
            collision,
            discount,
        )

    def clone(self) -> TensorResidentStealth:
        result = copy.copy(self)
        result.state = self.state.clone()
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "state"}:
                continue
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentStealth:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("stealth fork rows must be one-dimensional")
        result = copy.copy(self)
        result.state = TensorPassiveState(
            **{
                name: getattr(self.state, name)[selected].clone()
                for name in self.state.__dataclass_fields__
            }
        )
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "state"}:
                continue
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentStealth,
        source_rows: torch.Tensor | list[int] | None = None,
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
            raise ValueError("stealth reset row layout differs")
        for name in self.state.__dataclass_fields__:
            getattr(self.state, name)[destination] = getattr(source.state, name)[
                selected
            ]
        for descriptor in fields(self):
            if descriptor.name in {"catalog", "state"}:
                continue
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _mechanic_sources(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        cards = runtime.battle.entity_card.clamp(
            0, self.catalog.hide_supported_core.numel() - 1
        )
        return runtime.entity_pool.active & (
            self.catalog.hide_supported_core[cards]
            | self.catalog.fade_supported_core[cards]
        )

    def refresh_new_entities_(
        self,
        runtime: TensorBattleRuntime,
        new: torch.Tensor,
        *,
        base_targetable: torch.Tensor,
        blocks_secondary: torch.Tensor,
        collision_radius_units: torch.Tensor,
        distance_discount_sq_units: torch.Tensor,
    ) -> None:
        """Initialize newly allocated or reused canonical slots exactly once."""

        fresh = TensorPassiveState.from_entities(
            self.catalog.passive,
            entity_id=runtime.battle.entity_id,
            card_id=self.catalog.core_to_passive[
                runtime.battle.entity_card.clamp(
                    0, self.catalog.core_to_passive.numel() - 1
                )
            ],
            player=runtime.battle.entity_player,
            x_units=runtime.battle.entity_x_units,
            y_units=runtime.battle.entity_y_units,
            active=runtime.entity_pool.active,
            alive=runtime.battle.entity_active,
            target_slot=runtime.phases.target_slot,
        )
        if new.shape != self.state.shape:
            raise ValueError("stealth new-entity mask must have shape [batch, entity]")
        for descriptor in fields(self.state):
            destination = getattr(self.state, descriptor.name)
            source = getattr(fresh, descriptor.name)
            expanded = new
            while expanded.ndim < destination.ndim:
                expanded = expanded.unsqueeze(-1)
            destination.copy_(torch.where(expanded, source, destination))
        self.target_entity_id.copy_(
            torch.where(new, runtime.battle.entity_id, self.target_entity_id)
        )
        self.combat_target_entity_id.copy_(
            torch.where(new, 0, self.combat_target_entity_id)
        )
        self.target_base_targetable.copy_(
            torch.where(new, base_targetable, self.target_base_targetable)
        )
        self.target_blocks_secondary.copy_(
            torch.where(new, blocks_secondary, self.target_blocks_secondary)
        )
        self.target_collision_radius_units.copy_(
            torch.where(new, collision_radius_units, self.target_collision_radius_units)
        )
        self.target_distance_discount_sq_units.copy_(
            torch.where(
                new,
                distance_discount_sq_units,
                self.target_distance_discount_sq_units,
            )
        )

    def visibility_planes(
        self,
        runtime: TensorBattleRuntime,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return current pre-component visibility without advancing clocks."""

        return self._visibility_planes(runtime, self.state)

    def _visibility_planes(
        self,
        runtime: TensorBattleRuntime,
        state: TensorPassiveState,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
    ]:
        now_ms = torch.round(runtime.battle.time * 1_000.0).to(torch.int64)[:, None]
        invisible = state.stealth_until_ms > now_ms
        alive = runtime.entity_pool.active & runtime.battle.entity_active
        targetable = (
            alive
            & self.target_base_targetable
            & ~self.target_blocks_secondary
            & ~state.hidden_building
            & ~invisible
        )
        secondary = (
            alive
            & self.target_base_targetable
            & ~state.hidden_building
            & ~self.target_blocks_secondary
        )
        effect = alive & ~state.hidden_building
        core_cards = runtime.battle.entity_card.clamp(
            0, self.catalog.allow_area_damage_when_invisible.numel() - 1
        )
        area = effect & (
            ~invisible | self.catalog.allow_area_damage_when_invisible[core_cards]
        )
        return invisible, targetable, secondary, effect, area

    def _target_pairs(
        self,
        runtime: TensorBattleRuntime,
        state: TensorPassiveState,
        targetable: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        core = runtime.battle
        cards = core.entity_card.clamp(0, self.catalog.attack_range_units.numel() - 1)
        source_x = core.entity_x_units.to(torch.int64)[:, :, None]
        source_y = core.entity_y_units.to(torch.int64)[:, :, None]
        target_x = core.entity_x_units.to(torch.int64)[:, None, :]
        target_y = core.entity_y_units.to(torch.int64)[:, None, :]
        distance_sq = (
            (target_x - source_x).square()
            + (target_y - source_y).square()
            - self.target_distance_discount_sq_units[:, None, :]
        ).clamp_min(0)
        reach = self.catalog.attack_range_units[cards].to(torch.int64)[:, :, None]
        reach = reach + self.target_collision_radius_units[:, None, :]
        target_air = runtime.catalog.is_air_unit[
            runtime.card_catalog_index[core.entity_card].clamp_min(0)
        ]
        planes = torch.where(
            target_air[:, None, :],
            self.catalog.can_attack_air[cards][:, :, None],
            self.catalog.can_attack_ground[cards][:, :, None],
        )
        pair = (
            runtime.entity_pool.active[:, :, None]
            & core.entity_active[:, :, None]
            & targetable[:, None, :]
            & (core.entity_player[:, :, None] != core.entity_player[:, None, :])
            & planes
            & (distance_sq <= reach.square())
        )
        has_any = pair.any(dim=2)
        target_id = self.combat_target_entity_id
        current = runtime.entity_pool.active[:, None, :] & (
            core.entity_id[:, None, :] == target_id[:, :, None]
        )
        current_pair = (pair & current).any(dim=2)
        return has_any, current_pair

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        attack_started: torch.Tensor | None = None,
        battle_mask: torch.Tensor | None = None,
    ) -> ResidentStealthStepResult:
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("stealth battle_mask must have shape [batch]")
        attacks = (
            torch.zeros_like(runtime.entity_pool.active)
            if attack_started is None
            else torch.as_tensor(attack_started, dtype=torch.bool, device=self.device)
        )
        if attacks.shape != runtime.entity_pool.active.shape:
            raise ValueError("attack_started must have shape [batch, entity]")
        sources = self._mechanic_sources(runtime)
        identity = (~runtime.entity_pool.active) | (
            self.target_entity_id == runtime.battle.entity_id
        )
        source_identity = (~sources) | (
            self.state.entity_id == runtime.battle.entity_id
        )
        supported = selected & identity.all(dim=1) & source_identity.all(dim=1)
        working = self.clone()
        core = runtime.battle
        working.state.x_units.copy_(core.entity_x_units.to(torch.int64))
        working.state.y_units.copy_(core.entity_y_units.to(torch.int64))
        working.state.player.copy_(core.entity_player)
        working.state.alive.copy_(runtime.entity_pool.active & core.entity_active)
        working.state.target_slot.copy_(runtime.phases.target_slot)
        object_ready = (
            runtime.entity_pool.active
            & core.entity_active
            & (core.entity_deploy_delay <= 1e-9)
            & ~core.entity_placement_pending
        )
        working.state.active.copy_(object_ready & supported[:, None])
        _, targetable_before, _, _, _ = working._visibility_planes(
            runtime, working.state
        )
        _, current_in_range = working._target_pairs(
            runtime, working.state, targetable_before
        )
        combat_events = step_invisibility_when_not_attacking_(
            working.catalog.passive,
            working.state,
            0.0,
            attack_started=attacks & supported[:, None],
            has_attack_range_target=current_in_range,
        )
        _, targetable_after_attack, _, _, _ = working._visibility_planes(
            runtime, working.state
        )
        has_attack_target, current_in_range = working._target_pairs(
            runtime, working.state, targetable_after_attack
        )
        hide_events = step_hide_when_idle_(
            working.catalog.passive,
            working.state,
            core.tick_milliseconds.to(torch.float64),
            has_attack_target=has_attack_target,
            stunned=runtime.status.stun_timer > 1e-9,
            slow_multiplier=runtime.status.slow_multiplier,
            movement_speed_buff_multiplier=(
                runtime.status.movement_speed_buff_multiplier
            ),
        )
        fade_events = step_invisibility_when_not_attacking_(
            working.catalog.passive,
            working.state,
            core.tick_milliseconds.to(torch.float64),
            attack_started=torch.zeros_like(attacks),
            has_attack_range_target=current_in_range,
        )
        object_events = _merge_events(hide_events, fade_events, self.device)
        working.state.active.copy_(runtime.entity_pool.active)
        invisible, targetable, secondary, effect, area = working._visibility_planes(
            runtime, working.state
        )
        hidden_self = working.state.hidden_building & sources
        cancelled = hidden_self & (working.combat_target_entity_id > 0)
        working.combat_target_entity_id.masked_fill_(cancelled, 0)
        working.state.target_slot.masked_fill_(cancelled, -1)

        committed_rows = torch.where(supported)[0]
        self.reset_rows_(committed_rows, working, committed_rows)
        runtime.phases.target_slot.copy_(
            torch.where(
                supported[:, None] & cancelled,
                -1,
                runtime.phases.target_slot,
            )
        )
        combat_events = _select_event_rows(combat_events, supported)
        object_events = _select_event_rows(object_events, supported)
        committed_mask = supported[:, None]
        return ResidentStealthStepResult(
            committed=~selected | supported,
            combat_events=combat_events,
            object_events=object_events,
            hidden_building=self.state.hidden_building & committed_mask,
            invisible=invisible & committed_mask,
            targetable=targetable & committed_mask,
            secondary_targetable=secondary & committed_mask,
            effect_receivable=effect & committed_mask,
            area_receivable=area & committed_mask,
            area_receivable_affects_hidden=(
                runtime.entity_pool.active & committed_mask
            ),
            combat_blocked=self.state.hidden_building & committed_mask,
            movement_blocked=self.state.hidden_building & committed_mask,
            target_cancelled=cancelled & committed_mask,
        )

    def validate_combat_locks_(
        self,
        runtime: TensorBattleRuntime,
        *,
        battle_mask: torch.Tensor | None = None,
    ) -> ResidentStealthLockResult:
        """Cancel stale locks at the next combat validation boundary."""

        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("stealth lock battle_mask must have shape [batch]")
        sources = self._mechanic_sources(runtime)
        identity = (~runtime.entity_pool.active) | (
            self.target_entity_id == runtime.battle.entity_id
        )
        source_identity = (~sources) | (
            self.state.entity_id == runtime.battle.entity_id
        )
        supported = selected & identity.all(dim=1) & source_identity.all(dim=1)
        _, targetable, _, _, _ = self._visibility_planes(runtime, self.state)
        target_slots = runtime.entity_pool.slots_for_ids(self.combat_target_entity_id)
        valid_target = target_slots >= 0
        safe_target = target_slots.clamp_min(0)
        locked_targetable = torch.gather(targetable, 1, safe_target)
        cancelled = (
            supported[:, None]
            & valid_target
            & ~locked_targetable
            & runtime.entity_pool.active
            & runtime.battle.entity_active
        )
        self.combat_target_entity_id.masked_fill_(cancelled, 0)
        self.state.target_slot.masked_fill_(cancelled, -1)
        runtime.phases.target_slot.masked_fill_(cancelled, -1)
        return ResidentStealthLockResult(
            committed=~selected | supported,
            target_cancelled=cancelled,
        )


__all__ = [
    "ResidentStealthLockResult",
    "ResidentStealthStepResult",
    "TensorResidentStealth",
    "TensorStealthCatalog",
]
