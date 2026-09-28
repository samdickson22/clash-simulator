from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.recurrent_state_contract import (
    ACTION_TIME_RECURRENT_STATE_CONTRACT,
    snapshot_action_time_recurrent_state,
    validate_action_time_recurrent_arrays,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.value_guided_search import RecurrentValueGuidedSearch


def test_action_time_recurrent_snapshot_is_exact_and_detached() -> None:
    cell = torch.arange(64, dtype=torch.float32).reshape(1, 64)
    hidden = cell.clone()
    hidden[:, -1] = -7.0

    snapshot = snapshot_action_time_recurrent_state(
        (hidden, cell),
        expected_memory_size=64,
    )
    hidden.zero_()
    cell.zero_()

    np.testing.assert_array_equal(snapshot.cell, np.arange(64, dtype=np.float32))
    np.testing.assert_array_equal(
        snapshot.previous_play_hazard,
        np.asarray([-7.0], dtype=np.float32),
    )
    assert snapshot.cell.flags.writeable is False
    assert snapshot.previous_play_hazard.flags.writeable is False
    assert snapshot.contract == ACTION_TIME_RECURRENT_STATE_CONTRACT


@pytest.mark.parametrize(
    ("state", "error"),
    [
        ((torch.zeros(2, 64), torch.zeros(2, 64)), ValueError),
        ((torch.zeros(1, 32), torch.zeros(1, 32)), ValueError),
        (
            (torch.zeros(1, 64, dtype=torch.float64), torch.zeros(1, 64)),
            TypeError,
        ),
        (
            (torch.full((1, 64), float("nan")), torch.zeros(1, 64)),
            FloatingPointError,
        ),
        ((torch.ones(1, 64), torch.zeros(1, 64)), ValueError),
    ],
)
def test_action_time_recurrent_snapshot_fails_closed(
    state: tuple[torch.Tensor, torch.Tensor],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        snapshot_action_time_recurrent_state(state, expected_memory_size=64)


def test_champion_action_time_cell_matches_policy_repair_memory() -> None:
    device = torch.device("cpu")
    loaded = load_policy_checkpoint(
        Path(
            "checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/"
            "candidate.pt"
        ),
        device=device,
        decks_path=Path("decks.json"),
    )
    env = SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path=Path("decks.json"),
        sampling_decks_path=Path("training_decks/katacr_hog26_only.json"),
        seed=1169001,
        canonical_perspective=True,
        canonical_lane_globals=loaded.model.config.canonical_lane_globals,
        engine_fast_path="on",
    )
    env._structured_obs_builder = loaded.builder
    env.reset(seed=1169001)
    search = RecurrentValueGuidedSearch(
        policy=loaded,
        outcome=None,
        device=device,
        terminal_rollout=True,
    )
    states = {
        player: loaded.model.initial_state(1, device=device) for player in (0, 1)
    }
    no_op = env.action_space.no_op_action

    _actions, next_states, outputs, _masks = search.observe_policy_pair(
        env,
        states=states,
        previous_actions={0: no_op, 1: no_op},
        previous_rewards={0: 0.0, 1: 0.0},
        episode_start=True,
    )
    snapshot = snapshot_action_time_recurrent_state(
        next_states[0],
        expected_memory_size=loaded.model.config.memory_size,
    )
    repair = outputs[0].repair_features

    assert repair is not None
    np.testing.assert_array_equal(
        snapshot.cell,
        repair[0, 0, -loaded.model.config.memory_size :].detach().numpy(),
    )
    assert np.any(snapshot.cell != 0.0)
    np.testing.assert_array_equal(
        snapshot.previous_play_hazard,
        next_states[0][0][0, -1:].detach().numpy(),
    )


def test_serialized_action_time_recurrence_validates_compact_semantics() -> None:
    cell = np.zeros((3, 64), dtype=np.float32)
    cell[:, 0] = [0.0, 0.5, 2.0]
    cell[:, 1] = [0.0, 0.5, 1.0]
    cell[:, 2:] = 0.25
    hazard = np.asarray([[0.0], [0.2], [1.0]], dtype=np.float32)

    validate_action_time_recurrent_arrays(
        cell,
        hazard,
        expected_rows=3,
        expected_memory_size=64,
    )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        (0, 2.1, "clock"),
        (1, -0.1, "elixir"),
        (2, 1.1, "leaky"),
    ],
)
def test_serialized_action_time_recurrence_rejects_invalid_channels(
    column: int,
    value: float,
    message: str,
) -> None:
    cell = np.zeros((1, 64), dtype=np.float32)
    cell[0, column] = value

    with pytest.raises(ValueError, match=message):
        validate_action_time_recurrent_arrays(
            cell,
            np.zeros((1, 1), dtype=np.float32),
            expected_rows=1,
            expected_memory_size=64,
        )
