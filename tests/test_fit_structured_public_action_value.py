from __future__ import annotations

import numpy as np
import pytest
import torch

from clasher.rl.structured_action_value import (
    PublicStructuredActionValueHead,
    StructuredActionValueConfig,
)
from scripts.fit_public_action_value import OUTCOME_PRIORITY, PreferenceRows
from scripts.fit_structured_public_action_value import (
    _game_cluster_bootstrap_metrics,
    _pair_metrics,
    _require_finite_named_tensors,
    _score_states,
    _split_validation_states,
    _structured_state_sizes,
    _threshold_metrics,
)


def test_validation_split_is_deterministic_and_game_disjoint() -> None:
    payload = {
        "game_ids": np.repeat(np.arange(100, dtype=np.int64), 3),
    }

    states_a, games_a = _split_validation_states(payload, seed=1169102)
    states_b, games_b = _split_validation_states(payload, seed=1169102)

    assert games_a == games_b
    assert {name: values.tolist() for name, values in states_a.items()} == {
        name: values.tolist() for name, values in states_b.items()
    }
    assert len(games_a["selection"]) == 30
    assert len(games_a["calibration"]) == 30
    assert len(games_a["holdout"]) == 40
    assert not set(games_a["selection"]) & set(games_a["calibration"])
    assert not set(games_a["selection"]) & set(games_a["holdout"])
    assert not set(games_a["calibration"]) & set(games_a["holdout"])
    assert sum(len(values) for values in states_a.values()) == 300


def test_fixed_threshold_metrics_do_not_retune_on_holdout() -> None:
    payload = {
        "candidate_scores": np.asarray(
            [[0.0, 1.0], [1.0, 0.0]], dtype=np.float32
        ),
        "candidate_crown_differences": np.zeros((2, 2), dtype=np.int64),
        "candidate_tower_damage_differences": np.zeros(
            (2, 2), dtype=np.float32
        ),
        "candidate_valid": np.ones((2, 2), dtype=np.bool_),
    }
    scores = np.asarray([[0.0, 0.6], [0.0, 2.0]], dtype=np.float32)

    metrics = _threshold_metrics(
        scores=scores,
        payload=payload,
        state_indices=np.asarray([0, 1], dtype=np.int64),
        threshold=0.5,
    )

    assert metrics["threshold"] == 0.5
    assert metrics["overrides"] == 2
    assert metrics["improvements"]["outcome"] == 1
    assert metrics["regressions"]["outcome"] == 1


def test_pair_metrics_use_only_requested_validation_states() -> None:
    preferences = PreferenceRows(
        state_indices=np.asarray([0, 1], dtype=np.int64),
        positive_indices=np.asarray([1, 1], dtype=np.int64),
        negative_indices=np.asarray([0, 0], dtype=np.int64),
        priorities=np.full(2, OUTCOME_PRIORITY, dtype=np.int64),
        weights=np.ones(2, dtype=np.float32),
    )
    scores = np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)

    first = _pair_metrics(
        scores,
        preferences,
        np.asarray([0], dtype=np.int64),
    )
    second = _pair_metrics(
        scores,
        preferences,
        np.asarray([1], dtype=np.int64),
    )

    assert first["pairs"] == 1
    assert first["accuracy"] == 1.0
    assert first["outcome_accuracy"] == 1.0
    assert second["pairs"] == 1
    assert second["accuracy"] == 0.0
    assert second["outcome_accuracy"] == 0.0


def test_game_cluster_bootstrap_is_deterministic_and_game_scoped() -> None:
    payload = {
        "game_ids": np.arange(4, dtype=np.int64),
        "candidate_valid": np.ones((4, 2), dtype=np.bool_),
        "candidate_scores": np.asarray(
            [[0, 1], [0, 1], [0, 1], [1, 0]], dtype=np.float32
        ),
        "candidate_crown_differences": np.zeros((4, 2), dtype=np.int64),
        "candidate_tower_damage_differences": np.zeros(
            (4, 2), dtype=np.float32
        ),
    }
    preferences = PreferenceRows(
        state_indices=np.arange(4, dtype=np.int64),
        positive_indices=np.asarray([1, 1, 1, 0], dtype=np.int64),
        negative_indices=np.asarray([0, 0, 0, 1], dtype=np.int64),
        priorities=np.full(4, OUTCOME_PRIORITY, dtype=np.int64),
        weights=np.ones(4, dtype=np.float32),
    )
    scores = np.asarray(
        [[0, 1], [0, 1], [0, 1], [0, 1]], dtype=np.float32
    )
    kwargs = {
        "scores": scores,
        "payload": payload,
        "preferences": preferences,
        "state_indices": np.arange(4, dtype=np.int64),
        "seed": 2301,
        "samples": 1000,
    }

    first = _game_cluster_bootstrap_metrics(**kwargs)
    second = _game_cluster_bootstrap_metrics(**kwargs)

    assert first == second
    assert first["games"] == 4
    assert first["samples"] == 1000
    assert 0.0 <= first["accuracy_ci95"][0] <= first["accuracy_ci95"][1] <= 1.0
    assert first["optimal_action_rate_ci95"] == first["accuracy_ci95"]


