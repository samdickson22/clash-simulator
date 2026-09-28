from __future__ import annotations

import pytest
import torch

from clasher.rl.structured_action_value import (
    PublicStructuredActionValueHead,
    StructuredActionValueConfig,
)


def test_structured_action_value_is_entity_and_candidate_permutation_equivariant() -> None:
    torch.manual_seed(2301)
    config = StructuredActionValueConfig(
        state_size=7,
        entity_feature_size=6,
        global_feature_size=4,
        entity_card_feature_size=5,
        card_feature_size=5,
        tile_feature_size=3,
        visible_card_slots=5,
        d_model=16,
        num_heads=4,
        num_layers=1,
        hidden_size=24,
    )
    head = PublicStructuredActionValueHead(
        config,
        torch.randn(11, 5),
    ).eval()
    state = torch.randn(2, 7)
    entity_ids = torch.tensor([[2, 3, 4, 0], [5, 6, 0, 0]])
    entity_features = torch.randn(2, 4, 6)
    entity_mask = entity_ids != 0
    hand_ids = torch.tensor([[2, 3, 4, 5, 6], [3, 4, 5, 6, 7]])
    globals_ = torch.randn(2, 4)
    cards = torch.randn(2, 4, 5)
    tiles = torch.randn(2, 4, 3)
    kinds = torch.tensor([[1, 0, 2, 0], [1, 0, 0, 2]])
    policy = torch.randn(2, 4).clamp_max(0.0)
    type_policy = torch.randn(2, 4).clamp_max(0.0)
    entity_permutation = torch.tensor([2, 0, 3, 1])
    candidate_permutation = torch.tensor([2, 0, 3, 1])

    expected = head(
        state,
        entity_ids,
        entity_features,
        entity_mask,
        hand_ids,
        globals_,
        cards,
        tiles,
        kinds,
        policy,
        type_policy,
    )
    actual = head(
        state,
        entity_ids[:, entity_permutation],
        entity_features[:, entity_permutation],
        entity_mask[:, entity_permutation],
        hand_ids,
        globals_,
        cards[:, candidate_permutation],
        tiles[:, candidate_permutation],
        kinds[:, candidate_permutation],
        policy[:, candidate_permutation],
        type_policy[:, candidate_permutation],
    )

    torch.testing.assert_close(actual, expected[:, candidate_permutation])


def test_structured_action_value_can_disable_identity_residual() -> None:
    torch.manual_seed(2302)
    config = StructuredActionValueConfig(
        state_size=7,
        entity_feature_size=6,
        global_feature_size=4,
        entity_card_feature_size=5,
        card_feature_size=5,
        tile_feature_size=3,
        visible_card_slots=5,
        d_model=16,
        num_heads=4,
        num_layers=1,
        hidden_size=24,
        identity_residual=False,
    )
    head = PublicStructuredActionValueHead(config, torch.zeros(11, 5)).eval()
    common = (
        torch.randn(1, 7),
        torch.randn(1, 3, 6),
        torch.ones(1, 3, dtype=torch.bool),
        torch.tensor([[2, 3, 4, 5, 6]]),
        torch.randn(1, 4),
        torch.randn(1, 2, 5),
        torch.randn(1, 2, 3),
        torch.tensor([[1, 0]]),
        torch.zeros(1, 2),
        torch.zeros(1, 2),
    )

    first = head(common[0], torch.tensor([[2, 3, 4]]), *common[1:])
    second = head(common[0], torch.tensor([[7, 8, 9]]), *common[1:])

    torch.testing.assert_close(first, second)


def test_structured_action_value_consumes_compact_recurrent_context() -> None:
    torch.manual_seed(2303)
    config = StructuredActionValueConfig(
        state_size=7,
        entity_feature_size=6,
        global_feature_size=4,
        entity_card_feature_size=5,
        card_feature_size=5,
        tile_feature_size=3,
        visible_card_slots=5,
        d_model=16,
        num_heads=4,
        num_layers=1,
        hidden_size=24,
        recurrent_cell_size=3,
        play_hazard_size=1,
    )
    head = PublicStructuredActionValueHead(config, torch.randn(11, 5)).eval()
    common = (
        torch.randn(1, 7),
        torch.tensor([[2, 3, 0]]),
        torch.randn(1, 3, 6),
        torch.tensor([[True, True, False]]),
        torch.tensor([[2, 3, 4, 5, 6]]),
        torch.randn(1, 4),
        torch.randn(1, 2, 5),
        torch.randn(1, 2, 3),
        torch.tensor([[1, 0]]),
        torch.zeros(1, 2),
        torch.zeros(1, 2),
    )
    cell = torch.randn(1, 3)

    first = head(*common, cell, torch.zeros(1, 1))
    second = head(*common, cell, torch.ones(1, 1))

    assert not torch.equal(first, second)
    with pytest.raises(ValueError, match="recurrent cell shape"):
        head(*common, torch.zeros(1, 2), torch.zeros(1, 1))
