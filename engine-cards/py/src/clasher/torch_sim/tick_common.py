"""Shared exact tensor work for battle clocks, players, and outcomes."""

from __future__ import annotations

import torch

from clasher.balance import DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS

from .state import WINNER_DRAW, TensorBattleState


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


def tick_players(state: TensorBattleState, active: torch.Tensor) -> None:
    """Run exact player regeneration and delayed hand refill work."""

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
    regenerate = active[:, None] & (state.elixir < state.max_elixir)
    state.elixir.copy_(torch.where(regenerate, next_elixir, state.elixir))

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


def check_win_conditions(state: TensorBattleState, active: torch.Tensor) -> None:
    """Resolve exact Crown, overtime, sudden-death, and tiebreak outcomes."""

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
        still_active & (state.time >= state.overtime_start_time) & ~state.sudden_death
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

    tiebreak = sudden_active & ~sudden_win & (state.time >= state.tiebreaker_time)
    alive_hp = torch.where(
        state.tower_hp > 0,
        state.tower_hp,
        torch.full_like(state.tower_hp, torch.inf),
    )
    lowest = torch.round(alive_hp.min(dim=2).values * 1000.0).to(torch.int64)
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
