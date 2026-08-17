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
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.kinematics import LOGIC_TICK_SECONDS

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


@dataclass(frozen=True)
class ResidentPreflight:
    supported: torch.Tensor
    reasons: tuple[str | None, ...]
    unsupported_mechanic_opcodes: tuple[tuple[int, ...], ...]
    unsupported_effect_opcodes: tuple[tuple[int, ...], ...]


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


class TensorResidentEngine:
    """Retained complete-tick owner with atomic row publication."""

    def __init__(
        self,
        *,
        runtime: TensorBattleRuntime,
        deployment: TensorRuntimeDeployment,
        mechanics: TensorRuntimeMechanics,
        movement: TensorMovementAdapter,
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
        facing_x_units: torch.Tensor,
        facing_y_units: torch.Tensor,
    ) -> None:
        self.runtime = runtime
        self.deployment = deployment
        self.mechanics = mechanics
        self.movement = movement
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
        cards = catalog or TensorCardCatalog.compile(
            battles[0].card_loader, names, device=device
        )
        runtime = TensorBattleRuntime.from_battles(
            battles,
            device=device,
            max_entities=max_entities,
            event_capacity=event_capacity,
            catalog=cards,
        )
        action_catalog = TensorActionCatalog.compile(cards)
        deployment_catalog = TensorDeploymentCatalog.compile(
            battles[0].card_loader, cards
        )
        deployment = TensorRuntimeDeployment(
            action_catalog, TensorCommandMaterializer(deployment_catalog)
        )
        deployment.prepare_runtime(runtime)
        mechanics = TensorRuntimeMechanics.from_battles(runtime, battles)
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
        if movement.route_capacity < 64:
            expanded_routes = torch.zeros(
                (runtime.batch_size, max_entities, 64, 2),
                dtype=torch.int64,
                device=runtime.device,
            )
            expanded_routes[:, :, : movement.route_capacity] = movement.route_cells
            movement.route_cells = expanded_routes

        size = len(cards.names)
        uses_projectile = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        death_spawn = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        area_radius = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        self_center = torch.zeros(size, dtype=torch.bool, device=runtime.device)
        sight_clip = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        sight_clip_side = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        first_hit = torch.zeros(size, dtype=torch.int64, device=runtime.device)
        for card_id, name in enumerate(cards.names[1:], start=1):
            stats = battles[0].card_loader.get_card(name)
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
        return cls(
            runtime=runtime,
            deployment=deployment,
            mechanics=mechanics,
            movement=movement,
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
            facing_x_units=self.facing_x_units.clone(),
            facing_y_units=self.facing_y_units.clone(),
        )

    def _core_catalog_id(self) -> torch.Tensor:
        return self.runtime.card_catalog_index[self.runtime.battle.entity_card]

    def preflight(self, action_ids: torch.Tensor | None = None) -> ResidentPreflight:
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
        supported = (
            self.runtime.supported
            & ~self.runtime.battle.game_over
            & self.objects.static_supported
        )
        reasons: list[str | None] = [None] * self.batch_size
        mechanic_rows: list[tuple[int, ...]] = []
        effect_rows: list[tuple[int, ...]] = []
        catalog_id = self._core_catalog_id()
        active_character = self.runtime.entity_pool.active & (
            (self.runtime.battle.entity_kind == 0)
            | (self.runtime.battle.entity_kind == 1)
        )
        safe = catalog_id.clamp_min(0)
        known = (catalog_id >= 0) | (self.runtime.battle.entity_tower_slot >= 0)
        for row in range(self.batch_size):
            mechanics = tuple(
                sorted(
                    {
                        int(value)
                        for value in self.runtime.catalog.mechanic_opcode[
                            safe[row][active_character[row]]
                        ]
                        .flatten()
                        .tolist()
                        if int(value) != 0
                    }
                )
            )
            effects = tuple(
                sorted(
                    {
                        int(value)
                        for value in self.runtime.catalog.effect_opcode[
                            safe[row][active_character[row]]
                        ]
                        .flatten()
                        .tolist()
                        if int(value) != 0
                    }
                )
            )
            mechanic_rows.append(mechanics)
            effect_rows.append(effects)
            if self.device.type not in {"cpu", "cuda"}:
                supported[row] = False
                reasons[row] = "resident exact phases require CPU or CUDA"
            elif not bool(known[row][active_character[row]].all().item()):
                supported[row] = False
                reasons[row] = "active character card is absent from the catalog"
            elif mechanics:
                supported[row] = False
                reasons[row] = f"unsupported mechanic opcodes {mechanics}"
            elif effects:
                supported[row] = False
                reasons[row] = f"unsupported character effect opcodes {effects}"
            elif bool(
                (
                    self.uses_projectile[safe[row]]
                    & active_character[row]
                    & (self.runtime.battle.entity_tower_slot[row] < 0)
                )
                .any()
                .item()
            ):
                supported[row] = False
                reasons[row] = "resident combat projectile launch is not integrated"
            elif bool(
                (self.death_spawn[safe[row]] & active_character[row]).any().item()
            ):
                supported[row] = False
                reasons[row] = "resident character death spawn is not integrated"
            elif not bool(self.objects.static_supported[row].item()):
                supported[row] = False
                reasons[row] = self.objects.unsupported_reasons[row]

        # Pure action ingress contributes opcodes before any speculative state
        # or RNG is mutated.
        action_state = self.deployment.action_state(self.runtime)
        ingress = self.deployment.kernel.ingress(
            action_state,
            actions,
            legal_mask=self.deployment.kernel.legal_action_mask(action_state),
        )
        for command in range(int(ingress.commands.card_id.numel())):
            row = int(ingress.commands.battle_index[command].item())
            card = int(ingress.commands.card_id[command].item())
            opcodes = tuple(
                sorted(
                    int(value)
                    for value in self.runtime.catalog.mechanic_opcode[card].tolist()
                    if int(value) != 0
                )
            )
            effects = tuple(
                sorted(
                    int(value)
                    for value in self.runtime.catalog.effect_opcode[card].tolist()
                    if int(value) != 0
                )
            )
            if opcodes:
                mechanic_rows[row] = tuple(
                    sorted(set(mechanic_rows[row]) | set(opcodes))
                )
            if effects:
                effect_rows[row] = tuple(sorted(set(effect_rows[row]) | set(effects)))
            kind = int(self.runtime.catalog.kind[card].item())
            payload_supported = bool(
                self.deployment.materializer.catalog.supported_payload[card].item()
            )
            if bool(ingress.commands.is_ability[command].item()):
                supported[row] = False
                reasons[row] = (
                    reasons[row] or "champion action is not resident-integrated"
                )
            elif kind == 3:
                supported[row] = False
                reasons[row] = reasons[row] or "spell action is not resident-integrated"
            elif opcodes:
                supported[row] = False
                reasons[row] = reasons[row] or f"unsupported mechanic opcodes {opcodes}"
            elif effects:
                supported[row] = False
                reasons[row] = reasons[row] or f"unsupported effect opcodes {effects}"
            elif not payload_supported:
                supported[row] = False
                reasons[row] = reasons[row] or "mixed deployment payload is unsupported"
        return ResidentPreflight(
            supported=supported,
            reasons=tuple(reasons),
            unsupported_mechanic_opcodes=tuple(mechanic_rows),
            unsupported_effect_opcodes=tuple(effect_rows),
        )

    def _refresh_planes(self) -> torch.Tensor:
        runtime = self.runtime
        core = runtime.battle
        present = runtime.entity_pool.active
        old_id = self.combat.entity_id.clone()
        new = present & ((old_id != core.entity_id) | ~self.combat.present)
        catalog_id = runtime.card_catalog_index[core.entity_card]
        safe = catalog_id.clamp_min(0)
        known = catalog_id >= 0
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
        self.combat.damage.copy_(self.runtime.catalog.damage[safe])
        self.combat.range_units.copy_(
            self.runtime.catalog.range_units[safe].to(torch.int64)
        )
        self.combat.sight_range_units.copy_(
            self.runtime.catalog.sight_range_units[safe].to(torch.int64)
        )
        radius = self.runtime.catalog.collision_radius_units[safe].to(torch.int64)
        self.combat.collision_radius_units.copy_(torch.where(radius > 0, radius, 500))
        self.combat.sight_clip_units.copy_(self.sight_clip_units[safe])
        self.combat.sight_clip_side_units.copy_(self.sight_clip_side_units[safe])
        self.combat.can_attack_air.copy_(self.runtime.catalog.attacks_air[safe])
        self.combat.can_attack_ground.copy_(self.runtime.catalog.attacks_ground[safe])
        self.combat.buildings_only.copy_(self.runtime.catalog.buildings_only[safe])
        self.combat.uses_projectile.copy_(self.uses_projectile[safe])
        self.combat.airborne.copy_(self.runtime.catalog.is_air_unit[safe])
        self.combat.building_target.copy_(core.entity_kind == 1)
        self.combat.area_radius_units.copy_(self.area_radius_units[safe])
        self.combat.self_as_aoe_center.copy_(self.self_as_aoe_center[safe])
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
            self.runtime.catalog.hit_speed_ms[safe].to(torch.int64)
        )
        self.combat.first_hit_ms.copy_(self.first_hit_ms[safe])
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
        direct_waypoint = move & (
            self.movement.is_air | (self.movement.route_count == 0) | changed_target
        )
        self.movement.waypoint_units.copy_(
            torch.where(
                direct_waypoint.unsqueeze(-1),
                target_position,
                self.movement.waypoint_units,
            )
        )
        self.movement.waypoint_valid.copy_(move)
        self.movement.ordinary_supported.copy_(move)
        self._compile_straight_ground_routes_(changed_target)

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

    def _compile_straight_ground_routes_(self, changed: torch.Tensor) -> None:
        """Compile exact half-grid heads for unobstructed same-side movement."""

        movement = self.movement
        for row, slot in torch.nonzero(changed, as_tuple=False).tolist():
            if bool(movement.is_air[row, slot].item()):
                movement.route_count[row, slot] = 0
                continue
            start_y = int(movement.position_units[row, slot, 1].item())
            target_x = int(movement.target_position_units[row, slot, 0].item())
            target_y = int(movement.target_position_units[row, slot, 1].item())
            same_lower = start_y < 15_000 and target_y < 15_000
            same_upper = start_y > 17_000 and target_y > 17_000
            if not (same_lower or same_upper) or start_y == target_y:
                movement.ordinary_supported[row, slot] = False
                continue
            direction = 1 if target_y > start_y else -1
            first_y = start_y // 500 + direction
            terminal_y = target_y // 500
            y_cells = list(range(first_y, terminal_y, direction))
            if not y_cells or len(y_cells) > movement.route_capacity:
                movement.ordinary_supported[row, slot] = False
                continue
            x_cell = target_x // 500
            movement.route_cells[row, slot].zero_()
            movement.route_cells[row, slot, : len(y_cells), 0] = x_cell
            movement.route_cells[row, slot, : len(y_cells), 1] = torch.tensor(
                y_cells, dtype=torch.int64, device=self.device
            )
            movement.route_count[row, slot] = len(y_cells)
            movement.waypoint_units[row, slot] = torch.tensor(
                (x_cell * 500 + 250, y_cells[0] * 500 + 250),
                dtype=torch.int64,
                device=self.device,
            )
            movement.waypoint_valid[row, slot] = True

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
        self.combat.present[consumed] = False
        self.movement.slot_present[consumed] = False
        view = _MovementRuntimeView(
            core=self.runtime.battle,
            combat=self.combat,
            facing_x_units=self.facing_x_units,
            facing_y_units=self.facing_y_units,
        )
        result = step_runtime_movement_(view, self.movement)  # type: ignore[arg-type]
        self.combat.present[consumed] = saved_present[consumed]
        self.movement.slot_present[consumed] = saved_slots[consumed]
        self.runtime.battle.entity_x_units.copy_(view.core.entity_x_units)  # type: ignore[attr-defined]
        self.runtime.battle.entity_y_units.copy_(view.core.entity_y_units)  # type: ignore[attr-defined]
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
        preflight = self.preflight(actions)
        working = self.clone()
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
    "ResidentTickResult",
    "TensorResidentEngine",
]
