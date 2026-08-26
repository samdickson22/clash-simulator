from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import (
    SimpleStandardSetup,
    compile_standard_simple_setup,
)

ROOTS = ("Graveyard", "RoyalDelivery")


def _setup(device_name: str) -> SimpleStandardSetup:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return compile_standard_simple_setup(
        CardDataLoader(),
        ROOTS,
        device=device_name,
        canonical_lane_globals=True,
    )


def _runtime(
    name: str,
    device_name: str,
    *,
    max_entities: int = 64,
    max_effects: int = 16,
    max_scheduled_casts: int = 4,
) -> tuple[SimpleGymRuntime, SimpleStandardSetup]:
    setup = _setup(device_name)
    fast = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((2, fast.size), dtype=torch.int64, device=setup.device)
    hand = torch.zeros(fast.size, dtype=torch.int64, device=setup.device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id])
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id]):
            hand[card_id] = 2_000 + card_id
    runtime = setup.create_runtime(
        [[[name] * 8, [name] * 8]],
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        max_entities=max_entities,
        max_effects=max_effects,
        max_scheduled_casts=max_scheduled_casts,
        starting_elixir=10.0,
    )
    return runtime, setup


def _action(
    runtime: SimpleGymRuntime,
    *,
    x: int,
    y: int,
    both: bool = False,
) -> torch.Tensor:
    placement = y * BOARD_WIDTH + x
    return torch.tensor(
        [[placement, placement if both else NO_OP_ACTION]],
        dtype=torch.int64,
        device=runtime.device,
    )


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_full_runtime_repeated_schedule_has_typed_children_and_cadence(
    device_name: str,
) -> None:
    runtime, setup = _runtime("Graveyard", device_name)
    blueprints = setup.spawn_blueprints
    root = blueprints.cards.name_to_id["Graveyard"]
    child = blueprints.cards.name_to_id["Skeleton"]
    row = int(blueprints.scheduled_blueprint_by_card[root])
    assert bool(blueprints.fast_cards.training_supported[root])
    assert (
        int(blueprints.first_delay_ticks[row]),
        int(blueprints.interval_ticks[row]),
        int(blueprints.max_waves[row]),
        int(blueprints.count[row]),
    ) == (44, 11, 12, 1)

    cast = runtime.step_tick(_action(runtime, x=9, y=10))
    assert cast.action_success.tolist() == [[True, True]]
    assert cast.scheduled_cast_allocation is not None
    assert cast.scheduled_cast_allocation.accepted.tolist() == [[True, False]]
    assert runtime.scheduled_casts is not None
    assert int(runtime.scheduled_casts.active.sum()) == 1

    due_ticks: list[int] = []
    spawned = 0
    for _ in range(164):
        result = runtime.step_tick(_noop(runtime))
        assert result.scheduled_casts is not None
        assert result.scheduled_spawn_allocation is not None
        new_children = result.scheduled_spawn_allocation.spawned_mask
        if bool(result.scheduled_casts.emitted_count.any()):
            due_ticks.append(int(runtime.state.tick[0]))
            assert int(new_children.sum()) == 1
            assert torch.equal(
                runtime.state.card_id[new_children],
                torch.full_like(runtime.state.card_id[new_children], child),
            )
            assert torch.equal(
                runtime.state.owner[new_children],
                torch.zeros_like(runtime.state.owner[new_children]),
            )
            spawned += int(new_children.sum())
    assert due_ticks == [44 + 11 * wave for wave in range(12)]
    assert spawned == 12
    assert not bool(runtime.scheduled_casts.active.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_full_runtime_delayed_delivery_damages_then_spawns_typed_child(
    device_name: str,
) -> None:
    runtime, setup = _runtime("RoyalDelivery", device_name)
    blueprints = setup.spawn_blueprints
    root = blueprints.cards.name_to_id["RoyalDelivery"]
    row = int(blueprints.scheduled_blueprint_by_card[root])
    recruit = int(blueprints.child_card_id[row])
    assert blueprints.visible_names[recruit] == "DeliveryRecruit"
    assert int(blueprints.first_delay_ticks[row]) == 41
    assert float(blueprints.scheduled_initial_damage[row]) == pytest.approx(437.0)

    tower_slot = 3
    tower_before = float(runtime.state.hp[0, tower_slot])
    cast = runtime.step_tick(_action(runtime, x=3, y=25))
    assert cast.action_success.tolist() == [[True, True]]
    assert float(runtime.state.hp[0, tower_slot]) == tower_before
    for _ in range(39):
        early = runtime.step_tick(_noop(runtime))
        assert early.scheduled_casts is not None
        assert not bool(early.scheduled_casts.effect_commands.ready.any())
    assert int(runtime.state.tick[0]) == 40
    assert float(runtime.state.hp[0, tower_slot]) == tower_before

    impact = runtime.step_tick(_noop(runtime))
    assert int(runtime.state.tick[0]) == 41
    assert impact.scheduled_effect_allocation is not None
    assert impact.scheduled_spawn_allocation is not None
    assert impact.scheduled_effect_allocation.accepted.tolist()[0][0]
    assert int(impact.scheduled_spawn_allocation.spawned_mask.sum()) == 1
    spawned = impact.scheduled_spawn_allocation.spawned_mask
    assert runtime.state.card_id[spawned].tolist() == [recruit]
    assert runtime.state.owner[spawned].tolist() == [0]
    assert runtime.state.deploy_ticks[spawned].tolist() == [5]
    assert float(runtime.state.hp[0, tower_slot]) == pytest.approx(
        tower_before - 437.0
    )
    assert float(runtime.modifiers.shield[spawned][0]) == pytest.approx(94.0)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_joint_cast_capacity_rejects_and_rolls_back_second_actor(
    device_name: str,
) -> None:
    runtime, _ = _runtime(
        "Graveyard", device_name, max_scheduled_casts=1
    )
    player_one_hand = runtime.action_state.hand_ids[:, 1].clone()
    player_one_cycle = runtime.action_state.cycle_ids[:, 1].clone()
    player_one_elixir = runtime.action_state.elixir[:, 1].clone()
    result = runtime.step_tick(_action(runtime, x=9, y=10, both=True))
    assert result.scheduled_cast_allocation is not None
    assert result.scheduled_cast_allocation.accepted.tolist() == [[True, False]]
    assert result.scheduled_cast_allocation.capacity_rejected.tolist() == [
        [False, True]
    ]
    assert result.action_success.tolist() == [[True, False]]
    assert torch.equal(runtime.action_state.hand_ids[:, 1], player_one_hand)
    assert torch.equal(runtime.action_state.cycle_ids[:, 1], player_one_cycle)
    assert torch.equal(runtime.action_state.elixir[:, 1], player_one_elixir)

    effect_blocked, _ = _runtime(
        "RoyalDelivery", device_name, max_effects=1
    )
    effect_blocked.effects.active.fill_(True)
    before_hand = effect_blocked.action_state.hand_ids.clone()
    before_elixir = effect_blocked.action_state.elixir.clone()
    assert not bool(
        effect_blocked.observe().legal_mask[0, 0, :NO_OP_ACTION].any()
    )
    rejected = effect_blocked.step_tick(_action(effect_blocked, x=3, y=25))
    assert rejected.action_success.tolist() == [[False, True]]
    assert torch.equal(effect_blocked.action_state.hand_ids, before_hand)
    assert torch.equal(effect_blocked.action_state.elixir, before_elixir)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_capacity_mask_replay_and_reset_are_exact(device_name: str) -> None:
    left, _ = _runtime("RoyalDelivery", device_name, max_scheduled_casts=1)
    right, _ = _runtime("RoyalDelivery", device_name, max_scheduled_casts=1)
    action = _action(left, x=3, y=25)
    left_first = left.step_tick(action)
    right_first = right.step_tick(action.clone())
    assert left_first.action_success.tolist() == [[True, True]]
    assert right_first.action_success.tolist() == [[True, True]]
    # The only cast slot is occupied, so every placement from the replacement
    # copy of the spell is closed while no-op remains available.
    assert not bool(left.observe().legal_mask[0, 0, :NO_OP_ACTION].any())
    assert bool(left.observe().legal_mask[0, 0, NO_OP_ACTION])

    for _ in range(45):
        left_result = left.step_tick(_noop(left))
        right_result = right.step_tick(_noop(right))
        assert left_result.scheduled_casts is not None
        assert right_result.scheduled_casts is not None
        for descriptor in fields(left_result.scheduled_casts):
            left_value = getattr(left_result.scheduled_casts, descriptor.name)
            right_value = getattr(right_result.scheduled_casts, descriptor.name)
            if isinstance(left_value, torch.Tensor):
                assert torch.equal(left_value, right_value)
            else:
                for nested in fields(left_value):
                    assert torch.equal(
                        getattr(left_value, nested.name),
                        getattr(right_value, nested.name),
                    )
        for name in ("active", "stable_id", "card_id", "hp", "tick"):
            assert torch.equal(getattr(left.state, name), getattr(right.state, name))

    left.step_tick(_action(left, x=3, y=25))
    assert left.scheduled_casts is not None
    assert bool(left.scheduled_casts.active.any())
    reset = torch.ones(1, dtype=torch.bool, device=left.device)
    left.reset_rows(reset)
    assert not bool(left.scheduled_casts.active.any())
    assert left.scheduled_casts.next_stable_id.tolist() == [1]
    assert bool(left.observe().legal_mask[0, 0, 25 * BOARD_WIDTH + 3])
