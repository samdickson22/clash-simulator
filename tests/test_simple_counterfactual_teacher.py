from __future__ import annotations

import numpy as np
import pytest
import torch

from clasher.rl.common import NUM_TILES
from clasher.rl.outcome_model import ActorOutcomeHead, outcome_state_sha256
from scripts.probe_simple_counterfactual_teacher import (
    collect_counterfactual_branches,
    first_terminal_outcomes,
    first_terminal_tower_margins,
    load_outcome_ensemble,
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
        *,
        include_terminal_winners: bool = False,
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
            "terminal_winners": np.where(done, self.calls - 1, -1),
            "bootstrap_values": np.zeros(2, dtype=np.float64),
        }
        next_state = (state[0] + 1.0, state[1] + 1.0)
        return arrays, next_state, None, None, None


def test_outcome_loader_requires_current_untouched_holdout_authority(tmp_path) -> None:
    path = tmp_path / "outcome.pt"
    head = ActorOutcomeHead(18, hidden_size=4)
    report = {
        "status": "accepted-development",
        "actor_feature_contract": "public-globals",
        "outcome_head_state_sha256": outcome_state_sha256(head.state_dict()),
        "probability_calibration": (
            "factorized-training-mass-prior-plus-rank-preserving-shrinkage-v1"
        ),
        "selection_gates": {
            "natural_phase_auc_passed": True,
            "phase_auc_confidence_passed": True,
            "holdout_passed": True,
            "phase_auc_bootstrap_unit": "seed-style-deck-ordinal-cluster-v1",
            "minimum_phase_bootstrap_clusters": 8,
        },
    }
    payload = {
        "schema": "clasher.hog26.actor-outcome-training.v1",
        "base_checkpoint_sha256": "base",
        "state_size": 18,
        "hidden_size": 4,
        "separate_draw_trunk": False,
        "structured_residual_scale": 0.0,
        "outcome_head_state_dict": head.state_dict(),
        "training_report": report,
    }
    torch.save(payload, path)
    with pytest.raises(ValueError, match="untouched holdout"):
        load_outcome_ensemble(
            [path], base_checkpoint_sha256="base", device=torch.device("cpu")
        )

    report["status"] = "accepted-holdout"
    torch.save(payload, path)
    loaded = load_outcome_ensemble(
        [path], base_checkpoint_sha256="base", device=torch.device("cpu")
    )
    assert len(loaded) == 1
    assert loaded[0].feature_contract == "public-globals"

    del report["selection_gates"]["phase_auc_bootstrap_unit"]
    torch.save(payload, path)
    with pytest.raises(ValueError, match="predates"):
        load_outcome_ensemble(
            [path], base_checkpoint_sha256="base", device=torch.device("cpu")
        )

    report["selection_gates"]["phase_auc_bootstrap_unit"] = (
        "seed-style-deck-ordinal-cluster-v1"
    )
    report["selection_gates"]["minimum_phase_bootstrap_clusters"] = 7
    torch.save(payload, path)
    with pytest.raises(ValueError, match="predates"):
        load_outcome_ensemble(
            [path], base_checkpoint_sha256="base", device=torch.device("cpu")
        )

    report["selection_gates"]["minimum_phase_bootstrap_clusters"] = 8
    report["probability_calibration"] = (
        "factorized-training-mass-prior-plus-separate-decisive-temperature-v1"
    )
    torch.save(payload, path)
    with pytest.raises(ValueError, match="calibration"):
        load_outcome_ensemble(
            [path], base_checkpoint_sha256="base", device=torch.device("cpu")
        )

    report["probability_calibration"] = (
        "factorized-training-mass-prior-plus-rank-preserving-shrinkage-v1"
    )
    report["outcome_head_state_sha256"] = "0" * 64
    torch.save(payload, path)
    with pytest.raises(ValueError, match="tensor digest"):
        load_outcome_ensemble(
            [path], base_checkpoint_sha256="base", device=torch.device("cpu")
        )


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
    assert arrays["terminal_winners"].shape == (2, 6)
    torch.testing.assert_close(next_state[0], torch.full((2, 3), 2.0))


def test_first_terminal_outcomes_are_learner_relative_and_ignore_later_games() -> None:
    outcomes = first_terminal_outcomes(
        np.asarray(
            [
                [False, True, False, True],
                [True, False, False, False],
                [False, False, True, False],
                [False, False, False, False],
            ]
        ),
        np.asarray(
            [
                [-1, 0, -1, 1],
                [0, -1, -1, -1],
                [-1, -1, -1, -1],
                [-1, -1, -1, -1],
            ]
        ),
        np.asarray([0, 1, 0, 1]),
    )

    assert outcomes.tolist() == [1, -1, 0, 0]


def test_first_terminal_tower_margins_use_post_action_public_state() -> None:
    dones = np.asarray([[False, True, False], [False, False, False]])
    globals_rows = np.zeros((2, 3, 18), dtype=np.float32)
    globals_rows[0, 1, 8:11] = [1.0, 0.8, 1.0]
    globals_rows[0, 1, 11:14] = [0.5, 0.7, 1.0]
    margins = first_terminal_tower_margins(dones, globals_rows)
    assert margins[0] == pytest.approx(0.2)
    assert np.isnan(margins[1])
