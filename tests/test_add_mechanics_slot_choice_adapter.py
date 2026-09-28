from __future__ import annotations

import pytest
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.add_mechanics_slot_choice_adapter import (
    _probe_query_weight,
    add_mechanics_slot_choice_adapter,
)
from scripts.fit_mechanics_slot_probe import MechanicsSlotScorer


def _payload(*, semantics_version: int = 1) -> tuple[dict, torch.Tensor]:
    builder = StructuredObservationBuilder(
        card_vocab=["Knight"],
        max_entities=8,
        card_semantics_version=semantics_version,
    )
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            card_semantics_version=semantics_version,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=64,
        ),
        builder.card_stat_features,
    )
    return (
        {
            "format_version": 2,
            "update": 7,
            "token_names": builder.token_names,
            "model_config": model.config.to_dict(),
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": {"discard": True},
        },
        torch.as_tensor(builder.card_stat_features),
    )


def test_add_mechanics_adapter_preserves_every_existing_tensor() -> None:
    payload, card_stats = _payload()

    upgraded = add_mechanics_slot_choice_adapter(
        payload,
        card_stat_features=card_stats,
    )

    config = PolicyConfig.from_dict(upgraded["model_config"])
    assert config.mechanics_slot_choice_adapter_enabled
    assert not config.mechanics_slot_choice_replace_base
    assert "optimizer_state_dict" not in upgraded
    for name, tensor in payload["model_state_dict"].items():
        torch.testing.assert_close(upgraded["model_state_dict"][name], tensor)
    adapter_tensors = {
        name: tensor
        for name, tensor in upgraded["model_state_dict"].items()
        if name.startswith("mechanics_slot_")
    }
    assert set(adapter_tensors) == {
        "mechanics_slot_card_stats",
        "mechanics_slot_choice_query.weight",
    }
    torch.testing.assert_close(
        adapter_tensors["mechanics_slot_card_stats"],
        card_stats[:, :16],
    )
    assert torch.count_nonzero(
        adapter_tensors["mechanics_slot_choice_query.weight"]
    ) == 0
    assert upgraded["mechanics_slot_choice_adapter_upgrade"] == {
        "schema_version": 1,
        "source_update": 7,
        "preserves_base_policy_exactly_at_zero": True,
        "preserves_play_wait_ability_mass_after_training": True,
        "preserves_conditional_placement_geometry": True,
        "scores_only_frozen_public_mechanics": True,
        "mechanics_feature_count": 16,
        "replaces_base_conditional_slot_logits": False,
        "base_logit_scale": 1.0,
        "initialized_from_pretrained_query": False,
        "query_scale": 1.0,
    }


def test_add_mechanics_adapter_accepts_scaled_linear_probe_query() -> None:
    payload, card_stats = _payload()
    query = torch.randn((16, 96), generator=torch.Generator().manual_seed(7))

    upgraded = add_mechanics_slot_choice_adapter(
        payload,
        card_stat_features=card_stats,
        replace_base=True,
        query_weight=query,
        query_scale=0.25,
    )

    config = PolicyConfig.from_dict(upgraded["model_config"])
    assert config.mechanics_slot_choice_replace_base
    torch.testing.assert_close(
        upgraded["model_state_dict"]["mechanics_slot_choice_query.weight"],
        query * 0.25,
    )
    metadata = upgraded["mechanics_slot_choice_adapter_upgrade"]
    assert metadata["initialized_from_pretrained_query"]
    assert metadata["query_scale"] == 0.25
    assert not metadata["preserves_base_policy_exactly_at_zero"]


def test_add_mechanics_adapter_records_exact_logit_blend_scales() -> None:
    payload, card_stats = _payload()
    query = torch.randn((16, 96), generator=torch.Generator().manual_seed(17))

    upgraded = add_mechanics_slot_choice_adapter(
        payload,
        card_stat_features=card_stats,
        base_scale=0.7,
        query_weight=query,
        query_scale=0.3,
    )

    config = PolicyConfig.from_dict(upgraded["model_config"])
    assert config.mechanics_slot_choice_base_scale == 0.7
    metadata = upgraded["mechanics_slot_choice_adapter_upgrade"]
    assert metadata["base_logit_scale"] == 0.7
    assert metadata["query_scale"] == 0.3
    assert not metadata["preserves_base_policy_exactly_at_zero"]


def test_mechanics_adapter_rejects_semantics_without_base_features() -> None:
    payload, card_stats = _payload(semantics_version=2)

    with pytest.raises(ValueError, match="semantics v1 or v3"):
        add_mechanics_slot_choice_adapter(
            payload,
            card_stat_features=card_stats,
        )


def test_probe_query_requires_exact_linear_v1_contract() -> None:
    query = torch.zeros((16, 96))
    valid = {
        "schema_version": 1,
        "semantics_version": 1,
        "hidden_size": 0,
        "token_names": ("<pad>", "<unknown>", "Knight"),
        "state_dict": {"state_query.weight": query},
    }
    assert _probe_query_weight(
        valid,
        token_names=("<pad>", "<unknown>", "Knight"),
    ) is query

    invalid = {**valid, "hidden_size": 64}
    with pytest.raises(ValueError, match="linear scorer"):
        _probe_query_weight(
            invalid,
            token_names=("<pad>", "<unknown>", "Knight"),
        )


def test_policy_adapter_exactly_reproduces_linear_probe_scores() -> None:
    payload, card_stats = _payload()
    query = torch.randn((16, 96), generator=torch.Generator().manual_seed(8))
    upgraded = add_mechanics_slot_choice_adapter(
        payload,
        card_stat_features=card_stats,
        query_weight=query,
    )
    model = ClasherPolicy(
        PolicyConfig.from_dict(upgraded["model_config"]),
        card_stats,
    ).eval()
    model.load_state_dict(upgraded["model_state_dict"])
    probe = MechanicsSlotScorer(state_size=96, card_size=16, hidden_size=0).eval()
    probe.load_state_dict({"state_query.weight": query})
    state = torch.randn((3, 96), generator=torch.Generator().manual_seed(9))
    hand_ids = torch.tensor([[0, 1, 2, 1], [2, 1, 0, 2], [1, 2, 1, 0]])
    assert model.mechanics_slot_card_stats is not None

    with torch.no_grad():
        expected = probe(state, model.mechanics_slot_card_stats[hand_ids])
        actual = model._mechanics_slot_choice_scores(state, hand_ids)

    assert torch.equal(actual, expected)
