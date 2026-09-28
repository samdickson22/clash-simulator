from __future__ import annotations

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.set_equivariant_timing_pool import set_equivariant_timing_pool


def _payload(*, equivariant: bool = True) -> dict:
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=8)
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=8,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
        actor_current_hand_slot_invariant=equivariant,
        mechanics_slot_choice_adapter_enabled=equivariant,
        mechanics_slot_choice_replace_base=equivariant,
        equivariant_slot_choice=equivariant,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    return {
        "model_config": config.to_dict(),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": {"stale": True},
    }


def test_set_equivariant_timing_pool_changes_config_only() -> None:
    source = _payload()

    actual = set_equivariant_timing_pool(source, timing_pool="max")

    config = PolicyConfig.from_dict(actual["model_config"])
    assert config.equivariant_deterministic_timing_pool == "max"
    assert "optimizer_state_dict" not in actual
    assert actual["equivariant_timing_pool_upgrade"] == {
        "schema_version": 1,
        "timing_pool": "max",
        "stochastic_play_mass_unchanged": True,
        "model_tensors_unchanged": True,
    }
    for name, tensor in source["model_state_dict"].items():
        assert torch.equal(actual["model_state_dict"][name], tensor)


def test_set_equivariant_timing_pool_rejects_non_equivariant_checkpoint() -> None:
    try:
        set_equivariant_timing_pool(_payload(equivariant=False), timing_pool="max")
    except ValueError as error:
        assert "requires equivariant" in str(error)
    else:  # pragma: no cover - explicit fail path
        raise AssertionError("non-equivariant checkpoint accepted")
