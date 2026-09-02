from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.direct_simple_behavior import (
    CompleteEpisodeBuilder,
    DirectSimpleBehaviorCorpus,
    load_direct_simple_behavior_corpus,
    recurrent_behavior_windows,
    validate_direct_simple_behavior_corpus,
)


def _rollout(
    *,
    actions: list[list[int]],
    previous_actions: list[list[int]],
    rewards: list[list[float]],
    previous_rewards: list[list[float]],
    starts: list[list[bool]],
    dones: list[list[bool]],
) -> dict[str, np.ndarray]:
    action_array = np.asarray(actions, dtype=np.int64)
    streams, steps = action_array.shape
    action_masks = np.zeros((streams, steps, 12), dtype=np.bool_)
    for stream in range(streams):
        for step in range(steps):
            action_masks[stream, step, action_array[stream, step]] = True
    entity_mask = np.ones((streams, steps, 2), dtype=np.bool_)
    return {
        "entity_ids": np.ones((streams, steps, 2), dtype=np.int64),
        "entity_features": np.zeros((streams, steps, 2, 3), dtype=np.float32),
        "entity_mask": entity_mask,
        "hand_ids": np.ones((streams, steps, 5), dtype=np.int64),
        "global_features": np.zeros((streams, steps, 18), dtype=np.float32),
        "entity_id_confidence": entity_mask.astype(np.float32),
        "entity_feature_confidence": np.ones((streams, steps, 2, 3), dtype=np.float32),
        "hand_id_confidence": np.ones((streams, steps, 5), dtype=np.float32),
        "global_feature_confidence": np.ones((streams, steps, 18), dtype=np.float32),
        "action_masks": action_masks,
        "previous_actions": np.asarray(previous_actions, dtype=np.int64),
        "previous_rewards": np.asarray(previous_rewards, dtype=np.float32),
        "episode_starts": np.asarray(starts, dtype=np.bool_),
        "actions": action_array,
        "old_log_probs": np.zeros((streams, steps), dtype=np.float32),
        "rewards": np.asarray(rewards, dtype=np.float32),
        "dones": np.asarray(dones, dtype=np.bool_),
    }


def _complete_corpus() -> DirectSimpleBehaviorCorpus:
    builder = CompleteEpisodeBuilder(
        stream_count=2,
        episodes_per_stream=2,
        reset_hidden=np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        reset_cell=np.asarray([[5.0, 6.0], [7.0, 8.0]], dtype=np.float32),
    )
    builder.add_rollout(
        _rollout(
            actions=[[0, 1, 2], [6, 7, 8]],
            previous_actions=[[11, 0, 11], [11, 6, 7]],
            rewards=[[0.1, 0.2, 0.3], [0.6, 0.7, 0.8]],
            previous_rewards=[[0.0, 0.1, 0.0], [0.0, 0.6, 0.7]],
            starts=[[True, False, True], [True, False, False]],
            dones=[[False, True, False], [False, False, True]],
        )
    )
    assert builder.completed_by_stream.tolist() == [1, 1]
    builder.add_rollout(
        _rollout(
            actions=[[3, 4, 5], [9, 10, 11]],
            previous_actions=[[2, 3, 11], [11, 9, 10]],
            rewards=[[0.4, 0.5, 0.0], [0.9, 1.0, 1.1]],
            previous_rewards=[[0.3, 0.4, 0.0], [0.0, 0.9, 1.0]],
            starts=[[False, False, True], [True, False, False]],
            dones=[[False, True, False], [False, False, True]],
        )
    )
    assert builder.complete
    return builder.finalize()


def test_builder_publishes_only_complete_episodes_in_stable_stream_order() -> None:
    corpus = _complete_corpus()
    assert corpus.episode_offsets.tolist() == [0, 2, 5, 8, 11]
    assert corpus.episode_stream_rows.tolist() == [0, 0, 1, 1]
    assert corpus.episode_ordinals.tolist() == [0, 1, 0, 1]
    assert corpus.arrays["actions"].tolist() == [
        0,
        1,
        2,
        3,
        4,
        6,
        7,
        8,
        9,
        10,
        11,
    ]
    assert corpus.initial_hidden.tolist() == [
        [1.0, 2.0],
        [1.0, 2.0],
        [3.0, 4.0],
        [3.0, 4.0],
    ]
    assert corpus.initial_cell.tolist() == [
        [5.0, 6.0],
        [5.0, 6.0],
        [7.0, 8.0],
        [7.0, 8.0],
    ]


