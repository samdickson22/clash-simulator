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


def test_cuda_graph_runner_reset_validation_fails_closed() -> None:
    runner = object.__new__(SimpleCudaGraphRunner)
    runner.runtime = SimpleNamespace(
        device=torch.device("cpu"),
        batch_size=2,
        action_kernel=SimpleNamespace(catalog=SimpleNamespace(size=5)),
        spawn_blueprints=SimpleNamespace(
            public_card_mask=torch.tensor([False, True, True, True, True])
        ),
    )
    valid_mask = torch.tensor([True, False])
    valid_decks = torch.ones((2, 2, 8), dtype=torch.int64)

    runner._validate_reset_mask(valid_mask)
    runner._validate_reset_decks(valid_decks)
    with pytest.raises(ValueError, match=r"shape \[batch\]"):
        runner._validate_reset_mask(torch.zeros((2, 1), dtype=torch.bool))
    with pytest.raises(ValueError, match="runtime device"):
        runner._validate_reset_mask(torch.zeros(2, dtype=torch.bool, device="meta"))
    with pytest.raises(ValueError, match="must be bool"):
        runner._validate_reset_mask(torch.zeros(2, dtype=torch.int64))
    with pytest.raises(ValueError, match=r"shape \[batch, 2, 8\]"):
        runner._validate_reset_decks(torch.ones((2, 8), dtype=torch.int64))
    with pytest.raises(ValueError, match="runtime device"):
        runner._validate_reset_decks(
            torch.ones((2, 2, 8), dtype=torch.int64, device="meta")
        )
    with pytest.raises(ValueError, match="must be int64"):
        runner._validate_reset_decks(torch.ones((2, 2, 8), dtype=torch.int32))
    invalid_private_deck = valid_decks.clone()
    invalid_private_deck[1, 1, 7] = 0
    with pytest.raises(ValueError, match="public catalog rows"):
        runner._validate_reset_decks(invalid_private_deck)


def test_cuda_graph_runner_reset_replays_stable_cpu_test_doubles() -> None:
    class ReplayCounter:
        def __init__(self) -> None:
            self.calls = 0

        def replay(self) -> None:
            self.calls += 1

    runner = object.__new__(SimpleCudaGraphRunner)
    runner.runtime = SimpleNamespace(
        device=torch.device("cpu"),
        batch_size=2,
        action_kernel=SimpleNamespace(catalog=SimpleNamespace(size=9)),
        spawn_blueprints=None,
    )
    runner._reset_mask = torch.ones(2, dtype=torch.bool)
    runner._reset_deck_ids = torch.zeros((2, 2, 8), dtype=torch.int64)
    runner._reset_graph = ReplayCounter()  # type: ignore[assignment]
    runner._reset_with_decks_graph = ReplayCounter()  # type: ignore[assignment]
    runner._reset_observation = SimpleNamespace(kind="default")
    runner._reset_with_decks_observation = SimpleNamespace(kind="decks")

    all_false = torch.zeros(2, dtype=torch.bool)
    result = runner.reset_rows(all_false)
    assert result is runner._reset_observation
    assert torch.equal(runner._reset_mask, all_false)
    assert runner._reset_graph.calls == 1  # type: ignore[attr-defined]
    assert runner._reset_with_decks_graph.calls == 0  # type: ignore[attr-defined]

    selected = torch.tensor([True, False])
    decks = torch.arange(32, dtype=torch.int64).view(2, 2, 8)
    result = runner.reset_rows(selected, deck_ids=decks)
    assert result is runner._reset_with_decks_observation
    assert torch.equal(runner._reset_mask, selected)
    assert torch.equal(runner._reset_deck_ids, decks)
    assert runner._reset_graph.calls == 1  # type: ignore[attr-defined]
    assert runner._reset_with_decks_graph.calls == 1  # type: ignore[attr-defined]


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
    _assert_tensor_fields_equal(left.triggered_events, right.triggered_events)
    _assert_tensor_fields_equal(left.triggered_effects, right.triggered_effects)
    assert torch.equal(
        left._triggered_death_stable_id,
        right._triggered_death_stable_id,
    )
    assert torch.equal(left._travel_spawned, right._travel_spawned)
    assert torch.equal(left._travel_interrupted, right._travel_interrupted)
    assert torch.equal(
        left.travel_effect_consume_source_id,
        right.travel_effect_consume_source_id,
    )
    for name in ("_entity_special", "_entity_invisible", "_entity_hidden"):
        assert torch.equal(getattr(left, name), getattr(right, name))


