from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_reward_v2 import SimpleRewardV2Config
from clasher.torch_sim.simple_rollout import SimpleGymRolloutBridge
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import (
    SimpleStandardSetup,
    compile_standard_simple_setup,
)

PUBLIC_ROOTS = ("Golem", "Knight", "Lumberjack")


def _setup(device_name: str) -> SimpleStandardSetup:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    if device_name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    return compile_standard_simple_setup(
        CardDataLoader(),
        PUBLIC_ROOTS,
        device=device_name,
        canonical_lane_globals=True,
    )


def _typed_lookups(setup: SimpleStandardSetup) -> tuple[torch.Tensor, torch.Tensor]:
    cards = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((2, cards.size), dtype=torch.int64, device=setup.device)
    hand = torch.zeros(cards.size, dtype=torch.int64, device=setup.device)
    for card_id in range(1, cards.size):
        kind = int(cards.kind[card_id].cpu())
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id].cpu()):
            hand[card_id] = 2_000 + card_id
    return entity, hand


def _decks(batch_size: int) -> list[list[list[str]]]:
    names = ("Knight", "Golem", "Lumberjack")
    return [
        [
            [names[(row + player + card) % len(names)] for card in range(8)]
            for player in range(2)
        ]
        for row in range(batch_size)
    ]


def _runtime(
    setup: SimpleStandardSetup,
    entity_lookup: torch.Tensor,
    hand_lookup: torch.Tensor,
    *,
    batch_size: int,
) -> SimpleGymRuntime:
    return setup.create_runtime(
        _decks(batch_size),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
        max_entities=32,
        max_effects=24,
        include_privileged_critic=True,
    )


def _assert_repeated_runtime_rows(
    actual: SimpleGymRuntime,
    expected: SimpleGymRuntime,
    rows: torch.Tensor,
) -> None:
    actual_groups = actual._row_state_tensor_groups()
    expected_groups = expected._row_state_tensor_groups()
    assert actual_groups.keys() == expected_groups.keys()
    for group, tensors in actual_groups.items():
        assert tensors.keys() == expected_groups[group].keys()
        for name, value in tensors.items():
            assert torch.equal(
                value,
                expected_groups[group][name].index_select(0, rows),
            ), f"{group}.{name}"


