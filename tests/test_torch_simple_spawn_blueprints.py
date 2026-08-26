from __future__ import annotations

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_spawn_blueprints import (
    FastSpawnBlueprintCatalog,
    FastSpawnCommands,
    FastSpawnTrigger,
    allocate_fast_spawns_,
)
from clasher.torch_sim.simple_state import FastGymState

ROOTS = (
    "Balloon",
    "BarbarianBarrel",
    "BattleRam",
    "BombTower",
    "GoblinBarrel",
    "Golem",
    "LavaHound",
    "Lumberjack",
    "NightWitch",
    "SkeletonBarrel",
    "Tombstone",
)


def _compile(
    roots: tuple[str, ...] = ROOTS,
    *,
    device: str = "cpu",
) -> FastSpawnBlueprintCatalog:
    loader = CardDataLoader()
    base = TensorCardCatalog.compile(loader, roots, device=device)
    return FastSpawnBlueprintCatalog.compile(loader, base)


def _root_support(catalog: FastSpawnBlueprintCatalog, name: str) -> bool:
    card_id = catalog.cards.name_to_id[name]
    return bool(catalog.root_payload_supported[card_id])


def test_compiler_materializes_internal_rows_and_fails_closed_by_trigger_shape() -> (
    None
):
    catalog = _compile()

    rows_by_root = {
        name: [index for index, root in enumerate(catalog.root_names) if root == name]
        for name in ROOTS
    }
    assert _root_support(catalog, "BattleRam")
    assert _root_support(catalog, "LavaHound")
    assert _root_support(catalog, "GoblinBarrel")
    for name in ("BattleRam", "LavaHound", "GoblinBarrel"):
        card_id = catalog.cards.name_to_id[name]
        assert bool(catalog.public_card_mask[card_id])
        assert bool(catalog.fast_cards.training_supported[card_id])
    for name in (
        "Balloon",
        "BarbarianBarrel",
        "BombTower",
        "Golem",
        "Lumberjack",
        "NightWitch",
        "SkeletonBarrel",
        "Tombstone",
    ):
        assert bool(catalog.root_payload_required[catalog.cards.name_to_id[name]])
        assert not _root_support(catalog, name)

    ram_row = rows_by_root["BattleRam"][0]
    pups_row = rows_by_root["LavaHound"][0]
    barrel_row = rows_by_root["GoblinBarrel"][0]
    assert int(catalog.trigger[ram_row]) == int(FastSpawnTrigger.DEATH)
    assert int(catalog.count[ram_row]) == 2
    assert int(catalog.deploy_ticks[ram_row]) == 20
    assert int(catalog.count[pups_row]) == 6
    assert int(catalog.radius_units[pups_row]) == 2_500
    assert int(catalog.trigger[barrel_row]) == int(FastSpawnTrigger.PROJECTILE_IMPACT)
    assert int(catalog.count[barrel_row]) == 3
    assert int(
        catalog.fast_cards.death_spawn_card_id[catalog.cards.name_to_id["BattleRam"]]
    ) == int(catalog.child_card_id[ram_row])
    assert int(
        catalog.fast_cards.death_spawn_card_id[catalog.cards.name_to_id["LavaHound"]]
    ) == int(catalog.child_card_id[pups_row])
    assert (
        int(catalog.impact_blueprint_by_card[catalog.cards.name_to_id["GoblinBarrel"]])
        == barrel_row
    )

    expected_stats = {
        ram_row: ("Barbarian", 691.0, 192.0),
        pups_row: ("LavaPups", 215.0, 81.0),
        barrel_row: ("Goblin", 202.0, 120.0),
    }
    for row, (name, hp, damage) in expected_stats.items():
        child_id = int(catalog.child_card_id[row])
        assert child_id > 0
        assert catalog.visible_names[child_id] == name
        assert float(catalog.fast_cards.hitpoints[child_id]) == hp
        assert float(catalog.fast_cards.damage[child_id]) == damage

    # No internal entity blueprint is ever a public/root card row.
    public_ids = {catalog.cards.name_to_id[name] for name in ROOTS}
    assert all(
        int(catalog.child_card_id[row]) not in public_ids
        for row in (ram_row, pups_row, barrel_row)
    )


