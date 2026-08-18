"""Resident batched self-play boundary for tensor training rollouts.

This bridge owns decision-interval semantics around ``TensorResidentEngine``:
one simultaneous action/RNG transaction followed by zero or more action-free
logic ticks, exact dense rewards, terminal state, and resident observations.
Rows that cannot complete the interval stay explicitly marked for scalar
fallback and are never silently stepped through a different implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from clasher.battle import STANDARD_MATCH_TICKS, BattleState
from clasher.card_aliases import resolve_card_name
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder

from .actions import NO_OP_ACTION
from .catalog import TensorCardCatalog
from .observations import (
    TensorCvObservation,
    TensorObservationProjector,
    TensorStructuredObservation,
)
from .resident_engine import TensorResidentEngine


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

    structured: TensorStructuredObservation
    cv: TensorCvObservation
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
        projector: TensorObservationProjector,
        *,
        decision_interval_ticks: int = 8,
        max_ticks: int = STANDARD_MATCH_TICKS,
    ) -> None:
        if projector.state is not engine.runtime.battle:
            raise ValueError("observation projector must reference resident state")
        if decision_interval_ticks < 1:
            raise ValueError("decision_interval_ticks must be positive")
        if max_ticks < 1:
            raise ValueError("max_ticks must be positive")
        self.engine = engine
        self.projector = projector
        self.decision_interval_ticks = int(decision_interval_ticks)
        self.max_ticks = int(max_ticks)
        self._observed_entity_ids = engine.runtime.battle.entity_id.clone()
        self._entity_identity_lookup = self._compile_entity_identity_lookup()
        self._previous_potential = self._objective_potential()
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
        projector = TensorObservationProjector(
            engine.runtime.battle,
            battles,
            structured_builder=structured,
            cv_builder=cv,
        )
        bridge = cls(
            engine,
            projector,
            decision_interval_ticks=decision_interval_ticks,
            max_ticks=max_ticks,
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
        future_safe = (
            known
            & ((kind == 1) | (kind == 2))
            & (runtime.catalog.mechanic_count[safe] == 0)
            & (runtime.catalog.effect_count[safe] == 0)
            & ~self.engine.uses_projectile[safe]
            & ~self.engine.death_spawn[safe]
            & self.engine.deployment.materializer.catalog.supported_payload[safe]
            # Moving characters may later reach a river/path feature outside
            # current resident coverage. Route those episodes before IDs split.
            & (runtime.catalog.speed_units_per_tick[safe] == 0)
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

    def _compile_entity_identity_lookup(self) -> torch.Tensor:
        builder = self.projector.cv_builder
        values = []
        for name in self.engine.runtime.battle.card_names:
            identity = builder._entity_name_to_value.get(name)
            if identity is None:
                identity = builder._entity_name_to_value.get(
                    resolve_card_name(name), 0.0
                )
            values.append(float(identity))
        return torch.tensor(values, dtype=torch.float64, device=self.device)

    def _king_active(self) -> torch.Tensor:
        state = self.engine.runtime.battle
        active = self.engine.runtime.entity_pool.active & state.entity_active
        king = active & (state.entity_kind == 1) & (state.entity_tower_slot == 2)
        result = torch.zeros((self.batch_size, 2), dtype=torch.bool, device=self.device)
        for player in (0, 1):
            result[:, player] = (
                king & (state.entity_player == player) & state.entity_tower_active
            ).any(dim=1)
        return result

    def _objective_potential(self) -> torch.Tensor:
        state = self.engine.runtime.battle
        start = self.projector.starting_tower_hp
        start_princess = torch.clamp(0.5 * (start[:, :, 0] + start[:, :, 1]), min=1.0)
        princess_fraction = torch.clamp(
            0.5
            * (
                state.tower_hp[:, :, 0] / start_princess
                + state.tower_hp[:, :, 1] / start_princess
            ),
            0.0,
            1.0,
        )
        king_fraction = torch.clamp(
            state.tower_hp[:, :, 2] / torch.clamp(start[:, :, 2], min=1.0),
            0.0,
            1.0,
        )
        king_dead = state.tower_hp[:, :, 2] <= 0
        princess_dead = (state.tower_hp[:, :, :2] <= 0).sum(dim=2)
        lost = torch.where(king_dead, torch.full_like(princess_dead, 3), princess_dead)
        crowns = torch.stack((lost[:, 1], lost[:, 0]), dim=1)
        crown_diff = (crowns[:, 0] - crowns[:, 1]).to(torch.float64) / 3.0
        princess_pressure = princess_fraction[:, 0] - princess_fraction[:, 1]

        alive_count = (state.tower_hp[:, :, :2] > 0).sum(dim=2)
        active = self._king_active()
        enemy_alive = torch.stack((alive_count[:, 1], alive_count[:, 0]), dim=1)
        enemy_active = torch.stack((active[:, 1], active[:, 0]), dim=1)
        king_weight = torch.where(
            (enemy_alive == 2) & ~enemy_active,
            torch.zeros_like(king_fraction),
            torch.where(
                enemy_alive == 2,
                torch.full_like(king_fraction, 0.05),
                torch.where(
                    enemy_alive == 1,
                    torch.full_like(king_fraction, 0.25),
                    torch.full_like(king_fraction, 0.60),
                ),
            ),
        )
        king_pressure = king_weight[:, 0] * (1.0 - king_fraction[:, 1]) - (
            king_weight[:, 1] * (1.0 - king_fraction[:, 0])
        )

        alive_hp = torch.where(
            state.tower_hp > 0,
            state.tower_hp,
            torch.full_like(state.tower_hp, torch.inf),
        )
        lowest = alive_hp.min(dim=2).values
        tiebreak_scale = torch.clamp(start.amax(dim=(1, 2)), min=1.0) * 1_000.0
        tiebreak_edge = (lowest[:, 0] - lowest[:, 1]) / tiebreak_scale
        early_penalty = torch.where(
            alive_count[:, 1] == 2,
            1.0 - king_fraction[:, 1],
            0.0,
        ) - torch.where(
            alive_count[:, 0] == 2,
            1.0 - king_fraction[:, 0],
            0.0,
        )
        potential = (
            0.55 * crown_diff
            + 0.25 * princess_pressure
            + 0.10 * king_pressure
            + 0.10 * tiebreak_edge
            - 0.20 * early_penalty
        )
        return potential.clamp(-1.5, 1.5)

    def _refresh_observation_metadata(self) -> None:
        state = self.engine.runtime.battle
        active = self.engine.runtime.entity_pool.active & state.entity_active
        new = active & (state.entity_id != self._observed_entity_ids)
        catalog_id = self.engine.runtime.card_catalog_index[state.entity_card]
        safe = catalog_id.clamp_min(0)
        known = catalog_id >= 0
        projector = self.projector

        projector.entity_token.copy_(
            projector.structured_card_lookup[state.entity_card]
        )
        projector.entity_visible.copy_(active[:, None].expand(-1, 2, -1))
        projector.entity_airborne.copy_(
            self.engine.runtime.catalog.is_air_unit[safe] & known
        )
        projector.entity_is_building.copy_(state.entity_kind == 1)
        projector.entity_is_crown.copy_(state.entity_tower_slot >= 0)
        projector.entity_shield_current.zero_()
        projector.entity_shield_max.zero_()
        deploy_total = state.entity_deploy_delay + state.dt[:, None]
        projector.entity_deploy_total.copy_(
            torch.where(new, deploy_total, projector.entity_deploy_total)
        )
        projector.entity_stun.copy_(self.engine.runtime.status.stun_timer)
        projector.entity_slow.copy_(self.engine.runtime.status.slow_timer)
        projector.entity_haste.copy_(self.engine.runtime.status.haste_timer)
        projector.entity_special.zero_()
        projector.entity_stealth_until_ms.zero_()
        projector.entity_hidden_building.zero_()
        projector.entity_forced_movement.zero_()
        projector.entity_attack_windup.copy_(self.engine.combat.attack_windup_active)
        projector.entity_charging.zero_()
        projector.entity_speed.copy_(
            torch.where(
                known,
                self.engine.runtime.catalog.speed_units_per_tick[safe].to(
                    torch.float64
                ),
                projector.entity_speed,
            )
        )
        projector.entity_range.copy_(
            torch.where(
                known,
                self.engine.runtime.catalog.range_units[safe].to(torch.float64)
                / 1_000.0,
                projector.entity_range,
            )
        )
        projector.entity_sight_range.copy_(
            torch.where(
                known,
                self.engine.runtime.catalog.sight_range_units[safe].to(torch.float64)
                / 1_000.0,
                projector.entity_sight_range,
            )
        )
        projector.entity_collision_radius.copy_(
            torch.where(
                known,
                self.engine.runtime.catalog.collision_radius_units[safe].to(
                    torch.float64
                )
                / 1_000.0,
                projector.entity_collision_radius,
            )
        )
        projector.entity_facing_x.copy_(self.engine.facing_x_units.to(torch.float64))
        projector.entity_facing_y.copy_(self.engine.facing_y_units.to(torch.float64))
        projector.entity_effect_elapsed.zero_()
        projector.entity_effect_duration.zero_()
        projector.entity_damage.copy_(
            torch.where(
                known,
                self.engine.runtime.catalog.damage[safe],
                projector.entity_damage,
            )
        )
        projector.entity_identity.copy_(self._entity_identity_lookup[state.entity_card])
        self._observed_entity_ids.copy_(state.entity_id)

    def observe(
        self,
    ) -> tuple[TensorStructuredObservation, TensorCvObservation, torch.Tensor]:
        """Project observations and exact current resident action masks."""

        self._refresh_observation_metadata()
        action_state = self.engine.deployment.action_state(self.engine.runtime)
        masks = self.engine.deployment.kernel.legal_action_mask(action_state)
        return (
            self.projector.project_structured(),
            self.projector.project_cv(),
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
            result = self.engine.step(tick_actions, player_order=explicit_order)
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
            self._refresh_observation_metadata()

        resident = self._episode_resident
        current_potential = self._objective_potential()
        rewards = torch.zeros(
            (self.batch_size, 2), dtype=torch.float64, device=self.device
        )
        dense = current_potential - self._previous_potential
        rewards[:, 0] = dense
        rewards[:, 1] = -dense

        attempted = actions
        invalid = (attempted != NO_OP_ACTION) & ~action_success
        rewards -= 0.01 * invalid.to(torch.float64)
        pre_can_spend = (
            first_legal[:, :, :NO_OP_ACTION].any(dim=2)
            | first_legal[:, :, NO_OP_ACTION + 1]
        )
        direct_leak = (pre_elixir >= 9.9) & pre_can_spend & (attempted == NO_OP_ACTION)
        _, _, post_mask = self.observe()
        done = state.game_over | (state.tick >= self.max_ticks)
        post_can_spend = (
            post_mask[:, :, :NO_OP_ACTION].any(dim=2)
            | post_mask[:, :, NO_OP_ACTION + 1]
        )
        ongoing_leak = ~done[:, None] & (state.elixir >= 9.9) & post_can_spend
        penalties = 0.010 * direct_leak.to(torch.float64) + 0.005 * (
            ongoing_leak.to(torch.float64)
        )
        leak_edge = penalties[:, 1] - penalties[:, 0]
        rewards[:, 0] += leak_edge
        rewards[:, 1] -= leak_edge
        winner0 = done & (state.winner == 0)
        winner1 = done & (state.winner == 1)
        rewards[:, 0] += winner0.to(torch.float64) - winner1.to(torch.float64)
        rewards[:, 1] += winner1.to(torch.float64) - winner0.to(torch.float64)
        rewards *= resident[:, None]
        self._previous_potential.copy_(
            torch.where(resident, current_potential, self._previous_potential)
        )
        structured, cv, action_masks = self.observe()

        fallback_rows = torch.nonzero(fallback, as_tuple=False).flatten()
        fallback_actions = actions.index_select(0, fallback_rows)
        fallback_reasons = tuple(
            self._episode_route_reasons[row] for row in fallback_rows.tolist()
        )
        return ResidentSelfPlayStep(
            structured=structured,
            cv=cv,
            rewards=rewards,
            dones=done & resident,
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
    ) -> tuple[TensorStructuredObservation, TensorCvObservation, torch.Tensor]:
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
        replacement_projector = TensorObservationProjector(
            replacement.runtime.battle,
            battles,
            structured_builder=self.projector.structured_builder,
            cv_builder=self.projector.cv_builder,
        )
        self.engine._commit_rows(replacement, rows)
        _copy_projector_rows(self.projector, replacement_projector, rows)
        self._observed_entity_ids[rows] = self.engine.runtime.battle.entity_id[rows]
        reset_potential = self._objective_potential()
        self._previous_potential[rows] = reset_potential[rows]
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
