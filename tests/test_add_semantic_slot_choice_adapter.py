from __future__ import annotations

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.add_semantic_slot_choice_adapter import (
    add_semantic_slot_choice_adapter,
)


def test_add_semantic_slot_choice_adapter_preserves_every_existing_tensor() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=64,
        ),
        builder.card_stat_features,
    )
    payload = {
        "format_version": 2,
        "update": 7,
        "model_config": model.config.to_dict(),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": {"discard": True},
    }

    upgraded = add_semantic_slot_choice_adapter(payload)

    assert upgraded["model_config"]["semantic_slot_choice_adapter_enabled"] is True
    assert "optimizer_state_dict" not in upgraded
    for name, tensor in model.state_dict().items():
        torch.testing.assert_close(upgraded["model_state_dict"][name], tensor)
    adapter_tensors = {
        name: tensor
        for name, tensor in upgraded["model_state_dict"].items()
        if name.startswith("semantic_slot_choice_query.")
    }
    assert set(adapter_tensors) == {"semantic_slot_choice_query.weight"}
    assert all(torch.count_nonzero(tensor) == 0 for tensor in adapter_tensors.values())
    assert upgraded["semantic_slot_choice_adapter_upgrade"] == {
        "schema_version": 1,
        "source_update": 7,
        "preserves_base_policy_exactly_at_zero": True,
        "preserves_play_wait_ability_mass_after_training": True,
        "scores_frozen_identity_and_mechanics_embeddings": True,
        "replaces_base_conditional_slot_logits": False,
        "initialized_from_pretrained_query": False,
    }


def test_add_semantic_slot_choice_adapter_can_replace_legacy_slot_logits() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=64,
        ),
        builder.card_stat_features,
    )
    payload = {
        "format_version": 2,
        "update": 7,
        "model_config": model.config.to_dict(),
        "model_state_dict": model.state_dict(),
    }

    upgraded = add_semantic_slot_choice_adapter(payload, replace_base=True)

    config = PolicyConfig.from_dict(upgraded["model_config"])
    assert config.semantic_slot_choice_adapter_enabled
    assert config.semantic_slot_choice_replace_base
    assert upgraded["semantic_slot_choice_adapter_upgrade"] == {
        "schema_version": 1,
        "source_update": 7,
        "preserves_base_policy_exactly_at_zero": False,
        "preserves_play_wait_ability_mass_after_training": True,
        "scores_frozen_identity_and_mechanics_embeddings": True,
        "replaces_base_conditional_slot_logits": True,
        "initialized_from_pretrained_query": False,
    }


def test_add_semantic_slot_choice_adapter_accepts_pretrained_query() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=64,
        ),
        builder.card_stat_features,
    )
    payload = {
        "format_version": 2,
        "update": 7,
        "model_config": model.config.to_dict(),
        "model_state_dict": model.state_dict(),
    }
    query_weight = torch.randn((32, 96), generator=torch.Generator().manual_seed(7))

    upgraded = add_semantic_slot_choice_adapter(
        payload,
        replace_base=True,
        query_weight=query_weight,
    )

    torch.testing.assert_close(
        upgraded["model_state_dict"]["semantic_slot_choice_query.weight"],
        query_weight,
    )
    assert upgraded["semantic_slot_choice_adapter_upgrade"][
        "initialized_from_pretrained_query"
    ]
