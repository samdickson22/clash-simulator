import json
from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl import imitation as imitation_module
from clasher.rl.imitation import (
    CorpusMetadata,
    collect_oracle_corpus,
    conditional_slot_choice_loss,
    defensive_context_weights,
    expert_action_type_balance_weights,
    expert_card_balance_weights,
    expert_decision_balance_weights,
    fit_imitation_corpus,
    imitation_supervision_mask,
    informative_indices,
    load_corpus,
    load_public_observation_sidecar,
    mirror_imitation_batch,
    permute_hand_imitation_batch,
    sequence_chunks,
    split_indices,
)
from clasher.rl.public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from clasher.rl.public_observation import (
    REAL_PLAY_ENTITY_FEATURE_INDICES,
    REAL_PLAY_GLOBAL_FEATURE_INDICES,
)


def test_corpus_metadata_roundtrips_checkpoint_teacher_provenance() -> None:
    metadata = CorpusMetadata(
        schema_version=1,
        created_at="2026-08-28T00:00:00+00:00",
        seed=7,
        decisions=2,
        samples=2,
        decision_interval=8,
        max_ticks=6000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=48,
        token_names=("<pad>", "<unknown>"),
        label_source="checkpoint",
        label_checkpoint="teacher.pt",
        label_checkpoint_sha256="a" * 64,
    )

    assert CorpusMetadata.from_json(metadata.to_json()) == metadata


def test_defensive_context_weights_only_public_near_enemy_units():
    features = np.zeros((4, 2, 32), dtype=np.float32)
    mask = np.zeros((4, 2), dtype=np.bool_)
    mask[:, 0] = True
    features[:, 0, 3] = 1.0  # enemy
    features[:, 0, 4] = 1.0  # troop
    features[:, 0, 1] = np.asarray([0.20, 0.30, 0.20, 0.20])
    features[2, 0, 3] = 0.0  # friendly
    features[3, 0, 31] = 1.0  # Crown Tower, never a pressure unit

    weights = defensive_context_weights(
        features,
        mask,
        context_weight=4.0,
        maximum_canonical_y=0.25,
    )

    assert weights.tolist() == [4.0, 1.0, 1.0, 1.0]
    with pytest.raises(ValueError, match="at least one"):
        defensive_context_weights(
            features,
            mask,
            context_weight=0.5,
            maximum_canonical_y=0.25,
        )


def test_expert_action_type_balance_weights_use_training_frequencies_only():
    noop = 4 * 18 * 32
    actions = np.asarray([0, 0, 0, noop, noop, noop, noop, noop + 1], dtype=np.int64)
    training = np.arange(7, dtype=np.int64)

    weights = expert_action_type_balance_weights(
        actions,
        training,
        power=0.5,
        max_weight=3.0,
    )

    assert weights[0] > weights[3]
    assert float(weights[training].mean()) == pytest.approx(1.0)
    assert weights[-1] > weights[3]
    changed = actions.copy()
    changed[-1] = 2 * 18 * 32
    changed_weights = expert_action_type_balance_weights(
        changed,
        training,
        power=0.5,
        max_weight=3.0,
    )
    np.testing.assert_allclose(changed_weights[training], weights[training])


def test_hierarchical_decision_weights_balance_play_as_one_class() -> None:
    noop = 4 * 18 * 32
    actions = np.asarray([0, noop, noop, noop, noop, noop], dtype=np.int64)
    training = np.arange(len(actions), dtype=np.int64)

    weights = expert_decision_balance_weights(
        actions,
        training,
        power=1.0,
        max_weight=8.0,
    )

    assert weights[:1].sum() == pytest.approx(weights[1:].sum())
    assert float(weights.mean()) == pytest.approx(1.0)


def test_expert_card_balance_weights_are_clipped_and_training_only():
    noop = 4 * 18 * 32
    hand_ids = np.asarray(
        [
            [1, 2, 3, 4, 0],
            [1, 2, 3, 4, 0],
            [1, 2, 3, 4, 0],
            [1, 2, 3, 4, 0],
            [1, 9, 3, 4, 0],
            [8, 2, 3, 4, 0],
        ],
        dtype=np.int64,
    )
    actions = np.asarray([0, 0, 0, 0, 18 * 32, noop], dtype=np.int64)
    training = np.asarray([0, 1, 2, 3, 4], dtype=np.int64)

    weights = expert_card_balance_weights(
        hand_ids,
        actions,
        training,
        power=0.5,
        max_weight=2.0,
    )

    assert weights[4] > weights[0]
    assert weights[5] == 1.0
    assert float(weights[:5].mean()) == pytest.approx(1.0)
    assert float(weights.max()) <= 2.0

    changed = hand_ids.copy()
    changed[5, 0] = 99
    changed_weights = expert_card_balance_weights(
        changed,
        actions,
        training,
        power=0.5,
        max_weight=2.0,
    )
    np.testing.assert_allclose(changed_weights[:5], weights[:5])
from clasher.rl.model import PolicyInputs
from clasher.rl.oracle_corpus import manifest_path


def test_split_indices_is_reproducible_and_disjoint():
    episode_ids = np.asarray([0, 0, 1, 1, 2, 2], dtype=np.int64)
    train_a, validation_a = split_indices(episode_ids, validation_fraction=0.33, seed=7)
    train_b, validation_b = split_indices(episode_ids, validation_fraction=0.33, seed=7)

    assert np.array_equal(train_a, train_b)
    assert np.array_equal(validation_a, validation_b)
    assert not set(train_a).intersection(validation_a)
    assert set(episode_ids[train_a]).isdisjoint(set(episode_ids[validation_a]))


