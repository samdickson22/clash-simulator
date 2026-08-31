from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from scripts.train_hog26_factorized_counterfactual import (
    ROOT_POLICY_INPUT_KEYS,
    load_preferences,
    root_policy_input_fingerprints,
)


def test_preference_table_keeps_corrective_and_safety_pairs(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.npz"
    np.savez_compressed(
        corpus,
        counterfactual_root_rows=np.asarray([10]),
        root_base_actions=np.asarray([2304]),
        root_candidate_actions=np.asarray([[20, 21, 2304]]),
        root_candidate_valid=np.asarray([[True, True, True]]),
        root_candidate_scores=np.asarray([[0.3, -0.2, 0.0]]),
    )

    table = load_preferences(corpus)

    assert table.root_rows.tolist() == [10, 10]
    assert table.positive_actions.tolist() == [20, 2304]
    assert table.negative_actions.tolist() == [2304, 21]
    assert table.corrective.tolist() == [True, False]
    assert table.weights.tolist() == pytest.approx([4.0, 3.0])


def test_preference_table_rejects_missing_base_action(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.npz"
    np.savez_compressed(
        corpus,
        counterfactual_root_rows=np.asarray([10]),
        root_base_actions=np.asarray([2304]),
        root_candidate_actions=np.asarray([[20, 21]]),
        root_candidate_valid=np.asarray([[True, True]]),
        root_candidate_scores=np.asarray([[0.3, -0.2]]),
    )
    with pytest.raises(ValueError, match="base action"):
        load_preferences(corpus)


def test_preference_table_can_preserve_the_behavior_play_gate(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.npz"
    np.savez_compressed(
        corpus,
        counterfactual_root_rows=np.asarray([10]),
        root_base_actions=np.asarray([100]),
        root_candidate_actions=np.asarray([[20, 100, 2304]]),
        root_candidate_valid=np.asarray([[True, True, True]]),
        root_candidate_scores=np.asarray([[0.3, 0.0, 0.5]]),
    )

    table = load_preferences(corpus, preserve_behavior_gate=True)

    assert table.positive_actions.tolist() == [20]
    assert table.negative_actions.tolist() == [100]
    assert table.corrective.tolist() == [True]


def _policy_arrays() -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    for index, key in enumerate(ROOT_POLICY_INPUT_KEYS):
        arrays[key] = np.asarray([[index], [index + 1]], dtype=np.float32)
    return arrays


def test_root_fingerprints_ignore_provenance_but_detect_exact_input_overlap() -> None:
    train = _policy_arrays()
    validation = {key: value.copy() for key, value in train.items()}
    train["episode_ids"] = np.asarray([10, 10])
    validation["episode_ids"] = np.asarray([20, 20])

    train_hashes = root_policy_input_fingerprints(train, np.asarray([0]))
    validation_hashes = root_policy_input_fingerprints(validation, np.asarray([0]))

    assert train_hashes == validation_hashes
    validation["global_features"][0, 0] += 1.0
    assert train_hashes.isdisjoint(
        root_policy_input_fingerprints(validation, np.asarray([0]))
    )


def test_root_fingerprints_reject_out_of_range_rows() -> None:
    with pytest.raises(ValueError, match="outside the corpus"):
        root_policy_input_fingerprints(_policy_arrays(), np.asarray([2]))
