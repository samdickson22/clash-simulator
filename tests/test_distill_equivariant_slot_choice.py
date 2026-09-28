from __future__ import annotations

import itertools
from dataclasses import fields

import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import PolicyInputs
from scripts.distill_equivariant_slot_choice import (
    canonicalize_permuted_slot_probabilities,
    conditional_slot_probabilities,
    permute_current_hand_batch,
    repeat_state_for_permutations,
    time_slice,
)


def _inputs() -> PolicyInputs:
    batch = 2
    sequence = 2
    actions = NUM_HAND_SLOTS * NUM_TILES + 2
    masks = torch.zeros((batch, sequence, actions), dtype=torch.bool)
    for row in range(batch):
        for step in range(sequence):
            for slot in range(NUM_HAND_SLOTS):
                masks[row, step, slot * NUM_TILES + row + step + slot] = True
            masks[row, step, -2] = True
    return PolicyInputs(
        entity_ids=torch.ones((batch, sequence, 3), dtype=torch.long),
        entity_features=torch.zeros((batch, sequence, 3, 32)),
        entity_mask=torch.ones((batch, sequence, 3), dtype=torch.bool),
        hand_ids=torch.tensor(
            [
                [[10, 11, 12, 13, 14], [20, 21, 22, 23, 24]],
                [[30, 31, 32, 33, 34], [40, 41, 42, 43, 44]],
            ]
        ),
        global_features=torch.zeros((batch, sequence, 18)),
        action_mask=masks,
        previous_actions=torch.zeros((batch, sequence), dtype=torch.long),
        previous_rewards=torch.zeros((batch, sequence)),
        episode_starts=torch.zeros((batch, sequence), dtype=torch.bool),
        hand_id_confidence=torch.tensor(
            [
                [[0.1, 0.2, 0.3, 0.4, 0.5], [0.5, 0.6, 0.7, 0.8, 0.9]],
                [[0.9, 0.8, 0.7, 0.6, 0.5], [0.4, 0.3, 0.2, 0.1, 0.0]],
            ]
        ),
        critic_card_ids=torch.tensor(
            [
                [[110, 111, 112, 113, 114], [120, 121, 122, 123, 124]],
                [[130, 131, 132, 133, 134], [140, 141, 142, 143, 144]],
            ]
        ),
    )


def test_time_slice_preserves_every_optional_policy_field() -> None:
    inputs = _inputs()

    selected = time_slice(inputs, 1)

    for field in fields(PolicyInputs):
        expected = getattr(inputs, field.name)
        actual = getattr(selected, field.name)
        if expected is None:
            assert actual is None
        else:
            torch.testing.assert_close(actual, expected[:, 1:2])


def test_batch_permutation_moves_hand_mask_confidence_and_critic_together() -> None:
    inputs = time_slice(_inputs(), 0)
    orders = torch.tensor([[0, 1, 2, 3], [2, 0, 3, 1]])

    actual = permute_current_hand_batch(inputs, orders)

    assert actual.hand_ids[:, 0].tolist() == [
        [10, 11, 12, 13, 14],
        [12, 10, 13, 11, 14],
        [30, 31, 32, 33, 34],
        [32, 30, 33, 31, 34],
    ]
    assert actual.hand_id_confidence is not None
    torch.testing.assert_close(
        actual.hand_id_confidence[:, 0, :4],
        torch.tensor(
            [
                [0.1, 0.2, 0.3, 0.4],
                [0.3, 0.1, 0.4, 0.2],
                [0.9, 0.8, 0.7, 0.6],
                [0.7, 0.9, 0.6, 0.8],
            ]
        ),
    )
    assert actual.critic_card_ids is not None
    assert actual.critic_card_ids[:, 0, :4].tolist() == [
        [110, 111, 112, 113],
        [112, 110, 113, 111],
        [130, 131, 132, 133],
        [132, 130, 133, 131],
    ]
    placement = actual.action_mask[:, 0, :-2].reshape(-1, 4, NUM_TILES)
    assert placement[1].nonzero().tolist() == [
        [0, 2],
        [1, 0],
        [2, 3],
        [3, 1],
    ]


def test_canonicalization_exactly_removes_physical_slot_permutations() -> None:
    orders = torch.tensor(list(itertools.permutations(range(4))))
    canonical = torch.tensor([[0.05, 0.15, 0.30, 0.50], [0.4, 0.3, 0.2, 0.1]])
    physical = canonical[:, orders]

    restored = canonicalize_permuted_slot_probabilities(physical, orders)

    torch.testing.assert_close(
        restored,
        canonical[:, None, :].expand_as(restored),
    )
    torch.testing.assert_close(restored.mean(dim=1), canonical)


def test_conditional_probabilities_ignore_illegal_slots() -> None:
    logits = torch.tensor([[1.0, 100.0, 3.0, -9.0]])
    legal = torch.tensor([[True, False, True, False]])

    actual = conditional_slot_probabilities(logits, legal, temperature=2.0)

    expected = torch.softmax(torch.tensor([[0.5, 1.5]]), dim=-1)
    torch.testing.assert_close(actual[:, [0, 2]], expected)
    assert actual[:, [1, 3]].count_nonzero() == 0


def test_repeat_state_uses_batch_major_permutation_order() -> None:
    state = (torch.tensor([[1.0], [2.0]]), torch.tensor([[3.0], [4.0]]))

    hidden, cell = repeat_state_for_permutations(state, 3)

    assert hidden.flatten().tolist() == [1.0, 1.0, 1.0, 2.0, 2.0, 2.0]
    assert cell.flatten().tolist() == [3.0, 3.0, 3.0, 4.0, 4.0, 4.0]