def test_informative_indices_exclude_single_legal_action_rows():
    masks = np.asarray(
        [
            [False, False, True],
            [True, False, True],
            [False, True, True],
        ],
        dtype=np.bool_,
    )

    assert informative_indices(masks).tolist() == [1, 2]


def test_placement_only_supervision_keeps_only_informative_deployments():
    noop = 4 * 18 * 32
    masks = np.zeros((3, noop + 2), dtype=np.bool_)
    masks[0, noop] = True
    masks[1, [0, noop]] = True
    masks[2, [0, 1, noop]] = True
    actions = np.asarray([noop, noop, 1], dtype=np.int64)

    selected = imitation_supervision_mask(
        masks,
        actions,
        train_on_forced_actions=False,
        placement_actions_only=True,
    )

    assert selected.tolist() == [False, False, True]


def test_conditional_slot_choice_loss_ignores_special_logits_and_illegal_slots():
    noop = 4 * 18 * 32
    action_mask = torch.zeros((2, noop + 2), dtype=torch.bool)
    action_mask[0, [0, 2 * 18 * 32, noop]] = True
    action_mask[1, [18 * 32, 3 * 18 * 32, noop]] = True
    type_logits = torch.tensor(
        [[1.0, 100.0, 3.0, -100.0, -9.0, 12.0], [99.0, 2.0, -8.0, 4.0, 8.0, -7.0]]
    )
    targets = torch.tensor([2 * 18 * 32, 3 * 18 * 32])

    loss = conditional_slot_choice_loss(
        type_logits,
        targets,
        action_mask,
        reduction="none",
    )

    expected = torch.stack(
        [
            torch.nn.functional.cross_entropy(
                torch.tensor([[1.0, 3.0]]), torch.tensor([1])
            ),
            torch.nn.functional.cross_entropy(
                torch.tensor([[2.0, 4.0]]), torch.tensor([1])
            ),
        ]
    )
    torch.testing.assert_close(loss, expected)


def test_sequence_chunks_preserve_episode_order_and_drop_short_tails():
    episode_ids = np.asarray([0, 0, 0, 1, 1, 1, 1, 1], dtype=np.int64)
    indices = np.arange(len(episode_ids), dtype=np.int64)

    chunks = sequence_chunks(episode_ids, indices, sequence_length=2)

    assert chunks.tolist() == [[0, 1], [3, 4], [5, 6]]
    assert all(len(set(episode_ids[chunk])) == 1 for chunk in chunks)


def test_sequence_batch_inputs_can_trim_packed_entity_padding_before_transfer():
    arrays = {
        "entity_ids": np.arange(8, dtype=np.int64).reshape(2, 4),
        "entity_features": np.zeros((2, 4, 32), dtype=np.float32),
        "entity_mask": np.asarray(
            [[True, True, False, False], [True, False, False, False]],
            dtype=np.bool_,
        ),
        "hand_ids": np.ones((2, 5), dtype=np.int64),
        "global_features": np.zeros((2, 18), dtype=np.float32),
        "action_masks": np.ones((2, 2306), dtype=np.bool_),
        "previous_actions": np.zeros(2, dtype=np.int64),
        "previous_rewards": np.zeros(2, dtype=np.float32),
        "episode_starts": np.zeros(2, dtype=np.bool_),
        "entity_id_confidence": np.ones((2, 4), dtype=np.float16),
        "entity_feature_confidence": np.ones((2, 4, 32), dtype=np.float16),
        "hand_id_confidence": np.ones((2, 5), dtype=np.float16),
        "global_feature_confidence": np.ones((2, 18), dtype=np.float16),
    }
    chunks = np.asarray([[0, 1]], dtype=np.int64)

    full = imitation_module._sequence_batch_inputs(
        arrays, chunks, torch.device("cpu")
    )
    trimmed = imitation_module._sequence_batch_inputs(
        arrays,
        chunks,
        torch.device("cpu"),
        trim_entity_padding=True,
    )

    assert full.entity_ids.shape == (1, 2, 4)
    assert trimmed.entity_ids.shape == (1, 2, 2)
    assert trimmed.entity_ids.equal(full.entity_ids[..., :2])
    assert trimmed.entity_features.equal(full.entity_features[..., :2, :])
    assert trimmed.entity_mask.equal(full.entity_mask[..., :2])
    assert trimmed.entity_id_confidence is not None
    assert trimmed.entity_feature_confidence is not None
    assert trimmed.entity_id_confidence.equal(full.entity_id_confidence[..., :2])
    assert trimmed.entity_feature_confidence.equal(
        full.entity_feature_confidence[..., :2, :]
    )

    flat_full = imitation_module._batch_inputs(
        arrays, np.asarray([0, 1]), torch.device("cpu")
    )
    flat_trimmed = imitation_module._batch_inputs(
        arrays,
        np.asarray([0, 1]),
        torch.device("cpu"),
        trim_entity_padding=True,
    )
    assert flat_full.entity_ids.shape == (2, 1, 4)
    assert flat_trimmed.entity_ids.shape == (2, 1, 2)
    assert flat_trimmed.entity_ids.equal(flat_full.entity_ids[..., :2])
    assert flat_trimmed.entity_id_confidence is not None
    assert flat_trimmed.entity_feature_confidence is not None
    assert flat_trimmed.entity_id_confidence.equal(
        flat_full.entity_id_confidence[..., :2]
    )
    assert flat_trimmed.entity_feature_confidence.equal(
        flat_full.entity_feature_confidence[..., :2, :]
    )


