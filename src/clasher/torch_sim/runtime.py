"""Complete-tick orchestration for the currently exact tensor kernel slice.

The individual tensor modules deliberately own narrow component contracts.
This module supplies the battle-manager contract around them: one immutable
preflight, the native phase order, one event stream, dynamic object work, and
spawn-before-remove cleanup.  A row which needs an operation outside those
contracts is left byte-for-byte untouched and reported as unsupported.

The Python adapters in :meth:`from_battles` and :meth:`sync_to_battles` are
boundary/debug tools.  :meth:`step` retains and mutates tensors only.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.kinematics import LOGIC_TICK_SECONDS, tiles_to_logic_units
from clasher.unit_traits import is_airborne_target, is_native_building_target

from .actions import (
    NO_OP_ACTION,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
    TensorIngressResult,
)
from .catalog import TensorCardCatalog
from .combat import (
    CombatStepResult,
    StationaryCombatState,
    stationary_combat_support_mask,
    step_stationary_combat_,
)
from .entity_pool import EntitySelection, TensorEntityPool
from .movement import (
    CollisionBatch,
    CollisionResult,
    accumulate_collision_vectors,
)
from .objects import (
    ObjectPhaseResult,
    TensorObjectCatalog,
    TensorObjectEvents,
    TensorObjectState,
    step_object_phase,
)
from .state import WINNER_DRAW, WINNER_IN_PROGRESS, TensorBattleState
from .status import (
    BuildingLifetimeResult,
    PeriodicDamageSchedule,
    TensorStatusState,
    tick_building_lifetime,
)
from .tick_common import check_win_conditions, tick_players


class TickPhase(IntEnum):
    """Native manager order, including phases which are inert in this slice."""

    CLOCK = 1
    PLAYER = 2
    ACTION_INGRESS = 3
    PROJECTILE_RESERVATION = 4
    COMBAT = 5
    MOVEMENT = 6
    BUILDING_LIFETIME = 7
    STATUS = 8
    OBJECT = 9
    CLEANUP = 10
    WIN = 11


PHASE_ORDER = tuple(TickPhase)


class RuntimeEventOpcode(IntEnum):
    COMBAT_DAMAGE = 1
    PROJECTILE_LAUNCH = 2
    DEPLOYMENT_COMPLETE = 3
    OBJECT_EVENT = 4
    ENTITY_DEATH = 5


@dataclass(frozen=True)
class TensorRuntimeEvents:
    count: torch.Tensor
    phase: torch.Tensor
    opcode: torch.Tensor
    sequence: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor
    amount: torch.Tensor
    payload_opcode: torch.Tensor
    payload_id: torch.Tensor
    payload_count: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        device: torch.device,
    ) -> TensorRuntimeEvents:
        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros((batch_size, capacity), dtype=dtype, device=device)

        return cls(
            count=torch.zeros(batch_size, dtype=torch.int32, device=device),
            phase=zeros(torch.int8),
            opcode=zeros(torch.int16),
            sequence=zeros(torch.int32),
            source_id=zeros(torch.int64),
            target_id=zeros(torch.int64),
            amount=zeros(torch.float64),
            payload_opcode=zeros(torch.int16),
            payload_id=zeros(torch.int32),
            payload_count=zeros(torch.int16),
        )


@dataclass(frozen=True)
class RuntimeTickResult:
    supported: torch.Tensor
    advanced: torch.Tensor
    unsupported_reasons: tuple[str | None, ...]
    phase_order: tuple[TickPhase, ...]
    ingress: TensorIngressResult
    combat: CombatStepResult
    collision: CollisionResult
    building_lifetime: BuildingLifetimeResult
    periodic: PeriodicDamageSchedule
    objects: ObjectPhaseResult
    removed: EntitySelection
    deployment_completed: torch.Tensor
    events: TensorRuntimeEvents


def _clone_combat(state: StationaryCombatState) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            descriptor.name: getattr(state, descriptor.name).clone()
            for descriptor in fields(state)
        }
    )


def _combat_subset(
    state: StationaryCombatState, rows: torch.Tensor
) -> StationaryCombatState:
    return StationaryCombatState(
        **{
            descriptor.name: getattr(state, descriptor.name)
            .index_select(0, rows)
            .clone()
            for descriptor in fields(state)
        }
    )


def _empty_combat_result(state: StationaryCombatState) -> CombatStepResult:
    return CombatStepResult(
        attacked=torch.zeros_like(state.present),
        projectile_launched=torch.zeros_like(state.present),
        damage_received=torch.zeros_like(state.hp),
        target_before=state.target_slot.clone(),
        target_after=state.target_slot.clone(),
    )


def _scatter_combat_(
    destination: StationaryCombatState,
    rows: torch.Tensor,
    source: StationaryCombatState,
) -> None:
    for descriptor in fields(destination):
        getattr(destination, descriptor.name)[rows] = getattr(source, descriptor.name)


def _expand_combat_result(
    state: StationaryCombatState,
    rows: torch.Tensor,
    result: CombatStepResult,
) -> CombatStepResult:
    expanded = _empty_combat_result(state)
    expanded.attacked[rows] = result.attacked
    expanded.projectile_launched[rows] = result.projectile_launched
    expanded.damage_received[rows] = result.damage_received
    expanded.target_before[rows] = result.target_before
    expanded.target_after[rows] = result.target_after
    return expanded


def _object_subset(state: TensorObjectState, rows: torch.Tensor) -> TensorObjectState:
    values: dict[str, object] = {"catalog": state.catalog}
    for descriptor in fields(state):
        if descriptor.name == "catalog":
            continue
        value = getattr(state, descriptor.name)
        values[descriptor.name] = value.index_select(0, rows).clone()
    return TensorObjectState(**values)  # type: ignore[arg-type]


def _scatter_objects_(
    destination: TensorObjectState,
    rows: torch.Tensor,
    source: TensorObjectState,
) -> None:
    for descriptor in fields(destination):
        if descriptor.name == "catalog":
            continue
        getattr(destination, descriptor.name)[rows] = getattr(source, descriptor.name)


def _empty_object_result(state: TensorObjectState) -> ObjectPhaseResult:
    return ObjectPhaseResult(
        events=TensorObjectEvents.empty(
            state.batch_size,
            max(8, state.max_objects * 4),
            state.device,
        ),
        unsupported_batch=torch.zeros(
            state.batch_size, dtype=torch.bool, device=state.device
        ),
        processed_count=torch.zeros(
            state.batch_size, dtype=torch.int32, device=state.device
        ),
    )


def _expand_object_result(
    state: TensorObjectState,
    rows: torch.Tensor,
    result: ObjectPhaseResult,
) -> ObjectPhaseResult:
    expanded = _empty_object_result(state)
    expanded.unsupported_batch[rows] = result.unsupported_batch
    expanded.processed_count[rows] = result.processed_count
    for descriptor in fields(expanded.events):
        getattr(expanded.events, descriptor.name)[rows] = getattr(
            result.events, descriptor.name
        )
    return expanded


def _status_subset(state: TensorStatusState, rows: torch.Tensor) -> TensorStatusState:
    return TensorStatusState(
        **{
            descriptor.name: getattr(state, descriptor.name)
            .index_select(0, rows)
            .clone()
            for descriptor in fields(state)
        }
    )


def _scatter_status_(
    destination: TensorStatusState,
    rows: torch.Tensor,
    source: TensorStatusState,
) -> None:
    for descriptor in fields(destination):
        getattr(destination, descriptor.name)[rows] = getattr(source, descriptor.name)


def _empty_periodic(state: TensorStatusState) -> PeriodicDamageSchedule:
    batch, entity = state.entity_shape
    sources = state.max_periodic_sources
    shape = (batch, entity, sources)
    return PeriodicDamageSchedule(
        source_slots=torch.full(shape, -1, dtype=torch.int64, device=state.device),
        source_ids=torch.zeros(shape, dtype=torch.int64, device=state.device),
        source_kind=torch.zeros(shape, dtype=torch.int64, device=state.device),
        hit_counts=torch.zeros(shape, dtype=torch.int64, device=state.device),
        damage=torch.zeros(shape, dtype=torch.float64, device=state.device),
        affects_hidden=torch.zeros(shape, dtype=torch.bool, device=state.device),
        valid=torch.zeros(shape, dtype=torch.bool, device=state.device),
    )


def _expand_periodic(
    state: TensorStatusState,
    rows: torch.Tensor,
    result: PeriodicDamageSchedule,
) -> PeriodicDamageSchedule:
    expanded = _empty_periodic(state)
    for descriptor in fields(expanded):
        getattr(expanded, descriptor.name)[rows] = getattr(result, descriptor.name)
    return expanded


class TensorTickRuntime:
    """Retained batched runtime for exact stationary, mechanic-free frames."""

    def __init__(
        self,
        *,
        core: TensorBattleState,
        pool: TensorEntityPool,
        combat: StationaryCombatState,
        status: TensorStatusState,
        objects: TensorObjectState,
        action_state: TensorActionState,
        action_kernel: TensorActionKernel,
        lifetime_ms: torch.Tensor,
        lifetime_elapsed: torch.Tensor,
        lifetime_decay_work: torch.Tensor,
        lifetime_tick_carry_ms: torch.Tensor,
        mass_milliunits: torch.Tensor,
        facing_x_units: torch.Tensor,
        facing_y_units: torch.Tensor,
        hp_is_int: torch.Tensor,
        static_supported: torch.Tensor,
        static_reasons: tuple[str | None, ...],
        battle_identities: tuple[int, ...],
    ) -> None:
        self.core = core
        self.pool = pool
        self.combat = combat
        self.status = status
        self.objects = objects
        self.action_state = action_state
        self.action_kernel = action_kernel
        self.lifetime_ms = lifetime_ms
        self.lifetime_elapsed = lifetime_elapsed
        self.lifetime_decay_work = lifetime_decay_work
        self.lifetime_tick_carry_ms = lifetime_tick_carry_ms
        self.mass_milliunits = mass_milliunits
        self.facing_x_units = facing_x_units
        self.facing_y_units = facing_y_units
        self.hp_is_int = hp_is_int
        self.static_supported = static_supported
        self.static_reasons = static_reasons
        self.battle_identities = battle_identities

    @property
    def device(self) -> torch.device:
        return self.core.device

    @property
    def batch_size(self) -> int:
        return int(self.core.batch_size)

    @classmethod
    def from_battles(
        cls,
        battles: Sequence[BattleState],
        *,
        max_entities: int | None = None,
        max_objects: int = 16,
        device: str | torch.device = "cpu",
    ) -> TensorTickRuntime:
        """Compile Python oracle rows at the explicit synchronization boundary."""

        if not battles:
            raise ValueError("at least one battle is required")
        torch_device = torch.device(device)
        capacity = max(
            1,
            int(max_entities or max(len(battle.entities) for battle in battles)),
        )
        if capacity < max(len(battle.entities) for battle in battles):
            raise ValueError("max_entities is smaller than an input battle")

        core = TensorBattleState.from_battles(
            battles, device=torch_device, max_entities=capacity
        )
        id_sequences = [tuple(sorted(battle.entities)) for battle in battles]
        pool = TensorEntityPool.from_id_sequences(
            id_sequences,
            capacity=capacity,
            next_entity_ids=[battle.next_entity_id for battle in battles],
            device=torch_device,
        )
        combat = StationaryCombatState.empty(
            len(battles), capacity, device=torch_device
        )
        status = TensorStatusState.empty(len(battles), capacity, device=torch_device)
        shape = (len(battles), capacity)
        lifetime_ms = torch.zeros(shape, dtype=torch.int64, device=torch_device)
        lifetime_elapsed = torch.zeros(shape, dtype=torch.float64, device=torch_device)
        lifetime_decay_work = torch.zeros(shape, dtype=torch.int64, device=torch_device)
        lifetime_tick_carry_ms = torch.zeros(
            shape, dtype=torch.float64, device=torch_device
        )
        mass_milliunits = torch.full(
            shape, 5_000, dtype=torch.int64, device=torch_device
        )
        facing_x_units = torch.zeros(shape, dtype=torch.int64, device=torch_device)
        facing_y_units = torch.zeros(shape, dtype=torch.int64, device=torch_device)
        hp_is_int = torch.zeros(shape, dtype=torch.bool, device=torch_device)

        reasons: list[str | None] = []
        for battle_index, battle in enumerate(battles):
            reason = cls._static_reason(battle)
            reasons.append(reason)
            ordered = sorted(battle.entities.values(), key=lambda entity: entity.id)
            id_to_slot = {entity.id: slot for slot, entity in enumerate(ordered)}
            for slot, entity in enumerate(ordered):
                cls._load_entity(
                    combat,
                    status,
                    lifetime_ms,
                    lifetime_elapsed,
                    lifetime_decay_work,
                    lifetime_tick_carry_ms,
                    mass_milliunits,
                    facing_x_units,
                    facing_y_units,
                    hp_is_int,
                    battle_index,
                    slot,
                    entity,
                    id_to_slot,
                )

        player_cards = {
            str(name)
            for battle in battles
            for player in battle.players
            for name in (*player.deck, *player.hand, *player.cycle_queue)
            if name is not None
        }
        card_catalog = TensorCardCatalog.compile(
            battles[0].card_loader, player_cards, device=torch_device
        )
        action_catalog = TensorActionCatalog.compile(card_catalog)
        action_state = TensorActionState.from_battles(battles, action_catalog)
        action_kernel = TensorActionKernel(action_catalog)
        empty_objects = TensorObjectState.create(
            TensorObjectCatalog.compile([], device=torch_device),
            [[] for _ in battles],
            max_objects=max_objects,
        )
        static_supported = torch.tensor(
            [reason is None for reason in reasons],
            dtype=torch.bool,
            device=torch_device,
        )
        return cls(
            core=core,
            pool=pool,
            combat=combat,
            status=status,
            objects=empty_objects,
            action_state=action_state,
            action_kernel=action_kernel,
            lifetime_ms=lifetime_ms,
            lifetime_elapsed=lifetime_elapsed,
            lifetime_decay_work=lifetime_decay_work,
            lifetime_tick_carry_ms=lifetime_tick_carry_ms,
            mass_milliunits=mass_milliunits,
            facing_x_units=facing_x_units,
            facing_y_units=facing_y_units,
            hp_is_int=hp_is_int,
            static_supported=static_supported,
            static_reasons=tuple(reasons),
            battle_identities=tuple(id(battle) for battle in battles),
        )

    @staticmethod
    def _static_reason(battle: BattleState) -> str | None:
        if battle.dt != LOGIC_TICK_SECONDS:
            return "heterogeneous tick duration is not compiled"
        if battle._pending_spell_casts:
            return "pending spell casts require Python command resolution"
        if battle._pending_projectile_impacts:
            return "pending projectile impacts are not tensor-plumbed"
        if tuple(battle.entities) != tuple(sorted(battle.entities)):
            return "entity dictionary is not in ascending allocation order"
        for entity in battle.entities.values():
            if not isinstance(entity, (Troop, Building)):
                return "non-character object requires a tensor object adapter"
            if entity.mechanics:
                return "character mechanics are outside stationary ordinary combat"
            if isinstance(entity, Troop) and abs(float(entity.speed)) > 1e-15:
                return "natural movement route state is not compiled"
            if entity.forced_movement_active or entity._knockback_target is not None:
                return "forced movement is not compiled"
            if entity._death_spawn_travel_ticks_remaining > 0:
                return "death-spawn travel is not compiled"
            if entity._death_spawn_target_immunity_elapsed_ms >= 0:
                return "death-spawn target immunity is not compiled"
            if getattr(entity, "_native_avoidance", 0) != 0:
                return "retained avoidance is not compiled"
            if entity._movement_vector_count != 0:
                return "queued external movement is not compiled"
            if entity.stun_timer > 0 or entity.freeze_expiry_time > battle.time:
                return "active stun or freeze requires status-to-combat feedback"
            if entity.slow_timer > 0 or entity.haste_timer > 0:
                return "active slow or haste requires status-to-combat feedback"
            if entity._slow_effects or entity._haste_effects:
                return "status source lists are not compiled by this adapter"
            if entity._periodic_damage_effects:
                return "periodic damage event application is not orchestrated"
            if getattr(entity, "_hidden_building", False):
                return "hidden target state is not compiled"
            if getattr(entity.card_stats, "death_spawn_character", None):
                return "serialized death spawn payload is not compiled"
            if getattr(entity, "activation_delay_remaining", 0.0) > 1e-9:
                return "building activation transition is not compiled"
            if getattr(entity, "activation_first_hit_delay_remaining", 0.0) > 1e-9:
                return "building first-hit activation delay is not compiled"
        return None

    @staticmethod
    def _load_entity(
        combat: StationaryCombatState,
        status: TensorStatusState,
        lifetime_ms: torch.Tensor,
        lifetime_elapsed: torch.Tensor,
        lifetime_decay_work: torch.Tensor,
        lifetime_tick_carry_ms: torch.Tensor,
        mass_milliunits: torch.Tensor,
        facing_x_units: torch.Tensor,
        facing_y_units: torch.Tensor,
        hp_is_int: torch.Tensor,
        battle_index: int,
        slot: int,
        entity: Entity,
        id_to_slot: dict[int, int],
    ) -> None:
        combat.present[battle_index, slot] = True
        combat.entity_id[battle_index, slot] = entity.id
        combat.encounter_order[battle_index, slot] = slot
        combat.kind[battle_index, slot] = entity.entity_kind
        combat.owner[battle_index, slot] = entity.player_id
        combat.x_units[battle_index, slot] = tiles_to_logic_units(entity.position.x)
        combat.y_units[battle_index, slot] = tiles_to_logic_units(entity.position.y)
        combat.collision_radius_units[battle_index, slot] = tiles_to_logic_units(
            entity.get_collision_radius()
        )
        combat.target_distance_discount_sq_units[battle_index, slot] = int(
            entity._native_target_distance_discount_sq_units
        )
        combat.hp[battle_index, slot] = entity.hitpoints
        hp_is_int[battle_index, slot] = type(entity.hitpoints) is int
        combat.max_hp[battle_index, slot] = entity.max_hitpoints
        combat.damage[battle_index, slot] = entity.damage
        combat.alive[battle_index, slot] = entity.is_alive
        combat.targetable[battle_index, slot] = entity.is_targetable_by(
            1 - entity.player_id
        )
        combat.effect_receivable[battle_index, slot] = entity.can_receive_effect()
        combat.area_effect_receivable[battle_index, slot] = (
            entity.can_receive_area_damage()
        )
        combat.airborne[battle_index, slot] = is_airborne_target(entity)
        combat.building_target[battle_index, slot] = is_native_building_target(entity)
        crown_slot = getattr(entity, "_crown_tower_slot", None)
        combat.crown_slot[battle_index, slot] = {
            None: -1,
            "left": 0,
            "right": 1,
            "king": 2,
        }.get(crown_slot, -1)
        combat.range_units[battle_index, slot] = tiles_to_logic_units(entity.range)
        combat.sight_range_units[battle_index, slot] = tiles_to_logic_units(
            entity.sight_range
        )
        combat.sight_clip_units[battle_index, slot] = tiles_to_logic_units(
            float(getattr(entity.card_stats, "sight_clip", 0.0) or 0.0)
        )
        combat.sight_clip_side_units[battle_index, slot] = tiles_to_logic_units(
            float(getattr(entity.card_stats, "sight_clip_side", 0.0) or 0.0)
        )
        combat.can_attack_air[battle_index, slot] = entity._can_attack_air()
        combat.can_attack_ground[battle_index, slot] = entity._can_attack_ground()
        combat.buildings_only[battle_index, slot] = bool(
            getattr(entity.card_stats, "targets_only_buildings", False)
        )
        combat.uses_projectile[battle_index, slot] = bool(
            entity._uses_projectiles()  # type: ignore[attr-defined]
        )
        combat.target_slot[battle_index, slot] = (
            -1 if entity.target_id is None else id_to_slot.get(entity.target_id, -1)
        )
        combat.deploy_remaining[battle_index, slot] = entity.deploy_delay_remaining
        combat.stunned[battle_index, slot] = entity.is_stunned()
        combat.forced_movement[battle_index, slot] = entity.forced_movement_active
        combat.combat_enabled[battle_index, slot] = True
        combat.tower_active[battle_index, slot] = bool(
            getattr(entity, "_tower_active", True)
        )
        combat.attack_cooldown[battle_index, slot] = entity.attack_cooldown
        combat.hit_speed_ms[battle_index, slot] = int(entity.card_stats.hit_speed or 0)
        combat.first_hit_ms[battle_index, slot] = int(
            entity.card_stats.first_hit_time or 0
        )
        combat.attack_rate_multiplier[battle_index, slot] = (
            entity.get_attack_rate_multiplier()
        )
        combat.attack_preload_blocked[battle_index, slot] = (
            entity._attack_preload_blocked
        )
        combat.attack_windup_active[battle_index, slot] = entity._attack_windup_active
        combat.started_projectile_hit_cycle[battle_index, slot] = (
            entity.has_started_projectile_hit_cycle()
        )
        combat.area_radius_units[battle_index, slot] = tiles_to_logic_units(
            entity._attack_area_damage_radius()
        )
        combat.self_as_aoe_center[battle_index, slot] = bool(
            getattr(entity.card_stats, "self_as_aoe_center", False)
        )
        combat.last_attack_time[battle_index, slot] = entity.last_attack_time
        combat.has_attacked_once[battle_index, slot] = bool(
            getattr(entity, "_has_attacked_once", False)
        )
        mass_milliunits[battle_index, slot] = round(
            (entity.get_unit_mass() if isinstance(entity, Troop) else 5.0) * 1_000
        )
        facing_x_units[battle_index, slot] = entity._facing_x_units
        facing_y_units[battle_index, slot] = entity._facing_y_units
        status.stun_timer[battle_index, slot] = entity.stun_timer
        status.freeze_expiry_time[battle_index, slot] = entity.freeze_expiry_time
        status.slow_timer[battle_index, slot] = entity.slow_timer
        status.slow_multiplier[battle_index, slot] = entity.slow_multiplier
        status.haste_timer[battle_index, slot] = entity.haste_timer
        if isinstance(entity, Building):
            lifetime_ms[battle_index, slot] = int(
                getattr(entity.card_stats, "lifetime_ms", 0) or 0
            )
            lifetime_elapsed[battle_index, slot] = entity.lifetime_elapsed
            lifetime_decay_work[battle_index, slot] = entity.lifetime_decay_work
            lifetime_tick_carry_ms[battle_index, slot] = entity.lifetime_tick_carry_ms

    def _collision(self, combat: StationaryCombatState) -> CollisionResult:
        batch = CollisionBatch(
            position_units=torch.stack((combat.x_units, combat.y_units), dim=-1),
            active=combat.present & combat.alive,
            entity_id=combat.entity_id,
            entity_kind=combat.kind,
            player_id=combat.owner,
            collision_radius_units=combat.collision_radius_units,
            mass_milliunits=self.mass_milliunits,
            air_collision=combat.airborne,
            stunned=combat.stunned,
            in_transit=torch.zeros_like(combat.present),
            river_jump_active=torch.zeros_like(combat.present),
            death_spawn_travel=torch.zeros_like(combat.present),
            mega_knight_airborne=torch.zeros_like(combat.present),
        )
        return accumulate_collision_vectors(batch)

    def _dynamic_support(
        self, action_ids: torch.Tensor
    ) -> tuple[torch.Tensor, tuple[str | None, ...]]:
        supported = self.static_supported.clone() & ~self.core.game_over
        reasons = list(self.static_reasons)
        no_op = (action_ids == NO_OP_ACTION).all(dim=1)
        for row in torch.nonzero(supported & ~no_op, as_tuple=False).flatten().tolist():
            reasons[row] = "runtime deployment materialization is not integrated"
        supported &= no_op
        supported &= stationary_combat_support_mask(self.combat)
        supported &= ~self.objects.unsupported_batches()
        if not bool(supported.any().item()):
            return supported, tuple(reasons)

        probe = _clone_combat(self.combat)
        probe.present &= supported[:, None]
        combat_result = step_stationary_combat_(probe, LOGIC_TICK_SECONDS)
        launched = combat_result.projectile_launched.any(dim=1)
        crown_damage = (
            (combat_result.damage_received > 0.0) & (probe.crown_slot >= 0)
        ).any(dim=1)
        collision = self._collision(probe)
        contact = (collision.contact_count > 0).any(dim=1)
        for row in (
            torch.nonzero(supported & launched, as_tuple=False).flatten().tolist()
        ):
            reasons[row] = "combat projectile materialization is not integrated"
        for row in (
            torch.nonzero(supported & crown_damage, as_tuple=False).flatten().tolist()
        ):
            reasons[row] = "Crown damage activation/win side effects are not integrated"
        for row in (
            torch.nonzero(supported & contact, as_tuple=False).flatten().tolist()
        ):
            reasons[row] = "sequential collision movement is not integrated"
        supported &= ~launched & ~crown_damage & ~contact & collision.supported_batch
        return supported, tuple(reasons)

    def preflight(
        self,
        action_ids: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, tuple[str | None, ...]]:
        """Return exact per-row support without mutating retained state."""

        actions = (
            torch.full(
                (self.batch_size, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=self.device,
            )
            if action_ids is None
            else action_ids.to(device=self.device, dtype=torch.int64)
        )
        if actions.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        return self._dynamic_support(actions)

    def step(self, action_ids: torch.Tensor | None = None) -> RuntimeTickResult:
        """Advance one complete 50 ms frame for every preflight-supported row."""

        if action_ids is None:
            action_ids = torch.full(
                (self.batch_size, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=self.device,
            )
        else:
            action_ids = action_ids.to(device=self.device, dtype=torch.int64)
        if action_ids.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")

        supported, reasons = self._dynamic_support(action_ids)
        active = supported & ~self.core.game_over
        advanced = active.clone()

        # Clock -> phase globals -> player regeneration/refill.
        self.core.time.add_(torch.where(active, self.core.dt, 0.0))
        self.core.tick.add_(active.to(torch.int64))
        self.core.double_elixir |= active & (
            self.core.time >= self.core.double_elixir_start_time
        )
        self.core.overtime |= active & (self.core.time >= self.core.overtime_start_time)
        self.core.triple_elixir |= active & (
            self.core.time >= self.core.triple_elixir_start_time
        )
        tick_players(self.core, active)

        # Action ingress uses the exact generalized action decoder. This
        # supported slice accepts only no-ops; commands which allocate entities
        # are rejected during preflight before these retained tensors mutate.
        ingress = self.action_kernel.ingress(self.action_state, action_ids)
        self.action_state.elixir.copy_(self.core.elixir)

        # Projectile reservations are a start-of-frame snapshot. No tensor
        # projectiles are attached to character targets in this slice, so the
        # preflighted exact value is the all-false field loaded in combat.
        rows = torch.nonzero(active, as_tuple=False).flatten()
        combat_result = _empty_combat_result(self.combat)
        if rows.numel():
            combat_subset = _combat_subset(self.combat, rows)
            subset_result = step_stationary_combat_(combat_subset, LOGIC_TICK_SECONDS)
            _scatter_combat_(self.combat, rows, combat_subset)
            combat_result = _expand_combat_result(self.combat, rows, subset_result)
            self.hp_is_int[rows] &= ~(subset_result.damage_received > 0.0)

        # Target observation updates the retained raw native facing vector
        # before stun/attack clock decisions in the scalar component.
        target_slots = self.combat.target_slot.clamp(min=0)
        target_x = self.combat.x_units.gather(1, target_slots)
        target_y = self.combat.y_units.gather(1, target_slots)
        observed = (
            active[:, None]
            & self.combat.present
            & self.combat.alive
            & (self.combat.kind == 0)
            & (self.combat.deploy_remaining <= 0.0)
            & (self.combat.target_slot >= 0)
        )
        delta_x = target_x - self.combat.x_units
        delta_y = target_y - self.combat.y_units
        nonzero = observed & ((delta_x != 0) | (delta_y != 0))
        self.facing_x_units.copy_(torch.where(nonzero, delta_x, self.facing_x_units))
        self.facing_y_units.copy_(torch.where(nonzero, delta_y, self.facing_y_units))

        collision = self._collision(self.combat)

        building_mask = (
            active[:, None]
            & self.combat.present
            & self.combat.alive
            & (self.combat.kind == 1)
        )
        lifetime = tick_building_lifetime(
            hitpoints=self.combat.hp,
            max_hitpoints=self.combat.max_hp,
            lifetime_ms=self.lifetime_ms,
            lifetime_elapsed=self.lifetime_elapsed,
            lifetime_decay_work=self.lifetime_decay_work,
            lifetime_tick_carry_ms=self.lifetime_tick_carry_ms,
            is_alive=self.combat.alive,
            dt=LOGIC_TICK_SECONDS,
            component_mask=building_mask,
        )
        self.combat.hp.copy_(lifetime.hitpoints)
        self.combat.alive.copy_(lifetime.is_alive)
        self.hp_is_int &= ~((lifetime.hitpoint_loss > 0) & (lifetime.hitpoints <= 0.0))
        self.lifetime_elapsed.copy_(lifetime.lifetime_elapsed)
        self.lifetime_decay_work.copy_(lifetime.lifetime_decay_work)
        self.lifetime_tick_carry_ms.copy_(lifetime.lifetime_tick_carry_ms)

        periodic = _empty_periodic(self.status)
        if rows.numel():
            status_subset = _status_subset(self.status, rows)
            subset_periodic = status_subset.tick(
                LOGIC_TICK_SECONDS,
                component_mask=(
                    self.combat.present.index_select(0, rows)
                    & self.combat.alive.index_select(0, rows)
                ),
            )
            _scatter_status_(self.status, rows, status_subset)
            periodic = _expand_periodic(self.status, rows, subset_periodic)

        object_result = _empty_object_result(self.objects)
        if rows.numel():
            object_subset = _object_subset(self.objects, rows)
            subset_objects = step_object_phase(object_subset)
            _scatter_objects_(self.objects, rows, object_subset)
            object_result = _expand_object_result(self.objects, rows, subset_objects)

        # LogicCharacter::tick shares the dynamically growing object phase.
        deploying = (
            active[:, None]
            & self.combat.present
            & self.combat.alive
            & (self.combat.deploy_remaining > 0.0)
        )
        previous_deploy = self.combat.deploy_remaining.clone()
        self.combat.deploy_remaining.copy_(
            torch.where(
                deploying,
                torch.clamp(previous_deploy - LOGIC_TICK_SECONDS, min=0.0),
                previous_deploy,
            )
        )
        deployment_completed = (
            deploying & (previous_deploy > 0.0) & (self.combat.deploy_remaining <= 1e-9)
        )
        self.core.entity_deploy_delay.copy_(self.combat.deploy_remaining)
        self.core.entity_placement_pending &= ~deployment_completed
        self.core.entity_spawn_hook_pending &= ~deployment_completed
        self.core.entity_spawn_hook_fired |= deployment_completed

        # Publish Crown HP before spawn-before-remove cleanup and win checks.
        for tower_slot in range(3):
            tower = self.combat.present & (self.combat.crown_slot == tower_slot)
            if bool(tower.any().item()):
                hp = torch.where(tower, self.combat.hp, 0.0).sum(dim=1)
                owner_zero = torch.where(
                    tower & (self.combat.owner == 0), self.combat.hp, 0.0
                ).sum(dim=1)
                owner_one = torch.where(
                    tower & (self.combat.owner == 1), self.combat.hp, 0.0
                ).sum(dim=1)
                del hp
                self.core.tower_hp[:, 0, tower_slot] = torch.where(
                    active, owner_zero, self.core.tower_hp[:, 0, tower_slot]
                )
                self.core.tower_hp[:, 1, tower_slot] = torch.where(
                    active, owner_one, self.core.tower_hp[:, 1, tower_slot]
                )

        dead = active[:, None] & self.pool.active & ~self.combat.alive
        removed = self.pool.cleanup(dead)
        self.combat.present &= self.pool.active
        self.core.entity_active.copy_(self.pool.active & self.combat.alive)
        self.core.entity_id.copy_(self.pool.entity_id)
        self.status.expire_periodic_for_dead(dead)
        check_win_conditions(self.core, active)

        events = self._events(
            combat_result,
            object_result,
            removed,
            deployment_completed,
        )
        return RuntimeTickResult(
            supported=supported,
            advanced=advanced,
            unsupported_reasons=reasons,
            phase_order=PHASE_ORDER,
            ingress=ingress,
            combat=combat_result,
            collision=collision,
            building_lifetime=lifetime,
            periodic=periodic,
            objects=object_result,
            removed=removed,
            deployment_completed=deployment_completed,
            events=events,
        )

    def _events(
        self,
        combat: CombatStepResult,
        objects: ObjectPhaseResult,
        removed: EntitySelection,
        deployment_completed: torch.Tensor,
    ) -> TensorRuntimeEvents:
        capacity = max(16, self.combat.max_entities * 4 + self.objects.max_objects * 4)
        events = TensorRuntimeEvents.empty(self.batch_size, capacity, self.device)

        def emit(
            mask: torch.Tensor,
            phase: TickPhase,
            opcode: RuntimeEventOpcode,
            *,
            source_id: torch.Tensor,
            target_id: torch.Tensor,
            amount: torch.Tensor,
            payload_opcode: torch.Tensor | None = None,
            payload_id: torch.Tensor | None = None,
            payload_count: torch.Tensor | None = None,
        ) -> None:
            batches = torch.nonzero(mask, as_tuple=False).flatten()
            if batches.numel() == 0:
                return
            slots = events.count[batches].to(torch.int64)
            events.phase[batches, slots] = int(phase)
            events.opcode[batches, slots] = int(opcode)
            events.sequence[batches, slots] = slots.to(torch.int32)
            events.source_id[batches, slots] = source_id[batches]
            events.target_id[batches, slots] = target_id[batches]
            events.amount[batches, slots] = amount[batches]
            if payload_opcode is not None:
                events.payload_opcode[batches, slots] = payload_opcode[batches]
            if payload_id is not None:
                events.payload_id[batches, slots] = payload_id[batches]
            if payload_count is not None:
                events.payload_count[batches, slots] = payload_count[batches]
            events.count[batches] += 1

        zeros_id = torch.zeros(self.batch_size, dtype=torch.int64, device=self.device)
        zeros_amount = torch.zeros(
            self.batch_size, dtype=torch.float64, device=self.device
        )
        for slot in range(self.combat.max_entities):
            target_id = self.combat.entity_id[:, slot]
            emit(
                combat.damage_received[:, slot] > 0.0,
                TickPhase.COMBAT,
                RuntimeEventOpcode.COMBAT_DAMAGE,
                source_id=zeros_id,
                target_id=target_id,
                amount=combat.damage_received[:, slot],
            )
            emit(
                combat.projectile_launched[:, slot],
                TickPhase.COMBAT,
                RuntimeEventOpcode.PROJECTILE_LAUNCH,
                source_id=target_id,
                target_id=zeros_id,
                amount=zeros_amount,
            )
            emit(
                deployment_completed[:, slot],
                TickPhase.OBJECT,
                RuntimeEventOpcode.DEPLOYMENT_COMPLETE,
                source_id=target_id,
                target_id=zeros_id,
                amount=zeros_amount,
            )

        for slot in range(objects.events.opcode.shape[1]):
            valid = slot < objects.events.count
            emit(
                valid,
                TickPhase.OBJECT,
                RuntimeEventOpcode.OBJECT_EVENT,
                source_id=objects.events.source_id[:, slot],
                target_id=zeros_id,
                amount=objects.events.amount[:, slot],
                payload_opcode=objects.events.opcode[:, slot],
                payload_id=objects.events.payload_id[:, slot],
                payload_count=objects.events.payload_count[:, slot],
            )

        for rank in range(removed.valid.shape[1]):
            emit(
                removed.valid[:, rank],
                TickPhase.CLEANUP,
                RuntimeEventOpcode.ENTITY_DEATH,
                source_id=removed.entity_ids[:, rank],
                target_id=zeros_id,
                amount=zeros_amount,
            )
        return events

    def sync_to_battles(self, battles: Sequence[BattleState]) -> None:
        """Publish retained tensor state into the same oracle boundary rows."""

        if len(battles) != self.batch_size:
            raise ValueError("battle count does not match tensor batch")
        if tuple(id(battle) for battle in battles) != self.battle_identities:
            raise ValueError("runtime can only synchronize its original battle rows")

        for batch_index, battle in enumerate(battles):
            # Unsupported/game-over rows have not advanced. Publishing their
            # retained initial values could still change scalar kinds, so skip.
            if int(self.core.tick[batch_index].item()) == battle.tick:
                continue
            battle.time = float(self.core.time[batch_index].item())
            battle.tick = int(self.core.tick[batch_index].item())
            battle.double_elixir = bool(self.core.double_elixir[batch_index].item())
            battle.triple_elixir = bool(self.core.triple_elixir[batch_index].item())
            battle.overtime = bool(self.core.overtime[batch_index].item())
            battle.sudden_death = bool(self.core.sudden_death[batch_index].item())
            battle.game_over = bool(self.core.game_over[batch_index].item())
            winner = int(self.core.winner[batch_index].item())
            battle.winner = (
                None if winner in {WINNER_IN_PROGRESS, WINNER_DRAW} else winner
            )
            battle._sudden_death_crowns = (
                int(self.core.sudden_death_crowns[batch_index, 0].item()),
                int(self.core.sudden_death_crowns[batch_index, 1].item()),
            )
            for player_id, player in enumerate(battle.players):
                player.elixir = float(self.core.elixir[batch_index, player_id].item())
                player.max_elixir = float(
                    self.core.max_elixir[batch_index, player_id].item()
                )
                player.next_card_refill_cooldown_ms = int(
                    self.core.refill_cooldown_ms[batch_index, player_id].item()
                )
                player.hand = [
                    None if value == 0 else self.core.card_names[value]
                    for value in self.core.hand[batch_index, player_id].tolist()
                ]
                length = int(
                    self.core.cycle_queue_length[batch_index, player_id].item()
                )
                player.cycle_queue = deque(
                    self.core.card_names[value]
                    for value in self.core.cycle_queue[
                        batch_index, player_id, :length
                    ].tolist()
                )
                # Crown damage is excluded by preflight. Preserve the oracle's
                # existing scalar kinds instead of round-tripping untouched
                # integer tower values through float64 tensors.

            existing = dict(battle.entities)
            for slot in range(self.combat.max_entities):
                entity_id = int(self.combat.entity_id[batch_index, slot].item())
                if entity_id == 0 or entity_id not in existing:
                    continue
                entity = existing[entity_id]
                entity.position.x = (
                    int(self.combat.x_units[batch_index, slot]) / 1_000.0
                )
                entity.position.y = (
                    int(self.combat.y_units[batch_index, slot]) / 1_000.0
                )
                raw_hp = float(self.combat.hp[batch_index, slot].item())
                tensor_hp: float | int = (
                    int(raw_hp)
                    if bool(self.hp_is_int[batch_index, slot].item())
                    else raw_hp
                )
                if tensor_hp != entity.hitpoints:
                    entity.hitpoints = tensor_hp
                entity.is_alive = bool(self.combat.alive[batch_index, slot].item())
                entity.attack_cooldown = float(
                    self.combat.attack_cooldown[batch_index, slot].item()
                )
                entity.last_attack_time = float(
                    self.combat.last_attack_time[batch_index, slot].item()
                )
                entity._attack_preload_blocked = bool(
                    self.combat.attack_preload_blocked[batch_index, slot].item()
                )
                entity._attack_windup_active = bool(
                    self.combat.attack_windup_active[batch_index, slot].item()
                )
                entity._has_attacked_once = bool(
                    self.combat.has_attacked_once[batch_index, slot].item()
                )
                entity._facing_x_units = int(
                    self.facing_x_units[batch_index, slot].item()
                )
                entity._facing_y_units = int(
                    self.facing_y_units[batch_index, slot].item()
                )
                target_slot = int(self.combat.target_slot[batch_index, slot].item())
                entity.target_id = (
                    None
                    if target_slot < 0
                    else int(self.combat.entity_id[batch_index, target_slot].item())
                )
                entity.deploy_delay_remaining = float(
                    self.combat.deploy_remaining[batch_index, slot].item()
                )
                entity.placement_pending = bool(
                    self.core.entity_placement_pending[batch_index, slot].item()
                )
                entity._spawn_hook_pending = bool(
                    self.core.entity_spawn_hook_pending[batch_index, slot].item()
                )
                entity._spawn_hook_fired = bool(
                    self.core.entity_spawn_hook_fired[batch_index, slot].item()
                )
                entity.stun_timer = float(
                    self.status.stun_timer[batch_index, slot].item()
                )
                entity.freeze_expiry_time = float(
                    self.status.freeze_expiry_time[batch_index, slot].item()
                )
                entity.slow_timer = float(
                    self.status.slow_timer[batch_index, slot].item()
                )
                entity.slow_multiplier = float(
                    self.status.slow_multiplier[batch_index, slot].item()
                )
                entity.haste_timer = float(
                    self.status.haste_timer[batch_index, slot].item()
                )
                if isinstance(entity, Building):
                    entity.lifetime_elapsed = float(
                        self.lifetime_elapsed[batch_index, slot].item()
                    )
                    entity.lifetime_decay_work = int(
                        self.lifetime_decay_work[batch_index, slot].item()
                    )
                    entity.lifetime_tick_carry_ms = float(
                        self.lifetime_tick_carry_ms[batch_index, slot].item()
                    )

            live_ids = {
                int(value)
                for value in self.pool.entity_id[batch_index][
                    self.pool.active[batch_index]
                ].tolist()
            }
            for entity_id in tuple(battle.entities):
                if entity_id not in live_ids:
                    del battle.entities[entity_id]
            battle.next_entity_id = int(self.pool.next_entity_id[batch_index].item())
            battle._win_conditions_dirty = False
            if battle.fast_path:
                battle._refresh_fast_path_caches(trust_target_cache_dirty=False)
