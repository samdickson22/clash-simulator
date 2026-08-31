from __future__ import annotations

import numpy as np
import pytest
import torch

from clasher.rl.common import NUM_TILES
from scripts.probe_simple_counterfactual_teacher import (
    collect_counterfactual_branches,
    select_stratified_action_subset,
    truncated_n_step_returns,
)


class _FakeCollector:
    def __init__(self) -> None:
        self.calls = 0

    def collect(
        self,
        count: int,
        state: tuple[torch.Tensor, torch.Tensor],
    ) -> tuple[
        dict[str, np.ndarray],
        tuple[torch.Tensor, torch.Tensor],
        None,
        None,
        None,
    ]:
        self.calls += 1
        done = np.zeros((2, count), dtype=np.bool_)
        done[self.calls - 1, -1] = True
        arrays = {
            "rewards": np.full((2, count), self.calls, dtype=np.float64),
            "dones": done,
            "bootstrap_values": np.zeros(2, dtype=np.float64),
        }
        next_state = (state[0] + 1.0, state[1] + 1.0)
        return arrays, next_state, None, None, None


def test_stratified_candidates_cover_every_playable_slot_and_required_actions() -> None:
    no_op = 4 * NUM_TILES
    legal = np.concatenate(
        [np.arange(slot * NUM_TILES, (slot + 1) * NUM_TILES) for slot in range(4)]
        + [np.asarray([no_op])]
    )
    logits = np.linspace(-3.0, 3.0, no_op + 2, dtype=np.float64)
    parent = 2 * NUM_TILES + 17
    proposals = np.asarray([3 * NUM_TILES + 29, NUM_TILES + 31])

    first = select_stratified_action_subset(
        legal,
        logits,
        sample_limit=16,
        no_op_action=no_op,
        parent_action=parent,
        proposal_actions=proposals,
        random_fraction=0.25,
        rng=np.random.default_rng(2301),
    )
    second = select_stratified_action_subset(
        legal,
        logits,
        sample_limit=16,
        no_op_action=no_op,
        parent_action=parent,
        proposal_actions=proposals,
        random_fraction=0.25,
        rng=np.random.default_rng(2301),
    )

    assert np.array_equal(first, second)
    assert len(first) == len(np.unique(first)) == 16
    assert no_op in first
    assert parent in first
    assert np.isin(proposals, first).all()
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


def test_stratified_candidates_reject_proposals_over_capacity() -> None:
    no_op = 4 * NUM_TILES
    legal = np.asarray([0, 1, 2, 3, no_op], dtype=np.int64)
    logits = np.zeros(no_op + 2, dtype=np.float64)
    with pytest.raises(ValueError, match="exceed the sample limit"):
        select_stratified_action_subset(
            legal,
            logits,
            sample_limit=3,
            no_op_action=no_op,
            parent_action=0,
            proposal_actions=np.asarray([1, 2]),
            random_fraction=0.0,
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


def test_chunked_counterfactual_collection_stops_after_all_first_terminals() -> None:
    collector = _FakeCollector()
    state = (torch.zeros((2, 3)), torch.zeros((2, 3)))

    arrays, next_state = collect_counterfactual_branches(
        collector,  # type: ignore[arg-type]
        state,
        horizon_steps=12,
        stop_when_all_terminal=True,
        chunk_steps=3,
    )

    assert collector.calls == 2
    assert arrays["rewards"].shape == (2, 6)
    assert arrays["dones"].sum(axis=1).tolist() == [1, 1]
    torch.testing.assert_close(next_state[0], torch.full((2, 3), 2.0))
