from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.simple_outcomes import (
    FAST_TOWER_SLOT_COUNT,
    FAST_WINNER_DRAW,
    FastMatchRules,
    FastOutcomeTracker,
    FastTowerSpec,
    crown_tower_hp,
    initialize_crown_towers_,
)
from clasher.torch_sim.simple_state import (
    FAST_KIND_BUILDING,
    FAST_WINNER_IN_PROGRESS,
    FastGymState,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _tower_spec(device: torch.device) -> FastTowerSpec:
    return FastTowerSpec(
        card_id=torch.tensor([[91, 91, 92], [91, 91, 92]], device=device),
        x_units=torch.tensor(
            [[3500, 14500, 9000], [3500, 14500, 9000]], device=device
        ),
        y_units=torch.tensor(
            [[6500, 6500, 2500], [25500, 25500, 29500]], device=device
        ),
        hitpoints=torch.tensor(
            [[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]], device=device
        ),
        damage=torch.tensor(
            [[10.0, 10.0, 15.0], [10.0, 10.0, 15.0]], device=device
        ),
        range_units=torch.full((2, 3), 7500, device=device),
        sight_range_units=torch.full((2, 3), 9500, device=device),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_six_reserved_towers_initialize_from_tensors(device_name: str) -> None:
    device = _device(device_name)
    state = FastGymState.empty(2, max_entities=10, device=device)
    initialize_crown_towers_(state, _tower_spec(state.device))

    assert state.active[:, :FAST_TOWER_SLOT_COUNT].all()
    assert not state.active[:, FAST_TOWER_SLOT_COUNT:].any()
    assert state.kind[:, :FAST_TOWER_SLOT_COUNT].eq(FAST_KIND_BUILDING).all()
    assert state.owner[0, :FAST_TOWER_SLOT_COUNT].tolist() == [0, 0, 0, 1, 1, 1]
    assert state.stable_id[0, :FAST_TOWER_SLOT_COUNT].tolist() == [1, 2, 3, 4, 5, 6]
    assert state.card_id[0, :FAST_TOWER_SLOT_COUNT].tolist() == [91, 91, 92] * 2
    assert state.next_stable_id.tolist() == [7, 7]
    assert crown_tower_hp(state).tolist() == [
        [[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]],
        [[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]],
    ]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_integer_match_boundaries_cover_regulation_overtime_and_tiebreak(
    device_name: str,
) -> None:
    device = _device(device_name)
    state = FastGymState.empty(5, max_entities=8, device=device)
    initialize_crown_towers_(state, _tower_spec(state.device))
    tracker = FastOutcomeTracker(
        state, FastMatchRules(regulation_ticks=10, tiebreak_ticks=20)
    )

    # Immediate King resolution: single death and simultaneous draw.
    state.hp[0, 5] = 0
    state.hp[1, 2] = 0
    state.hp[1, 5] = 0
    # Regulation crown lead for player 0.
    state.hp[2, 3] = 0
    state.tick[2] = 10
    # Row 3 enters overtime tied. Row 4 resolves by lowest standing HP.
    state.tick[3:] = torch.tensor([10, 20], device=state.device)
    state.hp[4, 0] = 80
    state.hp[4, 3] = 70

    result = tracker.evaluate()
    assert result.done.tolist() == [True, True, True, False, True]
    assert result.winner.tolist() == [0, FAST_WINNER_DRAW, 0, -2, 0]
    assert result.overtime.tolist() == [False, False, False, True, True]
    assert result.crowns.tolist() == [[3, 0], [3, 3], [1, 0], [0, 0], [0, 0]]

    # The first crown advantage after the tied boundary wins sudden death.
    state.tick[3] = 11
    state.hp[3, 4] = 0
    sudden = tracker.evaluate()
    assert bool(sudden.done[3])
    assert int(sudden.winner[3]) == 0

    # Exact lowest-standing-tower equality is a real tiebreak draw.
    tied = FastGymState.empty(1, max_entities=6, device=device)
    initialize_crown_towers_(tied, _tower_spec(tied.device))
    tied.tick[0] = 20
    tied_result = FastOutcomeTracker(
        tied, FastMatchRules(regulation_ticks=10, tiebreak_ticks=20)
    ).evaluate()
    assert tied_result.done.tolist() == [True]
    assert tied_result.winner.tolist() == [FAST_WINNER_DRAW]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_tower_crown_and_terminal_rewards_are_incremental_and_zero_sum(
    device_name: str,
) -> None:
    device = _device(device_name)
    state = FastGymState.empty(3, max_entities=6, device=device)
    initialize_crown_towers_(state, _tower_spec(state.device))
    rules = FastMatchRules(
        regulation_ticks=10,
        tiebreak_ticks=20,
        tower_damage_weight=0.25,
        crown_weight=0.50,
        terminal_weight=1.00,
    )
    tracker = FastOutcomeTracker(state, rules)

    # Chip, one Princess Tower, and a terminal King Tower respectively.
    state.hp[0, 3] = 60
    state.hp[1, 3] = 0
    state.hp[2, 5] = 0
    result = tracker.evaluate()
    expected_p0 = torch.tensor(
        [0.025, 0.0625 + (0.5 / 3.0), 0.125 + 0.5 + 1.0],
        device=device,
    )
    torch.testing.assert_close(result.reward[:, 0], expected_p0)
    torch.testing.assert_close(result.reward[:, 1], -expected_p0)
    assert torch.equal(result.reward.sum(dim=1), torch.zeros(3, device=device))

    # Rewards are transition deltas, and finished rows cannot emit again.
    repeated = tracker.evaluate()
    torch.testing.assert_close(repeated.reward, torch.zeros_like(repeated.reward))
    assert repeated.winner[2] == 0


def test_outcome_hot_path_has_no_host_sync_or_card_name_dispatch() -> None:
    source = inspect.getsource(FastOutcomeTracker.evaluate)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero(", "card_name"):
        assert forbidden not in source


def test_tower_inputs_fail_closed_on_shape_capacity_and_clock_rules() -> None:
    state = FastGymState.empty(1, max_entities=5)
    with pytest.raises(ValueError, match="six Crown Tower"):
        initialize_crown_towers_(state, _tower_spec(state.device))
    with pytest.raises(ValueError, match="regulation_ticks"):
        FastMatchRules(regulation_ticks=0, tiebreak_ticks=20)
    with pytest.raises(ValueError, match="greater than"):
        FastMatchRules(regulation_ticks=10, tiebreak_ticks=10)

    state = FastGymState.empty(1, max_entities=6)
    spec = _tower_spec(state.device)
    bad = FastTowerSpec(
        card_id=spec.card_id[:, :2],
        x_units=spec.x_units,
        y_units=spec.y_units,
        hitpoints=spec.hitpoints,
        damage=spec.damage,
        range_units=spec.range_units,
        sight_range_units=spec.sight_range_units,
        hit_cooldown_ticks=spec.hit_cooldown_ticks,
    )
    with pytest.raises(ValueError, match="card_id must have shape"):
        initialize_crown_towers_(state, bad)