def test_public_observation_sidecar_is_aligned_and_fail_closed(tmp_path: Path):
    samples = 2
    base = {
        "entity_ids": np.ones((samples, 3), dtype=np.int64),
        "entity_features": np.ones((samples, 3, 32), dtype=np.float32),
        "entity_mask": np.ones((samples, 3), dtype=np.bool_),
        "hand_ids": np.ones((samples, 5), dtype=np.int64),
        "global_features": np.ones((samples, 18), dtype=np.float32),
        "action_masks": np.ones((samples, 2306), dtype=np.bool_),
        "expert_action_masked": np.zeros((samples,), dtype=np.bool_),
        "previous_rewards": np.asarray([0.5, -0.25], dtype=np.float32),
        "expert_actions": np.asarray([7, 8], dtype=np.int64),
        "episode_ids": np.asarray([0, 1], dtype=np.int64),
    }
    public_values = {
        "entity_ids": np.full((samples, 3), 2, dtype=np.int64),
        "entity_features": np.zeros((samples, 3, 32), dtype=np.float32),
        "entity_mask": np.ones((samples, 3), dtype=np.bool_),
        "entity_id_confidence": np.full((samples, 3), 0.8, dtype=np.float16),
        "entity_feature_confidence": np.zeros(
            (samples, 3, 32), dtype=np.float16
        ),
        "hand_ids": np.full((samples, 5), 2, dtype=np.int64),
        "hand_id_confidence": np.ones((samples, 5), dtype=np.float16),
        "global_features": np.zeros((samples, 18), dtype=np.float32),
        "global_feature_confidence": np.zeros(
            (samples, 18), dtype=np.float16
        ),
        "action_masks": np.ones((samples, 2306), dtype=np.bool_),
        "expert_action_masked": np.zeros((samples,), dtype=np.bool_),
        "expert_actions": base["expert_actions"],
        "episode_ids": base["episode_ids"],
        "schema_version": np.asarray(2),
        "action_mask_contract_version": np.asarray(
            PUBLIC_ACTION_MASK_CONTRACT_VERSION
        ),
    }
    public_values["entity_feature_confidence"][..., 0:2] = 0.7
    public_values["global_feature_confidence"][..., 0:6] = 0.6
    public_values["hand_ids"][..., 4] = 3
    public_values["hand_id_confidence"][..., 4] = 0.75
    sidecar = tmp_path / "public_v2.npz"
    np.savez(sidecar, **public_values)

    merged = load_public_observation_sidecar(sidecar, base_arrays=base)

    assert np.array_equal(merged["entity_ids"], public_values["entity_ids"])
    assert np.array_equal(merged["hand_ids"], public_values["hand_ids"])
    assert np.array_equal(
        merged["hand_id_confidence"], public_values["hand_id_confidence"]
    )
    assert np.array_equal(merged["expert_actions"], base["expert_actions"])
    assert "entity_id_confidence" in merged
    assert merged["previous_rewards"].tolist() == [0.0, 0.0]

    missing_masks = dict(public_values)
    del missing_masks["action_masks"]
    np.savez(sidecar, **missing_masks)
    with pytest.raises(ValueError, match="missing arrays.*action_masks"):
        load_public_observation_sidecar(sidecar, base_arrays=base)

    unversioned = dict(public_values)
    del unversioned["action_mask_contract_version"]
    np.savez(sidecar, **unversioned)
    with pytest.raises(ValueError, match="label-independent action-mask contract"):
        load_public_observation_sidecar(sidecar, base_arrays=base)

    public_values["expert_actions"] = np.asarray([8, 7], dtype=np.int64)
    np.savez(sidecar, **public_values)
    with pytest.raises(ValueError, match="expert_actions is not aligned"):
        load_public_observation_sidecar(sidecar, base_arrays=base)


