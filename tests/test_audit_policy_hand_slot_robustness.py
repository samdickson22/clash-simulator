from __future__ import annotations

import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import PolicyInputs
from scripts.audit_policy_hand_slot_robustness import permute_current_hand_slots


def _inputs() -> PolicyInputs:
    batch = 1
    sequence = 1
    action_mask = torch.zeros(
        batch, sequence, NUM_HAND_SLOTS * NUM_TILES + 2, dtype=torch.bool
    )
    for slot in range(NUM_HAND_SLOTS):
        action_mask[0, 0, slot * NUM_TILES + slot] = True
    return PolicyInputs(
        entity_ids=torch.tensor([[[1, 2]]]),
        entity_features=torch.zeros(batch, sequence, 2, 3),
        entity_mask=torch.ones(batch, sequence, 2, dtype=torch.bool),
        hand_ids=torch.tensor([[[10, 11, 12, 13, 14]]]),
        global_features=torch.zeros(batch, sequence, 2),
        action_mask=action_mask,
        previous_actions=torch.tensor([[3 * NUM_TILES + 9]]),
        previous_rewards=torch.zeros(batch, sequence),
        episode_starts=torch.zeros(batch, sequence, dtype=torch.bool),
        hand_id_confidence=torch.tensor([[[0.1, 0.2, 0.3, 0.4, 0.5]]]),
        critic_card_ids=torch.tensor([[[10, 11, 12, 13, 14, 20, 21]]]),
    )


def test_current_hand_permutation_updates_only_matching_slot_axes() -> None:
    inputs = _inputs()
    orders = torch.tensor([[2, 0, 3, 1], [3, 2, 1, 0]])

    actual = permute_current_hand_slots(inputs, orders)

    assert actual.hand_ids.tolist() == [
        [[12, 10, 13, 11, 14]],
        [[13, 12, 11, 10, 14]],
    ]
    assert actual.hand_id_confidence is not None
    torch.testing.assert_close(
        actual.hand_id_confidence,
        torch.tensor([[[0.3, 0.1, 0.4, 0.2, 0.5]], [[0.4, 0.3, 0.2, 0.1, 0.5]]]),
    )
    assert actual.critic_card_ids is not None
    assert actual.critic_card_ids.tolist() == [
        [[12, 10, 13, 11, 14, 20, 21]],
        [[13, 12, 11, 10, 14, 20, 21]],
    ]
    legal_tiles = (
        actual.action_mask[:, 0, : NUM_HAND_SLOTS * NUM_TILES]
        .reshape(2, NUM_HAND_SLOTS, NUM_TILES)
        .to(torch.int64)
        .argmax(dim=-1)
    )
    assert legal_tiles.tolist() == [[2, 0, 3, 1], [3, 2, 1, 0]]
    assert actual.previous_actions.tolist() == [[3 * NUM_TILES + 9]] * 2


def test_current_hand_permutation_rejects_invalid_orders() -> None:
    inputs = _inputs()
    invalid = torch.tensor([[0, 0, 1, 2]])

    try:
        permute_current_hand_slots(inputs, invalid)
    except ValueError as error:
        assert "permutation" in str(error)
    else:  # pragma: no cover - explicit fail path
        raise AssertionError("invalid hand order was accepted")
