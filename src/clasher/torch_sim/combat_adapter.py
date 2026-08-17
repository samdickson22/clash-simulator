"""Fail-closed bridge between Python battles and stationary tensor combat.

The tensor kernel intentionally knows nothing about mutable ``Entity``
objects.  This adapter is the single projection/synchronization boundary for
the ordinary combat component.  It accepts only state whose complete
component semantics are represented by :class:`StationaryCombatState`; every
other serialized operation or runtime phase is marked unsupported before the
kernel can mutate anything.

This is a combat-component adapter, not a complete tick adapter.  Deployment,
movement, hitpoint lifetime, buff expiry, object updates, cleanup, and win
resolution remain owned by their corresponding phase kernels or the Python
fail-closed path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Sequence

import torch

from clasher.arena import Position
from clasher.entities import Building, Entity, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.unit_traits import is_airborne_target, is_native_building_target

from .catalog import TensorCardCatalog
from .combat import (
    CombatStepResult,
    StationaryCombatState,
    UnsupportedStationaryCombatError,
    stationary_combat_support_mask,
    step_stationary_combat_,
)

if TYPE_CHECKING:
    from clasher.battle import BattleState


class UnsupportedCombatReason(str, Enum):
    """Stable diagnostic codes for fail-closed combat projection."""

    NON_CHARACTER_OBJECT = "non_character_object"
    CARD_NOT_IN_CATALOG = "card_not_in_catalog"
    SERIALIZED_MECHANIC = "serialized_mechanic"
    SERIALIZED_EFFECT = "serialized_effect"
    RUNTIME_MECHANIC = "runtime_mechanic"
    PROJECTILE_ATTACK = "projectile_attack"
    RETAINED_COMBAT_LOCK = "retained_combat_lock"
    TARGETABILITY_STATE = "targetability_state"
    FORCED_OR_SPECIAL_MOVEMENT = "forced_or_special_movement"
    CHARGE_OR_KAMIKAZE = "charge_or_kamikaze"
    SPAWN_HOOK = "spawn_hook"
    BUILDING_ACTIVATION = "building_activation"
    CROWN_TOWER = "crown_tower"
    PENDING_PROJECTILE_RESERVATION = "pending_projectile_reservation"
    OVERRIDDEN_COMBAT_LIFECYCLE = "overridden_combat_lifecycle"


@dataclass(frozen=True)
class UnsupportedCombatState:
    battle_index: int
    entity_id: int | None
    reason: UnsupportedCombatReason


@dataclass(frozen=True)
class EntityCombatMutation:
    """Oracle-visible mutation summary emitted by synchronization."""

    battle_index: int
    entity_id: int
    target_before: int | None
    target_after: int | None
    hp_before: float
    hp_after: float
    attacked: bool
    died: bool


@dataclass(frozen=True)
class StationaryCombatEvents:
    """Stable battle/entity-ordered component mutation summary."""

    mutations: tuple[EntityCombatMutation, ...]

    @property
    def attacked_entity_ids(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (mutation.battle_index, mutation.entity_id)
            for mutation in self.mutations
            if mutation.attacked
        )

    @property
    def death_entity_ids(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (mutation.battle_index, mutation.entity_id)
            for mutation in self.mutations
            if mutation.died
        )


@dataclass
class StationaryCombatProjection:
    """Projected batch plus stable object bindings needed for exact sync."""

    battles: tuple[BattleState, ...]
    state: StationaryCombatState
    entities_by_slot: tuple[tuple[Entity | None, ...], ...]
    unsupported: tuple[UnsupportedCombatState, ...]
    hp_before: torch.Tensor
    alive_before: torch.Tensor
    last_attack_time_before: torch.Tensor
    target_id_before: tuple[tuple[int | None, ...], ...]
    had_attacked_once_field: tuple[tuple[bool, ...], ...]
    synchronized: bool = False

    @property
    def support_mask(self) -> torch.Tensor:
        return stationary_combat_support_mask(self.state)


@dataclass(frozen=True)
class StationaryCombatAdapterResult:
    projection: StationaryCombatProjection
    kernel_result: CombatStepResult
    events: StationaryCombatEvents


def _catalog_card_id(entity: Entity, catalog: TensorCardCatalog) -> int | None:
    name = str(getattr(getattr(entity, "card_stats", None), "name", "") or "")
    card_id = catalog.name_to_id.get(name)
    return card_id if card_id not in {None, 0} else None


def _entity_unsupported_reasons(
    entity: Entity,
    catalog: TensorCardCatalog,
) -> tuple[UnsupportedCombatReason, ...]:
    reasons: list[UnsupportedCombatReason] = []
    if not isinstance(entity, (Troop, Building)):
        return (UnsupportedCombatReason.NON_CHARACTER_OBJECT,)

    card_id = _catalog_card_id(entity, catalog)
    if card_id is None:
        reasons.append(UnsupportedCombatReason.CARD_NOT_IN_CATALOG)
    else:
        if int(catalog.mechanic_count[card_id].item()) != 0:
            reasons.append(UnsupportedCombatReason.SERIALIZED_MECHANIC)
        if int(catalog.effect_count[card_id].item()) != 0:
            reasons.append(UnsupportedCombatReason.SERIALIZED_EFFECT)

    if entity.mechanics:
        reasons.append(UnsupportedCombatReason.RUNTIME_MECHANIC)
    if entity._uses_projectiles():
        reasons.append(UnsupportedCombatReason.PROJECTILE_ATTACK)

    # The kernel stores the current target but does not yet carry the
    # oracle's distinct remembered-lock lane. A death earlier in stable ID
    # order can otherwise require a retarget delay within this same frame.
    if getattr(entity, "_last_combat_target_id", None) is not None:
        reasons.append(UnsupportedCombatReason.RETAINED_COMBAT_LOCK)

    if (
        bool(getattr(entity, "_hidden_building", False))
        or int(getattr(entity, "_stealth_until", 0) or 0) > 0
        or int(entity._death_spawn_target_immunity_elapsed_ms) >= 0
        or bool(getattr(entity, "_river_jump_active", False))
    ):
        reasons.append(UnsupportedCombatReason.TARGETABILITY_STATE)

    if (
        entity.forced_movement_active
        or entity._knockback_target is not None
        or entity._death_spawn_travel_ticks_remaining > 0
        or bool(getattr(entity, "_special_move_active", False))
        or bool(getattr(entity, "_special_move_consumed_tick", False))
        or bool(getattr(entity, "_ground_path_backwards", False))
    ):
        reasons.append(UnsupportedCombatReason.FORCED_OR_SPECIAL_MOVEMENT)

    stats = entity.card_stats
    if (
        bool(getattr(stats, "charge_range", 0))
        or bool(getattr(stats, "kamikaze", False))
        or bool(getattr(entity, "kamikaze_primed", False))
        or float(getattr(entity, "kamikaze_timer_remaining", 0.0) or 0.0) > 0.0
        or bool(getattr(entity, "_force_melee_attack", False))
    ):
        reasons.append(UnsupportedCombatReason.CHARGE_OR_KAMIKAZE)

    if bool(getattr(entity, "_spawn_hook_pending", False)):
        reasons.append(UnsupportedCombatReason.SPAWN_HOOK)

    if isinstance(entity, Building):
        if (
            entity.requires_activation
            or entity.activation_delay_remaining > 1e-9
            or entity.activation_first_hit_delay_remaining > 1e-9
        ):
            reasons.append(UnsupportedCombatReason.BUILDING_ACTIVATION)
        if entity._crown_tower_slot is not None:
            reasons.append(UnsupportedCombatReason.CROWN_TOWER)

    # Subclass lifecycle overrides can introduce callbacks invisible to the
    # dense state even when the serialized mechanic list is empty.
    if (
        type(entity).take_damage is not Entity.take_damage
        or type(entity).on_death is not Entity.on_death
    ):
        reasons.append(UnsupportedCombatReason.OVERRIDDEN_COMBAT_LIFECYCLE)
    return tuple(dict.fromkeys(reasons))


def project_stationary_combat(
    battles: Sequence[BattleState],
    catalog: TensorCardCatalog,
    *,
    capacity: int | None = None,
    device: str | torch.device = "cpu",
) -> StationaryCombatProjection:
    """Project battles without mutating them and classify exact support.

    Slots follow each battle dictionary's encounter order. Combat execution
    itself remains stable-ID ordered inside the tensor kernel, matching the
    Python manager while preserving encounter order for target tie-breaking.
    """

    battle_tuple = tuple(battles)
    required_capacity = max(
        (len(battle.entities) for battle in battle_tuple), default=0
    )
    max_entities = required_capacity if capacity is None else capacity
    if max_entities < required_capacity:
        raise ValueError(
            f"capacity {max_entities} cannot hold {required_capacity} entities"
        )
    max_entities = max(1, max_entities)
    state = StationaryCombatState.empty(len(battle_tuple), max_entities, device=device)
    bindings: list[tuple[Entity | None, ...]] = []
    before_targets: list[tuple[int | None, ...]] = []
    attacked_field_rows: list[tuple[bool, ...]] = []
    unsupported: list[UnsupportedCombatState] = []

    for battle_index, battle in enumerate(battle_tuple):
        entities = tuple(battle.entities.values())
        id_to_slot = {entity.id: slot for slot, entity in enumerate(entities)}
        row: list[Entity | None] = [None] * max_entities
        target_row: list[int | None] = [None] * max_entities
        attacked_field_row = [False] * max_entities
        reservations = getattr(battle, "_projectile_lethal_reservations", None) or set()
        pending_reservation = bool(reservations)
        for slot, entity in enumerate(entities):
            row[slot] = entity
            target_row[slot] = entity.target_id
            attacked_field_row[slot] = hasattr(entity, "_has_attacked_once")
            state.present[battle_index, slot] = True
            state.entity_id[battle_index, slot] = entity.id
            state.encounter_order[battle_index, slot] = slot
            state.kind[battle_index, slot] = entity.entity_kind
            state.owner[battle_index, slot] = entity.player_id
            state.x_units[battle_index, slot] = tiles_to_logic_units(entity.position.x)
            state.y_units[battle_index, slot] = tiles_to_logic_units(entity.position.y)
            state.collision_radius_units[battle_index, slot] = tiles_to_logic_units(
                entity.get_collision_radius()
            )
            state.target_distance_discount_sq_units[battle_index, slot] = int(
                entity._native_target_distance_discount_sq_units
            )
            state.hp[battle_index, slot] = entity.hitpoints
            state.max_hp[battle_index, slot] = entity.max_hitpoints
            state.damage[battle_index, slot] = entity.damage
            state.alive[battle_index, slot] = entity.is_alive
            state.targetable[battle_index, slot] = not bool(
                getattr(entity, "_hidden_building", False)
            )
            state.effect_receivable[battle_index, slot] = not bool(entity.mechanics)
            state.area_effect_receivable[battle_index, slot] = not bool(
                entity.mechanics
            )
            state.airborne[battle_index, slot] = is_airborne_target(entity)
            state.building_target[battle_index, slot] = is_native_building_target(
                entity
            )
            crown_slot = getattr(entity, "_crown_tower_slot", None)
            state.crown_slot[battle_index, slot] = {
                None: -1,
                "left": 0,
                "right": 1,
                "king": 2,
            }.get(crown_slot, -1)
            state.range_units[battle_index, slot] = tiles_to_logic_units(entity.range)
            state.sight_range_units[battle_index, slot] = tiles_to_logic_units(
                entity.sight_range
            )
            state.sight_clip_units[battle_index, slot] = tiles_to_logic_units(
                float(getattr(entity.card_stats, "sight_clip", 0.0) or 0.0)
            )
            state.sight_clip_side_units[battle_index, slot] = tiles_to_logic_units(
                float(getattr(entity.card_stats, "sight_clip_side", 0.0) or 0.0)
            )
            state.can_attack_air[battle_index, slot] = entity._can_attack_air()
            state.can_attack_ground[battle_index, slot] = entity._can_attack_ground()
            state.buildings_only[battle_index, slot] = bool(
                getattr(entity.card_stats, "targets_only_buildings", False)
            )
            state.uses_projectile[battle_index, slot] = bool(
                isinstance(entity, (Troop, Building)) and entity._uses_projectiles()
            )
            state.reserved_lethal[battle_index, slot] = entity.id in reservations
            state.target_slot[battle_index, slot] = (
                id_to_slot.get(entity.target_id, -1)
                if entity.target_id is not None
                else -1
            )
            state.deploy_remaining[battle_index, slot] = entity.deploy_delay_remaining
            state.stunned[battle_index, slot] = entity.is_stunned()
            state.forced_movement[battle_index, slot] = entity.forced_movement_active
            state.combat_enabled[battle_index, slot] = True
            state.tower_active[battle_index, slot] = bool(
                getattr(entity, "_tower_active", True)
            )
            state.attack_cooldown[battle_index, slot] = entity.attack_cooldown
            state.hit_speed_ms[battle_index, slot] = int(
                getattr(entity.card_stats, "hit_speed", 0) or 0
            )
            state.first_hit_ms[battle_index, slot] = int(
                getattr(entity.card_stats, "first_hit_time", 0) or 0
            )
            state.attack_rate_multiplier[battle_index, slot] = (
                entity.get_attack_rate_multiplier()
            )
            state.attack_preload_blocked[battle_index, slot] = (
                entity._attack_preload_blocked
            )
            state.attack_windup_active[battle_index, slot] = (
                entity._attack_windup_active
            )
            state.started_projectile_hit_cycle[battle_index, slot] = (
                entity.has_started_projectile_hit_cycle()
            )
            state.area_radius_units[battle_index, slot] = tiles_to_logic_units(
                entity._attack_area_damage_radius()
            )
            state.self_as_aoe_center[battle_index, slot] = bool(
                getattr(entity.card_stats, "self_as_aoe_center", False)
            )
            state.last_attack_time[battle_index, slot] = entity.last_attack_time
            state.has_attacked_once[battle_index, slot] = bool(
                getattr(entity, "_has_attacked_once", False)
            )

            reasons = list(_entity_unsupported_reasons(entity, catalog))
            if pending_reservation:
                reasons.append(UnsupportedCombatReason.PENDING_PROJECTILE_RESERVATION)
            reasons = list(dict.fromkeys(reasons))
            state.ordinary_combat_supported[battle_index, slot] = not reasons
            unsupported.extend(
                UnsupportedCombatState(battle_index, entity.id, reason)
                for reason in reasons
            )
        bindings.append(tuple(row))
        before_targets.append(tuple(target_row))
        attacked_field_rows.append(tuple(attacked_field_row))

    return StationaryCombatProjection(
        battles=battle_tuple,
        state=state,
        entities_by_slot=tuple(bindings),
        unsupported=tuple(unsupported),
        hp_before=state.hp.clone(),
        alive_before=state.alive.clone(),
        last_attack_time_before=state.last_attack_time.clone(),
        target_id_before=tuple(before_targets),
        had_attacked_once_field=tuple(attacked_field_rows),
    )


def sync_stationary_combat_(
    projection: StationaryCombatProjection,
    result: CombatStepResult,
) -> StationaryCombatEvents:
    """Synchronize a supported kernel frame back into its Python battles."""

    if projection.synchronized:
        raise RuntimeError("stationary combat projection was already synchronized")
    unsupported_rows = torch.nonzero(~projection.support_mask, as_tuple=False).flatten()
    if unsupported_rows.numel():
        raise UnsupportedStationaryCombatError(unsupported_rows.tolist())
    expected = projection.state.present.shape
    for name in (
        "attacked",
        "projectile_launched",
        "damage_received",
        "target_before",
        "target_after",
    ):
        if getattr(result, name).shape != expected:
            raise ValueError(f"combat result {name} has the wrong shape")
    if bool(result.projectile_launched.any().item()):
        raise RuntimeError("supported direct combat unexpectedly launched a projectile")

    state = projection.state
    mutations: list[EntityCombatMutation] = []
    for battle_index, (battle, row) in enumerate(
        zip(projection.battles, projection.entities_by_slot, strict=True)
    ):
        id_by_slot = {
            slot: entity.id for slot, entity in enumerate(row) if entity is not None
        }
        for slot, entity in enumerate(row):
            if entity is None:
                continue
            old_hp = float(projection.hp_before[battle_index, slot].item())
            old_alive = bool(projection.alive_before[battle_index, slot].item())
            old_target = projection.target_id_before[battle_index][slot]
            new_hp = float(state.hp[battle_index, slot].item())
            new_alive = bool(state.alive[battle_index, slot].item())
            target_slot = int(state.target_slot[battle_index, slot].item())
            new_target = id_by_slot.get(target_slot)
            attacked = bool(result.attacked[battle_index, slot].item())

            entity.hitpoints = new_hp
            entity.is_alive = new_alive
            entity.target_id = new_target
            entity.attack_cooldown = float(
                state.attack_cooldown[battle_index, slot].item()
            )
            entity._attack_preload_blocked = bool(
                state.attack_preload_blocked[battle_index, slot].item()
            )
            entity._attack_windup_active = bool(
                state.attack_windup_active[battle_index, slot].item()
            )
            has_attacked_once = bool(state.has_attacked_once[battle_index, slot].item())
            if (
                projection.had_attacked_once_field[battle_index][slot]
                or has_attacked_once
            ):
                entity._has_attacked_once = has_attacked_once
            entity.last_attack_time = float(
                state.last_attack_time[battle_index, slot].item()
            )

            component_clock_advanced = entity.last_attack_time != float(
                projection.last_attack_time_before[battle_index, slot].item()
            )
            active_component = (
                old_alive
                and entity.deploy_delay_remaining <= 0.0
                and (new_alive or component_clock_advanced or attacked)
            )
            if active_component:
                setattr(entity, "_last_combat_target_id", new_target)
                target: Entity | None = (
                    battle.entities.get(new_target) if new_target is not None else None
                )
                if target is not None:
                    entity.face_towards(target.position)
                if isinstance(entity, Troop):
                    if entity.initial_position is None:
                        entity.initial_position = Position(
                            entity.position.x, entity.position.y
                        )
                    entity._movement_target_id = None
                    if (
                        target is not None
                        and not entity.is_stunned()
                        and not entity.is_within_attack_clock_reach(target)
                    ):
                        entity._movement_target_id = target.id
            elif isinstance(entity, Troop) and old_alive:
                # Troop combat clears this lane before its deployment return.
                entity._movement_target_id = None

            if new_hp != old_hp:
                battle.mark_win_conditions_dirty_if_crown(entity)
            if old_alive and not new_alive:
                entity.on_death()
                if isinstance(entity, Building):
                    battle.invalidate_alive_buildings_cache()

            if (
                new_target != old_target
                or new_hp != old_hp
                or attacked
                or new_alive != old_alive
            ):
                mutations.append(
                    EntityCombatMutation(
                        battle_index=battle_index,
                        entity_id=entity.id,
                        target_before=old_target,
                        target_after=new_target,
                        hp_before=old_hp,
                        hp_after=new_hp,
                        attacked=attacked,
                        died=old_alive and not new_alive,
                    )
                )
    mutations.sort(key=lambda mutation: (mutation.battle_index, mutation.entity_id))
    projection.synchronized = True
    return StationaryCombatEvents(tuple(mutations))


def step_supported_stationary_combat_(
    battles: Sequence[BattleState],
    catalog: TensorCardCatalog,
    *,
    dt_seconds: float = 0.05,
    capacity: int | None = None,
) -> StationaryCombatAdapterResult:
    """Project, execute, and synchronize one fully supported combat frame."""

    projection = project_stationary_combat(
        battles, catalog, capacity=capacity, device="cpu"
    )
    kernel_result = step_stationary_combat_(projection.state, dt_seconds)
    events = sync_stationary_combat_(projection, kernel_result)
    return StationaryCombatAdapterResult(projection, kernel_result, events)
