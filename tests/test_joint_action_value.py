from __future__ import annotations

import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.joint_action_value import (
    NUM_ACTIONS,
    FactorizedActionValueHead,
)


def _permute_slot_blocks(
    values: torch.Tensor, permutation: torch.Tensor
) -> torch.Tensor:
    placements = values[..., : NUM_HAND_SLOTS * NUM_TILES].reshape(
        *values.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
    )
    return torch.cat(
        [
            placements.index_select(-2, permutation).reshape(*values.shape[:-1], -1),
            values[..., NUM_HAND_SLOTS * NUM_TILES :],
        ],
        dim=-1,
    )


def test_action_values_are_exactly_slot_equivariant() -> None:
    torch.manual_seed(71)
    head = FactorizedActionValueHead(state_size=7, d_model=5)
    state = torch.randn(3, 7)
    cards = torch.randn(3, NUM_HAND_SLOTS, 5)
    tiles = torch.randn(3, NUM_TILES, 5)
    mask = torch.rand(3, NUM_ACTIONS) > 0.2
    mask[:, -2] = True
    permutation = torch.tensor([2, 0, 3, 1])

    control = head(state, cards, tiles, mask)
    permuted = head(
        state,
        cards.index_select(1, permutation),
        tiles,
        _permute_slot_blocks(mask, permutation),
    )

    assert torch.equal(permuted, _permute_slot_blocks(control, permutation))


def test_action_values_mask_illegal_actions_and_train_selected_values() -> None:
    head = FactorizedActionValueHead(state_size=6, d_model=4)
    state = torch.randn(2, 6)
    cards = torch.randn(2, NUM_HAND_SLOTS, 4)
    tiles = torch.randn(2, NUM_TILES, 4)
    mask = torch.zeros(2, NUM_ACTIONS, dtype=torch.bool)
    mask[0, 17] = True
    mask[1, -2] = True
    values = head(state, cards, tiles, mask)
    assert torch.isneginf(values[0, 18])
    selected = head.selected_values(values, torch.tensor([17, NUM_ACTIONS - 2]))
    assert bool(torch.isfinite(selected).all())
    selected.square().mean().backward()
    assert all(parameter.grad is not None for parameter in head.parameters())


def test_action_value_parameter_budget_is_small() -> None:
    head = FactorizedActionValueHead(state_size=192, d_model=128)
    assert sum(parameter.numel() for parameter in head.parameters()) < 70_000
