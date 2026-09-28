from __future__ import annotations

from dataclasses import replace

import pytest
import torch
from torch import nn

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.hierarchical_imitation import (
    ABILITY_ACTION,
    NUM_ACTIONS,
    PLAY_DECISION,
    UNKNOWN_LABEL,
    WAIT_DECISION,
    HierarchicalImitationLabels,
    factor_public_action_mask,
    hierarchical_imitation_metric_sums,
    hierarchical_masked_imitation_loss,
    labels_from_flat_actions,
)


def _public_mask(batch_size: int) -> torch.Tensor:
    mask = torch.ones(batch_size, NUM_ACTIONS, dtype=torch.bool)
    mask[:, 7] = False
    return mask


def test_uncertain_labels_are_ignored_instead_of_becoming_wait_or_tile_zero() -> None:
    torch.manual_seed(1)
    decision_logits = torch.randn(4, 3, requires_grad=True)
    card_logits = torch.randn(4, NUM_HAND_SLOTS, requires_grad=True)
    tile_logits = torch.randn(4, NUM_HAND_SLOTS, NUM_TILES, requires_grad=True)
    actions = torch.tensor([NUM_HAND_SLOTS * NUM_TILES, 2 * NUM_TILES + 42, 0, ABILITY_ACTION])
    labels = labels_from_flat_actions(
        actions,
        decision_trusted=torch.tensor([True, True, False, True]),
        card_trusted=torch.tensor([False, True, False, False]),
        tile_trusted=torch.tensor([False, True, False, False]),
    )
    masks = factor_public_action_mask(_public_mask(4))

    loss = hierarchical_masked_imitation_loss(
        decision_logits, card_logits, tile_logits, masks, labels
    )
    expected_decision = nn.functional.cross_entropy(
        decision_logits[[0, 1, 3]], torch.tensor([WAIT_DECISION, PLAY_DECISION, 2])
    )
    expected_card = nn.functional.cross_entropy(card_logits[[1]], torch.tensor([2]))
    expected_tile = nn.functional.cross_entropy(tile_logits[1, 2].unsqueeze(0), torch.tensor([42]))
    torch.testing.assert_close(loss.decision, expected_decision)
    torch.testing.assert_close(loss.card, expected_card)
    torch.testing.assert_close(loss.tile, expected_tile)
    assert (loss.decision_count.item(), loss.card_count.item(), loss.tile_count.item()) == (3, 1, 1)
    assert labels.decision_target[2].item() == UNKNOWN_LABEL
    assert labels.card_target[2].item() == UNKNOWN_LABEL
    assert labels.tile_target[2].item() == UNKNOWN_LABEL
    metrics = hierarchical_imitation_metric_sums(
        decision_logits, card_logits, tile_logits, masks, labels
    )
    assert metrics["decision_count"].item() == 3
    assert metrics["card_count"].item() == 1
    assert metrics["tile_count"].item() == 1

    loss.total.backward()
    assert torch.count_nonzero(decision_logits.grad[2]).item() == 0
    assert torch.count_nonzero(card_logits.grad[[0, 2, 3]]).item() == 0
    assert torch.count_nonzero(tile_logits.grad[[0, 2, 3]]).item() == 0


def test_empty_conditional_components_are_finite_differentiable_zero() -> None:
    decision_logits = torch.randn(2, 3, requires_grad=True)
    card_logits = torch.full(
        (2, NUM_HAND_SLOTS), -torch.inf, requires_grad=True
    )
    tile_logits = torch.full(
        (2, NUM_HAND_SLOTS, NUM_TILES), -torch.inf, requires_grad=True
    )
    actions = torch.full((2,), NUM_HAND_SLOTS * NUM_TILES, dtype=torch.long)
    labels = labels_from_flat_actions(
        actions,
        decision_trusted=torch.ones(2, dtype=torch.bool),
        card_trusted=torch.zeros(2, dtype=torch.bool),
        tile_trusted=torch.zeros(2, dtype=torch.bool),
    )
    loss = hierarchical_masked_imitation_loss(
        decision_logits,
        card_logits,
        tile_logits,
        factor_public_action_mask(_public_mask(2)),
        labels,
    )
    assert torch.isfinite(loss.total)
    assert loss.card.item() == 0.0
    assert loss.tile.item() == 0.0
    loss.total.backward()
    assert card_logits.grad is not None
    assert tile_logits.grad is not None
    assert torch.count_nonzero(card_logits.grad).item() == 0
    assert torch.count_nonzero(tile_logits.grad).item() == 0


