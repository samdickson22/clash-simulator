from __future__ import annotations

from pathlib import Path

import torch

from scripts.pretrain_public_cycle_belief import (
    build_upgraded_policy,
    configure_belief_trainable,
    verify_policy_equivalence,
)

SOURCE = Path(
    "checkpoints/tv_raw1000_spatial_value_rl_seed1044801/"
    "policy_v2_update_000040.pt"
)


def test_belief_upgrade_is_zero_output_and_has_narrow_trainable_scope() -> None:
    payload = torch.load(SOURCE, map_location="cpu", weights_only=False)
    model, builder, missing = build_upgraded_policy(payload, seed=1048803)
    trainable = configure_belief_trainable(model)

    assert model.config.public_history_slots == 4
    assert model.config.public_seen_card_slots == 8
    assert missing
    assert trainable
    assert not any(name.startswith("public_history_projection.") for name in trainable)
    assert model.public_history_projection is not None
    assert not torch.count_nonzero(model.public_history_projection[-1].weight)
    assert not torch.count_nonzero(model.public_history_projection[-1].bias)
    assert model.public_belief_card_query is not None
    assert model.public_belief_timing_head is not None
    assert not torch.count_nonzero(model.public_belief_card_query.weight)
    assert not torch.count_nonzero(model.public_belief_card_query.bias)
    assert not torch.count_nonzero(model.public_belief_timing_head.weight)
    assert not torch.count_nonzero(model.public_belief_timing_head.bias)
    result = verify_policy_equivalence(payload, model, builder)
    assert result["bit_exact"] is True
    assert result["max_joint_logit_abs_difference"] == 0.0
    assert result["max_value_abs_difference"] == 0.0
