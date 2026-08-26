from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.simple_adapter import (
    SIMPLIFIED_GYM_ACTION_MASK_PROFILE,
    SimpleGymContractError,
)
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_rollout import (
    SimpleGymRolloutBridge,
    SimpleGymRolloutObservation,
    SimpleGymRolloutStep,
)
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def _bridge(device_name: str) -> tuple[SimpleGymRolloutBridge, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    full = TensorCardCatalog.compile(
        BattleState().card_loader, ["Knight", "Archers"], device=device
    )
    catalog = FastCardCatalog.from_tensor_catalog(full)
    ids = {name: full.name_to_id[name] for name in ("Knight", "Archers")}
    decks = torch.full((2, 2, 8), ids["Knight"], dtype=torch.int64, device=device)
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), ids["Knight"], dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.tensor(
            [[2_000.0, 2_000.0, 3_000.0], [2_000.0, 2_000.0, 3_000.0]],
            device=device,
        ),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    entity_lookup = torch.zeros((2, catalog.size), dtype=torch.int64, device=device)
    entity_lookup[0, ids["Knight"]] = 101
    entity_lookup[0, ids["Archers"]] = 102
    entity_lookup[1, ids["Knight"]] = 201
    entity_lookup[1, ids["Archers"]] = 202
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device) + 100
    runtime = SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=20, tiebreak_ticks=40),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=14,
        max_effects=8,
        include_privileged_critic=True,
    )
    return SimpleGymRolloutBridge(runtime), ids


def _placement_actions(bridge: SimpleGymRolloutBridge) -> torch.Tensor:
    tile = 14 * BOARD_WIDTH + 8
    return torch.full(
        (bridge.batch_size, 2), tile, dtype=torch.int64, device=bridge.device
    )


def _assert_structured_equal(actual: object, expected: object) -> None:
    assert type(actual) is type(expected)
    if actual is None:
        return
    for descriptor in fields(actual):
        assert torch.equal(
            getattr(actual, descriptor.name), getattr(expected, descriptor.name)
        ), descriptor.name


