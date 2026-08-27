from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace
from typing import Any

import pytest
import torch

from clasher.rl.deck_pool import load_deck_pool
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_reward_v2 import SimpleRewardV2Config
from clasher.torch_sim.simple_rollout import SimpleGymRolloutBridge
from clasher.torch_sim.simple_standard import (
    STANDARD_REGULATION_TICK,
    STANDARD_TIEBREAK_TICK,
)
from scripts.validate_simple_full_matches import (
    build_simple_runtime,
    select_actions,
    supported_simple_decks,
)


def test_cuda_graph_runner_rejects_cpu_runtime() -> None:
    runtime = SimpleNamespace(device=torch.device("cpu"), batch_size=1)
    actions = torch.zeros((1, 2), dtype=torch.int64)

    with pytest.raises(ValueError, match="requires a CUDA runtime"):
        SimpleCudaGraphRunner(runtime, actions)  # type: ignore[arg-type]


def _assert_tensor_fields_equal(left: Any, right: Any) -> None:
    for descriptor in fields(left):
        left_value = getattr(left, descriptor.name)
        if isinstance(left_value, torch.Tensor):
            assert torch.equal(left_value, getattr(right, descriptor.name))


def _assert_status_planes_equal(left: Any, right: Any) -> None:
    for name in (
        "entity_status_kind",
        "entity_status_ticks",
        "entity_slow_ticks",
        "entity_attack_clock_fraction",
    ):
        assert torch.equal(getattr(left, name), getattr(right, name))


