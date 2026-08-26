"""End-to-end runtime for the practical, unified tensor Gym.

The runtime owns the small policy/action state and the dense combat pool.  A
tick resolves the two player requests in stable player order, advances combat,
regenerates fractional elixir, resolves match outcomes, and returns an already
projected policy transition.  It has no dependency on ``BattleState``, scalar
entities, or the retained resident verifier.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .actions import NO_OP_ACTION
from .simple_actions import FastActionKernel, FastActionState
from .simple_catalog import FastCardCatalog
from .simple_effects import FastEffectState, FastEffectStepResult, step_fast_effects
from .simple_engine import FastTensorGym
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

    @property
    def device(self) -> torch.device:
        return self.state.device

    @property
    def batch_size(self) -> int:
        return self.state.batch_size

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

    def _legal_action_mask(self) -> torch.Tensor:
        mask = self.action_kernel.legal_action_mask(self.action_state)
        has_deploy_slot = (~self.state.active[:, FAST_TOWER_SLOT_COUNT:]).any(dim=1)
        mask[:, :, :NO_OP_ACTION] &= has_deploy_slot[:, None, None]
        return mask

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

        failed_deployment = ingress.deployment_accepted & ~deployed
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

        combat = self.combat.step_tick()
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
        )
        outcome = self.outcomes.evaluate()
        self._refresh_policy_state()
        observation = self.projector.project(self._legal_action_mask())
        action_success = (
            torch.where(
                ingress.deployment_accepted,
                deployed,
                ingress.accepted,
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
            effects=effect_result,
        )


__all__ = ["SimpleGymRuntime", "SimpleGymRuntimeStep"]