def test_public_observation_sidecar_overlays_its_causal_action_masks(
    tmp_path: Path,
) -> None:
    samples = 2
    expert_actions = np.asarray([7, 8], dtype=np.int64)
    base = {
        "entity_ids": np.ones((samples, 3), dtype=np.int64),
        "entity_features": np.ones((samples, 3, 32), dtype=np.float32),
        "entity_mask": np.ones((samples, 3), dtype=np.bool_),
        "hand_ids": np.ones((samples, 5), dtype=np.int64),
        "global_features": np.ones((samples, 18), dtype=np.float32),
        "action_masks": np.ones((samples, 2306), dtype=np.bool_),
        "previous_rewards": np.asarray([0.5, -0.25], dtype=np.float32),
        "expert_actions": expert_actions,
    }
    causal_masks = np.zeros((samples, 2306), dtype=np.bool_)
    causal_masks[:, 2304] = True
    causal_masks[np.arange(samples), expert_actions] = True
    sidecar_values = {
        "entity_ids": np.full((samples, 3), 2, dtype=np.int64),
        "entity_features": np.zeros((samples, 3, 32), dtype=np.float32),
        "entity_mask": np.ones((samples, 3), dtype=np.bool_),
        "entity_id_confidence": np.ones((samples, 3), dtype=np.float16),
        "entity_feature_confidence": np.zeros(
            (samples, 3, 32), dtype=np.float16
        ),
        "hand_ids": np.full((samples, 5), 2, dtype=np.int64),
        "hand_id_confidence": np.ones((samples, 5), dtype=np.float16),
        "global_features": np.zeros((samples, 18), dtype=np.float32),
        "global_feature_confidence": np.zeros(
            (samples, 18), dtype=np.float16
        ),
        "action_masks": causal_masks,
        "expert_action_masked": np.zeros((samples,), dtype=np.bool_),
        "expert_actions": expert_actions,
        "schema_version": np.asarray(2),
        "action_mask_contract_version": np.asarray(
            PUBLIC_ACTION_MASK_CONTRACT_VERSION
        ),
    }
    sidecar_values["entity_feature_confidence"][..., 0:2] = 1.0
    sidecar_values["global_feature_confidence"][..., 0:6] = 1.0
    sidecar_values["hand_ids"][..., 4:] = 0
    sidecar_values["hand_id_confidence"][..., 4:] = 0.0
    sidecar = tmp_path / "public_masks_v2.npz"
    np.savez(sidecar, **sidecar_values)

    merged = load_public_observation_sidecar(sidecar, base_arrays=base)

    assert np.array_equal(merged["action_masks"], causal_masks)

    sidecar_values["action_masks"] = causal_masks.copy()
    sidecar_values["action_masks"][0, expert_actions[0]] = False
    np.savez(sidecar, **sidecar_values)
    with pytest.raises(ValueError, match="expert_action_masked is inconsistent"):
        load_public_observation_sidecar(sidecar, base_arrays=base)

    sidecar_values["expert_action_masked"][0] = True
    np.savez(sidecar, **sidecar_values)
    masked = load_public_observation_sidecar(sidecar, base_arrays=base)
    assert masked["expert_action_supervision_valid"].tolist() == [False, True]

    sidecar_values["action_masks"][0, expert_actions[0]] = True
    sidecar_values["expert_action_masked"][0] = False
    sidecar_values["entity_features"][0, 0, 14] = 0.25
    sidecar_values["entity_feature_confidence"][0, 0, 14] = 1.0
    np.savez(sidecar, **sidecar_values)
    with pytest.raises(ValueError, match="exceeds real-play feature contract"):
        load_public_observation_sidecar(sidecar, base_arrays=base)


def test_mirror_imitation_batch_is_exact_and_involutive():
    action_count = 4 * 18 * 32 + 2
    noop = 4 * 18 * 32
    features = torch.zeros((2, 2, 3, 32), dtype=torch.float32)
    entity_mask = torch.tensor(
        [[[True, False, False], [True, False, False]]] * 2,
        dtype=torch.bool,
    )
    features[0, 0, 0, 0] = 0.25
    features[0, 1, 0, 0] = 0.75
    action_mask = torch.zeros((2, 2, action_count), dtype=torch.bool)
    action = 2 * (18 * 32) + 5 * 18 + 3
    mirrored_action = 2 * (18 * 32) + 5 * 18 + 14
    action_mask[0, :, action] = True
    action_mask[0, :, noop] = True
    action_mask[1, :, 7] = True
    previous_actions = torch.tensor([[action, noop], [7, noop]])
    inputs = PolicyInputs(
        entity_ids=torch.zeros((2, 2, 3), dtype=torch.long),
        entity_features=features,
        entity_mask=entity_mask,
        hand_ids=torch.zeros((2, 2, 5), dtype=torch.long),
        global_features=torch.zeros((2, 2, 18)),
        action_mask=action_mask,
        previous_actions=previous_actions,
        previous_rewards=torch.zeros((2, 2)),
        episode_starts=torch.zeros((2, 2), dtype=torch.bool),
    )
    targets = torch.tensor([[action, noop], [7, noop]])
    flip_rows = torch.tensor([True, False])

    mirrored_inputs, mirrored_targets = mirror_imitation_batch(
        inputs, targets, flip_rows
    )

    assert mirrored_inputs.entity_features[0, :, 0, 0].tolist() == [0.75, 0.25]
    assert mirrored_inputs.entity_features[1].equal(inputs.entity_features[1])
    assert mirrored_inputs.action_mask[0, :, mirrored_action].all()
    assert not mirrored_inputs.action_mask[0, :, action].any()
    assert mirrored_targets[0].tolist() == [mirrored_action, noop]
    assert mirrored_inputs.previous_actions[0].tolist() == [mirrored_action, noop]
    restored_inputs, restored_targets = mirror_imitation_batch(
        mirrored_inputs, mirrored_targets, flip_rows
    )
    assert restored_inputs.entity_features.equal(inputs.entity_features)
    assert restored_inputs.action_mask.equal(inputs.action_mask)
    assert restored_inputs.previous_actions.equal(inputs.previous_actions)
    assert restored_targets.equal(targets)


