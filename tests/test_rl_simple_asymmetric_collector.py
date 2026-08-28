from __future__ import annotations

import hashlib
from dataclasses import fields
from typing import ClassVar

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.rl.simple_asymmetric_collector import (
    SIMPLE_ALTERNATING_LEARNER_SEAT_PROFILE,
    SimpleTensorAsymmetricCollector,
    alternating_learner_seats,
)
from clasher.rl.simple_tensor_collector import (
    SimplePublicActionMaskV2,
    SimpleTensorCollectorError,
    SimpleTensorMaskRequest,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_outputs import (
    TensorPrivilegedCriticObservation,
    TensorPublicStructuredObservation,
)
from clasher.torch_sim.simple_outcomes import FastMatchRules
from clasher.torch_sim.simple_reward_v2 import SimpleRewardV2Config
from clasher.torch_sim.simple_rollout import (
    SimpleGymRolloutBridge,
    SimpleGymRolloutObservation,
)
from clasher.torch_sim.simple_standard import compile_standard_simple_setup


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _bridge(device_name: str = "cpu") -> SimpleGymRolloutBridge:
    device = _device(device_name)
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("Knight", "Archers"),
        device=device,
        canonical_lane_globals=True,
    )
    fast = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((5, fast.size), dtype=torch.int64, device=setup.device)
    hand = torch.zeros(fast.size, dtype=torch.int64, device=setup.device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id].detach().cpu())
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id].detach().cpu()):
            hand[card_id] = 2_000 + card_id
    decks = [[("Knight",) * 8, ("Archers",) * 8]] * 2
    runtime = setup.create_runtime(
        decks,
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        max_entities=24,
        max_effects=16,
        include_privileged_critic=True,
    )
    runtime.outcomes.rules = FastMatchRules(regulation_ticks=20, tiebreak_ticks=80)
    runtime.state.hp[0, 2] = 0.0
    return SimpleGymRolloutBridge(
        runtime,
        decision_interval=2,
        reward_v2_config=SimpleRewardV2Config(gamma=0.995),
        strict_reset_check=False,
    )


class _TestPublicMask:
    semantics: ClassVar[dict[str, object]] = {
        "schema": "test.stationary-ownership.public-mask-v2",
        "simulator_mask_reference_only": True,
    }

    def __call__(self, request: SimpleTensorMaskRequest) -> SimplePublicActionMaskV2:
        return SimplePublicActionMaskV2(
            masks=request.observation.legal_mask.clone(),
            semantics_id="test-stationary-ownership-mask-v2",
            semantics=self.semantics,
        )


class _Policy:
    def __init__(self, *, no_op: bool, increment: float) -> None:
        self.no_op = no_op
        self.increment = increment

    def __call__(
        self,
        boundary: SimpleTensorPolicyBoundary,
    ) -> SimpleTensorPolicyDecision:
        if boundary.recurrent_inputs is None:
            raise AssertionError("test policy requires recurrent state")
        hidden = boundary.recurrent_inputs["hidden"]
        if self.no_op:
            actions = torch.full(
                hidden.shape[:2],
                NO_OP_ACTION,
                dtype=torch.int64,
                device=hidden.device,
            )
        else:
            actions = boundary.public_action_masks.to(torch.int64).argmax(dim=2)
        return SimpleTensorPolicyDecision(
            actions=actions,
            next_recurrent_inputs={"hidden": hidden + self.increment},
            storage={
                "log_prob": torch.full_like(hidden[..., 0], -self.increment),
                "value": hidden[..., 0].clone(),
            },
        )


def _python_select(value: torch.Tensor, seats: tuple[int, ...]) -> torch.Tensor:
    return torch.stack(
        [value[row, seat] for row, seat in enumerate(seats)],
        dim=0,
    ).unsqueeze(1)


