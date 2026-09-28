from __future__ import annotations

import numpy as np
import torch

from scripts.fit_terminal_counterfactual_adapter import PreferenceRows
from scripts.train_recurrent_counterfactual_actor import (
    ChunkPreferences,
    _actor_trainable,
    _build_action_preferences,
    _eligible,
    chunk_preferences,
    hazard_preference_loss,
    pairwise_preference_loss,
)


def test_action_preferences_retain_same_card_tile_corrections() -> None:
    rows = _build_action_preferences(
        {
            "base_actions": np.asarray([0], dtype=np.int64),
            "candidate_actions": np.asarray([[0, 1]], dtype=np.int64),
            "candidate_valid": np.asarray([[True, True]]),
            "candidate_scores": np.asarray([[0.0, 0.0]], dtype=np.float32),
            "candidate_crown_differences": np.asarray([[0, 0]], dtype=np.int8),
            "candidate_tower_damage_differences": np.asarray(
                [[-100.0, 100.0]], dtype=np.float32
            ),
        }
    )

    assert rows.state_indices.tolist() == [0]
    assert rows.positive_types.tolist() == [1]
    assert rows.negative_types.tolist() == [0]
    assert rows.kinds.tolist() == [1]


def test_decisive_only_excludes_crown_and_damage_tiebreak_preferences() -> None:
    payload = {
        "base_actions": np.asarray([0], dtype=np.int64),
        "candidate_actions": np.asarray([[0, 1, 2]], dtype=np.int64),
        "candidate_valid": np.asarray([[True, True, True]]),
        "candidate_scores": np.asarray([[0.0, 0.0, 1.0]], dtype=np.float32),
        "candidate_crown_differences": np.asarray([[0, 2, 1]], dtype=np.int8),
        "candidate_tower_damage_differences": np.asarray(
            [[-100.0, 500.0, 100.0]], dtype=np.float32
        ),
    }

    all_rows = _build_action_preferences(payload)
    decisive_rows = _build_action_preferences(payload, decisive_only=True)

    assert all_rows.positive_types.tolist() == [1, 2]
    assert decisive_rows.positive_types.tolist() == [2]
    assert decisive_rows.negative_types.tolist() == [0]
    assert decisive_rows.weights.tolist() == [4.0]


def test_action_preferences_can_require_large_terminal_margin() -> None:
    payload = {
        "base_actions": np.asarray([0], dtype=np.int64),
        "candidate_actions": np.asarray([[0, 1, 2, 3]], dtype=np.int64),
        "candidate_valid": np.asarray([[True, True, True, True]]),
        "candidate_scores": np.asarray([[0.0, 0.0, 0.0, 1.0]], dtype=np.float32),
        "candidate_crown_differences": np.asarray([[0, 0, 1, 0]], dtype=np.int8),
        "candidate_tower_damage_differences": np.asarray(
            [[0.0, 100.0, 500.0, 0.0]], dtype=np.float32
        ),
    }

    rows = _build_action_preferences(
        payload,
        minimum_crown_gap=1,
        minimum_tower_damage_gap=1500.0,
    )

    assert rows.positive_types.tolist() == [2, 3]
    assert rows.negative_types.tolist() == [0, 0]


def test_trainable_prefixes_freeze_timing_and_shared_representation() -> None:
    prefixes = ("card_query.", "location_bias.")

    assert _actor_trainable("card_query.0.weight", prefixes)
    assert _actor_trainable("location_bias.bias", prefixes)
    assert not _actor_trainable("play_hazard_head.0.weight", prefixes)
    assert not _actor_trainable("actor_encoder.card_embedding.weight", prefixes)


def test_chunk_preferences_maps_root_indices_to_recurrent_time() -> None:
    rows = PreferenceRows(
        state_indices=np.asarray([0, 1, 1], dtype=np.int64),
        positive_types=np.asarray([2, 3, 4], dtype=np.int64),
        negative_types=np.asarray([4, 4, 3], dtype=np.int64),
        weights=np.asarray([4.0, 2.0, 1.0], dtype=np.float32),
        kinds=np.asarray([1, 1, 0], dtype=np.int8),
    )
    selected = chunk_preferences(
        rows,
        np.asarray([5, 20], dtype=np.int64),
        start=4,
        stop=10,
        device=torch.device("cpu"),
    )

    assert selected.count == 1
    assert selected.state_indices.tolist() == [1]
    assert selected.positive_types.tolist() == [2]
    assert selected.negative_types.tolist() == [4]
    assert selected.weights.tolist() == [4.0]
    assert selected.kinds.tolist() == [1]