def test_hand_permutation_augmentation_relabels_complete_sequences_exactly():
    action_count = 4 * 18 * 32 + 2
    noop = 4 * 18 * 32
    slot_size = 18 * 32
    orders = torch.tensor([[2, 0, 3, 1], [0, 1, 2, 3]])
    hand_ids = torch.tensor(
        [
            [[10, 11, 12, 13, 14], [20, 21, 22, 23, 24]],
            [[30, 31, 32, 33, 34], [40, 41, 42, 43, 44]],
        ]
    )
    hand_confidence = hand_ids.to(torch.float32) / 100.0
    critic_cards = hand_ids.clone()
    first_action = 7
    second_action = 2 * slot_size + 9
    action_mask = torch.zeros((2, 2, action_count), dtype=torch.bool)
    action_mask[0, 0, first_action] = True
    action_mask[0, 0, noop] = True
    action_mask[0, 1, second_action] = True
    action_mask[0, 1, noop] = True
    action_mask[1, :, 3] = True
    action_mask[1, :, noop] = True
    targets = torch.tensor([[first_action, second_action], [3, noop]])
    inputs = PolicyInputs(
        entity_ids=torch.zeros((2, 2, 1), dtype=torch.long),
        entity_features=torch.zeros((2, 2, 1, 32)),
        entity_mask=torch.ones((2, 2, 1), dtype=torch.bool),
        hand_ids=hand_ids,
        global_features=torch.zeros((2, 2, 18)),
        action_mask=action_mask,
        previous_actions=targets.clone(),
        previous_rewards=torch.zeros((2, 2)),
        episode_starts=torch.zeros((2, 2), dtype=torch.bool),
        hand_id_confidence=hand_confidence,
        critic_card_ids=critic_cards,
    )

    permuted, permuted_targets = permute_hand_imitation_batch(
        inputs, targets, orders
    )

    assert permuted.hand_ids[0].tolist() == [
        [12, 10, 13, 11, 14],
        [22, 20, 23, 21, 24],
    ]
    assert permuted.hand_ids[1].equal(inputs.hand_ids[1])
    assert permuted.hand_id_confidence is not None
    assert permuted.hand_id_confidence[0, 0].tolist() == pytest.approx(
        [0.12, 0.10, 0.13, 0.11, 0.14]
    )
    assert permuted.critic_card_ids is not None
    assert permuted.critic_card_ids[0].equal(permuted.hand_ids[0])
    expected_first = slot_size + 7
    expected_second = 9
    assert permuted_targets[0].tolist() == [expected_first, expected_second]
    assert permuted.previous_actions[0].tolist() == [
        expected_first,
        expected_second,
    ]
    assert permuted.action_mask[0, 0, expected_first]
    assert permuted.action_mask[0, 1, expected_second]
    assert not permuted.action_mask[0, 0, first_action]

    inverse = torch.empty_like(orders)
    inverse.scatter_(1, orders, torch.arange(4)[None, :].expand_as(orders))
    restored, restored_targets = permute_hand_imitation_batch(
        permuted, permuted_targets, inverse
    )
    assert restored.hand_ids.equal(inputs.hand_ids)
    assert restored.action_mask.equal(inputs.action_mask)
    assert restored.previous_actions.equal(inputs.previous_actions)
    assert restored_targets.equal(targets)


def test_hand_permutation_probability_samples_identity_mixture_reproducibly():
    zero = imitation_module._sample_hand_permutation_orders(
        np.random.default_rng(101), batch_size=8, probability=0.0
    )
    assert zero.tolist() == [list(range(4))] * 8

    full = imitation_module._sample_hand_permutation_orders(
        np.random.default_rng(103), batch_size=8, probability=1.0
    )
    assert all(sorted(row.tolist()) == list(range(4)) for row in full)
    assert any(row.tolist() != list(range(4)) for row in full)

    first = imitation_module._sample_hand_permutation_orders(
        np.random.default_rng(107), batch_size=32, probability=0.25
    )
    second = imitation_module._sample_hand_permutation_orders(
        np.random.default_rng(107), batch_size=32, probability=0.25
    )
    assert np.array_equal(first, second)
    assert 0 < np.sum(np.any(first != np.arange(4), axis=1)) < len(first)

    with pytest.raises(ValueError, match="between zero and one"):
        imitation_module._sample_hand_permutation_orders(
            np.random.default_rng(109), batch_size=1, probability=1.1
        )


