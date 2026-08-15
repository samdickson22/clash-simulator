"""Mode selection, tensor tick kernels, and fail-closed fallback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import torch

from clasher.balance import DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS
from clasher.battle import BattleState
from clasher.kinematics import LOGIC_TICK_MILLISECONDS, LOGIC_TICK_SECONDS

from .diagnostics import TorchParityError, battle_snapshot, first_divergence
from .state import WINNER_DRAW, TensorBattleState


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


def _idle_tensor_supported(battle: BattleState) -> bool:
    """The first complete-tick vertical slice: inert static Crown Towers."""

    return bool(battle.can_fast_forward_idle())


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
    delta = (1.0 / base_regen) * LOGIC_TICK_SECONDS
    next_elixir = torch.minimum(state.max_elixir, state.elixir + delta[:, None])
    state.elixir.copy_(torch.where(active[:, None], next_elixir, state.elixir))

    reduced = torch.clamp(
        state.refill_cooldown_ms - LOGIC_TICK_MILLISECONDS,
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
    regulation_boundary = still_active & (state.time >= 180.0) & ~state.sudden_death
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

    tiebreak = sudden_active & ~sudden_win & (state.time >= 300.0)
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


def step_idle_tensor_ticks(state: TensorBattleState, ticks: int) -> int:
    """Advance a batch of idle complete ticks without Python object stepping."""

    requested = max(0, int(ticks))
    advanced = 0
    for _ in range(requested):
        active = state.active & ~state.game_over
        if not bool(active.any().item()):
            break
        state.time.add_(torch.where(active, torch.full_like(state.time, 0.05), 0.0))
        state.tick.add_(active.to(torch.int64))
        state.double_elixir |= active & (state.time >= 120.0)
        state.overtime |= active & (state.time >= 180.0)
        state.triple_elixir |= active & (state.time >= 240.0)
        _tick_players(state, active)
        active_towers = (
            active[:, None]
            & state.entity_active
            & (state.entity_tower_slot >= 0)
            & state.entity_tower_active
        )
        state.entity_last_attack_time.add_(
            active_towers.to(torch.float64) * LOGIC_TICK_SECONDS
        )
        timer_boundary = (~state.sudden_death & (state.time >= 180.0)) | (
            state.sudden_death & (state.time >= 300.0)
        )
        if bool((active & timer_boundary).any().item()):
            _check_win_conditions(state, active)
        advanced += 1
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
        self._battle_identity: int | None = None

    def _state_for(self, battle: BattleState) -> TensorBattleState:
        if (
            self._state is None
            or self._battle_identity != id(battle)
            or not self._state.clocks_match(battle)
        ):
            self._state = TensorBattleState.from_battles([battle], device=self.device)
            self._battle_identity = id(battle)
        return self._state

    def _fallback(self, battle: BattleState, ticks: int) -> int:
        advanced = battle.step_logic_ticks(ticks)
        self.metrics.python_ticks += advanced
        self.metrics.unsupported_fallbacks += 1
        self._state = None
        self._battle_identity = None
        return advanced

    def step_logic_ticks(self, battle: BattleState, ticks: int) -> int:
        requested = max(0, int(ticks))
        if self.backend is SimulatorBackend.PYTHON:
            advanced = battle.step_logic_ticks(requested)
            self.metrics.python_ticks += advanced
            return advanced
        if not _idle_tensor_supported(battle):
            return self._fallback(battle, requested)

        if self.backend is SimulatorBackend.PYTORCH_SHADOW:
            candidate = battle.clone()
            advanced = battle.step_logic_ticks(requested)
            tensor_state = TensorBattleState.from_battles(
                [candidate], device=self.device
            )
            tensor_advanced = step_idle_tensor_ticks(tensor_state, requested)
            tensor_state.sync_to_battles([candidate])
            self.metrics.python_ticks += advanced
            self.metrics.tensor_ticks += tensor_advanced
            self.metrics.shadow_checks += 1
            mismatch = first_divergence(
                battle_snapshot(battle), battle_snapshot(candidate)
            )
            if mismatch is not None:
                self.metrics.shadow_mismatches += 1
                raise TorchParityError(mismatch)
            return advanced

        state = self._state_for(battle)
        advanced = step_idle_tensor_ticks(state, requested)
        state.sync_to_battles([battle])
        self.metrics.tensor_ticks += advanced
        return advanced

    def metrics_dict(self) -> dict[str, float]:
        return self.metrics.as_dict()

    def pop_metrics(self) -> dict[str, float]:
        result = self.metrics.as_dict()
        self.metrics = BackendMetrics()
        return result