def _assert_policy_planes_equal(left: Any, right: Any) -> None:
    _assert_tensor_fields_equal(left.policy_mechanics, right.policy_mechanics)
    _assert_tensor_fields_equal(left.abilities, right.abilities)
    _assert_tensor_fields_equal(left.travel, right.travel)
    _assert_tensor_fields_equal(left.travel_effects, right.travel_effects)
    assert torch.equal(left._travel_spawned, right._travel_spawned)
    assert torch.equal(left._travel_interrupted, right._travel_interrupted)
    assert torch.equal(
        left.travel_effect_consume_source_id,
        right.travel_effect_consume_source_id,
    )
    for name in ("_entity_special", "_entity_invisible", "_entity_hidden"):
        assert torch.equal(getattr(left, name), getattr(right, name))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_cuda_graph_runner_matches_eager_replays() -> None:
    decks = supported_simple_decks(
        [list(deck) for deck in load_deck_pool("decks.json")],
        device="cuda",
    )
    kwargs: Any = {
        "seed": 202_608_264,
        "decks": decks,
        "batch_size": 2,
        "device": "cuda",
        "max_entities": 32,
        "max_effects": 32,
        "regulation_ticks": STANDARD_REGULATION_TICK,
        "tiebreak_ticks": STANDARD_TIEBREAK_TICK,
        "supported_only": True,
    }
    runtime = build_simple_runtime(**kwargs)
    reference = build_simple_runtime(**kwargs)
    observation = runtime.observe()
    reference_observation = reference.observe()
    example = select_actions(observation.legal_mask, "first-legal")
    runner = SimpleCudaGraphRunner(runtime, example)

    for _ in range(3):
        actions = select_actions(observation.legal_mask, "first-legal")
        reference_actions = select_actions(
            reference_observation.legal_mask, "first-legal"
        )
        assert torch.equal(actions, reference_actions)
        step = runner.step_tick(actions)
        reference_step = reference.step_tick(reference_actions)
        torch.cuda.synchronize(runtime.device)

        _assert_tensor_fields_equal(runtime.state, reference.state)
        _assert_tensor_fields_equal(
            runtime.combat.navigation.state,
            reference.combat.navigation.state,
        )
        _assert_tensor_fields_equal(runtime.action_state, reference.action_state)
        _assert_status_planes_equal(runtime, reference)
        _assert_policy_planes_equal(runtime, reference)
        assert torch.equal(step.reward, reference_step.reward)
        assert torch.equal(step.done, reference_step.done)
        assert step.travel is not None
        assert reference_step.travel is not None
        _assert_tensor_fields_equal(step.travel, reference_step.travel)
        _assert_tensor_fields_equal(step.travel.view, reference_step.travel.view)
        _assert_tensor_fields_equal(step.travel.impact, reference_step.travel.impact)
        assert step.travel_effect_allocation is not None
        assert reference_step.travel_effect_allocation is not None
        _assert_tensor_fields_equal(
            step.travel_effect_allocation,
            reference_step.travel_effect_allocation,
        )
        assert step.travel_effects is not None
        assert reference_step.travel_effects is not None
        _assert_tensor_fields_equal(step.travel_effects, reference_step.travel_effects)
        assert step.travel_impulse is not None
        assert reference_step.travel_impulse is not None
        _assert_tensor_fields_equal(step.travel_impulse, reference_step.travel_impulse)
        assert torch.equal(
            step.observation.actor.entity_ids,
            reference_step.observation.actor.entity_ids,
        )
        assert torch.equal(
            step.observation.actor.entity_features,
            reference_step.observation.actor.entity_features,
        )
        assert torch.equal(
            step.observation.legal_mask,
            reference_step.observation.legal_mask,
        )
        observation = step.observation
        reference_observation = reference_step.observation


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_cuda_graph_runner_matches_interval_bridge_and_reset() -> None:
    decks = supported_simple_decks(
        [list(deck) for deck in load_deck_pool("decks.json")],
        device="cuda",
    )
    kwargs: Any = {
        "seed": 202_608_265,
        "decks": decks,
        "batch_size": 2,
        "device": "cuda",
        "max_entities": 32,
        "max_effects": 32,
        "regulation_ticks": STANDARD_REGULATION_TICK,
        "tiebreak_ticks": STANDARD_TIEBREAK_TICK,
        "supported_only": True,
    }
    runtime = build_simple_runtime(**kwargs)
    reference = build_simple_runtime(**kwargs)
    no_op = torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    runner = SimpleCudaGraphRunner(runtime, no_op)
    reward = SimpleRewardV2Config(gamma=0.995)
    bridge = SimpleGymRolloutBridge(
        runner,
        decision_interval=8,
        reward_v2_config=reward,
        strict_reset_check=False,
    )
    reference_bridge = SimpleGymRolloutBridge(
        reference,
        decision_interval=8,
        reward_v2_config=reward,
        strict_reset_check=False,
    )
    runtime.state.hp[0, 2] = 0.0
    reference.state.hp[0, 2] = 0.0

    step = bridge.step(no_op)
    reference_step = reference_bridge.step(no_op)
    torch.cuda.synchronize(runtime.device)
    for name in (
        "rewards",
        "done",
        "winner",
        "action_success",
        "native_ticks",
        "committed",
    ):
        assert torch.equal(getattr(step, name), getattr(reference_step, name))
    _assert_tensor_fields_equal(step.actor, reference_step.actor)
    _assert_tensor_fields_equal(step.next_actor, reference_step.next_actor)
    assert torch.equal(step.legal_mask, reference_step.legal_mask)
    assert torch.equal(step.next_legal_mask, reference_step.next_legal_mask)
    _assert_tensor_fields_equal(runtime.state, reference.state)
    _assert_tensor_fields_equal(
        runtime.combat.navigation.state,
        reference.combat.navigation.state,
    )
    _assert_tensor_fields_equal(runtime.action_state, reference.action_state)
    _assert_status_planes_equal(runtime, reference)
    _assert_policy_planes_equal(runtime, reference)

    reset = bridge.reset_done(step.done)
    reference_reset = reference_bridge.reset_done(reference_step.done)
    torch.cuda.synchronize(runtime.device)
    _assert_tensor_fields_equal(reset.actor, reference_reset.actor)
    assert torch.equal(reset.legal_mask, reference_reset.legal_mask)
    _assert_tensor_fields_equal(runtime.state, reference.state)
    _assert_tensor_fields_equal(
        runtime.combat.navigation.state,
        reference.combat.navigation.state,
    )
    _assert_tensor_fields_equal(runtime.action_state, reference.action_state)
    _assert_status_planes_equal(runtime, reference)
    _assert_policy_planes_equal(runtime, reference)

    second = bridge.step(no_op)
    reference_second = reference_bridge.step(no_op)
    torch.cuda.synchronize(runtime.device)
    assert torch.equal(second.rewards, reference_second.rewards)
    assert torch.equal(second.done, reference_second.done)
    _assert_tensor_fields_equal(second.next_actor, reference_second.next_actor)
    _assert_tensor_fields_equal(runtime.state, reference.state)
    _assert_tensor_fields_equal(
        runtime.combat.navigation.state,
        reference.combat.navigation.state,
    )
    _assert_status_planes_equal(runtime, reference)
    _assert_policy_planes_equal(runtime, reference)
