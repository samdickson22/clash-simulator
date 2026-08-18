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

from .actions import NO_OP_ACTION, TensorActionCatalog
from .catalog import EFFECT_OPCODE, MECHANIC_OPCODE, TensorCardCatalog
from .combat import (
    CombatStepResult,
    StationaryCombatState,
    step_stationary_combat_,
)
from .combat_adapter import project_stationary_combat
from .deployment import TensorCommandMaterializer, TensorDeploymentCatalog
from .entity_pool import EntitySelection
from .movement_adapter import TensorMovementAdapter
from .resident_pathing import (
    TensorResidentPathCache,
    plan_standard_routes,
)
from .runtime_deployment import (
    TensorRuntimeDeployment,
    TensorRuntimeDeploymentResult,
)
from .runtime_mechanics import TensorRuntimeMechanics
from .runtime_movement import RuntimeMovementResult, step_runtime_movement_
from .runtime_objects import (
    RuntimeObjectPhaseResult,
    TensorRuntimeObjectPhase,
    step_runtime_object_phase_,
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
from .tick_common import check_win_conditions, tick_players

RESIDENT_PHASE_ORDER = tuple(TickPhase)
RESIDENT_UNSUPPORTED_MECHANIC_OPCODES = {
    opcode: name for name, opcode in MECHANIC_OPCODE.items()
}
RESIDENT_UNSUPPORTED_EFFECT_OPCODES = {
    opcode: name for name, opcode in EFFECT_OPCODE.items()
}


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
        if parent is None:
            continue
        for payload in (
            parent.summon_character_data,
            parent.summon_character_second_data,
        ):
            if not isinstance(payload, dict):
                continue
            child_name = str(payload.get("name", "") or "")
            if not child_name or child_name == parent_name:
                continue
            rarity = str(payload.get("rarity", parent.rarity or "Common"))
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
    combat: CombatStepResult
    movement: RuntimeMovementResult
    status: RuntimeStatusPhaseResult
    objects: RuntimeObjectPhaseResult
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
        movement: TensorMovementAdapter,
        path_cache: TensorResidentPathCache,
        status: TensorRuntimeStatusPhase,
        objects: TensorRuntimeObjectPhase,
        combat: StationaryCombatState,
        uses_projectile: torch.Tensor,
        death_spawn: torch.Tensor,
        area_radius_units: torch.Tensor,
        self_as_aoe_center: torch.Tensor,
        sight_clip_units: torch.Tensor,
        sight_clip_side_units: torch.Tensor,
        first_hit_ms: torch.Tensor,
        jump_height: torch.Tensor,
        facing_x_units: torch.Tensor,
        facing_y_units: torch.Tensor,
    ) -> None:
        self.runtime = runtime
        self.deployment = deployment
        self.mechanics = mechanics
        self.movement = movement
        self.path_cache = path_cache
        self.status = status
        self.objects = objects
        self.combat = combat
        self.uses_projectile = uses_projectile
        self.death_spawn = death_spawn
        self.area_radius_units = area_radius_units
        self.self_as_aoe_center = self_as_aoe_center
        self.sight_clip_units = sight_clip_units
        self.sight_clip_side_units = sight_clip_side_units
        self.first_hit_ms = first_hit_ms
        self.jump_height = jump_height
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
        mechanics = TensorRuntimeMechanics.from_battles(runtime, mechanic_battles)
        status = TensorRuntimeStatusPhase.from_battles(runtime, battles)
        objects = TensorRuntimeObjectPhase.from_battles(
            runtime, battles, max_objects=max_objects
        )
        projection = project_stationary_combat(
            battles,
            cards,
            capacity=max_entities,
            device=device,
        )
        combat = projection.state
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
        death_spawn = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        area_radius = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        self_center = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        sight_clip = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        sight_clip_side = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        first_hit = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        jump_height = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        for card_id, name in enumerate(cards.names[1:], start=1):
            stats = catalog_loader.get_card(name)
            if stats is None:
                continue
            uses_projectile[card_id] = bool(
                getattr(stats, "projectile_speed", 0)
                or getattr(stats, "projectile_data", None)
            )
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
        return cls(
            runtime=runtime,
            deployment=deployment,
            mechanics=mechanics,
            movement=movement,
            path_cache=path_cache,
            status=status,
            objects=objects,
            combat=combat,
            uses_projectile=uses_projectile,
            death_spawn=death_spawn,
            area_radius_units=area_radius,
            self_as_aoe_center=self_center,
            sight_clip_units=sight_clip,
            sight_clip_side_units=sight_clip_side,
            first_hit_ms=first_hit,
            jump_height=jump_height,
            facing_x_units=movement.facing_units[..., 0].clone(),
            facing_y_units=movement.facing_units[..., 1].clone(),
        )

    def clone(self) -> TensorResidentEngine:
        runtime = self.runtime.clone()
        # TensorBattleRuntime.fork currently shares this nested mutable owner.
        runtime.battle.rng = self.runtime.battle.rng.clone()
        return type(self)(
            runtime=runtime,
            deployment=self.deployment,
            mechanics=self.mechanics.clone(),
            movement=_clone_tensor_dataclass(self.movement),  # type: ignore[arg-type]
            # Entries are immutable deterministic functions of standard-arena
            # keys and are not battle-observable. Speculative rows may safely
            # warm one shared cache, including rows which later fail closed.
            path_cache=self.path_cache,
            status=self.status.clone(),
            objects=_clone_object_phase(self.objects),
            combat=_clone_tensor_dataclass(self.combat),  # type: ignore[arg-type]
            uses_projectile=self.uses_projectile,
            death_spawn=self.death_spawn,
            area_radius_units=self.area_radius_units,
            self_as_aoe_center=self.self_as_aoe_center,
            sight_clip_units=self.sight_clip_units,
            sight_clip_side_units=self.sight_clip_side_units,
            first_hit_ms=self.first_hit_ms,
            jump_height=self.jump_height,
            facing_x_units=self.facing_x_units.clone(),
            facing_y_units=self.facing_y_units.clone(),
        )

    def _core_catalog_id(self) -> torch.Tensor:
        return self.runtime.card_catalog_index[self.runtime.battle.entity_card]

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
        safe = catalog_id.clamp_min(0)
        known = (catalog_id >= 0) | (self.runtime.battle.entity_tower_slot >= 0)
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

        if self.device.type not in {"cpu", "cuda"}:
            publish(torch.ones_like(base_supported), ResidentUnsupportedReason.DEVICE)
        publish(
            (~known & active_character).any(dim=1),
            ResidentUnsupportedReason.UNKNOWN_CHARACTER,
        )
        publish(mechanic_present.any(dim=1), ResidentUnsupportedReason.ACTIVE_MECHANIC)
        publish(effect_present.any(dim=1), ResidentUnsupportedReason.ACTIVE_EFFECT)
        publish(
            (
                self.uses_projectile[safe]
                & active_character
                & (self.runtime.battle.entity_tower_slot < 0)
            ).any(dim=1),
            ResidentUnsupportedReason.PROJECTILE_COMBAT,
        )
        publish(
            (self.death_spawn[safe] & active_character).any(dim=1),
            ResidentUnsupportedReason.DEATH_SPAWN,
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
        command_has_mechanic = (command_mechanics > 0).any(dim=1)
        command_has_effect = (command_effects > 0).any(dim=1)
        command_kind = self.runtime.catalog.kind[command_cards]
        command_payload = self.deployment.materializer.catalog.supported_payload[
            command_cards
        ]

        def command_rows_with(mask: torch.Tensor) -> torch.Tensor:
            rows = torch.zeros(self.batch_size, dtype=torch.int32, device=self.device)
            rows.scatter_add_(0, command_rows, mask.to(torch.int32))
            return rows > 0

        publish(
            command_rows_with(ingress.commands.is_ability),
            ResidentUnsupportedReason.CHAMPION_ACTION,
        )
        publish(
            command_rows_with(command_kind == 3),
            ResidentUnsupportedReason.SPELL_ACTION,
        )
        publish(
            command_rows_with(command_has_mechanic),
            ResidentUnsupportedReason.ACTION_MECHANIC,
        )
        publish(
            command_rows_with(command_has_effect),
            ResidentUnsupportedReason.ACTION_EFFECT,
        )
        publish(
            command_rows_with(~command_payload),
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
        catalog_known = catalog_id >= 0
        crown = core.entity_tower_slot >= 0
        known = catalog_known | crown
        character = present & ((core.entity_kind == 0) | (core.entity_kind == 1))
        troop = character & (core.entity_kind == 0)

        self.combat.present.copy_(present)
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
                self.runtime.catalog.attacks_air[safe],
                self.combat.can_attack_air,
            )
        )
        self.combat.can_attack_ground.copy_(
            torch.where(
                catalog_known,
                self.runtime.catalog.attacks_ground[safe],
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
        self.combat.target_distance_discount_sq_units.zero_()
        self.combat.reserved_lethal.zero_()
        self.combat.outgoing_damage_multiplier.fill_(1.0)
        self.combat.incoming_damage_multiplier.fill_(1.0)

        movement = self.movement
        movement.slot_present.copy_(present)
        movement.entity_id.copy_(core.entity_id)
        movement.entity_active.copy_(core.entity_active & present)
        movement.entity_kind.copy_(core.entity_kind.to(torch.int64))
        movement.player_id.copy_(core.entity_player.to(torch.int64))
        movement.position_units.copy_(
            torch.stack((core.entity_x_units, core.entity_y_units), dim=-1).to(
                torch.int64
            )
        )
        movement.is_troop.copy_(troop)
        movement.is_air.copy_(self.runtime.catalog.is_air_unit[safe])
        movement.is_hover.copy_(self.runtime.catalog.is_hover_unit[safe])
        movement.jump_height.copy_(self.jump_height[safe])
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
        movement.mechanic_free.copy_(self.runtime.catalog.mechanic_count[safe] == 0)
        movement.stunned.copy_(self.combat.stunned)
        movement.forced_movement.zero_()
        movement.special_movement.zero_()
        movement.death_spawn_travel.zero_()
        movement.knockback_active.zero_()
        movement.kamikaze_primed.zero_()
        movement.charge_component.zero_()
        movement.movement_cycle.zero_()
        movement.avoidance_prepass_required.zero_()
        movement.ordinary_unsupported.zero_()
        movement.river_unsupported.fill_(1)
        movement.ordinary_supported.copy_(troop & known)
        movement.river_jump_supported.zero_()
        movement.pending_vector_consumed.copy_(
            torch.where(
                new,
                torch.ones_like(movement.pending_vector_consumed),
                movement.pending_vector_consumed,
            )
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

    def _combat_phase(self, active: torch.Tensor) -> CombatStepResult:
        self._refresh_planes()
        self.combat.present &= active[:, None]
        result = step_stationary_combat_(self.combat, LOGIC_TICK_SECONDS)
        runtime = self.runtime
        runtime.battle.entity_hp.copy_(
            torch.where(active[:, None], self.combat.hp, runtime.battle.entity_hp)
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
            active[:, None] & self.combat.present & (self.combat.target_slot >= 0)
        )
        self.facing_x_units.copy_(torch.where(observed, dx, self.facing_x_units))
        self.facing_y_units.copy_(torch.where(observed, dy, self.facing_y_units))
        move = (
            observed
            & self.combat.alive
            & (self.combat.kind == 0)
            & (self.combat.deploy_remaining <= 1e-9)
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
            torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
            if component_consumed is None
            else component_consumed.to(device=self.device, dtype=torch.bool)
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
            torch.where(self.runtime.entity_pool.active, physical_ids, sentinel),
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
        sorted_combat.present[consumed] = False
        sorted_movement.slot_present[consumed] = False

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

    def _character_object_phase(self, active: torch.Tensor) -> torch.Tensor:
        core = self.runtime.battle
        character = self.runtime.entity_pool.active & (
            (core.entity_kind == 0) | (core.entity_kind == 1)
        )
        deploying = (
            active[:, None]
            & character
            & core.entity_active
            & (core.entity_deploy_delay > 0.0)
        )
        previous = core.entity_deploy_delay.clone()
        core.entity_deploy_delay.copy_(
            torch.where(
                deploying,
                torch.clamp(previous - core.dt[:, None], min=0.0),
                previous,
            )
        )
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
        runtime.battle.entity_id.copy_(runtime.entity_pool.entity_id)
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
        for left, right in (
            (self.combat, source.combat),
            (self.movement, source.movement),
            (self.status, source.status),
            (self.mechanics, source.mechanics),
            (self.objects, source.objects),
            (self.objects.objects, source.objects.objects),
        ):
            _copy_rows_(left, right, rows)
        self.facing_x_units[rows] = source.facing_x_units[rows]
        self.facing_y_units[rows] = source.facing_y_units[rows]
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
        deployment = working.deployment.apply(
            working.runtime, actions, player_order=player_order
        )
        active = (
            preflight.supported
            & deployment.committed
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

        working.mechanics.refresh_new_entities_(working.runtime)
        working.mechanics.tick_cloak_(working.runtime)
        combat = working._combat_phase(active)
        combat_death = (working.combat.present & ~working.combat.alive).any(dim=1)
        movement = working._movement_phase(combat_death)
        status = step_runtime_status_phase_(
            working.runtime,
            working.status,
            dt=core.dt,
            battle_mask=active,
        )
        completed = working._character_object_phase(active)
        objects = step_runtime_object_phase_(
            working.runtime, working.objects, battle_mask=active
        )
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
            combat=combat,
            movement=movement,
            status=status,
            objects=objects,
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
