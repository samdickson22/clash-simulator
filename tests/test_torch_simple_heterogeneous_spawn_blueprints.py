from __future__ import annotations

import copy
from dataclasses import fields, replace

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_spawn_blueprints import (
    FastAtomicSpawnCommands,
    FastSpawnBlueprintCatalog,
    FastSpawnTrigger,
    allocate_fast_atomic_spawns_,
)
from clasher.torch_sim.simple_state import FastGymState


def _compile(
    roots: tuple[str, ...] = ("GoblinGang",),
    *,
    loader: CardDataLoader | None = None,
    device: str = "cpu",
) -> FastSpawnBlueprintCatalog:
    source = CardDataLoader() if loader is None else loader
    base = TensorCardCatalog.compile(source, roots, device=device)
    return FastSpawnBlueprintCatalog.compile(source, base)


def _goblin_event(catalog: FastSpawnBlueprintCatalog) -> tuple[int, int]:
    root = catalog.cards.name_to_id["GoblinGang"]
    return root, int(catalog.action_atomic_event_by_card[root])


def _assert_state_equal(left: FastGymState, right: FastGymState) -> None:
    for field in fields(FastGymState):
        left_value = getattr(left, field.name)
        right_value = getattr(right, field.name)
        if isinstance(left_value, torch.Tensor):
            torch.testing.assert_close(left_value, right_value)
        else:
            assert left_value == right_value


def test_goblin_gang_compiles_two_typed_groups_as_one_private_atomic_event() -> None:
    catalog = _compile()
    root, event = _goblin_event(catalog)

    assert event >= 0
    assert catalog.root_names == ("GoblinGang", "GoblinGang")
    assert catalog.source_paths == (
        "GoblinGang.summonCharacterData",
        "GoblinGang.summonCharacterSecondData",
    )
    assert catalog.trigger.tolist() == [
        int(FastSpawnTrigger.DEPLOY_ACTION),
        int(FastSpawnTrigger.DEPLOY_ACTION),
    ]
    assert catalog.atomic_event_id.tolist() == [event, event]
    assert catalog.atomic_event_row_valid[event].tolist() == [True, True]
    assert catalog.atomic_event_row_id[event].tolist() == [0, 1]
    assert int(catalog.atomic_event_required_capacity[event]) == 6
    assert bool(catalog.atomic_event_supported[event])
    assert bool(catalog.root_payload_supported[root])

    member_ids = catalog.atomic_member_child_card_id[event].tolist()
    assert member_ids == [member_ids[0]] * 3 + [member_ids[3]] * 3
    assert member_ids[0] != member_ids[3]
    assert [catalog.visible_names[card_id] for card_id in member_ids] == (
        ["Goblin_Stab"] * 3 + ["SpearGoblin"] * 3
    )
    assert catalog.atomic_member_valid[event].tolist() == [True] * 6
    assert catalog.atomic_member_deploy_ticks[event].tolist() == [
        20,
        22,
        24,
        26,
        28,
        30,
    ]
    assert catalog.fast_cards.hitpoints[member_ids].tolist() == [
        202.0,
        202.0,
        202.0,
        133.0,
        133.0,
        133.0,
    ]
    assert catalog.fast_cards.damage[member_ids].tolist() == [
        120.0,
        120.0,
        120.0,
        81.0,
        81.0,
        81.0,
    ]

    # The public action row never doubles as either entity identity.
    assert bool(catalog.public_card_mask[root])
    assert not bool(catalog.public_card_mask[member_ids].any())
    assert root not in member_ids

    assert catalog.atomic_member_offset_x_units[event, 0, 0].tolist() == [
        999,
        0,
        -999,
        -999,
        0,
        999,
    ]
    assert catalog.atomic_member_offset_y_units[event, 0, 0].tolist() == [
        577,
        1_154,
        577,
        -577,
        -1_154,
        -577,
    ]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_goblin_gang_allocation_is_six_member_atomic_and_replay_stable(
    device_name: str,
) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    catalog = _compile(device=device_name)
    _, event = _goblin_event(catalog)
    device = torch.device(device_name)
    initial = FastGymState.empty(2, max_entities=12, device=device)
    initial.next_stable_id[:] = torch.tensor([42, 90], device=device)
    # Slots [6, 12) are the deploy pool. Battle zero has exactly six; battle
    # one has only five, so the latter must not receive a partial child group.
    initial.active[1, 6] = True
    commands = FastAtomicSpawnCommands(
        ready=torch.ones((2, 1), dtype=torch.bool, device=device),
        owner=torch.tensor([[1], [0]], dtype=torch.int8, device=device),
        atomic_event_id=torch.full((2, 1), event, dtype=torch.int64, device=device),
        x_units=torch.tensor([[9_000], [8_000]], dtype=torch.int32, device=device),
        y_units=torch.tensor([[20_000], [12_000]], dtype=torch.int32, device=device),
        lane_index=torch.tensor([[1], [0]], dtype=torch.int8, device=device),
    )

    left = initial.clone()
    right = initial.clone()
    left_result = allocate_fast_atomic_spawns_(
        left,
        catalog,
        commands,
        reserved_slot_floor=6,
    )
    right_result = allocate_fast_atomic_spawns_(
        right,
        catalog,
        commands,
        reserved_slot_floor=6,
    )

    assert left_result.accepted.tolist() == [[True], [False]]
    assert left_result.capacity_rejected.tolist() == [[False], [True]]
    assert not left_result.invalid.any()
    assert left_result.spawned_mask.sum(dim=1).tolist() == [6, 0]
    assert left.stable_id[0, 6:12].tolist() == [42, 43, 44, 45, 46, 47]
    assert int(left.next_stable_id[0]) == 48
    assert int(left.next_stable_id[1]) == 90

    typed_ids = catalog.atomic_member_child_card_id[event]
    torch.testing.assert_close(left.card_id[0, 6:12], typed_ids)
    assert not (left.card_id[0, 6:12] == catalog.cards.name_to_id["GoblinGang"]).any()
    torch.testing.assert_close(
        left.x_units[0, 6:12],
        commands.x_units[0, 0] + catalog.atomic_member_offset_x_units[event, 1, 1],
    )
    torch.testing.assert_close(
        left.y_units[0, 6:12],
        commands.y_units[0, 0] + catalog.atomic_member_offset_y_units[event, 1, 1],
    )
    torch.testing.assert_close(
        left.hp[0, 6:12], catalog.fast_cards.hitpoints[typed_ids]
    )
    torch.testing.assert_close(
        left.damage[0, 6:12], catalog.fast_cards.damage[typed_ids]
    )

    _assert_state_equal(left, right)
    for field in fields(type(left_result)):
        torch.testing.assert_close(
            getattr(left_result, field.name),
            getattr(right_result, field.name),
        )