def test_hand_permutation_preserves_loss_and_metrics() -> None:
    torch.manual_seed(2)
    decision_logits = torch.randn(3, 3)
    card_logits = torch.randn(3, NUM_HAND_SLOTS)
    tile_logits = torch.randn(3, NUM_HAND_SLOTS, NUM_TILES)
    actions = torch.tensor([0 * NUM_TILES + 12, 2 * NUM_TILES + 100, 3 * NUM_TILES + 300])
    trusted = torch.ones(3, dtype=torch.bool)
    labels = labels_from_flat_actions(
        actions,
        decision_trusted=trusted,
        card_trusted=trusted,
        tile_trusted=trusted,
    )
    flat_mask = _public_mask(3)
    masks = factor_public_action_mask(flat_mask)
    original = hierarchical_masked_imitation_loss(
        decision_logits, card_logits, tile_logits, masks, labels
    )
    original_metrics = hierarchical_imitation_metric_sums(
        decision_logits, card_logits, tile_logits, masks, labels
    )

    permutation = torch.tensor([2, 0, 3, 1])
    inverse = torch.empty_like(permutation)
    inverse[permutation] = torch.arange(NUM_HAND_SLOTS)
    permuted_labels = replace(labels, card_target=inverse[labels.card_target])
    permuted_masks = replace(
        masks,
        card=masks.card.index_select(1, permutation),
        tile=masks.tile.index_select(1, permutation),
    )
    permuted = hierarchical_masked_imitation_loss(
        decision_logits,
        card_logits.index_select(1, permutation),
        tile_logits.index_select(1, permutation),
        permuted_masks,
        permuted_labels,
    )
    permuted_metrics = hierarchical_imitation_metric_sums(
        decision_logits,
        card_logits.index_select(1, permutation),
        tile_logits.index_select(1, permutation),
        permuted_masks,
        permuted_labels,
    )
    torch.testing.assert_close(original.total, permuted.total)
    assert {key: value.item() for key, value in original_metrics.items()} == {
        key: value.item() for key, value in permuted_metrics.items()
    }


def test_labels_cannot_change_or_mutate_public_masks() -> None:
    flat_mask = _public_mask(2)
    flat_before = flat_mask.clone()
    masks = factor_public_action_mask(flat_mask)
    masks_before = (masks.decision.clone(), masks.card.clone(), masks.tile.clone())
    wait_labels = labels_from_flat_actions(
        torch.tensor([NUM_HAND_SLOTS * NUM_TILES, NUM_HAND_SLOTS * NUM_TILES]),
        decision_trusted=torch.ones(2, dtype=torch.bool),
        card_trusted=torch.zeros(2, dtype=torch.bool),
        tile_trusted=torch.zeros(2, dtype=torch.bool),
    )
    ability_labels = labels_from_flat_actions(
        torch.tensor([ABILITY_ACTION, ABILITY_ACTION]),
        decision_trusted=torch.ones(2, dtype=torch.bool),
        card_trusted=torch.zeros(2, dtype=torch.bool),
        tile_trusted=torch.zeros(2, dtype=torch.bool),
    )
    logits = (torch.randn(2, 3), torch.randn(2, 4), torch.randn(2, 4, NUM_TILES))
    hierarchical_masked_imitation_loss(*logits, masks, wait_labels)
    hierarchical_masked_imitation_loss(*logits, masks, ability_labels)
    assert torch.equal(flat_mask, flat_before)
    assert torch.equal(masks.decision, masks_before[0])
    assert torch.equal(masks.card, masks_before[1])
    assert torch.equal(masks.tile, masks_before[2])


def test_invalid_trust_relationships_and_illegal_targets_fail_closed() -> None:
    masks = factor_public_action_mask(_public_mask(1))
    logits = (torch.randn(1, 3), torch.randn(1, 4), torch.randn(1, 4, NUM_TILES))
    base = HierarchicalImitationLabels(
        decision_target=torch.tensor([UNKNOWN_LABEL]),
        decision_trusted=torch.tensor([False]),
        card_target=torch.tensor([UNKNOWN_LABEL]),
        card_trusted=torch.tensor([False]),
        tile_target=torch.tensor([UNKNOWN_LABEL]),
        tile_trusted=torch.tensor([False]),
    )
    with pytest.raises(ValueError, match="untrusted decision"):
        hierarchical_masked_imitation_loss(
            *logits, masks, replace(base, decision_target=torch.tensor([WAIT_DECISION]))
        )
    with pytest.raises(ValueError, match="trusted card identity requires a trusted decision"):
        hierarchical_masked_imitation_loss(
            *logits,
            masks,
            replace(base, card_target=torch.tensor([0]), card_trusted=torch.tensor([True])),
        )
    play = replace(
        base,
        decision_target=torch.tensor([PLAY_DECISION]),
        decision_trusted=torch.tensor([True]),
        card_target=torch.tensor([0]),
        card_trusted=torch.tensor([True]),
        tile_target=torch.tensor([7]),
        tile_trusted=torch.tensor([True]),
    )
    with pytest.raises(ValueError, match="tile target is not public-legal"):
        hierarchical_masked_imitation_loss(*logits, masks, play)

    inconsistent_masks = replace(masks, card=torch.zeros_like(masks.card))
    with pytest.raises(ValueError, match="card mask must equal"):
        hierarchical_masked_imitation_loss(*logits, inconsistent_masks, base)


def test_tiny_batch_backpropagates_through_every_supervised_head() -> None:
    torch.manual_seed(3)
    decision_logits = torch.randn(3, 3, requires_grad=True)
    card_logits = torch.randn(3, 4, requires_grad=True)
    tile_logits = torch.randn(3, 4, NUM_TILES, requires_grad=True)
    actions = torch.tensor([11, NUM_TILES + 80, ABILITY_ACTION])
    labels = labels_from_flat_actions(
        actions,
        decision_trusted=torch.ones(3, dtype=torch.bool),
        card_trusted=torch.tensor([True, True, False]),
        tile_trusted=torch.tensor([True, True, False]),
    )
    loss = hierarchical_masked_imitation_loss(
        decision_logits,
        card_logits,
        tile_logits,
        factor_public_action_mask(_public_mask(3)),
        labels,
    )
    loss.total.backward()
    for gradient in (decision_logits.grad, card_logits.grad, tile_logits.grad):
        assert gradient is not None
        assert torch.isfinite(gradient).all()
        assert torch.count_nonzero(gradient).item() > 0
