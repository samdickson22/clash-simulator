"""Mode selection, tensor tick kernels, and fail-closed fallback."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

import torch

from clasher.balance import (
    DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS,
    EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS,
)
from clasher.battle import BattleState
from clasher.entities import Building, Troop

from .diagnostics import TorchParityError, battle_snapshot, first_divergence
from .state import WINNER_DRAW, TensorBattleFork, TensorBattleState


class SimulatorBackend(str, Enum):
    PYTHON = "python"
    PYTORCH_SHADOW = "pytorch-shadow"
    PYTORCH = "pytorch"


@dataclass
class BackendMetrics:
    tensor_ticks: int = 0
    python_ticks: int = 0
    shadow_checks: int = 0
    shadow_mismatches: int = 0
    unsupported_fallbacks: int = 0

    def as_dict(self) -> dict[str, float]:
        return {
            "tensor_ticks": float(self.tensor_ticks),
            "python_ticks": float(self.python_ticks),
            "shadow_checks": float(self.shadow_checks),
            "shadow_mismatches": float(self.shadow_mismatches),
            "unsupported_fallbacks": float(self.unsupported_fallbacks),
        }


def _static_tower_tensor_inert(battle: BattleState, tower: Building) -> bool:
    """Return whether a Crown Tower has only the tensorized visual clock."""

    if (
        not tower.is_alive
        or tower.mechanics
        or tower.deploy_delay_remaining > 1e-9
        or tower.target_id is not None
        or tower._attack_windup_active
        or tower.attack_cooldown
        > tower.get_preloaded_attack_time_seconds() + 1e-9
        or tower.stun_timer > 1e-9
        or tower.slow_timer > 1e-9
        or tower.haste_timer > 1e-9
        or tower.freeze_expiry_time > battle.time + 1e-9
        or tower._slow_effects
        or tower._haste_effects
        or tower._periodic_damage_effects
        or bool(getattr(tower, "_buff_active", False))
        or tower.forced_movement_active
        or tower._knockback_target is not None
        or tower._death_spawn_travel_ticks_remaining > 0
        or tower.activation_delay_remaining > 1e-9
        or tower.activation_first_hit_delay_remaining > 1e-9
    ):
        return False
    if not bool(getattr(tower, "_tower_active", False)):
        return True
    include_crown_fallback = bool(
        tower.range
        > tower.sight_range
        + float(EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS) / 1000.0
    )
    return (
        tower.get_nearest_target(
            battle.entities,
            include_crown_fallback=include_crown_fallback,
        )
        is None
    )


def _deployment_only_tensor_supported(battle: BattleState) -> bool:
    """Return whether every non-Crown object is inert and still deploying."""

    if battle.game_over or battle._pending_spell_casts:
        return False
    deploying_troops: list[Troop] = []
    for entity in battle.entities.values():
        if battle._is_static_tower_entity(entity):
            if not isinstance(entity, Building) or not _static_tower_tensor_inert(
                battle, entity
            ):
                return False
            continue
        if not isinstance(entity, (Troop, Building)):
            return False
        if (
            not entity.is_alive
            or entity.deploy_delay_remaining <= 1e-9
            or not entity.placement_pending
            or entity.mechanics
            or entity.forced_movement_active
            or entity._knockback_target is not None
            or entity._death_spawn_travel_ticks_remaining > 0
            or entity._death_spawn_target_immunity_elapsed_ms >= 0
            or entity.stun_timer > 0
            or entity.freeze_expiry_time > battle.time
            or entity.slow_timer > 0
            or entity.haste_timer > 0
            or entity._slow_effects
            or entity._haste_effects
            or entity._periodic_damage_effects
            or bool(getattr(entity, "_buff_active", False))
            or getattr(entity, "_native_avoidance", 0) != 0
            or entity._movement_vector_count != 0
            or not entity._pending_movement_consumed
        ):
            return False
        if isinstance(entity, Troop):
            deploying_troops.append(entity)
        else:
            lifetime_ms = getattr(entity.card_stats, "lifetime_ms", None)
            if lifetime_ms and lifetime_ms > 0:
                deployment_frames = math.ceil(
                    entity.deploy_delay_remaining / battle.dt - 1e-9
                )
                native_ticks = int(
                    (
                        entity.lifetime_tick_carry_ms
                        + deployment_frames * battle.dt * 1000.0
                        + 1e-9
                    )
                    // 50.0
                )
                decay_rate = (
                    5000
                    * round(entity.max_hitpoints)
                    // int(lifetime_ms)
                )
                lifetime_loss = (
                    entity.lifetime_decay_work + decay_rate * native_ticks
                ) // 100
                # Scalar cleanup and death hooks are outside this slice.
                if entity.hitpoints - lifetime_loss <= 0:
                    return False

    # Deployment frames still execute body-pressure collection. Restrict this
    # slice to states whose exact collision result is the zero vector.
    collision_objects = [
        entity
        for entity in battle.entities.values()
        if entity.is_alive and entity.entity_kind in {0, 1}
    ]
    for troop in deploying_troops:
        for other in collision_objects:
            if other is troop:
                continue
            minimum = troop.get_collision_radius() + other.get_collision_radius()
            # Native emits a one-unit pressure vector even at exact contact.
            if troop.position.distance_to(other.position) <= minimum:
                return False
    return any(
        not battle._is_static_tower_entity(entity)
        for entity in battle.entities.values()
    )


def _tensor_slice_supported(battle: BattleState) -> bool:
    """Current exact coverage: inert Crown state or inert character deployment."""

    return bool(
        battle.can_fast_forward_idle()
        or _deployment_only_tensor_supported(battle)
    )


def _crowns_for_players(state: TensorBattleState) -> torch.Tensor:
    king_dead = state.tower_hp[:, :, 2] <= 0
    side_lost = (state.tower_hp[:, :, :2] <= 0).sum(dim=2).to(torch.int8)
    towers_lost = torch.where(
        king_dead,
        torch.full_like(side_lost, 3),
        side_lost,
    )
    return torch.stack((towers_lost[:, 1], towers_lost[:, 0]), dim=1)


def _refill_cooldown_for_time(time: torch.Tensor) -> torch.Tensor:
    result = torch.full_like(
        time,
        int(DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS[-1][1]),
        dtype=torch.int32,
    )
    for segment_end, cooldown_ms in reversed(
        DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS[:-1]
    ):
        result = torch.where(
            time < float(segment_end) - 1e-9,
            torch.full_like(result, int(cooldown_ms)),
            result,
        )
    return result


def _tick_players(state: TensorBattleState, active: torch.Tensor) -> None:
    base_regen = torch.where(
        state.triple_elixir,
        torch.full_like(state.time, 0.93),
        torch.where(
            state.double_elixir,
            torch.full_like(state.time, 1.4),
            torch.full_like(state.time, 2.8),
        ),
    )
    delta = (1.0 / base_regen) * state.dt
    next_elixir = torch.minimum(state.max_elixir, state.elixir + delta[:, None])
    state.elixir.copy_(torch.where(active[:, None], next_elixir, state.elixir))

    reduced = torch.clamp(
        state.refill_cooldown_ms - state.tick_milliseconds[:, None],
        min=0,
    )
    cooldown = torch.where(
        state.refill_cooldown_ms > 0,
        reduced,
        state.refill_cooldown_ms,
    )
    state.refill_cooldown_ms.copy_(
        torch.where(active[:, None], cooldown, state.refill_cooldown_ms)
    )

    empty = state.hand == 0
    eligible = (
        active[:, None]
        & (state.refill_cooldown_ms == 0)
        & (state.cycle_queue_length > 0)
        & empty.any(dim=2)
    )
    first_empty = empty.to(torch.int8).argmax(dim=2)
    next_card = state.cycle_queue[:, :, 0]
    batch_index = torch.arange(state.batch_size, device=state.device)[:, None]
    player_index = torch.arange(2, device=state.device)[None, :]
    current = state.hand[batch_index, player_index, first_empty]
    state.hand[batch_index, player_index, first_empty] = torch.where(
        eligible, next_card, current
    )

    shifted = torch.zeros_like(state.cycle_queue)
    shifted[:, :, :-1] = state.cycle_queue[:, :, 1:]
    state.cycle_queue.copy_(
        torch.where(eligible[:, :, None], shifted, state.cycle_queue)
    )
    state.cycle_queue_length.copy_(
        torch.where(
            eligible,
            state.cycle_queue_length - 1,
            state.cycle_queue_length,
        )
    )
    refill = _refill_cooldown_for_time(state.time)
    state.refill_cooldown_ms.copy_(
        torch.where(eligible, refill[:, None], state.refill_cooldown_ms)
    )


def _check_win_conditions(state: TensorBattleState, active: torch.Tensor) -> None:
    king_alive = state.tower_hp[:, :, 2] > 0
    any_king_dead = ~king_alive.all(dim=1)
    both_dead = ~king_alive.any(dim=1)
    king_winner = torch.where(
        both_dead,
        torch.full_like(state.winner, WINNER_DRAW),
        torch.where(
            king_alive[:, 0],
            torch.zeros_like(state.winner),
            torch.ones_like(state.winner),
        ),
    )
    finish_by_king = active & any_king_dead
    state.game_over |= finish_by_king
    state.winner.copy_(torch.where(finish_by_king, king_winner, state.winner))

    still_active = active & ~finish_by_king
    crowns = _crowns_for_players(state)
    crown_unequal = crowns[:, 0] != crowns[:, 1]
    regulation_boundary = (
        still_active
        & (state.time >= state.overtime_start_time)
        & ~state.sudden_death
    )
    regulation_win = regulation_boundary & crown_unequal
    crown_winner = torch.where(
        crowns[:, 0] > crowns[:, 1],
        torch.zeros_like(state.winner),
        torch.ones_like(state.winner),
    )
    state.game_over |= regulation_win
    state.winner.copy_(torch.where(regulation_win, crown_winner, state.winner))
    enter_sudden_death = regulation_boundary & ~crown_unequal
    state.sudden_death |= enter_sudden_death
    state.sudden_death_crowns.copy_(
        torch.where(
            enter_sudden_death[:, None],
            crowns,
            state.sudden_death_crowns,
        )
    )

    sudden_active = still_active & ~regulation_win & state.sudden_death
    sudden_win = sudden_active & crown_unequal
    state.game_over |= sudden_win
    state.winner.copy_(torch.where(sudden_win, crown_winner, state.winner))

    tiebreak = (
        sudden_active & ~sudden_win & (state.time >= state.tiebreaker_time)
    )
    alive_hp = torch.where(
        state.tower_hp > 0,
        state.tower_hp,
        torch.full_like(state.tower_hp, torch.inf),
    )
    lowest = alive_hp.min(dim=2).values
    tiebreak_winner = torch.where(
        lowest[:, 0] > lowest[:, 1],
        torch.zeros_like(state.winner),
        torch.where(
            lowest[:, 1] > lowest[:, 0],
            torch.ones_like(state.winner),
            torch.full_like(state.winner, WINNER_DRAW),
        ),
    )
    state.game_over |= tiebreak
    state.winner.copy_(torch.where(tiebreak, tiebreak_winner, state.winner))
    state.active.copy_(~state.game_over)


def step_idle_tensor_ticks(state: TensorBattleState, ticks: int) -> torch.Tensor:
    """Advance supported idle/deployment ticks without Python object stepping."""

    requested = max(0, int(ticks))
    advanced = torch.zeros((state.batch_size,), dtype=torch.int64, device=state.device)
    for _ in range(requested):
        deploying = (
            state.entity_active
            & (state.entity_tower_slot < 0)
            & (state.entity_id != 0)
        )
        newly_actionable = (
            deploying & (state.entity_deploy_delay <= 1e-9)
        ).any(dim=1)
        active = state.active & ~state.game_over & ~newly_actionable
        if not bool(active.any().item()):
            break
        state.time.add_(torch.where(active, state.dt, 0.0))
        state.tick.add_(active.to(torch.int64))
        state.double_elixir |= active & (
            state.time >= state.double_elixir_start_time
        )
        state.overtime |= active & (state.time >= state.overtime_start_time)
        state.triple_elixir |= active & (
            state.time >= state.triple_elixir_start_time
        )
        _tick_players(state, active)
        active_towers = (
            active[:, None]
            & state.entity_active
            & (state.entity_tower_slot >= 0)
            & state.entity_tower_active
        )
        state.entity_last_attack_time.add_(
            active_towers.to(torch.float64) * state.dt[:, None]
        )
        deployment_mask = active[:, None] & deploying
        deploying_buildings = (
            deployment_mask
            & (state.entity_kind == 1)
            & (state.entity_lifetime_ms > 0)
        )
        lifetime_tick_ms = torch.where(
            deploying_buildings,
            state.dt[:, None] * 1000.0,
            torch.zeros_like(state.entity_lifetime_tick_carry_ms),
        )
        state.entity_lifetime_elapsed.add_(
            deploying_buildings.to(torch.float64) * state.dt[:, None]
        )
        total_lifetime_tick_ms = (
            state.entity_lifetime_tick_carry_ms + lifetime_tick_ms
        )
        native_lifetime_ticks = torch.floor(
            (total_lifetime_tick_ms + 1e-9) / 50.0
        ).to(torch.int64)
        state.entity_lifetime_tick_carry_ms.copy_(
            torch.where(
                deploying_buildings,
                total_lifetime_tick_ms
                - native_lifetime_ticks.to(torch.float64) * 50.0,
                state.entity_lifetime_tick_carry_ms,
            )
        )
        lifetime_work = (
            state.entity_lifetime_decay_work
            + state.entity_lifetime_decay_rate * native_lifetime_ticks
        )
        whole_hp_loss = torch.div(lifetime_work, 100, rounding_mode="floor")
        state.entity_lifetime_decay_work.copy_(
            torch.where(
                deploying_buildings,
                torch.remainder(lifetime_work, 100),
                state.entity_lifetime_decay_work,
            )
        )
        state.entity_hp.copy_(
            torch.where(
                deploying_buildings,
                torch.clamp(
                    state.entity_hp - whole_hp_loss.to(torch.float64),
                    min=0.0,
                ),
                state.entity_hp,
            )
        )
        # Preserve the pre-tick values: ``copy_`` below mutates the retained
        # tensor in place, and an alias would make the zero-crossing predicate
        # observe only post-tick values.
        previous_deploy_delay = state.entity_deploy_delay.clone()
        next_deploy_delay = torch.clamp(
            previous_deploy_delay - state.dt[:, None],
            min=0.0,
        )
        state.entity_deploy_delay.copy_(
            torch.where(
                deployment_mask,
                next_deploy_delay,
                previous_deploy_delay,
            )
        )
        deployment_finished = (
            deployment_mask
            & (previous_deploy_delay > 0)
            & (state.entity_deploy_delay <= 1e-9)
        )
        state.entity_placement_pending &= ~deployment_finished
        state.entity_spawn_hook_pending &= ~deployment_finished
        state.entity_spawn_hook_fired |= deployment_finished
        timer_boundary = (
            ~state.sudden_death & (state.time >= state.overtime_start_time)
        ) | (state.sudden_death & (state.time >= state.tiebreaker_time))
        if bool((active & timer_boundary).any().item()):
            _check_win_conditions(state, active)
        advanced.add_(active.to(torch.int64))
    return advanced


class TorchBattleExecutor:
    """Execute Python, shadow, or PyTorch-on ticks with fail-closed fallback."""

    def __init__(
        self,
        backend: str | SimulatorBackend = SimulatorBackend.PYTHON,
        *,
        device: str | torch.device = "cpu",
    ) -> None:
        self.backend = SimulatorBackend(backend)
        self.device = torch.device(device)
        self.metrics = BackendMetrics()
        self._state: TensorBattleState | None = None
        self._battle_identities: tuple[int, ...] = ()
        self._primed_fork: TensorBattleFork | None = None

    def prime_tensor_fork(
        self,
        battles: Sequence[BattleState],
        tensor_fork: TensorBattleFork,
    ) -> None:
        """Bind an exact tensor fork to scalar clones for the next step.

        Search code can capture a root once and cheaply clone its tensors for
        each simulation.  Binding fails closed unless the behavior-bearing
        scalar snapshot is still exact.  If actions mutate a bound battle
        before the step, ``_state_for`` discards the stale fork and re-encodes
        the new scalar state.
        """

        if self.backend is not SimulatorBackend.PYTORCH:
            raise ValueError("tensor forks require the pytorch backend")
        if not tensor_fork.matches_battles(battles):
            raise ValueError("tensor fork does not match scalar battle state")
        self._state = tensor_fork._materialize_state()
        self._battle_identities = tuple(id(battle) for battle in battles)
        self._primed_fork = tensor_fork

    def _state_for(self, battles: Sequence[BattleState]) -> TensorBattleState:
        identities = tuple(id(battle) for battle in battles)
        use_primed_state = False
        if self._primed_fork is not None:
            if self._primed_fork.matches_battles(battles):
                use_primed_state = True
            else:
                self._state = None
                self._battle_identities = ()
            self._primed_fork = None
        rebuild = (
            self._state is None
            or self._battle_identities != identities
            or any(
                not self._state.clocks_match(battle, batch_index)
                for batch_index, battle in enumerate(battles)
            )
        )
        if rebuild:
            self._state = TensorBattleState.from_battles(battles, device=self.device)
            self._battle_identities = identities
        elif not use_primed_state:
            # Action ingress and callers still mutate the authoritative Python
            # battle between decision windows. Refresh the retained storage at
            # that boundary so same-clock changes cannot be overwritten by a
            # stale tensor snapshot. Once ingress is tensor-native this copy is
            # removed and the state remains resident across decisions too.
            assert self._state is not None
            try:
                self._state.load_battles(battles)
            except (IndexError, ValueError):
                self._state = TensorBattleState.from_battles(
                    battles, device=self.device
                )
        assert self._state is not None
        return self._state

    def _fallback(self, battle: BattleState, ticks: int) -> int:
        advanced = battle.step_logic_ticks(ticks)
        self.metrics.python_ticks += advanced
        self.metrics.unsupported_fallbacks += 1
        self._state = None
        self._battle_identities = ()
        self._primed_fork = None
        return advanced

    def step_logic_ticks(self, battle: BattleState, ticks: int) -> int:
        return self.step_battles([battle], ticks)[0]

    def step_battles(
        self,
        battles: Sequence[BattleState],
        ticks: int,
    ) -> list[int]:
        """Advance multiple battles through one retained tensor batch.

        Unsupported members fail closed independently. Supported members are
        grouped into one tensor state/kernel call, including in mixed batches.
        """

        if not battles:
            return []
        requested = max(0, int(ticks))
        if self.backend is SimulatorBackend.PYTHON:
            advanced = [battle.step_logic_ticks(requested) for battle in battles]
            self.metrics.python_ticks += sum(advanced)
            return advanced

        supported_indices = [
            index
            for index, battle in enumerate(battles)
            if _tensor_slice_supported(battle)
        ]
        supported_set = set(supported_indices)
        unsupported_indices = [
            index for index in range(len(battles)) if index not in supported_set
        ]
        if unsupported_indices:
            advanced = [0 for _ in battles]
            for index in unsupported_indices:
                advanced[index] = self._fallback(battles[index], requested)
            if supported_indices:
                tensor_advanced = self.step_battles(
                    [battles[index] for index in supported_indices],
                    requested,
                )
                for index, count in zip(supported_indices, tensor_advanced):
                    advanced[index] = count
            return advanced

        if self.backend is SimulatorBackend.PYTORCH_SHADOW:
            candidates = [battle.clone() for battle in battles]
            advanced = [battle.step_logic_ticks(requested) for battle in battles]
            tensor_state = TensorBattleState.from_battles(
                candidates, device=self.device
            )
            tensor_counts = step_idle_tensor_ticks(tensor_state, requested)
            tensor_state.sync_to_battles(candidates)
            self.metrics.python_ticks += sum(advanced)
            self.metrics.tensor_ticks += sum(
                int(count) for count in tensor_counts.tolist()
            )
            self.metrics.shadow_checks += len(battles)
            for index, count in enumerate(tensor_counts.tolist()):
                remaining = advanced[index] - int(count)
                if remaining > 0:
                    candidates[index].step_logic_ticks(remaining)
                    self.metrics.unsupported_fallbacks += 1
            for index, (battle, candidate) in enumerate(zip(battles, candidates)):
                mismatch = first_divergence(
                    battle_snapshot(battle),
                    battle_snapshot(candidate),
                    path=f"battles[{index}]",
                )
                if mismatch is not None:
                    self.metrics.shadow_mismatches += 1
                    raise TorchParityError(mismatch)
            return advanced

        state = self._state_for(battles)
        tensor_counts = step_idle_tensor_ticks(state, requested)
        state.sync_to_battles(battles)
        tensor_advanced = [int(count) for count in tensor_counts.tolist()]
        self.metrics.tensor_ticks += sum(tensor_advanced)
        advanced = tensor_advanced.copy()
        for index, count in enumerate(tensor_advanced):
            remaining = requested - count
            if remaining > 0 and not battles[index].game_over:
                advanced[index] += self._fallback(battles[index], remaining)
        return advanced

    def metrics_dict(self) -> dict[str, float]:
        return self.metrics.as_dict()

    def pop_metrics(self) -> dict[str, float]:
        result = self.metrics.as_dict()
        self.metrics = BackendMetrics()
        return result