def test_fixed_corpus_builds_matched_v2_control_and_warm_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    corpus = tmp_path / "oracle_corpus.npz"
    sampling_decks = tmp_path / "sampling_decks.json"
    sampled_cards = [
        "Cannon",
        "Fireball",
        "HogRider",
        "IceGolem",
        "IceSpirit",
        "Musketeer",
        "Skeletons",
        "Log",
    ]
    sampling_decks.write_text(
        json.dumps({"decks": [{"name": "only", "cards": sampled_cards}]}),
        encoding="utf-8",
    )
    metadata = collect_oracle_corpus(
        output_path=corpus,
        decks_path=Path("decks.json").resolve(),
        sampling_decks_path=sampling_decks,
        decisions=2,
        seed=31,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
    )

    loaded_metadata, arrays = load_corpus(corpus)
    assert loaded_metadata == metadata
    assert loaded_metadata.reward_profile == "defense-v2"
    assert loaded_metadata.behavior_checkpoint is None
    assert loaded_metadata.expert_probability == 1.0
    assert loaded_metadata.sampling_decks_path == str(sampling_decks)
    assert arrays["expert_actions"].shape == (4,)
    assert np.all(arrays["action_masks"][np.arange(4), arrays["expert_actions"]])
    token_names = np.asarray(loaded_metadata.token_names)
    observed_hand_cards = set(token_names[np.unique(arrays["hand_ids"])]) - {"<pad>"}
    assert observed_hand_cards <= set(sampled_cards)

    imitation = tmp_path / "imitation.pt"
    control = tmp_path / "control.pt"
    manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=imitation,
        control_checkpoint=control,
        decks_path=Path("decks.json").resolve(),
        seed=41,
        split_seed=43,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
        hand_permutation_augmentation=True,
    )

    imitation_payload = torch.load(imitation, weights_only=False)
    control_payload = torch.load(control, weights_only=False)
    assert imitation_payload["format_version"] == 2
    assert control_payload["format_version"] == 2
    assert imitation_payload["imitation"]["trained"] is True
    assert control_payload["imitation"]["trained"] is False
    assert "optimizer_state_dict" not in imitation_payload
    assert "optimizer_state_dict" not in control_payload
    assert imitation_payload["args"]["split_seed"] == 43
    assert control_payload["args"]["split_seed"] == 43
    assert manifest["split_seed"] == 43
    assert manifest["hand_permutation_augmentation"] is True
    assert manifest["hand_permutation_augmentation_probability"] == 1.0
    assert imitation_payload["args"]["hand_permutation_augmentation"] is True
    assert (
        imitation_payload["args"]["hand_permutation_augmentation_probability"]
        == 1.0
    )
    assert control_payload["args"]["hand_permutation_augmentation"] is True
    assert (
        control_payload["args"]["hand_permutation_augmentation_probability"]
        == 1.0
    )
    assert manifest["trim_entity_padding"] is False
    assert manifest["train_samples"] + manifest["validation_samples"] == 4
    assert any(
        not torch.equal(
            imitation_payload["model_state_dict"][name],
            control_payload["model_state_dict"][name],
        )
        for name in imitation_payload["model_state_dict"]
    )

    structural_imitation = tmp_path / "structural_imitation.pt"
    structural_control = tmp_path / "structural_control.pt"
    fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=structural_imitation,
        control_checkpoint=structural_control,
        decks_path=Path("decks.json").resolve(),
        seed=47,
        split_seed=43,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
        equivariant_hand_policy=True,
    )
    structural_payload = torch.load(structural_imitation, weights_only=False)
    structural_config = structural_payload["model_config"]
    assert structural_config["actor_current_hand_slot_invariant"] is True
    assert structural_config["semantic_slot_choice_replace_base"] is True
    assert structural_config["mechanics_slot_choice_replace_base"] is True
    assert structural_config["equivariant_slot_choice"] is True
    assert structural_config["equivariant_timing_query_enabled"] is True

    slot_only_imitation = tmp_path / "slot_only_imitation.pt"
    slot_only_control = tmp_path / "slot_only_control.pt"
    slot_only_manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=slot_only_imitation,
        control_checkpoint=slot_only_control,
        decks_path=Path("decks.json").resolve(),
        seed=49,
        split_seed=43,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
        equivariant_slot_choice_only=True,
    )
    slot_only_payload = torch.load(slot_only_imitation, weights_only=False)
    slot_only_config = slot_only_payload["model_config"]
    assert slot_only_config["actor_current_hand_slot_invariant"] is True
    assert slot_only_config["semantic_slot_choice_replace_base"] is True
    assert slot_only_config["mechanics_slot_choice_replace_base"] is True
    assert slot_only_config["equivariant_slot_choice"] is True
    assert slot_only_config["equivariant_timing_query_enabled"] is False
    assert slot_only_manifest["equivariant_slot_choice_only"] is True

    hierarchical_imitation = tmp_path / "hierarchical_imitation.pt"
    hierarchical_control = tmp_path / "hierarchical_control.pt"
    hierarchical_manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=hierarchical_imitation,
        control_checkpoint=hierarchical_control,
        decks_path=Path("decks.json").resolve(),
        seed=51,
        split_seed=43,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
        imitation_objective="hierarchical-v1",
        hierarchical_mode_gate=True,
    )
    hierarchical_payload = torch.load(hierarchical_imitation, weights_only=False)
    assert hierarchical_payload["model_config"]["hierarchical_mode_gate_enabled"]
    assert hierarchical_payload["model_config"]["deterministic_hierarchy"] == (
        "play-gate"
    )
    assert hierarchical_manifest["hierarchical_mode_gate"] is True
    assert hierarchical_manifest["deterministic_hierarchy"] == "play-gate"
    assert "validation_hierarchical_play_accuracy" in hierarchical_payload["metrics"]

    dagger_corpus = tmp_path / "dagger_corpus.npz"
    dagger_metadata = collect_oracle_corpus(
        output_path=dagger_corpus,
        decks_path=Path("decks.json").resolve(),
        decisions=1,
        seed=53,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
        behavior_checkpoint=control,
        expert_probability=0.0,
    )
    assert dagger_metadata.behavior_checkpoint == str(control)
    assert dagger_metadata.expert_probability == 0.0
    _, dagger_arrays = load_corpus(dagger_corpus)
    assert np.all(
        dagger_arrays["action_masks"][
            np.arange(2), dagger_arrays["expert_actions"]
        ]
    )

    stationary_corpus = tmp_path / "stationary_dagger_corpus.npz"
    stationary_metadata = collect_oracle_corpus(
        output_path=stationary_corpus,
        decks_path=Path("decks.json").resolve(),
        decisions=2,
        seed=61,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
        behavior_checkpoint=control,
        expert_probability=0.0,
        stable_root_candidates=True,
        behavior_opponent="random",
    )
    assert stationary_metadata.samples == stationary_metadata.decisions == 2
    assert stationary_metadata.behavior_opponent == "random"
    _, stationary_arrays = load_corpus(stationary_corpus)
    assert stationary_arrays["expert_actions"].shape == (2,)
    assert stationary_arrays["episode_ids"].tolist() == [0, 0]
    assert np.all(
        stationary_arrays["action_masks"][
            np.arange(2), stationary_arrays["expert_actions"]
        ]
    )

    behavior_corpus = tmp_path / "behavior_corpus.npz"
    behavior_metadata = collect_oracle_corpus(
        output_path=behavior_corpus,
        decks_path=Path("decks.json").resolve(),
        decisions=2,
        seed=67,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
        behavior_checkpoint=control,
        expert_probability=0.0,
        behavior_opponent="random",
        label_source="behavior",
    )
    assert behavior_metadata.label_source == "behavior"
    _, behavior_arrays = load_corpus(behavior_corpus)
    assert behavior_arrays["expert_actions"].shape == (2,)
    assert np.all(
        behavior_arrays["action_masks"][
            np.arange(2), behavior_arrays["expert_actions"]
        ]
    )

    strategy_corpus = tmp_path / "strategy_corpus.npz"
    strategy_metadata = collect_oracle_corpus(
        output_path=strategy_corpus,
        decks_path=Path("decks.json").resolve(),
        decisions=2,
        seed=71,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
        behavior_checkpoint=control,
        expert_probability=0.0,
        behavior_opponent="random",
        label_source="strategy",
        label_strategy="strategy:balanced",
    )
    assert strategy_metadata.label_source == "strategy"
    assert strategy_metadata.label_strategy == "strategy:balanced"
    _, strategy_arrays = load_corpus(strategy_corpus)
    assert strategy_arrays["expert_actions"].shape == (2,)
    assert np.all(
        strategy_arrays["action_masks"][
            np.arange(2), strategy_arrays["expert_actions"]
        ]
    )

    initial = tmp_path / "initial.pt"
    control_payload["update"] = 240
    control_payload["total_transitions"] = 983_040
    torch.save(control_payload, initial)
    finetuned = tmp_path / "finetuned.pt"
    finetune_control = tmp_path / "finetune_control.pt"
    finetune_manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=finetuned,
        control_checkpoint=finetune_control,
        decks_path=Path("decks.json").resolve(),
        seed=59,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=128,
        num_heads=4,
        actor_layers=4,
        critic_layers=2,
        memory_size=256,
        initial_checkpoint=initial,
    )
    finetuned_payload = torch.load(finetuned, weights_only=False)
    finetune_control_payload = torch.load(finetune_control, weights_only=False)
    assert finetuned_payload["update"] == 240
    assert finetuned_payload["total_transitions"] == 983_040
    assert finetuned_payload["args"]["initialization"] == "oracle_imitation_finetune"
    assert finetune_control_payload["args"]["initialization"] == (
        "initial_checkpoint_control"
    )
    assert finetune_manifest["initial_checkpoint"] == str(initial)
    assert all(
        torch.equal(
            finetune_control_payload["model_state_dict"][name],
            control_payload["model_state_dict"][name],
        )
        for name in control_payload["model_state_dict"]
    )

    public_entity_features = arrays["entity_features"].copy()
    public_entity_confidence = np.ones_like(
        public_entity_features, dtype=np.float16
    )
    for feature in range(public_entity_features.shape[-1]):
        if feature not in REAL_PLAY_ENTITY_FEATURE_INDICES:
            public_entity_features[..., feature] = 0.0
            public_entity_confidence[..., feature] = 0.0
    public_global_features = arrays["global_features"].copy()
    public_global_confidence = np.ones_like(
        public_global_features, dtype=np.float16
    )
    for feature in range(public_global_features.shape[-1]):
        if feature not in REAL_PLAY_GLOBAL_FEATURE_INDICES:
            public_global_features[..., feature] = 0.0
            public_global_confidence[..., feature] = 0.0
    public_hand_ids = arrays["hand_ids"].copy()
    public_hand_confidence = np.ones_like(public_hand_ids, dtype=np.float16)
    public_hand_ids[..., 4:] = 0
    public_hand_confidence[..., 4:] = 0.0
    public_sidecar = tmp_path / "public_state_v2.npz"
    np.savez(
        public_sidecar,
            schema_version=np.asarray(2),
            action_mask_contract_version=np.asarray(
                PUBLIC_ACTION_MASK_CONTRACT_VERSION
            ),
        entity_ids=arrays["entity_ids"],
        entity_features=public_entity_features,
        entity_mask=arrays["entity_mask"],
        entity_id_confidence=np.ones_like(
            arrays["entity_ids"], dtype=np.float16
        ),
        entity_feature_confidence=public_entity_confidence,
        hand_ids=public_hand_ids,
        hand_id_confidence=public_hand_confidence,
            global_features=public_global_features,
            global_feature_confidence=public_global_confidence,
            action_masks=arrays["action_masks"],
            expert_action_masked=np.zeros(
                arrays["expert_actions"].shape, dtype=np.bool_
            ),
            expert_actions=arrays["expert_actions"],
        episode_ids=arrays["episode_ids"],
    )
    public_checkpoint = tmp_path / "public_imitation.pt"
    public_control = tmp_path / "public_control.pt"
    public_manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=public_checkpoint,
        control_checkpoint=public_control,
        decks_path=Path("decks.json").resolve(),
        seed=61,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
        initial_checkpoint=initial,
        public_observation_sidecar=public_sidecar,
    )
    public_payload = torch.load(public_checkpoint, weights_only=False)
    public_control_payload = torch.load(public_control, weights_only=False)
    assert public_payload["model_config"]["public_observation_confidence"] is True
    assert public_payload["model_config"]["actor_observation_domain"] == (
        "causal-frame-v1"
    )
    assert public_manifest["public_observation_sidecar"] == str(public_sidecar)
    assert all(
        torch.equal(
            public_control_payload["model_state_dict"][name],
            control_payload["model_state_dict"][name],
        )
        for name in control_payload["model_state_dict"]
    )
    assert set(public_control_payload["model_state_dict"]) - set(
        control_payload["model_state_dict"]
    ) == set(imitation_module.PUBLIC_CONFIDENCE_STATE_KEYS)

    type_head_checkpoint = tmp_path / "type_head.pt"
    type_head_control = tmp_path / "type_head_control.pt"
    type_head_manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=type_head_checkpoint,
        control_checkpoint=type_head_control,
        decks_path=Path("decks.json").resolve(),
        seed=67,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=128,
        num_heads=4,
        actor_layers=4,
        critic_layers=2,
        memory_size=256,
        initial_checkpoint=initial,
        imitation_objective="type-head-v1",
    )
    type_head_payload = torch.load(type_head_checkpoint, weights_only=False)
    type_head_control_payload = torch.load(type_head_control, weights_only=False)
    changed_names = {
        name
        for name, value in type_head_payload["model_state_dict"].items()
        if not torch.equal(
            value,
            type_head_control_payload["model_state_dict"][name],
        )
    }
    assert changed_names
    assert all(name.startswith("action_type_head.") for name in changed_names)
    assert type_head_manifest["trainable_scope"] == "action_type_head"

    scoped_checkpoint = tmp_path / "scoped.pt"
    scoped_control = tmp_path / "scoped_control.pt"
    scoped_manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=scoped_checkpoint,
        control_checkpoint=scoped_control,
        decks_path=Path("decks.json").resolve(),
        seed=71,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=128,
        num_heads=4,
        actor_layers=4,
        critic_layers=2,
        memory_size=256,
        initial_checkpoint=initial,
        imitation_objective="type-head-v1",
        trainable_prefixes=("memory.", "action_type_head."),
        anchor_policy_kl_coef=1.0,
    )
    scoped_payload = torch.load(scoped_checkpoint, weights_only=False)
    scoped_control_payload = torch.load(scoped_control, weights_only=False)
    scoped_changed_names = {
        name
        for name, value in scoped_payload["model_state_dict"].items()
        if not torch.equal(value, scoped_control_payload["model_state_dict"][name])
    }
    assert scoped_changed_names
    assert any(name.startswith("memory.") for name in scoped_changed_names)
    assert all(
        name.startswith(("memory.", "action_type_head."))
        for name in scoped_changed_names
    )
    assert scoped_manifest["trainable_scope"] == [
        "memory.",
        "action_type_head.",
    ]
    assert scoped_manifest["anchor_policy_kl_coef"] == 1.0
    assert scoped_payload["imitation"]["anchor_policy_kl_coef"] == 1.0
    assert type_head_manifest["spatial_config"]["location_loss_coef"] == 0.0

    monkeypatch.setattr(
        imitation_module,
        "policy_anchor_kl",
        lambda *_args: torch.tensor(float("nan")),
    )
    with pytest.raises(FloatingPointError, match="non-finite imitation loss"):
        fit_imitation_corpus(
            corpus_path=corpus,
            output_checkpoint=tmp_path / "nonfinite.pt",
            control_checkpoint=tmp_path / "nonfinite_control.pt",
            decks_path=Path("decks.json").resolve(),
            seed=73,
            epochs=1,
            batch_size=2,
            learning_rate=1e-4,
            validation_fraction=0.25,
            device=torch.device("cpu"),
            d_model=128,
            num_heads=4,
            actor_layers=4,
            critic_layers=2,
            memory_size=256,
            initial_checkpoint=initial,
            anchor_policy_kl_coef=1.0,
        )