def _assert_repeated_tensors(actual: Any, expected: Any, rows: torch.Tensor) -> None:
    if isinstance(actual, torch.Tensor):
        assert isinstance(expected, torch.Tensor)
        assert torch.equal(actual, expected.index_select(0, rows))
        return
    if is_dataclass(actual):
        assert type(actual) is type(expected)
        for descriptor in fields(actual):
            actual_value = getattr(actual, descriptor.name)
            expected_value = getattr(expected, descriptor.name)
            if isinstance(actual_value, torch.Tensor) or is_dataclass(actual_value):
                _assert_repeated_tensors(actual_value, expected_value, rows)


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_runtime_row_fork_repeats_complete_state_and_continues_exactly(
    device_name: str,
) -> None:
    setup = _setup(device_name)
    entity_lookup, hand_lookup = _typed_lookups(setup)
    source = _runtime(
        setup,
        entity_lookup,
        hand_lookup,
        batch_size=2,
    )
    speculative = _runtime(
        setup,
        entity_lookup,
        hand_lookup,
        batch_size=4,
    )

    first_legal = source.observe().legal_mask[:, :, :-1].to(torch.int64).argmax(dim=2)
    source.step_tick(first_legal)
    noop_source = torch.full(
        (source.batch_size, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=source.device,
    )
    for _ in range(7):
        source.step_tick(noop_source)

    rows = torch.tensor((1, 0, 1, 0), dtype=torch.int64, device=source.device)
    speculative.copy_rows_from_(source, rows)
    _assert_repeated_runtime_rows(speculative, source, rows)

    source_hp = source.state.hp.clone()
    speculative.state.hp[0, 0] -= 1.0
    assert torch.equal(source.state.hp, source_hp)
    speculative.copy_rows_from_(source, rows)

    noop_speculative = noop_source.index_select(0, rows)
    for _ in range(12):
        source_step = source.step_tick(noop_source)
        speculative_step = speculative.step_tick(noop_speculative)
        _assert_repeated_runtime_rows(speculative, source, rows)
        _assert_repeated_tensors(speculative_step, source_step, rows)


def test_runtime_row_fork_fails_before_mutation_for_incompatible_authority() -> None:
    setup = _setup("cpu")
    other_setup = _setup("cpu")
    entity_lookup, hand_lookup = _typed_lookups(setup)
    other_entity, other_hand = _typed_lookups(other_setup)
    source = _runtime(setup, entity_lookup, hand_lookup, batch_size=1)
    incompatible = _runtime(other_setup, other_entity, other_hand, batch_size=1)
    before = incompatible.state.tick.clone()

    with pytest.raises(ValueError, match="immutable setup authority"):
        incompatible.copy_rows_from_(source, torch.zeros(1, dtype=torch.int64))

    assert torch.equal(incompatible.state.tick, before)


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_rollout_bridge_fork_preserves_history_rewards_and_continuation(
    device_name: str,
) -> None:
    setup = _setup(device_name)
    entity_lookup, hand_lookup = _typed_lookups(setup)
    source_runtime = _runtime(
        setup,
        entity_lookup,
        hand_lookup,
        batch_size=2,
    )
    fork_runtime = _runtime(
        setup,
        entity_lookup,
        hand_lookup,
        batch_size=4,
    )
    reward = SimpleRewardV2Config(gamma=0.99)
    source = SimpleGymRolloutBridge(
        source_runtime,
        decision_interval=4,
        reward_v2_config=reward,
        strict_reset_check=False,
    )
    speculative = SimpleGymRolloutBridge(
        fork_runtime,
        decision_interval=4,
        reward_v2_config=reward,
        strict_reset_check=False,
    )

    first = source.observe().legal_mask[:, :, :-1].to(torch.int64).argmax(dim=2)
    source.step(first)
    rows = torch.tensor((1, 0, 1, 0), dtype=torch.int64, device=source.device)
    speculative.copy_rows_from_(source, rows)

    assert torch.equal(
        speculative.adapter.history.previous_actions,
        source.adapter.history.previous_actions.index_select(0, rows),
    )
    assert torch.equal(
        speculative.adapter.history.previous_rewards,
        source.adapter.history.previous_rewards.index_select(0, rows),
    )
    assert torch.equal(
        speculative.adapter.history.episode_starts,
        source.adapter.history.episode_starts.index_select(0, rows),
    )
    assert torch.equal(
        speculative._initial_tower_hp,
        source._initial_tower_hp.index_select(0, rows),
    )
    assert torch.equal(
        speculative.needs_reset,
        source.needs_reset.index_select(0, rows),
    )

    source_noop = torch.full(
        (source.batch_size, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=source.device,
    )
    fork_noop = source_noop.index_select(0, rows)
    for decision_index in range(5):
        source_step = source.step(source_noop)
        fork_step = speculative.step(fork_noop)
        if decision_index == 0:
            _assert_repeated_tensors(
                source.boundary_after(source_step),
                source.observe(),
                torch.arange(source.batch_size, device=source.device),
            )
        _assert_repeated_runtime_rows(fork_runtime, source_runtime, rows)
        _assert_repeated_tensors(fork_step, source_step, rows)


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (torch.zeros((1, 1), dtype=torch.int64), "shape"),
        (torch.zeros(1, dtype=torch.int32), "int64"),
        (torch.tensor((2,), dtype=torch.int64), "outside"),
    ),
)
def test_runtime_row_fork_rejects_invalid_row_selection(
    rows: torch.Tensor,
    message: str,
) -> None:
    setup = _setup("cpu")
    entity_lookup, hand_lookup = _typed_lookups(setup)
    source = _runtime(setup, entity_lookup, hand_lookup, batch_size=1)
    destination = _runtime(setup, entity_lookup, hand_lookup, batch_size=1)

    with pytest.raises((ValueError, IndexError), match=message):
        destination.copy_rows_from_(source, rows)