def _assert_reset_planes_equal(left: Any, right: Any) -> None:
    owners = {
        "state": "state",
        "action": "action_state",
        "effects": "effects",
        "travel": "travel",
        "travel_effects": "travel_effects",
        "death_effects": "death_effects",
        "triggered_events": "triggered_events",
        "triggered_effects": "triggered_effects",
        "death_bursts": "death_bursts",
        "payload_containers": "payload_containers",
        "positive_buff_areas": "positive_buff_areas",
        "positive_buffs": "positive_buffs",
        "lifecycle": "lifecycle",
        "modifiers": "modifiers",
        "damage_ramp": "damage_ramp",
        "rolling_spells": "rolling_spells",
        "navigation": "combat.navigation.state",
        "policy_mechanics": "policy_mechanics",
        "abilities": "abilities",
        "outcomes": "outcomes",
        "attack_locks": "attack_locks",
        "river_jumps": "river_jumps",
        "periodic_spawns": "periodic_spawns",
        "scheduled_casts": "scheduled_casts",
    }

    def resolve(value: Any, path: str) -> Any:
        for part in path.split("."):
            value = getattr(value, part)
        return value

    for group, path in owners.items():
        if group not in left._initial_templates:
            continue
        left_owner = resolve(left, path)
        right_owner = resolve(right, path)
        assert left_owner is not None
        assert right_owner is not None
        for name in left._initial_templates[group]:
            assert torch.equal(getattr(left_owner, name), getattr(right_owner, name))
    private_runtime_names = {
        "travel_spawned": "_travel_spawned",
        "travel_interrupted": "_travel_interrupted",
        "triggered_death_stable_id": "_triggered_death_stable_id",
        "projection_hand_ids": "_projection_hand_ids",
        "double_elixir": "_double_elixir",
        "triple_elixir": "_triple_elixir",
        "ability_cooldown": "_ability_cooldown",
        "ability_duration": "_ability_duration",
        "refill_cooldown_ms": "_refill_cooldown_ms",
        "entity_special": "_entity_special",
        "entity_invisible": "_entity_invisible",
        "entity_hidden": "_entity_hidden",
    }
    for name in left._initial_templates["runtime"]:
        if name == "public_visibility":
            left_value = left.projector.inputs.public_visibility
            right_value = right.projector.inputs.public_visibility
        elif name == "combat_spawned_mask":
            left_value = left.combat.spawned_mask
            right_value = right.combat.spawned_mask
        elif name == "combat_target_unavailable":
            left_value = left.combat._target_unavailable
            right_value = right.combat._target_unavailable
        else:
            attribute = private_runtime_names.get(name, name)
            left_value = getattr(left, attribute)
            right_value = getattr(right, attribute)
        assert torch.equal(left_value, right_value)


def _assert_observations_equal(left: Any, right: Any) -> None:
    _assert_tensor_fields_equal(left.actor, right.actor)
    assert (left.critic is None) == (right.critic is None)
    if left.critic is not None and right.critic is not None:
        _assert_tensor_fields_equal(left.critic, right.critic)
    assert torch.equal(left.legal_mask, right.legal_mask)


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


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_cuda_graph_runner_captured_reset_parity_and_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decks = supported_simple_decks(
        [list(deck) for deck in load_deck_pool("decks.json")],
        device="cuda",
    )
    kwargs: Any = {
        "seed": 202_608_266,
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

    for _ in range(2):
        actions = select_actions(observation.legal_mask, "first-legal")
        reference_actions = select_actions(
            reference_observation.legal_mask,
            "first-legal",
        )
        assert torch.equal(actions, reference_actions)
        observation = runner.step_tick(actions).observation
        reference_observation = reference.step_tick(reference_actions).observation

    ordered_decks = torch.cat(
        (runtime.action_state.hand_ids, runtime.action_state.cycle_ids),
        dim=2,
    )
    alternate_decks = ordered_decks.flip(2).contiguous()
    all_false = torch.zeros(2, dtype=torch.bool, device=runtime.device)

    def forbidden_eager_reset(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("captured runner reset delegated to eager runtime reset")

    monkeypatch.setattr(runtime, "reset_rows", forbidden_eager_reset)

    no_op_reset = runner.reset_rows(all_false)
    reference_no_op = reference.reset_rows(all_false)
    torch.cuda.synchronize(runtime.device)
    _assert_observations_equal(no_op_reset, reference_no_op)
    _assert_reset_planes_equal(runtime, reference)

    no_op_deck_reset = runner.reset_rows(all_false, deck_ids=alternate_decks)
    reference_no_op_deck = reference.reset_rows(
        all_false,
        deck_ids=alternate_decks,
    )
    torch.cuda.synchronize(runtime.device)
    _assert_observations_equal(no_op_deck_reset, reference_no_op_deck)
    _assert_reset_planes_equal(runtime, reference)

    reset_first = torch.tensor([True, False], device=runtime.device)
    first_observation = runner.reset_rows(reset_first, deck_ids=alternate_decks)
    reference_first = reference.reset_rows(reset_first, deck_ids=alternate_decks)
    torch.cuda.synchronize(runtime.device)
    _assert_observations_equal(first_observation, reference_first)
    _assert_reset_planes_equal(runtime, reference)
    assert torch.equal(
        runtime.action_state.hand_ids[0],
        alternate_decks[0, :, :4],
    )

    actions = select_actions(first_observation.legal_mask, "first-legal")
    reference_actions = select_actions(reference_first.legal_mask, "first-legal")
    assert torch.equal(actions, reference_actions)
    after_reset = runner.step_tick(actions)
    reference_after_reset = reference.step_tick(reference_actions)
    torch.cuda.synchronize(runtime.device)
    _assert_observations_equal(
        after_reset.observation, reference_after_reset.observation
    )
    _assert_reset_planes_equal(runtime, reference)

    reset_second = torch.tensor([False, True], device=runtime.device)
    second_observation = runner.reset_rows(reset_second)
    reference_second = reference.reset_rows(reset_second)
    torch.cuda.synchronize(runtime.device)
    _assert_observations_equal(second_observation, reference_second)
    _assert_reset_planes_equal(runtime, reference)

    rotated_decks = alternate_decks.roll(1, dims=2)
    final_observation = runner.reset_rows(reset_first, deck_ids=rotated_decks)
    reference_final = reference.reset_rows(reset_first, deck_ids=rotated_decks)
    torch.cuda.synchronize(runtime.device)
    _assert_observations_equal(final_observation, reference_final)
    _assert_reset_planes_equal(runtime, reference)