def _hash_tensors(values: list[torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for value in values:
        contiguous = value.detach().cpu().contiguous()
        digest.update(str(tuple(contiguous.shape)).encode())
        digest.update(str(contiguous.dtype).encode())
        digest.update(contiguous.numpy().tobytes())
    return digest.hexdigest()


def _python_stationary_ownership_digest(
    bridge: SimpleGymRolloutBridge,
    *,
    steps: int,
    learner_policy: _Policy,
    opponent_policy: _Policy,
    learner_state: dict[str, torch.Tensor],
    opponent_state: dict[str, torch.Tensor],
) -> str:
    """Independent row-loop oracle for Python stationary-collector ownership."""

    learner_seats = (0, 1)
    opponent_seats = (1, 0)
    values: list[torch.Tensor] = []
    for decision_index in range(steps):
        observation = bridge.observe()
        packet = _TestPublicMask()(
            SimpleTensorMaskRequest(observation, decision_index, False)
        )

        def boundary(
            current_observation: SimpleGymRolloutObservation,
            current_packet: SimplePublicActionMaskV2,
            current_decision_index: int,
            seats: tuple[int, ...],
            state: dict[str, torch.Tensor],
            *,
            critic: bool,
        ) -> SimpleTensorPolicyBoundary:
            actor = TensorPublicStructuredObservation(
                **{
                    descriptor.name: _python_select(
                        getattr(current_observation.actor, descriptor.name), seats
                    )
                    for descriptor in fields(TensorPublicStructuredObservation)
                }
            )
            critic_value = None
            if critic:
                assert current_observation.critic is not None
                critic_value = TensorPrivilegedCriticObservation(
                    **{
                        descriptor.name: _python_select(
                            getattr(current_observation.critic, descriptor.name), seats
                        )
                        for descriptor in fields(TensorPrivilegedCriticObservation)
                    }
                )
            return SimpleTensorPolicyBoundary(
                actor=actor,
                critic=critic_value,
                legal_mask=_python_select(current_observation.legal_mask, seats),
                public_action_masks=_python_select(current_packet.masks, seats),
                previous_actions=_python_select(
                    current_observation.previous_actions, seats
                ),
                previous_rewards=_python_select(
                    current_observation.previous_rewards, seats
                ),
                episode_starts=_python_select(
                    current_observation.episode_starts, seats
                ),
                recurrent_inputs=state,
                decision_index=current_decision_index,
            )

        learner_boundary = boundary(
            observation,
            packet,
            decision_index,
            learner_seats,
            learner_state,
            critic=True,
        )
        opponent_boundary = boundary(
            observation,
            packet,
            decision_index,
            opponent_seats,
            opponent_state,
            critic=False,
        )
        learner = learner_policy(learner_boundary)
        opponent = opponent_policy(opponent_boundary)
        joint = torch.empty((2, 2), dtype=torch.int64, device=bridge.device)
        for row, learner_seat in enumerate(learner_seats):
            joint[row, learner_seat] = learner.actions[row, 0]
            joint[row, 1 - learner_seat] = opponent.actions[row, 0]
        step = bridge.step(
            joint,
            public_action_masks=packet.masks,
            public_action_mask_contract_version=2,
            pre_action_boundary=observation,
        )
        values.extend(
            (
                learner_boundary.actor.entity_ids,
                learner_boundary.public_action_masks,
                learner_boundary.previous_actions,
                learner_boundary.previous_rewards,
                learner_boundary.episode_starts,
                learner.actions,
                _python_select(step.rewards, learner_seats),
                step.done,
                opponent.actions,
            )
        )
        learner_state = dict(learner.next_recurrent_inputs or {})
        opponent_state = dict(opponent.next_recurrent_inputs or {})
        bridge.reset_done(step.done)
    return _hash_tensors(values)


def test_asymmetric_collector_matches_python_stationary_ownership_hash() -> None:
    actual_bridge = _bridge()
    reference_bridge = _bridge()
    learner_policy = _Policy(no_op=False, increment=1.0)
    opponent_policy = _Policy(no_op=True, increment=10.0)
    learner_state = {"hidden": torch.zeros((2, 1, 3))}
    opponent_state = {"hidden": torch.zeros((2, 1, 3))}
    collector = SimpleTensorAsymmetricCollector(
        actual_bridge,
        public_mask_provider=_TestPublicMask(),
        learner_policy=learner_policy,
        opponent_policy=opponent_policy,
        learner_seats=alternating_learner_seats(2, device="cpu"),
        opponent_contract_id="test-frozen-opponent-v1",
        opponent_contract={"kind": "checkpoint", "sha256": "1" * 64},
        strict_host_validation=True,
    )

    actual = collector.collect(
        3,
        learner_recurrent_inputs={"hidden": learner_state["hidden"].clone()},
        opponent_recurrent_inputs={"hidden": opponent_state["hidden"].clone()},
    )
    actual_values: list[torch.Tensor] = []
    for step in range(3):
        actual_values.extend(
            (
                actual.learner.actor.entity_ids[step],
                actual.learner.public_action_masks[step],
                actual.learner.previous_actions[step],
                actual.learner.previous_rewards[step],
                actual.learner.episode_starts[step],
                actual.learner.actions[step],
                actual.learner.rewards[step],
                actual.learner.done[step],
                actual.opponent_actions[step],
            )
        )
    expected_digest = _python_stationary_ownership_digest(
        reference_bridge,
        steps=3,
        learner_policy=learner_policy,
        opponent_policy=opponent_policy,
        learner_state={"hidden": learner_state["hidden"].clone()},
        opponent_state={"hidden": opponent_state["hidden"].clone()},
    )

    actual_digest = _hash_tensors(actual_values)
    assert actual_digest == expected_digest
    assert actual_digest == (
        "7c29456d6bdcdc3d489c4712d78d480efb8dcbfd96523e8c17b6cdd5cc80b8ba"
    )
    assert actual.learner.actions.shape == (3, 2, 1)
    assert actual.learner.done.tolist() == [
        [True, False],
        [False, False],
        [False, False],
    ]
    assert actual.learner.episode_starts[1, 0, 0]
    assert not actual.learner.episode_starts[1, 1, 0]
    assert actual.opponent_bootstrap.recurrent_inputs is not None
    assert actual.opponent_bootstrap.recurrent_inputs["hidden"].eq(30.0).all()
    assert actual.learner.bootstrap.recurrent_inputs is not None
    assert actual.learner.bootstrap.recurrent_inputs["hidden"].eq(3.0).all()
    assert actual.metadata.learner_seat_profile == (
        SIMPLE_ALTERNATING_LEARNER_SEAT_PROFILE
    )
    assert actual.learner.all_rows_admitted.all()
    assert actual.learner.committed.all()
    assert not actual.learner.fallback_rows.any()


def test_asymmetric_collector_rejects_nonalternating_seats() -> None:
    bridge = _bridge()
    with pytest.raises(SimpleTensorCollectorError, match="alternate"):
        SimpleTensorAsymmetricCollector(
            bridge,
            public_mask_provider=_TestPublicMask(),
            learner_policy=_Policy(no_op=True, increment=1.0),
            opponent_policy=_Policy(no_op=True, increment=1.0),
            learner_seats=torch.zeros(2, dtype=torch.int64),
            opponent_contract_id="test",
            opponent_contract={"kind": "noop"},
        )


def test_asymmetric_collector_rejects_public_masked_opponent_action() -> None:
    bridge = _bridge()

    class InvalidPolicy:
        def __call__(
            self,
            boundary: SimpleTensorPolicyBoundary,
        ) -> SimpleTensorPolicyDecision:
            return SimpleTensorPolicyDecision(
                actions=torch.full(
                    (2, 1),
                    boundary.public_action_masks.shape[2] - 1,
                    dtype=torch.int64,
                )
            )

    collector = SimpleTensorAsymmetricCollector(
        bridge,
        public_mask_provider=_TestPublicMask(),
        learner_policy=_Policy(no_op=True, increment=1.0),
        opponent_policy=InvalidPolicy(),
        learner_seats=alternating_learner_seats(2, device="cpu"),
        opponent_contract_id="test",
        opponent_contract={"kind": "invalid"},
        strict_host_validation=True,
    )
    tick_before = bridge.runtime.state.tick.clone()

    with pytest.raises(SimpleTensorCollectorError, match="opponent selected"):
        collector.collect(
            1,
            learner_recurrent_inputs={"hidden": torch.zeros((2, 1, 3))},
        )

    assert torch.equal(bridge.runtime.state.tick, tick_before)
