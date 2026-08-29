"""End-to-end runtime for the practical, unified tensor Gym.

The runtime owns the small policy/action state and the dense combat pool.  A
tick resolves the two player requests in stable player order, advances combat,
regenerates fractional elixir, resolves match outcomes, and returns an already
projected policy transition.  It has no dependency on ``BattleState``, scalar
entities, or the retained resident verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES

from .actions import NO_OP_ACTION
from .simple_abilities import (
    FastAbilityActivationResult,
    FastAbilityCatalog,
    FastAbilityPlayerView,
    FastAbilityState,
    FastAbilityStepResult,
    activate_fast_abilities_,
    fast_ability_player_view,
    step_fast_abilities_,
)
from .simple_actions import FastActionIngressResult, FastActionKernel, FastActionState
from .simple_attack_effects import (
    FastEffectAllocationResult,
    FastEffectCommands,
    FastNumericEffectCommands,
    allocate_fast_attack_effects_,
)
from .simple_attack_locks import FastAttackLockState, FastAttackTimingCatalog
from .simple_catalog import FastCardCatalog
from .simple_damage_ramp import (
    FastDamageRampParameters,
    FastDamageRampState,
    pre_attack_damage_ramp_,
)
from .simple_death_burst import (
    FastDeathBurstCatalog,
    FastDeathBurstCommands,
    FastDeathBurstState,
    FastDeathBurstStepResult,
    step_fast_death_bursts_,
)
from .simple_effects import (
    FAST_STATUS_STUN,
    FastEffectState,
    FastEffectStepResult,
    step_fast_effects,
)
from .simple_engine import FastTensorGym
from .simple_impulse import FastRadialImpulseResult, compute_fast_radial_impulse
from .simple_lifecycle import (
    FastLifecycleState,
    FastLifecycleStepResult,
    step_fast_lifecycle_,
)
from .simple_modifiers import (
    FastChargeParameters,
    FastModifierState,
    advance_fast_charge_,
    pre_move_charge_multipliers,
)
from .simple_outcomes import (
    FAST_TOWER_SLOT_COUNT,
    FastMatchRules,
    FastOutcomeTracker,
    FastTowerSpec,
    crown_tower_hp,
    initialize_crown_towers_,
    update_king_activation_,
)
from .simple_payload_containers import (
    FastPayloadAllocationResult,
    FastPayloadContainerState,
    FastPayloadEffectAllocationResult,
    FastPayloadEffectCommands,
    FastPayloadStepResult,
    allocate_fast_payload_containers_,
    allocate_fast_payload_effects_,
    step_fast_payload_containers_,
)
from .simple_periodic_spawn import (
    FastPeriodicSpawnCatalog,
    FastPeriodicSpawnCommands,
    FastPeriodicSpawnState,
    step_periodic_spawns_,
)
from .simple_policy_mechanics import (
    FastPolicyMechanicCatalog,
    FastPolicyMechanicState,
    FastPolicyVisibilityStep,
    FastPolicyVisibilityView,
    fast_policy_visibility_view,
    step_fast_policy_visibility_,
)
from .simple_positive_buffs import (
    FastPositiveBuffAdvanceResult,
    FastPositiveBuffApplyResult,
    FastPositiveBuffAreaAllocationResult,
    FastPositiveBuffAreaState,
    FastPositiveBuffAreaStepResult,
    FastPositiveBuffState,
    advance_fast_positive_buffs_,
    allocate_fast_positive_buff_areas_,
    apply_fast_positive_area_buffs_,
    fast_positive_buff_view,
    step_fast_positive_buff_areas_,
)
from .simple_projection import (
    SimpleProjectedObservation,
    SimpleProjectionInputs,
    SimpleTensorProjector,
)
from .simple_river_jump import FastRiverJumpCatalog, FastRiverJumpState
from .simple_rolling_spells import (
    FAST_ROLLING_NO_SPAWN,
    FastRollingAllocationResult,
    FastRollingSpellCommands,
    FastRollingSpellState,
    FastRollingStepResult,
    allocate_fast_rolling_spells_,
    step_fast_rolling_spells_,
)
from .simple_scheduled_spawns import (
    FastScheduledAreaEffectCommands,
    FastScheduledCastAllocationResult,
    FastScheduledCastCommands,
    FastScheduledCastState,
    FastScheduledCastStepResult,
    FastScheduledSpawnCommands,
    allocate_fast_scheduled_casts_,
    step_fast_scheduled_casts_,
)
from .simple_spawn_blueprints import (
    FastAtomicSpawnCommands,
    FastSpawnAllocationResult,
    FastSpawnBlueprintCatalog,
    FastSpawnCommands,
    allocate_fast_atomic_spawns_,
    allocate_fast_spawns_,
    death_payload_container_commands,
    impact_spawn_commands,
    payload_spawn_commands,
    positive_area_activation_commands,
    rolling_spawn_commands,
)
from .simple_state import FAST_KIND_BUILDING, FastGymState
from .simple_travel import (
    FAST_TRAVEL_LEAP,
    FAST_TRAVEL_TRANSIT,
    FAST_TRAVEL_UNDERGROUND,
    FAST_TRAVEL_WINDUP,
    FastTravelCatalog,
    FastTravelState,
    FastTravelStepResult,
    FastTravelView,
    advance_fast_travel_,
    fast_travel_view,
    travel_impact_radial_impulse_inputs,
)
from .simple_travel_effects import (
    FastTravelEffectAllocationResult,
    allocate_fast_travel_effects_,
)
from .simple_triggered_impacts import (
    FAST_TRIGGER_ATTACK_COMMIT,
    FAST_TRIGGER_DEATH,
    FAST_TRIGGER_DEPLOY_COMPLETE,
    FAST_TRIGGER_IMPACT,
    FastTriggeredImpactCatalog,
    FastTriggeredImpactCommands,
    FastTriggeredImpactEvents,
    FastTriggeredImpactTargets,
    resolve_fast_triggered_impacts,
    triggered_commands_to_effect_state,
    triggered_commands_to_impulse_inputs,
)


def _same_device(left: torch.device, right: torch.device) -> bool:
    """Treat an unspecified accelerator index as its current concrete device."""

    return left.type == right.type and (
        left.index is None or right.index is None or left.index == right.index
    )


@dataclass(frozen=True)
class SimpleGymRuntimeStep:
    """One fully projected, native transition accepted by SimpleGymAdapter."""

    observation: SimpleProjectedObservation
    action_success: torch.Tensor
    reward: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor
    native_ticks: torch.Tensor
    committed: torch.Tensor
    ability_activation: FastAbilityActivationResult | None
    abilities: FastAbilityStepResult | None
    effect_allocation: FastEffectAllocationResult
    effects: FastEffectStepResult
    lifecycle: FastLifecycleStepResult
    payloads: FastPayloadStepResult
    payload_effect_allocation: FastPayloadEffectAllocationResult
    positive_area_step: FastPositiveBuffAreaStepResult
    positive_buff_apply: FastPositiveBuffApplyResult
    positive_buff_advance: FastPositiveBuffAdvanceResult
    positive_area_allocation: FastPositiveBuffAreaAllocationResult | None
    positive_area_effect_allocation: FastPayloadEffectAllocationResult | None
    payload_container_allocation: FastPayloadAllocationResult | None
    atomic_spawn_allocation: FastSpawnAllocationResult | None
    spawn_allocation: FastSpawnAllocationResult | None
    payload_spawn_allocation: FastSpawnAllocationResult | None
    periodic_spawn_allocation: FastSpawnAllocationResult | None
    scheduled_cast_allocation: FastScheduledCastAllocationResult | None
    scheduled_casts: FastScheduledCastStepResult | None
    scheduled_effect_allocation: FastPayloadEffectAllocationResult | None
    scheduled_spawn_allocation: FastSpawnAllocationResult | None
    rolling_allocation: FastRollingAllocationResult
    rolling: FastRollingStepResult
    rolling_spawn_allocation: FastSpawnAllocationResult | None
    death_bursts: tuple[FastDeathBurstStepResult, FastDeathBurstStepResult]
    death_burst_effects: tuple[FastEffectStepResult, FastEffectStepResult]
    policy_visibility: FastPolicyVisibilityStep
    travel: FastTravelStepResult | None
    travel_effect_allocation: FastTravelEffectAllocationResult | None
    travel_effects: FastEffectStepResult | None
    travel_impulse: FastRadialImpulseResult | None
    triggered: FastTriggeredRuntimeStep | None


@dataclass(frozen=True)
class FastTriggeredEventAllocation:
    """Stable bounded admission telemetry for one tick's trigger candidates."""

    accepted: torch.Tensor
    capacity_rejected: torch.Tensor
    accepted_count: torch.Tensor
    capacity_rejected_count: torch.Tensor


@dataclass(frozen=True)
class FastTriggeredEffectAllocation:
    """Stable allocation telemetry for persistent triggered area effects."""

    accepted: torch.Tensor
    capacity_rejected: torch.Tensor
    effect_slot: torch.Tensor


@dataclass(frozen=True)
class FastTriggeredRuntimeStep:
    """Device-resident telemetry for the generalized triggered-impact seam."""

    event_allocation: FastTriggeredEventAllocation
    events: FastTriggeredImpactEvents
    commands: FastTriggeredImpactCommands
    effect_allocation: FastTriggeredEffectAllocation
    effects: FastEffectStepResult
    impulse: FastRadialImpulseResult


