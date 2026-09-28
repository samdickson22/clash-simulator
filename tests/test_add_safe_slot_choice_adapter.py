from __future__ import annotations

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.add_safe_slot_choice_adapter import add_safe_slot_choice_adapter


def test_add_safe_slot_choice_adapter_preserves_every_existing_tensor():
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

    upgraded = add_safe_slot_choice_adapter(payload)

    assert upgraded["model_config"]["safe_slot_choice_adapter_enabled"] is True
    assert "optimizer_state_dict" not in upgraded
    for name, tensor in model.state_dict().items():
        torch.testing.assert_close(upgraded["model_state_dict"][name], tensor)
    adapter_tensors = {
        name: tensor
        for name, tensor in upgraded["model_state_dict"].items()
        if name.startswith("safe_slot_choice_adapter.")
    }
    assert set(adapter_tensors) == {
        "safe_slot_choice_adapter.weight",
        "safe_slot_choice_adapter.bias",
    }
    assert all(torch.count_nonzero(tensor) == 0 for tensor in adapter_tensors.values())
