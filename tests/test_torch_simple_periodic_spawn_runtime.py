from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep
from clasher.torch_sim.simple_spawn_blueprints import FastSpawnBlueprintCatalog


def _runtime(
    root_name: str,
    *,
    device_name: str,
    max_entities: int = 32,
) -> tuple[SimpleGymRuntime, FastSpawnBlueprintCatalog, int]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    loader = BattleState().card_loader
    base = TensorCardCatalog.compile(loader, [root_name], device=device)
    blueprints = FastSpawnBlueprintCatalog.compile(loader, base)
    root = blueprints.cards.name_to_id[root_name]
    decks = torch.full((1, 2, 8), root, dtype=torch.int64, device=device)
    tower_spec = FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.full((2, 3), 100_000.0, device=device),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    entity_lookup = torch.zeros(
        (2, blueprints.fast_cards.size), dtype=torch.int64, device=device
    )
    hand_lookup = torch.zeros(
        blueprints.fast_cards.size, dtype=torch.int64, device=device
    )
    for card_id, visible_name in enumerate(blueprints.visible_names):
        if not visible_name:
            continue
        kind = int(blueprints.fast_cards.kind[card_id])
        if kind >= 0:
            entity_lookup[kind, card_id] = 1_000 + card_id
        if bool(blueprints.public_card_mask[card_id]):
            hand_lookup[card_id] = 2_000 + card_id
    runtime = SimpleGymRuntime(
        decks,
        blueprints.fast_cards,
        tower_spec,
        FastMatchRules(regulation_ticks=2_000, tiebreak_ticks=3_000),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=max_entities,
        starting_elixir=10.0,
        spawn_blueprints=blueprints,
    )
    return runtime, blueprints, root


def _deploy(runtime: SimpleGymRuntime) -> SimpleGymRuntimeStep:
    action = 10 * BOARD_WIDTH + 9
    result = runtime.step_tick(
        torch.tensor([[action, NO_OP_ACTION]], dtype=torch.int64, device=runtime.device)
    )
    assert result.action_success.tolist() == [[True, True]]
    return result


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