def test_pairwise_preference_loss_rewards_the_preferred_action_type() -> None:
    preferences = chunk_preferences(
        PreferenceRows(
            state_indices=np.asarray([0], dtype=np.int64),
            positive_types=np.asarray([1], dtype=np.int64),
            negative_types=np.asarray([4], dtype=np.int64),
            weights=np.asarray([4.0], dtype=np.float32),
            kinds=np.asarray([1], dtype=np.int8),
        ),
        np.asarray([0], dtype=np.int64),
        start=0,
        stop=1,
        device=torch.device("cpu"),
    )
    correct = torch.tensor([[0.0, 2.0, 0.0, 0.0, -2.0, 0.0]])
    wrong = torch.tensor([[0.0, -2.0, 0.0, 0.0, 2.0, 0.0]])

    assert pairwise_preference_loss(correct, preferences) < pairwise_preference_loss(
        wrong, preferences
    )


def test_hazard_preference_loss_moves_only_placement_wait_crossings() -> None:
    preferences = ChunkPreferences(
        state_indices=torch.tensor([0, 1, 2]),
        positive_types=torch.tensor([0, 2304, 1]),
        negative_types=torch.tensor([2304, 2, 3]),
        weights=torch.tensor([4.0, 4.0, 4.0]),
        kinds=torch.tensor([1, 0, 1], dtype=torch.int8),
    )
    reference = torch.zeros(3)
    preferred = torch.tensor([2.0, -2.0, 0.0])
    reversed_logits = torch.tensor([-2.0, 2.0, 0.0])

    assert hazard_preference_loss(
        preferred, reference, preferences
    ) < hazard_preference_loss(reversed_logits, reference, preferences)


def test_hazard_preference_loss_is_zero_without_placement_wait_crossing() -> None:
    logits = torch.tensor([1.0], requires_grad=True)
    loss = hazard_preference_loss(
        logits,
        torch.zeros(1),
        ChunkPreferences(
            state_indices=torch.tensor([0]),
            positive_types=torch.tensor([1]),
            negative_types=torch.tensor([2]),
            weights=torch.tensor([4.0]),
            kinds=torch.tensor([1], dtype=torch.int8),
        ),
    )

    loss.backward()
    assert loss.item() == 0.0
    assert logits.grad is not None
    assert logits.grad.item() == 0.0


def test_hazard_preference_loss_balances_corrective_and_safety_strata() -> None:
    logits = torch.tensor([0.0], requires_grad=True)
    loss = hazard_preference_loss(
        logits,
        torch.zeros(1),
        ChunkPreferences(
            state_indices=torch.tensor([0, 0, 0, 0]),
            positive_types=torch.tensor([0, 1, 2, 2304]),
            negative_types=torch.tensor([2304, 2304, 2304, 3]),
            weights=torch.ones(4),
            kinds=torch.tensor([1, 1, 1, 0], dtype=torch.int8),
        ),
    )

    loss.backward()
    assert logits.grad is not None
    assert abs(logits.grad.item()) < 1e-7


def test_selection_gate_requires_correction_without_safety_regression() -> None:
    initial = {
        "behavior": {"action_type_accuracy": 0.80},
        "preferences": {
            "corrective": {"accuracy": 0.40},
            "safety": {"accuracy": 0.60},
        },
    }
    passing = {
        "behavior": {"action_type_accuracy": 0.795},
        "preferences": {
            "corrective": {"accuracy": 0.43},
            "safety": {"accuracy": 0.595},
        },
    }
    unsafe = {
        "behavior": {"action_type_accuracy": 0.80},
        "preferences": {
            "corrective": {"accuracy": 0.50},
            "safety": {"accuracy": 0.58},
        },
    }

    assert _eligible(
        passing,
        initial,
        maximum_safety_regression=0.01,
        maximum_behavior_regression=0.01,
        minimum_corrective_improvement=0.01,
    )
    assert not _eligible(
        unsafe,
        initial,
        maximum_safety_regression=0.01,
        maximum_behavior_regression=0.01,
        minimum_corrective_improvement=0.01,
    )


def test_action_level_selection_can_guard_exact_behavior_accuracy() -> None:
    initial = {
        "behavior": {"action_type_accuracy": 0.1, "exact_action_accuracy": 0.9},
        "preferences": {
            "corrective": {"accuracy": 0.4},
            "safety": {"accuracy": 0.8},
        },
    }
    candidate = {
        "behavior": {"action_type_accuracy": 0.0, "exact_action_accuracy": 0.9},
        "preferences": {
            "corrective": {"accuracy": 0.5},
            "safety": {"accuracy": 0.8},
        },
    }

    assert _eligible(
        candidate,
        initial,
        maximum_safety_regression=0.0,
        maximum_behavior_regression=0.0,
        minimum_corrective_improvement=0.01,
        behavior_accuracy_key="exact_action_accuracy",
    )