class SimpleGymRuntime:
    """Compose action, combat, outcome, and projection into one native Gym."""

    def __init__(
        self,
        deck_ids: torch.Tensor,
        catalog: FastCardCatalog,
        tower_spec: FastTowerSpec,
        rules: FastMatchRules,
        *,
        entity_token_lookup: torch.Tensor,
        hand_token_lookup: torch.Tensor,
        max_entities: int = 64,
        max_effects: int = 64,
        max_payload_containers: int = 32,
        max_scheduled_casts: int = 16,
        max_rolling_spells: int = 16,
        starting_elixir: float = 6.0,
        max_elixir: float = 10.0,
        include_privileged_critic: bool = False,
        tick_seconds: float = 0.05,
        double_elixir_tick: int | None = None,
        triple_elixir_tick: int | None = None,
        spawn_blueprints: FastSpawnBlueprintCatalog | None = None,
        policy_mechanics: FastPolicyMechanicCatalog | None = None,
        ability_catalog: FastAbilityCatalog | None = None,
        travel_catalog: FastTravelCatalog | None = None,
        river_jump_catalog: FastRiverJumpCatalog | None = None,
        triggered_impact_catalog: FastTriggeredImpactCatalog | None = None,
        attack_timings: FastAttackTimingCatalog | None = None,
        knockback_immune_by_card: torch.Tensor | None = None,
        max_triggered_events: int = 8,
        max_triggered_effects: int = 32,
    ) -> None:
        if deck_ids.ndim != 3 or tuple(deck_ids.shape[1:]) != (2, 8):
            raise ValueError("deck_ids must have shape [batch, 2, 8]")
        if deck_ids.device != catalog.device:
            raise ValueError("deck_ids and catalog must use the same device")
        if max_entities <= FAST_TOWER_SLOT_COUNT:
            raise ValueError("max_entities must leave room beyond six tower slots")
        if tick_seconds <= 0:
            raise ValueError("tick_seconds must be positive")
        if double_elixir_tick is not None and double_elixir_tick < 0:
            raise ValueError("double_elixir_tick must be non-negative")
        if triple_elixir_tick is not None and triple_elixir_tick < 0:
            raise ValueError("triple_elixir_tick must be non-negative")
        if policy_mechanics is not None:
            if policy_mechanics.size != catalog.size:
                raise ValueError("policy mechanic catalog must align with cards")
            if not _same_device(policy_mechanics.device, catalog.device):
                raise ValueError("policy mechanics and cards must share a device")
        if ability_catalog is not None:
            if ability_catalog.card_capacity != catalog.size:
                raise ValueError("ability catalog must align with cards")
            if not _same_device(ability_catalog.device, catalog.device):
                raise ValueError("ability catalog and cards must share a device")
        if travel_catalog is not None:
            if travel_catalog.size != catalog.size:
                raise ValueError("travel catalog must align with cards")
            if not _same_device(travel_catalog.device, catalog.device):
                raise ValueError("travel catalog and cards must share a device")
        if river_jump_catalog is not None:
            if river_jump_catalog.size != catalog.size:
                raise ValueError("river jump catalog must align with cards")
            if not _same_device(river_jump_catalog.device, catalog.device):
                raise ValueError("river jump catalog and cards must share a device")
        if triggered_impact_catalog is not None:
            if triggered_impact_catalog.card_capacity != catalog.size:
                raise ValueError("triggered impact catalog must align with cards")
            if not _same_device(triggered_impact_catalog.device, catalog.device):
                raise ValueError("triggered impacts and cards must share a device")
        if attack_timings is not None:
            if attack_timings.size != catalog.size:
                raise ValueError("attack timings must align with cards")
            if not _same_device(attack_timings.device, catalog.device):
                raise ValueError("attack timings and cards must share a device")
        if max_triggered_events < 1 or max_triggered_effects < 1:
            raise ValueError("triggered pool capacities must be positive")
        if knockback_immune_by_card is not None:
            if knockback_immune_by_card.shape != (catalog.size,):
                raise ValueError("knockback immunity must align with cards")
            if knockback_immune_by_card.device != catalog.device:
                raise ValueError("knockback immunity must use the catalog device")
            if knockback_immune_by_card.dtype != torch.bool:
                raise ValueError("knockback immunity must be bool")
        if spawn_blueprints is not None:
            if spawn_blueprints.fast_cards is not catalog:
                raise ValueError(
                    "spawn_blueprints must own the supplied expanded fast catalog"
                )
            if not _same_device(spawn_blueprints.device, catalog.device):
                raise ValueError("spawn blueprints and catalog must share a device")
            safe_deck = deck_ids.clamp(0, catalog.size - 1)
            public_deck = (
                (deck_ids >= 0)
                & (deck_ids < catalog.size)
                & spawn_blueprints.public_card_mask[safe_deck]
            )
            if not bool(public_deck.all()):
                raise ValueError("deck_ids may contain only public catalog rows")
        if entity_token_lookup.ndim != 2 or entity_token_lookup.shape[1] < catalog.size:
            raise ValueError("entity_token_lookup must cover every catalog row")
        if hand_token_lookup.ndim != 1 or hand_token_lookup.shape[0] < catalog.size:
            raise ValueError("hand_token_lookup must cover every catalog row")
        if spawn_blueprints is not None:
            synthetic = ~spawn_blueprints.public_card_mask
            if bool((hand_token_lookup[: catalog.size][synthetic] != 0).any()):
                raise ValueError("synthetic child rows must not have hand tokens")
            runtime_blueprint = (
                spawn_blueprints.blueprint_supported
                & (
                    spawn_blueprints.root_payload_supported[
                        spawn_blueprints.root_card_id
                    ]
                )
            )
            child = spawn_blueprints.child_card_id[runtime_blueprint]
            child = child[child > 0]
            nested_child = spawn_blueprints.container_nested_child_card_id
            nested_child = nested_child[nested_child > 0]
            typed_child = torch.cat((child, nested_child)).unique()
            child_kind = catalog.kind[typed_child].to(torch.int64)
            body_token = entity_token_lookup[child_kind, typed_child]
            if bool((body_token <= 0).any()):
                raise ValueError(
                    "every runtime-supported synthetic child needs a typed entity token"
                )

        self.state = FastGymState.empty(
            int(deck_ids.shape[0]),
            max_entities=max_entities,
            device=catalog.device,
        )
        initialize_crown_towers_(self.state, tower_spec)
        tower_shape = (self.state.batch_size, FAST_TOWER_SLOT_COUNT)

        def tower_rows(
            value: torch.Tensor | None,
            *,
            dtype: torch.dtype,
            fill: float | bool,
        ) -> torch.Tensor:
            if value is None:
                return torch.full(
                    tower_shape, fill, dtype=dtype, device=self.state.device
                )
            return value.reshape(1, FAST_TOWER_SLOT_COUNT).expand(
                self.state.batch_size, -1
            )

        self._tower_effect_kind = tower_rows(
            tower_spec.effect_kind,
            dtype=torch.int8,
            fill=-1,
        )
        self._tower_preload_cooldown_floor = tower_rows(
            tower_spec.preload_cooldown_floor_ticks,
            dtype=torch.int32,
            fill=0,
        )
        self._tower_projectile_speed = tower_rows(
            tower_spec.projectile_speed_units_per_tick,
            dtype=torch.int32,
            fill=0,
        )
        self._tower_projectile_start_radius = tower_rows(
            tower_spec.projectile_start_radius_units,
            dtype=torch.int32,
            fill=0,
        )
        self._tower_effect_radius = tower_rows(
            tower_spec.effect_radius_units,
            dtype=torch.int32,
            fill=0,
        )
        self._tower_hits_air = tower_rows(
            tower_spec.hits_air,
            dtype=torch.bool,
            fill=True,
        )
        self._tower_hits_ground = tower_rows(
            tower_spec.hits_ground,
            dtype=torch.bool,
            fill=True,
        )
        self._tower_affects_hidden = tower_rows(
            tower_spec.affects_hidden,
            dtype=torch.bool,
            fill=False,
        )
        self._king_activation_delay_ticks = (
            tower_spec.king_activation_ticks
            if tower_spec.king_activation_ticks is not None
            else torch.zeros(2, dtype=torch.int32, device=self.state.device)
        )
        self.action_state = FastActionState.from_decks(
            deck_ids,
            starting_elixir=starting_elixir,
            max_elixir=max_elixir,
        )
        self.action_kernel = FastActionKernel(catalog)
        self.attack_timings = attack_timings
        self.attack_locks = (
            FastAttackLockState.empty(
                self.state.batch_size,
                self.state.max_entities,
                device=self.state.device,
            )
            if attack_timings is not None
            else None
        )
        self.river_jump_catalog = river_jump_catalog
        self.river_jumps = (
            FastRiverJumpState.empty(
                self.state.batch_size,
                self.state.max_entities,
                device=self.state.device,
            )
            if river_jump_catalog is not None
            else None
        )
        collision_radius_override = torch.zeros_like(self.state.x_units)
        if tower_spec.collision_radius_units is not None:
            collision_radius_override[:, :FAST_TOWER_SLOT_COUNT] = tower_rows(
                tower_spec.collision_radius_units,
                dtype=torch.int32,
                fill=0,
            )
        self.combat = FastTensorGym(
            self.state,
            catalog,
            reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
            attack_timings=attack_timings,
            attack_locks=self.attack_locks,
            collision_radius_override_units=collision_radius_override,
            river_jump_catalog=river_jump_catalog,
            river_jump_state=self.river_jumps,
        )
        self.policy_catalog = (
            policy_mechanics
            if policy_mechanics is not None
            else FastPolicyMechanicCatalog.empty(catalog.size, device=self.state.device)
        )
        self.policy_mechanics = FastPolicyMechanicState.empty(
            self.state.batch_size,
            max_entities=self.state.max_entities,
            device=self.state.device,
        )
        self.ability_catalog = ability_catalog
        self.abilities = FastAbilityState.empty_like(self.state)
        self.travel_catalog = travel_catalog
        self.triggered_impact_catalog = triggered_impact_catalog
        self.travel = FastTravelState.empty(
            self.state.batch_size,
            max_entities=self.state.max_entities,
            device=self.state.device,
        )
        self.effects = FastEffectState.empty(
            self.state.batch_size,
            max_effects=max_effects,
            device=self.state.device,
        )
        self.travel_effects = FastEffectState.empty(
            self.state.batch_size,
            max_effects=max_entities,
            device=self.state.device,
        )
        self.death_effects = FastEffectState.empty(
            self.state.batch_size,
            max_effects=max_entities,
            device=self.state.device,
        )
        self.triggered_events = FastTriggeredImpactEvents.empty(
            self.state.batch_size,
            max_events=max_triggered_events,
            device=self.state.device,
        )
        self.triggered_effects = FastEffectState.empty(
            self.state.batch_size,
            max_effects=max_triggered_effects,
            device=self.state.device,
        )
        self._triggered_death_stable_id = torch.zeros_like(self.state.stable_id)
        self.death_burst_catalog = (
            spawn_blueprints.death_burst_catalog
            if spawn_blueprints is not None
            else FastDeathBurstCatalog.empty(catalog.size, device=self.state.device)
        )
        self.death_bursts = FastDeathBurstState.empty_like(self.state)
        self.payload_containers = FastPayloadContainerState.empty(
            self.state.batch_size,
            max_containers=max_payload_containers,
            device=self.state.device,
        )
        self.positive_buff_areas = FastPositiveBuffAreaState.empty(
            self.state.batch_size,
            max_areas=max_payload_containers,
            device=self.state.device,
        )
        self.positive_buffs = FastPositiveBuffState.empty(
            self.state.batch_size,
            max_entities=max_entities,
            device=self.state.device,
        )
        self.lifecycle = FastLifecycleState.empty_like(self.state)
        self.modifiers = FastModifierState.empty(
            self.state.batch_size,
            max_entities=self.state.max_entities,
            device=self.state.device,
        )
        self.damage_ramp = FastDamageRampState.empty(
            self.state.batch_size,
            max_entities=self.state.max_entities,
            device=self.state.device,
        )
        self.periodic_catalog = (
            FastPeriodicSpawnCatalog.from_spawn_blueprints(spawn_blueprints)
            if spawn_blueprints is not None
            else None
        )
        self.periodic_spawns = (
            FastPeriodicSpawnState.empty(
                self.state.batch_size,
                self.state.max_entities,
                device=self.state.device,
            )
            if self.periodic_catalog is not None
            else None
        )
        self.scheduled_casts = (
            FastScheduledCastState.empty(
                self.state.batch_size,
                max_casts=max_scheduled_casts,
                device=self.state.device,
            )
            if spawn_blueprints is not None
            else None
        )
        self.rolling_spells = FastRollingSpellState.empty(
            self.state.batch_size,
            max_rollers=max_rolling_spells,
            max_hit_records=max_entities,
            device=self.state.device,
        )
        entity_shape = (self.state.batch_size, self.state.max_entities)
        self.entity_status_kind = torch.zeros(
            entity_shape, dtype=torch.int8, device=self.state.device
        )
        self.entity_status_ticks = torch.zeros(
            entity_shape, dtype=torch.int32, device=self.state.device
        )
        self.entity_slow_ticks = torch.zeros(
            (*entity_shape, self.action_kernel.catalog.size),
            dtype=torch.int32,
            device=self.state.device,
        )
        self.entity_attack_clock_fraction = torch.zeros(
            entity_shape, dtype=torch.float32, device=self.state.device
        )
        self.entity_kamikaze_ticks = torch.zeros(
            entity_shape, dtype=torch.int32, device=self.state.device
        )
        self.entity_kamikaze_windup_ticks = torch.zeros_like(self.entity_kamikaze_ticks)
        self.effect_consume_source_id = torch.zeros(
            (self.state.batch_size, max_effects),
            dtype=torch.int64,
            device=self.state.device,
        )
        self.death_effect_consume_source_id = torch.zeros(
            (self.state.batch_size, max_entities),
            dtype=torch.int64,
            device=self.state.device,
        )
        self.travel_effect_consume_source_id = torch.zeros(
            (self.state.batch_size, max_entities),
            dtype=torch.int64,
            device=self.state.device,
        )
        self._travel_spawned = torch.zeros_like(self.state.active)
        self._travel_interrupted = torch.zeros_like(self.state.active)
        self.knockback_immune_by_card = (
            knockback_immune_by_card
            if knockback_immune_by_card is not None
            else torch.zeros(catalog.size, dtype=torch.bool, device=self.state.device)
        )
        self.outcomes = FastOutcomeTracker(self.state, rules)
        self.tick_seconds = float(tick_seconds)
        self.double_elixir_tick = double_elixir_tick
        self.triple_elixir_tick = triple_elixir_tick
        self.spawn_blueprints = spawn_blueprints

        batch = self.state.batch_size
        device = self.state.device
        self._projection_hand_ids = torch.zeros(
            (batch, 2, 5), dtype=torch.int64, device=device
        )
        self._double_elixir = torch.zeros(batch, dtype=torch.bool, device=device)
        self._triple_elixir = torch.zeros(batch, dtype=torch.bool, device=device)
        self._ability_cooldown = torch.zeros(
            (batch, 2), dtype=torch.float32, device=device
        )
        self._ability_duration = torch.zeros_like(self._ability_cooldown)
        self._refill_cooldown_ms = torch.zeros_like(self._ability_cooldown)
        self._entity_special = torch.zeros(
            entity_shape, dtype=torch.bool, device=device
        )
        self._entity_invisible = torch.zeros_like(self._entity_special)
        self._entity_hidden = torch.zeros_like(self._entity_special)
        self._effect_owners = (
            torch.arange(2, dtype=torch.int8, device=device)
            .view(1, 2)
            .expand(batch, -1)
        )
        self._spell_source_slots = torch.tensor(
            (2, 5), dtype=torch.int64, device=device
        )
        command_shape = (batch, 2 + self.state.max_entities)

        def tower_command_profile(
            tower_value: torch.Tensor,
            *,
            dtype: torch.dtype,
            fill: float | bool,
        ) -> torch.Tensor:
            result = torch.full(command_shape, fill, dtype=dtype, device=device)
            result[:, 2 : 2 + FAST_TOWER_SLOT_COUNT] = tower_value
            return result

        numeric_enabled = torch.zeros(command_shape, dtype=torch.bool, device=device)
        numeric_enabled[:, 2 : 2 + FAST_TOWER_SLOT_COUNT] = (
            self._tower_effect_kind >= 0
        ) & (self.state.card_id[:, :FAST_TOWER_SLOT_COUNT] == 0)
        self._numeric_effect_commands = FastNumericEffectCommands(
            enabled=numeric_enabled,
            effect_kind=tower_command_profile(
                self._tower_effect_kind, dtype=torch.int8, fill=-1
            ),
            projectile_speed_units_per_tick=tower_command_profile(
                self._tower_projectile_speed, dtype=torch.int32, fill=0
            ),
            projectile_start_radius_units=tower_command_profile(
                self._tower_projectile_start_radius, dtype=torch.int32, fill=0
            ),
            damage=tower_command_profile(
                self.state.damage[:, :FAST_TOWER_SLOT_COUNT],
                dtype=torch.float32,
                fill=0.0,
            ),
            radius_units=tower_command_profile(
                self._tower_effect_radius, dtype=torch.int32, fill=0
            ),
            tower_damage_multiplier=torch.ones(
                command_shape, dtype=torch.float32, device=device
            ),
            building_damage_multiplier=torch.ones(
                command_shape, dtype=torch.float32, device=device
            ),
            hits_air=tower_command_profile(
                self._tower_hits_air, dtype=torch.bool, fill=True
            ),
            hits_ground=tower_command_profile(
                self._tower_hits_ground, dtype=torch.bool, fill=True
            ),
            affects_hidden=tower_command_profile(
                self._tower_affects_hidden, dtype=torch.bool, fill=False
            ),
        )
        tower_command_slice = slice(2, 2 + FAST_TOWER_SLOT_COUNT)
        self._tower_effect_kind = self._numeric_effect_commands.effect_kind[
            :, tower_command_slice
        ]
        self._tower_projectile_speed = (
            self._numeric_effect_commands.projectile_speed_units_per_tick[
                :, tower_command_slice
            ]
        )
        self._tower_projectile_start_radius = (
            self._numeric_effect_commands.projectile_start_radius_units[
                :, tower_command_slice
            ]
        )
        self._tower_effect_radius = self._numeric_effect_commands.radius_units[
            :, tower_command_slice
        ]
        self._tower_hits_air = self._numeric_effect_commands.hits_air[
            :, tower_command_slice
        ]
        self._tower_hits_ground = self._numeric_effect_commands.hits_ground[
            :, tower_command_slice
        ]
        self._tower_affects_hidden = self._numeric_effect_commands.affects_hidden[
            :, tower_command_slice
        ]
        entity_slots = torch.arange(
            self.state.max_entities, dtype=torch.int64, device=device
        ).view(1, -1)
        self._king_source_mask = (entity_slots == 2) | (entity_slots == 5)
        self._cooldown_floor_ticks = torch.zeros_like(self.state.cooldown_ticks)
        self._cooldown_floor_ticks[:, :FAST_TOWER_SLOT_COUNT] = (
            self._tower_preload_cooldown_floor
        )
        projection_inputs = SimpleProjectionInputs(
            entity_token_lookup=entity_token_lookup,
            hand_token_lookup=hand_token_lookup,
            hand_card_ids=self._projection_hand_ids,
            public_visibility=torch.ones(
                (batch, 2, max_entities), dtype=torch.bool, device=device
            ),
            elixir=self.action_state.elixir,
            max_elixir=self.action_state.max_elixir,
            tower_hp=crown_tower_hp(self.state),
            tower_max_hp=self.state.max_hp[:, :FAST_TOWER_SLOT_COUNT].view(batch, 2, 3),
            double_elixir=self._double_elixir,
            triple_elixir=self._triple_elixir,
            overtime=self.outcomes.overtime,
            ability_cooldown=self._ability_cooldown,
            ability_duration=self._ability_duration,
            refill_cooldown_ms=self._refill_cooldown_ms,
            entity_special=self._entity_special,
            entity_invisible=self._entity_invisible,
            entity_hidden=self._entity_hidden,
            max_ticks=rules.tiebreak_ticks,
        )
        self.projector = SimpleTensorProjector(
            self.state,
            projection_inputs,
            include_privileged_critic=include_privileged_critic,
        )
        self._refresh_policy_state()
        self._initial_templates = self._capture_initial_templates()

    @property
    def device(self) -> torch.device:
        return self.state.device

    @property
    def batch_size(self) -> int:
        return int(self.state.batch_size)

    def _row_state_objects(self) -> dict[str, Any]:
        """Return every retained owner whose tensor rows define a battle.

        Catalogs, arena constants, and projection lookup tables are immutable
        setup authority and are deliberately absent.  Keeping this registry in
        one place makes reset and speculative battle forks share the exact same
        state boundary.
        """

        objects: dict[str, Any] = {
            "state": self.state,
            "action": self.action_state,
            "effects": self.effects,
            "travel": self.travel,
            "travel_effects": self.travel_effects,
            "death_effects": self.death_effects,
            "triggered_events": self.triggered_events,
            "triggered_effects": self.triggered_effects,
            "death_bursts": self.death_bursts,
            "payload_containers": self.payload_containers,
            "positive_buff_areas": self.positive_buff_areas,
            "positive_buffs": self.positive_buffs,
            "lifecycle": self.lifecycle,
            "modifiers": self.modifiers,
            "damage_ramp": self.damage_ramp,
            "rolling_spells": self.rolling_spells,
            "navigation": self.combat.navigation.state,
            "policy_mechanics": self.policy_mechanics,
            "abilities": self.abilities,
        }
        if self.attack_locks is not None:
            objects["attack_locks"] = self.attack_locks
        if self.river_jumps is not None:
            objects["river_jumps"] = self.river_jumps
        if self.periodic_spawns is not None:
            objects["periodic_spawns"] = self.periodic_spawns
        if self.scheduled_casts is not None:
            objects["scheduled_casts"] = self.scheduled_casts
        return objects

    def _runtime_row_tensors(self) -> dict[str, torch.Tensor]:
        """Return retained runtime tensors which do not belong to a dataclass."""

        return {
            "entity_status_kind": self.entity_status_kind,
            "entity_status_ticks": self.entity_status_ticks,
            "entity_slow_ticks": self.entity_slow_ticks,
            "entity_attack_clock_fraction": self.entity_attack_clock_fraction,
            "entity_kamikaze_ticks": self.entity_kamikaze_ticks,
            "entity_kamikaze_windup_ticks": self.entity_kamikaze_windup_ticks,
            "effect_consume_source_id": self.effect_consume_source_id,
            "death_effect_consume_source_id": self.death_effect_consume_source_id,
            "travel_effect_consume_source_id": self.travel_effect_consume_source_id,
            "travel_spawned": self._travel_spawned,
            "travel_interrupted": self._travel_interrupted,
            "triggered_death_stable_id": self._triggered_death_stable_id,
            "projection_hand_ids": self._projection_hand_ids,
            "double_elixir": self._double_elixir,
            "triple_elixir": self._triple_elixir,
            "ability_cooldown": self._ability_cooldown,
            "ability_duration": self._ability_duration,
            "refill_cooldown_ms": self._refill_cooldown_ms,
            "public_visibility": self.projector.inputs.public_visibility,
            "combat_spawned_mask": self.combat.spawned_mask,
            "combat_target_unavailable": self.combat._target_unavailable,
            "entity_special": self._entity_special,
            "entity_invisible": self._entity_invisible,
            "entity_hidden": self._entity_hidden,
        }

    def _row_state_tensor_groups(self) -> dict[str, dict[str, torch.Tensor]]:
        groups = {
            group: {
                descriptor.name: tensor
                for descriptor in fields(owner)
                if isinstance((tensor := getattr(owner, descriptor.name)), torch.Tensor)
            }
            for group, owner in self._row_state_objects().items()
        }
        groups["outcomes"] = {
            "initial_tower_hp": self.outcomes.initial_tower_hp,
            "previous_tower_hp": self.outcomes.previous_tower_hp,
            "previous_crowns": self.outcomes.previous_crowns,
            "overtime": self.outcomes.overtime,
        }
        groups["runtime"] = self._runtime_row_tensors()
        return groups

    def _capture_initial_templates(self) -> dict[str, dict[str, torch.Tensor]]:
        """Capture the constructed episode state as device-resident tensors.

        These templates deliberately contain no ``BattleState`` or scalar
        simulator objects.  Selective resets therefore remain ordinary dense
        tensor mutations and do not rebuild the runtime, catalog, or projector.
        """

        return {
            group: {name: tensor.clone() for name, tensor in tensors.items()}
            for group, tensors in self._row_state_tensor_groups().items()
        }

    def copy_rows_from_(
        self,
        source: Any,
        source_rows: torch.Tensor,
    ) -> None:
        """Replace this runtime with exact selected rows from ``source``.

        The destination runtime is a preallocated speculative arena.  It may
        have a different batch size, but it must have been constructed from the
        same immutable setup authority and with identical capacities.  Rows may
        repeat, which expands one live battle into many independent candidate
        continuations without materializing scalar simulators.

        This copies only retained episode state.  Policy recurrence and rollout
        history remain collector-owned and must be forked by their owner.
        """

        if not isinstance(source, SimpleGymRuntime):
            raise TypeError("source must be a SimpleGymRuntime")
        if source_rows.shape != (self.batch_size,):
            raise ValueError("source_rows must have shape [destination batch]")
        if source_rows.device != self.device or source.device != self.device:
            raise ValueError("fork runtimes and source_rows must share a device")
        if source_rows.dtype != torch.int64:
            raise ValueError("source_rows must be int64")
        if bool(((source_rows < 0) | (source_rows >= source.batch_size)).any()):
            raise IndexError("source row is outside the source runtime")
        immutable_pairs = (
            (self.action_kernel.catalog, source.action_kernel.catalog),
            (self.spawn_blueprints, source.spawn_blueprints),
            (self.policy_catalog, source.policy_catalog),
            (self.ability_catalog, source.ability_catalog),
            (self.travel_catalog, source.travel_catalog),
            (self.river_jump_catalog, source.river_jump_catalog),
            (self.triggered_impact_catalog, source.triggered_impact_catalog),
            (self.attack_timings, source.attack_timings),
            (
                self.projector.inputs.entity_token_lookup,
                source.projector.inputs.entity_token_lookup,
            ),
            (
                self.projector.inputs.hand_token_lookup,
                source.projector.inputs.hand_token_lookup,
            ),
        )
        if any(destination is not origin for destination, origin in immutable_pairs):
            raise ValueError("fork runtimes must share immutable setup authority")
        if (
            self.tick_seconds != source.tick_seconds
            or self.double_elixir_tick != source.double_elixir_tick
            or self.triple_elixir_tick != source.triple_elixir_tick
            or self.outcomes.rules is not source.outcomes.rules
        ):
            raise ValueError("fork runtimes must share match timing and rules")

        destination_groups = self._row_state_tensor_groups()
        source_groups = source._row_state_tensor_groups()
        if destination_groups.keys() != source_groups.keys():
            raise ValueError("fork runtimes have different retained state owners")
        for group, destination_tensors in destination_groups.items():
            source_tensors = source_groups[group]
            if destination_tensors.keys() != source_tensors.keys():
                raise ValueError(f"fork runtime state differs for {group}")
            for name, destination in destination_tensors.items():
                origin = source_tensors[name]
                if (
                    destination.shape[1:] != origin.shape[1:]
                    or destination.dtype != origin.dtype
                ):
                    raise ValueError(f"fork runtime tensor differs for {group}.{name}")

        for group, destination_tensors in destination_groups.items():
            source_tensors = source_groups[group]
            for name, destination in destination_tensors.items():
                destination.copy_(source_tensors[name].index_select(0, source_rows))

    @staticmethod
    def _restore_rows_(
        destination: torch.Tensor,
        template: torch.Tensor,
        reset_mask: torch.Tensor,
    ) -> None:
        row_mask = reset_mask.view(
            reset_mask.shape[0], *((1,) * (destination.ndim - 1))
        )
        destination.copy_(torch.where(row_mask, template, destination))

    def reset_rows(
        self,
        reset_mask: torch.Tensor,
        deck_ids: torch.Tensor | None = None,
    ) -> SimpleProjectedObservation:
        """Start fresh episodes for selected batch rows in-place.

        ``reset_mask`` is a boolean ``[batch]`` tensor on the runtime device.
        Optional ordered decks replace the initial hand and cycle for selected
        rows only.  Runtime templates, outcome reward baselines, effect pools,
        and episode-local stable IDs are restored without reconstructing any
        Python simulator objects.  Recurrent policy history remains adapter
        owned and is intentionally unaffected by this method.
        """

        if reset_mask.shape != (self.batch_size,):
            raise ValueError("reset_mask must have shape [batch]")
        if reset_mask.device != self.device:
            raise ValueError("reset_mask must use the runtime device")
        if reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool")
        if deck_ids is not None:
            if deck_ids.shape != (self.batch_size, 2, 8):
                raise ValueError("deck_ids must have shape [batch, 2, 8]")
            if deck_ids.device != self.device:
                raise ValueError("deck_ids must use the runtime device")
            if deck_ids.dtype != torch.int64:
                raise ValueError("deck_ids must be int64")
            if self.spawn_blueprints is not None:
                safe_deck = deck_ids.clamp(0, self.action_kernel.catalog.size - 1)
                public_deck = (
                    (deck_ids >= 0)
                    & (deck_ids < self.action_kernel.catalog.size)
                    & self.spawn_blueprints.public_card_mask[safe_deck]
                )
                if not bool(public_deck.all()):
                    raise ValueError("deck_ids may contain only public catalog rows")

        for group, destinations in self._row_state_tensor_groups().items():
            for name, destination in destinations.items():
                self._restore_rows_(
                    destination,
                    self._initial_templates[group][name],
                    reset_mask,
                )

        if deck_ids is not None:
            hand = deck_ids[:, :, :NUM_HAND_SLOTS]
            cycle = deck_ids[:, :, NUM_HAND_SLOTS:]
            self._restore_rows_(self.action_state.hand_ids, hand, reset_mask)
            self._restore_rows_(self.action_state.cycle_ids, cycle, reset_mask)

        projected_hand = torch.cat(
            (self.action_state.hand_ids, self.action_state.own_next[..., None]),
            dim=2,
        )
        self._restore_rows_(self._projection_hand_ids, projected_hand, reset_mask)
        return self.projector.project(self._legal_action_mask())

    def _phase_multiplier(self) -> torch.Tensor:
        multiplier = torch.ones(
            self.batch_size, dtype=torch.float32, device=self.device
        )
        if self.double_elixir_tick is not None:
            multiplier = torch.where(
                self.state.tick >= self.double_elixir_tick,
                torch.full_like(multiplier, 2.0),
                multiplier,
            )
        if self.triple_elixir_tick is not None:
            multiplier = torch.where(
                self.state.tick >= self.triple_elixir_tick,
                torch.full_like(multiplier, 3.0),
                multiplier,
            )
        return multiplier

    def _stunned(self) -> torch.Tensor:
        """Return the shared independently-timed stun plane."""

        return (self.entity_status_kind == FAST_STATUS_STUN) & (
            self.entity_status_ticks > 0
        )

    def _entity_airborne_target(self) -> torch.Tensor:
        """Compose permanent and temporary serialized target planes."""

        safe_card = self.state.card_id.clamp(0, self.action_kernel.catalog.size - 1)
        airborne = self.action_kernel.catalog.is_air[safe_card]
        if self.river_jumps is not None:
            airborne = airborne | self.river_jumps.active
        return airborne

    def _entity_collision_radius_units(self) -> torch.Tensor:
        """Return the common serialized body edge for combat and movement."""

        safe_card = self.state.card_id.clamp(0, self.action_kernel.catalog.size - 1)
        return self.action_kernel.catalog.collision_radius_units[safe_card].maximum(
            self.combat._collision_radius_override_units
        )

    def _ability_player_view(self) -> FastAbilityPlayerView | None:
        """Refresh entity ownership and expose only player-ordered ability state."""

        if self.ability_catalog is None:
            return None
        return fast_ability_player_view(
            self.state,
            self.abilities,
            self.ability_catalog,
            elixir=self.action_state.elixir,
            stunned=self._stunned(),
            player_alive=self.action_state.player_alive,
        )

    def _refresh_policy_state(self) -> None:
        tower_hp = crown_tower_hp(self.state)
        tower_alive = tower_hp > 0
        self.action_state.tower_alive.copy_(tower_alive)
        self.action_state.player_alive.copy_(
            tower_alive[:, :, 2] & ~self.state.game_over[:, None]
        )
        ability = self._ability_player_view()
        if ability is None:
            self._ability_cooldown.zero_()
            self._ability_duration.zero_()
        else:
            self._ability_cooldown.copy_(ability.cooldown_fraction)
            self._ability_duration.copy_(ability.duration_fraction)
        self._projection_hand_ids[:, :, :4].copy_(self.action_state.hand_ids)
        self._projection_hand_ids[:, :, 4].copy_(self.action_state.own_next)
        if self.double_elixir_tick is not None:
            self._double_elixir.copy_(self.state.tick >= self.double_elixir_tick)
        if self.triple_elixir_tick is not None:
            self._triple_elixir.copy_(self.state.tick >= self.triple_elixir_tick)
        multiplier = self._phase_multiplier()[:, None]
        fractional = torch.ceil(self.action_state.elixir) - self.action_state.elixir
        refill_ms = fractional.clamp_min(0.0) * 2_800.0 / multiplier
        self._refill_cooldown_ms.copy_(
            torch.where(
                self.action_state.elixir < self.action_state.max_elixir,
                refill_ms,
                torch.zeros_like(refill_ms),
            )
        )

    def observe(self) -> SimpleProjectedObservation:
        self._publish_policy_visibility_(self._policy_visibility_view())
        self._publish_travel_mechanics_(self._travel_view())
        self._publish_river_jump_mechanics_()
        self._refresh_policy_state()
        return self.projector.project(self._legal_action_mask())

    def _policy_visibility_view(self) -> FastPolicyVisibilityView:
        return fast_policy_visibility_view(
            self.policy_catalog,
            self.policy_mechanics,
            active=self.state.active & (self.state.hp > 0),
            stable_id=self.state.stable_id,
            card_id=self.state.card_id,
        )

    def _publish_policy_visibility_(
        self,
        view: FastPolicyVisibilityView,
    ) -> None:
        """Publish one common availability view to combat and observation."""

        self.combat._target_unavailable.copy_(view.target_unavailable)
        self._entity_special.copy_(view.special_active)
        self._entity_invisible.copy_(view.invisible)
        self._entity_hidden.copy_(view.hidden)

    def _publish_ability_mechanics_(
        self,
        abilities: FastAbilityStepResult | None,
    ) -> None:
        """Compose Champion state into common targeting and observation planes."""

        if abilities is None:
            return
        self.combat._target_unavailable.logical_or_(abilities.effect_active)
        self._entity_special.logical_or_(abilities.pending | abilities.effect_active)
        # Cloaked Champions remain publicly represented, but the structured
        # invisible flag and target-unavailable plane carry their semantics.
        self._entity_invisible.logical_or_(abilities.effect_active)

    def _travel_view(self) -> FastTravelView:
        """Return current travel gates, including not-yet-advanced spawns."""

        view = fast_travel_view(
            self.travel,
            active=self.state.active & (self.state.hp > 0),
            stable_id=self.state.stable_id,
            card_id=self.state.card_id,
        )
        if self.travel_catalog is None:
            return view
        safe_card = self.state.card_id.clamp(0, self.travel_catalog.size - 1)
        known = (self.state.card_id > 0) & (
            self.state.card_id < self.travel_catalog.size
        )
        pending = (
            self._travel_spawned
            & self.state.active
            & (self.state.hp > 0)
            & known
            & self.travel_catalog.declares_travel[safe_card]
        )
        rejected = pending & ~self.travel_catalog.profile_supported[safe_card]
        protected = pending & ~rejected
        return FastTravelView(
            current=view.current | pending,
            profile_rejected=view.profile_rejected | rejected,
            special_active=view.special_active | protected,
            target_unavailable=view.target_unavailable | pending,
            immune=view.immune | protected,
            combat_blocked=view.combat_blocked | pending,
            movement_blocked=view.movement_blocked | pending,
        )

    def _publish_travel_mechanics_(self, view: FastTravelView) -> None:
        """Compose travel state into shared targeting and observation planes."""

        self.combat._target_unavailable.logical_or_(view.target_unavailable)
        self._entity_special.logical_or_(view.special_active)
        underground = (self.travel.kind == FAST_TRAVEL_UNDERGROUND) & (
            view.target_unavailable
        )
        if self.travel_catalog is not None:
            safe_card = self.state.card_id.clamp(0, self.travel_catalog.size - 1)
            underground |= self._travel_spawned & (
                self.travel_catalog.kind[safe_card] == FAST_TRAVEL_UNDERGROUND
            )
        self._entity_hidden.logical_or_(underground)

    def _publish_river_jump_mechanics_(self) -> None:
        """Expose committed river flight as public special movement."""

        if self.river_jumps is not None:
            self._entity_special.logical_or_(self.river_jumps.active)

    def _queue_travel_spawned_(self, spawned: torch.Tensor) -> None:
        if spawned.shape != self.state.active.shape:
            raise ValueError("spawned must have shape [batch, entities]")
        self._travel_spawned.logical_or_(spawned)

    def _step_travel_(
        self,
        *,
        stunned: torch.Tensor,
        policy_view: FastPolicyVisibilityView,
        abilities: FastAbilityStepResult | None,
    ) -> FastTravelStepResult | None:
        """Advance special movement once before ordinary movement and combat."""

        if self.travel_catalog is None:
            self._travel_spawned.zero_()
            self._travel_interrupted.zero_()
            return None
        ability_locked = (
            abilities.cast_locked
            if abilities is not None
            else torch.zeros_like(self.state.active)
        )
        current_before = fast_travel_view(
            self.travel,
            active=self.state.active & (self.state.hp > 0),
            stable_id=self.state.stable_id,
            card_id=self.state.card_id,
        )
        paused_windup = (
            current_before.current & (self.travel.phase == FAST_TRAVEL_WINDUP) & stunned
        )
        snapshot = self.combat.target_snapshot()
        safe_pending_card = self.state.card_id.clamp(0, self.travel_catalog.size - 1)
        pending_kind = self.travel_catalog.kind[safe_pending_card]
        # Spawn impacts belong to the deployment-complete hook, not the action
        # allocation frame. The core decrements deploy time later in this same
        # tick, so a single remaining tick is ready here. Other travel profiles
        # bind immediately because their transport begins at placement.
        ready_spawn = self._travel_spawned & (
            (pending_kind != FAST_TRAVEL_LEAP) | (self.state.deploy_ticks <= 1)
        )
        result = advance_fast_travel_(
            self.travel_catalog,
            self.travel,
            active=self.state.active & (self.state.hp > 0),
            stable_id=self.state.stable_id,
            card_id=self.state.card_id,
            owner=self.state.owner,
            x_units=self.state.x_units,
            y_units=self.state.y_units,
            spawned=ready_spawn,
            trigger=(
                snapshot.found
                & ~stunned
                & ~policy_view.combat_blocked
                & ~ability_locked
            ),
            target_stable_id=snapshot.target_stable_id,
            target_x_units=snapshot.destination_x_units,
            target_y_units=snapshot.destination_y_units,
            target_distance_units=snapshot.edge_distance_units,
            target_valid=snapshot.found,
            interrupted=self._travel_interrupted,
        )
        self.state.x_units.copy_(result.x_units)
        self.state.y_units.copy_(result.y_units)
        paused_windup &= ~result.cancelled
        launched_while_paused = paused_windup & (
            self.travel.phase == FAST_TRAVEL_TRANSIT
        )
        safe_card = self.state.card_id.clamp(0, self.travel_catalog.size - 1)
        restored_ticks = torch.where(
            launched_while_paused,
            self.travel_catalog.windup_ticks[safe_card].clamp_min(1) - 1,
            (self.travel.phase_ticks - 1).clamp_min(0),
        )
        self.travel.phase.copy_(
            torch.where(
                paused_windup,
                torch.full_like(self.travel.phase, FAST_TRAVEL_WINDUP),
                self.travel.phase,
            )
        )
        self.travel.phase_ticks.copy_(
            torch.where(paused_windup, restored_ticks, self.travel.phase_ticks)
        )
        result = replace(
            result,
            view=fast_travel_view(
                self.travel,
                active=self.state.active & (self.state.hp > 0),
                stable_id=self.state.stable_id,
                card_id=self.state.card_id,
            ),
        )
        self._travel_spawned.logical_and_(
            ~ready_spawn & self.state.active & (self.state.hp > 0)
        )
        self._travel_interrupted.zero_()
        return result

    def _resolve_travel_impacts_(
        self,
        travel: FastTravelStepResult,
        *,
        policy_view: FastPolicyVisibilityView,
        travel_view: FastTravelView,
    ) -> tuple[
        FastTravelEffectAllocationResult,
        FastEffectStepResult,
        FastRadialImpulseResult,
    ]:
        """Commit travel damage and push through shared numeric kernels."""

        allocation = allocate_fast_travel_effects_(
            self.state,
            self.travel_effects,
            self.travel_effect_consume_source_id,
            travel.impact,
        )
        safe_card = self.state.card_id.clamp(0, self.action_kernel.catalog.size - 1)
        receivable = ~travel_view.immune
        effects = step_fast_effects(
            self.state,
            self.travel_effects,
            self.entity_status_kind,
            self.entity_status_ticks,
            consume_source_id=self.travel_effect_consume_source_id,
            cleanup_dead=False,
            modifiers=self.modifiers,
            entity_is_air=self._entity_airborne_target(),
            entity_collision_radius_units=self._entity_collision_radius_units(),
            tick_status=False,
            entity_slow_ticks=self.entity_slow_ticks,
            slow_movement_multiplier_by_card=(
                self.action_kernel.catalog.slow_movement_multiplier
            ),
            slow_attack_multiplier_by_card=(
                self.action_kernel.catalog.slow_attack_multiplier
            ),
            entity_committed_direct_receivable=(
                policy_view.effect_receivable_affects_hidden & receivable
            ),
            entity_secondary_targetable=(policy_view.secondary_targetable & receivable),
            entity_area_receivable=policy_view.area_receivable & receivable,
            entity_effect_receivable_affects_hidden=(
                policy_view.effect_receivable_affects_hidden & receivable
            ),
        )
        entity_is_air = self._entity_airborne_target()
        eligible = (
            allocation.accepted[:, :, None]
            & self.state.active[:, None, :]
            & (self.state.hp[:, None, :] > 0)
            & (self.state.owner[:, None, :] != travel.impact.source_owner[:, :, None])
            & ~entity_is_air[:, None, :]
            & (self.state.kind[:, None, :] != FAST_KIND_BUILDING)
            & ~self.knockback_immune_by_card[safe_card][:, None, :]
            & policy_view.area_receivable[:, None, :]
            & ~travel_view.immune[:, None, :]
        )
        impulse = compute_fast_radial_impulse(
            travel_impact_radial_impulse_inputs(
                travel.impact,
                target_x_units=self.state.x_units,
                target_y_units=self.state.y_units,
                target_stable_id=self.state.stable_id,
                eligible=eligible,
            )
        )
        self.state.x_units.add_(impulse.dx_units).clamp_(0, 18_000)
        self.state.y_units.add_(impulse.dy_units).clamp_(0, 32_000)
        self._travel_interrupted.logical_or_(impulse.affected)
        return allocation, effects, impulse

    def _initialize_policy_mechanics_(self, spawned: torch.Tensor) -> None:
        self.policy_mechanics.initialize_spawned_(
            self.policy_catalog,
            stable_id=self.state.stable_id,
            card_id=self.state.card_id,
            spawned=spawned,
        )

    def _initialize_lifecycle_(self, mask: torch.Tensor) -> None:
        """Install card-indexed lifecycle payloads on newly occupied slots."""

        catalog = self.action_kernel.catalog
        safe_card = self.state.card_id.clamp(0, catalog.size - 1)
        known = (self.state.card_id > 0) & (self.state.card_id < catalog.size)
        selected = mask & known

        def write(field: torch.Tensor, table: torch.Tensor) -> None:
            field.copy_(torch.where(selected, table[safe_card], field))

        write(self.lifecycle.lifetime_ticks, catalog.lifetime_ticks)
        write(self.lifecycle.death_spawn_count, catalog.death_spawn_count)
        write(self.lifecycle.death_spawn_card_id, catalog.death_spawn_card_id)
        write(self.lifecycle.death_spawn_kind, catalog.death_spawn_kind)
        write(self.lifecycle.death_spawn_hp, catalog.death_spawn_hp)
        write(
            self.lifecycle.death_spawn_radius_units,
            catalog.death_spawn_radius_units,
        )
        write(
            self.lifecycle.death_spawn_deploy_ticks,
            catalog.death_spawn_deploy_ticks,
        )

    def _initialize_modifiers_(self, mask: torch.Tensor) -> None:
        """Initialize numeric modifiers on newly occupied entity slots."""

        catalog = self.action_kernel.catalog
        safe_card = self.state.card_id.clamp(0, catalog.size - 1)
        known = (self.state.card_id > 0) & (self.state.card_id < catalog.size)
        selected = mask & known
        initial_shield = catalog.shield_hitpoints[safe_card]
        self.modifiers.shield.copy_(
            torch.where(selected, initial_shield, self.modifiers.shield)
        )
        self.modifiers.max_shield.copy_(
            torch.where(selected, initial_shield, self.modifiers.max_shield)
        )
        self.modifiers.charge_progress_ticks.masked_fill_(mask, 0)
        self.modifiers.charge_progress_distance_units.masked_fill_(mask, 0)
        self.modifiers.charge_ready.masked_fill_(mask, False)

    def _clear_modifiers_(self, mask: torch.Tensor) -> None:
        self.modifiers.shield.masked_fill_(mask, 0.0)
        self.modifiers.max_shield.masked_fill_(mask, 0.0)
        self.modifiers.charge_progress_ticks.masked_fill_(mask, 0)
        self.modifiers.charge_progress_distance_units.masked_fill_(mask, 0)
        self.modifiers.charge_ready.masked_fill_(mask, False)

    def _clear_damage_ramp_(self, mask: torch.Tensor) -> None:
        """Clear connection history before a physical slot is reused."""

        self.damage_ramp.observed_target_stable_id.masked_fill_(mask, 0)
        self.damage_ramp.connected_ticks.masked_fill_(mask, 0)
        self.damage_ramp.stage.masked_fill_(mask, 0)

    def _clear_status_(self, mask: torch.Tensor) -> None:
        """Clear all independently timed status sources for reused slots."""

        self.entity_status_kind.masked_fill_(mask, 0)
        self.entity_status_ticks.masked_fill_(mask, 0)
        self.entity_slow_ticks.masked_fill_(mask[:, :, None], 0)
        self.entity_attack_clock_fraction.masked_fill_(mask, 0.0)
        self.entity_kamikaze_ticks.masked_fill_(mask, 0)
        self.entity_kamikaze_windup_ticks.masked_fill_(mask, 0)

    def _initialize_action_spawns_(self, spawned: torch.Tensor) -> None:
        """Initialize every entity-bound plane from one action spawn ledger.

        Both ordinary homogeneous deployments and setup-compiled heterogeneous
        deployments enter through this seam.  Clearing identity-bound state
        before rebinding makes physical-slot reuse independent of the previous
        occupant without adding card-specific runtime dispatch.
        """

        self.combat.navigation.state.reset_(spawned)
        self.policy_mechanics.clear_(spawned)
        self.travel.clear_(spawned)
        self._travel_spawned.masked_fill_(spawned, False)
        self._travel_interrupted.masked_fill_(spawned, False)
        for descriptor in fields(self.abilities):
            if descriptor.name in {"device", "newest_owner_stable_id"}:
                continue
            getattr(self.abilities, descriptor.name).masked_fill_(spawned, 0)
        self.death_bursts.emitted_source_stable_id.masked_fill_(spawned, 0)
        self._triggered_death_stable_id.masked_fill_(spawned, 0)
        self._initialize_spawn_sidecars_(spawned)

    def _initialize_spawn_sidecars_(
        self,
        spawned: torch.Tensor,
        *,
        core_from_catalog: bool = False,
    ) -> None:
        """Initialize retained mechanics for newly allocated entity slots.

        All ordinary, atomic, scheduled, rolling, impact, payload, and periodic
        allocators already materialize the core combat fields. Lifecycle
        children are the sole exception, so only that caller requests the
        catalog-backed core write.
        """

        if core_from_catalog:
            self._initialize_spawned_combat_(spawned)
        self._clear_status_(spawned)
        self._initialize_lifecycle_(spawned)
        self._initialize_modifiers_(spawned)
        self._clear_damage_ramp_(spawned)
        self._initialize_policy_mechanics_(spawned)
        self._queue_travel_spawned_(spawned)

    def _slow_multipliers(self) -> tuple[torch.Tensor, torch.Tensor]:
        """Reduce active serialized slow sources independently on each axis."""

        active = self.entity_slow_ticks > 0
        any_active = active.any(dim=2)
        catalog = self.action_kernel.catalog
        infinity = torch.full_like(
            self.entity_slow_ticks, torch.inf, dtype=torch.float32
        )
        movement = torch.where(
            active,
            catalog.slow_movement_multiplier[None, None, :],
            infinity,
        ).amin(dim=2)
        attack = torch.where(
            active,
            catalog.slow_attack_multiplier[None, None, :],
            infinity,
        ).amin(dim=2)
        one = torch.ones_like(movement)
        return (
            torch.where(any_active, movement, one),
            torch.where(any_active, attack, one),
        )

    def _attack_clock_decrement_(
        self,
        *,
        cooling: torch.Tensor,
        rate_multiplier: torch.Tensor,
    ) -> torch.Tensor:
        """Advance cooldowns at a fractional composed haste/slow rate."""

        total = self.entity_attack_clock_fraction + rate_multiplier.clamp(min=0.0)
        # Float32 catalog percentages such as 0.7 must earn exactly seven
        # ticks over ten frames instead of stalling at 6.999999.
        decrement = torch.floor(total + 1e-6).to(torch.int32)
        self.entity_attack_clock_fraction.copy_(
            torch.where(
                cooling,
                (total - decrement.to(torch.float32)).clamp(min=0.0),
                0.0,
            )
        )
        return torch.where(cooling, decrement.clamp(min=0), 0)

    def _charge_parameters(self) -> FastChargeParameters:
        """Gather numeric charge descriptors for the current slot identities."""

        catalog = self.action_kernel.catalog
        safe_card = self.state.card_id.clamp(0, catalog.size - 1)
        known = (self.state.card_id > 0) & (self.state.card_id < catalog.size)
        threshold_distance = catalog.charge_threshold_distance_units[safe_card]
        return FastChargeParameters(
            enabled=known & (threshold_distance > 0),
            threshold_ticks=catalog.charge_threshold_ticks[safe_card],
            threshold_distance_units=threshold_distance,
            ready_speed_multiplier=catalog.charge_ready_speed_multiplier[safe_card],
            ready_damage_multiplier=catalog.charge_ready_damage_multiplier[safe_card],
        )

    def _damage_ramp_parameters(self) -> FastDamageRampParameters:
        """Gather serialized ramp descriptors for current slot identities."""

        catalog = self.action_kernel.catalog
        safe_card = self.state.card_id.clamp(0, catalog.size - 1)
        known = (self.state.card_id > 0) & (self.state.card_id < catalog.size)
        return FastDamageRampParameters(
            enabled=known & catalog.damage_ramp_enabled[safe_card],
            stage_1_ticks=catalog.damage_ramp_stage_1_ticks[safe_card],
            stage_2_ticks=catalog.damage_ramp_stage_2_ticks[safe_card],
            stage_0_damage_multiplier=(
                catalog.damage_ramp_stage_0_multiplier[safe_card]
            ),
            stage_1_damage_multiplier=(
                catalog.damage_ramp_stage_1_multiplier[safe_card]
            ),
            stage_2_damage_multiplier=(
                catalog.damage_ramp_stage_2_multiplier[safe_card]
            ),
            retarget_grace_ticks=(catalog.damage_ramp_retarget_grace_ticks[safe_card]),
        )

    def _initialize_spawned_combat_(self, mask: torch.Tensor) -> None:
        """Fill ordinary combat planes for data-resolved death-spawn children."""

        catalog = self.action_kernel.catalog
        safe_card = self.state.card_id.clamp(0, catalog.size - 1)
        known = (self.state.card_id > 0) & (self.state.card_id < catalog.size)
        selected = mask & known

        def write(field: torch.Tensor, table: torch.Tensor) -> None:
            field.copy_(torch.where(selected, table[safe_card], field))

        write(self.state.kind, catalog.kind)
        write(self.state.hp, catalog.hitpoints)
        write(self.state.max_hp, catalog.hitpoints)
        write(self.state.damage, catalog.damage)
        write(self.state.range_units, catalog.range_units)
        write(self.state.sight_range_units, catalog.sight_range_units)
        write(self.state.speed_units_per_tick, catalog.speed_units_per_tick)
        write(self.state.hit_cooldown_ticks, catalog.hit_cooldown_ticks)

    def _periodic_materialization_commands(
        self,
        commands: FastPeriodicSpawnCommands,
    ) -> FastSpawnCommands:
        """Attach current source transforms to stable-ordered wave triggers."""

        source_slot = commands.source_slot.clamp(0, self.state.max_entities - 1)
        return FastSpawnCommands(
            ready=commands.ready,
            owner=self.state.owner.gather(1, source_slot),
            child_card_id=commands.child_card_id,
            x_units=self.state.x_units.gather(1, source_slot),
            y_units=self.state.y_units.gather(1, source_slot),
            count=commands.count,
            radius_units=commands.radius_units,
            deploy_ticks=commands.deploy_ticks,
        )

    @staticmethod
    def _death_burst_effect_commands(
        commands: FastDeathBurstCommands,
    ) -> FastPayloadEffectCommands:
        """Project lethal novas into the common numeric area-effect path."""

        zeros_i8 = torch.zeros_like(commands.source_owner, dtype=torch.int8)
        zeros_i32 = torch.zeros_like(commands.source_x_units, dtype=torch.int32)
        return FastPayloadEffectCommands(
            ready=commands.ready,
            payload_stable_id=commands.source_stable_id,
            source_id=commands.source_stable_id,
            owner=commands.source_owner,
            effect_card_id=commands.source_card_id,
            x_units=commands.source_x_units,
            y_units=commands.source_y_units,
            damage=commands.damage,
            radius_units=commands.radius_units,
            status_kind=zeros_i8,
            status_duration_ticks=zeros_i32,
            tower_damage_multiplier=commands.tower_damage_multiplier,
            building_damage_multiplier=commands.building_damage_multiplier,
            hits_air=commands.hits_air,
            hits_ground=commands.hits_ground,
        )

    def _step_death_burst_pass(
        self,
    ) -> tuple[FastDeathBurstStepResult, FastEffectStepResult]:
        burst = step_fast_death_bursts_(
            self.state,
            self.death_burst_catalog,
            self.death_bursts,
        )
        allocate_fast_payload_effects_(
            self.state,
            self.death_effects,
            self.death_effect_consume_source_id,
            self._death_burst_effect_commands(burst.commands),
        )
        visibility = self._policy_visibility_view()
        travel_view = self._travel_view()
        receivable = ~travel_view.immune
        effect = step_fast_effects(
            self.state,
            self.death_effects,
            self.entity_status_kind,
            self.entity_status_ticks,
            consume_source_id=self.death_effect_consume_source_id,
            cleanup_dead=False,
            modifiers=self.modifiers,
            entity_is_air=self._entity_airborne_target(),
            entity_collision_radius_units=self._entity_collision_radius_units(),
            tick_status=False,
            entity_slow_ticks=self.entity_slow_ticks,
            slow_movement_multiplier_by_card=(
                self.action_kernel.catalog.slow_movement_multiplier
            ),
            slow_attack_multiplier_by_card=(
                self.action_kernel.catalog.slow_attack_multiplier
            ),
            entity_committed_direct_receivable=(
                visibility.effect_receivable_affects_hidden & receivable
            ),
            entity_secondary_targetable=(visibility.secondary_targetable & receivable),
            entity_area_receivable=visibility.area_receivable & receivable,
            entity_effect_receivable_affects_hidden=(
                visibility.effect_receivable_affects_hidden & receivable
            ),
        )
        return burst, effect

    def _scheduled_cast_commands(
        self,
        ingress: FastActionIngressResult,
    ) -> tuple[torch.Tensor, FastScheduledCastCommands] | None:
        """Decode supported spell rows into the numeric delayed-cast pool."""

        if (
            self.spawn_blueprints is None
            or self.scheduled_casts is None
            or self.spawn_blueprints.blueprint_count == 0
        ):
            return None
        catalog = self.spawn_blueprints
        safe_card = ingress.selected_card_ids.clamp(0, catalog.fast_cards.size - 1)
        row = catalog.scheduled_blueprint_by_card[safe_card]
        scheduled = ingress.spell_cast & (row >= 0)
        safe_row = row.clamp(0, max(0, catalog.blueprint_count - 1))
        zeros_i8 = torch.zeros_like(ingress.selected_card_ids, dtype=torch.int8)
        zeros_i32 = torch.zeros_like(ingress.selected_card_ids, dtype=torch.int32)
        return scheduled, FastScheduledCastCommands(
            ready=scheduled,
            owner=self._effect_owners,
            source_card_id=ingress.selected_card_ids,
            x_units=ingress.selection.world_x_units.to(torch.int32),
            y_units=ingress.selection.world_y_units.to(torch.int32),
            first_delay_ticks=catalog.first_delay_ticks[safe_row],
            interval_ticks=catalog.interval_ticks[safe_row],
            waves=catalog.max_waves[safe_row],
            child_card_id=catalog.child_card_id[safe_row],
            count=catalog.count[safe_row].to(torch.int32),
            radius_units=catalog.radius_units[safe_row],
            deploy_ticks=catalog.deploy_ticks[safe_row],
            initial_damage=catalog.scheduled_initial_damage[safe_row],
            initial_radius_units=(catalog.scheduled_initial_radius_units[safe_row]),
            initial_status_kind=zeros_i8,
            initial_status_duration_ticks=zeros_i32,
            tower_damage_multiplier=(
                catalog.scheduled_tower_damage_multiplier[safe_row]
            ),
            building_damage_multiplier=(
                catalog.scheduled_building_damage_multiplier[safe_row]
            ),
            hits_air=catalog.scheduled_hits_air[safe_row],
            hits_ground=catalog.scheduled_hits_ground[safe_row],
        )

    @staticmethod
    def _scheduled_effect_commands(
        commands: FastScheduledAreaEffectCommands,
    ) -> FastPayloadEffectCommands:
        return FastPayloadEffectCommands(
            ready=commands.ready,
            payload_stable_id=commands.cast_stable_id,
            source_id=commands.cast_stable_id,
            owner=commands.owner,
            effect_card_id=commands.source_card_id,
            x_units=commands.x_units,
            y_units=commands.y_units,
            damage=commands.damage,
            radius_units=commands.radius_units,
            status_kind=commands.status_kind,
            status_duration_ticks=commands.status_duration_ticks,
            tower_damage_multiplier=commands.tower_damage_multiplier,
            building_damage_multiplier=commands.building_damage_multiplier,
            hits_air=commands.hits_air,
            hits_ground=commands.hits_ground,
        )

    def _scheduled_spawn_commands(
        self,
        commands: FastScheduledSpawnCommands,
    ) -> FastSpawnCommands:
        """Spread single-child waves deterministically within their cast area."""

        single = commands.ready & (commands.count == 1) & (commands.radius_units > 0)
        phase = torch.remainder(
            commands.cast_stable_id * 1_103_515_245 + self.state.tick[:, None] * 12_345,
            65_536,
        ).to(torch.float32) * (2.0 * torch.pi / 65_536.0)
        distance = torch.round(commands.radius_units.to(torch.float32) * 0.75)
        offset_x = torch.round(torch.cos(phase) * distance).to(torch.int32)
        offset_y = torch.round(torch.sin(phase) * distance).to(torch.int32)
        return FastSpawnCommands(
            ready=commands.ready,
            owner=commands.owner,
            child_card_id=commands.child_card_id,
            x_units=torch.where(single, commands.x_units + offset_x, commands.x_units),
            y_units=torch.where(single, commands.y_units + offset_y, commands.y_units),
            count=commands.count,
            radius_units=torch.where(
                single, torch.zeros_like(commands.radius_units), commands.radius_units
            ),
            deploy_ticks=commands.deploy_ticks,
        )

    def _rolling_commands(
        self,
        ingress: FastActionIngressResult,
    ) -> tuple[torch.Tensor, FastRollingSpellCommands]:
        """Compile accepted spell actions into numeric rolling commands."""

        catalog = self.action_kernel.catalog
        safe_card = ingress.selected_card_ids.clamp(0, catalog.size - 1)
        selected = ingress.spell_cast & catalog.rolling_enabled[safe_card]
        source_x = self.state.x_units.index_select(1, self._spell_source_slots)
        source_y = self.state.y_units.index_select(1, self._spell_source_slots)
        shape = ingress.selected_card_ids.shape
        no_spawn = torch.full(
            shape,
            FAST_ROLLING_NO_SPAWN,
            dtype=torch.int64,
            device=self.device,
        )
        spawn_count = torch.zeros(shape, dtype=torch.int32, device=self.device)
        spawn_deploy = torch.zeros_like(spawn_count)
        blueprint = no_spawn
        if self.spawn_blueprints is not None:
            rows = self.spawn_blueprints.rolling_blueprint_by_card[safe_card]
            blueprint = rows
            if self.spawn_blueprints.blueprint_count > 0:
                safe_row = rows.clamp(0, self.spawn_blueprints.blueprint_count - 1)
                has_spawn = rows >= 0
                spawn_count = torch.where(
                    has_spawn,
                    self.spawn_blueprints.count[safe_row].to(torch.int32),
                    spawn_count,
                )
                spawn_deploy = torch.where(
                    has_spawn,
                    self.spawn_blueprints.deploy_ticks[safe_row],
                    spawn_deploy,
                )
        return selected, FastRollingSpellCommands(
            ready=selected,
            owner=self._effect_owners,
            source_card_id=ingress.selected_card_ids,
            origin_x_units=source_x,
            origin_y_units=source_y,
            target_x_units=ingress.selection.world_x_units.to(torch.int32),
            target_y_units=ingress.selection.world_y_units.to(torch.int32),
            travel_range_units=catalog.rolling_travel_range_units[safe_card],
            speed_units_per_tick=catalog.rolling_speed_units_per_tick[safe_card],
            half_width_units=catalog.rolling_half_width_units[safe_card],
            damage=catalog.rolling_damage[safe_card],
            ground_only=catalog.rolling_ground_only[safe_card],
            tower_damage_multiplier=(
                catalog.rolling_tower_damage_multiplier[safe_card]
            ),
            radial_push_units=catalog.rolling_radial_push_units[safe_card],
            forward_push_units=catalog.rolling_forward_push_units[safe_card],
            impact_spawn_blueprint_id=blueprint,
            impact_spawn_count=spawn_count,
            impact_spawn_deploy_ticks=spawn_deploy,
        )

    @staticmethod
    def _allocate_triggered_effects_(
        destination: FastEffectState,
        incoming: FastEffectState,
    ) -> FastTriggeredEffectAllocation:
        """Allocate fixed command lanes into a persistent low-slot pool."""

        if incoming.batch_size != destination.batch_size:
            raise ValueError("triggered effect pools must share a batch size")
        if incoming.device != destination.device:
            raise ValueError("triggered effect pools must share a device")
        ready = incoming.active
        free = ~destination.active
        ready_rank = ready.to(torch.int64).cumsum(dim=1) - 1
        free_rank = free.to(torch.int64).cumsum(dim=1) - 1
        selected = (
            ready[:, :, None]
            & free[:, None, :]
            & (ready_rank[:, :, None] == free_rank[:, None, :])
        )
        accepted = selected.any(dim=2)
        written = selected.any(dim=1)
        effect_slot = torch.where(
            accepted,
            selected.to(torch.int8).argmax(dim=2).to(torch.int64),
            -1,
        )
        for descriptor in fields(destination):
            if descriptor.name == "device":
                continue
            target = getattr(destination, descriptor.name)
            source = getattr(incoming, descriptor.name)
            neutral = torch.zeros((), dtype=source.dtype, device=source.device)
            value = torch.where(
                selected,
                source[:, :, None],
                neutral,
            ).sum(dim=1, dtype=source.dtype)
            target.copy_(torch.where(written, value, target))
        return FastTriggeredEffectAllocation(
            accepted=accepted,
            capacity_rejected=ready & ~accepted,
            effect_slot=effect_slot,
        )

    def _allocate_triggered_events_(
        self,
        candidates: FastTriggeredImpactEvents,
    ) -> FastTriggeredEventAllocation:
        """Admit candidates to the bounded per-tick queue in stable order."""

        queue = self.triggered_events
        queue.active.zero_()
        ready = candidates.active
        rank = ready.to(torch.int64).cumsum(dim=1) - 1
        lanes = torch.arange(
            queue.active.shape[1], dtype=torch.int64, device=self.device
        ).view(1, 1, -1)
        selected = ready[:, :, None] & (rank[:, :, None] == lanes)
        accepted = selected.any(dim=2)
        written = selected.any(dim=1)
        for descriptor in fields(queue):
            target = getattr(queue, descriptor.name)
            source = getattr(candidates, descriptor.name)
            neutral = torch.zeros((), dtype=source.dtype, device=source.device)
            value = torch.where(
                selected,
                source[:, :, None],
                neutral,
            ).sum(dim=1, dtype=source.dtype)
            target.copy_(torch.where(written, value, target))
        queue.repeat_count.copy_(torch.where(queue.active, queue.repeat_count, 1))
        return FastTriggeredEventAllocation(
            accepted=accepted,
            capacity_rejected=ready & ~accepted,
            accepted_count=accepted.sum(dim=1, dtype=torch.int64),
            capacity_rejected_count=(ready & ~accepted).sum(dim=1, dtype=torch.int64),
        )

    def _triggered_candidates(
        self,
        *,
        deploy_completed: torch.Tensor,
        committed_attacks: torch.Tensor,
        effect_result: FastEffectStepResult,
        rolling_result: FastRollingStepResult,
        travel_result: FastTravelStepResult | None,
    ) -> FastTriggeredImpactEvents:
        """Form one fixed candidate ledger from generalized runtime hooks."""

        state = self.state
        travel_spawn_owned = (
            travel_result.impact.spawn_impact
            if travel_result is not None
            else torch.zeros_like(state.active)
        )
        deploy = deploy_completed & ~travel_spawn_owned
        impact = effect_result.impacted
        rolling = rolling_result.hit.any(dim=2)
        death = (
            state.active
            & (state.stable_id > 0)
            & (state.hp <= 0)
            & (self._triggered_death_stable_id != state.stable_id)
        )
        self._triggered_death_stable_id.copy_(
            torch.where(death, state.stable_id, self._triggered_death_stable_id)
        )

        target_match = (
            state.active[:, None, :]
            & (state.target_id[:, :, None] > 0)
            & (state.target_id[:, :, None] == state.stable_id[:, None, :])
        )
        target_slot = target_match.to(torch.int8).argmax(dim=2).to(torch.int64)
        target_found = target_match.any(dim=2)
        attack_target_x = torch.where(
            target_found,
            state.x_units.gather(1, target_slot),
            state.x_units,
        )
        attack_target_y = torch.where(
            target_found,
            state.y_units.gather(1, target_slot),
            state.y_units,
        )

        maximum = torch.iinfo(torch.int64).max
        rolling_target_id = torch.where(
            rolling_result.hit,
            state.stable_id[:, None, :],
            maximum,
        ).amin(dim=2)
        rolling_target_id = torch.where(
            rolling_target_id == maximum, 0, rolling_target_id
        )
        rolling_target_match = (rolling_target_id[:, :, None] > 0) & (
            rolling_target_id[:, :, None] == state.stable_id[:, None, :]
        )
        rolling_target_slot = (
            rolling_target_match.to(torch.int8).argmax(dim=2).to(torch.int64)
        )
        rolling_target_x = state.x_units.gather(1, rolling_target_slot)
        rolling_target_y = state.y_units.gather(1, rolling_target_slot)

        active = torch.cat((deploy, committed_attacks, impact, rolling, death), dim=1)
        zeros_entity = torch.zeros_like(state.stable_id)
        zeros_effect = torch.zeros_like(self.effects.target_id)
        zeros_rolling = torch.zeros_like(self.rolling_spells.source_card_id)

        def cat(*values: torch.Tensor) -> torch.Tensor:
            return torch.cat(values, dim=1)

        return FastTriggeredImpactEvents(
            active=active,
            card_id=cat(
                state.card_id,
                state.card_id,
                self.effects.source_card_id,
                self.rolling_spells.source_card_id,
                state.card_id,
            ),
            trigger=cat(
                torch.full_like(state.owner, FAST_TRIGGER_DEPLOY_COMPLETE),
                torch.full_like(state.owner, FAST_TRIGGER_ATTACK_COMMIT),
                torch.full_like(self.effects.kind, FAST_TRIGGER_IMPACT),
                torch.full_like(self.rolling_spells.owner, FAST_TRIGGER_IMPACT),
                torch.full_like(state.owner, FAST_TRIGGER_DEATH),
            ).to(torch.int8),
            source_owner=cat(
                state.owner,
                state.owner,
                self.effects.source_owner,
                self.rolling_spells.owner,
                state.owner,
            ).to(torch.int8),
            source_entity_id=cat(
                state.stable_id,
                state.stable_id,
                zeros_effect,
                zeros_rolling,
                state.stable_id,
            ),
            target_entity_id=cat(
                zeros_entity,
                state.target_id,
                self.effects.target_id,
                rolling_target_id,
                zeros_entity,
            ),
            source_x_units=cat(
                state.x_units,
                state.x_units,
                self.effects.source_x_units,
                self.rolling_spells.x_units,
                state.x_units,
            ),
            source_y_units=cat(
                state.y_units,
                state.y_units,
                self.effects.source_y_units,
                self.rolling_spells.y_units,
                state.y_units,
            ),
            target_x_units=cat(
                state.x_units,
                attack_target_x,
                self.effects.x_units,
                rolling_target_x,
                state.x_units,
            ),
            target_y_units=cat(
                state.y_units,
                attack_target_y,
                self.effects.y_units,
                rolling_target_y,
                state.y_units,
            ),
            self_x_units=cat(
                state.x_units,
                state.x_units,
                self.effects.source_x_units,
                self.rolling_spells.x_units,
                state.x_units,
            ),
            self_y_units=cat(
                state.y_units,
                state.y_units,
                self.effects.source_y_units,
                self.rolling_spells.y_units,
                state.y_units,
            ),
            repeat_count=torch.ones_like(active, dtype=torch.int32),
        )

    def _resolve_triggered_impacts_(
        self,
        candidates: FastTriggeredImpactEvents,
    ) -> FastTriggeredRuntimeStep | None:
        """Resolve admitted hooks through shared effect and impulse kernels."""

        if self.triggered_impact_catalog is None:
            return None
        event_allocation = self._allocate_triggered_events_(candidates)
        commands = resolve_fast_triggered_impacts(
            self.triggered_impact_catalog,
            self.triggered_events,
        )
        commands = replace(
            commands,
            repeat_count=torch.where(
                commands.trigger == FAST_TRIGGER_IMPACT,
                commands.repeat_count * commands.impulse_scan_count.clamp_min(1),
                commands.repeat_count,
            ),
        )
        # Ordinary effect payloads own IMPACT damage/status, while the death
        # burst subsystem owns DeathDamage. These lanes contribute only the
        # defining secondary impulse. DeathArea status remains independent.
        base_impact = commands.trigger == FAST_TRIGGER_IMPACT
        death_damage_owned = commands.trigger == FAST_TRIGGER_DEATH
        effect_commands = replace(
            commands,
            damage=torch.where(
                base_impact | death_damage_owned,
                torch.zeros_like(commands.damage),
                commands.damage,
            ),
            status_kind=torch.where(
                base_impact,
                torch.zeros_like(commands.status_kind),
                commands.status_kind,
            ),
            max_damage_hits=torch.where(
                base_impact | death_damage_owned,
                torch.zeros_like(commands.max_damage_hits),
                commands.max_damage_hits,
            ),
        )
        incoming_effects = triggered_commands_to_effect_state(effect_commands)
        effect_allocation = self._allocate_triggered_effects_(
            self.triggered_effects,
            incoming_effects,
        )
        visibility = self._policy_visibility_view()
        travel = self._travel_view()
        receivable = ~travel.immune
        safe_card = self.state.card_id.clamp(0, self.action_kernel.catalog.size - 1)
        effects = step_fast_effects(
            self.state,
            self.triggered_effects,
            self.entity_status_kind,
            self.entity_status_ticks,
            cleanup_dead=False,
            modifiers=self.modifiers,
            entity_is_air=self._entity_airborne_target(),
            entity_collision_radius_units=self._entity_collision_radius_units(),
            tick_status=False,
            entity_slow_ticks=self.entity_slow_ticks,
            slow_movement_multiplier_by_card=(
                self.action_kernel.catalog.slow_movement_multiplier
            ),
            slow_attack_multiplier_by_card=(
                self.action_kernel.catalog.slow_attack_multiplier
            ),
            entity_committed_direct_receivable=(
                visibility.effect_receivable_affects_hidden & receivable
            ),
            entity_secondary_targetable=(visibility.secondary_targetable & receivable),
            entity_area_receivable=visibility.area_receivable & receivable,
            entity_effect_receivable_affects_hidden=(
                visibility.effect_receivable_affects_hidden & receivable
            ),
        )
        targets = FastTriggeredImpactTargets(
            active=(
                self.state.active
                & (self.state.hp > 0)
                & ~self.knockback_immune_by_card[safe_card]
                & receivable
            ),
            stable_id=self.state.stable_id,
            owner=self.state.owner,
            x_units=self.state.x_units,
            y_units=self.state.y_units,
            collision_radius_units=self._entity_collision_radius_units(),
            base_speed_units_per_tick=(
                self.action_kernel.catalog.speed_units_per_tick[safe_card]
            ),
            is_air=self._entity_airborne_target(),
            is_building=self.state.kind == FAST_KIND_BUILDING,
            area_receivable=visibility.area_receivable & receivable,
            effect_receivable_affects_hidden=(
                visibility.effect_receivable_affects_hidden & receivable
            ),
            max_displacement_units=torch.full_like(self.state.x_units, -1),
        )
        impulse = compute_fast_radial_impulse(
            triggered_commands_to_impulse_inputs(commands, targets)
        )
        self.state.x_units.add_(impulse.dx_units).clamp_(0, 18_000)
        self.state.y_units.add_(impulse.dy_units).clamp_(0, 32_000)
        self._travel_interrupted.logical_or_(impulse.affected)
        return FastTriggeredRuntimeStep(
            event_allocation=event_allocation,
            events=self.triggered_events,
            commands=commands,
            effect_allocation=effect_allocation,
            effects=effects,
            impulse=impulse,
        )

    def _action_atomic_commands(
        self,
        ingress: FastActionIngressResult,
    ) -> tuple[torch.Tensor, FastAtomicSpawnCommands] | None:
        """Map selected public entity actions to compiled private spawn events."""

        catalog = self.spawn_blueprints
        if catalog is None:
            return None
        safe_card = ingress.selected_card_ids.clamp(
            0, self.action_kernel.catalog.size - 1
        )
        event_id = catalog.action_atomic_event_by_card[safe_card]
        mapped = ingress.entity_deployment & (event_id >= 0)
        lane_index = (ingress.selection.world_x_units >= 9_000).to(torch.int8)
        return mapped, FastAtomicSpawnCommands(
            ready=mapped,
            owner=self._effect_owners,
            atomic_event_id=event_id,
            x_units=ingress.selection.world_x_units.to(torch.int32),
            y_units=ingress.selection.world_y_units.to(torch.int32),
            lane_index=lane_index,
        )

    def _legal_action_mask(self) -> torch.Tensor:
        ability = self._ability_player_view()
        mask = self.action_kernel.legal_action_mask(
            self.action_state,
            ability_legal=None if ability is None else ability.legal,
        )
        free_deploy_slots = (~self.state.active[:, FAST_TOWER_SLOT_COUNT:]).sum(dim=1)
        has_effect_slot = (~self.effects.active).any(dim=1)
        hand = self.action_state.hand_ids
        safe_card = hand.clamp(0, self.action_kernel.catalog.size - 1)
        spell = (self.action_kernel.catalog.kind[safe_card] < 0) & (
            (self.action_kernel.catalog.effect_kind[safe_card] >= 0)
            | self.action_kernel.catalog.rolling_enabled[safe_card]
        )
        rolling = self.action_kernel.catalog.rolling_enabled[safe_card]
        required_slots = self.action_kernel.catalog.summon_count[safe_card].to(
            torch.int64
        )
        required_slots = torch.where(
            rolling, torch.zeros_like(required_slots), required_slots
        )
        if self.spawn_blueprints is not None:
            atomic_event = self.spawn_blueprints.action_atomic_event_by_card[safe_card]
            has_atomic_event = atomic_event >= 0
            if self.spawn_blueprints.atomic_event_count > 0:
                safe_atomic_event = atomic_event.clamp(
                    0, self.spawn_blueprints.atomic_event_count - 1
                )
                atomic_count = self.spawn_blueprints.atomic_event_required_capacity[
                    safe_atomic_event
                ].to(torch.int64)
                required_slots = torch.where(
                    has_atomic_event,
                    atomic_count,
                    required_slots,
                )
            impact_row = self.spawn_blueprints.impact_blueprint_by_card[safe_card]
            has_impact_spawn = torch.zeros_like(impact_row, dtype=torch.bool)
            rolling_row = self.spawn_blueprints.rolling_blueprint_by_card[safe_card]
            has_rolling_spawn = torch.zeros_like(rolling_row, dtype=torch.bool)
            scheduled_row = self.spawn_blueprints.scheduled_blueprint_by_card[safe_card]
            has_scheduled = torch.zeros_like(scheduled_row, dtype=torch.bool)
            if self.spawn_blueprints.blueprint_count > 0:
                safe_impact = impact_row.clamp(
                    0, self.spawn_blueprints.blueprint_count - 1
                )
                has_impact_spawn = impact_row >= 0
                impact_count = self.spawn_blueprints.count[safe_impact].to(torch.int64)
                required_slots = torch.where(
                    has_impact_spawn,
                    impact_count,
                    required_slots,
                )
                safe_rolling = rolling_row.clamp(
                    0, self.spawn_blueprints.blueprint_count - 1
                )
                has_rolling_spawn = rolling_row >= 0
                rolling_count = self.spawn_blueprints.count[safe_rolling].to(
                    torch.int64
                )
                required_slots = torch.where(
                    has_rolling_spawn,
                    rolling_count,
                    required_slots,
                )
                safe_scheduled = scheduled_row.clamp(
                    0, self.spawn_blueprints.blueprint_count - 1
                )
                has_scheduled = scheduled_row >= 0
                scheduled_count = self.spawn_blueprints.count[safe_scheduled].to(
                    torch.int64
                )
                required_slots = torch.where(
                    has_scheduled,
                    scheduled_count,
                    required_slots,
                )
        else:
            has_scheduled = torch.zeros_like(spell)
        has_rolling_slot = (~self.rolling_spells.active).any(dim=1)
        enough_deploy_slots = free_deploy_slots[:, None, None] >= required_slots
        has_cast_slot = (
            (~self.scheduled_casts.active).any(dim=1)
            if self.scheduled_casts is not None
            else torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
        )
        scheduled_capacity = (
            has_cast_slot[:, None, None]
            & has_effect_slot[:, None, None]
            & enough_deploy_slots
        )
        capacity = torch.where(
            rolling,
            has_rolling_slot[:, None, None] & enough_deploy_slots,
            torch.where(
                has_scheduled,
                scheduled_capacity,
                torch.where(
                    spell,
                    has_effect_slot[:, None, None] & enough_deploy_slots,
                    enough_deploy_slots,
                ),
            ),
        )
        placement_capacity = (
            capacity[..., None]
            .expand(-1, -1, NUM_HAND_SLOTS, NUM_TILES)
            .reshape(self.batch_size, 2, NO_OP_ACTION)
        )
        profile_supported = self.policy_catalog.profile_supported[safe_card]
        placement_profile = (
            profile_supported[..., None]
            .expand(-1, -1, NUM_HAND_SLOTS, NUM_TILES)
            .reshape(self.batch_size, 2, NO_OP_ACTION)
        )
        mask[:, :, :NO_OP_ACTION] &= placement_capacity & placement_profile
        return mask

    def _effect_commands(
        self,
        ingress: FastActionIngressResult,
        attack_ready: torch.Tensor,
        attack_damage_multiplier: torch.Tensor,
        scheduled_spell: torch.Tensor,
        rolling_spell: torch.Tensor,
    ) -> FastEffectCommands:
        """Put policy spell casts before entity-slot-ordered attacks."""

        spell_source_x = self.state.x_units.index_select(1, self._spell_source_slots)
        spell_source_y = self.state.y_units.index_select(1, self._spell_source_slots)
        zeros_i64 = torch.zeros_like(ingress.selected_card_ids)
        ones_spell = torch.ones_like(ingress.selected_card_ids, dtype=torch.float32)
        spell = FastEffectCommands(
            ready=ingress.spell_cast & ~scheduled_spell & ~rolling_spell,
            source_id=zeros_i64,
            owner=self._effect_owners,
            card_id=ingress.selected_card_ids,
            source_x_units=spell_source_x,
            source_y_units=spell_source_y,
            target_id=zeros_i64,
            target_x_units=ingress.selection.world_x_units.to(torch.int32),
            target_y_units=ingress.selection.world_y_units.to(torch.int32),
            damage_multiplier=ones_spell,
        )
        zeros_entity = torch.zeros_like(self.state.x_units)
        if self.travel_catalog is not None:
            safe_source = self.state.card_id.clamp(0, self.travel_catalog.size - 1)
            target_match = (
                self.state.active[:, None, :]
                & (self.state.hp[:, None, :] > 0)
                & (self.state.target_id[:, :, None] > 0)
                & (self.state.target_id[:, :, None] == self.state.stable_id[:, None, :])
            )
            target_found = target_match.any(dim=2)
            target_slot = target_match.to(torch.int8).argmax(dim=2).to(torch.int64)
            crown_target = target_found & (target_slot < FAST_TOWER_SLOT_COUNT)
            underground = (
                self.travel_catalog.kind[safe_source] == FAST_TRAVEL_UNDERGROUND
            ) & self.travel_catalog.profile_supported[safe_source]
            ordinary_damage = self.action_kernel.catalog.effect_damage[
                safe_source
            ].clamp_min(torch.finfo(torch.float32).tiny)
            tower_scale = (
                self.travel_catalog.tower_damage[safe_source] / ordinary_damage
            )
            attack_damage_multiplier = attack_damage_multiplier * torch.where(
                crown_target & underground,
                tower_scale,
                torch.ones_like(tower_scale),
            )
        attack = FastEffectCommands(
            ready=attack_ready,
            source_id=self.state.stable_id,
            owner=self.state.owner,
            card_id=self.state.card_id,
            source_x_units=self.state.x_units,
            source_y_units=self.state.y_units,
            target_id=self.state.target_id,
            target_x_units=zeros_entity,
            target_y_units=zeros_entity,
            damage_multiplier=attack_damage_multiplier,
        )

        def combined(name: str) -> torch.Tensor:
            return torch.cat((getattr(spell, name), getattr(attack, name)), dim=1)

        return FastEffectCommands(
            ready=combined("ready"),
            source_id=combined("source_id"),
            owner=combined("owner"),
            card_id=combined("card_id"),
            source_x_units=combined("source_x_units"),
            source_y_units=combined("source_y_units"),
            target_id=combined("target_id"),
            target_x_units=combined("target_x_units"),
            target_y_units=combined("target_y_units"),
            damage_multiplier=combined("damage_multiplier"),
            numeric=self._numeric_effect_commands,
        )

    def step_tick(self, action_ids: torch.Tensor) -> SimpleGymRuntimeStep:
        """Apply both requests, advance one native tick, and project its result."""

        if action_ids.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        if action_ids.device != self.device:
            raise ValueError("action_ids must use the runtime device")
        if action_ids.dtype != torch.int64:
            raise ValueError("action_ids must be int64")

        legal_mask = self._legal_action_mask()
        pre_hand = self.action_state.hand_ids.clone()
        pre_cycle = self.action_state.cycle_ids.clone()
        pre_head = self.action_state.cycle_head.clone()
        pre_elixir = self.action_state.elixir.clone()
        ingress = self.action_kernel.ingress(
            self.action_state, action_ids, legal_mask=legal_mask
        )
        ability_activation: FastAbilityActivationResult | None = None
        abilities_before: FastAbilityStepResult | None = None
        if self.ability_catalog is not None:
            ability_activation = activate_fast_abilities_(
                self.state,
                self.abilities,
                self.ability_catalog,
                ingress.ability_activation,
                elixir=self.action_state.elixir,
                stunned=self._stunned(),
                player_alive=self.action_state.player_alive,
            )
            self.action_state.elixir.add_(ability_activation.elixir_delta)
            abilities_before = step_fast_abilities_(
                self.state,
                self.abilities,
                self.ability_catalog,
                elixir=self.action_state.elixir,
                stunned=self._stunned(),
                player_alive=self.action_state.player_alive,
            )
        rolling_spell, rolling_commands = self._rolling_commands(ingress)
        rolling_allocation = allocate_fast_rolling_spells_(
            self.rolling_spells,
            rolling_commands,
            game_over=self.state.game_over,
        )
        scheduled_spell = torch.zeros_like(ingress.spell_cast)
        scheduled_cast_allocation: FastScheduledCastAllocationResult | None = None
        scheduled_request = self._scheduled_cast_commands(ingress)
        if scheduled_request is not None and self.scheduled_casts is not None:
            scheduled_spell, scheduled_commands = scheduled_request
            scheduled_cast_allocation = allocate_fast_scheduled_casts_(
                self.scheduled_casts,
                scheduled_commands,
                tick=self.state.tick,
            )
        atomic_spawn_allocation: FastSpawnAllocationResult | None = None
        atomic_request = self._action_atomic_commands(ingress)
        if atomic_request is None:
            deployed = self.combat.deploy_many_once(ingress.requests)
        else:
            atomic_selected, atomic_commands = atomic_request
            player_zero = replace(
                ingress.requests[0],
                valid=ingress.requests[0].valid & ~atomic_selected[:, 0],
            )
            player_one = replace(
                ingress.requests[1],
                valid=ingress.requests[1].valid & ~atomic_selected[:, 1],
            )

            ordinary_zero = self.combat.deploy_many_once((player_zero,))[:, 0]
            action_spawned = self.combat.spawned_mask.clone()
            assert self.spawn_blueprints is not None
            atomic_spawn_allocation = allocate_fast_atomic_spawns_(
                self.state,
                self.spawn_blueprints,
                atomic_commands,
                reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
            )
            action_spawned.logical_or_(atomic_spawn_allocation.spawned_mask)
            ordinary_one = self.combat.deploy_many_once((player_one,))[:, 0]
            action_spawned.logical_or_(self.combat.spawned_mask)
            self.combat.spawned_mask.copy_(action_spawned)
            ordinary_deployed = torch.stack((ordinary_zero, ordinary_one), dim=1)
            deployed = torch.where(
                atomic_selected,
                atomic_spawn_allocation.accepted,
                ordinary_deployed,
            )
        self._initialize_action_spawns_(self.combat.spawned_mask)
        pending_deploy_complete = self.state.active & (self.state.deploy_ticks == 1)
        pre_visibility = self._policy_visibility_view()
        self._publish_policy_visibility_(pre_visibility)
        self._publish_ability_mechanics_(abilities_before)
        self._publish_travel_mechanics_(self._travel_view())
        self._publish_river_jump_mechanics_()
        stunned = (self.entity_status_kind == FAST_STATUS_STUN) & (
            self.entity_status_ticks > 0
        )
        travel_result = self._step_travel_(
            stunned=stunned,
            policy_view=pre_visibility,
            abilities=abilities_before,
        )
        active_travel_view = self._travel_view()
        if travel_result is not None:
            assert self.travel_catalog is not None
            safe_travel_card = self.state.card_id.clamp(0, self.travel_catalog.size - 1)
            consumed_tick = travel_result.completed | (
                travel_result.initialized
                & self.travel_catalog.declares_travel[safe_travel_card]
            )
            active_travel_view = replace(
                active_travel_view,
                combat_blocked=(active_travel_view.combat_blocked | consumed_tick),
                movement_blocked=(active_travel_view.movement_blocked | consumed_tick),
            )
        self._publish_policy_visibility_(pre_visibility)
        self._publish_ability_mechanics_(abilities_before)
        self._publish_travel_mechanics_(active_travel_view)
        self._publish_river_jump_mechanics_()
        travel_effect_allocation: FastTravelEffectAllocationResult | None = None
        travel_effect_result: FastEffectStepResult | None = None
        travel_impulse: FastRadialImpulseResult | None = None
        if travel_result is not None:
            (
                travel_effect_allocation,
                travel_effect_result,
                travel_impulse,
            ) = self._resolve_travel_impacts_(
                travel_result,
                policy_view=pre_visibility,
                travel_view=active_travel_view,
            )

        positive_area_step = step_fast_positive_buff_areas_(self.positive_buff_areas)
        positive_buff_apply = apply_fast_positive_area_buffs_(
            self.state,
            self.positive_buffs,
            positive_area_step.scans,
        )
        charge_parameters = self._charge_parameters()
        charge_view = pre_move_charge_multipliers(self.modifiers, charge_parameters)
        slow_movement, slow_attack = self._slow_multipliers()
        positive_view = fast_positive_buff_view(self.state, self.positive_buffs)
        ability_attack = (
            abilities_before.attack_speed_multiplier
            if abilities_before is not None
            else torch.ones_like(self.state.damage)
        )
        ability_movement = (
            abilities_before.movement_speed_multiplier
            if abilities_before is not None
            else torch.ones_like(self.state.damage)
        )
        ability_cast_locked = (
            abilities_before.cast_locked
            if abilities_before is not None
            else torch.zeros_like(self.state.active)
        )
        update_king_activation_(
            self.state,
            self._king_activation_delay_ticks,
            advance_clock=True,
        )
        king_owner_active = self.state.king_active.gather(
            1, self.state.owner.to(torch.int64).clamp(0, 1)
        )
        king_owner_ready = (
            self.state.king_activation_ticks.gather(
                1, self.state.owner.to(torch.int64).clamp(0, 1)
            )
            == 0
        )
        inactive_king = self._king_source_mask & ~(king_owner_active & king_owner_ready)
        kamikaze_primed = self.entity_kamikaze_ticks > 0
        attack_clock_positive = self.state.cooldown_ticks > 0
        if self.attack_timings is not None:
            assert self.attack_locks is not None
            safe_attack_card = self.state.card_id.clamp(0, self.attack_timings.size - 1)
            timed_source = (
                self.state.active
                & (self.state.hp > 0)
                & (self.state.deploy_ticks == 0)
                & (self.state.stable_id > 0)
                & (self.state.card_id > 0)
                & (self.state.card_id < self.attack_timings.size)
                & self.attack_timings.ordinary_attack_supported[safe_attack_card]
            )
            same_attack_generation = (
                self.attack_locks.source_stable_id == self.state.stable_id
            )
            timed_clock_positive = torch.where(
                same_attack_generation,
                self.attack_locks.cooldown_ticks > 0,
                self.attack_timings.first_hit_delay_ticks[safe_attack_card] > 0,
            )
            attack_clock_positive = torch.where(
                timed_source,
                timed_clock_positive,
                attack_clock_positive,
            )
        cooldown_decrement = self._attack_clock_decrement_(
            cooling=(
                self.state.active
                & ~stunned
                & ~inactive_king
                & ~pre_visibility.combat_blocked
                & ~ability_cast_locked
                & ~active_travel_view.combat_blocked
                & ~kamikaze_primed
                & attack_clock_positive
            ),
            rate_multiplier=(
                positive_view.cooldown_decrement_multiplier
                * slow_attack
                * ability_attack
            ),
        )
        combat = self.combat.step_tick(
            disabled=(
                stunned
                | inactive_king
                | pre_visibility.combat_blocked
                | ability_cast_locked
                | active_travel_view.combat_blocked
                | kamikaze_primed
            ),
            speed_multiplier=(
                charge_view.speed
                * positive_view.movement_speed_multiplier
                * slow_movement
                * ability_movement
            ),
            cooldown_decrement=cooldown_decrement,
            cooldown_floor_ticks=self._cooldown_floor_ticks,
            clear_source_lock=(
                stunned
                | pre_visibility.combat_blocked
                | active_travel_view.combat_blocked
                | kamikaze_primed
            ),
            reload_source_attack=(stunned | active_travel_view.combat_blocked),
            collision_excluded=active_travel_view.immune,
            river_jump_stunned=stunned,
        )
        safe_kamikaze_card = self.state.card_id.clamp(
            0, self.action_kernel.catalog.size - 1
        )
        kamikaze_delay = self.action_kernel.catalog.kamikaze_delay_ticks[
            safe_kamikaze_card
        ]
        kamikaze_prime_delay = self.action_kernel.catalog.kamikaze_prime_delay_ticks[
            safe_kamikaze_card
        ]
        kamikaze_known = (self.state.card_id > 0) & (
            self.state.card_id < self.action_kernel.catalog.size
        )
        delayed_kamikaze = kamikaze_known & (kamikaze_delay > 0)
        contact = combat.target_in_contact_range & delayed_kamikaze
        windup_before = self.entity_kamikaze_windup_ticks > 0
        start_windup = contact & ~kamikaze_primed & ~windup_before & ~stunned
        start_remaining = (kamikaze_prime_delay - 1).clamp_min(0)
        advance_windup = windup_before & contact & ~stunned
        advanced_windup = (self.entity_kamikaze_windup_ticks - 1).clamp_min(0)
        windup_completed = advance_windup & (advanced_windup == 0)
        immediate_prime = start_windup & (kamikaze_prime_delay <= 1)
        reset_windup = windup_before & ~contact & ~stunned
        windup_next = torch.where(
            start_windup,
            start_remaining,
            torch.where(
                advance_windup,
                advanced_windup,
                torch.where(
                    reset_windup,
                    torch.zeros_like(self.entity_kamikaze_windup_ticks),
                    self.entity_kamikaze_windup_ticks,
                ),
            ),
        )
        kamikaze_prime = immediate_prime | windup_completed
        live_primed = kamikaze_primed & self.state.active & (self.state.hp > 0)
        decrement_primed = live_primed & ~stunned
        decremented_timer = (self.entity_kamikaze_ticks - 1).clamp_min(0)
        kamikaze_next = torch.where(
            decrement_primed,
            decremented_timer,
            torch.where(
                live_primed,
                self.entity_kamikaze_ticks,
                torch.where(
                    kamikaze_prime,
                    kamikaze_delay,
                    torch.zeros_like(self.entity_kamikaze_ticks),
                ),
            ),
        )
        kamikaze_expired = decrement_primed & (kamikaze_next == 0)
        self.entity_kamikaze_windup_ticks.copy_(
            torch.where(kamikaze_prime, 0, windup_next)
        )
        self.entity_kamikaze_ticks.copy_(kamikaze_next)
        self.state.hp.masked_fill_(kamikaze_expired, 0.0)
        ramp_parameters = self._damage_ramp_parameters()
        ramp_target = torch.where(
            combat.target_in_attack_range,
            self.state.target_id,
            torch.zeros_like(self.state.target_id),
        )
        ramp = pre_attack_damage_ramp_(
            self.damage_ramp,
            ramp_parameters,
            current_target_stable_id=ramp_target,
            stunned=stunned,
        )
        if self.attack_timings is None:
            self.state.cooldown_ticks.copy_(
                torch.maximum(
                    self.state.cooldown_ticks,
                    ramp.retarget_delay_ticks,
                )
            )
            attack_ready = combat.attack_ready & (ramp.retarget_delay_ticks == 0)
        else:
            # Stable attack locks are the sole retarget-clock authority. The
            # ramp state still owns continuous-target stage progression and
            # its damage multiplier, but cannot install a second delay.
            attack_ready = combat.attack_ready
        attack_damage_multiplier = charge_view.damage * ramp.damage_multiplier
        commands = self._effect_commands(
            ingress,
            attack_ready,
            attack_damage_multiplier,
            scheduled_spell,
            rolling_spell,
        )
        allocation = allocate_fast_attack_effects_(
            self.state,
            self.effects,
            self.effect_consume_source_id,
            self.action_kernel.catalog,
            commands,
        )
        immediate_spell_allocated = allocation.accepted[:, :2]
        scheduled_or_immediate = (
            torch.where(
                scheduled_spell,
                scheduled_cast_allocation.accepted,
                immediate_spell_allocated,
            )
            if scheduled_cast_allocation is not None
            else immediate_spell_allocated
        )
        spell_allocated = torch.where(
            rolling_spell,
            rolling_allocation.accepted,
            scheduled_or_immediate,
        )
        attack_allocated = allocation.accepted[:, 2:]
        committed_attacks = self.combat.commit_attacks_(attack_ready, attack_allocated)
        advance_fast_charge_(
            self.modifiers,
            charge_parameters,
            active=self.state.active,
            moved_distance_units=combat.moved_distance_units,
            attacked=committed_attacks,
        )
        policy_visibility = step_fast_policy_visibility_(
            self.policy_catalog,
            self.policy_mechanics,
            active=self.state.active & (self.state.hp > 0),
            stable_id=self.state.stable_id,
            card_id=self.state.card_id,
            deployed=(
                self.state.active & (self.state.hp > 0) & (self.state.deploy_ticks == 0)
            ),
            attack_started=committed_attacks,
            has_attack_range_target=combat.target_in_attack_range,
            has_attack_target=self.combat.has_attack_range_target(),
            stunned=stunned,
        )
        self.state.target_id.masked_fill_(policy_visibility.clear_source_target, 0)
        self._publish_policy_visibility_(policy_visibility.view)
        self._publish_ability_mechanics_(abilities_before)
        self._publish_travel_mechanics_(self._travel_view())
        self._publish_river_jump_mechanics_()

        failed_deployment = (ingress.entity_deployment & ~deployed) | (
            ingress.spell_cast & ~spell_allocated
        )
        self.action_state.hand_ids.copy_(
            torch.where(
                failed_deployment[..., None], pre_hand, self.action_state.hand_ids
            )
        )
        self.action_state.cycle_ids.copy_(
            torch.where(
                failed_deployment[..., None], pre_cycle, self.action_state.cycle_ids
            )
        )
        self.action_state.cycle_head.copy_(
            torch.where(failed_deployment, pre_head, self.action_state.cycle_head)
        )
        self.action_state.elixir.copy_(
            torch.where(failed_deployment, pre_elixir, self.action_state.elixir)
        )

        multiplier = self._phase_multiplier()[:, None]
        self.action_kernel.regenerate_elixir_(
            self.action_state,
            tick_seconds=self.tick_seconds,
            multiplier=multiplier,
            live=(~self.state.game_over)[:, None].expand(-1, 2),
        )
        payload_result = step_fast_payload_containers_(self.payload_containers)
        payload_effect_allocation = allocate_fast_payload_effects_(
            self.state,
            self.effects,
            self.effect_consume_source_id,
            payload_result.effect_commands,
        )
        positive_area_allocation: FastPositiveBuffAreaAllocationResult | None = None
        positive_area_effect_allocation: FastPayloadEffectAllocationResult | None = None
        if self.spawn_blueprints is not None:
            positive_area_commands, positive_area_effect_commands = (
                positive_area_activation_commands(
                    self.spawn_blueprints,
                    payload_result.spawn_triggers,
                )
            )
            positive_area_allocation = allocate_fast_positive_buff_areas_(
                self.positive_buff_areas,
                positive_area_commands,
            )
            positive_area_effect_allocation = allocate_fast_payload_effects_(
                self.state,
                self.effects,
                self.effect_consume_source_id,
                replace(
                    positive_area_effect_commands,
                    ready=(
                        positive_area_effect_commands.ready
                        & positive_area_allocation.accepted
                    ),
                ),
            )
        scheduled_step: FastScheduledCastStepResult | None = None
        scheduled_effect_allocation: FastPayloadEffectAllocationResult | None = None
        scheduled_spawn_allocation: FastSpawnAllocationResult | None = None
        if self.scheduled_casts is not None:
            scheduled_step = step_fast_scheduled_casts_(
                self.scheduled_casts,
                tick=self.state.tick,
            )
            scheduled_effect_allocation = allocate_fast_payload_effects_(
                self.state,
                self.effects,
                self.effect_consume_source_id,
                self._scheduled_effect_commands(scheduled_step.effect_commands),
            )
            scheduled_spawn_allocation = allocate_fast_spawns_(
                self.state,
                self.action_kernel.catalog,
                self._scheduled_spawn_commands(scheduled_step.spawn_commands),
                reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
            )
            scheduled_spawned = scheduled_spawn_allocation.spawned_mask
            self._initialize_spawn_sidecars_(scheduled_spawned)
        effect_visibility = self._policy_visibility_view()
        effect_travel_view = self._travel_view()
        effect_receivable = ~effect_travel_view.immune
        effect_result = step_fast_effects(
            self.state,
            self.effects,
            self.entity_status_kind,
            self.entity_status_ticks,
            consume_source_id=self.effect_consume_source_id,
            cleanup_dead=False,
            modifiers=self.modifiers,
            entity_is_air=self._entity_airborne_target(),
            entity_collision_radius_units=self._entity_collision_radius_units(),
            entity_slow_ticks=self.entity_slow_ticks,
            slow_movement_multiplier_by_card=(
                self.action_kernel.catalog.slow_movement_multiplier
            ),
            slow_attack_multiplier_by_card=(
                self.action_kernel.catalog.slow_attack_multiplier
            ),
            entity_committed_direct_receivable=(
                effect_visibility.effect_receivable_affects_hidden & effect_receivable
            ),
            entity_secondary_targetable=(
                effect_visibility.secondary_targetable
                & (
                    ~abilities_before.effect_active
                    if abilities_before is not None
                    else torch.ones_like(self.state.active)
                )
                & effect_receivable
            ),
            entity_area_receivable=(
                effect_visibility.area_receivable & effect_receivable
            ),
            entity_effect_receivable_affects_hidden=(
                effect_visibility.effect_receivable_affects_hidden & effect_receivable
            ),
        )
        crown_slots = (
            torch.arange(
                self.state.max_entities, dtype=torch.int64, device=self.device
            )[None, :]
            < FAST_TOWER_SLOT_COUNT
        ).expand(self.batch_size, -1)
        rolling_result = step_fast_rolling_spells_(
            self.state,
            self.rolling_spells,
            entity_is_air=self._entity_airborne_target(),
            entity_collision_radius_units=self._entity_collision_radius_units(),
            entity_is_crown_tower=crown_slots,
            modifiers=self.modifiers,
            entity_area_receivable=(
                effect_visibility.area_receivable & effect_receivable
            ),
        )
        self.state.x_units.add_(rolling_result.impulse_dx_units).clamp_(0, 18_000)
        self.state.y_units.add_(rolling_result.impulse_dy_units).clamp_(0, 32_000)
        self._travel_interrupted.logical_or_(rolling_result.impulse_affected)
        rolling_spawn_allocation: FastSpawnAllocationResult | None = None
        if self.spawn_blueprints is not None:
            rolling_spawn_allocation = allocate_fast_spawns_(
                self.state,
                self.action_kernel.catalog,
                rolling_spawn_commands(
                    self.spawn_blueprints,
                    rolling_result.spawn,
                ),
                reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
            )
            rolling_spawned = rolling_spawn_allocation.spawned_mask
            self._initialize_spawn_sidecars_(rolling_spawned)
        # The first death pass commits defining DeathDamage before a triggered
        # secondary push can move recipients out of the source radius. The
        # second pass retains the fixed current-corpus cascade depth and also
        # catches entities killed by deploy-complete triggered areas.
        death_burst_first, death_effect_first = self._step_death_burst_pass()
        deploy_completed = pending_deploy_complete & (self.state.deploy_ticks == 0)
        triggered = self._resolve_triggered_impacts_(
            self._triggered_candidates(
                deploy_completed=deploy_completed,
                committed_attacks=committed_attacks,
                effect_result=effect_result,
                rolling_result=rolling_result,
                travel_result=travel_result,
            )
        )
        # Two fixed passes cover the current serialized terminal depth
        # (Golem -> Golemite) without a host-driven work queue. The first pass
        # commits all already-lethal novas simultaneously; the second catches
        # supported children killed by that committed damage before cleanup.
        death_burst_second, death_effect_second = self._step_death_burst_pass()
        payload_container_allocation: FastPayloadAllocationResult | None = None
        if self.spawn_blueprints is not None:
            payload_container_allocation = allocate_fast_payload_containers_(
                self.payload_containers,
                death_payload_container_commands(
                    self.spawn_blueprints,
                    self.state,
                ),
            )
        lifecycle_result = step_fast_lifecycle_(
            self.state,
            self.lifecycle,
            reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
        )
        self._clear_status_(lifecycle_result.resolved_parent_mask)
        self._clear_modifiers_(lifecycle_result.resolved_parent_mask)
        self._clear_damage_ramp_(lifecycle_result.resolved_parent_mask)
        self.policy_mechanics.clear_(lifecycle_result.resolved_parent_mask)
        self.travel.clear_(lifecycle_result.resolved_parent_mask)
        self._travel_spawned.masked_fill_(lifecycle_result.resolved_parent_mask, False)
        self._travel_interrupted.masked_fill_(
            lifecycle_result.resolved_parent_mask, False
        )
        self._initialize_spawn_sidecars_(
            lifecycle_result.spawned_mask,
            core_from_catalog=True,
        )
        spawn_allocation: FastSpawnAllocationResult | None = None
        if self.spawn_blueprints is not None:
            spawn_commands = impact_spawn_commands(
                self.spawn_blueprints,
                self.effects,
                effect_result.impacted,
            )
            spawn_allocation = allocate_fast_spawns_(
                self.state,
                self.action_kernel.catalog,
                spawn_commands,
                reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
            )
            self._initialize_spawn_sidecars_(spawn_allocation.spawned_mask)
        payload_spawn_allocation: FastSpawnAllocationResult | None = None
        if self.spawn_blueprints is not None:
            payload_spawn_allocation = allocate_fast_spawns_(
                self.state,
                self.action_kernel.catalog,
                payload_spawn_commands(
                    self.spawn_blueprints,
                    payload_result.spawn_triggers,
                ),
                reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
            )
            payload_spawned = payload_spawn_allocation.spawned_mask
            self._initialize_spawn_sidecars_(payload_spawned)
        periodic_spawn_allocation: FastSpawnAllocationResult | None = None
        if self.periodic_catalog is not None and self.periodic_spawns is not None:
            periodic_commands = step_periodic_spawns_(
                self.periodic_catalog,
                self.periodic_spawns,
                tick=self.state.tick,
                active=self.state.active,
                source_stable_id=self.state.stable_id,
                source_card_id=self.state.card_id,
                stunned=(
                    (self.entity_status_kind == FAST_STATUS_STUN)
                    & (self.entity_status_ticks > 0)
                ),
            )
            periodic_spawn_allocation = allocate_fast_spawns_(
                self.state,
                self.action_kernel.catalog,
                self._periodic_materialization_commands(periodic_commands),
                reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
            )
            periodic_spawned = periodic_spawn_allocation.spawned_mask
            self._initialize_spawn_sidecars_(periodic_spawned)
        positive_buff_advance = advance_fast_positive_buffs_(
            self.state,
            self.positive_buffs,
        )
        self._publish_policy_visibility_(self._policy_visibility_view())
        abilities_after: FastAbilityStepResult | None = None
        if self.ability_catalog is not None:
            abilities_after = step_fast_abilities_(
                self.state,
                self.abilities,
                self.ability_catalog,
                elixir=self.action_state.elixir,
                stunned=self._stunned(),
                player_alive=self.action_state.player_alive,
            )
        self._publish_ability_mechanics_(abilities_after)
        self._publish_travel_mechanics_(self._travel_view())
        self._publish_river_jump_mechanics_()
        self._entity_special.logical_or_(self.entity_kamikaze_ticks > 0)
        update_king_activation_(
            self.state,
            self._king_activation_delay_ticks,
            advance_clock=False,
        )
        outcome = self.outcomes.evaluate()
        self._refresh_policy_state()
        observation = self.projector.project(self._legal_action_mask())
        action_success = (
            torch.where(
                ingress.ability_activation,
                (
                    ability_activation.activated
                    if ability_activation is not None
                    else torch.zeros_like(ingress.accepted)
                ),
                torch.where(
                    ingress.entity_deployment,
                    deployed,
                    torch.where(
                        ingress.spell_cast,
                        spell_allocated,
                        ingress.accepted,
                    ),
                ),
            )
            & combat.committed[:, None]
        )
        return SimpleGymRuntimeStep(
            observation=observation,
            action_success=action_success,
            reward=outcome.reward,
            done=outcome.done,
            winner=outcome.winner,
            native_ticks=combat.native_ticks,
            committed=combat.committed,
            ability_activation=ability_activation,
            abilities=abilities_after,
            effect_allocation=allocation,
            effects=effect_result,
            lifecycle=lifecycle_result,
            payloads=payload_result,
            payload_effect_allocation=payload_effect_allocation,
            positive_area_step=positive_area_step,
            positive_buff_apply=positive_buff_apply,
            positive_buff_advance=positive_buff_advance,
            positive_area_allocation=positive_area_allocation,
            positive_area_effect_allocation=positive_area_effect_allocation,
            payload_container_allocation=payload_container_allocation,
            atomic_spawn_allocation=atomic_spawn_allocation,
            spawn_allocation=spawn_allocation,
            payload_spawn_allocation=payload_spawn_allocation,
            periodic_spawn_allocation=periodic_spawn_allocation,
            scheduled_cast_allocation=scheduled_cast_allocation,
            scheduled_casts=scheduled_step,
            scheduled_effect_allocation=scheduled_effect_allocation,
            scheduled_spawn_allocation=scheduled_spawn_allocation,
            rolling_allocation=rolling_allocation,
            rolling=rolling_result,
            rolling_spawn_allocation=rolling_spawn_allocation,
            death_bursts=(death_burst_first, death_burst_second),
            death_burst_effects=(death_effect_first, death_effect_second),
            policy_visibility=policy_visibility,
            travel=travel_result,
            travel_effect_allocation=travel_effect_allocation,
            travel_effects=travel_effect_result,
            travel_impulse=travel_impulse,
            triggered=triggered,
        )


__all__ = [
    "FastTriggeredEffectAllocation",
    "FastTriggeredEventAllocation",
    "FastTriggeredRuntimeStep",
    "SimpleGymRuntime",
    "SimpleGymRuntimeStep",
]
