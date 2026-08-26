"""Crown towers, match outcomes, and rewards for the practical tensor Gym.

The first six entity slots are reserved, owner-major, for left, right, and
King Crown Towers.  All mechanics use numeric tensors supplied by the caller;
this module neither resolves card names nor depends on Python battle objects.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .simple_state import (
    FAST_KIND_BUILDING,
    FAST_WINNER_IN_PROGRESS,
    FastGymState,
)

FAST_TOWER_SLOTS_PER_PLAYER = 3
FAST_TOWER_SLOT_COUNT = 6
FAST_TOWER_LEFT = 0
FAST_TOWER_RIGHT = 1
FAST_TOWER_KING = 2
FAST_WINNER_DRAW = -1


@dataclass(frozen=True)
class FastTowerSpec:
    """Serialized Crown Tower values with shape ``[2, 3]``.

    The second dimension is always left, right, King.  Values may come from a
    serialized mechanics catalog or from an explicitly versioned default
    balance snapshot.  Keeping them as inputs makes balance changes data, not
    card-specific branches in the Gym.
    """

    card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    hitpoints: torch.Tensor
    damage: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    hit_cooldown_ticks: torch.Tensor


@dataclass(frozen=True)
class FastMatchRules:
    """Integer clock thresholds and deliberately small reward coefficients."""

    regulation_ticks: int
    tiebreak_ticks: int
    tower_damage_weight: float = 0.25
    crown_weight: float = 0.50
    terminal_weight: float = 1.00

    def __post_init__(self) -> None:
        if self.regulation_ticks < 1:
            raise ValueError("regulation_ticks must be positive")
        if self.tiebreak_ticks <= self.regulation_ticks:
            raise ValueError("tiebreak_ticks must be greater than regulation_ticks")
        if min(
            self.tower_damage_weight,
            self.crown_weight,
            self.terminal_weight,
        ) < 0.0:
            raise ValueError("reward weights must be non-negative")


@dataclass(frozen=True)
class FastOutcomeResult:
    """Policy-facing outcome values for one batched native tick."""

    tower_hp: torch.Tensor
    crowns: torch.Tensor
    overtime: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor
    reward: torch.Tensor


def _validate_tower_spec(state: FastGymState, spec: FastTowerSpec) -> None:
    expected = (2, FAST_TOWER_SLOTS_PER_PLAYER)
    for name in (
        "card_id",
        "x_units",
        "y_units",
        "hitpoints",
        "damage",
        "range_units",
        "sight_range_units",
        "hit_cooldown_ticks",
    ):
        value = getattr(spec, name)
        if tuple(value.shape) != expected:
            raise ValueError(f"{name} must have shape {expected}")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
    if spec.card_id.dtype != torch.int64:
        raise ValueError("card_id must be int64")


def initialize_crown_towers_(state: FastGymState, spec: FastTowerSpec) -> None:
    """Initialize the six reserved slots from tensorized tower mechanics.

    This is setup work, not part of the tick hot path.  It intentionally
    overwrites the reserved slots and advances ``next_stable_id`` beyond them.
    Ordinary deployment must treat these slots as permanently reserved even
    after a tower dies.
    """

    if state.max_entities < FAST_TOWER_SLOT_COUNT:
        raise ValueError("max_entities must reserve six Crown Tower slots")
    _validate_tower_spec(state, spec)
    tower_slice = slice(0, FAST_TOWER_SLOT_COUNT)
    batch = state.batch_size

    def rows(value: torch.Tensor) -> torch.Tensor:
        return value.reshape(1, FAST_TOWER_SLOT_COUNT).expand(batch, -1)

    owners = torch.tensor(
        [0, 0, 0, 1, 1, 1], dtype=torch.int8, device=state.device
    ).view(1, FAST_TOWER_SLOT_COUNT)
    stable_ids = torch.arange(
        1, FAST_TOWER_SLOT_COUNT + 1, dtype=torch.int64, device=state.device
    ).view(1, FAST_TOWER_SLOT_COUNT)
    state.active[:, tower_slice] = True
    state.stable_id[:, tower_slice] = stable_ids
    state.kind[:, tower_slice] = FAST_KIND_BUILDING
    state.owner[:, tower_slice] = owners
    state.card_id[:, tower_slice] = rows(spec.card_id).to(torch.int64)
    state.x_units[:, tower_slice] = rows(spec.x_units).to(torch.int32)
    state.y_units[:, tower_slice] = rows(spec.y_units).to(torch.int32)
    hp = rows(spec.hitpoints).to(torch.float32)
    state.hp[:, tower_slice] = hp
    state.max_hp[:, tower_slice] = hp
    state.target_id[:, tower_slice] = 0
    state.damage[:, tower_slice] = rows(spec.damage).to(torch.float32)
    state.range_units[:, tower_slice] = rows(spec.range_units).to(torch.int32)
    state.sight_range_units[:, tower_slice] = rows(spec.sight_range_units).to(
        torch.int32
    )
    state.speed_units_per_tick[:, tower_slice] = 0
    state.hit_cooldown_ticks[:, tower_slice] = rows(
        spec.hit_cooldown_ticks
    ).to(torch.int32)
    state.deploy_ticks[:, tower_slice] = 0
    state.cooldown_ticks[:, tower_slice] = 0
    state.next_stable_id.copy_(
        torch.maximum(
            state.next_stable_id,
            torch.full_like(state.next_stable_id, FAST_TOWER_SLOT_COUNT + 1),
        )
    )


def crown_tower_hp(state: FastGymState) -> torch.Tensor:
    """Return the live ``[batch, owner, left/right/King]`` tower HP view."""

    if state.max_entities < FAST_TOWER_SLOT_COUNT:
        raise ValueError("state does not contain the six reserved tower slots")
    return state.hp[:, :FAST_TOWER_SLOT_COUNT].view(
        state.batch_size, 2, FAST_TOWER_SLOTS_PER_PLAYER
    )


def crowns_for_players(tower_hp: torch.Tensor) -> torch.Tensor:
    """Return crowns earned by each player from the opponent's tower losses."""

    if tower_hp.ndim != 3 or tuple(tower_hp.shape[1:]) != (2, 3):
        raise ValueError("tower_hp must have shape [batch, 2, 3]")
    king_dead = tower_hp[:, :, FAST_TOWER_KING] <= 0
    side_lost = (tower_hp[:, :, :FAST_TOWER_KING] <= 0).sum(dim=2).to(torch.int8)
    towers_lost = torch.where(king_dead, torch.full_like(side_lost, 3), side_lost)
    return towers_lost[:, [1, 0]]


