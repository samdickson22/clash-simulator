"""Resident batched self-play boundary for tensor training rollouts.

This bridge owns decision-interval semantics around ``TensorResidentEngine``:
one simultaneous action/RNG transaction followed by zero or more action-free
logic ticks, exact dense rewards, terminal state, and resident observations.
Rows that cannot complete the interval stay explicitly marked for scalar
fallback and are never silently stepped through a different implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from clasher.battle import STANDARD_MATCH_TICKS, BattleState
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder

from .actions import NO_OP_ACTION
from .catalog import TensorCardCatalog
from .observations import TensorObservationProjector
from .resident_engine import TensorResidentEngine
from .resident_outputs import (
    ResidentOutputProjector,
    TensorPrivilegedCriticObservation,
    TensorResidentPublicOutputs,
    TensorRewardOutcome,
)
from .resident_workspace import TensorResidentWorkspace


@dataclass(frozen=True)
class ResidentFallbackRows:
    """Tensor boundary state needed to route rejected rows to an oracle."""

    mask: torch.Tensor
    row_indices: torch.Tensor
    action_ids: torch.Tensor
    reasons: tuple[str | None, ...]
    ticks_completed: torch.Tensor
    tick_at_boundary: torch.Tensor
    time_at_boundary: torch.Tensor
    scalar_battles: tuple[BattleState, ...]


@dataclass(frozen=True)
class ResidentSelfPlayStep:
    """One batched self-play decision result, resident on the engine device."""

    public: TensorResidentPublicOutputs
    privileged_critic: TensorPrivilegedCriticObservation | None
    reward_outcome: TensorRewardOutcome
    rewards: torch.Tensor
    dones: torch.Tensor
    observation_valid: torch.Tensor
    action_success: torch.Tensor
    action_masks: torch.Tensor
    ticks_advanced: torch.Tensor
    player_order: torch.Tensor
    fallback: ResidentFallbackRows


class ResidentEpisodeCoverageError(RuntimeError):
    """Raised instead of unsafe mid-episode scalar rehydration."""


def _copy_projector_rows(
    destination: TensorObservationProjector,
    source: TensorObservationProjector,
    rows: torch.Tensor,
) -> None:
    batch_size = destination.state.batch_size
    for name, left in vars(destination).items():
        if name == "state" or name in destination._SHARED_TENSOR_NAMES:
            continue
        right = getattr(source, name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim > 0
            and left.shape == right.shape
            and left.shape[0] == batch_size
        ):
            left[rows] = right[rows]


class TensorResidentSelfPlay:
    """Batched self-play environment semantics over a retained tensor engine."""

    def __init__(
        self,
        engine: TensorResidentEngine,
        outputs: ResidentOutputProjector,
        *,
        decision_interval_ticks: int = 8,
        max_ticks: int = STANDARD_MATCH_TICKS,
        include_privileged_critic: bool = False,
    ) -> None:
        if outputs.runtime is not engine.runtime or outputs.engine is not engine:
            raise ValueError("output projector must own the resident engine")
        if decision_interval_ticks < 1:
            raise ValueError("decision_interval_ticks must be positive")
        if max_ticks < 1:
            raise ValueError("max_ticks must be positive")
        self.engine = engine
        self.workspace = TensorResidentWorkspace(engine)
        self.outputs = outputs
        self.projector = outputs.observations
        self.decision_interval_ticks = int(decision_interval_ticks)
        self.max_ticks = int(max_ticks)
        self.include_privileged_critic = bool(include_privileged_critic)
        self._scalar_roots: list[BattleState] = []
        self._episode_resident = torch.ones(
            self.batch_size, dtype=torch.bool, device=self.device
        )
        self._episode_route_reasons: list[str | None] = [None] * self.batch_size

    @property
    def device(self) -> torch.device:
        return self.engine.device

    @property
    def batch_size(self) -> int:
        return self.engine.batch_size

    @classmethod
    def from_battles(
        cls,
        battles: list[BattleState] | tuple[BattleState, ...],
        *,
        device: str | torch.device = "cpu",
        decision_interval_ticks: int = 8,
        max_ticks: int = STANDARD_MATCH_TICKS,
        max_entities: int = 128,
        max_objects: int = 128,
        event_capacity: int = 512,
        catalog: TensorCardCatalog | None = None,
        structured_builder: StructuredObservationBuilder | None = None,
        cv_builder: CvObservationBuilder | None = None,
        include_privileged_critic: bool = False,
    ) -> TensorResidentSelfPlay:
        if not battles:
            raise ValueError("at least one battle is required")
        engine = TensorResidentEngine.from_battles(
            battles,
            device=device,
            max_entities=max_entities,
            max_objects=max_objects,
            event_capacity=event_capacity,
            catalog=catalog,
        )
        structured = structured_builder or StructuredObservationBuilder(
            max_entities=max_entities
        )
        cv = cv_builder or CvObservationBuilder()
        outputs = ResidentOutputProjector.from_engine(
            engine,
            battles,
            structured_builder=structured,
            cv_builder=cv,
            max_entities=max_entities,
            max_ticks=max_ticks,
        )
        bridge = cls(
            engine,
            outputs,
            decision_interval_ticks=decision_interval_ticks,
            max_ticks=max_ticks,
            include_privileged_critic=include_privileged_critic,
        )
        bridge._scalar_roots = [battle.clone() for battle in battles]
        admitted, reasons = bridge._episode_admission()
        bridge._episode_resident.copy_(admitted)
        bridge._episode_route_reasons = reasons
        bridge.engine.runtime.supported[~admitted] = False
        return bridge

    def _episode_admission(self) -> tuple[torch.Tensor, list[str | None]]:
        """Route rows before mutation unless every future card is guaranteed."""

        runtime = self.engine.runtime
        state = runtime.battle
        noops = torch.full(
            (self.batch_size, 2),
            NO_OP_ACTION,
            dtype=torch.int64,
            device=self.device,
        )
        preflight = self.engine.preflight(noops)
        diagnostics = self.engine.diagnose_preflight(noops)
        core_cards = torch.cat(
            (
                state.deck,
                state.hand,
                state.cycle_queue,
            ),
            dim=2,
        )
        catalog_id = runtime.card_catalog_index[core_cards]
        live = core_cards != 0
        safe = catalog_id.clamp_min(0)
        known = (catalog_id >= 0) | ~live
        kind = runtime.catalog.kind[safe]
        deploy_ticks = torch.ceil(
            runtime.catalog.deploy_time_ms[safe].to(torch.float64)
            / state.tick_milliseconds[:, None, None].clamp_min(1).to(torch.float64)
        ).to(torch.int64)
        remaining_episode_ticks = (self.max_ticks - state.tick).clamp_min(0)[
            :, None, None
        ]
        movement_cannot_begin = (runtime.catalog.speed_units_per_tick[safe] == 0) | (
            remaining_episode_ticks <= deploy_ticks
        )
        future_safe = (
            known
            & ((kind == 1) | (kind == 2))
            & (runtime.catalog.mechanic_count[safe] == 0)
            & (runtime.catalog.effect_count[safe] == 0)
            & ~self.engine.uses_projectile[safe]
            & ~self.engine.death_spawn[safe]
            & self.engine.deployment.materializer.catalog.supported_payload[safe]
            # Moving characters are admitted only when the complete remaining
            # episode ends before their deployment timer can reach movement.
            & movement_cannot_begin
        ) | ~live
        all_future_safe = future_safe.all(dim=2).all(dim=1)
        admitted = (preflight.supported & all_future_safe) | state.game_over
        reasons: list[str | None] = []
        for row in range(self.batch_size):
            if bool(admitted[row].item()):
                reasons.append(None)
            elif not bool(preflight.supported[row].item()):
                reasons.append(diagnostics.reasons[row])
            else:
                reasons.append(
                    "episode deck can reach mechanics, projectiles, spawns, or "
                    "movement/pathing outside guaranteed resident coverage"
                )
        return admitted, reasons

    def observe(
        self,
    ) -> tuple[
        TensorResidentPublicOutputs,
        TensorPrivilegedCriticObservation | None,
        torch.Tensor,
    ]:
        """Project separated actor/critic outputs and resident action masks."""

        action_state = self.engine.deployment.action_state(self.engine.runtime)
        masks = self.engine.deployment.kernel.legal_action_mask(action_state)
        return (
            self.outputs.project_public(),
            (
                self.outputs.project_privileged_critic()
                if self.include_privileged_critic
                else None
            ),
            masks,
        )

    def step(self, action_ids: torch.Tensor) -> ResidentSelfPlayStep:
        actions = torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        if actions.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        state = self.engine.runtime.battle
        pre_elixir = state.elixir.clone()
        start_eligible = (
            self._episode_resident & ~state.game_over & (state.tick < self.max_ticks)
        )
        ticks = torch.zeros(self.batch_size, dtype=torch.int64, device=self.device)
        fallback = ~self._episode_resident & ~state.game_over
        action_success = torch.zeros(
            (self.batch_size, 2), dtype=torch.bool, device=self.device
        )
        player_order = (
            torch.tensor([0, 1], dtype=torch.int64, device=self.device)
            .expand(self.batch_size, -1)
            .clone()
        )
        first_legal = self.engine.deployment.kernel.legal_action_mask(
            self.engine.deployment.action_state(self.engine.runtime)
        )

        active = start_eligible.clone()
        for logic_tick in range(self.decision_interval_ticks):
            needs_tick = active & ~state.game_over & (state.tick < self.max_ticks)
            finished = active & ~needs_tick
            if bool(finished.any().item()):
                self.engine.runtime.supported[finished] = False
                active &= ~finished
            if not bool(needs_tick.any().item()):
                break
            tick_actions = (
                actions if logic_tick == 0 else torch.full_like(actions, NO_OP_ACTION)
            )
            explicit_order = None if logic_tick == 0 else player_order
            result = self.workspace.step(
                tick_actions,
                player_order=explicit_order,
            )
            self.outputs.capture_tick_events(result)
            if logic_tick == 0:
                action_success = (
                    result.deployment.ingress.accepted & result.committed[:, None]
                )
                player_order.copy_(result.deployment.deployment.player_order)
            committed = result.committed & needs_tick
            ticks.add_(committed.to(torch.int64))
            failed = needs_tick & ~committed
            if bool(failed.any().item()):
                diagnostics = self.engine.diagnose_preflight(tick_actions)
                failed_rows = torch.nonzero(failed, as_tuple=False).flatten().tolist()
                details = "; ".join(
                    f"row {row}: {diagnostics.reasons[row] or 'resident phase rejected'}"
                    for row in failed_rows
                )
                raise ResidentEpisodeCoverageError(
                    "resident episode lost guaranteed coverage after tensor "
                    "mutation; scalar fallback is unsafe because entity identity "
                    f"sets may have diverged ({details})"
                )
            active &= committed

        resident = self._episode_resident
        pre_can_spend = (
            first_legal[:, :, :NO_OP_ACTION].any(dim=2)
            | first_legal[:, :, NO_OP_ACTION + 1]
        )
        post_state = self.engine.deployment.action_state(self.engine.runtime)
        post_mask = self.engine.deployment.kernel.legal_action_mask(post_state)
        post_can_spend = (
            post_mask[:, :, :NO_OP_ACTION].any(dim=2)
            | post_mask[:, :, NO_OP_ACTION + 1]
        )
        raw_outcome = self.outputs.project_reward_outcome(
            action_ids=actions,
            action_success=action_success,
            no_op_action=NO_OP_ACTION,
            pre_elixir=pre_elixir,
            pre_can_spend=pre_can_spend,
            post_can_spend=post_can_spend,
        )
        reward_outcome = TensorRewardOutcome(
            potential_p0=raw_outcome.potential_p0,
            win_probability_p0=raw_outcome.win_probability_p0,
            dense_reward=raw_outcome.dense_reward * resident[:, None],
            reward=raw_outcome.reward * resident[:, None],
            done=raw_outcome.done & resident,
            winner=raw_outcome.winner,
            outcome=raw_outcome.outcome * resident[:, None],
        )
        public = TensorResidentPublicOutputs(
            structured=self.outputs.project_public_structured(),
            cv=self.outputs.project_cv(),
            events=self.outputs.consume_public_events(),
        )
        privileged = (
            self.outputs.project_privileged_critic()
            if self.include_privileged_critic
            else None
        )
        action_state = self.engine.deployment.action_state(self.engine.runtime)
        action_masks = self.engine.deployment.kernel.legal_action_mask(action_state)

        fallback_rows = torch.nonzero(fallback, as_tuple=False).flatten()
        fallback_actions = actions.index_select(0, fallback_rows)
        fallback_reasons = tuple(
            self._episode_route_reasons[row] for row in fallback_rows.tolist()
        )
        return ResidentSelfPlayStep(
            public=public,
            privileged_critic=privileged,
            reward_outcome=reward_outcome,
            rewards=reward_outcome.reward,
            dones=reward_outcome.done,
            observation_valid=resident,
            action_success=action_success,
            action_masks=action_masks,
            ticks_advanced=ticks,
            player_order=player_order,
            fallback=ResidentFallbackRows(
                mask=fallback,
                row_indices=fallback_rows,
                action_ids=fallback_actions,
                reasons=fallback_reasons,
                ticks_completed=ticks.index_select(0, fallback_rows),
                tick_at_boundary=state.tick.index_select(0, fallback_rows).clone(),
                time_at_boundary=state.time.index_select(0, fallback_rows).clone(),
                scalar_battles=tuple(
                    self._scalar_roots[row] for row in fallback_rows.tolist()
                ),
            ),
        )

    def reset_rows(
        self,
        battles: list[BattleState] | tuple[BattleState, ...],
        reset_mask: torch.Tensor,
    ) -> tuple[
        TensorResidentPublicOutputs,
        TensorPrivilegedCriticObservation | None,
        torch.Tensor,
    ]:
        """Replace selected resident rows with supplied freshly reset battles."""

        if len(battles) != self.batch_size:
            raise ValueError("reset battles must match resident batch size")
        rows = torch.as_tensor(reset_mask, dtype=torch.bool, device=self.device)
        if rows.shape != (self.batch_size,):
            raise ValueError("reset_mask must have shape [batch]")
        replacement = TensorResidentEngine.from_battles(
            battles,
            device=self.device,
            max_entities=self.engine.runtime.max_entities,
            max_objects=self.engine.objects.objects.max_objects,
            event_capacity=self.engine.runtime.events.capacity,
            catalog=self.engine.runtime.catalog,
        )
        replacement_outputs = ResidentOutputProjector.from_engine(
            replacement,
            battles,
            structured_builder=self.projector.structured_builder,
            cv_builder=self.projector.cv_builder,
            max_entities=self.projector.max_entities,
            max_ticks=self.max_ticks,
        )
        self.engine._commit_rows(replacement, rows)
        _copy_projector_rows(self.projector, replacement_outputs.observations, rows)
        for descriptor in fields(self.outputs.rewards):
            destination = getattr(self.outputs.rewards, descriptor.name)
            source = getattr(replacement_outputs.rewards, descriptor.name)
            destination[rows] = source[rows]
        for name in (
            "public_event_count",
            "event_time_ms",
            "event_player",
            "event_card",
            "event_x_units",
            "event_y_units",
        ):
            destination = getattr(self.outputs, name)
            source = getattr(replacement_outputs, name)
            destination[rows] = source[rows]
        selected_rows = torch.nonzero(rows, as_tuple=False).flatten().tolist()
        for row in selected_rows:
            self._scalar_roots[row] = battles[row].clone()
        admitted, reasons = self._episode_admission()
        self._episode_resident[rows] = admitted[rows]
        for row in selected_rows:
            self._episode_route_reasons[row] = reasons[row]
        self.engine.runtime.supported[rows & ~admitted] = False
        return self.observe()


__all__ = [
    "ResidentEpisodeCoverageError",
    "ResidentFallbackRows",
    "ResidentSelfPlayStep",
    "TensorResidentSelfPlay",
]
