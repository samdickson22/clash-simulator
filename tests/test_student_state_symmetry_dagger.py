from __future__ import annotations

import itertools

import numpy as np
import pytest
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import PolicyInputs, PolicyOutput
from scripts.train_student_state_symmetry_dagger import (
    NUM_ACTIONS,
    canonicalize_permuted_joint_probabilities,
    episode_sequences,
    soft_cross_entropy,
    soft_kl,
    symmetrized_teacher_step,
)


def test_joint_canonicalization_moves_tiles_and_preserves_special_actions() -> None:
    orders = torch.tensor([[0, 1, 2, 3], [2, 0, 3, 1]])
    probabilities = torch.zeros((1, 2, NUM_ACTIONS))
    for permutation in range(2):
        for physical_slot in range(NUM_HAND_SLOTS):
            probabilities[
                0,
                permutation,
                physical_slot * NUM_TILES + physical_slot,
            ] = 10 * permutation + physical_slot + 1
    probabilities[0, :, -2:] = torch.tensor([[101.0, 102.0], [201.0, 202.0]])

    actual = canonicalize_permuted_joint_probabilities(probabilities, orders)
    placements = actual[..., :-2].reshape(1, 2, NUM_HAND_SLOTS, NUM_TILES)

    assert placements[0, 0].nonzero().tolist() == [
        [0, 0],
        [1, 1],
        [2, 2],
        [3, 3],
    ]
    assert placements[0, 1].nonzero().tolist() == [
        [0, 1],
        [1, 3],
        [2, 0],
        [3, 2],
    ]
    torch.testing.assert_close(actual[0, :, -2:], probabilities[0, :, -2:])


def test_episode_sequences_require_complete_contiguous_episode_partitions() -> None:
    episode_ids = np.asarray([0, 0, 1, 1, 1, 2], dtype=np.int64)

    actual = episode_sequences(episode_ids, np.asarray([2, 3, 4, 5]))

    assert [rows.tolist() for rows in actual] == [[2, 3, 4], [5]]
    with pytest.raises(ValueError, match="whole episodes"):
        episode_sequences(episode_ids, np.asarray([0, 2, 3, 4]))


def test_soft_losses_ignore_zero_mass_at_negative_infinity() -> None:
    target = torch.tensor([[0.75, 0.25, 0.0]])
    log_probabilities = torch.tensor([[np.log(0.5), np.log(0.5), -torch.inf]])

    cross_entropy = soft_cross_entropy(target, log_probabilities)
    divergence = soft_kl(target, log_probabilities)

    torch.testing.assert_close(cross_entropy, torch.tensor([np.log(2.0)]))
    expected_kl = 0.75 * np.log(0.75 / 0.5) + 0.25 * np.log(0.25 / 0.5)
    torch.testing.assert_close(divergence, torch.tensor([expected_kl]))


class _PhysicalSlotTeacher:
    def __call__(
        self,
        inputs: PolicyInputs,
        state: tuple[torch.Tensor, torch.Tensor],
    ) -> PolicyOutput:
        batch = inputs.batch_size
        logits = torch.full((batch, 1, NUM_ACTIONS), -100.0)
        for slot in range(NUM_HAND_SLOTS):
            logits[:, 0, slot * NUM_TILES] = float(slot)
        logits[:, 0, -2] = -10.0
        logits[:, 0, -1] = -100.0
        action_types = torch.zeros((batch, 1, NUM_HAND_SLOTS + 2))
        locations = torch.zeros((batch, 1, NUM_HAND_SLOTS, NUM_TILES))
        return PolicyOutput(
            joint_logits=logits,
            values=torch.zeros((batch, 1)),
            opponent_hand_logits=torch.zeros((batch, 1, 1)),
            opponent_elixir=torch.zeros((batch, 1)),
            next_state=(state[0] + 1.0, state[1] + 2.0),
            action_type_logits=action_types,
            location_logits=locations,
        )


def _inputs() -> PolicyInputs:
    mask = torch.zeros((1, 1, NUM_ACTIONS), dtype=torch.bool)
    for slot in range(NUM_HAND_SLOTS):
        mask[0, 0, slot * NUM_TILES] = True
    mask[0, 0, -2] = True
    return PolicyInputs(
        entity_ids=torch.ones((1, 1, 1), dtype=torch.long),
        entity_features=torch.zeros((1, 1, 1, 32)),
        entity_mask=torch.ones((1, 1, 1), dtype=torch.bool),
        hand_ids=torch.tensor([[[10, 11, 12, 13, 14]]]),
        global_features=torch.zeros((1, 1, 18)),
        action_mask=mask,
        previous_actions=torch.full((1, 1), NUM_ACTIONS - 2, dtype=torch.long),
        previous_rewards=torch.zeros((1, 1)),
        episode_starts=torch.ones((1, 1), dtype=torch.bool),
    )


def test_all_permutation_teacher_removes_pure_physical_slot_preference() -> None:
    teacher = _PhysicalSlotTeacher()
    state = (torch.zeros((1, 3)), torch.zeros((1, 3)))

    symmetrized, original, next_state = symmetrized_teacher_step(  # type: ignore[arg-type]
        teacher,
        _inputs(),
        state,
        temperature=1.0,
        orders=torch.tensor(list(itertools.permutations(range(NUM_HAND_SLOTS)))),
    )

    placement_mass = symmetrized[0, :-2].reshape(NUM_HAND_SLOTS, NUM_TILES).sum(-1)
    torch.testing.assert_close(
        placement_mass,
        placement_mass.mean().expand_as(placement_mass),
        atol=1e-6,
        rtol=1e-6,
    )
    assert not torch.allclose(
        original[0, :-2].reshape(NUM_HAND_SLOTS, NUM_TILES).sum(-1),
        placement_mass,
    )
    torch.testing.assert_close(next_state[0], torch.ones_like(state[0]))
    torch.testing.assert_close(next_state[1], torch.full_like(state[1], 2.0))
    torch.testing.assert_close(symmetrized.sum(-1), torch.ones(1))
