from __future__ import annotations

import numpy as np
from torch import nn

from scripts.audit_live_policy_budget import (
    fresh_factorial_budget,
    parameter_partition,
    select_entity_buckets,
)


class _PartitionFixture(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.actor_encoder = nn.Linear(2, 3)
        self.memory = nn.Linear(3, 3)
        self.critic_encoder = nn.Linear(2, 4)
        self.value_head = nn.Linear(4, 1)
        self.opponent_hand_head = nn.Linear(3, 5)
        self.opponent_elixir_head = nn.Linear(3, 1)


def test_parameter_partition_separates_deployment_from_training_heads() -> None:
    model = _PartitionFixture()
    result = parameter_partition(model)  # type: ignore[arg-type]
    assert result["total_trainable"] == sum(p.numel() for p in model.parameters())
    assert result["deployable_actor_recurrent_action"] == 21
    assert result["training_only_privileged_critic"] == 12
    assert result["training_only_value_head"] == 5
    assert result["training_only_auxiliary_heads"] == 24
    assert result["training_only_total"] == 41


def test_select_entity_buckets_uses_packed_quantiles_and_maximum() -> None:
    counts = np.asarray([2, 4, 6, 8, 10, 12, 14, 16, 20, 30], dtype=np.int64)
    mask = np.arange(32)[None, :] < counts[:, None]
    buckets = select_entity_buckets(mask)
    assert [bucket.name for bucket in buckets] == [
        "small_p05",
        "median_p50",
        "p95",
        "crowded_max",
    ]
    assert [bucket.entity_count for bucket in buckets] == [4, 12, 30, 30]
    assert all(mask[bucket.row_index].sum() == bucket.entity_count for bucket in buckets)


def test_factorial_parameter_budget_is_matched_within_five_percent() -> None:
    budget = fresh_factorial_budget(
        current_client_f0_total=1_645_266,
        current_client_f0_deployable=1_052_770,
        d_model=128,
        memory_size=64,
    )
    assert budget["within_five_percent"] is True
    arms = budget["arms"]
    assert arms["F0_control"]["total_trainable_target"] == 1_645_266
    assert arms["F1_gate_positional_card"]["delta_vs_f0"] == 65
    assert arms["F2_control_timing_shared_pointer"]["delta_vs_f0"] == 24_316
    assert arms["F3_gate_shared_pointer"]["delta_vs_f0"] == 24_381