def test_compiler_ids_are_stable_under_root_order() -> None:
    left = _compile(ROOTS)
    right = _compile(tuple(reversed(ROOTS)))
    assert left.cards.names == right.cards.names
    assert left.cards.name_to_id == right.cards.name_to_id
    assert left.visible_names == right.visible_names
    assert left.root_names == right.root_names
    torch.testing.assert_close(left.trigger, right.trigger)
    torch.testing.assert_close(left.child_card_id, right.child_card_id)
    torch.testing.assert_close(left.blueprint_supported, right.blueprint_supported)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_fixed_shape_allocator_materializes_blueprint_stats_and_is_atomic(
    device_name: str,
) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    catalog = _compile(("BattleRam", "LavaHound"), device=device_name)
    device = torch.device(device_name)
    state = FastGymState.empty(2, max_entities=9, device=device)
    state.next_stable_id[:] = torch.tensor([10, 20], device=device)
    rows = {root: index for index, root in enumerate(catalog.root_names)}
    ram_row = rows["BattleRam"]
    pups_row = rows["LavaHound"]
    child = torch.tensor(
        [
            [
                int(catalog.child_card_id[ram_row]),
                int(catalog.child_card_id[pups_row]),
            ],
            [
                int(catalog.child_card_id[pups_row]),
                int(catalog.child_card_id[ram_row]),
            ],
        ],
        dtype=torch.int64,
        device=device,
    )
    commands = FastSpawnCommands(
        ready=torch.ones((2, 2), dtype=torch.bool, device=device),
        owner=torch.tensor([[0, 0], [1, 1]], dtype=torch.int8, device=device),
        child_card_id=child,
        x_units=torch.tensor(
            [[8_000, 12_000], [10_000, 5_000]],
            dtype=torch.int32,
            device=device,
        ),
        y_units=torch.tensor(
            [[10_000, 20_000], [22_000, 6_000]],
            dtype=torch.int32,
            device=device,
        ),
        count=torch.tensor([[2, 6], [6, 2]], dtype=torch.int32, device=device),
        radius_units=torch.tensor(
            [[600, 2_500], [2_500, 600]], dtype=torch.int32, device=device
        ),
        deploy_ticks=torch.tensor([[20, 0], [0, 20]], dtype=torch.int32, device=device),
    )
    result = allocate_fast_spawns_(
        state,
        catalog.fast_cards,
        commands,
        reserved_slot_floor=2,
    )

    # Seven free slots: the first command is accepted, the second rejected as
    # one atomic wave in each row regardless of its requested size.
    assert result.accepted.tolist() == [[True, False], [True, False]]
    assert result.capacity_rejected.tolist() == [[False, True], [False, True]]
    assert result.spawned_mask.sum(dim=1).tolist() == [2, 6]
    assert state.next_stable_id.tolist() == [12, 26]
    assert state.stable_id[0, 2:4].tolist() == [10, 11]
    assert state.stable_id[1, 2:8].tolist() == [20, 21, 22, 23, 24, 25]

    ram_id = int(catalog.child_card_id[ram_row])
    pups_id = int(catalog.child_card_id[pups_row])
    assert state.card_id[0, 2:4].tolist() == [ram_id, ram_id]
    assert state.card_id[1, 2:8].tolist() == [pups_id] * 6
    torch.testing.assert_close(state.hp[0, 2:4], torch.full((2,), 691.0, device=device))
    torch.testing.assert_close(
        state.damage[1, 2:8], torch.full((6,), 81.0, device=device)
    )
    assert state.deploy_ticks[0, 2:4].tolist() == [20, 20]
    assert state.deploy_ticks[1, 2:8].tolist() == [0] * 6


def test_allocator_rejects_unknown_and_nonpositive_commands_without_mutation() -> None:
    catalog = _compile(("BattleRam",))
    state = FastGymState.empty(1, max_entities=8)
    before = state.clone()
    commands = FastSpawnCommands(
        ready=torch.ones((1, 2), dtype=torch.bool),
        owner=torch.tensor([[0, 0]], dtype=torch.int8),
        child_card_id=torch.tensor([[catalog.fast_cards.size + 3, 0]]),
        x_units=torch.zeros((1, 2), dtype=torch.int32),
        y_units=torch.zeros((1, 2), dtype=torch.int32),
        count=torch.tensor([[1, 0]], dtype=torch.int32),
        radius_units=torch.zeros((1, 2), dtype=torch.int32),
        deploy_ticks=torch.zeros((1, 2), dtype=torch.int32),
    )
    result = allocate_fast_spawns_(state, catalog.fast_cards, commands)
    assert result.invalid.tolist() == [[True, True]]
    assert not result.spawned_mask.any()
    for name in (
        "active",
        "stable_id",
        "card_id",
        "hp",
        "next_stable_id",
    ):
        torch.testing.assert_close(getattr(state, name), getattr(before, name))
