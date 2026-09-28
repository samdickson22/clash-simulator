from __future__ import annotations

import numpy as np
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from scripts.evaluate_recurrent_corpus import (
    _action_type_log_probs,
    _binary_ranking_metrics,
    _conditional_card_slot_accuracy,
    _paired_metrics,
    _temporal_play_metrics,
)


def test_flat_joint_argmax_is_not_used_as_deterministic_policy_action() -> None:
    """Document the evaluator invariant enforced by model inference tests.

    A placement type with probability 0.6 spread over many legal tiles can
    lose a flat action argmax to a 0.4 no-op. Live policy inference deliberately
    selects type first; the corpus evaluator must call that same model path.
    """
    type_probabilities = torch.tensor([[0.6, 0.0, 0.0, 0.0, 0.4, 0.0]])
    placement = torch.zeros((1, NUM_HAND_SLOTS, NUM_TILES))
    placement[:, 0, :100] = 0.6 / 100
    joint = torch.cat(
        [
            placement.reshape(1, -1),
            type_probabilities[:, NUM_HAND_SLOTS:],
        ],
        dim=-1,
    )

    assert int(joint.argmax(dim=-1).item()) == NUM_HAND_SLOTS * NUM_TILES
    assert int(type_probabilities.argmax(dim=-1).item()) == 0


def test_action_type_log_probs_preserve_exact_type_mass() -> None:
    type_probabilities = torch.tensor(
        [[0.05, 0.10, 0.15, 0.20, 0.30, 0.20]], dtype=torch.float64
    )
    placement = (
        type_probabilities[:, :NUM_HAND_SLOTS, None]
        .expand(-1, -1, NUM_TILES)
        / NUM_TILES
    ).reshape(1, -1)
    joint_probabilities = torch.cat(
        [placement, type_probabilities[:, NUM_HAND_SLOTS:]], dim=-1
    )

    actual = _action_type_log_probs(joint_probabilities.log()).exp()

    torch.testing.assert_close(actual, type_probabilities, rtol=1e-12, atol=1e-12)


def test_paired_metrics_exposes_correct_to_incorrect_changes() -> None:
    no_op = 4 * 576
    expert = np.asarray([no_op, 0, 100, 200], dtype=np.int64)
    reference = np.asarray([no_op, 1, 100, 200], dtype=np.int64)
    candidate = np.asarray([0, 0, 101, 900], dtype=np.int64)

    metrics = _paired_metrics(reference, candidate, expert)

    assert metrics["action_changes_vs_first"] == 4
    assert metrics["exact_improvements_vs_first"] == 1
    assert metrics["exact_regressions_vs_first"] == 3
    assert metrics["action_type_improvements_vs_first"] == 0
    assert metrics["action_type_regressions_vs_first"] == 2
    assert metrics["within_one_tile_improvements_vs_first"] == 0
    assert metrics["within_one_tile_regressions_vs_first"] == 1


def test_conditional_card_slot_accuracy_ignores_play_wait_threshold() -> None:
    no_op = NUM_HAND_SLOTS * NUM_TILES
    expert = np.asarray([no_op, 0, NUM_TILES, 2 * NUM_TILES], dtype=np.int64)
    conditional_slots = np.asarray([0, 0, 2, 2], dtype=np.int64)

    assert _conditional_card_slot_accuracy(conditional_slots, expert) == 2 / 3


def test_temporal_play_metrics_match_once_and_can_require_same_card() -> None:
    no_op = NUM_HAND_SLOTS * NUM_TILES
    expert = np.asarray([no_op, 0, no_op, NUM_TILES, no_op], dtype=np.int64)
    chosen = np.asarray([0, no_op, 2 * NUM_TILES, no_op, no_op], dtype=np.int64)
    arrays = {
        "episode_ids": np.zeros((5,), dtype=np.int64),
        "source_frames": np.asarray([0, 2, 4, 6, 8], dtype=np.int64),
        "source_replays": np.asarray(["a"] * 5),
        "source_actor_ids": np.zeros((5,), dtype=np.int8),
    }
    valid = np.ones((5,), dtype=np.bool_)

    any_card = _temporal_play_metrics(
        chosen,
        expert,
        arrays,
        valid,
        tolerance_frames=2,
        require_same_card=False,
    )
    same_card = _temporal_play_metrics(
        chosen,
        expert,
        arrays,
        valid,
        tolerance_frames=2,
        require_same_card=True,
    )

    assert any_card == {
        "matched": 2,
        "predicted": 2,
        "expert": 2,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
    assert same_card["matched"] == 1
    assert same_card["precision"] == 0.5
    assert same_card["recall"] == 0.5


def test_binary_ranking_metrics_score_perfect_and_reversed_order() -> None:
    labels = np.asarray([False, True, False, True])

    perfect = _binary_ranking_metrics(
        np.asarray([0.1, 0.8, 0.2, 0.9]), labels
    )
    reversed_order = _binary_ranking_metrics(
        np.asarray([0.9, 0.2, 0.8, 0.1]), labels
    )

    assert perfect == {"roc_auc": 1.0, "average_precision": 1.0}
    assert reversed_order["roc_auc"] == 0.0
    assert reversed_order["average_precision"] < 0.5
