from __future__ import annotations

import numpy as np
import torch

from scripts.pretrain_public_outcome_value import (
    OutcomeCorpus,
    PublicOutcomeHead,
    _concatenate_corpora,
    _game_balanced_weights,
    _learner_player,
    _opponent_kind,
    _paired_player_indices,
    evaluate_head,
    evaluate_head_by_opponent,
    evaluate_head_symmetry,
)


def test_game_balanced_weights_give_each_game_equal_mass() -> None:
    game_ids = np.asarray([0, 0, 0, 1], dtype=np.int64)
    weights = _game_balanced_weights(game_ids)

    assert np.isclose(weights[game_ids == 0].sum(), weights[game_ids == 1].sum())


def test_public_outcome_head_reports_ordered_auc() -> None:
    corpus = OutcomeCorpus(
        features=np.asarray([[-2.0], [-1.0], [1.0], [2.0]], dtype=np.float32),
        targets=np.asarray([0.0, 0.0, 1.0, 1.0], dtype=np.float32),
        game_ids=np.asarray([0, 1, 2, 3], dtype=np.int64),
        ticks=np.asarray([10, 10, 10, 10], dtype=np.int64),
        final_ticks=np.asarray([60, 60, 60, 60], dtype=np.int64),
        battle_ids=np.asarray([0, 1, 2, 3], dtype=np.int64),
        players=np.asarray([0, 1, 0, 1], dtype=np.int8),
        policy_controlled=np.ones(4, dtype=np.bool_),
    )
    head = PublicOutcomeHead(1, "linear")
    with torch.no_grad():
        head.network.weight.fill_(1.0)
        head.network.bias.zero_()

    report = evaluate_head(head, corpus, device=torch.device("cpu"))

    for phase in ("early", "middle", "late"):
        assert report[phase]["auc"] == 1.0


def test_paired_player_indices_align_exact_battle_ticks() -> None:
    corpus = OutcomeCorpus(
        features=np.zeros((5, 1), dtype=np.float32),
        targets=np.asarray([1.0, 0.0, 1.0, 0.0, 1.0], dtype=np.float32),
        game_ids=np.asarray([0, 1, 0, 1, 2], dtype=np.int64),
        ticks=np.asarray([8, 8, 16, 16, 8], dtype=np.int64),
        final_ticks=np.full(5, 32, dtype=np.int64),
        battle_ids=np.asarray([0, 0, 0, 0, 1], dtype=np.int64),
        players=np.asarray([0, 1, 0, 1, 0], dtype=np.int8),
        policy_controlled=np.ones(5, dtype=np.bool_),
    )

    player_0, player_1 = _paired_player_indices(corpus)

    assert player_0.tolist() == [0, 2]
    assert player_1.tolist() == [1, 3]


def test_concatenate_outcome_corpora_preserves_order_and_global_ids() -> None:
    def corpus(game: int, target: float) -> OutcomeCorpus:
        return OutcomeCorpus(
            features=np.asarray([[game, target]], dtype=np.float32),
            targets=np.asarray([target], dtype=np.float32),
            game_ids=np.asarray([game * 2], dtype=np.int64),
            ticks=np.asarray([8], dtype=np.int64),
            final_ticks=np.asarray([80], dtype=np.int64),
            battle_ids=np.asarray([game], dtype=np.int64),
            players=np.asarray([0], dtype=np.int8),
            policy_controlled=np.ones(1, dtype=np.bool_),
        )

    combined = _concatenate_corpora([corpus(3, 1.0), corpus(4, 0.0)])

    assert combined.battle_ids.tolist() == [3, 4]
    assert combined.game_ids.tolist() == [6, 8]
    assert combined.targets.tolist() == [1.0, 0.0]
    assert combined.features.tolist() == [[3.0, 1.0], [4.0, 0.0]]


def test_mixed_outcome_opponents_cover_all_strategies_random_and_selfplay() -> None:
    kinds = [_opponent_kind("mixed", game) for game in range(8)]

    assert kinds == [
        "bridge-pressure",
        "slow-push",
        "spell-control",
        "reactive-defense",
        "split-lane",
        "balanced",
        "random",
        "selfplay",
    ]
    assert [_learner_player("mixed", game) for game in range(16)] == [
        *([0] * 8),
        *([1] * 8),
    ]


def test_public_outcome_symmetry_aligns_complementary_player_views() -> None:
    corpus = OutcomeCorpus(
        features=np.asarray([[2.0], [-2.0], [-1.0], [1.0]], dtype=np.float32),
        targets=np.asarray([1.0, 0.0, 0.0, 1.0], dtype=np.float32),
        game_ids=np.asarray([0, 1, 2, 3], dtype=np.int64),
        ticks=np.asarray([8, 8, 8, 8], dtype=np.int64),
        final_ticks=np.asarray([48, 48, 48, 48], dtype=np.int64),
        battle_ids=np.asarray([0, 0, 1, 1], dtype=np.int64),
        players=np.asarray([0, 1, 0, 1], dtype=np.int8),
        policy_controlled=np.ones(4, dtype=np.bool_),
    )
    head = PublicOutcomeHead(1, "linear")
    with torch.no_grad():
        head.network.weight.fill_(1.0)
        head.network.bias.zero_()

    symmetry = evaluate_head_symmetry(head, corpus, device=torch.device("cpu"))
    by_opponent = evaluate_head_by_opponent(
        head,
        corpus,
        opponent_schedule=("first", "second"),
        device=torch.device("cpu"),
    )
    antisymmetric = evaluate_head(
        head,
        corpus,
        device=torch.device("cpu"),
        antisymmetric=True,
    )

    assert symmetry["pairs"] == 2
    assert symmetry["mean_abs_logit_sum"] == 0.0
    assert np.isclose(symmetry["mean_abs_probability_sum_error"], 0.0, atol=1e-7)
    assert set(by_opponent) == {"first", "second"}
    assert by_opponent["first"]["symmetry"]["pairs"] == 1
    assert antisymmetric["early"]["auc"] == 1.0