def _next_periodic_event(
    runtime: SimpleGymRuntime,
    *,
    budget: int,
) -> SimpleGymRuntimeStep:
    noop = _noop(runtime)
    for _ in range(budget):
        result = runtime.step_tick(noop)
        allocation = result.periodic_spawn_allocation
        assert allocation is not None
        if bool((allocation.accepted | allocation.capacity_rejected).any()):
            return result
    raise AssertionError("periodic source did not reach a wave deadline")


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("root_name", "child_name", "first_delay", "interval", "count"),
    (
        ("Witch", "Skeleton", 20, 140, 4),
        ("NightWitch", "Bat", 20, 100, 2),
        ("Tombstone", "Skeleton", 70, 70, 2),
    ),
)
def test_runtime_periodic_wave_cadence_counts_and_typed_projection(
    device_name: str,
    root_name: str,
    child_name: str,
    first_delay: int,
    interval: int,
    count: int,
) -> None:
    runtime, blueprints, root = _runtime(root_name, device_name=device_name)
    assert bool(blueprints.root_payload_supported[root])
    assert bool(blueprints.fast_cards.training_supported[root])
    _deploy(runtime)
    parent = runtime.state.active & (runtime.state.card_id == root)
    assert int(parent.sum()) == 1
    runtime.state.speed_units_per_tick.masked_fill_(parent, 0)
    assert runtime.periodic_spawns is not None
    assert runtime.periodic_spawns.next_tick[parent].tolist() == [1 + first_delay]

    first = _next_periodic_event(runtime, budget=first_delay)
    assert int(runtime.state.tick[0]) == 1 + first_delay
    assert first.periodic_spawn_allocation is not None
    assert first.periodic_spawn_allocation.accepted.tolist()[0][0]
    assert int(first.periodic_spawn_allocation.spawned_mask.sum()) == count
    assert runtime.periodic_spawns.next_tick[parent].tolist() == [
        1 + first_delay + interval
    ]

    child = next(
        card_id
        for card_id, name in enumerate(blueprints.visible_names)
        if name == child_name and card_id != root
    )
    children = runtime.state.active & (runtime.state.card_id == child)
    assert int(children.sum()) == count
    expected_token = int(runtime.projector.inputs.entity_token_lookup[0, child])
    visible = first.observation.actor.entity_ids[0, 0][
        first.observation.actor.entity_mask[0, 0]
    ]
    assert int((visible == expected_token).sum()) == count
    assert int(runtime.projector.inputs.hand_token_lookup[child]) == 0

    second = _next_periodic_event(runtime, budget=interval)
    assert int(runtime.state.tick[0]) == 1 + first_delay + interval
    assert second.periodic_spawn_allocation is not None
    assert int(second.periodic_spawn_allocation.spawned_mask.sum()) == count


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("root_name", "periodic_count", "death_count"),
    (("NightWitch", 2, 1), ("Tombstone", 2, 4)),
)
def test_periodic_and_death_payloads_coexist_without_a_postdeath_wave(
    device_name: str,
    root_name: str,
    periodic_count: int,
    death_count: int,
) -> None:
    runtime, _, root = _runtime(root_name, device_name=device_name)
    _deploy(runtime)
    first = _next_periodic_event(runtime, budget=80)
    assert first.periodic_spawn_allocation is not None
    assert int(first.periodic_spawn_allocation.spawned_mask.sum()) == periodic_count

    parent = runtime.state.active & (runtime.state.card_id == root)
    runtime.state.hp.masked_fill_(parent, 0.0)
    death = runtime.step_tick(_noop(runtime))
    assert int(death.lifecycle.spawned_mask.sum()) == death_count
    assert death.periodic_spawn_allocation is not None
    assert not bool(death.periodic_spawn_allocation.accepted.any())
    assert runtime.periodic_spawns is not None
    assert not bool((runtime.periodic_spawns.source_stable_id > 0).any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_periodic_wave_capacity_rejection_is_atomic(device_name: str) -> None:
    runtime, _, root = _runtime("Witch", device_name=device_name, max_entities=10)
    _deploy(runtime)
    parent = runtime.state.active & (runtime.state.card_id == root)
    runtime.state.speed_units_per_tick.masked_fill_(parent, 0)
    wave = _next_periodic_event(runtime, budget=20)
    assert wave.periodic_spawn_allocation is not None
    assert wave.periodic_spawn_allocation.capacity_rejected.tolist()[0][0]
    assert not bool(wave.periodic_spawn_allocation.accepted.any())
    assert not bool(wave.periodic_spawn_allocation.spawned_mask.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_full_runtime_periodic_replay_is_exact(device_name: str) -> None:
    first, _, _ = _runtime("NightWitch", device_name=device_name)
    replay, _, _ = _runtime("NightWitch", device_name=device_name)
    _deploy(first)
    _deploy(replay)
    noop = _noop(first)
    for _ in range(125):
        first_result = first.step_tick(noop)
        replay_result = replay.step_tick(noop.clone())
        assert first_result.periodic_spawn_allocation is not None
        assert replay_result.periodic_spawn_allocation is not None
        for descriptor in fields(first_result.periodic_spawn_allocation):
            assert torch.equal(
                getattr(first_result.periodic_spawn_allocation, descriptor.name),
                getattr(replay_result.periodic_spawn_allocation, descriptor.name),
            )
    for owner_name in (
        "state",
        "effects",
        "lifecycle",
        "modifiers",
        "damage_ramp",
        "periodic_spawns",
    ):
        left = getattr(first, owner_name)
        right = getattr(replay, owner_name)
        assert left is not None and right is not None
        for descriptor in fields(left):
            if descriptor.name != "device":
                assert torch.equal(
                    getattr(left, descriptor.name), getattr(right, descriptor.name)
                )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_selective_runtime_reset_clears_periodic_source_identity(
    device_name: str,
) -> None:
    runtime, _, root = _runtime("Witch", device_name=device_name)
    _deploy(runtime)
    assert runtime.periodic_spawns is not None
    active_source = runtime.periodic_spawns.source_stable_id > 0
    assert active_source.sum().tolist() == 1
    assert runtime.periodic_spawns.next_tick[active_source].tolist() == [21]

    runtime.reset_rows(torch.ones(1, dtype=torch.bool, device=runtime.device))
    assert not bool((runtime.periodic_spawns.source_stable_id > 0).any())
    assert not bool((runtime.periodic_spawns.next_tick > 0).any())
    assert bool((runtime.periodic_spawns.blueprint_row == -1).all())

    _deploy(runtime)
    parent = runtime.state.active & (runtime.state.card_id == root)
    assert runtime.state.stable_id[parent].tolist() == [7]
    assert runtime.periodic_spawns.source_stable_id[parent].tolist() == [7]
    assert runtime.periodic_spawns.next_tick[parent].tolist() == [21]
