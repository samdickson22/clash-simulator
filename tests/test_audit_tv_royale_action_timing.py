from __future__ import annotations

import numpy as np

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from scripts.audit_tv_royale_action_timing import (
    build_duration_weights,
    weighted_checkpoint_metrics,
)


def test_duration_weights_restore_dense_replay_action_rate() -> None:
    noop = NUM_HAND_SLOTS * NUM_TILES
    timing = build_duration_weights(
        expert_actions=np.asarray([0, noop, noop, 1, 2], dtype=np.int64),
        episode_ids=np.asarray([0, 0, 0, 1, 1], dtype=np.int64),
        source_replays=np.asarray(["a", "a", "a", "b", "b"]),
        replay_frame_counts={"a": 100, "b": 50},
        source_frame_hz=10.0,
        policy_decision_hz=4.0,
    )

    # Replay a has 40 dense decisions: one play and 39 no-ops represented by
    # two retained no-op rows. Replay b has no retained no-op and is correctly
    # excluded from policy calibration rather than pretending its no-ops exist.
    np.testing.assert_allclose(timing.weights, [1.0, 19.5, 19.5, 0.0, 0.0])
    assert timing.evaluable.tolist() == [True, True, True, False, False]
    assert timing.summary["estimated_decision_opportunities"] == 60
    assert timing.summary["duration_estimated_human_play_rate"] == 3 / 60
    assert timing.summary["evaluable_duration_estimated_human_play_rate"] == 1 / 40
    assert timing.summary["episodes_without_retained_noop"] == 1


def test_weighted_metrics_do_not_treat_case_controlled_rows_as_natural_rate() -> None:
    noop = NUM_HAND_SLOTS * NUM_TILES
    timing = build_duration_weights(
        expert_actions=np.asarray([0, noop, noop], dtype=np.int64),
        episode_ids=np.zeros((3,), dtype=np.int64),
        source_replays=np.asarray(["a", "a", "a"]),
        replay_frame_counts={"a": 100},
        source_frame_hz=10.0,
        policy_decision_hz=4.0,
    )
    metrics = weighted_checkpoint_metrics(
        chosen_actions=np.asarray([0, 0, noop], dtype=np.int64),
        play_probabilities=np.asarray([0.8, 0.8, 0.2]),
        expert_actions=np.asarray([0, noop, noop], dtype=np.int64),
        timing=timing,
    )

    assert metrics["weighted_target_play_rate"] == 1 / 40
    assert metrics["weighted_predicted_play_rate"] == 20.5 / 40
    assert metrics["weighted_play_recall"] == 1.0
    assert metrics["weighted_noop_recall"] == 0.5