class FastOutcomeTracker:
    """Resolve match rules and emit incremental antisymmetric rewards."""

    def __init__(self, state: FastGymState, rules: FastMatchRules) -> None:
        self.state = state
        self.rules = rules
        initial_hp = crown_tower_hp(state)
        self.initial_tower_hp = initial_hp.clone()
        self.previous_tower_hp = initial_hp.clone()
        self.previous_crowns = crowns_for_players(initial_hp)
        self.overtime = torch.zeros(
            state.batch_size, dtype=torch.bool, device=state.device
        )

    def evaluate(self) -> FastOutcomeResult:
        """Resolve outcomes at the current integer tick and advance reward state."""

        state = self.state
        hp = crown_tower_hp(state)
        crowns = crowns_for_players(hp)
        was_active = ~state.game_over

        king_alive = hp[:, :, FAST_TOWER_KING] > 0
        any_king_dead = ~king_alive.all(dim=1)
        both_kings_dead = ~king_alive.any(dim=1)
        king_winner = torch.where(
            both_kings_dead,
            torch.full_like(state.winner, FAST_WINNER_DRAW),
            torch.where(
                king_alive[:, 0],
                torch.zeros_like(state.winner),
                torch.ones_like(state.winner),
            ),
        )
        finish_by_king = was_active & any_king_dead
        state.game_over |= finish_by_king
        state.winner.copy_(torch.where(finish_by_king, king_winner, state.winner))

        still_active = was_active & ~finish_by_king
        crown_unequal = crowns[:, 0] != crowns[:, 1]
        at_regulation = (
            still_active
            & ~self.overtime
            & (state.tick >= self.rules.regulation_ticks)
        )
        crown_winner = torch.where(
            crowns[:, 0] > crowns[:, 1],
            torch.zeros_like(state.winner),
            torch.ones_like(state.winner),
        )
        regulation_win = at_regulation & crown_unequal
        state.game_over |= regulation_win
        state.winner.copy_(torch.where(regulation_win, crown_winner, state.winner))
        self.overtime |= at_regulation & ~crown_unequal

        sudden_active = still_active & ~regulation_win & self.overtime
        sudden_win = sudden_active & crown_unequal
        state.game_over |= sudden_win
        state.winner.copy_(torch.where(sudden_win, crown_winner, state.winner))

        tiebreak = (
            sudden_active
            & ~sudden_win
            & (state.tick >= self.rules.tiebreak_ticks)
        )
        standing_hp = torch.where(
            hp > 0, hp, torch.full_like(hp, torch.inf)
        )
        lowest = torch.round(standing_hp.amin(dim=2) * 1000.0).to(torch.int64)
        tiebreak_winner = torch.where(
            lowest[:, 0] > lowest[:, 1],
            torch.zeros_like(state.winner),
            torch.where(
                lowest[:, 1] > lowest[:, 0],
                torch.ones_like(state.winner),
                torch.full_like(state.winner, FAST_WINNER_DRAW),
            ),
        )
        state.game_over |= tiebreak
        state.winner.copy_(torch.where(tiebreak, tiebreak_winner, state.winner))

        hp_lost = (self.previous_tower_hp - hp).clamp_min(0.0)
        damage_edge_p0 = hp_lost[:, 1].sum(dim=1) - hp_lost[:, 0].sum(dim=1)
        common_hp_scale = self.initial_tower_hp.sum(dim=(1, 2)).clamp_min(1.0) * 0.5
        damage_reward = (
            self.rules.tower_damage_weight * damage_edge_p0 / common_hp_scale
        )
        crown_delta = crowns - self.previous_crowns
        crown_reward = self.rules.crown_weight * (
            crown_delta[:, 0].to(torch.float32)
            - crown_delta[:, 1].to(torch.float32)
        ) / 3.0
        newly_done = was_active & state.game_over
        terminal_sign = torch.where(
            state.winner == 0,
            torch.ones_like(hp[:, 0, 0]),
            torch.where(
                state.winner == 1,
                -torch.ones_like(hp[:, 0, 0]),
                torch.zeros_like(hp[:, 0, 0]),
            ),
        )
        terminal_reward = (
            self.rules.terminal_weight * terminal_sign * newly_done.to(torch.float32)
        )
        reward_p0 = torch.where(
            was_active, damage_reward + crown_reward + terminal_reward, 0.0
        )
        reward = torch.stack((reward_p0, -reward_p0), dim=1)

        self.previous_tower_hp.copy_(hp)
        self.previous_crowns.copy_(crowns)
        return FastOutcomeResult(
            tower_hp=hp.clone(),
            crowns=crowns,
            overtime=self.overtime.clone(),
            done=state.game_over.clone(),
            winner=state.winner.clone(),
            reward=reward,
        )
