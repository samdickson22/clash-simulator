"""End-to-end runtime for the practical, unified tensor Gym.

The runtime owns the small policy/action state and the dense combat pool.  A
tick resolves the two player requests in stable player order, advances combat,
regenerates fractional elixir, resolves match outcomes, and returns an already
projected policy transition.  It has no dependency on ``BattleState``, scalar
entities, or the retained resident verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES

from .actions import NO_OP_ACTION
from .simple_actions import FastActionIngressResult, FastActionKernel, FastActionState
from .simple_attack_effects import (
    FastEffectAllocationResult,
    FastEffectCommands,
    allocate_fast_attack_effects_,
)
from .simple_catalog import FastCardCatalog
from .simple_effects import FastEffectState, FastEffectStepResult, step_fast_effects
from .simple_engine import FastTensorGym
from .simple_lifecycle import FastLifecycleState, step_fast_lifecycle_
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
)
from .simple_projection import (
    SimpleProjectedObservation,
    SimpleProjectionInputs,
    SimpleTensorProjector,
)
from .simple_state import FastGymState


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
    effect_allocation: FastEffectAllocationResult
    effects: FastEffectStepResult


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
        starting_elixir: float = 6.0,
        max_elixir: float = 10.0,
        include_privileged_critic: bool = False,
        tick_seconds: float = 0.05,
        double_elixir_tick: int | None = None,
        triple_elixir_tick: int | None = None,
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

        self.state = FastGymState.empty(
            int(deck_ids.shape[0]),
            max_entities=max_entities,
            device=catalog.device,
        )
        initialize_crown_towers_(self.state, tower_spec)
        self.action_state = FastActionState.from_decks(
            deck_ids,
            starting_elixir=starting_elixir,
            max_elixir=max_elixir,
        )
        self.action_kernel = FastActionKernel(catalog)
        self.combat = FastTensorGym(
            self.state,
            catalog,
            reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
        )
        self.effects = FastEffectState.empty(
            self.state.batch_size,
            max_effects=max_effects,
            device=self.state.device,
        )
        self.lifecycle = FastLifecycleState.empty_like(self.state)
        self.modifiers = FastModifierState.empty(
            self.state.batch_size,
            max_entities=self.state.max_entities,
            device=self.state.device,
        )
        entity_shape = (self.state.batch_size, self.state.max_entities)
        self.entity_status_kind = torch.zeros(
            entity_shape, dtype=torch.int8, device=self.state.device
        )
        self.entity_status_ticks = torch.zeros(
            entity_shape, dtype=torch.int32, device=self.state.device
        )
        self.effect_consume_source_id = torch.zeros(
            (self.state.batch_size, max_effects),
            dtype=torch.int64,
            device=self.state.device,
        )
        self.outcomes = FastOutcomeTracker(self.state, rules)
        self.tick_seconds = float(tick_seconds)
        self.double_elixir_tick = double_elixir_tick
        self.triple_elixir_tick = triple_elixir_tick

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
        self._effect_owners = (
            torch.arange(2, dtype=torch.int8, device=device)
            .view(1, 2)
            .expand(batch, -1)
        )
        self._spell_source_slots = torch.tensor(
            (2, 5), dtype=torch.int64, device=device
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

    @staticmethod
    def _tensor_fields(value: object) -> dict[str, torch.Tensor]:
        """Clone batch-leading tensor fields without retaining object graphs."""

        return {
            descriptor.name: tensor.clone()
            for descriptor in fields(value)
            if isinstance((tensor := getattr(value, descriptor.name)), torch.Tensor)
        }

    def _capture_initial_templates(self) -> dict[str, dict[str, torch.Tensor]]:
        """Capture the constructed episode state as device-resident tensors.

        These templates deliberately contain no ``BattleState`` or scalar
        simulator objects.  Selective resets therefore remain ordinary dense
        tensor mutations and do not rebuild the runtime, catalog, or projector.
        """

        return {
            "state": self._tensor_fields(self.state),
            "action": self._tensor_fields(self.action_state),
            "effects": self._tensor_fields(self.effects),
            "lifecycle": self._tensor_fields(self.lifecycle),
            "modifiers": self._tensor_fields(self.modifiers),
            "outcomes": {
                "initial_tower_hp": self.outcomes.initial_tower_hp.clone(),
                "previous_tower_hp": self.outcomes.previous_tower_hp.clone(),
                "previous_crowns": self.outcomes.previous_crowns.clone(),
                "overtime": self.outcomes.overtime.clone(),
            },
            "runtime": {
                "entity_status_kind": self.entity_status_kind.clone(),
                "entity_status_ticks": self.entity_status_ticks.clone(),
                "effect_consume_source_id": self.effect_consume_source_id.clone(),
                "projection_hand_ids": self._projection_hand_ids.clone(),
                "double_elixir": self._double_elixir.clone(),
                "triple_elixir": self._triple_elixir.clone(),
                "ability_cooldown": self._ability_cooldown.clone(),
                "ability_duration": self._ability_duration.clone(),
                "refill_cooldown_ms": self._refill_cooldown_ms.clone(),
                "public_visibility": self.projector.inputs.public_visibility.clone(),
                "combat_spawned_mask": self.combat.spawned_mask.clone(),
                "combat_target_unavailable": self.combat._target_unavailable.clone(),
            },
        }

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

        objects = {
            "state": self.state,
            "action": self.action_state,
            "effects": self.effects,
            "lifecycle": self.lifecycle,
            "modifiers": self.modifiers,
            "outcomes": self.outcomes,
        }
        for group, owner in objects.items():
            for name, template in self._initial_templates[group].items():
                self._restore_rows_(getattr(owner, name), template, reset_mask)

        runtime_tensors = {
            "entity_status_kind": self.entity_status_kind,
            "entity_status_ticks": self.entity_status_ticks,
            "effect_consume_source_id": self.effect_consume_source_id,
            "projection_hand_ids": self._projection_hand_ids,
            "double_elixir": self._double_elixir,
            "triple_elixir": self._triple_elixir,
            "ability_cooldown": self._ability_cooldown,
            "ability_duration": self._ability_duration,
            "refill_cooldown_ms": self._refill_cooldown_ms,
            "public_visibility": self.projector.inputs.public_visibility,
            "combat_spawned_mask": self.combat.spawned_mask,
            "combat_target_unavailable": self.combat._target_unavailable,
        }
        for name, destination in runtime_tensors.items():
            self._restore_rows_(
                destination, self._initial_templates["runtime"][name], reset_mask
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

    def _refresh_policy_state(self) -> None:
        tower_hp = crown_tower_hp(self.state)
        tower_alive = tower_hp > 0
        self.action_state.tower_alive.copy_(tower_alive)
        self.action_state.player_alive.copy_(
            tower_alive[:, :, 2] & ~self.state.game_over[:, None]
        )
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
        self._refresh_policy_state()
        return self.projector.project(self._legal_action_mask())

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

    def _legal_action_mask(self) -> torch.Tensor:
        mask = self.action_kernel.legal_action_mask(self.action_state)
        free_deploy_slots = (~self.state.active[:, FAST_TOWER_SLOT_COUNT:]).sum(dim=1)
        has_effect_slot = (~self.effects.active).any(dim=1)
        hand = self.action_state.hand_ids
        safe_card = hand.clamp(0, self.action_kernel.catalog.size - 1)
        spell = (self.action_kernel.catalog.kind[safe_card] < 0) & (
            self.action_kernel.catalog.effect_kind[safe_card] >= 0
        )
        enough_deploy_slots = free_deploy_slots[:, None, None] >= (
            self.action_kernel.catalog.summon_count[safe_card].to(torch.int64)
        )
        capacity = torch.where(
            spell,
            has_effect_slot[:, None, None],
            enough_deploy_slots,
        )
        placement_capacity = (
            capacity[..., None]
            .expand(-1, -1, NUM_HAND_SLOTS, NUM_TILES)
            .reshape(self.batch_size, 2, NO_OP_ACTION)
        )
        mask[:, :, :NO_OP_ACTION] &= placement_capacity
        return mask

    def _effect_commands(
        self,
        ingress: FastActionIngressResult,
        attack_ready: torch.Tensor,
        attack_damage_multiplier: torch.Tensor,
    ) -> FastEffectCommands:
        """Put policy spell casts before entity-slot-ordered attacks."""

        spell_source_x = self.state.x_units.index_select(1, self._spell_source_slots)
        spell_source_y = self.state.y_units.index_select(1, self._spell_source_slots)
        zeros_i64 = torch.zeros_like(ingress.selected_card_ids)
        ones_spell = torch.ones_like(ingress.selected_card_ids, dtype=torch.float32)
        spell = FastEffectCommands(
            ready=ingress.spell_cast,
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
        deployed = self.combat.deploy_many_once(ingress.requests)
        self._initialize_lifecycle_(self.combat.spawned_mask)
        self._initialize_modifiers_(self.combat.spawned_mask)

        charge_parameters = self._charge_parameters()
        charge_view = pre_move_charge_multipliers(self.modifiers, charge_parameters)
        combat = self.combat.step_tick(
            disabled=self.entity_status_ticks > 0,
            speed_multiplier=charge_view.speed,
        )
        commands = self._effect_commands(
            ingress, combat.attack_ready, charge_view.damage
        )
        allocation = allocate_fast_attack_effects_(
            self.state,
            self.effects,
            self.effect_consume_source_id,
            self.action_kernel.catalog,
            commands,
        )
        spell_allocated = allocation.accepted[:, :2]
        attack_allocated = allocation.accepted[:, 2:]
        committed_attacks = self.combat.commit_attacks_(
            combat.attack_ready, attack_allocated
        )
        advance_fast_charge_(
            self.modifiers,
            charge_parameters,
            active=self.state.active,
            moved_distance_units=combat.moved_distance_units,
            attacked=committed_attacks,
        )

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
        effect_result = step_fast_effects(
            self.state,
            self.effects,
            self.entity_status_kind,
            self.entity_status_ticks,
            consume_source_id=self.effect_consume_source_id,
            cleanup_dead=False,
            modifiers=self.modifiers,
            entity_is_air=self.action_kernel.catalog.is_air[
                self.state.card_id.clamp(0, self.action_kernel.catalog.size - 1)
            ],
            entity_collision_radius_units=(
                self.action_kernel.catalog.collision_radius_units[
                    self.state.card_id.clamp(0, self.action_kernel.catalog.size - 1)
                ]
            ),
        )
        lifecycle_result = step_fast_lifecycle_(
            self.state,
            self.lifecycle,
            reserved_slot_floor=FAST_TOWER_SLOT_COUNT,
        )
        self.entity_status_kind.masked_fill_(lifecycle_result.resolved_parent_mask, 0)
        self.entity_status_ticks.masked_fill_(lifecycle_result.resolved_parent_mask, 0)
        self._clear_modifiers_(lifecycle_result.resolved_parent_mask)
        self._initialize_spawned_combat_(lifecycle_result.spawned_mask)
        self._initialize_lifecycle_(lifecycle_result.spawned_mask)
        self._initialize_modifiers_(lifecycle_result.spawned_mask)
        outcome = self.outcomes.evaluate()
        self._refresh_policy_state()
        observation = self.projector.project(self._legal_action_mask())
        action_success = (
            torch.where(
                ingress.entity_deployment,
                deployed,
                torch.where(
                    ingress.spell_cast,
                    spell_allocated,
                    ingress.accepted,
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
            effect_allocation=allocation,
            effects=effect_result,
        )


__all__ = ["SimpleGymRuntime", "SimpleGymRuntimeStep"]