def test_builder_preserves_opt_in_teacher_factors() -> None:
    builder = CompleteEpisodeBuilder(
        stream_count=1,
        episodes_per_stream=1,
        reset_hidden=np.zeros((1, 2), dtype=np.float32),
        reset_cell=np.zeros((1, 2), dtype=np.float32),
        extra_transition_keys=("play_hazard_probabilities",),
    )
    rollout = _rollout(
        actions=[[0, 1]],
        previous_actions=[[11, 0]],
        rewards=[[0.1, 0.2]],
        previous_rewards=[[0.0, 0.1]],
        starts=[[True, False]],
        dones=[[False, True]],
    )
    rollout["play_hazard_probabilities"] = np.asarray([[0.125, 0.75]], dtype=np.float32)
    builder.add_rollout(rollout)
    corpus = builder.finalize()
    np.testing.assert_array_equal(
        corpus.arrays["play_hazard_probabilities"],
        np.asarray([0.125, 0.75], dtype=np.float32),
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("previous_action", "previous-action chronology"),
        ("previous_reward", "previous-reward chronology"),
        ("illegal_action", "not legal"),
        ("early_done", "first terminal"),
    ),
)
def test_validator_rejects_corrupted_episode_contract(
    mutation: str, message: str
) -> None:
    source = _complete_corpus()
    arrays = deepcopy(source.arrays)
    if mutation == "previous_action":
        arrays["previous_actions"][1] = 9
    elif mutation == "previous_reward":
        arrays["previous_rewards"][1] = 9.0
    elif mutation == "illegal_action":
        arrays["action_masks"][0, arrays["actions"][0]] = False
    else:
        arrays["dones"][0] = True
    corrupted = DirectSimpleBehaviorCorpus(
        arrays=arrays,
        episode_offsets=source.episode_offsets,
        episode_stream_rows=source.episode_stream_rows,
        episode_ordinals=source.episode_ordinals,
        initial_hidden=source.initial_hidden,
        initial_cell=source.initial_cell,
    )
    with pytest.raises(ValueError, match=message):
        validate_direct_simple_behavior_corpus(corrupted)


def test_builder_rejects_reset_before_terminal() -> None:
    builder = CompleteEpisodeBuilder(
        stream_count=1,
        episodes_per_stream=1,
        reset_hidden=np.zeros((1, 2), dtype=np.float32),
        reset_cell=np.zeros((1, 2), dtype=np.float32),
    )
    broken = _rollout(
        actions=[[0, 1, 2]],
        previous_actions=[[11, 0, 11]],
        rewards=[[0.1, 0.2, 0.3]],
        previous_rewards=[[0.0, 0.1, 0.0]],
        starts=[[True, False, True]],
        dones=[[False, False, True]],
    )
    with pytest.raises(ValueError, match="before the prior one terminated"):
        builder.add_rollout(broken)


def test_loader_round_trips_and_requires_complete_episode_metadata(
    tmp_path: Path,
) -> None:
    corpus = _complete_corpus()
    path = tmp_path / "corpus.npz"

    def write(complete: bool) -> None:
        np.savez_compressed(
            path,
            **corpus.arrays,
            episode_offsets=corpus.episode_offsets,
            episode_stream_rows=corpus.episode_stream_rows,
            episode_ordinals=corpus.episode_ordinals,
            episode_opponent_indices=np.zeros(corpus.episode_count, dtype=np.int64),
            episode_learner_players=np.zeros(corpus.episode_count, dtype=np.int64),
            initial_hidden=corpus.initial_hidden,
            initial_cell=corpus.initial_cell,
            metadata_json=np.asarray(
                json.dumps(
                    {
                        "complete_episodes_only": complete,
                        "episode_count": corpus.episode_count,
                        "row_count": corpus.row_count,
                    }
                )
            ),
        )

    write(True)
    metadata, loaded = load_direct_simple_behavior_corpus(path)
    assert metadata["complete_episodes_only"] is True
    assert loaded.episode_offsets.tolist() == corpus.episode_offsets.tolist()
    assert loaded.arrays["actions"].tolist() == corpus.arrays["actions"].tolist()
    assert "episode_opponent_indices" not in loaded.arrays
    assert "episode_learner_players" not in loaded.arrays

    write(False)
    with pytest.raises(ValueError, match="complete episodes"):
        load_direct_simple_behavior_corpus(path)


def test_recurrent_windows_cover_targets_once_with_causal_burn_in() -> None:
    offsets = np.asarray([0, 5, 14], dtype=np.int64)
    windows = recurrent_behavior_windows(
        offsets,
        train_steps=4,
        burn_in_steps=3,
    )
    assert [
        (row.episode, row.context_start, row.train_start, row.end) for row in windows
    ] == [
        (0, 0, 0, 4),
        (0, 1, 4, 5),
        (1, 5, 5, 9),
        (1, 6, 9, 13),
        (1, 10, 13, 14),
    ]
    covered = [
        index for window in windows for index in range(window.train_start, window.end)
    ]
    assert covered == list(range(14))
    assert all(
        window.context_start <= window.train_start < window.end for window in windows
    )
    assert all(window.burn_in_rows <= 3 for window in windows)
    assert all(window.train_rows <= 4 for window in windows)
