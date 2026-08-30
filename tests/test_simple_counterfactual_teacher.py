from __future__ import annotations

import numpy as np
import pytest

from clasher.rl.common import NUM_TILES
from scripts.probe_simple_counterfactual_teacher import (
    select_stratified_action_subset,
    truncated_n_step_returns,
)


def test_stratified_candidates_cover_every_playable_slot_and_required_actions() -> None:
    no_op = 4 * NUM_TILES
    legal = np.concatenate(
        [np.arange(slot * NUM_TILES, (slot + 1) * NUM_TILES) for slot in range(4)]
        + [np.asarray([no_op])]
    )
    logits = np.linspace(-3.0, 3.0, no_op + 2, dtype=np.float64)
    parent = 2 * NUM_TILES + 17

    first = select_stratified_action_subset(
        legal,
        logits,
        sample_limit=16,
        no_op_action=no_op,
        parent_action=parent,
        random_fraction=0.25,
        rng=np.random.default_rng(2301),
    )
    second = select_stratified_action_subset(
        legal,
        logits,
        sample_limit=16,
        no_op_action=no_op,
        parent_action=parent,
        random_fraction=0.25,
        rng=np.random.default_rng(2301),
    )

    assert np.array_equal(first, second)
    assert len(first) == len(np.unique(first)) == 16
    assert no_op in first
    assert parent in first
    assert set((first[first < no_op] // NUM_TILES).tolist()) == {0, 1, 2, 3}
    assert np.isin(first, legal).all()


def test_stratified_candidates_reject_illegal_required_action() -> None:
    no_op = 4 * NUM_TILES
    legal = np.asarray([0, 1, 2, no_op], dtype=np.int64)
    logits = np.zeros(no_op + 2, dtype=np.float64)
    with pytest.raises(ValueError, match="required action"):
        select_stratified_action_subset(
            legal,
            logits,
            sample_limit=3,
            no_op_action=no_op,
            parent_action=99,
            random_fraction=0.25,
            rng=np.random.default_rng(1),
        )


def test_truncated_returns_stop_at_terminal_and_bootstrap_only_nonterminal() -> None:
    values, rewards, bootstrap = truncated_n_step_returns(
        np.asarray([[1.0, 2.0, 100.0], [1.0, 2.0, 3.0]]),
        np.asarray([[False, True, False], [False, False, False]]),
        np.asarray([50.0, 10.0]),
        gamma=0.5,
    )

    assert rewards.tolist() == pytest.approx([2.0, 2.75])
    assert bootstrap.tolist() == pytest.approx([0.0, 1.25])
    assert values.tolist() == pytest.approx([2.0, 4.0])
