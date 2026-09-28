from __future__ import annotations

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.add_equivariant_timing_query import add_equivariant_timing_query


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
        actor_current_hand_slot_invariant=True,
        mechanics_slot_choice_adapter_enabled=True,
        mechanics_slot_choice_replace_base=True,
        equivariant_slot_choice=True,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    return {
        "model_config": config.to_dict(),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": {"stale": True},
    }


def test_add_equivariant_timing_query_preserves_existing_tensors() -> None:
    source = _payload()

    actual = add_equivariant_timing_query(source)

    config = PolicyConfig.from_dict(actual["model_config"])
    assert config.equivariant_timing_query_enabled
    assert config.equivariant_deterministic_timing_pool == "log-mass"
    assert "optimizer_state_dict" not in actual
    assert actual["equivariant_timing_query_upgrade"] == {
        "schema_version": 1,
        "outputs": ["play", "wait", "ability"],
        "query_is_zero_and_requires_distillation": True,
        "slot_choice_tensors_unchanged": True,
    }
    for name, tensor in source["model_state_dict"].items():
        assert torch.equal(actual["model_state_dict"][name], tensor)
    assert not bool(
        torch.count_nonzero(
            actual["model_state_dict"]["equivariant_timing_query.weight"]
        )
    )
    assert not bool(
        torch.count_nonzero(
            actual["model_state_dict"]["equivariant_timing_query.bias"]
        )
    )


def test_add_equivariant_timing_query_rejects_duplicate_upgrade() -> None:
    first = add_equivariant_timing_query(_payload())
    try:
        add_equivariant_timing_query(first)
    except ValueError as error:
        assert "already has" in str(error)
    else:  # pragma: no cover - explicit fail path
        raise AssertionError("duplicate timing query accepted")
