"""Tensor-native training outputs from retained resident battle state.

Boundary construction reuses :class:`TensorObservationProjector` to compile
the exact Python observation vocabulary and immutable metadata once.  Every
subsequent structured/CV projection, reward, outcome, clone, and row fan-out
reads resident tensors directly and never synchronizes a ``BattleState``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import torch

from clasher.battle import STANDARD_MATCH_TICKS, BattleState
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.observations import (
    TOWER_ENTITY_TOKEN_NAMESPACE_INDEX,
    TensorCvObservation,
    TensorObservationProjector,
    TensorStructuredObservation,
)
from clasher.torch_sim.resident_engine import ResidentTickResult, TensorResidentEngine
from clasher.torch_sim.runtime_state import TensorBattleRuntime


@dataclass(frozen=True)
class TensorPublicStructuredObservation:
    """Actor-public tensors only; visible HP/status cues live in features."""

    entity_ids: torch.Tensor
    entity_features: torch.Tensor
    entity_mask: torch.Tensor
    hand_ids: torch.Tensor
    global_features: torch.Tensor


@dataclass(frozen=True)
class TensorPrivilegedCriticObservation:
    """Privileged simulator tensors, deliberately separate from actor input."""

    entity_ids: torch.Tensor
    entity_features: torch.Tensor
    entity_mask: torch.Tensor
    card_ids: torch.Tensor
    global_features: torch.Tensor


@dataclass(frozen=True)
class TensorPublicEventObservation:
    """Public card-play timeline projected for both player perspectives."""

    clock_seconds: torch.Tensor
    card_ids: torch.Tensor
    play_time_seconds: torch.Tensor
    age_seconds: torch.Tensor
    owner: torch.Tensor
    own: torch.Tensor
    deployment_x: torch.Tensor
    deployment_y: torch.Tensor
    valid: torch.Tensor


@dataclass(frozen=True)
class TensorResidentPublicOutputs:
    structured: TensorPublicStructuredObservation
    cv: TensorCvObservation
    events: TensorPublicEventObservation


@dataclass(frozen=True)
class TensorResidentProjectionBundle:
    """One live refresh shared by actor, optional critic, and CV projection."""

    public_structured: TensorPublicStructuredObservation
    privileged_critic: TensorPrivilegedCriticObservation | None
    cv: TensorCvObservation


@dataclass(frozen=True)
class TensorRewardOutcome:
    """Batched two-player reward and terminal outputs."""

    potential_p0: torch.Tensor
    win_probability_p0: torch.Tensor
    dense_reward: torch.Tensor
    reward: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor
    outcome: torch.Tensor


def tensor_objective_potential_p0(
    runtime: TensorBattleRuntime,
    starting_tower_hp: torch.Tensor,
) -> torch.Tensor:
    """Exact float64 tensor form of ``objective_potential_p0``."""

    tower_hp = runtime.battle.tower_hp
    if starting_tower_hp.shape != tower_hp.shape:
        raise ValueError("starting_tower_hp must have shape [batch, 2, 3]")
    if starting_tower_hp.device != runtime.device:
        raise ValueError("starting_tower_hp is on a different device")

    start_princess = torch.clamp(
        0.5 * (starting_tower_hp[:, :, 0] + starting_tower_hp[:, :, 1]),
        min=1.0,
    )
    princess_fraction = (
        (tower_hp[:, :, 0] / start_princess + tower_hp[:, :, 1] / start_princess) * 0.5
    ).clamp(0.0, 1.0)
    king_fraction = (
        tower_hp[:, :, 2] / torch.clamp(starting_tower_hp[:, :, 2], min=1.0)
    ).clamp(0.0, 1.0)

    king_dead = tower_hp[:, :, 2] <= 0.0
    side_lost = (tower_hp[:, :, :2] <= 0.0).sum(dim=2).to(torch.float64)
    towers_lost = torch.where(king_dead, torch.full_like(side_lost, 3.0), side_lost)
    crown_diff = (towers_lost[:, 1] - towers_lost[:, 0]) / 3.0
    princess_pressure = (1.0 - princess_fraction[:, 1]) - (
        1.0 - princess_fraction[:, 0]
    )

    princess_alive = (tower_hp[:, :, :2] > 0.0).sum(dim=2)
    crown_king = (
        runtime.entity_pool.active
        & runtime.battle.entity_active
        & (runtime.battle.entity_kind == 1)
        & (runtime.battle.entity_tower_slot == 2)
    )
    active_king_entity = crown_king & runtime.battle.entity_tower_active
    king_active = torch.stack(
        tuple(
            (active_king_entity & (runtime.battle.entity_player == player_id)).any(
                dim=1
            )
            for player_id in range(2)
        ),
        dim=1,
    )
    # The reward weighs damage to player 1's King by player 0 according to
    # player 1's Princess/activation state, and symmetrically for player 0.
    two = princess_alive == 2
    one = princess_alive == 1
    zero_weight = torch.zeros_like(king_fraction)
    king_weight = torch.where(
        two & ~king_active,
        zero_weight,
        torch.where(
            two,
            torch.full_like(king_fraction, 0.05),
            torch.where(
                one,
                torch.full_like(king_fraction, 0.25),
                torch.full_like(king_fraction, 0.60),
            ),
        ),
    )
    king_pressure = king_weight[:, 1] * (1.0 - king_fraction[:, 1]) - king_weight[
        :, 0
    ] * (1.0 - king_fraction[:, 0])

    standing = tower_hp > 0.0
    infinity = torch.full_like(tower_hp, torch.inf)
    lowest = torch.where(standing, tower_hp, infinity).amin(dim=2)
    lowest = torch.where(standing.any(dim=2), lowest, 0.0)
    lowest_fixed = torch.round(lowest * 1000.0)
    scale = torch.clamp(starting_tower_hp.amax(dim=(1, 2)), min=1.0) * 1000.0
    tiebreak_edge = (lowest_fixed[:, 0] - lowest_fixed[:, 1]) / scale

    early_king_chip = torch.where(princess_alive == 2, 1.0 - king_fraction, 0.0)
    early_king_penalty = early_king_chip[:, 1] - early_king_chip[:, 0]
    return (
        0.55 * crown_diff
        + 0.25 * princess_pressure
        + 0.10 * king_pressure
        + 0.10 * tiebreak_edge
        - 0.20 * early_king_penalty
    ).clamp(-1.5, 1.5)


@dataclass
class TensorRewardTracker:
    """Retained dense-reward baseline and one-shot terminal accounting."""

    starting_tower_hp: torch.Tensor
    previous_potential_p0: torch.Tensor
    terminal_emitted: torch.Tensor
    max_ticks: torch.Tensor

    @classmethod
    def create(
        cls,
        runtime: TensorBattleRuntime,
        starting_tower_hp: torch.Tensor,
        *,
        max_ticks: int | torch.Tensor = STANDARD_MATCH_TICKS,
    ) -> TensorRewardTracker:
        maximum = torch.as_tensor(max_ticks, dtype=torch.int64, device=runtime.device)
        maximum = torch.broadcast_to(maximum, (runtime.batch_size,)).clone()
        starts = starting_tower_hp.to(
            device=runtime.device, dtype=torch.float64
        ).clone()
        return cls(
            starting_tower_hp=starts,
            previous_potential_p0=tensor_objective_potential_p0(runtime, starts),
            terminal_emitted=torch.zeros(
                runtime.batch_size, dtype=torch.bool, device=runtime.device
            ),
            max_ticks=maximum,
        )

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorRewardTracker:
        indices = torch.as_tensor(
            rows, dtype=torch.int64, device=self.starting_tower_hp.device
        )
        if indices.ndim != 1 or indices.numel() < 1:
            raise ValueError("fork rows must be a non-empty vector")
        batch = self.previous_potential_p0.shape[0]
        if bool(((indices < 0) | (indices >= batch)).any().item()):
            raise IndexError("fork row is outside reward batch")
        return TensorRewardTracker(
            starting_tower_hp=self.starting_tower_hp.index_select(0, indices).clone(),
            previous_potential_p0=self.previous_potential_p0.index_select(
                0, indices
            ).clone(),
            terminal_emitted=self.terminal_emitted.index_select(0, indices).clone(),
            max_ticks=self.max_ticks.index_select(0, indices).clone(),
        )

    def clone(self) -> TensorRewardTracker:
        return self.fork(
            torch.arange(
                self.previous_potential_p0.shape[0],
                device=self.previous_potential_p0.device,
            )
        )

    def project(
        self,
        runtime: TensorBattleRuntime,
        *,
        commit: bool = True,
        action_ids: torch.Tensor | None = None,
        action_success: torch.Tensor | None = None,
        no_op_action: int | None = None,
        pre_elixir: torch.Tensor | None = None,
        pre_can_spend: torch.Tensor | None = None,
        post_can_spend: torch.Tensor | None = None,
    ) -> TensorRewardOutcome:
        """Project the exact environment reward components represented here.

        Optional action arguments add legacy invalid-action and elixir-leak
        terms.  Omitting them yields dense potential plus terminal reward.
        ``commit=False`` is a read-only search projection.
        """

        batch = runtime.batch_size
        if self.previous_potential_p0.shape != (batch,):
            raise ValueError("reward tracker batch differs from runtime")
        potential = tensor_objective_potential_p0(runtime, self.starting_tower_hp)
        delta = potential - self.previous_potential_p0
        dense = torch.stack((delta, -delta), dim=1)
        reward = dense.clone()
        done = runtime.battle.game_over | (runtime.battle.tick >= self.max_ticks)

        if action_ids is not None or action_success is not None:
            if action_ids is None or action_success is None or no_op_action is None:
                raise ValueError(
                    "action_ids, action_success, and no_op_action are required together"
                )
            actions = torch.as_tensor(
                action_ids, dtype=torch.int64, device=runtime.device
            )
            successes = torch.as_tensor(
                action_success, dtype=torch.bool, device=runtime.device
            )
            if actions.shape != (batch, 2) or successes.shape != (batch, 2):
                raise ValueError("action tensors must have shape [batch, 2]")
            invalid = (actions != int(no_op_action)) & ~successes
            reward -= invalid.to(torch.float64) * 0.01

        leak_arguments = (pre_elixir, pre_can_spend, post_can_spend)
        if any(value is not None for value in leak_arguments):
            if any(value is None for value in leak_arguments):
                raise ValueError("all elixir leak tensors are required together")
            if action_ids is None or no_op_action is None:
                raise ValueError("elixir leak projection requires action_ids")
            pre = torch.as_tensor(
                pre_elixir, dtype=torch.float64, device=runtime.device
            )
            pre_spend = torch.as_tensor(
                pre_can_spend, dtype=torch.bool, device=runtime.device
            )
            post_spend = torch.as_tensor(
                post_can_spend, dtype=torch.bool, device=runtime.device
            )
            if any(value.shape != (batch, 2) for value in (pre, pre_spend, post_spend)):
                raise ValueError("elixir leak tensors must have shape [batch, 2]")
            actions = torch.as_tensor(
                action_ids, dtype=torch.int64, device=runtime.device
            )
            direct = ((pre >= 9.9) & pre_spend & (actions == int(no_op_action))).to(
                torch.float64
            ) * 0.010
            ongoing = (~done[:, None] & (runtime.battle.elixir >= 9.9) & post_spend).to(
                torch.float64
            ) * 0.005
            penalty = direct + ongoing
            edge = penalty[:, 1] - penalty[:, 0]
            reward[:, 0] += edge
            reward[:, 1] -= edge

        terminal_now = done & ~self.terminal_emitted
        winner = runtime.battle.winner
        p0_win = terminal_now & (winner == 0)
        p1_win = terminal_now & (winner == 1)
        reward[:, 0] += p0_win.to(torch.float64) - p1_win.to(torch.float64)
        reward[:, 1] += p1_win.to(torch.float64) - p0_win.to(torch.float64)
        outcome = torch.stack(
            (
                (winner == 0).to(torch.float64) - (winner == 1).to(torch.float64),
                (winner == 1).to(torch.float64) - (winner == 0).to(torch.float64),
            ),
            dim=1,
        )
        outcome = torch.where(done[:, None], outcome, 0.0)
        terminal_probability = torch.where(
            winner == 0,
            1.0,
            torch.where(winner == 1, 0.0, 0.5),
        ).to(torch.float64)
        probability = torch.where(
            runtime.battle.game_over,
            terminal_probability,
            torch.sigmoid(2.5 * potential),
        )
        if commit:
            self.previous_potential_p0.copy_(potential)
            self.terminal_emitted |= terminal_now
        return TensorRewardOutcome(
            potential_p0=potential,
            win_probability_p0=probability,
            dense_reward=dense,
            reward=reward,
            done=done,
            winner=winner.clone(),
            outcome=outcome,
        )


class ResidentOutputProjector:
    """Live structured/CV/reward projection from a resident engine."""

    def __init__(
        self,
        *,
        runtime: TensorBattleRuntime,
        observations: TensorObservationProjector,
        rewards: TensorRewardTracker,
        engine: TensorResidentEngine | None,
        cv_identity_lookup: torch.Tensor,
        catalog_to_core_card: torch.Tensor,
        public_event_count: torch.Tensor,
        event_time_ms: torch.Tensor,
        event_player: torch.Tensor,
        event_card: torch.Tensor,
        event_x_units: torch.Tensor,
        event_y_units: torch.Tensor,
    ) -> None:
        self.runtime = runtime
        self.observations = observations
        self.rewards = rewards
        self.engine = engine
        self.cv_identity_lookup = cv_identity_lookup
        self.catalog_to_core_card = catalog_to_core_card
        self.public_event_count = public_event_count
        self.event_time_ms = event_time_ms
        self.event_player = event_player
        self.event_card = event_card
        self.event_x_units = event_x_units
        self.event_y_units = event_y_units
        self._event_slots = torch.arange(
            event_time_ms.shape[1], device=runtime.device
        ).view(1, -1)
        self._event_perspectives = torch.arange(2, device=runtime.device).view(1, 2, 1)
        self._command_indices = torch.arange(
            runtime.batch_size * 2, device=runtime.device
        )
        self.observations.state = runtime.battle

    @classmethod
    def from_engine(
        cls,
        engine: TensorResidentEngine,
        battles: Sequence[BattleState],
        *,
        structured_builder: StructuredObservationBuilder | None = None,
        cv_builder: CvObservationBuilder | None = None,
        max_entities: int | None = None,
        max_ticks: int | torch.Tensor = STANDARD_MATCH_TICKS,
    ) -> ResidentOutputProjector:
        capacity = engine.runtime.max_entities if max_entities is None else max_entities
        structured = structured_builder or StructuredObservationBuilder(
            max_entities=capacity
        )
        cv = cv_builder or CvObservationBuilder()
        observations = TensorObservationProjector(
            engine.runtime.battle,
            battles,
            structured_builder=structured,
            cv_builder=cv,
        )
        identity = torch.zeros(
            len(engine.runtime.battle.card_names),
            dtype=torch.float64,
            device=engine.device,
        )
        for card_id, name in enumerate(engine.runtime.battle.card_names):
            value = cv._entity_name_to_value.get(name)
            if value is not None:
                identity[card_id] = float(value)
        rewards = TensorRewardTracker.create(
            engine.runtime,
            observations.starting_tower_hp,
            max_ticks=max_ticks,
        )
        catalog_to_core = torch.tensor(
            [
                engine.runtime.battle.card_to_id.get(name, 0)
                for name in engine.runtime.catalog.names
            ],
            dtype=torch.int64,
            device=engine.device,
        )
        event_shape = (
            engine.runtime.batch_size,
            engine.runtime.events.capacity,
        )
        return cls(
            runtime=engine.runtime,
            observations=observations,
            rewards=rewards,
            engine=engine,
            cv_identity_lookup=identity,
            catalog_to_core_card=catalog_to_core,
            public_event_count=torch.zeros(
                engine.runtime.batch_size,
                dtype=torch.int32,
                device=engine.device,
            ),
            event_time_ms=torch.zeros(
                event_shape, dtype=torch.int64, device=engine.device
            ),
            event_player=torch.full(
                event_shape, -1, dtype=torch.int8, device=engine.device
            ),
            event_card=torch.zeros(
                event_shape, dtype=torch.int64, device=engine.device
            ),
            event_x_units=torch.zeros(
                event_shape, dtype=torch.int32, device=engine.device
            ),
            event_y_units=torch.zeros(
                event_shape, dtype=torch.int32, device=engine.device
            ),
        )

    @property
    def device(self) -> torch.device:
        return self.runtime.device

    @property
    def batch_size(self) -> int:
        return self.runtime.batch_size

    def _refresh_from_engine(self) -> None:
        engine = self.engine
        if engine is None:
            return
        if engine.runtime is not self.runtime:
            raise ValueError("resident engine runtime changed after projection binding")
        projection = self.observations
        core = self.runtime.battle
        catalog_id = self.runtime.card_catalog_index[core.entity_card]
        known = catalog_id >= 0
        safe = catalog_id.clamp_min(0)

        entity_kind = core.entity_kind.to(torch.int64).clamp(0, 4)
        token_namespace = torch.where(
            core.entity_tower_slot >= 0,
            torch.full_like(entity_kind, TOWER_ENTITY_TOKEN_NAMESPACE_INDEX),
            entity_kind,
        )
        token = projection.structured_entity_lookup[
            token_namespace,
            core.entity_card,
        ]
        projection.entity_visible.copy_(
            core.entity_active[:, None, :].expand(-1, 2, -1)
        )
        projection.entity_token.copy_(
            torch.where(core.entity_card > 0, token, projection.entity_token)
        )
        projection.entity_airborne.copy_(
            torch.where(
                known,
                self.runtime.catalog.is_air_unit[safe],
                projection.entity_airborne,
            )
        )
        projection.entity_is_building.copy_(core.entity_kind == 1)
        projection.entity_is_crown.copy_(core.entity_tower_slot >= 0)
        projection.entity_shield_current.copy_(engine.mechanics.shield_current)
        projection.entity_shield_max.copy_(engine.mechanics.shield_max)
        deploy_total = (
            self.runtime.catalog.deploy_time_ms[safe].to(torch.float64) / 1000.0
        )
        projection.entity_deploy_total.copy_(
            torch.where(known, deploy_total, projection.entity_deploy_total)
        )
        projection.entity_stun.copy_(self.runtime.status.stun_timer)
        projection.entity_slow.copy_(self.runtime.status.slow_timer)
        projection.entity_haste.copy_(self.runtime.status.haste_timer)
        projection.entity_special.copy_(
            engine.movement.special_movement
            | engine.movement.river_jump_active
            | engine.movement.charge_component
        )
        stealth_cards = core.entity_card.clamp(
            0, engine.stealth.catalog.hide_supported_core.numel() - 1
        )
        stealth_owned = (
            engine.stealth.catalog.hide_supported_core[stealth_cards]
            | engine.stealth.catalog.fade_supported_core[stealth_cards]
        )
        projection.entity_stealth_until_ms.copy_(
            torch.where(
                stealth_owned,
                engine.stealth.state.stealth_until_ms,
                engine.mechanics.stealth_until_ms,
            )
        )
        projection.entity_hidden_building.copy_(
            stealth_owned & engine.stealth.state.hidden_building
        )
        projection.entity_forced_movement.copy_(engine.movement.forced_movement)
        projection.entity_attack_windup.copy_(engine.combat.attack_windup_active)
        projection.entity_charging.copy_(engine.movement.charge_component)
        projection.entity_speed.copy_(engine.status.movement_speed)
        projection.entity_range.copy_(
            torch.where(
                known,
                self.runtime.catalog.range_units[safe].to(torch.float64) / 1000.0,
                projection.entity_range,
            )
        )
        projection.entity_sight_range.copy_(
            torch.where(
                known,
                self.runtime.catalog.sight_range_units[safe].to(torch.float64) / 1000.0,
                projection.entity_sight_range,
            )
        )
        projection.entity_collision_radius.copy_(
            torch.where(
                known,
                self.runtime.catalog.collision_radius_units[safe].to(torch.float64)
                / 1000.0,
                projection.entity_collision_radius,
            )
        )
        projection.entity_facing_x.copy_(engine.facing_x_units.to(torch.float64))
        projection.entity_facing_y.copy_(engine.facing_y_units.to(torch.float64))
        projection.entity_damage.copy_(
            torch.where(
                known,
                self.runtime.catalog.damage[safe],
                projection.entity_damage,
            )
        )
        projection.entity_identity.copy_(
            torch.where(
                core.entity_card > 0,
                self.cv_identity_lookup[core.entity_card],
                projection.entity_identity,
            )
        )

    def project_structured(self) -> TensorStructuredObservation:
        self._refresh_from_engine()
        return self.observations.project_structured()

    @staticmethod
    def _public_structured(
        projected: TensorStructuredObservation,
    ) -> TensorPublicStructuredObservation:
        return TensorPublicStructuredObservation(
            entity_ids=projected.entity_ids,
            entity_features=projected.entity_features,
            entity_mask=projected.entity_mask,
            hand_ids=projected.hand_ids,
            global_features=projected.global_features,
        )

    @staticmethod
    def _privileged_structured(
        projected: TensorStructuredObservation,
    ) -> TensorPrivilegedCriticObservation:
        return TensorPrivilegedCriticObservation(
            entity_ids=projected.critic_entity_ids,
            entity_features=projected.critic_entity_features,
            entity_mask=projected.critic_entity_mask,
            card_ids=projected.critic_card_ids,
            global_features=projected.critic_global_features,
        )

    def project_all(
        self,
        *,
        include_privileged_critic: bool = False,
    ) -> TensorResidentProjectionBundle:
        """Refresh once and share structured work across actor and critic."""

        self._refresh_from_engine()
        structured = self.observations.project_structured()
        return TensorResidentProjectionBundle(
            public_structured=self._public_structured(structured),
            privileged_critic=(
                self._privileged_structured(structured)
                if include_privileged_critic
                else None
            ),
            cv=self.observations.project_cv(),
        )

    def project_public_structured(self) -> TensorPublicStructuredObservation:
        return self._public_structured(self.project_structured())

    def project_privileged_critic(self) -> TensorPrivilegedCriticObservation:
        return self._privileged_structured(self.project_structured())

    def project_cv(self) -> TensorCvObservation:
        self._refresh_from_engine()
        return self.observations.project_cv()

    def capture_tick_events(self, result: ResidentTickResult) -> None:
        """Consume one tick's commands immediately and clear engine events.

        The deployment transaction owns card, player, and world-point facts
        even when the spawned source dies during the same tick. Capturing at
        this boundary also preserves the first tick's timestamp across a
        multi-tick decision interval.
        """

        if self.engine is None:
            raise ValueError("tick capture requires a live resident engine")
        commands = result.deployment.ingress.commands
        command_count = int(commands.battle_index.numel())
        if command_count:
            valid = (
                ~commands.is_ability
                & result.committed[commands.battle_index]
                & result.deployment.deployment.command_supported
            )
            battle = commands.battle_index[valid]
            player = commands.player_id[valid]
            card = commands.card_id[valid]
            x_units = commands.world_x_units[valid]
            y_units = commands.world_y_units[valid]
            if battle.numel():
                one_hot = torch.nn.functional.one_hot(
                    battle,
                    num_classes=self.batch_size,
                ).to(torch.int64)
                local_rank = torch.cumsum(one_hot, dim=0) - 1
                rank = local_rank[self._command_indices[: battle.numel()], battle]
                destination = self.public_event_count[battle].to(torch.int64) + rank
                additions = torch.bincount(battle, minlength=self.batch_size).to(
                    torch.int64
                )
                torch._assert_async(
                    (
                        self.public_event_count.to(torch.int64) + additions
                        <= self.event_time_ms.shape[1]
                    ).all(),
                    "public card-play event capacity exhausted before decision consume",
                )
                core_card = self.catalog_to_core_card[card]
                self.event_time_ms[battle, destination] = torch.round(
                    self.runtime.battle.time[battle] * 1000.0
                ).to(torch.int64)
                self.event_player[battle, destination] = player.to(torch.int8)
                self.event_card[battle, destination] = core_card
                self.event_x_units[battle, destination] = x_units.to(torch.int32)
                self.event_y_units[battle, destination] = y_units.to(torch.int32)
                self.public_event_count.add_(additions.to(torch.int32))
        # Runtime phase events have now been consumed for public output. They
        # must not accumulate across the episode and exhaust simulation space.
        self.runtime.events.clear(result.committed)

    def step_and_capture(
        self,
        action_ids: torch.Tensor | None = None,
        *,
        player_order: torch.Tensor | None = None,
    ) -> ResidentTickResult:
        if self.engine is None:
            raise ValueError("step_and_capture requires a live resident engine")
        result = self.engine.step(action_ids, player_order=player_order)
        self.capture_tick_events(result)
        return result

    def project_public_events(self) -> TensorPublicEventObservation:
        """Project public clock/card/timing/deployment facts, never critic state."""

        capacity = self.event_time_ms.shape[1]
        valid = (self._event_slots < self.public_event_count[:, None]) & (
            self.event_player >= 0
        )
        card = self.observations.structured_card_lookup[
            self.event_card.clamp(0, len(self.runtime.battle.card_names) - 1)
        ]
        perspectives = self._event_perspectives
        owner = self.event_player[:, None, :].expand(-1, 2, -1)
        x = self.event_x_units.to(torch.float64)[:, None, :].expand(-1, 2, -1)
        y = self.event_y_units.to(torch.float64)[:, None, :].expand(-1, 2, -1)
        if self.observations.canonical_structured:
            x = torch.where(perspectives == 1, 18_000.0 - x, x)
            y = torch.where(perspectives == 1, 32_000.0 - y, y)
        now = self.runtime.battle.time[:, None, None].expand(-1, 2, capacity)
        played = self.event_time_ms.to(torch.float64)[:, None, :] / 1000.0
        played = played.expand(-1, 2, -1)
        expanded_valid = valid[:, None, :].expand(-1, 2, -1)
        return TensorPublicEventObservation(
            clock_seconds=self.runtime.battle.time[:, None].expand(-1, 2),
            card_ids=torch.where(
                expanded_valid,
                card[:, None, :].expand(-1, 2, -1),
                0,
            ),
            play_time_seconds=torch.where(expanded_valid, played, 0.0),
            age_seconds=torch.where(expanded_valid, (now - played).clamp_min(0.0), 0.0),
            owner=torch.where(expanded_valid, owner, -1),
            own=expanded_valid & (owner == perspectives),
            deployment_x=torch.where(expanded_valid, x / 18_000.0, 0.0).to(
                torch.float32
            ),
            deployment_y=torch.where(expanded_valid, y / 32_000.0, 0.0).to(
                torch.float32
            ),
            valid=expanded_valid,
        )

    def consume_public_events(self) -> TensorPublicEventObservation:
        """Return the current decision interval's plays, then clear them."""

        projected = self.project_public_events()
        self.public_event_count.zero_()
        self.event_time_ms.zero_()
        self.event_player.fill_(-1)
        self.event_card.zero_()
        self.event_x_units.zero_()
        self.event_y_units.zero_()
        return projected

    def project_public(self) -> TensorResidentPublicOutputs:
        projected = self.project_all()
        return TensorResidentPublicOutputs(
            structured=projected.public_structured,
            cv=projected.cv,
            events=self.project_public_events(),
        )

    def project_reward_outcome(self, **kwargs: object) -> TensorRewardOutcome:
        return self.rewards.project(self.runtime, **kwargs)  # type: ignore[arg-type]

    def clone(
        self,
        *,
        engine: TensorResidentEngine | None = None,
    ) -> ResidentOutputProjector:
        self._refresh_from_engine()
        cloned_engine = (
            engine
            if engine is not None
            else self.engine.clone()
            if self.engine is not None
            else None
        )
        runtime = (
            cloned_engine.runtime if cloned_engine is not None else self.runtime.clone()
        )
        observations = self.observations.clone()
        observations.state = runtime.battle
        return type(self)(
            runtime=runtime,
            observations=observations,
            rewards=self.rewards.clone(),
            engine=cloned_engine,
            cv_identity_lookup=self.cv_identity_lookup,
            catalog_to_core_card=self.catalog_to_core_card,
            public_event_count=self.public_event_count.clone(),
            event_time_ms=self.event_time_ms.clone(),
            event_player=self.event_player.clone(),
            event_card=self.event_card.clone(),
            event_x_units=self.event_x_units.clone(),
            event_y_units=self.event_y_units.clone(),
        )

    def fork(
        self,
        rows: Sequence[int] | torch.Tensor,
    ) -> ResidentOutputProjector:
        """Fan out read/write output snapshots without Python battle rebuilds."""

        self._refresh_from_engine()
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        runtime = self.runtime.fork(indices)
        runtime.battle.rng = self.runtime.battle.rng.fork(indices)
        observations = self.observations.fork(indices)
        observations.state = runtime.battle
        return type(self)(
            runtime=runtime,
            observations=observations,
            rewards=self.rewards.fork(indices),
            engine=None,
            cv_identity_lookup=self.cv_identity_lookup,
            catalog_to_core_card=self.catalog_to_core_card,
            public_event_count=self.public_event_count.index_select(0, indices).clone(),
            event_time_ms=self.event_time_ms.index_select(0, indices).clone(),
            event_player=self.event_player.index_select(0, indices).clone(),
            event_card=self.event_card.index_select(0, indices).clone(),
            event_x_units=self.event_x_units.index_select(0, indices).clone(),
            event_y_units=self.event_y_units.index_select(0, indices).clone(),
        )


__all__ = [
    "ResidentOutputProjector",
    "TensorPrivilegedCriticObservation",
    "TensorPublicEventObservation",
    "TensorPublicStructuredObservation",
    "TensorResidentProjectionBundle",
    "TensorResidentPublicOutputs",
    "TensorRewardOutcome",
    "TensorRewardTracker",
    "tensor_objective_potential_p0",
]
