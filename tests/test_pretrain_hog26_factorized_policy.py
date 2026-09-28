from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from scripts.pretrain_hog26_factorized_policy import (
    actor_parameters,
    fixed_sequence_chunks,
    load_behavior_corpus,
)


def test_fixed_chunks_never_cross_episode_boundaries() -> None:
    chunks = fixed_sequence_chunks(np.asarray([0, 0, 0, 0, 1, 1, 1, 1]), 2)
    assert chunks.tolist() == [[0, 1], [2, 3], [4, 5], [6, 7]]
    with pytest.raises(ValueError, match="contiguous"):
        fixed_sequence_chunks(np.asarray([0, 1, 0, 1]), 2)


def test_actor_pretraining_excludes_privileged_and_value_heads() -> None:
    config = PolicyConfig(
        num_tokens=8,
        max_entities=4,
        d_model=16,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
        memory_kind="structured",
        deterministic_hierarchy="play-gate",
        hierarchical_mode_gate_enabled=True,
        semantic_slot_choice_adapter_enabled=True,
        semantic_slot_choice_replace_base=True,
        actor_current_hand_slot_invariant=True,
        equivariant_slot_choice=True,
    )
    model = ClasherPolicy(config, torch.zeros(8, 16))
    names, _parameters = actor_parameters(model)
    assert names
    assert not any(name.startswith("critic_encoder.") for name in names)
    assert not any(name.startswith("value_head.") for name in names)
    assert any(name.startswith("actor_encoder.") for name in names)


def test_exact_simulator_corpus_derives_all_confidences(tmp_path) -> None:
    path = tmp_path / "corpus.npz"
    rows = 2
    np.savez_compressed(
        path,
        entity_ids=np.asarray([[2, 0], [3, 4]]),
        entity_features=np.zeros((rows, 2, 32), dtype=np.float32),
        entity_mask=np.asarray([[True, False], [True, True]]),
        hand_ids=np.asarray([[2, 3, 4, 5, 6], [2, 3, 4, 5, 6]]),
        global_features=np.zeros((rows, 18), dtype=np.float32),
        action_masks=np.ones((rows, 2306), dtype=np.bool_),
        previous_actions=np.zeros(rows, dtype=np.int64),
        previous_rewards=np.zeros(rows, dtype=np.float32),
        episode_starts=np.asarray([True, False]),
        expert_actions=np.zeros(rows, dtype=np.int64),
        episode_ids=np.zeros(rows, dtype=np.int64),
        metadata_json=np.asarray(json.dumps({"token_names": ["<pad>"] * 8})),
    )
    metadata, arrays = load_behavior_corpus(path)
    assert metadata["confidence_authority"] == "exact-simulator-derived"
    assert arrays["entity_id_confidence"].tolist() == [[1.0, 0.0], [1.0, 1.0]]
    assert bool((arrays["global_feature_confidence"] == 1.0).all())
