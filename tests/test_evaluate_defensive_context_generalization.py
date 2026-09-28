from __future__ import annotations

import numpy as np

from clasher.rl.human_context import visible_enemy_pressure_mask
from scripts.evaluate_defensive_context_generalization import (
    _context_metrics,
    _pressure_context_masks,
)


def test_pressure_context_uses_enemy_combatants_not_towers_or_spells() -> None:
    features = np.zeros((3, 3, 32), dtype=np.float16)
    mask = np.ones((3, 3), dtype=np.bool_)
    # A near enemy troop is genuine pressure.
    features[0, 0, 3] = 1
    features[0, 0, 4] = 1
    features[0, 0, 1] = 0.2
    # A near enemy Crown Tower and spell are excluded.
    features[1, 0, 3] = 1
    features[1, 0, 5] = 1
    features[1, 0, 31] = 1
    features[1, 0, 1] = 0.1
    features[1, 1, 3] = 1
    features[1, 1, 7] = 1
    features[1, 1, 1] = 0.1
    # A troop in the remote half is not own-half pressure.
    features[2, 0, 3] = 1
    features[2, 0, 4] = 1
    features[2, 0, 1] = 0.75

    contexts = _pressure_context_masks(features, mask)

    np.testing.assert_array_equal(contexts["tower_zone"], [True, False, False])
    np.testing.assert_array_equal(
        contexts["own_half_pressure"], [True, False, False]
    )
    np.testing.assert_array_equal(
        contexts["remote_or_clear"], [False, True, True]
    )


def test_context_metrics_separates_play_and_wait_behavior() -> None:
    no_op = 4 * 18 * 32
    selected = np.asarray([True, True, False])
    expert = np.asarray([0, no_op, 2 * 18 * 32])
    chosen = np.asarray([1, no_op, no_op])

    result = _context_metrics(
        selected=selected,
        episode_ids=np.asarray([0, 0, 1]),
        expert_actions=expert,
        chosen_actions=chosen,
        action_type_nll=np.asarray([0.1, 0.2, 9.0]),
    )

    assert result["samples"] == 2
    assert result["episodes"] == 1
    assert result["action_type_nll"] == 0.15000000000000002
    assert result["action_type_accuracy"] == 1.0
    assert result["expert_play_rate"] == 0.5
    assert result["predicted_play_rate"] == 0.5
    assert result["play_recall"] == 1.0
    assert result["noop_recall"] == 1.0
    assert result["played_card_slot_accuracy"] == 1.0


def test_visible_pressure_threshold_is_validated() -> None:
    features = np.zeros((1, 1, 32), dtype=np.float32)
    mask = np.ones((1, 1), dtype=np.bool_)

    with np.testing.assert_raises_regex(ValueError, "between zero and one"):
        visible_enemy_pressure_mask(
            features,
            mask,
            maximum_canonical_y=1.1,
        )
