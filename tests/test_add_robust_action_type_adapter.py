from __future__ import annotations

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.add_robust_action_type_adapter import add_robust_action_type_adapter


def test_add_robust_action_type_adapter_preserves_every_existing_tensor():
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

    upgraded = add_robust_action_type_adapter(payload, hidden_size=16)

    assert upgraded["model_config"]["robust_action_type_adapter_size"] == 16
    assert "optimizer_state_dict" not in upgraded
    for name, tensor in model.state_dict().items():
        torch.testing.assert_close(upgraded["model_state_dict"][name], tensor)
    adapter_tensors = {
        name: tensor
        for name, tensor in upgraded["model_state_dict"].items()
        if name.startswith("robust_action_type_adapter.")
    }
    assert set(adapter_tensors) == {
        "robust_action_type_adapter.0.weight",
        "robust_action_type_adapter.0.bias",
        "robust_action_type_adapter.2.weight",
        "robust_action_type_adapter.2.bias",
    }
    assert torch.count_nonzero(adapter_tensors["robust_action_type_adapter.0.weight"])
    assert not torch.count_nonzero(adapter_tensors["robust_action_type_adapter.2.weight"])
    assert not torch.count_nonzero(adapter_tensors["robust_action_type_adapter.2.bias"])
    torch.testing.assert_close(
        upgraded["model_state_dict"]["robust_action_card_stats"],
        model.state_dict()["actor_encoder.card_stat_features"][:, :16],
    )