def test_parallel_corpus_collection_has_disjoint_episode_ids(tmp_path: Path):
    corpus = tmp_path / "parallel_oracle_corpus.npz"
    metadata = collect_oracle_corpus(
        output_path=corpus,
        decks_path=Path("decks.json").resolve(),
        decisions=2,
        seed=71,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
        workers=2,
    )

    loaded_metadata, arrays = load_corpus(corpus)
    assert loaded_metadata == metadata
    assert metadata.workers == 2
    assert arrays["episode_ids"].tolist() == [0, 0, 1, 1]


def test_completed_oracle_shard_resumes_without_recollection(
    tmp_path: Path,
    monkeypatch,
):
    output = tmp_path / "oracle.npz"
    kwargs = {
        "output_path": output,
        "decks_path": Path("decks.json").resolve(),
        "decisions": 1,
        "seed": 71,
        "decision_interval": 1,
        "max_ticks": 20,
        "planner_depth": 1,
        "planner_simulations": 1,
        "planner_action_samples": 4,
        "max_entities": 16,
        "quiet_engine": True,
        "workers": 1,
    }
    first = collect_oracle_corpus(**kwargs)
    output.unlink()

    def fail_recollection(_config):
        raise AssertionError("completed shard should be reused")

    monkeypatch.setattr(
        imitation_module,
        "_collect_oracle_shard",
        fail_recollection,
    )
    resumed = collect_oracle_corpus(**kwargs)
    loaded, arrays = load_corpus(output)

    assert first.samples == resumed.samples == loaded.samples == 2
    assert arrays["expert_actions"].shape == (2,)
    manifest = json.loads(manifest_path(output).read_text())
    assert manifest["complete"] is True
    assert manifest["completed_shards"] == [0]
