"""Whole-row transactional resident PyTorch battle engine.

Boundary construction may inspect Python battles.  Once constructed, action
ingress and every tick phase operate on retained tensors only.  A tick is run
on an isolated speculative engine and published per row only when deployment,
combat, movement, status, objects, cleanup, and win resolution all remain
supported.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields, replace
from enum import IntEnum
from functools import lru_cache
from typing import Any, cast

import torch

from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.kinematics import LOGIC_TICK_SECONDS
from clasher.native_tilemap import (
    HALF_TILE_LOGIC_UNITS,
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_ROWS,
    STANDARD_PATH_WIDTH,
)
from clasher.spells import (
    SPELL_REGISTRY,
    GraveyardSpell,
    RollingProjectileSpell,
    RoyalDeliverySpell,
    SpawnProjectileSpell,
)

from .actions import NO_OP_ACTION, TensorActionCatalog
from .catalog import EFFECT_OPCODE, MECHANIC_OPCODE, TensorCardCatalog
from .combat import (
    CombatStepResult,
    StationaryCombatState,
    projectile_lethal_reservations,
    step_stationary_combat_,
)
from .combat_adapter import project_stationary_combat
from .combat_clock_transitions import (
    TensorCombatClockPlanes,
    apply_forced_movement_interrupt_,
    apply_stun_interrupt_,
    initialize_spawned_attack_clocks_,
)
from .deployment import TensorCommandMaterializer, TensorDeploymentCatalog
from .entity_pool import EntitySelection
from .mechanic_dispatcher import (
    MechanicTickInputs,
    TensorMechanicDispatcher,
)
from .movement_adapter import TensorMovementAdapter
from .object_adapter import RuntimeObjectKind
from .objects import _integer_sqrt
from .projectile_bridge import (
    BridgePayloadKind,
    TensorResidentProjectileSpellBridge,
)
from .resident_action_router import (
    TensorResidentActionRouter,
    TensorResidentActionRouterResult,
)
from .resident_continuous_areas import (
    ContinuousAreaStepResult,
    TensorResidentContinuousAreas,
)
from .resident_graveyard import GraveyardStepResult, TensorResidentGraveyards
from .resident_pathing import (
    TensorResidentPathCache,
    plan_standard_routes,
)
from .resident_pending_spells import (
    PendingSpellResolveResult,
    TensorResidentPendingSpells,
)
from .resident_periodic_spawner import (
    TensorPeriodicSpawnerCatalog,
    TensorPeriodicSpawnerResult,
    TensorPeriodicSpawnerRuntimeState,
    step_runtime_periodic_spawners_,
)
from .resident_rolling_spell import (
    TensorResidentRollingSpells,
    TensorRollingDueHandoff,
    TensorRollingProjectileState,
    TensorRollingSpellCatalog,
    TensorRollingStepResult,
    TensorRollingTargets,
)
from .resident_royal_delivery import (
    RoyalDeliveryStepResult,
    TensorResidentRoyalDelivery,
)
from .resident_spell_ingress import (
    TensorResidentSpellActionIngress,
    TensorResidentSpellIngressResult,
)
from .resident_terminal_pipeline import (
    ResidentTerminalPipelineResult,
    TensorResidentTerminalPipeline,
    TensorTerminalPipelineTargets,
)
from .resident_timed_terminal_payloads import TensorTimedTerminalCatalog
from .resident_tornado import TensorResidentTornadoes, TornadoStepResult
from .runtime_deployment import (
    TensorRuntimeDeployment,
    TensorRuntimeDeploymentResult,
)
from .runtime_mechanics import TensorRuntimeMechanics
from .runtime_movement import RuntimeMovementResult, step_runtime_movement_
from .runtime_objects import (
    RuntimeObjectPhaseResult,
    TensorRuntimeObjectPhase,
)
from .runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)
from .runtime_status import (
    RuntimeStatusPhaseResult,
    TensorRuntimeStatusPhase,
    step_runtime_status_phase_,
)
from .special_movement import SpecialMovementOpcode
from .status import TensorStatusState
from .tick_common import check_win_conditions, tick_players

RESIDENT_PHASE_ORDER = tuple(TickPhase)
RESIDENT_UNSUPPORTED_MECHANIC_OPCODES = {
    opcode: name for name, opcode in MECHANIC_OPCODE.items()
}
RESIDENT_UNSUPPORTED_EFFECT_OPCODES = {
    opcode: name for name, opcode in EFFECT_OPCODE.items()
}
RESIDENT_DISPATCH_MECHANIC_OPCODES = frozenset(
    MECHANIC_OPCODE[name]
    for name in (
        "BanditDash",
        "SerializedOnHitBuff",
        "SkeletonKingSoulCollector",
    )
)


class _ResidentCatalogLoader(CardDataLoader):
    """Loader-local serialized child definitions used by one resident catalog."""

    def __init__(self, source: CardDataLoader) -> None:
        # Avoid reparsing gamedata: definitions are immutable prototypes and
        # nested compatibility cards are owned only by this overlay.
        self.data_file = source.data_file
        self._card_definitions = dict(source.load_card_definitions())
        self._cards = {}
        self._synthetic_names: set[str] = set()

    def add_character(self, name: str, data: dict[str, Any], rarity: str) -> None:
        existing = self._cards.get(name)
        if existing is not None and name in self._synthetic_names:
            existing_data = existing.summon_character_data or {}
            if existing_data != data:
                raise ValueError(
                    f"conflicting serialized deployment payload for {name!r}"
                )
            return
        stats = troop_from_character_data(
            name,
            data,
            elixir=0,
            rarity=rarity,
        )
        self._cards[name] = stats
        self._card_definitions[name] = stats.card_definition
        self._synthetic_names.add(name)


def _resident_deployment_catalog_closure(
    source: CardDataLoader,
    initial_names: set[str],
) -> tuple[_ResidentCatalogLoader, tuple[str, ...]]:
    """Compile the recursive primary/secondary deployment character closure."""

    overlay = _ResidentCatalogLoader(source)
    discovered = set(initial_names)
    pending = set(initial_names)
    while pending:
        parent_name = min(pending)
        pending.remove(parent_name)
        parent = overlay.get_card(parent_name)
        payloads: list[tuple[dict[str, Any], str, str]] = []
        if parent is not None:
            payloads.extend(
                (payload, str(parent.rarity or "Common"), "")
                for payload in (
                    parent.summon_character_data,
                    parent.summon_character_second_data,
                )
                if isinstance(payload, dict)
            )
        spell = SPELL_REGISTRY.get(parent_name)
        if isinstance(spell, SpawnProjectileSpell) and isinstance(
            spell.spawn_character_data, dict
        ):
            payloads.append(
                (
                    spell.spawn_character_data,
                    "Common",
                    str(spell.spawn_character),
                )
            )
        if isinstance(spell, GraveyardSpell) and isinstance(spell.skeleton_data, dict):
            payloads.append(
                (
                    spell.skeleton_data,
                    str(spell.skeleton_data.get("rarity", "Common")),
                    str(spell.spawn_character),
                )
            )
        if isinstance(spell, RollingProjectileSpell) and isinstance(
            spell.spawn_character_data, dict
        ):
            payloads.append(
                (
                    spell.spawn_character_data,
                    str(spell.spawn_character_data.get("rarity", "Common")),
                    str(spell.spawn_character),
                )
            )
        if isinstance(spell, RoyalDeliverySpell) and isinstance(
            spell.spawn_character_data, dict
        ):
            payloads.append(
                (
                    spell.spawn_character_data,
                    str(spell.spawn_character_data.get("rarity", "Common")),
                    str(spell.spawn_character),
                )
            )
        definition = overlay.load_card_definitions().get(parent_name)
        if definition is not None:
            for mechanic in definition.mechanics:
                unit_data = getattr(mechanic, "unit_data", None)
                child_name = str(getattr(mechanic, "unit_name", "") or "")
                if isinstance(unit_data, dict) and child_name:
                    payloads.append(
                        (
                            unit_data,
                            str(unit_data.get("rarity", "Common")),
                            child_name,
                        )
                    )
        for payload, parent_rarity, default_child_name in payloads:
            child_name = str(payload.get("name", "") or default_child_name)
            if not child_name or child_name == parent_name:
                continue
            rarity = str(payload.get("rarity", parent_rarity))
            overlay.add_character(child_name, payload, rarity)
            if child_name not in discovered:
                discovered.add(child_name)
                pending.add(child_name)
    return overlay, tuple(sorted(discovered))


@dataclass(frozen=True)
class ResidentPreflight:
    supported: torch.Tensor
    reason_code: torch.Tensor
    mechanic_opcode_present: torch.Tensor
    effect_opcode_present: torch.Tensor


@dataclass(frozen=True)
class ResidentPreflightDiagnostics:
    """Human-readable boundary view; never used by the resident step path."""

    supported: tuple[bool, ...]
    reasons: tuple[str | None, ...]
    unsupported_mechanic_opcodes: tuple[tuple[int, ...], ...]
    unsupported_effect_opcodes: tuple[tuple[int, ...], ...]


class ResidentUnsupportedReason(IntEnum):
    NONE = 0
    DEVICE = 1
    UNKNOWN_CHARACTER = 2
    ACTIVE_MECHANIC = 3
    ACTIVE_EFFECT = 4
    PROJECTILE_COMBAT = 5
    DEATH_SPAWN = 6
    OBJECT_PHASE = 7
    CHAMPION_ACTION = 8
    SPELL_ACTION = 9
    ACTION_MECHANIC = 10
    ACTION_EFFECT = 11
    MIXED_PAYLOAD = 12


_REASON_TEXT = {
    ResidentUnsupportedReason.DEVICE: "resident exact phases require CPU or CUDA",
    ResidentUnsupportedReason.UNKNOWN_CHARACTER: (
        "active character card is absent from the catalog"
    ),
    ResidentUnsupportedReason.ACTIVE_MECHANIC: "unsupported active mechanic opcode",
    ResidentUnsupportedReason.ACTIVE_EFFECT: "unsupported active effect opcode",
    ResidentUnsupportedReason.PROJECTILE_COMBAT: (
        "resident combat projectile launch is not integrated"
    ),
    ResidentUnsupportedReason.DEATH_SPAWN: (
        "resident character death spawn is not integrated"
    ),
    ResidentUnsupportedReason.OBJECT_PHASE: "runtime object phase is unsupported",
    ResidentUnsupportedReason.CHAMPION_ACTION: (
        "champion action is not resident-integrated"
    ),
    ResidentUnsupportedReason.SPELL_ACTION: "spell action is not resident-integrated",
    ResidentUnsupportedReason.ACTION_MECHANIC: "unsupported action mechanic opcode",
    ResidentUnsupportedReason.ACTION_EFFECT: "unsupported action effect opcode",
    ResidentUnsupportedReason.MIXED_PAYLOAD: "mixed deployment payload is unsupported",
}


@dataclass(frozen=True)
class ResidentTickResult:
    preflight: ResidentPreflight
    committed: torch.Tensor
    deployment: TensorRuntimeDeploymentResult
    spell_ingress: TensorResidentSpellIngressResult
    action_router: TensorResidentActionRouterResult
    pending_spells: PendingSpellResolveResult
    combat: CombatStepResult
    movement: RuntimeMovementResult
    status: RuntimeStatusPhaseResult
    objects: RuntimeObjectPhaseResult
    continuous_areas: ContinuousAreaStepResult | None
    graveyards: GraveyardStepResult | None
    tornadoes: TornadoStepResult | None
    rolling_spells: TensorRollingStepResult | None
    royal_delivery: RoyalDeliveryStepResult | None
    periodic_spawner: TensorPeriodicSpawnerResult | None
    terminal: ResidentTerminalPipelineResult | None
    cleanup: EntitySelection
    deployment_completed: torch.Tensor
    phase_order: tuple[TickPhase, ...]


@dataclass
class _MovementRuntimeView:
    """Tensor-only compatibility view required by runtime_movement."""

    core: object
    combat: StationaryCombatState
    facing_x_units: torch.Tensor
    facing_y_units: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.combat.batch_size)

    @property
    def device(self) -> torch.device:
        return self.combat.device


def _clone_tensor_dataclass(value: object) -> object:
    copied: dict[str, object] = {}
    for descriptor in fields(value):  # type: ignore[arg-type]
        item = getattr(value, descriptor.name)
        copied[descriptor.name] = (
            item.clone() if isinstance(item, torch.Tensor) else item
        )
    return type(value)(**copied)


def _copy_rows_(destination: object, source: object, rows: torch.Tensor) -> None:
    batch = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim > 0
            and left.shape[0] == batch
            and left.shape == right.shape
        ):
            left[rows] = right[rows]


def _gather_slots(value: torch.Tensor, order: torch.Tensor) -> torch.Tensor:
    index = order.reshape(
        *order.shape,
        *((1,) * (value.ndim - 2)),
    ).expand(*order.shape, *value.shape[2:])
    return value.gather(1, index)


def _copy_slots_(
    destination: object,
    source: object,
    physical_to_sorted: torch.Tensor,
) -> None:
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim >= 2
            and left.shape[:2] == physical_to_sorted.shape
            and left.shape == right.shape
        ):
            left.copy_(_gather_slots(right, physical_to_sorted))


def _removed_entities(
    before: EntitySelection,
    runtime: TensorBattleRuntime,
) -> EntitySelection:
    matches = (
        (before.entity_ids[:, :, None] == runtime.battle.entity_id[:, None, :])
        & runtime.entity_pool.active[:, None, :]
        & (before.entity_ids[:, :, None] > 0)
    )
    removed = before.valid & ~matches.any(dim=2)
    return EntitySelection(
        slots=torch.where(removed, before.slots, torch.full_like(before.slots, -1)),
        entity_ids=torch.where(
            removed, before.entity_ids, torch.zeros_like(before.entity_ids)
        ),
        valid=removed,
    )


def _sorted_slot_clone(value: object, order: torch.Tensor) -> object:
    cloned = _clone_tensor_dataclass(value)
    for descriptor in fields(cloned):  # type: ignore[arg-type]
        item = getattr(cloned, descriptor.name)
        if (
            isinstance(item, torch.Tensor)
            and item.ndim >= 2
            and item.shape[:2] == order.shape
        ):
            item.copy_(_gather_slots(item, order))
    return cloned


def _clone_object_phase(phase: TensorRuntimeObjectPhase) -> TensorRuntimeObjectPhase:
    cloned = copy.copy(phase)
    for descriptor in fields(phase):
        item = getattr(phase, descriptor.name)
        if descriptor.name == "objects":
            cloned_objects = copy.copy(phase.objects)
            for object_descriptor in fields(item):
                object_item = getattr(item, object_descriptor.name)
                if isinstance(object_item, torch.Tensor):
                    setattr(cloned_objects, object_descriptor.name, object_item.clone())
            cloned.objects = cloned_objects
        elif isinstance(item, torch.Tensor):
            setattr(cloned, descriptor.name, item.clone())
    return cloned


def _clone_terminal_pipeline(
    pipeline: TensorResidentTerminalPipeline,
) -> TensorResidentTerminalPipeline:
    state = copy.copy(pipeline.state)
    state.objects = copy.copy(pipeline.state.objects)
    for descriptor in fields(pipeline.state.objects):
        item = getattr(pipeline.state.objects, descriptor.name)
        if isinstance(item, torch.Tensor):
            setattr(state.objects, descriptor.name, item.clone())
    for descriptor in fields(pipeline.state):
        if descriptor.name == "objects":
            continue
        item = getattr(pipeline.state, descriptor.name)
        if isinstance(item, torch.Tensor):
            setattr(state, descriptor.name, item.clone())
    return TensorResidentTerminalPipeline(
        pipeline.catalog,
        state,
        pipeline.targets.clone(),
    )


def _copy_terminal_pipeline_rows_(
    destination: TensorResidentTerminalPipeline,
    source: TensorResidentTerminalPipeline,
    rows: torch.Tensor,
) -> None:
    _copy_rows_(destination.state.objects, source.state.objects, rows)
    for name in (
        "operation_row",
        "facing_x_units",
        "facing_y_units",
        "freeze_expiry_time",
    ):
        getattr(destination.state, name)[rows] = getattr(source.state, name)[rows]
    batch_size = int(rows.shape[0])
    for descriptor in fields(destination.targets):
        left = getattr(destination.targets, descriptor.name)
        right = getattr(source.targets, descriptor.name)
        if left.ndim > 0 and left.shape[0] == batch_size:
            left[rows] = right[rows]
        elif left.ndim > 1 and left.shape[1] == batch_size:
            left[:, rows] = right[:, rows]


def _clone_projectile_bridge(
    bridge: TensorResidentProjectileSpellBridge,
) -> TensorResidentProjectileSpellBridge:
    cloned = copy.copy(bridge)
    for descriptor in fields(bridge):
        item = getattr(bridge, descriptor.name)
        if isinstance(item, torch.Tensor):
            setattr(cloned, descriptor.name, item.clone())
    return cloned


def _copy_projectile_bridge_rows_(
    destination: TensorResidentProjectileSpellBridge,
    source: TensorResidentProjectileSpellBridge,
    rows: torch.Tensor,
) -> None:
    batch_size = destination.blueprint_for_slot.shape[0]
    blueprint_indices = source.blueprint_for_slot[rows].flatten()
    for descriptor in fields(destination):
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if not isinstance(left, torch.Tensor) or not isinstance(right, torch.Tensor):
            continue
        if left.ndim > 0 and left.shape[0] == batch_size:
            left[rows] = right[rows]
        elif descriptor.name.startswith("blueprint_") and left.ndim == 1:
            left[blueprint_indices] = right[blueprint_indices]


def _copy_dispatcher_rows_(
    destination: TensorMechanicDispatcher,
    source: TensorMechanicDispatcher,
    rows: torch.Tensor,
) -> None:
    for left, right in (
        (destination.combat_world, source.combat_world),
        (destination.damage_ramp, source.damage_ramp),
        (destination.dash, source.dash),
        (destination.leap, source.leap),
        (destination.hook, source.hook),
    ):
        _copy_rows_(left, right, rows)
    for descriptor in fields(destination.passive):
        if descriptor.name == "entity_id":
            continue
        left = getattr(destination.passive, descriptor.name)
        right = getattr(source.passive, descriptor.name)
        left[rows] = right[rows]
    destination.passive.entity_id.copy_(destination.runtime.battle.entity_id)
    for name in (
        "special_triggered",
        "forced_movement",
        "knockback_target_units",
        "knockback_velocity_work",
        "initialized_entity_id",
        "multiple_target_ids",
        "multiple_target_valid",
        "underground_active",
    ):
        getattr(destination, name)[rows] = getattr(source, name)[rows]


def _copy_object_blueprint_rows_(
    destination: TensorRuntimeObjectPhase,
    source: TensorRuntimeObjectPhase,
    blueprint_indices: torch.Tensor,
) -> None:
    for descriptor in fields(destination):
        if not descriptor.name.startswith("blueprint_"):
            continue
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and left.ndim == 1:
            left[blueprint_indices] = right[blueprint_indices]


def _empty_combat_result(state: StationaryCombatState) -> CombatStepResult:
    return CombatStepResult(
        attacked=torch.zeros_like(state.present),
        projectile_launched=torch.zeros_like(state.present),
        damage_received=torch.zeros_like(state.hp),
        target_before=state.target_slot.clone(),
        target_after=state.target_slot.clone(),
    )


@lru_cache(maxsize=4)
def _resident_lane_candidates(
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    candidate_x = torch.arange(STANDARD_PATH_WIDTH, device=device).repeat_interleave(
        STANDARD_PATH_HEIGHT
    )
    candidate_y = torch.arange(STANDARD_PATH_HEIGHT, device=device).repeat(
        STANDARD_PATH_WIDTH
    )
    candidate_lane = torch.tensor(
        [
            ord(STANDARD_PATH_ROWS[y][x]) - ord("0")
            for x in range(STANDARD_PATH_WIDTH)
            for y in range(STANDARD_PATH_HEIGHT)
        ],
        dtype=torch.int64,
        device=device,
    )
    return candidate_x, candidate_y, candidate_lane


def _resident_native_lane_ids(position_units: torch.Tensor) -> torch.Tensor:
    """Port the spawn-time nearest path-ID scan without Python entities."""

    device = position_units.device
    source_x = torch.div(
        position_units[..., 0], HALF_TILE_LOGIC_UNITS, rounding_mode="trunc"
    )
    source_y = torch.div(
        position_units[..., 1], HALF_TILE_LOGIC_UNITS, rounding_mode="trunc"
    )
    candidate_x, candidate_y, candidate_lane = _resident_lane_candidates(device)
    distance = (candidate_x - source_x[..., None]) ** 2 + (
        candidate_y - source_y[..., None]
    ) ** 2
    sentinel = torch.iinfo(torch.int64).max
    selected = torch.argmin(torch.where(candidate_lane > 0, distance, sentinel), dim=-1)
    return candidate_lane[selected]


class TensorResidentEngine:
    """Retained complete-tick owner with atomic row publication."""

    def __init__(
        self,
        *,
        runtime: TensorBattleRuntime,
        deployment: TensorRuntimeDeployment,
        mechanics: TensorRuntimeMechanics,
        dispatcher: TensorMechanicDispatcher,
        movement: TensorMovementAdapter,
        path_cache: TensorResidentPathCache,
        status: TensorRuntimeStatusPhase,
        objects: TensorRuntimeObjectPhase,
        continuous_areas: TensorResidentContinuousAreas,
        continuous_effect_deadline_seconds: torch.Tensor,
        graveyards: TensorResidentGraveyards,
        tornadoes: TensorResidentTornadoes,
        rolling_spells: TensorResidentRollingSpells,
        royal_delivery: TensorResidentRoyalDelivery,
        periodic_catalog: TensorPeriodicSpawnerCatalog,
        periodic_state: TensorPeriodicSpawnerRuntimeState,
        terminal_pipeline: TensorResidentTerminalPipeline,
        projectile_bridge: TensorResidentProjectileSpellBridge,
        spell_ingress: TensorResidentSpellActionIngress,
        action_router: TensorResidentActionRouter,
        pending_spells: TensorResidentPendingSpells,
        pending_projectile_max_duration_ms: torch.Tensor,
        projectile_duration_ms: torch.Tensor,
        combat: StationaryCombatState,
        combat_target_entity_id: torch.Tensor,
        uses_projectile: torch.Tensor,
        can_attack_air: torch.Tensor,
        can_attack_ground: torch.Tensor,
        death_spawn: torch.Tensor,
        area_radius_units: torch.Tensor,
        self_as_aoe_center: torch.Tensor,
        sight_clip_units: torch.Tensor,
        sight_clip_side_units: torch.Tensor,
        first_hit_ms: torch.Tensor,
        jump_height: torch.Tensor,
        jump_speed_units: torch.Tensor,
        charge_range_units: torch.Tensor,
        movement_stop_after_ms: torch.Tensor,
        movement_wait_ms: torch.Tensor,
        movement_base_speed_units: torch.Tensor,
        facing_x_units: torch.Tensor,
        facing_y_units: torch.Tensor,
    ) -> None:
        self.runtime = runtime
        self.deployment = deployment
        self.mechanics = mechanics
        self.dispatcher = dispatcher
        self.movement = movement
        self.path_cache = path_cache
        self.status = status
        self.objects = objects
        self.continuous_areas = continuous_areas
        self.continuous_effect_deadline_seconds = continuous_effect_deadline_seconds
        self.graveyards = graveyards
        self.tornadoes = tornadoes
        self.rolling_spells = rolling_spells
        self.royal_delivery = royal_delivery
        self.periodic_catalog = periodic_catalog
        self.periodic_state = periodic_state
        self.terminal_pipeline = terminal_pipeline
        self.projectile_bridge = projectile_bridge
        self.spell_ingress = spell_ingress
        self.action_router = action_router
        self.pending_spells = pending_spells
        self.pending_projectile_max_duration_ms = pending_projectile_max_duration_ms
        self.projectile_duration_ms = projectile_duration_ms
        self.combat = combat
        self.combat_target_entity_id = combat_target_entity_id
        self.uses_projectile = uses_projectile
        self.can_attack_air = can_attack_air
        self.can_attack_ground = can_attack_ground
        self.death_spawn = death_spawn
        self.area_radius_units = area_radius_units
        self.self_as_aoe_center = self_as_aoe_center
        self.sight_clip_units = sight_clip_units
        self.sight_clip_side_units = sight_clip_side_units
        self.first_hit_ms = first_hit_ms
        self.jump_height = jump_height
        self.jump_speed_units = jump_speed_units
        self.charge_range_units = charge_range_units
        self.movement_stop_after_ms = movement_stop_after_ms
        self.movement_wait_ms = movement_wait_ms
        self.movement_base_speed_units = movement_base_speed_units
        self.facing_x_units = facing_x_units
        self.facing_y_units = facing_y_units

    @property
    def device(self) -> torch.device:
        return self.runtime.device

    @property
    def batch_size(self) -> int:
        return int(self.runtime.batch_size)

    @classmethod
    def from_battles(
        cls,
        battles: Sequence[BattleState],
        *,
        device: str | torch.device = "cpu",
        max_entities: int = 128,
        max_objects: int = 128,
        event_capacity: int = 512,
        catalog: TensorCardCatalog | None = None,
    ) -> TensorResidentEngine:
        if not battles:
            raise ValueError("at least one battle is required")
        names = {
            str(name)
            for battle in battles
            for player in battle.players
            for name in (*player.deck, *player.hand, *player.cycle_queue)
            if name is not None
        } | {
            str(getattr(entity.card_stats, "name", ""))
            for battle in battles
            for entity in battle.entities.values()
            if getattr(entity.card_stats, "name", "") not in {"Tower", "KingTower"}
        }
        if catalog is not None:
            names.update(catalog.names[1:])
        catalog_loader, closure_names = _resident_deployment_catalog_closure(
            battles[0].card_loader,
            names,
        )
        cards = (
            catalog
            if catalog is not None and set(closure_names).issubset(catalog.name_to_id)
            else TensorCardCatalog.compile(catalog_loader, closure_names, device=device)
        )
        runtime = TensorBattleRuntime.from_battles(
            battles,
            device=device,
            max_entities=max_entities,
            event_capacity=event_capacity,
            catalog=cards,
        )
        action_catalog = TensorActionCatalog.compile(cards)
        deployment_catalog = TensorDeploymentCatalog.compile(catalog_loader, cards)
        deployment = TensorRuntimeDeployment(
            action_catalog, TensorCommandMaterializer(deployment_catalog)
        )
        deployment.prepare_runtime(runtime)
        mechanic_battles = list(battles)
        mechanic_boundary = copy.copy(battles[0])
        mechanic_boundary.card_loader = catalog_loader
        mechanic_battles[0] = mechanic_boundary
        dispatcher = TensorMechanicDispatcher.from_battles(runtime, mechanic_battles)
        mechanics = dispatcher.mechanics
        status = TensorRuntimeStatusPhase.from_battles(runtime, battles)
        objects = TensorRuntimeObjectPhase.from_battles(
            runtime, battles, max_objects=max_objects
        )
        area_capacity = min(max_objects, 8)
        continuous_areas = TensorResidentContinuousAreas.from_battles(
            runtime, battles, capacity=area_capacity
        )
        continuous_duration_ms = (
            continuous_areas.catalog.duration_ms.detach().cpu().tolist()
        )
        continuous_interval_ms = (
            continuous_areas.catalog.effect_interval_ms.detach().cpu().tolist()
        )
        maximum_effect_scans = max(
            (
                (int(duration) + max(1, int(interval)) - 1) // max(1, int(interval))
                for duration, interval in zip(
                    continuous_duration_ms,
                    continuous_interval_ms,
                    strict=True,
                )
            ),
            default=1,
        )
        continuous_effect_deadline_seconds = torch.zeros(
            (continuous_areas.catalog.size, max(1, maximum_effect_scans)),
            dtype=torch.float64,
            device=runtime.device,
        )
        deadline_rows: list[list[float]] = []
        for interval_ms in continuous_interval_ms:
            interval_seconds = max(1, int(interval_ms)) / 1_000.0
            deadline = interval_seconds
            deadline_row: list[float] = []
            for _ in range(continuous_effect_deadline_seconds.shape[1]):
                deadline_row.append(deadline)
                deadline += interval_seconds
            deadline_rows.append(deadline_row)
        continuous_effect_deadline_seconds.copy_(
            torch.tensor(
                deadline_rows,
                dtype=torch.float64,
                device=runtime.device,
            )
        )
        graveyards = TensorResidentGraveyards.from_battles(
            runtime, battles, capacity=area_capacity
        )
        tornadoes = TensorResidentTornadoes.from_battles(
            runtime, battles, capacity=area_capacity
        )
        royal_delivery = TensorResidentRoyalDelivery.from_battles(
            runtime,
            mechanic_battles,
            capacity=area_capacity,
        )
        rolling_catalog = TensorRollingSpellCatalog.compile(
            runtime, mechanic_battles[0]
        )
        rolling_spells = TensorResidentRollingSpells(
            rolling_catalog,
            TensorRollingProjectileState.empty(
                runtime.batch_size,
                area_capacity,
                runtime.max_entities,
                device=runtime.device,
            ),
            TensorRollingTargets.from_battles(
                runtime,
                mechanic_battles,
                rolling_catalog,
            ),
        )
        periodic_catalog = TensorPeriodicSpawnerCatalog.compile(
            catalog_loader,
            cards,
            list(cards.names[1:]),
        )
        if periodic_catalog.cards is not cards:
            raise ValueError("resident periodic catalog expanded after runtime compile")
        periodic_state = TensorPeriodicSpawnerRuntimeState.zeros(runtime)
        periodic_operation = periodic_catalog.source_row_by_card[
            runtime.card_catalog_index[runtime.battle.entity_card].clamp_min(0)
        ]
        periodic_active = (
            runtime.entity_pool.active
            & runtime.battle.entity_active
            & (periodic_operation >= 0)
            & ((runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1))
        )
        periodic_state.source_entity_id.copy_(
            torch.where(
                periodic_active,
                runtime.battle.entity_id,
                periodic_state.source_entity_id,
            )
        )
        periodic_state.operation_row.copy_(
            torch.where(
                periodic_active,
                periodic_operation,
                periodic_state.operation_row,
            )
        )
        periodic_state.time_since_spawn_ms.copy_(
            dispatcher.passive.periodic_time_since_spawn_ms
        )
        periodic_state.spawns_created.copy_(dispatcher.passive.periodic_spawns_created)
        periodic_state.pending_units.copy_(dispatcher.passive.periodic_pending_units)
        periodic_state.time_since_unit_spawn_ms.copy_(
            dispatcher.passive.periodic_time_since_unit_spawn_ms
        )
        periodic_state.current_wave_spawned.copy_(
            dispatcher.passive.periodic_current_wave_spawned
        )
        terminal_catalog = TensorTimedTerminalCatalog.compile(
            catalog_loader,
            cards,
            list(cards.names[1:]),
        )
        if terminal_catalog.terminal.cards is not cards:
            raise ValueError("resident terminal catalog expanded after runtime compile")
        terminal_state = terminal_catalog.create_state(
            runtime.batch_size,
            max_objects,
        )
        terminal_targets = TensorTerminalPipelineTargets.from_battles(
            runtime,
            battles,
            terminal_catalog,
        )
        terminal_pipeline = TensorResidentTerminalPipeline(
            terminal_catalog,
            terminal_state,
            terminal_targets,
        )
        projectile_bridge = TensorResidentProjectileSpellBridge.from_battles(
            runtime, objects, mechanic_battles
        )
        spell_payload_supported_core = (
            projectile_bridge.catalog.supported
            | continuous_areas.catalog.supported
            | graveyards.catalog.supported
            | tornadoes.catalog.supported
            | rolling_spells.catalog.supported
            | royal_delivery.catalog.supported
        )
        spell_ingress = TensorResidentSpellActionIngress(
            runtime,
            objects,
            projectile_bridge,
            cards,
            episode_supported_core=spell_payload_supported_core,
        )
        pending_spells = TensorResidentPendingSpells.from_battles(
            runtime,
            battles,
            cards,
        )
        action_router = TensorResidentActionRouter(
            runtime,
            objects,
            projectile_bridge,
            deployment,
            spell_ingress,
            pending_spells,
            spell_payload_supported_core,
        )
        pending_projectile_max_duration_ms = torch.zeros(
            (runtime.batch_size, runtime.max_entities),
            dtype=torch.int64,
            device=runtime.device,
        )
        projectile_duration_ms = torch.zeros(
            (runtime.batch_size, objects.objects.max_objects),
            dtype=torch.int64,
            device=runtime.device,
        )
        for row, battle in enumerate(battles):
            for slot, entity in enumerate(
                sorted(battle.entities.values(), key=lambda candidate: candidate.id)
            ):
                pending_projectile_max_duration_ms[row, slot] = int(
                    getattr(entity, "_pending_projectile_max_duration_ms", 0) or 0
                )
            by_id = battle.entities
            for object_slot in range(objects.objects.max_objects):
                if not bool(objects.objects.allocated[row, object_slot].item()):
                    continue
                object_id = int(objects.objects.object_id[row, object_slot].item())
                obj = by_id.get(object_id)
                duration = getattr(obj, "_native_pending_damage_duration_ms", None)
                if callable(duration):
                    projectile_duration_ms[row, object_slot] = int(duration())
                blueprint = int(objects.objects.blueprint_id[row, object_slot].item())
                projectile_bridge.blueprint_tracks_target[blueprint] = bool(
                    getattr(obj, "reserves_pending_damage", False)
                )
                projectile_bridge.blueprint_actual_damage[blueprint] = float(
                    objects.objects.amount[row, object_slot].item()
                )
            if (
                objects.unsupported_reasons[row]
                == "live target tracking is not represented"
            ):
                allocated = objects.objects.allocated[row]
                object_cards = runtime.battle.entity_card[row][
                    runtime.battle.entity_kind[row] == 2
                ]
                supported_objects = projectile_bridge.catalog.supported[
                    object_cards
                ] & (
                    projectile_bridge.catalog.kind[object_cards]
                    == BridgePayloadKind.COMBAT_PROJECTILE
                )
                if int(allocated.sum().item()) == int(
                    supported_objects.sum().item()
                ) and bool(supported_objects.all().item()):
                    objects.static_supported[row] = True
                    objects.objects.feature_mask[row, allocated] = 0
                    reasons = list(objects.unsupported_reasons)
                    reasons[row] = None
                    objects.unsupported_reasons = tuple(reasons)
        projection = project_stationary_combat(
            battles,
            cards,
            capacity=max_entities,
            device=device,
        )
        combat = projection.state
        combat_target_entity_id = torch.full(
            (runtime.batch_size, max_entities),
            -1,
            dtype=torch.int64,
            device=runtime.device,
        )
        for row, battle in enumerate(battles):
            for slot, entity in enumerate(
                sorted(battle.entities.values(), key=lambda candidate: candidate.id)
            ):
                target_id = getattr(entity, "target_id", None)
                combat_target_entity_id[row, slot] = (
                    -1 if target_id is None else int(target_id)
                )
        movement = TensorMovementAdapter.from_battles(
            battles, device=device, max_entities=max_entities
        )
        if movement.route_capacity < 128:
            expanded_routes = torch.zeros(
                (runtime.batch_size, max_entities, 128, 2),
                dtype=torch.int64,
                device=runtime.device,
            )
            expanded_routes[:, :, : movement.route_capacity] = movement.route_cells
            movement.route_cells = expanded_routes
        path_cache = TensorResidentPathCache.create(
            capacity=2_048,
            route_capacity=movement.route_capacity,
            device=runtime.device,
        )

        size = len(cards.names)
        uses_projectile = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        can_attack_air = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        can_attack_ground = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        death_spawn = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        area_radius = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        self_center = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        sight_clip = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        sight_clip_side = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        first_hit = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        jump_height = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        jump_speed = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        charge_range = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        movement_stop_after = torch.zeros(
            size, dtype=torch.int64, device=runtime.device
        )
        movement_wait = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        movement_base_speed = torch.zeros(
            size, dtype=torch.int64, device=runtime.device
        )
        for card_id, name in enumerate(cards.names[1:], start=1):
            stats = catalog_loader.get_card(name)
            if stats is None:
                continue
            uses_projectile[card_id] = bool(
                getattr(stats, "projectile_speed", 0)
                or getattr(stats, "projectile_data", None)
            )
            target_type = str(getattr(stats, "target_type", "") or "")
            can_attack_air[card_id] = target_type in {
                "TID_TARGETS_AIR",
                "TID_TARGETS_AIR_AND_GROUND",
            } or bool(getattr(stats, "attacks_air", False))
            can_attack_ground[card_id] = target_type in {
                "TID_TARGETS_GROUND",
                "TID_TARGETS_AIR_AND_GROUND",
                "TID_TARGETS_BUILDINGS",
                "TID_TARGETS_GROUND_AND_BUILDINGS",
                "TID_TARGETS_BUILDINGS_AND_GROUND",
            } or bool(getattr(stats, "attacks_ground", True))
            death_spawn[card_id] = bool(getattr(stats, "death_spawn_character", None))
            area_radius[card_id] = round(
                float(getattr(stats, "area_damage_radius", 0.0) or 0.0) * 1_000
            )
            self_center[card_id] = bool(getattr(stats, "self_as_aoe_center", False))
            sight_clip[card_id] = round(
                float(getattr(stats, "sight_clip", 0.0) or 0.0) * 1_000
            )
            sight_clip_side[card_id] = round(
                float(getattr(stats, "sight_clip_side", 0.0) or 0.0) * 1_000
            )
            first_hit[card_id] = round(
                float(getattr(stats, "first_hit_time", 0.0) or 0.0)
            )
            jump_height[card_id] = bool(getattr(stats, "jump_height", None))
            jump_speed[card_id] = round(float(getattr(stats, "jump_speed", 0) or 0))
            charge_range[card_id] = int(getattr(stats, "charge_range", 0) or 0)
            movement_stop_after[card_id] = round(
                float(getattr(stats, "stop_movement_after_ms", 0) or 0)
            )
            movement_wait[card_id] = round(float(getattr(stats, "wait_ms", 0) or 0))
            movement_base_speed[card_id] = max(
                1, round(float(getattr(stats, "speed", 0) or 0))
            )
        return cls(
            runtime=runtime,
            deployment=deployment,
            mechanics=mechanics,
            dispatcher=dispatcher,
            movement=movement,
            path_cache=path_cache,
            status=status,
            objects=objects,
            continuous_areas=continuous_areas,
            continuous_effect_deadline_seconds=(continuous_effect_deadline_seconds),
            graveyards=graveyards,
            tornadoes=tornadoes,
            rolling_spells=rolling_spells,
            royal_delivery=royal_delivery,
            periodic_catalog=periodic_catalog,
            periodic_state=periodic_state,
            terminal_pipeline=terminal_pipeline,
            projectile_bridge=projectile_bridge,
            spell_ingress=spell_ingress,
            action_router=action_router,
            pending_spells=pending_spells,
            pending_projectile_max_duration_ms=pending_projectile_max_duration_ms,
            projectile_duration_ms=projectile_duration_ms,
            combat=combat,
            combat_target_entity_id=combat_target_entity_id,
            uses_projectile=uses_projectile,
            can_attack_air=can_attack_air,
            can_attack_ground=can_attack_ground,
            death_spawn=death_spawn,
            area_radius_units=area_radius,
            self_as_aoe_center=self_center,
            sight_clip_units=sight_clip,
            sight_clip_side_units=sight_clip_side,
            first_hit_ms=first_hit,
            jump_height=jump_height,
            jump_speed_units=jump_speed,
            charge_range_units=charge_range,
            movement_stop_after_ms=movement_stop_after,
            movement_wait_ms=movement_wait,
            movement_base_speed_units=movement_base_speed,
            facing_x_units=movement.facing_units[..., 0].clone(),
            facing_y_units=movement.facing_units[..., 1].clone(),
        )

    def clone(self) -> TensorResidentEngine:
        runtime = self.runtime.clone()
        # TensorBattleRuntime.fork currently shares this nested mutable owner.
        runtime.battle.rng = self.runtime.battle.rng.clone()
        mechanics = self.mechanics.clone()
        dispatcher = self.dispatcher._fork(
            torch.arange(self.batch_size, dtype=torch.int64, device=self.device)
        )
        dispatcher.runtime = runtime
        dispatcher.mechanics = mechanics
        dispatcher.passive.entity_id = runtime.battle.entity_id
        objects = _clone_object_phase(self.objects)
        continuous_areas = self.continuous_areas.clone()
        graveyards = self.graveyards.clone()
        tornadoes = self.tornadoes.clone()
        rolling_spells = TensorResidentRollingSpells(
            self.rolling_spells.catalog,
            self.rolling_spells.state.clone(),
            _clone_tensor_dataclass(self.rolling_spells.targets),  # type: ignore[arg-type]
        )
        royal_delivery = self.royal_delivery.clone()
        periodic_state = self.periodic_state.clone()
        terminal_pipeline = _clone_terminal_pipeline(self.terminal_pipeline)
        projectile_bridge = _clone_projectile_bridge(self.projectile_bridge)
        spell_ingress = self.spell_ingress.fork(
            runtime,
            objects,
            projectile_bridge,
        )
        pending_spells = self.pending_spells.clone()
        action_router = copy.copy(self.action_router)
        action_router.runtime = runtime
        action_router.objects = objects
        action_router.bridge = projectile_bridge
        action_router.spells = spell_ingress
        action_router.pending_spells = pending_spells
        return type(self)(
            runtime=runtime,
            deployment=self.deployment,
            mechanics=mechanics,
            dispatcher=dispatcher,
            movement=_clone_tensor_dataclass(self.movement),  # type: ignore[arg-type]
            # Entries are immutable deterministic functions of standard-arena
            # keys and are not battle-observable. Speculative rows may safely
            # warm one shared cache, including rows which later fail closed.
            path_cache=self.path_cache,
            status=self.status.clone(),
            objects=objects,
            continuous_areas=continuous_areas,
            continuous_effect_deadline_seconds=(
                self.continuous_effect_deadline_seconds
            ),
            graveyards=graveyards,
            tornadoes=tornadoes,
            rolling_spells=rolling_spells,
            royal_delivery=royal_delivery,
            periodic_catalog=self.periodic_catalog,
            periodic_state=periodic_state,
            terminal_pipeline=terminal_pipeline,
            projectile_bridge=projectile_bridge,
            spell_ingress=spell_ingress,
            action_router=action_router,
            pending_spells=pending_spells,
            pending_projectile_max_duration_ms=(
                self.pending_projectile_max_duration_ms.clone()
            ),
            projectile_duration_ms=self.projectile_duration_ms.clone(),
            combat=_clone_tensor_dataclass(self.combat),  # type: ignore[arg-type]
            combat_target_entity_id=self.combat_target_entity_id.clone(),
            uses_projectile=self.uses_projectile,
            can_attack_air=self.can_attack_air,
            can_attack_ground=self.can_attack_ground,
            death_spawn=self.death_spawn,
            area_radius_units=self.area_radius_units,
            self_as_aoe_center=self.self_as_aoe_center,
            sight_clip_units=self.sight_clip_units,
            sight_clip_side_units=self.sight_clip_side_units,
            first_hit_ms=self.first_hit_ms,
            jump_height=self.jump_height,
            jump_speed_units=self.jump_speed_units,
            charge_range_units=self.charge_range_units,
            movement_stop_after_ms=self.movement_stop_after_ms,
            movement_wait_ms=self.movement_wait_ms,
            movement_base_speed_units=self.movement_base_speed_units,
            facing_x_units=self.facing_x_units.clone(),
            facing_y_units=self.facing_y_units.clone(),
        )

    def _core_catalog_id(self) -> torch.Tensor:
        return self.runtime.card_catalog_index[self.runtime.battle.entity_card]

    def _terminal_entity_supported(self) -> torch.Tensor:
        catalog_id = self._core_catalog_id()
        safe = catalog_id.clamp_min(0)
        active_character = self.runtime.entity_pool.active & (
            (self.runtime.battle.entity_kind == 0)
            | (self.runtime.battle.entity_kind == 1)
        )
        operation = self.terminal_pipeline.catalog.terminal.source_row_by_card[safe]
        if not self.terminal_pipeline.catalog.timed_supported.numel():
            return torch.zeros_like(active_character)
        safe_operation = operation.clamp_min(0)
        payload_supported = (
            self.terminal_pipeline.catalog.terminal.direct_supported[safe_operation]
            | self.terminal_pipeline.catalog.timed_supported[safe_operation]
        )
        mechanics = self.runtime.catalog.mechanic_opcode[safe]
        death_spawn_opcode = MECHANIC_OPCODE["DeathSpawn"]
        terminal_only = ((mechanics == 0) | (mechanics == death_spawn_opcode)).all(
            dim=2
        )
        return active_character & (operation >= 0) & payload_supported & terminal_only

    def _periodic_entity_supported(self) -> torch.Tensor:
        """Return sources whose complete serialized mechanic set is resident."""

        catalog_id = self._core_catalog_id()
        safe = catalog_id.clamp_min(0)
        active_character = self.runtime.entity_pool.active & (
            (self.runtime.battle.entity_kind == 0)
            | (self.runtime.battle.entity_kind == 1)
        )
        operation = self.periodic_catalog.source_row_by_card[safe]
        mechanics = self.runtime.catalog.mechanic_opcode[safe]
        periodic_opcode = MECHANIC_OPCODE["PeriodicSpawner"]
        death_spawn_opcode = MECHANIC_OPCODE["DeathSpawn"]
        allowed_set = (
            (mechanics == 0)
            | (mechanics == periodic_opcode)
            | (mechanics == death_spawn_opcode)
        ).all(dim=2)
        has_death_spawn = (mechanics == death_spawn_opcode).any(dim=2)

        terminal_operation = self.terminal_pipeline.catalog.terminal.source_row_by_card[
            safe
        ]
        if self.terminal_pipeline.catalog.timed_supported.numel():
            safe_terminal = terminal_operation.clamp_min(0)
            terminal_supported = (
                self.terminal_pipeline.catalog.terminal.direct_supported[safe_terminal]
                | self.terminal_pipeline.catalog.timed_supported[safe_terminal]
            )
            terminal_supported &= terminal_operation >= 0
        else:
            terminal_supported = torch.zeros_like(active_character)
        return (
            active_character
            & (operation >= 0)
            & allowed_set
            & (~has_death_spawn | terminal_supported)
        )

    def _refresh_projectile_reservations_(self) -> None:
        state = self.objects.objects
        blueprints = state.blueprint_id.to(torch.int64).clamp_min(0)
        projectile_active = (
            state.allocated
            & state.active
            & (
                self.objects.blueprint_kind[blueprints]
                == int(RuntimeObjectKind.PROJECTILE)
            )
        )
        target_id = self.objects.blueprint_primary_target_id[blueprints]
        matches = (
            (target_id[:, :, None] == self.runtime.battle.entity_id[:, None, :])
            & self.runtime.entity_pool.active[:, None, :]
            & (target_id[:, :, None] > 0)
        )
        target_found = matches.any(dim=2)
        target_slot = matches.to(torch.int64).argmax(dim=2)
        base_damage = state.amount
        target_crown = torch.gather(self.objects.target_crown, 1, target_slot)
        base_integer = torch.round(base_damage).to(torch.int64).clamp_min(0)
        percentage = (
            torch.round(self.objects.blueprint_crown_multiplier[blueprints] * 100.0)
            .to(torch.int64)
            .clamp_min(0)
        )
        native_crown = torch.where(
            (base_integer > 0) & (percentage > 0),
            torch.div(
                base_integer * percentage + 99,
                100,
                rounding_mode="floor",
            ),
            0,
        ).to(torch.float64)
        expected_damage = torch.where(
            target_crown,
            torch.where(
                self.objects.blueprint_crown_damage_valid[blueprints],
                self.objects.blueprint_crown_damage[blueprints],
                native_crown,
            ),
            base_damage,
        )
        self.combat.reserved_lethal.copy_(
            projectile_lethal_reservations(
                target_hp=self.runtime.battle.entity_hp,
                target_alive=(
                    self.runtime.entity_pool.active & self.runtime.battle.entity_active
                ),
                target_shield_hp=torch.zeros_like(self.runtime.battle.entity_hp),
                prior_max_duration_ms=self.pending_projectile_max_duration_ms,
                projectile_active=projectile_active & target_found,
                projectile_reserves_damage=(
                    self.projectile_bridge.blueprint_tracks_target[blueprints]
                ),
                projectile_target_slot=target_slot,
                projectile_expected_damage=expected_damage,
                projectile_duration_ms=self.projectile_duration_ms,
            )
        )

    def _record_new_projectile_durations_(
        self, previously_allocated: torch.Tensor
    ) -> None:
        state = self.objects.objects
        blueprints = state.blueprint_id.to(torch.int64).clamp_min(0)
        new_projectile = (
            state.allocated
            & ~previously_allocated
            & (
                self.objects.blueprint_kind[blueprints]
                == int(RuntimeObjectKind.PROJECTILE)
            )
            & self.projectile_bridge.blueprint_tracks_target[blueprints]
        )
        dx = state.target_x_units.to(torch.int64) - state.x_units.to(torch.int64)
        dy = state.target_y_units.to(torch.int64) - state.y_units.to(torch.int64)
        distance = _integer_sqrt(dx * dx + dy * dy)
        speed = state.speed_units_per_tick.to(torch.int64)
        raw_duration = torch.div(
            distance * 50,
            speed.clamp_min(1),
            rounding_mode="floor",
        )
        duration = torch.where(
            speed > 0,
            torch.div(raw_duration + 49, 50, rounding_mode="floor") * 50,
            1_000,
        ).clamp_max(1_000)
        self.projectile_duration_ms.copy_(
            torch.where(
                new_projectile,
                duration,
                self.projectile_duration_ms,
            )
        )
        target_id = self.objects.blueprint_primary_target_id[blueprints]
        matches = (
            (target_id[:, :, None] == self.runtime.battle.entity_id[:, None, :])
            & self.runtime.entity_pool.active[:, None, :]
            & (target_id[:, :, None] > 0)
        )
        found = matches.any(dim=2)
        target_slot = matches.to(torch.int64).argmax(dim=2)
        projected = torch.zeros_like(self.pending_projectile_max_duration_ms)
        projected.scatter_reduce_(
            1,
            target_slot,
            torch.where(new_projectile & found, duration, 0),
            reduce="amax",
            include_self=True,
        )
        self.pending_projectile_max_duration_ms.copy_(
            torch.maximum(self.pending_projectile_max_duration_ms, projected)
        )

    def preflight(self, action_ids: torch.Tensor | None = None) -> ResidentPreflight:
        """Return production support planes without host-side row extraction."""

        actions = (
            torch.full(
                (self.batch_size, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=self.device,
            )
            if action_ids is None
            else torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        )
        if actions.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        base_supported = self.runtime.supported & ~self.runtime.battle.game_over
        reason = torch.zeros(self.batch_size, dtype=torch.int16, device=self.device)

        def publish(mask: torch.Tensor, code: ResidentUnsupportedReason) -> None:
            nonlocal reason
            reason = torch.where(
                (reason == 0) & mask,
                torch.full_like(reason, int(code)),
                reason,
            )

        catalog_id = self._core_catalog_id()
        active_character = self.runtime.entity_pool.active & (
            (self.runtime.battle.entity_kind == 0)
            | (self.runtime.battle.entity_kind == 1)
        )
        live_character = active_character & self.runtime.battle.entity_active
        safe = catalog_id.clamp_min(0)
        known = (catalog_id > 0) | (self.runtime.battle.entity_tower_slot >= 0)
        mechanic_codes = torch.arange(
            max(RESIDENT_UNSUPPORTED_MECHANIC_OPCODES) + 1,
            dtype=torch.int64,
            device=self.device,
        )
        effect_codes = torch.arange(
            max(RESIDENT_UNSUPPORTED_EFFECT_OPCODES) + 1,
            dtype=torch.int64,
            device=self.device,
        )
        entity_mechanics = self.runtime.catalog.mechanic_opcode[safe]
        entity_effects = self.runtime.catalog.effect_opcode[safe]
        mechanic_present = (
            (entity_mechanics[..., None] == mechanic_codes)
            & active_character[..., None, None]
            & (mechanic_codes > 0)
        ).any(dim=(1, 2))
        effect_present = (
            (entity_effects[..., None] == effect_codes)
            & active_character[..., None, None]
            & (effect_codes > 0)
        ).any(dim=(1, 2))
        admitted_mechanic = torch.zeros(
            mechanic_codes.shape[0], dtype=torch.bool, device=self.device
        )
        admitted_mechanic[list(RESIDENT_DISPATCH_MECHANIC_OPCODES)] = True
        death_spawn_opcode = MECHANIC_OPCODE["DeathSpawn"]
        periodic_opcode = MECHANIC_OPCODE["PeriodicSpawner"]
        mechanic_admitted = (
            admitted_mechanic[entity_mechanics.to(torch.int64).clamp_min(0)]
            | (entity_mechanics == death_spawn_opcode)
            | (entity_mechanics == periodic_opcode)
        )
        unsupported_active_mechanic = (
            active_character[:, :, None] & (entity_mechanics > 0) & ~mechanic_admitted
        ).any(dim=(1, 2))
        terminal_operation = self.terminal_pipeline.catalog.terminal.source_row_by_card[
            safe
        ]
        if self.terminal_pipeline.catalog.timed_supported.numel():
            safe_terminal_operation = terminal_operation.clamp_min(0)
            terminal_payload_supported = (
                self.terminal_pipeline.catalog.terminal.direct_supported[
                    safe_terminal_operation
                ]
                | self.terminal_pipeline.catalog.timed_supported[
                    safe_terminal_operation
                ]
            )
        else:
            terminal_payload_supported = torch.zeros_like(active_character)
        terminal_only_death_spawn = (
            (entity_mechanics == 0) | (entity_mechanics == death_spawn_opcode)
        ).all(dim=2)
        terminal_entity_supported = (
            active_character
            & (terminal_operation >= 0)
            & terminal_payload_supported
            & terminal_only_death_spawn
        )
        periodic_entity_supported = self._periodic_entity_supported()
        periodic_entity = (entity_mechanics == periodic_opcode).any(dim=2)
        death_spawn_supported = terminal_entity_supported | periodic_entity_supported

        if self.device.type not in {"cpu", "cuda"}:
            publish(torch.ones_like(base_supported), ResidentUnsupportedReason.DEVICE)
        publish(
            (~known & active_character).any(dim=1),
            ResidentUnsupportedReason.UNKNOWN_CHARACTER,
        )
        publish(
            unsupported_active_mechanic,
            ResidentUnsupportedReason.ACTIVE_MECHANIC,
        )
        publish(
            (periodic_entity & active_character & ~periodic_entity_supported).any(
                dim=1
            ),
            ResidentUnsupportedReason.ACTIVE_MECHANIC,
        )
        publish(effect_present.any(dim=1), ResidentUnsupportedReason.ACTIVE_EFFECT)
        core_card = self.runtime.battle.entity_card.clamp_min(0)
        bridge_projectile = self.projectile_bridge.catalog.supported[core_card] & (
            self.projectile_bridge.catalog.kind[core_card]
            == BridgePayloadKind.COMBAT_PROJECTILE
        )
        retained_projectile = (
            self.combat.present
            & (self.combat.entity_id == self.runtime.battle.entity_id)
            & self.combat.uses_projectile
        )
        projectile_entity = self.uses_projectile[safe] | retained_projectile
        target_slot = self.combat.target_slot.clamp_min(0)
        target_x = torch.gather(self.combat.x_units, 1, target_slot)
        target_y = torch.gather(self.combat.y_units, 1, target_slot)
        target_radius = torch.gather(self.combat.collision_radius_units, 1, target_slot)
        dx = target_x - self.combat.x_units
        dy = target_y - self.combat.y_units
        reach = self.combat.range_units + target_radius
        crown_launch_imminent = (
            (self.runtime.battle.entity_tower_slot >= 0)
            & (self.combat.target_slot >= 0)
            & (dx * dx + dy * dy <= reach * reach)
            & (
                self.combat.attack_cooldown
                <= LOGIC_TICK_SECONDS
                * self.combat.attack_rate_multiplier.clamp_min(0.05)
                + 1e-9
            )
            & ~self.combat.stunned
            & (self.combat.deploy_remaining <= 0.0)
        )
        hostile_character_exists = (
            live_character[:, :, None]
            & live_character[:, None, :]
            & (
                self.runtime.battle.entity_player[:, :, None]
                != self.runtime.battle.entity_player[:, None, :]
            )
        ).any(dim=2)
        publish(
            (
                projectile_entity
                & live_character
                & ~bridge_projectile
                & (
                    (
                        (self.runtime.battle.entity_tower_slot < 0)
                        & hostile_character_exists
                    )
                    | crown_launch_imminent
                )
            ).any(dim=1),
            ResidentUnsupportedReason.PROJECTILE_COMBAT,
        )
        death_spawn_entity = (entity_mechanics == death_spawn_opcode).any(dim=2)
        publish(
            (death_spawn_entity & active_character & ~death_spawn_supported).any(dim=1),
            ResidentUnsupportedReason.DEATH_SPAWN,
        )
        timed_live = self.terminal_pipeline.state.objects.allocated.any(dim=1)
        general_live = self.objects.objects.allocated.any(dim=1)
        terminal_dead = death_spawn_supported & ~self.runtime.battle.entity_active
        publish(
            (timed_live | terminal_dead.any(dim=1)) & general_live,
            ResidentUnsupportedReason.OBJECT_PHASE,
        )
        periodic_live = periodic_entity_supported.any(dim=1)
        publish(
            periodic_live & (timed_live | general_live),
            ResidentUnsupportedReason.OBJECT_PHASE,
        )
        area_kind_count = (
            self.continuous_areas.active.any(dim=1).to(torch.int8)
            + self.graveyards.active.any(dim=1).to(torch.int8)
            + self.tornadoes.active.any(dim=1).to(torch.int8)
        )
        area_live = area_kind_count > 0
        publish(
            (area_kind_count > 1)
            | (area_live & (timed_live | general_live | periodic_live)),
            ResidentUnsupportedReason.OBJECT_PHASE,
        )
        retained_spell_live = self.rolling_spells.state.active.any(
            dim=1
        ) | self.royal_delivery.active.any(dim=1)
        publish(
            retained_spell_live
            & (timed_live | general_live | periodic_live | area_live),
            ResidentUnsupportedReason.OBJECT_PHASE,
        )
        publish(~self.objects.static_supported, ResidentUnsupportedReason.OBJECT_PHASE)

        # Pure action ingress contributes opcodes before any speculative state
        # or RNG is mutated.
        action_state = self.deployment.action_state(self.runtime)
        ingress = self.deployment.kernel.ingress(
            action_state,
            actions,
            legal_mask=self.deployment.kernel.legal_action_mask(action_state),
        )
        command_rows = ingress.commands.battle_index
        command_cards = ingress.commands.card_id
        command_mechanics = self.runtime.catalog.mechanic_opcode[command_cards]
        command_effects = self.runtime.catalog.effect_opcode[command_cards]

        def scatter_opcode_presence(
            destination: torch.Tensor,
            opcodes: torch.Tensor,
        ) -> torch.Tensor:
            width = destination.shape[1]
            expanded_rows = command_rows[:, None].expand_as(opcodes)
            valid = opcodes > 0
            flat = torch.zeros(
                self.batch_size * width, dtype=torch.int32, device=self.device
            )
            keys = expanded_rows * width + opcodes.to(torch.int64)
            flat.scatter_add_(
                0,
                keys[valid],
                torch.ones_like(keys[valid], dtype=torch.int32),
            )
            return destination | (flat.reshape(self.batch_size, width) > 0)

        mechanic_present = scatter_opcode_presence(mechanic_present, command_mechanics)
        effect_present = scatter_opcode_presence(effect_present, command_effects)
        # Deployment materialization still rejects every mechanic-bearing
        # payload. Keep those actions at the preflight boundary until the
        # materializer receives the same admitted-opcode contract.
        command_has_mechanic = (command_mechanics > 0).any(dim=1)
        command_has_effect = (command_effects > 0).any(dim=1)
        command_payload = self.deployment.materializer.catalog.supported_payload[
            command_cards
        ]
        spell_preflight = self.spell_ingress.preflight(ingress)

        def command_rows_with(mask: torch.Tensor) -> torch.Tensor:
            rows = torch.zeros(self.batch_size, dtype=torch.int32, device=self.device)
            rows.scatter_add_(0, command_rows, mask.to(torch.int32))
            return rows > 0

        publish(
            command_rows_with(ingress.commands.is_ability),
            ResidentUnsupportedReason.CHAMPION_ACTION,
        )
        publish(
            command_rows_with(
                spell_preflight.command_spell & ~spell_preflight.command_supported
            ),
            ResidentUnsupportedReason.SPELL_ACTION,
        )
        publish(
            command_rows_with(command_has_mechanic & ~spell_preflight.command_spell),
            ResidentUnsupportedReason.ACTION_MECHANIC,
        )
        publish(
            command_rows_with(command_has_effect & ~spell_preflight.command_spell),
            ResidentUnsupportedReason.ACTION_EFFECT,
        )
        publish(
            command_rows_with(~command_payload & ~spell_preflight.command_spell),
            ResidentUnsupportedReason.MIXED_PAYLOAD,
        )
        return ResidentPreflight(
            supported=base_supported & (reason == 0),
            reason_code=reason,
            mechanic_opcode_present=mechanic_present,
            effect_opcode_present=effect_present,
        )

    def diagnose_preflight(
        self, action_ids: torch.Tensor | None = None
    ) -> ResidentPreflightDiagnostics:
        """Convert support planes to strings at an explicit debug boundary."""

        result = self.preflight(action_ids)
        reasons: list[str | None] = []
        mechanics: list[tuple[int, ...]] = []
        effects: list[tuple[int, ...]] = []
        supported = tuple(bool(value) for value in result.supported.tolist())
        for row, raw_code in enumerate(result.reason_code.tolist()):
            code = ResidentUnsupportedReason(int(raw_code))
            row_mechanics = tuple(
                int(value)
                for value in torch.nonzero(
                    result.mechanic_opcode_present[row], as_tuple=False
                )
                .flatten()
                .tolist()
            )
            row_effects = tuple(
                int(value)
                for value in torch.nonzero(
                    result.effect_opcode_present[row], as_tuple=False
                )
                .flatten()
                .tolist()
            )
            text = (
                None if code is ResidentUnsupportedReason.NONE else _REASON_TEXT[code]
            )
            if code in {
                ResidentUnsupportedReason.ACTIVE_MECHANIC,
                ResidentUnsupportedReason.ACTION_MECHANIC,
            }:
                text = f"{text}: {row_mechanics}"
            elif code in {
                ResidentUnsupportedReason.ACTIVE_EFFECT,
                ResidentUnsupportedReason.ACTION_EFFECT,
            }:
                text = f"{text}: {row_effects}"
            elif code is ResidentUnsupportedReason.OBJECT_PHASE:
                text = self.objects.unsupported_reasons[row] or text
            reasons.append(text)
            mechanics.append(row_mechanics)
            effects.append(row_effects)
        return ResidentPreflightDiagnostics(
            supported=supported,
            reasons=tuple(reasons),
            unsupported_mechanic_opcodes=tuple(mechanics),
            unsupported_effect_opcodes=tuple(effects),
        )

    def _refresh_planes(self) -> torch.Tensor:
        runtime = self.runtime
        core = runtime.battle
        present = runtime.entity_pool.active
        old_id = self.combat.entity_id.clone()
        new = present & ((old_id != core.entity_id) | ~self.combat.present)
        catalog_id = runtime.card_catalog_index[core.entity_card]
        safe = catalog_id.clamp_min(0)
        catalog_known = catalog_id > 0
        crown = core.entity_tower_slot >= 0
        known = catalog_known | crown
        character = present & ((core.entity_kind == 0) | (core.entity_kind == 1))
        troop = character & (core.entity_kind == 0)

        component_present = present & character
        self.combat.present.copy_(component_present)
        self.combat.entity_id.copy_(core.entity_id)
        self.combat.encounter_order.copy_(core.entity_id)
        self.combat.kind.copy_(core.entity_kind)
        self.combat.owner.copy_(core.entity_player)
        self.combat.x_units.copy_(core.entity_x_units.to(torch.int64))
        self.combat.y_units.copy_(core.entity_y_units.to(torch.int64))
        self.combat.hp.copy_(core.entity_hp)
        self.combat.max_hp.copy_(core.entity_max_hp)
        self.combat.alive.copy_(core.entity_active & present)
        self.combat.deploy_remaining.copy_(core.entity_deploy_delay)
        self.combat.last_attack_time.copy_(core.entity_last_attack_time)
        self.combat.crown_slot.copy_(core.entity_tower_slot)
        self.combat.tower_active.copy_(core.entity_tower_active)
        self.combat.damage.copy_(
            torch.where(
                catalog_known,
                self.runtime.catalog.damage[safe],
                self.combat.damage,
            )
        )
        self.combat.range_units.copy_(
            torch.where(
                catalog_known,
                self.runtime.catalog.range_units[safe].to(torch.int64),
                self.combat.range_units,
            )
        )
        self.combat.sight_range_units.copy_(
            torch.where(
                catalog_known,
                self.runtime.catalog.sight_range_units[safe].to(torch.int64),
                self.combat.sight_range_units,
            )
        )
        radius = self.runtime.catalog.collision_radius_units[safe].to(torch.int64)
        self.combat.collision_radius_units.copy_(
            torch.where(
                catalog_known,
                torch.where(radius > 0, radius, 500),
                self.combat.collision_radius_units,
            )
        )
        self.combat.sight_clip_units.copy_(
            torch.where(
                catalog_known,
                self.sight_clip_units[safe],
                self.combat.sight_clip_units,
            )
        )
        self.combat.sight_clip_side_units.copy_(
            torch.where(
                catalog_known,
                self.sight_clip_side_units[safe],
                self.combat.sight_clip_side_units,
            )
        )
        self.combat.can_attack_air.copy_(
            torch.where(
                catalog_known,
                self.can_attack_air[safe],
                self.combat.can_attack_air,
            )
        )
        self.combat.can_attack_ground.copy_(
            torch.where(
                catalog_known,
                self.can_attack_ground[safe],
                self.combat.can_attack_ground,
            )
        )
        self.combat.buildings_only.copy_(
            torch.where(
                catalog_known,
                self.runtime.catalog.buildings_only[safe],
                self.combat.buildings_only,
            )
        )
        self.combat.uses_projectile.copy_(
            torch.where(
                catalog_known,
                self.uses_projectile[safe],
                self.combat.uses_projectile,
            )
        )
        self.combat.airborne.copy_(
            torch.where(
                catalog_known,
                self.runtime.catalog.is_air_unit[safe],
                self.combat.airborne,
            )
        )
        self.combat.building_target.copy_(core.entity_kind == 1)
        self.combat.area_radius_units.copy_(
            torch.where(
                catalog_known,
                self.area_radius_units[safe],
                self.combat.area_radius_units,
            )
        )
        self.combat.self_as_aoe_center.copy_(
            torch.where(
                catalog_known,
                self.self_as_aoe_center[safe],
                self.combat.self_as_aoe_center,
            )
        )
        self.combat.targetable.copy_(present & core.entity_active)
        self.combat.effect_receivable.fill_(True)
        self.combat.area_effect_receivable.fill_(True)
        self.combat.stunned.copy_(runtime.status.stun_timer > 1e-9)
        self.combat.forced_movement.zero_()
        self.combat.combat_blocked.copy_(self.mechanics.combat_blocked())
        self.combat.combat_blocked |= self.dispatcher.dash.phase != 0
        self.combat.combat_blocked |= (
            self.movement.river_jump_active | self.movement.special_move_consumed_tick
        )
        retained_knockback = (
            self.projectile_bridge.knockback_active
            & self.runtime.entity_pool.active
            & (
                self.projectile_bridge.knockback_entity_id
                == self.runtime.battle.entity_id
            )
        )
        self.combat.forced_movement |= retained_knockback
        self.combat.combat_blocked |= retained_knockback
        self.combat.attack_rate_multiplier.copy_(
            self.mechanics.attack_rate_multiplier(runtime)
        )
        self.combat.ordinary_combat_supported.copy_(~present | ~character | known)
        self.combat.hit_speed_ms.copy_(
            torch.where(
                catalog_known,
                self.runtime.catalog.hit_speed_ms[safe].to(torch.int64),
                self.combat.hit_speed_ms,
            )
        )
        self.combat.first_hit_ms.copy_(
            torch.where(
                catalog_known,
                self.first_hit_ms[safe],
                self.combat.first_hit_ms,
            )
        )
        initial_cooldown = self.first_hit_ms[safe].to(torch.float64) / 1_000.0
        self.combat.attack_cooldown.copy_(
            torch.where(new & character, initial_cooldown, self.combat.attack_cooldown)
        )
        self.combat.attack_preload_blocked &= ~new
        self.combat.attack_windup_active &= ~new
        self.combat.has_attacked_once &= ~new
        self.combat.target_slot.copy_(torch.where(new, -1, runtime.phases.target_slot))
        self.combat_target_entity_id.copy_(
            torch.where(new, -1, self.combat_target_entity_id)
        )
        self.combat.target_distance_discount_sq_units.zero_()
        self.pending_projectile_max_duration_ms.copy_(
            torch.where(
                new,
                torch.zeros_like(self.pending_projectile_max_duration_ms),
                self.pending_projectile_max_duration_ms,
            )
        )
        self._refresh_projectile_reservations_()
        self.combat.outgoing_damage_multiplier.fill_(1.0)
        self.combat.incoming_damage_multiplier.fill_(1.0)

        movement = self.movement
        movement.slot_present.copy_(component_present)
        movement.entity_id.copy_(core.entity_id)
        movement.entity_active.copy_(core.entity_active & present)
        movement.entity_kind.copy_(core.entity_kind.to(torch.int64))
        movement.player_id.copy_(core.entity_player.to(torch.int64))
        movement.position_units.copy_(
            torch.stack((core.entity_x_units, core.entity_y_units), dim=-1).to(
                torch.int64
            )
        )
        new_troop = new & troop
        spawn_facing_y = torch.where(
            core.entity_player == 0,
            torch.full_like(core.entity_id, 1_000),
            torch.full_like(core.entity_id, -1_000),
        )
        self.facing_x_units.copy_(
            torch.where(
                new_troop, torch.zeros_like(self.facing_x_units), self.facing_x_units
            )
        )
        self.facing_y_units.copy_(
            torch.where(new_troop, spawn_facing_y, self.facing_y_units)
        )
        movement.facing_units[..., 0].copy_(
            torch.where(
                new_troop,
                torch.zeros_like(movement.facing_units[..., 0]),
                movement.facing_units[..., 0],
            )
        )
        movement.facing_units[..., 1].copy_(
            torch.where(
                new_troop,
                spawn_facing_y,
                movement.facing_units[..., 1],
            )
        )
        movement.is_troop.copy_(troop)
        movement.is_air.copy_(self.runtime.catalog.is_air_unit[safe])
        movement.is_hover.copy_(self.runtime.catalog.is_hover_unit[safe])
        movement.jump_height.copy_(self.jump_height[safe])
        movement.jump_speed_units.copy_(self.jump_speed_units[safe])
        spawn_lane = _resident_native_lane_ids(movement.position_units)
        movement.lane_id.copy_(torch.where(new & troop, spawn_lane, movement.lane_id))
        movement.collision_radius_units.copy_(self.combat.collision_radius_units)
        movement.mass_milliunits.copy_(
            torch.round(self.runtime.catalog.mass[safe] * 1_000.0)
            .to(torch.int64)
            .clamp_min(1)
        )
        movement.effective_speed_units.copy_(
            self.runtime.catalog.speed_units_per_tick[safe].to(torch.int64)
        )
        movement_operations = self.runtime.catalog.mechanic_opcode[safe]
        movement_admitted = torch.zeros(
            max(MECHANIC_OPCODE.values()) + 1,
            dtype=torch.bool,
            device=self.device,
        )
        movement_admitted[0] = True
        movement_admitted[list(RESIDENT_DISPATCH_MECHANIC_OPCODES)] = True
        movement.mechanic_free.copy_(
            movement_admitted[movement_operations.to(torch.int64)].all(dim=2)
        )
        movement.stunned.copy_(self.combat.stunned)
        movement.forced_movement.zero_()
        movement.special_movement.copy_(movement.river_jump_active)
        movement.death_spawn_travel.zero_()
        movement.knockback_active.zero_()
        movement.kamikaze_primed.zero_()
        movement.charge_component.copy_(
            troop & catalog_known & (self.charge_range_units[safe] > 0)
        )
        movement.movement_cycle.copy_(
            catalog_known
            & (self.movement_stop_after_ms[safe] > 0)
            & (self.movement_wait_ms[safe] > 0)
        )
        movement.ordinary_unsupported.zero_()
        active_river_supported = (
            troop
            & movement.river_jump_active
            & movement.jump_height
            & (movement.jump_speed_units > 0)
            & movement.river_origin_valid
            & movement.river_target_valid
        )
        movement.river_unsupported.copy_(
            torch.where(
                active_river_supported,
                torch.zeros_like(movement.river_unsupported),
                torch.ones_like(movement.river_unsupported),
            )
        )
        movement.ordinary_supported.copy_(troop & known)
        movement.river_jump_supported.copy_(active_river_supported)
        movement.air_collision.copy_(
            movement.is_air
            | movement.is_hover
            | movement.river_jump_active
            | movement.mega_knight_airborne
        )
        movement.in_transit.copy_(
            movement.river_jump_active | movement.mega_knight_airborne
        )
        movement.pending_vector_consumed.copy_(
            torch.where(
                new,
                torch.ones_like(movement.pending_vector_consumed),
                movement.pending_vector_consumed,
            )
        )
        movement.accumulated_vector_units.copy_(runtime.phases.movement_vector_units)
        movement.accumulated_vector_count.copy_(runtime.phases.movement_vector_count)
        movement.accumulated_vector_bypasses_cap.copy_(
            runtime.phases.movement_vector_bypasses_cap
        )

        self.status.lifetime_ms.copy_(core.entity_lifetime_ms)
        self.status.lifetime_elapsed.copy_(core.entity_lifetime_elapsed)
        self.status.lifetime_decay_work.copy_(core.entity_lifetime_decay_work)
        self.status.lifetime_tick_carry_ms.copy_(core.entity_lifetime_tick_carry_ms)
        self.status.movement_speed.copy_(
            torch.where(
                new,
                self.runtime.catalog.speed_units_per_tick[safe].to(torch.float64),
                self.status.movement_speed,
            )
        )
        self.mechanics.refresh_new_entities_(runtime)
        return new

    def _refresh_area_target_planes_(self, new: torch.Tensor) -> None:
        """Refresh dynamic target metadata after canonical entity allocation."""

        runtime = self.runtime
        core = runtime.battle
        catalog_id = runtime.card_catalog_index[core.entity_card]
        safe = catalog_id.clamp_min(0)
        known = catalog_id > 0
        character = runtime.entity_pool.active & (
            (core.entity_kind == 0) | (core.entity_kind == 1)
        )
        receiver = new & character & core.entity_active & known
        radius = runtime.catalog.collision_radius_units[safe].to(torch.int32)
        radius = torch.where(radius > 0, radius, 500)
        crown = core.entity_tower_slot >= 0

        continuous = self.continuous_areas.targets
        continuous.entity_id.copy_(core.entity_id)
        continuous.collision_radius_units.copy_(
            torch.where(new, radius, continuous.collision_radius_units)
        )
        continuous.airborne.copy_(
            torch.where(new, runtime.catalog.is_air_unit[safe], continuous.airborne)
        )
        continuous.building.copy_(
            torch.where(new, core.entity_kind == 1, continuous.building)
        )
        continuous.crown.copy_(torch.where(new, crown, continuous.crown))
        continuous.freeze_carrier.masked_fill_(new, False)
        continuous.damage_receivable[new] = receiver[new][:, None]
        continuous.effect_receivable[new] = receiver[new][:, None]

        tornado = self.tornadoes.targets
        tornado.entity_id.copy_(core.entity_id)
        tornado.collision_radius_units.copy_(
            torch.where(new, radius, tornado.collision_radius_units)
        )
        tornado.airborne.copy_(
            torch.where(new, runtime.catalog.is_air_unit[safe], tornado.airborne)
        )
        tornado.building.copy_(
            torch.where(new, core.entity_kind == 1, tornado.building)
        )
        tornado.crown.copy_(torch.where(new, crown, tornado.crown))
        tornado.base_speed.copy_(
            torch.where(
                new,
                runtime.catalog.speed_units_per_tick[safe].to(torch.int64),
                tornado.base_speed,
            )
        )
        tornado.area_displaceable.masked_fill_(new, False)
        tornado.effect_receivable[new] = receiver[new][:, None]
        tornado.damage_receivable[new] = receiver[new][:, None]
        tornado.transit_supported.copy_(
            ~self.movement.in_transit | self.movement.river_jump_active
        )

        rolling = self.rolling_spells.targets
        rolling.collision_radius_units.copy_(
            torch.where(new, radius.to(torch.int64), rolling.collision_radius_units)
        )
        rolling.above_ground.copy_(
            torch.where(new, runtime.catalog.is_air_unit[safe], rolling.above_ground)
        )
        rolling.crown.copy_(torch.where(new, crown, rolling.crown))
        rolling.knockback_immune.copy_(
            torch.where(
                new,
                self.royal_delivery.catalog.knockback_immune_catalog[safe],
                rolling.knockback_immune,
            )
        )
        death_opcode = runtime.catalog.mechanic_opcode[safe]
        unsupported_death = (
            (death_opcode == MECHANIC_OPCODE["DeathDamage"])
            | (death_opcode == MECHANIC_OPCODE["DeathSpawn"])
            | (death_opcode == MECHANIC_OPCODE["DeathAreaEffect"])
        ).any(dim=2)
        rolling.death_payload_supported.copy_(
            torch.where(new, ~unsupported_death, rolling.death_payload_supported)
        )
        expanded_new = new[None, :, :]
        expanded_receiver = receiver[None, :, :]
        rolling.area_receivable.copy_(
            torch.where(
                expanded_new,
                expanded_receiver,
                rolling.area_receivable,
            )
        )
        rolling.effect_receivable.copy_(
            torch.where(
                expanded_new,
                expanded_receiver,
                rolling.effect_receivable,
            )
        )
        rolling.knockback_receivable.copy_(
            torch.where(
                expanded_new,
                expanded_receiver,
                rolling.knockback_receivable,
            )
        )

    def _combat_clock_planes(self) -> TensorCombatClockPlanes:
        return TensorCombatClockPlanes(
            attack_cooldown=self.combat.attack_cooldown,
            target_slot=self.combat.target_slot,
            attack_windup_active=self.combat.attack_windup_active,
            attack_preload_blocked=self.combat.attack_preload_blocked,
            has_attacked_once=self.combat.has_attacked_once,
        )

    def _resolve_pending_spells_(self) -> PendingSpellResolveResult:
        """Resolve due commands through one globally ordered handler worklist."""

        pending = self.pending_spells
        due = pending.active & (
            pending.execute_at <= self.runtime.battle.time[:, None] + 1e-9
        )
        due_rows = due.any(dim=1)
        supported = self.runtime.supported.clone()
        processed = torch.zeros_like(due)
        resolved_count = torch.zeros(
            self.batch_size, dtype=torch.int64, device=self.device
        )
        rows = torch.arange(self.batch_size, device=self.device)
        maximum_sequence = torch.iinfo(torch.int64).max
        infinity = torch.full_like(pending.execute_at, torch.inf)
        self.projectile_bridge.stun_applied.zero_()

        for _ in range(pending.capacity):
            candidate = due & ~processed & supported[:, None]
            selected_time = torch.where(candidate, pending.execute_at, infinity).amin(
                dim=1
            )
            at_time = candidate & (pending.execute_at == selected_time[:, None])
            sequence = torch.where(
                at_time,
                pending.sequence,
                torch.full_like(pending.sequence, maximum_sequence),
            )
            selected_sequence, slot = sequence.min(dim=1)
            selected = selected_sequence != maximum_sequence
            cards = torch.gather(pending.card_id, 1, slot[:, None])[:, 0]
            players = torch.gather(pending.player_id.to(torch.int64), 1, slot[:, None])[
                :, 0
            ]
            x_units = torch.gather(
                pending.target_x_units.to(torch.int64), 1, slot[:, None]
            )[:, 0]
            y_units = torch.gather(
                pending.target_y_units.to(torch.int64), 1, slot[:, None]
            )[:, 0]
            in_range = (cards >= 0) & (
                cards < self.projectile_bridge.catalog.supported.numel()
            )
            safe = cards.clamp(0, self.projectile_bridge.catalog.supported.numel() - 1)
            bridge_handler = (
                selected & in_range & self.projectile_bridge.catalog.supported[safe]
            )
            continuous_handler = (
                selected & self.continuous_areas.catalog.supported[safe] & in_range
            )
            graveyard_handler = (
                selected & in_range & self.graveyards.catalog.supported[safe]
            )
            tornado_handler = (
                selected & in_range & self.tornadoes.catalog.supported[safe]
            )
            rolling_handler = (
                selected & in_range & self.rolling_spells.catalog.supported[safe]
            )
            delivery_handler = (
                selected & in_range & self.royal_delivery.catalog.supported[safe]
            )
            handler_count = (
                bridge_handler.to(torch.int8)
                + continuous_handler.to(torch.int8)
                + graveyard_handler.to(torch.int8)
                + tornado_handler.to(torch.int8)
                + rolling_handler.to(torch.int8)
                + delivery_handler.to(torch.int8)
            )
            known = handler_count == 1
            bridge_supported = self.projectile_bridge.materialize_spell_actions_(
                self.runtime,
                self.objects,
                card_ids=cards,
                player_ids=players,
                target_x_units=x_units,
                target_y_units=y_units,
                valid=bridge_handler & known,
            )
            continuous_supported = self.continuous_areas.materialize_due_spell_actions_(
                self.runtime,
                card_ids=cards,
                player_ids=players,
                target_x_units=x_units,
                target_y_units=y_units,
                valid=continuous_handler & known,
            )
            graveyard_supported = self.graveyards.materialize_due_spell_actions_(
                self.runtime,
                card_ids=cards,
                player_ids=players,
                target_x_units=x_units,
                target_y_units=y_units,
                valid=graveyard_handler & known,
            )
            tornado_supported = self.tornadoes.materialize_due_spell_actions_(
                self.runtime,
                card_ids=cards,
                player_ids=players,
                target_x_units=x_units,
                target_y_units=y_units,
                valid=tornado_handler & known,
            )
            rolling_selected = rolling_handler & known
            rolling_handoff = TensorRollingDueHandoff(
                batch_index=rows[rolling_selected],
                pending_slot=slot[rolling_selected],
                card_id=cards[rolling_selected],
                player_id=players[rolling_selected],
                x_units=x_units[rolling_selected],
                y_units=y_units[rolling_selected],
                sequence=selected_sequence[rolling_selected],
            )
            rolling_supported = self.rolling_spells.consume_due_(
                self.runtime,
                pending,
                rolling_handoff,
            )
            delivery_result = self.royal_delivery.materialize_due_spell_actions_(
                self.runtime,
                card_ids=cards,
                player_ids=players,
                target_x_units=x_units,
                target_y_units=y_units,
                valid=delivery_handler & known,
            )
            materialized = (
                (~bridge_handler | bridge_supported)
                & (~continuous_handler | continuous_supported)
                & (~graveyard_handler | graveyard_supported)
                & (~tornado_handler | tornado_supported)
                & (~rolling_handler | rolling_supported)
                & (~delivery_handler | delivery_result.committed)
            )
            failed = selected & (~known | ~materialized)
            supported &= ~failed
            committed = selected & known & materialized
            selected_rows = rows[committed]
            selected_slots = slot[committed]
            pending.active[selected_rows, selected_slots] = False
            pending.execute_at[selected_rows, selected_slots] = 0.0
            pending.sequence[selected_rows, selected_slots] = 0
            pending.card_id[selected_rows, selected_slots] = 0
            pending.player_id[selected_rows, selected_slots] = 0
            pending.target_x_units[selected_rows, selected_slots] = 0
            pending.target_y_units[selected_rows, selected_slots] = 0
            resolved_count += committed.to(torch.int64)
            processed[rows[selected], slot[selected]] = True

        commit_rows = due_rows & supported
        return PendingSpellResolveResult(
            committed=~due_rows | commit_rows,
            due_rows=due_rows,
            resolved_count=torch.where(
                commit_rows, resolved_count, torch.zeros_like(resolved_count)
            ),
            failed_rows=due_rows & ~supported,
            stun_applied=self.projectile_bridge.stun_applied & commit_rows[:, None],
        )

    def _rewrite_area_periodic_events_(self, start: torch.Tensor) -> None:
        """Project target-local area damage onto the public Python ledger."""

        events = self.runtime.events
        slots = torch.arange(events.capacity, device=self.device)[None, :]
        segment = (slots >= start[:, None]) & (slots < events.count[:, None])
        safe_payload = events.payload.clamp(0, self.continuous_areas.catalog.size - 1)
        area_payload = (
            self.continuous_areas.catalog.target_local_damage[safe_payload]
            | self.tornadoes.catalog.supported[safe_payload]
        )
        public = (
            segment
            & area_payload
            & (
                (events.opcode == int(RuntimeEventOpcode.DAMAGE))
                | (events.opcode == int(RuntimeEventOpcode.DEATH))
            )
        )
        events.phase.copy_(torch.where(public, int(TickPhase.COMBAT), events.phase))
        events.source_id.masked_fill_(public, 0)
        events.payload.masked_fill_(public, 0)

    def _project_continuous_area_slow_status(
        self,
    ) -> tuple[Any, torch.Tensor]:
        """Reproduce scalar repeated-add deadlines for continuous slows.

        The retained area owner schedules work in exact integer milliseconds.
        Python's public slow duration is nevertheless computed from the
        repeatedly incremented binary64 ``next_effect_time``.  The immutable
        deadline table preserves those scalar bits on every device while this
        projection mirrors the owner's signature/slot order without host
        stepping.
        """

        owner = self.continuous_areas
        runtime = self.runtime
        cards = owner.card_id.clamp(0, owner.catalog.size - 1)
        selected = owner.active & runtime.supported[:, None]
        age_after = (
            owner.age_ms.to(torch.int64)
            + (runtime.battle.tick_milliseconds.to(torch.int64)[:, None])
        )
        duration_ms = owner.catalog.duration_ms[cards].to(torch.int64)
        deadline_ms = torch.minimum(age_after, duration_ms)
        targets, identity_supported, freeze_carrier = owner._target_mask(runtime, cards)
        supported = runtime.supported & identity_supported
        supported &= ~(
            freeze_carrier & owner.catalog.freeze_snapshot[cards][:, :, None]
        ).any(dim=(1, 2))
        card_index = cards[:, :, None, None].expand(
            self.batch_size,
            owner.capacity,
            runtime.max_entities,
            1,
        )
        effect_receivable = torch.gather(
            owner.targets.effect_receivable[:, None, :, :].expand(
                self.batch_size,
                owner.capacity,
                runtime.max_entities,
                -1,
            ),
            3,
            card_index,
        )[:, :, :, 0]
        projection = cast(
            TensorStatusState,
            _clone_tensor_dataclass(runtime.status),
        )

        freeze_area = (
            selected
            & owner.catalog.freeze_snapshot[cards]
            & ~owner.freeze_applied
            & supported[:, None]
        )
        freeze_targets = (
            targets
            & effect_receivable
            & freeze_area[:, :, None]
            & runtime.battle.entity_active[:, None, :]
        )
        freeze_matches = (
            projection.slow_active
            & (projection.slow_movement == 0.0)
            & (projection.slow_attack == 0.0)
            & (projection.slow_spawn == 0.0)
        ).any(dim=2)
        freeze_capacity = freeze_matches | (~projection.slow_active).any(dim=2)
        supported &= ~(freeze_targets & ~freeze_capacity[:, None, :]).any(dim=(1, 2))
        freeze_targets &= supported[:, None, None]
        expiry = runtime.battle.time[:, None, None] + (
            duration_ms.to(torch.float64)[:, :, None] / 1_000.0
        )
        maximum_expiry = torch.where(freeze_targets, expiry, 0.0).amax(dim=1)
        projection.apply_freeze_until(
            maximum_expiry,
            runtime.battle.time[:, None],
            mask=maximum_expiry > runtime.battle.time[:, None],
        )

        effect_due = (
            selected
            & ~owner.catalog.freeze_snapshot[cards]
            & (owner.next_effect_ms.to(torch.int64) <= deadline_ms)
            & (owner.next_effect_ms.to(torch.int64) < duration_ms)
            & supported[:, None]
        )
        projected_rows = torch.zeros(
            self.batch_size, dtype=torch.bool, device=self.device
        )
        for area_slot in range(owner.capacity):
            area_cards = cards[:, area_slot]
            slow_targets = (
                targets[:, area_slot]
                & effect_receivable[:, area_slot]
                & runtime.battle.entity_active
                & effect_due[:, area_slot, None]
                & (owner.catalog.movement_multiplier[area_cards][:, None] < 1.0)
            )
            movement = owner.catalog.movement_multiplier[area_cards][:, None]
            attack = owner.catalog.attack_multiplier[area_cards][:, None]
            spawn = owner.catalog.spawn_multiplier[area_cards][:, None]
            slow_matches = (
                projection.slow_active
                & (projection.slow_movement == movement[:, :, None])
                & (projection.slow_attack == attack[:, :, None])
                & (projection.slow_spawn == spawn[:, :, None])
            ).any(dim=2)
            slow_capacity = slow_matches | (~projection.slow_active).any(dim=2)
            supported &= ~(slow_targets & ~slow_capacity).any(dim=1)
            slow_targets &= supported[:, None]

            interval_ms = owner.catalog.effect_interval_ms[area_cards].to(torch.int64)
            ordinal = torch.div(
                owner.next_effect_ms[:, area_slot].to(torch.int64),
                interval_ms.clamp_min(1),
                rounding_mode="floor",
            ).clamp_min(1)
            ordinal = (ordinal - 1).clamp_max(
                self.continuous_effect_deadline_seconds.shape[1] - 1
            )
            exact_deadline = self.continuous_effect_deadline_seconds[
                area_cards, ordinal
            ]
            refresh = torch.maximum(
                owner.catalog.slow_refresh_ms[area_cards].to(torch.float64) / 1_000.0,
                interval_ms.to(torch.float64) / 1_000.0,
            )
            exact_remaining = (
                duration_ms[:, area_slot].to(torch.float64) / 1_000.0 - exact_deadline
            ).clamp_min(0.0)
            refresh = torch.where(
                owner.catalog.cap_slow_to_area[area_cards],
                torch.minimum(refresh, exact_remaining),
                refresh,
            )
            projection.apply_slow(
                refresh[:, None],
                movement,
                attack_speed_multiplier=attack,
                spawn_speed_multiplier=spawn,
                mask=slow_targets & (refresh[:, None] > 1e-9),
            )
            projected_rows |= slow_targets.any(dim=1)
        return projection, projected_rows & supported

    def _publish_continuous_area_slow_projection_(
        self,
        projection: Any,
        rows: torch.Tensor,
    ) -> None:
        for name in (
            "slow_active",
            "slow_remaining",
            "slow_movement",
            "slow_attack",
            "slow_spawn",
            "slow_timer",
            "slow_multiplier",
            "attack_speed_debuff_multiplier",
            "spawn_speed_debuff_multiplier",
        ):
            destination = getattr(self.runtime.status, name)
            source = getattr(projection, name)
            row_mask = rows.reshape(
                self.batch_size,
                *((1,) * (destination.ndim - 1)),
            )
            destination.copy_(torch.where(row_mask, source, destination))

    def _combat_phase(
        self,
        active: torch.Tensor,
        stun_applied: torch.Tensor | None = None,
    ) -> CombatStepResult:
        new = self._refresh_planes()
        self._refresh_area_target_planes_(new)
        if stun_applied is not None:
            accepted_stun = stun_applied & active[:, None] & self.combat.present
            stun_transition = apply_stun_interrupt_(
                self._combat_clock_planes(),
                status_applied=accepted_stun,
                hit_speed_ms=self.combat.hit_speed_ms,
                river_jump_active=self.movement.river_jump_active,
            )
            self.runtime.phases.target_slot.masked_fill_(
                stun_transition.transitioned, -1
            )
            self.combat_target_entity_id.masked_fill_(stun_transition.transitioned, -1)
            charge_reset = stun_transition.charge_reset & self.movement.charge_component
            self.movement.native_charge_progress.masked_fill_(charge_reset, 0)
            self.movement.distance_traveled_bits.masked_fill_(charge_reset, 0)
        self.combat.present &= active[:, None]
        retained_target_slot = self.combat.target_slot.clamp_min(0)
        retained_target_id = self.combat.entity_id.gather(1, retained_target_slot)
        retained_target_present = self.combat.present.gather(1, retained_target_slot)
        target_identity_matches = (
            (self.combat.target_slot >= 0)
            & retained_target_present
            & (retained_target_id == self.combat_target_entity_id)
        )
        self.combat.target_slot.copy_(
            torch.where(target_identity_matches, self.combat.target_slot, -1)
        )
        consumed_special = (
            self.movement.special_move_consumed_tick
            & self.combat.present
            & self.combat.alive
            & (self.combat.deploy_remaining <= 1e-9)
        )
        cooldown_work = (
            LOGIC_TICK_SECONDS * self.combat.attack_rate_multiplier.clamp_min(0.05)
        )
        cooldown_boundary = (self.combat.attack_cooldown > 0.0) & (
            (self.combat.attack_cooldown - cooldown_work).abs() <= 1e-9
        )
        self.combat.attack_cooldown.copy_(
            torch.where(
                cooldown_boundary,
                cooldown_work,
                self.combat.attack_cooldown,
            )
        )
        result = step_stationary_combat_(self.combat, LOGIC_TICK_SECONDS)
        resolved_target_slot = self.combat.target_slot.clamp_min(0)
        resolved_target_id = self.combat.entity_id.gather(1, resolved_target_slot)
        self.combat_target_entity_id.copy_(
            torch.where(self.combat.target_slot >= 0, resolved_target_id, -1)
        )
        self.movement.special_move_consumed_tick &= ~consumed_special
        runtime = self.runtime
        runtime.battle.entity_hp.copy_(
            torch.where(active[:, None], self.combat.hp, runtime.battle.entity_hp)
        )
        runtime.battle.entity_hp_integer_kind &= ~(
            active[:, None] & (result.damage_received > 0.0)
        )
        runtime.battle.entity_active.copy_(
            torch.where(
                active[:, None], self.combat.alive, runtime.battle.entity_active
            )
        )
        runtime.battle.entity_last_attack_time.copy_(
            torch.where(
                active[:, None],
                self.combat.last_attack_time,
                runtime.battle.entity_last_attack_time,
            )
        )
        runtime.phases.target_slot.copy_(
            torch.where(
                active[:, None], self.combat.target_slot, runtime.phases.target_slot
            )
        )
        runtime.phases.death_pending |= active[:, None] & ~self.combat.alive

        target = self.combat.target_slot.clamp_min(0)
        target_x = self.combat.x_units.gather(1, target)
        target_y = self.combat.y_units.gather(1, target)
        dx = target_x - self.combat.x_units
        dy = target_y - self.combat.y_units
        target_radius = self.combat.collision_radius_units.gather(1, target)
        reach = self.combat.range_units + target_radius
        in_range = dx * dx + dy * dy <= reach * reach
        observed = (
            active[:, None]
            & self.combat.present
            & (self.combat.target_slot >= 0)
            & self.combat.present.gather(1, target)
            & self.combat.alive.gather(1, target)
        )
        self.facing_x_units.copy_(torch.where(observed, dx, self.facing_x_units))
        self.facing_y_units.copy_(torch.where(observed, dy, self.facing_y_units))
        self.movement.facing_units[..., 0].copy_(
            torch.where(observed, dx, self.movement.facing_units[..., 0])
        )
        self.movement.facing_units[..., 1].copy_(
            torch.where(observed, dy, self.movement.facing_units[..., 1])
        )
        move = (
            observed
            & self.combat.alive
            & (self.combat.kind == 0)
            & (self.combat.deploy_remaining <= 1e-9)
            & ~self.combat.combat_blocked
            & ~in_range
        )
        previous_movement_target = self.movement.target_id.clone()
        self.movement.target_slot.copy_(torch.where(move, self.combat.target_slot, -1))
        target_id = self.combat.entity_id.gather(1, target)
        self.movement.target_id.copy_(torch.where(move, target_id, -1))
        self.movement.target_valid.copy_(move)
        target_position = torch.stack((target_x, target_y), dim=-1)
        self.movement.target_position_units.copy_(
            torch.where(
                move.unsqueeze(-1), target_position, self.movement.target_position_units
            )
        )
        changed_target = move & (previous_movement_target != self.movement.target_id)
        self._compile_straight_ground_routes_(move, changed_target)

        ordered = self.runtime.entity_pool.id_order(result.damage_received > 0)
        slots = ordered.slots.clamp_min(0)
        damage = result.damage_received.gather(1, slots)
        died = ordered.valid & ~self.combat.alive.gather(1, slots)
        valid = torch.stack((ordered.valid, died), dim=2).flatten(1)
        additions = valid.sum(dim=1, dtype=torch.int64)
        overflow = active & (
            runtime.events.count.to(torch.int64) + additions > runtime.events.capacity
        )
        runtime.mark_unsupported(overflow, phase=TickPhase.COMBAT)
        admitted = active & ~overflow
        if bool((valid & admitted[:, None]).any().item()):
            ids = ordered.entity_ids
            opcode = torch.stack(
                (
                    torch.full_like(ids, RuntimeEventOpcode.DAMAGE),
                    torch.full_like(ids, RuntimeEventOpcode.DEATH),
                ),
                dim=2,
            ).flatten(1)
            target_ids = torch.stack((ids, ids), dim=2).flatten(1)
            amount = torch.stack((damage, torch.zeros_like(damage)), dim=2).flatten(1)
            runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=opcode,
                valid=valid & admitted[:, None],
                target_id=target_ids,
                amount=amount,
            )
        runtime.mark_dirty(admitted, phase=TickPhase.COMBAT)
        return result

    def _mechanic_inputs(
        self,
        deployment: TensorRuntimeDeploymentResult,
        combat: CombatStepResult,
        active: torch.Tensor,
    ) -> MechanicTickInputs:
        runtime = self.runtime
        count = runtime.max_entities
        inputs = MechanicTickInputs.empty(
            self.dispatcher,
            event_width=count,
        )
        inputs.dt_ms.copy_(torch.round(runtime.battle.dt * 1_000.0).to(torch.int64))
        slots = torch.arange(count, dtype=torch.int64, device=self.device)[None, :]
        slots = slots.expand(self.batch_size, count)
        target_before = combat.target_before.clamp(min=0, max=count - 1)
        target_after = self.combat.target_slot.clamp(min=0, max=count - 1)
        direct_hit = (
            active[:, None]
            & combat.attacked
            & ~combat.projectile_launched
            & (combat.target_before >= 0)
        )
        inputs.attack_source_slot.copy_(slots)
        inputs.attack_target_slot.copy_(target_before)
        inputs.attack_damage.copy_(self.combat.damage)
        inputs.attack_valid.copy_(direct_hit)
        inputs.attack_damage_already_applied.copy_(direct_hit)
        inputs.status_eligible.copy_(direct_hit)
        inputs.attack_started.copy_(active[:, None] & combat.attacked)

        connected = (
            active[:, None]
            & self.combat.present
            & self.combat.alive
            & (self.combat.target_slot >= 0)
            & self.combat.present.gather(1, target_after)
            & self.combat.alive.gather(1, target_after)
        )
        inputs.connected_target_slot.copy_(
            torch.where(connected, self.combat.target_slot, -1)
        )
        inputs.connected.copy_(connected)
        inputs.attack_rate.copy_(self.combat.attack_rate_multiplier)
        inputs.has_attack_target.copy_(connected)
        dx = self.combat.x_units.gather(1, target_after) - self.combat.x_units
        dy = self.combat.y_units.gather(1, target_after) - self.combat.y_units
        target_radius = self.combat.collision_radius_units.gather(1, target_after)
        reach = self.combat.range_units + target_radius
        inputs.has_attack_range_target.copy_(
            connected & (dx * dx + dy * dy <= reach * reach)
        )
        inputs.stunned.copy_(self.runtime.status.stun_timer > 1e-9)

        dash_card, dash_slot, has_dash = self.dispatcher._special_operation(
            SpecialMovementOpcode.BANDIT_DASH
        )
        minimum = self.dispatcher._special_parameter(
            self.dispatcher.special_catalog.min_range_units,
            dash_card,
            dash_slot,
        )
        maximum = self.dispatcher._special_parameter(
            self.dispatcher.special_catalog.max_range_units,
            dash_card,
            dash_slot,
        )
        source_radius = self.combat.collision_radius_units
        distance_sq = (
            dx.to(torch.int64).square()
            + dy.to(torch.int64).square()
            - self.combat.target_distance_discount_sq_units
        ).clamp_min(0)
        inner = minimum + source_radius + target_radius
        outer = maximum + target_radius
        inputs.special_target_in_range.copy_(
            connected
            & has_dash
            & (distance_sq >= inner.square())
            & (distance_sq <= outer.square())
        )

        allocation = deployment.deployment.allocation
        spawned = torch.zeros_like(inputs.spawned)
        spawned.scatter_reduce_(
            1,
            allocation.slots.clamp_min(0),
            allocation.valid,
            reduce="amax",
            include_self=True,
        )
        inputs.spawned.copy_(spawned & active[:, None])
        inputs.death_triggered.copy_(
            active[:, None] & self.combat.present & ~self.combat.alive
        )
        return inputs

    def _compile_straight_ground_routes_(
        self,
        move: torch.Tensor,
        changed_target: torch.Tensor,
    ) -> None:
        """Compile exact cached native routes for changed target keys."""

        movement = self.movement
        plan = plan_standard_routes(
            entity_id=movement.entity_id,
            active=move,
            mover_position_units=movement.position_units,
            target_position_units=movement.target_position_units,
            required_range_units=self.combat.range_units,
            lane_id=movement.lane_id,
            jump_height=movement.jump_height,
            direct_single_node=movement.is_air | movement.is_hover,
            route_capacity=movement.route_capacity,
            cache=self.path_cache,
        )
        direct = movement.is_air | movement.is_hover
        cache_kind = torch.where(direct, 2, 1)
        changed_key = move & (
            changed_target
            | (movement.route_cache_kind != cache_kind)
            | torch.any(movement.route_cache_goal != plan.goal_cell, dim=-1)
            | (movement.route_cache_lane != movement.lane_id)
            | (movement.route_cache_jump != movement.jump_height)
        )
        accepted = changed_key & plan.supported
        route_supported = move & (~changed_key | plan.supported)
        movement.ordinary_supported.copy_(route_supported)
        movement.ordinary_unsupported.copy_(
            torch.where(
                move & ~route_supported,
                torch.ones_like(movement.ordinary_unsupported),
                torch.zeros_like(movement.ordinary_unsupported),
            )
        )
        movement.route_cells.copy_(
            torch.where(
                accepted[..., None, None],
                plan.route_cells,
                movement.route_cells,
            )
        )
        movement.route_count.copy_(
            torch.where(accepted, plan.route_count, movement.route_count)
        )
        movement.ground_path_backwards.copy_(
            torch.where(
                accepted,
                plan.route_moves_backwards,
                movement.ground_path_backwards,
            )
        )
        movement.route_cache_backwards.copy_(
            torch.where(
                accepted,
                plan.route_moves_backwards,
                movement.route_cache_backwards,
            )
        )
        movement.route_cache_kind.copy_(
            torch.where(accepted, cache_kind, movement.route_cache_kind)
        )
        movement.route_cache_goal.copy_(
            torch.where(accepted[..., None], plan.goal_cell, movement.route_cache_goal)
        )
        movement.route_cache_lane.copy_(
            torch.where(accepted, movement.lane_id, movement.route_cache_lane)
        )
        movement.route_cache_jump.copy_(
            torch.where(accepted, movement.jump_height, movement.route_cache_jump)
        )
        empty_cached_route = move & ~accepted & (movement.route_count == 0)
        next_waypoint = torch.where(
            accepted[..., None],
            plan.head_units,
            torch.where(
                empty_cached_route[..., None],
                movement.target_position_units,
                movement.waypoint_units,
            ),
        )
        movement.waypoint_units.copy_(next_waypoint)
        movement.waypoint_valid.copy_(route_supported)

        landing_units = plan.river_landing_cell * 500 + 250
        movement.river_target_units.copy_(
            torch.where(
                accepted[..., None] & plan.river_landing_valid[..., None],
                landing_units,
                movement.river_target_units,
            )
        )
        movement.river_target_valid.copy_(
            torch.where(
                accepted,
                plan.river_landing_valid,
                movement.river_target_valid,
            )
        )

    def _movement_phase(
        self, component_consumed: torch.Tensor | None = None
    ) -> RuntimeMovementResult:
        consumed = (
            torch.zeros(
                (self.batch_size, self.runtime.max_entities),
                dtype=torch.bool,
                device=self.device,
            )
            if component_consumed is None
            else component_consumed.to(device=self.device, dtype=torch.bool)
        )
        if consumed.shape == (self.batch_size,):
            consumed = consumed[:, None].expand(
                self.batch_size, self.runtime.max_entities
            )
        if consumed.shape != (self.batch_size, self.runtime.max_entities):
            raise ValueError(
                "component_consumed must have shape [batch] or [batch, entity]"
            )
        saved_present = self.combat.present.clone()
        saved_slots = self.movement.slot_present.clone()
        # A direct hit can create a physical-slot hole before movement. The
        # surviving attacker has no movement component work after its target
        # died in-range; neutralize that row for the packed collision adapter
        # without moving cleanup ahead of the native object/cleanup boundary.
        physical_ids = self.runtime.battle.entity_id.to(torch.int64)
        sentinel = torch.iinfo(torch.int64).max
        order = torch.argsort(
            torch.where(self.movement.slot_present, physical_ids, sentinel),
            dim=1,
            stable=True,
        )
        physical_to_sorted = torch.empty_like(order)
        sorted_index = torch.arange(
            order.shape[1], dtype=torch.int64, device=self.device
        ).expand_as(order)
        physical_to_sorted.scatter_(1, order, sorted_index)
        sorted_combat = _sorted_slot_clone(self.combat, order)
        sorted_movement = _sorted_slot_clone(self.movement, order)
        assert isinstance(sorted_combat, StationaryCombatState)
        assert isinstance(sorted_movement, TensorMovementAdapter)
        sorted_consumed = _gather_slots(consumed, order)
        sorted_combat.present &= ~sorted_consumed
        sorted_movement.slot_present &= ~sorted_consumed

        def physical_target_to_sorted(target: torch.Tensor) -> torch.Tensor:
            safe = target.clamp_min(0)
            remapped = physical_to_sorted.gather(1, safe)
            return torch.where(target >= 0, remapped, -1)

        sorted_combat.target_slot.copy_(
            physical_target_to_sorted(sorted_combat.target_slot)
        )
        sorted_movement.target_slot.copy_(
            physical_target_to_sorted(sorted_movement.target_slot)
        )
        sorted_core = copy.copy(self.runtime.battle)
        sorted_core.entity_x_units = _gather_slots(
            self.runtime.battle.entity_x_units, order
        )
        sorted_core.entity_y_units = _gather_slots(
            self.runtime.battle.entity_y_units, order
        )
        sorted_facing_x = _gather_slots(self.facing_x_units, order)
        sorted_facing_y = _gather_slots(self.facing_y_units, order)
        view = _MovementRuntimeView(
            core=sorted_core,
            combat=sorted_combat,
            facing_x_units=sorted_facing_x,
            facing_y_units=sorted_facing_y,
        )
        sorted_result = step_runtime_movement_(
            cast(Any, view),
            sorted_movement,
            movement_stop_after_ms=_gather_slots(
                self.movement_stop_after_ms[self._core_catalog_id().clamp_min(0)],
                order,
            ),
            movement_wait_ms=_gather_slots(
                self.movement_wait_ms[self._core_catalog_id().clamp_min(0)],
                order,
            ),
            movement_base_speed_units=_gather_slots(
                self.movement_base_speed_units[self._core_catalog_id().clamp_min(0)],
                order,
            ),
            charge_range_units=_gather_slots(
                self.charge_range_units[self._core_catalog_id().clamp_min(0)],
                order,
            ),
        )

        def sorted_target_to_physical(target: torch.Tensor) -> torch.Tensor:
            safe = target.clamp_min(0)
            remapped = order.gather(1, safe)
            return torch.where(target >= 0, remapped, -1)

        sorted_combat.target_slot.copy_(
            sorted_target_to_physical(sorted_combat.target_slot)
        )
        sorted_movement.target_slot.copy_(
            sorted_target_to_physical(sorted_movement.target_slot)
        )
        _copy_slots_(self.combat, sorted_combat, physical_to_sorted)
        _copy_slots_(self.movement, sorted_movement, physical_to_sorted)
        self.combat.present.copy_(saved_present)
        self.movement.slot_present.copy_(saved_slots)
        self.runtime.battle.entity_x_units.copy_(
            _gather_slots(sorted_core.entity_x_units, physical_to_sorted)
        )
        self.runtime.battle.entity_y_units.copy_(
            _gather_slots(sorted_core.entity_y_units, physical_to_sorted)
        )
        self.facing_x_units.copy_(_gather_slots(sorted_facing_x, physical_to_sorted))
        self.facing_y_units.copy_(_gather_slots(sorted_facing_y, physical_to_sorted))
        result = replace(
            sorted_result,
            ordinary_moved=_gather_slots(
                sorted_result.ordinary_moved, physical_to_sorted
            ),
            collision_only_moved=_gather_slots(
                sorted_result.collision_only_moved, physical_to_sorted
            ),
            river_jump_moved=_gather_slots(
                sorted_result.river_jump_moved, physical_to_sorted
            ),
            route_advanced=_gather_slots(
                sorted_result.route_advanced, physical_to_sorted
            ),
            river_jump_finished=_gather_slots(
                sorted_result.river_jump_finished, physical_to_sorted
            ),
            collision=replace(
                sorted_result.collision,
                accumulated_vector_units=_gather_slots(
                    sorted_result.collision.accumulated_vector_units,
                    physical_to_sorted,
                ),
                contact_count=_gather_slots(
                    sorted_result.collision.contact_count,
                    physical_to_sorted,
                ),
            ),
        )
        self.runtime.mark_unsupported(
            self.runtime.supported & ~result.supported_batch,
            phase=TickPhase.MOVEMENT,
        )
        moved = (
            result.ordinary_moved
            | result.collision_only_moved
            | result.river_jump_moved
        )
        self.runtime.mark_dirty(moved.any(dim=1), phase=TickPhase.MOVEMENT)
        return result

    def _character_object_phase(
        self,
        active: torch.Tensor,
        entity_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        core = self.runtime.battle
        character = self.runtime.entity_pool.active & (
            (core.entity_kind == 0) | (core.entity_kind == 1)
        )
        selected = torch.ones_like(character) if entity_mask is None else entity_mask
        if selected.shape != character.shape:
            raise ValueError("entity_mask must have shape [batch, entity]")
        deploying = (
            active[:, None]
            & character
            & selected
            & core.entity_active
            & (core.entity_deploy_delay > 0.0)
        )
        previous = core.entity_deploy_delay.clone()
        decremented = torch.clamp(previous - core.dt[:, None], min=0.0)
        next_delay = torch.where(decremented <= 1e-9, 0.0, decremented)
        core.entity_deploy_delay.copy_(torch.where(deploying, next_delay, previous))
        completed = deploying & (previous > 0.0) & (core.entity_deploy_delay <= 1e-9)
        core.entity_placement_pending &= ~completed
        core.entity_spawn_hook_pending &= ~completed
        core.entity_spawn_hook_fired |= completed
        self.combat.deploy_remaining.copy_(core.entity_deploy_delay)
        return completed

    def _cleanup(self, active: torch.Tensor) -> EntitySelection:
        runtime = self.runtime
        dead = (
            active[:, None] & runtime.entity_pool.active & ~runtime.battle.entity_active
        )
        removed = runtime.entity_pool.cleanup(dead)
        for owner in (
            runtime.battle,
            runtime.status,
            runtime.phases,
            self.combat,
            self.movement,
            self.status,
            self.mechanics,
            self.dispatcher.passive,
            self.dispatcher.combat_world,
            self.dispatcher.damage_ramp,
            self.dispatcher.dash,
            self.dispatcher.leap,
            self.dispatcher.hook,
        ):
            for descriptor in fields(owner):
                value = getattr(owner, descriptor.name)
                if (
                    isinstance(value, torch.Tensor)
                    and value.ndim >= 2
                    and value.shape[:2] == dead.shape
                ):
                    expanded = dead.reshape(*dead.shape, *((1,) * (value.ndim - 2)))
                    if descriptor.name in {"target_slot"}:
                        value.masked_fill_(expanded, -1)
                    else:
                        value.masked_fill_(expanded, 0)
        for value in (
            self.dispatcher.special_triggered,
            self.dispatcher.forced_movement,
            self.dispatcher.knockback_target_units,
            self.dispatcher.knockback_velocity_work,
            self.dispatcher.initialized_entity_id,
            self.dispatcher.multiple_target_ids,
            self.dispatcher.multiple_target_valid,
            self.dispatcher.underground_active,
        ):
            expanded = dead.reshape(*dead.shape, *((1,) * (value.ndim - 2)))
            value.masked_fill_(expanded, 0)
        runtime.battle.entity_id.copy_(runtime.entity_pool.entity_id)
        self.combat_target_entity_id.masked_fill_(dead, -1)
        self.pending_projectile_max_duration_ms.masked_fill_(dead, 0)
        runtime.phases.death_pending &= ~dead
        runtime.mark_dirty(dead.any(dim=1), phase=TickPhase.CLEANUP_AND_SPAWNS)
        return removed

    def _commit_rows(self, source: TensorResidentEngine, rows: torch.Tensor) -> None:
        _copy_rows_(self.runtime.battle, source.runtime.battle, rows)
        _copy_rows_(self.runtime.battle.rng, source.runtime.battle.rng, rows)
        self.runtime.entity_pool.active[rows] = source.runtime.entity_pool.active[rows]
        self.runtime.entity_pool.next_entity_id[rows] = (
            source.runtime.entity_pool.next_entity_id[rows]
        )
        _copy_rows_(self.runtime.status, source.runtime.status, rows)
        _copy_rows_(self.runtime.phases, source.runtime.phases, rows)
        _copy_rows_(self.runtime.events, source.runtime.events, rows)
        self.runtime.supported[rows] = source.runtime.supported[rows]
        self.runtime.dirty[rows] = source.runtime.dirty[rows]
        self.combat_target_entity_id[rows] = source.combat_target_entity_id[rows]
        for left, right in (
            (self.combat, source.combat),
            (self.movement, source.movement),
            (self.status, source.status),
            (self.mechanics, source.mechanics),
            (self.objects, source.objects),
            (self.objects.objects, source.objects.objects),
            (self.periodic_state, source.periodic_state),
        ):
            _copy_rows_(left, right, rows)
        _copy_terminal_pipeline_rows_(
            self.terminal_pipeline,
            source.terminal_pipeline,
            rows,
        )
        _copy_dispatcher_rows_(self.dispatcher, source.dispatcher, rows)
        self.dispatcher.runtime = self.runtime
        self.dispatcher.mechanics = self.mechanics
        _copy_projectile_bridge_rows_(
            self.projectile_bridge, source.projectile_bridge, rows
        )
        _copy_object_blueprint_rows_(
            self.objects,
            source.objects,
            source.projectile_bridge.blueprint_for_slot[rows].flatten(),
        )
        selected_rows = torch.nonzero(rows, as_tuple=False).flatten()
        self.pending_spells.reset_rows_(
            selected_rows,
            source.pending_spells,
            selected_rows,
        )
        self.continuous_areas.reset_rows_(
            selected_rows,
            source.continuous_areas,
            selected_rows,
        )
        self.graveyards.reset_rows_(
            selected_rows,
            source.graveyards,
            selected_rows,
        )
        self.tornadoes.reset_rows_(
            selected_rows,
            source.tornadoes,
            selected_rows,
        )
        _copy_rows_(self.rolling_spells.state, source.rolling_spells.state, rows)
        _copy_rows_(self.rolling_spells.targets, source.rolling_spells.targets, rows)
        self.royal_delivery.reset_rows_(
            selected_rows,
            source.royal_delivery,
            selected_rows,
        )
        self.facing_x_units[rows] = source.facing_x_units[rows]
        self.facing_y_units[rows] = source.facing_y_units[rows]
        self.pending_projectile_max_duration_ms[rows] = (
            source.pending_projectile_max_duration_ms[rows]
        )
        self.projectile_duration_ms[rows] = source.projectile_duration_ms[rows]
        # Route-cache entries are immutable consequences of standard-arena
        # keys, not battle state. Retaining the speculative cache cannot make
        # a failed row observable and lets successful rows reuse exact paths.
        self.path_cache = source.path_cache
        self.runtime.assert_invariants()

    def step(
        self,
        action_ids: torch.Tensor | None = None,
        *,
        player_order: torch.Tensor | None = None,
    ) -> ResidentTickResult:
        actions = (
            torch.full(
                (self.batch_size, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=self.device,
            )
            if action_ids is None
            else torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        )
        if actions.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        return self._step_transaction(
            self.clone(),
            actions,
            player_order=player_order,
        )

    def _step_transaction(
        self,
        working: TensorResidentEngine,
        actions: torch.Tensor,
        *,
        player_order: torch.Tensor | None,
    ) -> ResidentTickResult:
        """Execute one transaction in a separate, already-initialized engine.

        The ordinary path supplies a fresh clone. Reusable workspaces refresh
        a persistent scratch engine first and call this same routine, keeping
        phase order and fail-closed publication in one implementation.
        """

        if working is self:
            raise ValueError("resident transaction requires separate scratch state")
        if working.batch_size != self.batch_size or working.device != self.device:
            raise ValueError("resident transaction scratch layout differs")
        preflight = self.preflight(actions)
        working.runtime.supported &= preflight.supported
        action_router = working.action_router.apply(
            actions,
            player_order=player_order,
        )
        deployment = action_router.deployment
        spell_ingress = action_router.spell_ingress
        active = (
            preflight.supported
            & action_router.committed
            & ~working.runtime.battle.game_over
        )
        working.runtime.supported &= active

        core = working.runtime.battle
        core.time.add_(torch.where(active, core.dt, 0.0))
        core.tick.add_(active.to(torch.int64))
        core.double_elixir |= active & (core.time >= core.double_elixir_start_time)
        core.overtime |= active & (core.time >= core.overtime_start_time)
        core.triple_elixir |= active & (core.time >= core.triple_elixir_start_time)
        tick_players(core, active)
        working.runtime.mark_dirty(active, phase=TickPhase.CLOCKS_AND_PLAYERS)
        objects_before_pending = working.objects.objects.allocated.clone()
        continuous_before_pending = working.continuous_areas.active.clone()
        graveyards_before_pending = working.graveyards.active.clone()
        tornadoes_before_pending = working.tornadoes.active.clone()
        pending_spells = working._resolve_pending_spells_()
        active &= pending_spells.committed
        working.runtime.supported &= active
        pending_new_objects = (
            working.objects.objects.allocated & ~objects_before_pending
        )
        pending_new_continuous = (
            working.continuous_areas.active & ~continuous_before_pending
        )
        pending_new_graveyards = working.graveyards.active & ~graveyards_before_pending
        pending_new_tornadoes = working.tornadoes.active & ~tornadoes_before_pending
        area_kind_count = (
            working.continuous_areas.active.any(dim=1).to(torch.int8)
            + working.graveyards.active.any(dim=1).to(torch.int8)
            + working.tornadoes.active.any(dim=1).to(torch.int8)
        )
        area_live = area_kind_count > 0
        area_conflict = (area_kind_count > 1) | (
            area_live & working.objects.objects.allocated.any(dim=1)
        )
        retained_spell_live = working.rolling_spells.state.active.any(
            dim=1
        ) | working.royal_delivery.active.any(dim=1)
        retained_spell_conflict = retained_spell_live & (
            area_live
            | working.objects.objects.allocated.any(dim=1)
            | working.terminal_pipeline.state.objects.allocated.any(dim=1)
            | working._periodic_entity_supported().any(dim=1)
        )
        area_conflict |= retained_spell_conflict
        working.runtime.mark_unsupported(
            active & area_conflict,
            phase=TickPhase.OBJECTS,
        )
        active &= ~area_conflict
        working.runtime.supported &= active

        working.mechanics.refresh_new_entities_(working.runtime)
        # Cloak remains outside RESIDENT_DISPATCH_MECHANIC_OPCODES. The
        # dispatcher also owns this hook for future closure, but no admitted
        # row can currently execute both paths with a live Cloak operation.
        working.mechanics.tick_cloak_(working.runtime)
        combat = working._combat_phase(active, pending_spells.stun_applied)
        previously_allocated_objects = working.objects.objects.allocated.clone()
        projectile_supported = working.projectile_bridge.materialize_combat_launches_(
            working.runtime,
            working.objects,
            working.combat,
            combat,
        )
        working._record_new_projectile_durations_(previously_allocated_objects)
        working.runtime.mark_unsupported(
            active & ~projectile_supported,
            phase=TickPhase.COMBAT,
        )
        mechanic_inputs = working._mechanic_inputs(deployment, combat, active)
        terminal_only_entities = working._terminal_entity_supported()
        periodic_entities = working._periodic_entity_supported()
        retained_kind = working.runtime.battle.entity_kind.clone()
        working.runtime.battle.entity_kind.copy_(
            torch.where(
                terminal_only_entities | periodic_entities,
                torch.full_like(retained_kind, 2),
                retained_kind,
            )
        )
        mechanic_result = working.dispatcher.step(mechanic_inputs)
        working.runtime.battle.entity_kind.copy_(retained_kind)
        working.runtime.mark_unsupported(
            active & ~mechanic_result.committed,
            phase=TickPhase.COMBAT,
        )
        working.combat.x_units.copy_(
            working.runtime.battle.entity_x_units.to(torch.int64)
        )
        working.combat.y_units.copy_(
            working.runtime.battle.entity_y_units.to(torch.int64)
        )
        working.combat.hp.copy_(working.runtime.battle.entity_hp)
        working.combat.alive.copy_(working.runtime.battle.entity_active)
        working.movement.position_units.copy_(
            torch.stack(
                (
                    working.runtime.battle.entity_x_units,
                    working.runtime.battle.entity_y_units,
                ),
                dim=-1,
            ).to(torch.int64)
        )
        special_consumed = (
            working.dispatcher.dash.special_active
            | working.dispatcher.dash.special_consumed
        )
        working.movement.special_movement.copy_(
            special_consumed | working.movement.river_jump_active
        )
        combat_death = (working.combat.present & ~working.combat.alive).any(dim=1)
        special_row = special_consumed.any(dim=1)
        # Removing only the special mover creates a non-prefix physical-slot
        # hole in the current collision kernel. A row with any other mobile
        # ordinary troop therefore remains conservatively fail-closed; rows
        # whose other characters are immobile may skip movement as a whole.
        other_mobile = (
            working.movement.slot_present
            & working.movement.entity_active
            & working.movement.is_troop
            & ~working.movement.stunned
            & ~special_consumed
        ).any(dim=1)
        working.runtime.mark_unsupported(
            active & special_row & other_mobile,
            phase=TickPhase.MOVEMENT,
        )
        movement_consumed = (combat_death | special_row)[
            :, None
        ] | working.projectile_bridge.knockback_active
        movement = working._movement_phase(movement_consumed)
        working.runtime.phases.movement_vector_units.copy_(
            working.movement.accumulated_vector_units
        )
        working.runtime.phases.movement_vector_count.copy_(
            working.movement.accumulated_vector_count
        )
        working.runtime.phases.movement_vector_bypasses_cap.copy_(
            working.movement.accumulated_vector_bypasses_cap
        )
        status_event_start = working.runtime.events.count.clone()
        status = step_runtime_status_phase_(
            working.runtime,
            working.status,
            dt=core.dt,
            battle_mask=active,
        )
        working.runtime.battle.entity_hp_integer_kind &= ~(
            active[:, None] & (status.periodic_hitpoint_loss > 0.0)
        )
        working._rewrite_area_periodic_events_(status_event_start)
        completed = working._character_object_phase(active)
        entity_id_before_periodic = working.runtime.battle.entity_id.clone()
        if working.periodic_catalog.spawn.periodic_rows().numel():
            periodic_spawner = step_runtime_periodic_spawners_(
                working.runtime,
                working.periodic_catalog,
                working.periodic_state,
                dt_ms=core.dt * 1_000.0,
                stunned=working.runtime.status.stun_timer > 1e-9,
                spawn_rate=working.dispatcher._native_rate(
                    working.runtime.status.spawn_speed_debuff_multiplier,
                    working.runtime.status.spawn_speed_buff_multiplier,
                ),
                facing_x_units=working.facing_x_units,
                facing_y_units=working.facing_y_units,
            )
            working.runtime.mark_unsupported(
                active & ~periodic_spawner.committed,
                phase=TickPhase.OBJECTS,
            )
            active &= periodic_spawner.committed
            working.runtime.supported &= active
            periodic_children = working.runtime.entity_pool.active & (
                working.runtime.battle.entity_id != entity_id_before_periodic
            )
            completed |= working._character_object_phase(active, periodic_children)
            working._refresh_area_target_planes_(periodic_children)
        else:
            periodic_spawner = None
        working.continuous_areas.active[pending_new_continuous] = False
        working.graveyards.active[pending_new_graveyards] = False
        working.tornadoes.active[pending_new_tornadoes] = False
        area_entity_ids_before = working.runtime.battle.entity_id.clone()
        area_freeze_before = working.runtime.status.freeze_expiry_time.clone()
        continuous_slow_projection, continuous_slow_rows = (
            working._project_continuous_area_slow_status()
        )
        continuous_areas = working.continuous_areas.step_(working.runtime)
        working._publish_continuous_area_slow_projection_(
            continuous_slow_projection,
            continuous_slow_rows & continuous_areas.committed,
        )
        working.runtime.mark_unsupported(
            active & ~continuous_areas.committed,
            phase=TickPhase.OBJECTS,
        )
        active &= continuous_areas.committed
        working.runtime.supported &= active
        graveyards = working.graveyards.step_(working.runtime)
        working.runtime.mark_unsupported(
            active & ~graveyards.committed,
            phase=TickPhase.OBJECTS,
        )
        active &= graveyards.committed
        working.runtime.supported &= active
        graveyard_spawned = (
            working.runtime.entity_pool.active
            & (working.runtime.battle.entity_id != area_entity_ids_before)
            & (
                (working.runtime.battle.entity_kind == 0)
                | (working.runtime.battle.entity_kind == 1)
            )
        )
        working._refresh_area_target_planes_(graveyard_spawned)
        tornadoes = working.tornadoes.step_(working.runtime)
        working.runtime.mark_unsupported(
            active & ~tornadoes.committed,
            phase=TickPhase.OBJECTS,
        )
        active &= tornadoes.committed
        working.runtime.supported &= active

        spell_knockback_before = working.projectile_bridge.knockback_active.clone()
        rolling_ids_before = working.runtime.battle.entity_id.clone()
        rolling_spells = working.rolling_spells.step_(working.runtime)
        working.runtime.mark_unsupported(
            active & ~rolling_spells.committed,
            phase=TickPhase.OBJECTS,
        )
        active &= rolling_spells.committed
        working.runtime.supported &= active
        rolling_spawned = (
            working.runtime.entity_pool.active
            & (working.runtime.battle.entity_id != rolling_ids_before)
            & (
                (working.runtime.battle.entity_kind == 0)
                | (working.runtime.battle.entity_kind == 1)
            )
        )
        delivery_ids_before = working.runtime.battle.entity_id.clone()
        royal_delivery = working.royal_delivery.step_(
            working.runtime,
            dt_ms=torch.round(core.dt * 1_000.0).to(torch.int64),
            battle_mask=active,
        )
        working.runtime.mark_unsupported(
            active & ~royal_delivery.committed,
            phase=TickPhase.OBJECTS,
        )
        active &= royal_delivery.committed
        working.runtime.supported &= active
        working.runtime.battle.entity_hp_integer_kind &= ~(
            (rolling_spells.damage > 0.0) | (royal_delivery.damage > 0.0)
        )

        delivery_spawned = (
            working.runtime.entity_pool.active
            & (working.runtime.battle.entity_id != delivery_ids_before)
            & (
                (working.runtime.battle.entity_kind == 0)
                | (working.runtime.battle.entity_kind == 1)
            )
        )
        completed |= working._character_object_phase(active, rolling_spawned)
        retained_spell_spawned = rolling_spawned | delivery_spawned
        working._refresh_area_target_planes_(retained_spell_spawned)
        retained_catalog = working.runtime.card_catalog_index[
            working.runtime.battle.entity_card
        ].clamp_min(0)
        initialize_spawned_attack_clocks_(
            working._combat_clock_planes(),
            spawned=retained_spell_spawned,
            first_hit_ms=working.first_hit_ms[retained_catalog],
        )

        rolling_knockback = rolling_spells.knockback.valid & active[:, None]
        rolling_endpoint = torch.stack(
            (
                working.runtime.battle.entity_x_units.to(torch.int64),
                working.runtime.battle.entity_y_units.to(torch.int64)
                + rolling_spells.knockback.direction_y.to(torch.int64)
                * rolling_spells.knockback.distance_units,
            ),
            dim=-1,
        )
        rolling_velocity = torch.zeros_like(rolling_spells.knockback.distance_units)
        rolling_accumulated = torch.zeros_like(rolling_velocity)
        for _ in range(32):
            rolling_advance = (
                rolling_accumulated < rolling_spells.knockback.distance_units
            )
            rolling_velocity = torch.where(
                rolling_advance, rolling_velocity + 25, rolling_velocity
            )
            rolling_accumulated = torch.where(
                rolling_advance,
                rolling_accumulated + rolling_velocity,
                rolling_accumulated,
            )
        delivery_knockback = working.royal_delivery.pushback_active & active[:, None]
        combined_knockback = rolling_knockback | delivery_knockback
        working.projectile_bridge.knockback_active |= combined_knockback
        working.projectile_bridge.knockback_entity_id.copy_(
            torch.where(
                combined_knockback,
                working.runtime.battle.entity_id,
                working.projectile_bridge.knockback_entity_id,
            )
        )
        working.projectile_bridge.knockback_target_units.copy_(
            torch.where(
                delivery_knockback[..., None],
                working.royal_delivery.pushback_target_units,
                torch.where(
                    rolling_knockback[..., None],
                    rolling_endpoint,
                    working.projectile_bridge.knockback_target_units,
                ),
            )
        )
        working.projectile_bridge.knockback_velocity_work.copy_(
            torch.where(
                delivery_knockback,
                working.royal_delivery.pushback_velocity_work,
                torch.where(
                    rolling_knockback,
                    rolling_velocity.to(torch.int32),
                    working.projectile_bridge.knockback_velocity_work,
                ),
            )
        )

        area_stun_applied = (
            working.runtime.status.freeze_expiry_time > area_freeze_before + 1e-9
        ) & active[:, None]
        area_stun_transition = apply_stun_interrupt_(
            working._combat_clock_planes(),
            status_applied=area_stun_applied,
            hit_speed_ms=working.combat.hit_speed_ms,
            river_jump_active=working.movement.river_jump_active,
        )
        working.runtime.phases.target_slot.masked_fill_(
            area_stun_transition.transitioned, -1
        )
        working.combat_target_entity_id.masked_fill_(
            area_stun_transition.transitioned, -1
        )
        area_charge_reset = (
            area_stun_transition.charge_reset & working.movement.charge_component
        )
        working.movement.native_charge_progress.masked_fill_(area_charge_reset, 0)
        working.movement.distance_traveled_bits.masked_fill_(area_charge_reset, 0)
        working.combat.stunned |= area_stun_applied
        working.combat.combat_blocked |= area_stun_applied

        area_spawned = (
            working.runtime.entity_pool.active
            & (working.runtime.battle.entity_id != area_entity_ids_before)
            & (
                (working.runtime.battle.entity_kind == 0)
                | (working.runtime.battle.entity_kind == 1)
            )
        ) & ~retained_spell_spawned
        working._refresh_area_target_planes_(area_spawned)
        completed |= working._character_object_phase(active, area_spawned)
        area_spawned_catalog = working.runtime.card_catalog_index[
            working.runtime.battle.entity_card
        ].clamp_min(0)
        initialize_spawned_attack_clocks_(
            working._combat_clock_planes(),
            spawned=area_spawned,
            first_hit_ms=working.first_hit_ms[area_spawned_catalog],
        )
        working.continuous_areas.active[pending_new_continuous] = True
        working.graveyards.active[pending_new_graveyards] = True
        working.tornadoes.active[pending_new_tornadoes] = True
        pending_new_active = working.objects.objects.active[pending_new_objects].clone()
        working.objects.objects.allocated[pending_new_objects] = False
        working.objects.objects.active[pending_new_objects] = False
        terminal_dead_before_objects = (
            active[:, None]
            & working.runtime.entity_pool.active
            & ~working.runtime.battle.entity_active
            & (
                (working.runtime.battle.entity_kind == 0)
                | (working.runtime.battle.entity_kind == 1)
            )
        )
        # runtime_objects historically owns cleanup as well as object updates.
        # Keep character deaths resident until the later terminal cleanup
        # transaction; admitted terminal rows cannot concurrently contain a
        # general retained object, so this cannot make a dead target hittable.
        working.runtime.battle.entity_active |= terminal_dead_before_objects
        entity_id_before_objects = working.runtime.battle.entity_id.clone()
        objects = working.projectile_bridge.step_objects_(
            working.runtime, working.objects
        )
        knockback_started = (
            working.projectile_bridge.knockback_active
            & ~spell_knockback_before
            & working.runtime.entity_pool.active
            & (
                working.projectile_bridge.knockback_entity_id
                == working.runtime.battle.entity_id
            )
        )
        object_stun_transition = apply_stun_interrupt_(
            working._combat_clock_planes(),
            status_applied=working.projectile_bridge.stun_applied,
            hit_speed_ms=working.combat.hit_speed_ms,
            river_jump_active=working.movement.river_jump_active,
        )
        working.runtime.phases.target_slot.masked_fill_(
            object_stun_transition.transitioned, -1
        )
        working.combat_target_entity_id.masked_fill_(
            object_stun_transition.transitioned, -1
        )
        stun_charge_reset = (
            object_stun_transition.charge_reset & working.movement.charge_component
        )
        working.movement.native_charge_progress.masked_fill_(stun_charge_reset, 0)
        working.movement.distance_traveled_bits.masked_fill_(stun_charge_reset, 0)
        charged_before_interrupt = working.movement.charge_component & (
            working.movement.native_charge_progress >= 10_000
        )
        forced_transition = apply_forced_movement_interrupt_(
            working._combat_clock_planes(),
            movement_started=knockback_started,
            hit_speed_ms=working.combat.hit_speed_ms,
            first_hit_ms=working.combat.first_hit_ms,
            charged_attack_ready=charged_before_interrupt,
        )
        charge_reset = (
            forced_transition.charge_reset & working.movement.charge_component
        )
        working.movement.native_charge_progress.masked_fill_(charge_reset, 0)
        working.movement.distance_traveled_bits.masked_fill_(charge_reset, 0)
        working.combat.combat_blocked |= forced_transition.combat_blocked

        spawned_character = (
            working.runtime.entity_pool.active
            & (working.runtime.battle.entity_id != entity_id_before_objects)
            & (
                (working.runtime.battle.entity_kind == 0)
                | (working.runtime.battle.entity_kind == 1)
            )
        )
        spawned_catalog = working.runtime.card_catalog_index[
            working.runtime.battle.entity_card
        ].clamp_min(0)
        initialize_spawned_attack_clocks_(
            working._combat_clock_planes(),
            spawned=spawned_character,
            first_hit_ms=working.first_hit_ms[spawned_catalog],
        )
        working.runtime.battle.entity_active &= ~terminal_dead_before_objects
        working.objects.objects.allocated[pending_new_objects] = True
        working.objects.objects.active[pending_new_objects] = pending_new_active
        if working.terminal_pipeline.catalog.timed_supported.numel():
            before_terminal_cleanup = working.runtime.entity_pool.id_order()
            terminal_dead = (
                active[:, None]
                & working.runtime.entity_pool.active
                & ~working.runtime.battle.entity_active
            )
            terminal = working.terminal_pipeline.step(
                working.runtime,
                terminal_dead,
                facing_x_units=working.facing_x_units,
                facing_y_units=working.facing_y_units,
            )
            working.runtime.mark_unsupported(
                active & ~terminal.committed,
                phase=TickPhase.CLEANUP_AND_SPAWNS,
            )
            active &= terminal.committed
            cleanup = _removed_entities(before_terminal_cleanup, working.runtime)
            working._cleanup(active)
        else:
            terminal = None
            cleanup = working._cleanup(active)
        check_win_conditions(core, active)
        working.runtime.mark_dirty(active, phase=TickPhase.WIN_CONDITIONS)

        phase_supported = working.runtime.phases.supported.all(dim=1)
        committed = active & working.runtime.supported & phase_supported
        self._commit_rows(working, committed)
        return ResidentTickResult(
            preflight=preflight,
            committed=committed,
            deployment=deployment,
            spell_ingress=spell_ingress,
            action_router=action_router,
            pending_spells=pending_spells,
            combat=combat,
            movement=movement,
            status=status,
            objects=objects,
            continuous_areas=continuous_areas,
            graveyards=graveyards,
            tornadoes=tornadoes,
            rolling_spells=rolling_spells,
            royal_delivery=royal_delivery,
            periodic_spawner=periodic_spawner,
            terminal=terminal,
            cleanup=cleanup,
            deployment_completed=completed,
            phase_order=RESIDENT_PHASE_ORDER,
        )


__all__ = [
    "RESIDENT_PHASE_ORDER",
    "RESIDENT_UNSUPPORTED_EFFECT_OPCODES",
    "RESIDENT_UNSUPPORTED_MECHANIC_OPCODES",
    "ResidentPreflight",
    "ResidentPreflightDiagnostics",
    "ResidentTickResult",
    "ResidentUnsupportedReason",
    "TensorResidentEngine",
]
