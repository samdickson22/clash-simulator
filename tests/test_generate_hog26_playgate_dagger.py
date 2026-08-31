from __future__ import annotations

import numpy as np

from scripts.generate_hog26_playgate_dagger import flatten_batch, pack_entities


def test_pack_entities_preserves_order_and_moves_padding_to_suffix() -> None:
    arrays = {
        "entity_ids": np.asarray([[[3, 0, 7, 0]]]),
        "entity_features": np.arange(1 * 1 * 4 * 2).reshape(1, 1, 4, 2),
        "entity_mask": np.asarray([[[True, False, True, False]]]),
    }
    expected = arrays["entity_features"][0, 0, [0, 2]].copy()
    pack_entities(arrays)
    assert arrays["entity_ids"].tolist() == [[[3, 7, 0, 0]]]
    assert arrays["entity_mask"].tolist() == [[[True, True, False, False]]]
    np.testing.assert_array_equal(arrays["entity_features"][0, 0, :2], expected)


def test_flatten_batch_keeps_each_recurrent_sequence_contiguous() -> None:
    arrays: dict[str, np.ndarray] = {}
    for name in (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
        "entity_id_confidence",
        "entity_feature_confidence",
        "hand_id_confidence",
        "global_feature_confidence",
        "action_masks",
        "previous_actions",
        "previous_rewards",
        "episode_starts",
    ):
        arrays[name] = np.arange(6).reshape(2, 3)
    teacher = np.asarray([[10, 11, 12], [20, 21, 22]])
    flat = flatten_batch(arrays, teacher, episode_base=7)
    assert flat["expert_actions"].tolist() == [10, 11, 12, 20, 21, 22]
    assert flat["episode_ids"].tolist() == [7, 7, 7, 8, 8, 8]
    assert flat["source_frames"].tolist() == [0, 1, 2, 0, 1, 2]
