from __future__ import annotations

import copy
import inspect
from dataclasses import fields, replace
from typing import Any

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.rl.common import BOARD_WIDTH, NUM_TILES
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_spawn_blueprints import (
    FastSpawnBlueprintCatalog,
    allocate_fast_atomic_spawns_,
)
from clasher.torch_sim.simple_standard import compile_standard_simple_setup

ROOTS = ("Archers", "GoblinGang")


def _runtime(
    device_name: str,
    *,
    max_entities: int,
    player_zero: str = "GoblinGang",
    player_one: str = "GoblinGang",
) -> tuple[SimpleGymRuntime, FastSpawnBlueprintCatalog, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    loader = CardDataLoader()
    base = TensorCardCatalog.compile(loader, ROOTS, device=device)
    blueprints = FastSpawnBlueprintCatalog.compile(loader, base)
    ids = {name: blueprints.cards.name_to_id[name] for name in ROOTS}

    def deck(first: str) -> list[int]:
        other = "Archers" if first == "GoblinGang" else "GoblinGang"
        return [ids[first], ids[other], ids[other], ids[first]] + [
            ids[other],
            ids[first],
            ids[other],
            ids[first],
        ]

    decks = torch.tensor(
        [[deck(player_zero), deck(player_one)]],
        dtype=torch.int64,
        device=device,
    )
    tower_spec = FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]],
            dtype=torch.int32,
            device=device,
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]],
            dtype=torch.int32,
            device=device,
        ),
        hitpoints=torch.tensor(
            [[20_000.0, 20_000.0, 30_000.0]] * 2,
            dtype=torch.float32,
            device=device,
        ),
        damage=torch.zeros((2, 3), dtype=torch.float32, device=device),
        range_units=torch.full((2, 3), 7_500, dtype=torch.int32, device=device),
        sight_range_units=torch.full((2, 3), 9_500, dtype=torch.int32, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    entity = torch.zeros(
        (2, blueprints.fast_cards.size), dtype=torch.int64, device=device
    )
    hand = torch.zeros(blueprints.fast_cards.size, dtype=torch.int64, device=device)
    for card_id, visible_name in enumerate(blueprints.visible_names):
        if not visible_name:
            continue
        kind = int(blueprints.fast_cards.kind[card_id])
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(blueprints.public_card_mask[card_id]):
            hand[card_id] = 2_000 + card_id
    runtime = SimpleGymRuntime(
        decks,
        blueprints.fast_cards,
        tower_spec,
        FastMatchRules(regulation_ticks=2_000, tiebreak_ticks=3_000),
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        max_entities=max_entities,
        max_effects=16,
        starting_elixir=10.0,
        spawn_blueprints=blueprints,
    )
    return runtime, blueprints, ids


def _actions(runtime: SimpleGymRuntime) -> torch.Tensor:
    tile = 14 * BOARD_WIDTH + 8
    return torch.full((1, 2), tile, dtype=torch.int64, device=runtime.device)


def _assert_tensor_fields_equal(left: Any, right: Any) -> None:
    for descriptor in fields(left):
        left_value = getattr(left, descriptor.name)
        if isinstance(left_value, torch.Tensor):
            torch.testing.assert_close(left_value, getattr(right, descriptor.name))


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_materializes_exact_typed_three_plus_three_action(
    device_name: str,
) -> None:
    runtime, blueprints, ids = _runtime(device_name, max_entities=18)
    root = ids["GoblinGang"]
    event = int(blueprints.action_atomic_event_by_card[root])
    members = blueprints.atomic_member_child_card_id[event]

    result = runtime.step_tick(_actions(runtime))

    assert result.atomic_spawn_allocation is not None
    assert result.atomic_spawn_allocation.accepted.tolist() == [[True, True]]
    assert result.action_success.tolist() == [[True, True]]
    assert runtime.combat.spawned_mask.sum(dim=1).tolist() == [12]
    torch.testing.assert_close(runtime.state.card_id[0, 6:12], members)
    torch.testing.assert_close(runtime.state.card_id[0, 12:18], members)
    assert runtime.state.stable_id[0, 6:18].tolist() == list(range(7, 19))
    assert int(runtime.state.next_stable_id[0]) == 19
    assert not bool((runtime.state.card_id[0, 6:18] == root).any())
    assert [blueprints.visible_names[index] for index in members.tolist()] == [
        "Goblin_Stab",
        "Goblin_Stab",
        "Goblin_Stab",
        "SpearGoblin",
        "SpearGoblin",
        "SpearGoblin",
    ]
    torch.testing.assert_close(
        runtime.state.hp[0, 6:12], blueprints.fast_cards.hitpoints[members]
    )
    torch.testing.assert_close(
        runtime.state.damage[0, 6:12], blueprints.fast_cards.damage[members]
    )
    torch.testing.assert_close(
        runtime.state.deploy_ticks[0, 6:12] + 1,
        blueprints.atomic_member_deploy_ticks[event],
    )
    torch.testing.assert_close(
        runtime.state.x_units[0, 6:12],
        torch.full((6,), 8_500, dtype=torch.int32, device=runtime.device)
        + blueprints.atomic_member_offset_x_units[event, 0, 0],
    )
    torch.testing.assert_close(
        runtime.state.y_units[0, 6:12],
        torch.full((6,), 14_500, dtype=torch.int32, device=runtime.device)
        + blueprints.atomic_member_offset_y_units[event, 0, 0],
    )

    stab, spear = int(members[0]), int(members[3])
    actor_ids = result.observation.actor.entity_ids[0, 0]
    assert int((actor_ids == 1_000 + stab).sum()) == 6
    assert int((actor_ids == 1_000 + spear).sum()) == 6
    assert int(runtime.projector.inputs.hand_token_lookup[stab]) == 0
    assert int(runtime.projector.inputs.hand_token_lookup[spear]) == 0
    root_token = int(runtime.projector.inputs.hand_token_lookup[root])
    assert bool((result.observation.actor.hand_ids == root_token).any())


def test_exact_capacity_is_player_ordered_and_rolls_back_whole_action() -> None:
    runtime, blueprints, ids = _runtime("cpu", max_entities=12)
    before_hand = runtime.action_state.hand_ids.clone()
    before_cycle = runtime.action_state.cycle_ids.clone()
    before_head = runtime.action_state.cycle_head.clone()
    before_elixir = runtime.action_state.elixir.clone()

    result = runtime.step_tick(_actions(runtime))

    assert result.atomic_spawn_allocation is not None
    assert result.atomic_spawn_allocation.accepted.tolist() == [[True, False]]
    assert result.atomic_spawn_allocation.capacity_rejected.tolist() == [[False, True]]
    assert result.action_success.tolist() == [[True, False]]
    assert runtime.state.active.sum().item() == 12
    event = int(blueprints.action_atomic_event_by_card[ids["GoblinGang"]])
    torch.testing.assert_close(
        runtime.state.card_id[0, 6:12],
        blueprints.atomic_member_child_card_id[event],
    )
    assert torch.equal(runtime.action_state.hand_ids[0, 1], before_hand[0, 1])
    assert torch.equal(runtime.action_state.cycle_ids[0, 1], before_cycle[0, 1])
    assert torch.equal(runtime.action_state.cycle_head[0, 1], before_head[0, 1])
    torch.testing.assert_close(runtime.action_state.elixir[0, 1], before_elixir[0, 1])
    assert not torch.equal(runtime.action_state.hand_ids[0, 0], before_hand[0, 0])


def test_one_slot_short_fails_mask_closed_without_transaction_mutation() -> None:
    runtime, _, _ = _runtime("cpu", max_entities=11)
    before_state = runtime.state.clone()
    before_action = runtime.action_state.clone()
    mask = runtime.observe().legal_mask
    assert not bool(mask[0, :, :NUM_TILES].any())
    assert bool(mask[0, :, NO_OP_ACTION].all())

    result = runtime.step_tick(_actions(runtime))

    assert result.action_success.tolist() == [[False, False]]
    assert result.atomic_spawn_allocation is not None
    assert not bool(result.atomic_spawn_allocation.accepted.any())
    assert not bool(result.atomic_spawn_allocation.spawned_mask.any())
    before_state.tick.add_(1)
    _assert_tensor_fields_equal(runtime.state, before_state)
    # One committed no-op-equivalent native tick advances the clock only.
    assert runtime.state.tick.tolist() == [1]
    _assert_tensor_fields_equal(runtime.action_state, before_action)


@pytest.mark.parametrize(
    ("player_zero", "player_one", "expected_cards", "expected_success"),
    (
        ("Archers", "GoblinGang", ("Archers", "Archers"), (True, False)),
        (
            "GoblinGang",
            "Archers",
            (
                "Goblin_Stab",
                "Goblin_Stab",
                "Goblin_Stab",
                "SpearGoblin",
                "SpearGoblin",
                "SpearGoblin",
            ),
            (True, False),
        ),
    ),
)
def test_mixed_homogeneous_and_atomic_actions_preserve_global_player_order(
    player_zero: str,
    player_one: str,
    expected_cards: tuple[str, ...],
    expected_success: tuple[bool, bool],
) -> None:
    runtime, blueprints, _ = _runtime(
        "cpu",
        max_entities=12,
        player_zero=player_zero,
        player_one=player_one,
    )

    result = runtime.step_tick(_actions(runtime))

    assert result.action_success.tolist() == [list(expected_success)]
    names = tuple(
        blueprints.visible_names[int(card_id)]
        for card_id in runtime.state.card_id[0, 6:12]
        if int(card_id) > 0
    )
    assert names == expected_cards
    assert runtime.state.owner[0, 6:12][runtime.state.active[0, 6:12]].eq(0).all()


def test_spawned_ledger_reinitializes_every_entity_bound_plane() -> None:
    runtime, _, _ = _runtime("cpu", max_entities=12)
    slots = slice(6, 12)
    runtime.entity_status_kind[0, slots] = 7
    runtime.entity_status_ticks[0, slots] = 99
    runtime.entity_slow_ticks[0, slots] = 99
    runtime.entity_attack_clock_fraction[0, slots] = 0.75
    runtime.combat.navigation.state.mover_stable_id[0, slots] = 999
    runtime.combat.navigation.state.bridge_index[0, slots] = 1
    runtime.modifiers.shield[0, slots] = 999.0
    runtime.modifiers.charge_progress_ticks[0, slots] = 99
    runtime.damage_ramp.connected_ticks[0, slots] = 99
    runtime.policy_mechanics.bound_stable_id[0, slots] = 999
    runtime.travel.bound_stable_id[0, slots] = 999
    runtime.travel.phase_ticks[0, slots] = 99
    runtime.abilities.bound_stable_id[0, slots] = 999
    runtime.abilities.cooldown_end_tick[0, slots] = 99
    runtime.death_bursts.emitted_source_stable_id[0, slots] = 999
    runtime._triggered_death_stable_id[0, slots] = 999

    runtime.step_tick(
        torch.tensor([[14 * BOARD_WIDTH + 8, NO_OP_ACTION]], dtype=torch.int64)
    )

    assert not bool(runtime.entity_status_kind[0, slots].any())
    assert not bool(runtime.entity_status_ticks[0, slots].any())
    assert not bool(runtime.entity_slow_ticks[0, slots].any())
    assert not bool(runtime.entity_attack_clock_fraction[0, slots].any())
    assert not bool(runtime.combat.navigation.state.mover_stable_id[0, slots].any())
    assert runtime.combat.navigation.state.bridge_index[0, slots].eq(-1).all()
    assert not bool(runtime.modifiers.shield[0, slots].any())
    assert not bool(runtime.modifiers.charge_progress_ticks[0, slots].any())
    assert not bool(runtime.damage_ramp.connected_ticks[0, slots].any())
    assert torch.equal(
        runtime.policy_mechanics.bound_stable_id[0, slots],
        runtime.state.stable_id[0, slots],
    )
    assert not bool(runtime.travel.bound_stable_id[0, slots].any())
    assert not bool(runtime.travel.phase_ticks[0, slots].any())
    assert not bool(runtime.abilities.bound_stable_id[0, slots].any())
    assert not bool(runtime.abilities.cooldown_end_tick[0, slots].any())
    assert not bool(runtime.death_bursts.emitted_source_stable_id[0, slots].any())
    assert not bool(runtime._triggered_death_stable_id[0, slots].any())


def test_replay_and_reset_reproduce_atomic_runtime_state() -> None:
    first, _, _ = _runtime("cpu", max_entities=18)
    replay, _, _ = _runtime("cpu", max_entities=18)
    actions = _actions(first)

    first_step = first.step_tick(actions)
    replay_step = replay.step_tick(actions.clone())
    _assert_tensor_fields_equal(first.state, replay.state)
    _assert_tensor_fields_equal(first.action_state, replay.action_state)
    _assert_tensor_fields_equal(first.policy_mechanics, replay.policy_mechanics)
    _assert_tensor_fields_equal(first.travel, replay.travel)
    _assert_tensor_fields_equal(first.abilities, replay.abilities)
    assert first_step.atomic_spawn_allocation is not None
    assert replay_step.atomic_spawn_allocation is not None
    _assert_tensor_fields_equal(
        first_step.atomic_spawn_allocation,
        replay_step.atomic_spawn_allocation,
    )

    expected_state = first.state.clone()
    expected_action = first.action_state.clone()
    first.reset_rows(torch.ones(1, dtype=torch.bool))
    reset_step = first.step_tick(actions)
    _assert_tensor_fields_equal(first.state, expected_state)
    _assert_tensor_fields_equal(first.action_state, expected_action)
    assert reset_step.atomic_spawn_allocation is not None
    _assert_tensor_fields_equal(
        reset_step.atomic_spawn_allocation,
        first_step.atomic_spawn_allocation,
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_cuda_graph_matches_eager_atomic_runtime_tick() -> None:
    captured, _, _ = _runtime("cuda", max_entities=18)
    eager, _, _ = _runtime("cuda", max_entities=18)
    actions = _actions(captured)
    runner = SimpleCudaGraphRunner(captured, actions)

    graph_step = runner.step_tick(actions)
    eager_step = eager.step_tick(actions)
    torch.cuda.synchronize(captured.device)

    _assert_tensor_fields_equal(captured.state, eager.state)
    _assert_tensor_fields_equal(captured.action_state, eager.action_state)
    _assert_tensor_fields_equal(captured.policy_mechanics, eager.policy_mechanics)
    _assert_tensor_fields_equal(captured.travel, eager.travel)
    _assert_tensor_fields_equal(captured.abilities, eager.abilities)
    assert graph_step.atomic_spawn_allocation is not None
    assert eager_step.atomic_spawn_allocation is not None
    _assert_tensor_fields_equal(
        graph_step.atomic_spawn_allocation,
        eager_step.atomic_spawn_allocation,
    )
    torch.testing.assert_close(
        graph_step.observation.actor.entity_ids,
        eager_step.observation.actor.entity_ids,
    )


def test_standard_setup_requires_a_supported_atomic_action_event() -> None:
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("GoblinGang",),
        device="cpu",
        canonical_lane_globals=True,
    )
    root = setup.cards.name_to_id["GoblinGang"]
    event = int(setup.spawn_blueprints.action_atomic_event_by_card[root])
    assert event >= 0
    assert bool(setup.spawn_blueprints.atomic_event_supported[event])
    assert bool(setup.supported_public_root_mask[root])

    loader = CardDataLoader()
    definitions = dict(loader.load_card_definitions())
    definition = definitions["GoblinGang"]
    raw = copy.deepcopy(definition.raw)
    secondary = copy.deepcopy(raw["summonCharacterSecondData"])
    secondary.pop("hitpoints")
    raw["summonCharacterSecondData"] = secondary
    definitions["GoblinGang"] = replace(definition, raw=raw)
    loader._card_definitions = definitions
    loader._cards = {}
    malformed = compile_standard_simple_setup(
        loader,
        ("GoblinGang",),
        device="cpu",
        canonical_lane_globals=True,
    )
    malformed_root = malformed.cards.name_to_id["GoblinGang"]
    assert (
        int(malformed.spawn_blueprints.action_atomic_event_by_card[malformed_root]) < 0
    )
    assert not bool(malformed.supported_public_root_mask[malformed_root])


def test_atomic_action_hot_path_has_no_sync_compaction_or_name_dispatch() -> None:
    source = inspect.getsource(SimpleGymRuntime._action_atomic_commands)
    source += inspect.getsource(SimpleGymRuntime._initialize_action_spawns_)
    source += inspect.getsource(SimpleGymRuntime._legal_action_mask)
    source += inspect.getsource(SimpleGymRuntime.step_tick)
    source += inspect.getsource(allocate_fast_atomic_spawns_)
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
        "GoblinGang",
        "Goblin_Stab",
        "SpearGoblin",
    ):
        assert forbidden not in source