def test_incomplete_secondary_group_fails_closed_without_allocating_primary() -> None:
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

    catalog = _compile(loader=loader)
    root = catalog.cards.name_to_id["GoblinGang"]
    event = int(catalog.atomic_event_id[0])
    assert bool(catalog.root_payload_required[root])
    assert not bool(catalog.root_payload_supported[root])
    assert not bool(catalog.fast_cards.training_supported[root])
    assert not bool(catalog.atomic_event_supported[event])
    assert int(catalog.action_atomic_event_by_card[root]) == -1

    state = FastGymState.empty(1, max_entities=12)
    before = state.clone()
    commands = FastAtomicSpawnCommands(
        ready=torch.ones((1, 1), dtype=torch.bool),
        owner=torch.zeros((1, 1), dtype=torch.int8),
        atomic_event_id=torch.tensor([[event]], dtype=torch.int64),
        x_units=torch.zeros((1, 1), dtype=torch.int32),
        y_units=torch.zeros((1, 1), dtype=torch.int32),
        lane_index=torch.zeros((1, 1), dtype=torch.int8),
    )
    result = allocate_fast_atomic_spawns_(state, catalog, commands)
    assert result.invalid.tolist() == [[True]]
    assert not result.spawned_mask.any()
    _assert_state_equal(state, before)


def test_heterogeneous_event_ids_and_member_order_ignore_public_root_order() -> None:
    left = _compile(("GoblinGang", "Rascals"))
    right = _compile(("Rascals", "GoblinGang"))

    assert left.cards.names == right.cards.names
    assert left.visible_names == right.visible_names
    assert left.root_names == right.root_names
    assert left.source_paths == right.source_paths
    for name in (
        "atomic_event_id",
        "atomic_event_root_card_id",
        "atomic_event_trigger",
        "atomic_event_row_id",
        "atomic_event_required_capacity",
        "atomic_event_supported",
        "atomic_member_child_card_id",
        "atomic_member_deploy_ticks",
        "atomic_member_offset_x_units",
        "atomic_member_offset_y_units",
        "action_atomic_event_by_card",
    ):
        torch.testing.assert_close(getattr(left, name), getattr(right, name))