def test_structured_v2_state_sizes_require_exact_recurrent_tail() -> None:
    cell = np.asarray([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
    hazard = np.asarray([[0.5], [0.6]], dtype=np.float32)
    pooled = np.concatenate(
        (np.zeros((2, 3), dtype=np.float32), cell), axis=1
    )
    train = {
        "features": pooled.copy(),
        "structured_recurrent_cell": cell.copy(),
        "structured_previous_play_hazard": hazard.copy(),
    }
    validation = {name: value.copy() for name, value in train.items()}

    assert _structured_state_sizes(
        train,
        validation,
        contract="public-actor-v2-action-time-recurrence",
    ) == (3, 2, 1)

    validation["structured_recurrent_cell"][1, 1] = 0.9
    with np.testing.assert_raises_regex(ValueError, "tail disagrees"):
        _structured_state_sizes(
            train,
            validation,
            contract="public-actor-v2-action-time-recurrence",
        )


def test_structured_fit_rejects_nonfinite_gradients_and_parameters() -> None:
    layer = torch.nn.Linear(2, 1)
    layer(torch.ones(1, 2)).sum().backward()
    _require_finite_named_tensors(
        [(name, parameter.grad) for name, parameter in layer.named_parameters()],
        kind="gradients",
    )

    assert layer.weight.grad is not None
    layer.weight.grad[0, 0] = torch.nan
    with pytest.raises(FloatingPointError, match="gradients.*weight"):
        _require_finite_named_tensors(
            [
                (name, parameter.grad)
                for name, parameter in layer.named_parameters()
            ],
            kind="gradients",
        )

    with torch.no_grad():
        layer.weight.fill_(torch.inf)
    with pytest.raises(FloatingPointError, match="parameters.*weight"):
        _require_finite_named_tensors(
            list(layer.named_parameters()),
            kind="parameters",
        )


def test_ranker_scores_are_independent_of_terminal_supervision_arrays() -> None:
    torch.manual_seed(2301)
    head = PublicStructuredActionValueHead(
        StructuredActionValueConfig(
            state_size=3,
            entity_feature_size=2,
            global_feature_size=2,
            entity_card_feature_size=4,
            card_feature_size=4,
            tile_feature_size=3,
            visible_card_slots=5,
            d_model=8,
            num_heads=2,
            num_layers=1,
            hidden_size=8,
        ),
        torch.arange(24, dtype=torch.float32).reshape(6, 4) / 24.0,
    ).eval()
    payload = {
        "features": np.arange(6, dtype=np.float32).reshape(2, 3) / 6.0,
        "structured_entity_ids": np.asarray([[2, 3], [4, 0]]),
        "structured_entity_features": np.arange(
            8, dtype=np.float32
        ).reshape(2, 2, 2),
        "structured_entity_mask": np.asarray(
            [[True, True], [True, False]], dtype=np.bool_
        ),
        "structured_hand_ids": np.asarray(
            [[2, 3, 4, 5, 2], [3, 4, 5, 2, 3]], dtype=np.int64
        ),
        "structured_global_features": np.asarray(
            [[0.1, 0.2], [0.3, 0.4]], dtype=np.float32
        ),
        "candidate_card_features": np.arange(
            24, dtype=np.float32
        ).reshape(2, 3, 4),
        "candidate_tile_features": np.arange(
            18, dtype=np.float32
        ).reshape(2, 3, 3),
        "candidate_kinds": np.asarray([[0, 1, 2], [0, 0, 1]], dtype=np.int64),
        "candidate_policy_log_probabilities": np.asarray(
            [[-0.2, -1.0, -2.0], [-0.1, -0.8, -1.5]], dtype=np.float32
        ),
        "candidate_policy_type_log_probabilities": np.asarray(
            [[-0.1, -0.7, -1.7], [-0.2, -0.9, -1.3]], dtype=np.float32
        ),
        "candidate_scores": np.asarray(
            [[-1.0, 0.0, 1.0], [1.0, 0.0, -1.0]], dtype=np.float32
        ),
        "candidate_crown_differences": np.asarray(
            [[-1, 0, 1], [1, 0, -1]], dtype=np.int64
        ),
        "candidate_tower_damage_differences": np.asarray(
            [[-0.5, 0.0, 0.5], [0.5, 0.0, -0.5]], dtype=np.float32
        ),
        "candidate_terminal_ticks": np.asarray(
            [[6000, 5000, 4000], [4000, 5000, 6000]], dtype=np.int64
        ),
        "best_actions": np.asarray([2, 0], dtype=np.int64),
    }
    states = np.asarray([0, 1], dtype=np.int64)
    before = _score_states(head, payload, states, torch.device("cpu"))

    payload["candidate_scores"] *= -7.0
    payload["candidate_crown_differences"] *= -1
    payload["candidate_tower_damage_differences"] += 99.0
    payload["candidate_terminal_ticks"][:] = 1
    payload["best_actions"][:] = np.asarray([0, 2])
    after = _score_states(head, payload, states, torch.device("cpu"))

    torch.testing.assert_close(before, after, rtol=0.0, atol=0.0)
