from __future__ import annotations

from dataclasses import dataclass

import pytest
import torch

from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.resident_outputs import (
    TensorPrivilegedCriticObservation,
    TensorPublicStructuredObservation,
)
from clasher.torch_sim.simple_adapter import (
    SimpleGymAdapter,
    SimpleGymContractError,
    SimpleGymObservation,
    SimpleGymStepResult,
)


@dataclass(frozen=True)
class _Observation:
    actor: TensorPublicStructuredObservation
    critic: TensorPrivilegedCriticObservation | None
    legal_mask: torch.Tensor


@dataclass(frozen=True)
class _Step:
    observation: _Observation
    action_success: torch.Tensor
    reward: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor
    native_ticks: torch.Tensor
    committed: torch.Tensor


class _FakeEngine:
    device = torch.device("cpu")
    batch_size = 2

    def __init__(self) -> None:
        self.calls = 0
        self.observation = _Observation(
            actor=TensorPublicStructuredObservation(
                entity_ids=torch.zeros((2, 2, 3), dtype=torch.int64),
                entity_features=torch.zeros((2, 2, 3, 4)),
                entity_mask=torch.ones((2, 2, 3), dtype=torch.bool),
                hand_ids=torch.zeros((2, 2, 5), dtype=torch.int64),
                global_features=torch.zeros((2, 2, 6)),
            ),
            critic=TensorPrivilegedCriticObservation(
                entity_ids=torch.zeros((2, 2, 3), dtype=torch.int64),
                entity_features=torch.zeros((2, 2, 3, 5)),
                entity_mask=torch.ones((2, 2, 3), dtype=torch.bool),
                card_ids=torch.zeros((2, 2, 10), dtype=torch.int64),
                global_features=torch.zeros((2, 2, 7)),
            ),
            legal_mask=torch.ones((2, 2, 9), dtype=torch.bool),
        )

    def observe(self) -> SimpleGymObservation:
        return self.observation

    def step_tick(self, action_ids: torch.Tensor) -> SimpleGymStepResult:
        self.calls += 1
        return _Step(
            observation=self.observation,
            action_success=torch.ones((2, 2), dtype=torch.bool),
            reward=torch.tensor([[0.25, -0.25], [1.0, -1.0]]),
            done=torch.tensor([False, True]),
            winner=torch.tensor([-1, 0], dtype=torch.int64),
            native_ticks=torch.ones(2, dtype=torch.int64),
            committed=torch.ones(2, dtype=torch.bool),
        )


def test_fake_engine_maps_public_private_transition_and_history() -> None:
    engine = _FakeEngine()
    adapter = SimpleGymAdapter(engine, no_op_action=8)
    actions = torch.tensor([[1, 2], [3, 4]], dtype=torch.int64)
    public_masks = torch.ones((2, 2, 9), dtype=torch.bool)

    result = adapter.step(
        actions,
        recurrent_inputs={"hidden": torch.zeros((2, 2, 4))},
        public_action_masks=public_masks,
        public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
    )

    assert result.transition.actor is engine.observation.actor
    assert result.transition.critic is engine.observation.critic
    assert not hasattr(result.transition.actor, "card_ids")
    assert result.legal_mask is engine.observation.legal_mask
    assert result.transition.public_action_masks is public_masks
    assert result.action_success.shape == (2, 2)
    assert result.rewards.shape == (2, 2)
    assert result.dones.shape == (2,)
    assert result.history_before.previous_actions.tolist() == [[8, 8], [8, 8]]
    assert result.history_after.previous_actions.tolist() == [[1, 2], [8, 8]]
    assert result.history_after.previous_rewards.tolist() == [
        [0.25, -0.25],
        [0.0, 0.0],
    ]
    assert result.history_after.episode_starts.tolist() == [
        [False, False],
        [True, True],
    ]
    assert result.admission.fallback_rows == ()
    assert result.admission.all_rows_admitted


def test_v1_public_mask_fails_closed_before_engine_mutation() -> None:
    engine = _FakeEngine()
    adapter = SimpleGymAdapter(engine, no_op_action=8)

    with pytest.raises(SimpleGymContractError, match="contract v2 only"):
        adapter.step(
            torch.zeros((2, 2), dtype=torch.int64),
            public_action_masks=torch.ones((2, 2, 9), dtype=torch.bool),
            public_action_mask_contract_version=1,
        )

    assert engine.calls == 0