def _assert_rollout_equal(
    actual: SimpleGymRolloutObservation,
    expected: SimpleGymRolloutObservation,
) -> None:
    _assert_structured_equal(actual.actor, expected.actor)
    _assert_structured_equal(actual.critic, expected.critic)
    for name in (
        "legal_mask",
        "previous_actions",
        "previous_rewards",
        "episode_starts",
    ):
        assert torch.equal(getattr(actual, name), getattr(expected, name)), name
    if actual.public_action_masks is None:
        assert expected.public_action_masks is None
    else:
        assert expected.public_action_masks is not None
        assert torch.equal(actual.public_action_masks, expected.public_action_masks)
    assert (
        actual.public_action_mask_contract_version
        == expected.public_action_mask_contract_version
    )
    assert (
        actual.simulator_action_mask_profile == expected.simulator_action_mask_profile
    )
    if isinstance(actual, SimpleGymRolloutStep):
        assert isinstance(expected, SimpleGymRolloutStep)
        for name in (
            "rewards",
            "done",
            "winner",
            "action_success",
            "native_ticks",
            "committed",
            "fallback_rows",
            "all_rows_admitted",
        ):
            assert torch.equal(getattr(actual, name), getattr(expected, name)), name


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_mixed_terminal_reset_new_deck_preserves_unselected_history(
    device_name: str,
) -> None:
    bridge, ids = _bridge(device_name)
    initial = bridge.observe()
    assert initial.episode_starts.all()
    first_actions = _placement_actions(bridge)
    first = bridge.step(first_actions)
    assert first.previous_actions.eq(NO_OP_ACTION).all()
    assert not first.fallback_rows.any()
    assert first.all_rows_admitted.all()
    assert first.public_action_mask_contract_version is None
    assert first.public_action_masks is None
    assert first.simulator_action_mask_profile == SIMPLIFIED_GYM_ACTION_MASK_PROFILE

    bridge.runtime.state.hp[0, 2] = 0.0
    second_actions = _placement_actions(bridge)
    terminal = bridge.step(second_actions)
    assert terminal.done.tolist() == [True, False]
    assert torch.equal(terminal.previous_actions, first_actions)
    assert terminal.critic is not None
    assert terminal.critic.entity_mask.shape[:2] == (bridge.batch_size, 2)

    history_before_reset = tuple(
        value[1].clone()
        for value in (
            bridge.adapter.history.previous_actions,
            bridge.adapter.history.previous_rewards,
            bridge.adapter.history.episode_starts,
        )
    )
    new_decks = torch.full(
        (bridge.batch_size, 2, 8),
        ids["Archers"],
        dtype=torch.int64,
        device=bridge.device,
    )
    reset = bridge.reset_done(
        torch.tensor([True, False], dtype=torch.bool, device=bridge.device),
        deck_ids=new_decks,
    )

    assert reset.previous_actions[0].eq(NO_OP_ACTION).all()
    assert reset.previous_rewards[0].eq(0).all()
    assert reset.episode_starts[0].all()
    for actual, expected in zip(
        (
            reset.previous_actions[1],
            reset.previous_rewards[1],
            reset.episode_starts[1],
        ),
        history_before_reset,
        strict=True,
    ):
        assert torch.equal(actual, expected)
    assert bridge.runtime.action_state.hand_ids[0].eq(ids["Archers"]).all()
    assert bridge.runtime.action_state.hand_ids[1].eq(ids["Knight"]).all()
    assert reset.actor.hand_ids[0].eq(ids["Archers"] + 100).all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_rollout_v1_mask_fails_closed_before_runtime_mutation(
    device_name: str,
) -> None:
    bridge, _ = _bridge(device_name)
    boundary = bridge.observe()
    tick_before = bridge.runtime.state.tick.clone()
    history_before = bridge.adapter.history

    with pytest.raises(SimpleGymContractError, match="contract v2 only"):
        bridge.step(
            _placement_actions(bridge),
            public_action_masks=boundary.legal_mask,
            public_action_mask_contract_version=1,
        )

    assert torch.equal(bridge.runtime.state.tick, tick_before)
    assert bridge.adapter.history is history_before


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_seedless_simple_rollout_is_deterministic_and_emits_fixed_telemetry(
    device_name: str,
) -> None:
    left, _ = _bridge(device_name)
    right, _ = _bridge(device_name)
    _assert_rollout_equal(left.observe(), right.observe())

    for index in range(4):
        left_actions = (
            _placement_actions(left)
            if index == 0
            else torch.full(
                (left.batch_size, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=left.device,
            )
        )
        right_actions = left_actions.clone()
        masks_left = left.observe().legal_mask.clone()
        masks_right = right.observe().legal_mask.clone()
        recurrent_left = {
            "hidden": torch.full(
                (left.batch_size, 2, 3),
                float(index),
                device=left.device,
            )
        }
        recurrent_right = {"hidden": recurrent_left["hidden"].clone()}
        step_left = left.step(
            left_actions,
            recurrent_inputs=recurrent_left,
            public_action_masks=masks_left,
            public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
        )
        step_right = right.step(
            right_actions,
            recurrent_inputs=recurrent_right,
            public_action_masks=masks_right,
            public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
        )
        _assert_rollout_equal(step_left, step_right)
        assert step_left.public_action_masks is masks_left
        assert step_left.public_action_mask_contract_version == 2
        assert step_left.simulator_action_mask_profile == (
            SIMPLIFIED_GYM_ACTION_MASK_PROFILE
        )
        assert step_left.fallback_rows.shape == (left.batch_size,)
        assert step_left.fallback_rows.dtype == torch.bool
        assert step_left.fallback_rows.device == left.device
        assert step_left.all_rows_admitted.shape == (left.batch_size,)
        assert step_left.all_rows_admitted.all()
        assert torch.equal(
            step_left.recurrent_inputs["hidden"], recurrent_left["hidden"]
        )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_adapter_history_reset_validates_mask_and_preserves_other_rows(
    device_name: str,
) -> None:
    bridge, _ = _bridge(device_name)
    bridge.step(_placement_actions(bridge))
    before = bridge.adapter.history
    reset_mask = torch.tensor([True, False], dtype=torch.bool, device=bridge.device)
    after = bridge.adapter.reset_history_rows(reset_mask)

    assert after.previous_actions[0].eq(NO_OP_ACTION).all()
    assert after.previous_rewards[0].eq(0).all()
    assert after.episode_starts[0].all()
    assert torch.equal(after.previous_actions[1], before.previous_actions[1])
    assert torch.equal(after.previous_rewards[1], before.previous_rewards[1])
    assert torch.equal(after.episode_starts[1], before.episode_starts[1])
    with pytest.raises(SimpleGymContractError, match="reset_mask"):
        bridge.adapter.reset_history_rows(
            torch.ones((bridge.batch_size, 1), dtype=torch.bool, device=bridge.device)
        )
