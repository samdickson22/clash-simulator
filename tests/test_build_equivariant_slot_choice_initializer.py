from __future__ import annotations

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.build_equivariant_slot_choice_initializer import (
    build_equivariant_initializer,
)


def _payload() -> dict:
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=8)
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=8,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
        mechanics_slot_choice_adapter_enabled=True,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    return {
        "format_version": 2,
        "model_config": config.to_dict(),
        "model_state_dict": model.state_dict(),
        "token_names": tuple(builder.token_names),
        "optimizer_state_dict": {"stale": True},
    }


def test_build_equivariant_initializer_is_state_dict_compatible() -> None:
    source = _payload()

    actual = build_equivariant_initializer(source)

    config = PolicyConfig.from_dict(actual["model_config"])
    assert config.actor_current_hand_slot_invariant
    assert config.mechanics_slot_choice_replace_base
    assert config.equivariant_slot_choice
    assert "optimizer_state_dict" not in actual
    assert actual["equivariant_slot_choice_upgrade"] == {
        "schema_version": 1,
        "actor_current_hand_slots_share_their_mean_embedding": True,
        "aggregate_play_timing_is_slot_permutation_invariant": True,
        "conditional_card_choice_replaces_fixed_slot_logits": True,
        "conditional_card_choice_query": "mechanics_slot_choice_query",
        "semantic_card_query_enabled": False,
        "query_is_zero_and_requires_supervised_pretraining": True,
        "legacy_checkpoint_outputs_preserved": False,
    }
    for name, tensor in source["model_state_dict"].items():
        assert torch.equal(actual["model_state_dict"][name], tensor)


def test_build_equivariant_initializer_rejects_nonzero_query() -> None:
    source = _payload()
    source["model_state_dict"]["mechanics_slot_choice_query.weight"].fill_(1.0)

    try:
        build_equivariant_initializer(source)
    except ValueError as error:
        assert "must be zero" in str(error)
    else:  # pragma: no cover - explicit fail path
        raise AssertionError("nonzero query was accepted")


def test_build_equivariant_initializer_can_add_semantic_capacity() -> None:
    source = _payload()

    actual = build_equivariant_initializer(
        source,
        include_semantic_query=True,
    )

    config = PolicyConfig.from_dict(actual["model_config"])
    assert config.semantic_slot_choice_adapter_enabled
    assert config.semantic_slot_choice_replace_base
    assert actual["equivariant_slot_choice_upgrade"]["semantic_card_query_enabled"]
    semantic = actual["model_state_dict"]["semantic_slot_choice_query.weight"]
    assert not bool(torch.count_nonzero(semantic))


def test_build_equivariant_initializer_supports_semantic_v3() -> None:
    builder = StructuredObservationBuilder(
        decks_path="decks.json", max_entities=8, card_semantics_version=3
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=8,
        card_semantics_version=3,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
        mechanics_slot_choice_adapter_enabled=True,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    source = {
        "format_version": 2,
        "model_config": config.to_dict(),
        "model_state_dict": model.state_dict(),
        "token_names": tuple(builder.token_names),
    }

    actual = build_equivariant_initializer(source)

    upgraded = PolicyConfig.from_dict(actual["model_config"])
    assert upgraded.equivariant_slot_choice
    assert actual["model_state_dict"][
        "actor_encoder.semantic_card_features"
    ].shape == model.state_dict()["actor_encoder.semantic_card_features"].shape
