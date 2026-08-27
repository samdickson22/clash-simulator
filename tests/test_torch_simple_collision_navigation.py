from __future__ import annotations

import inspect

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_collision_navigation import (
    FAST_MAX_CONTACT_CORRECTION_UNITS,
    resolve_fast_collision_navigation,
)
from clasher.torch_sim.simple_engine import FastTensorGym
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from clasher.torch_sim.simple_state import (
    FAST_KIND_BUILDING,
    FAST_KIND_TROOP,
    FastGymState,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _inputs(
    device_name: str,
    *,
    entities: int,
) -> dict[str, torch.Tensor]:
    device = _device(device_name)
    shape = (1, entities)
    return {
        "active": torch.ones(shape, dtype=torch.bool, device=device),
        "stable_id": torch.arange(
            1, entities + 1, dtype=torch.int64, device=device
        ).view(shape),
        "owner": torch.zeros(shape, dtype=torch.int8, device=device),
        "kind": torch.full(shape, FAST_KIND_TROOP, dtype=torch.int8, device=device),
        "x_units": torch.zeros(shape, dtype=torch.int32, device=device),
        "y_units": torch.full(shape, 10_000, dtype=torch.int32, device=device),
        "intended_x_units": torch.zeros(shape, dtype=torch.int32, device=device),
        "intended_y_units": torch.zeros(shape, dtype=torch.int32, device=device),
        "collision_radius_units": torch.full(
            shape, 500, dtype=torch.int32, device=device
        ),
        "mass": torch.full(shape, 5.0, dtype=torch.float32, device=device),
        "airborne": torch.zeros(shape, dtype=torch.bool, device=device),
        "hover": torch.zeros(shape, dtype=torch.bool, device=device),
        "movement_enabled": torch.ones(shape, dtype=torch.bool, device=device),
        "collision_excluded": torch.zeros(shape, dtype=torch.bool, device=device),
    }


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_dense_same_and_opponent_congestion_separates_simultaneously(
    device_name: str,
) -> None:
    inputs = _inputs(device_name, entities=5)
    device = inputs["active"].device
    inputs["x_units"][0] = torch.tensor(
        [8_000, 8_350, 8_700, 9_050, 9_400], device=device
    )
    inputs["stable_id"][0] = torch.tensor([9, 2, 15, 4, 7], device=device)

    first = resolve_fast_collision_navigation(**inputs)
    perm = torch.tensor([2, 4, 0, 3, 1], device=device)
    permuted = {name: value[:, perm] for name, value in inputs.items()}
    second = resolve_fast_collision_navigation(**permuted)
    inverse = torch.argsort(perm)

    assert first.contacted.all()
    assert torch.equal(first.x_units, second.x_units[:, inverse])
    assert torch.equal(first.y_units, second.y_units[:, inverse])
    assert int(first.correction_x_units.abs().amax()) <= (
        FAST_MAX_CONTACT_CORRECTION_UNITS
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_mass_asymmetry_moves_light_body_farther(device_name: str) -> None:
    inputs = _inputs(device_name, entities=2)
    device = inputs["active"].device
    inputs["x_units"][0] = torch.tensor([8_000, 8_400], device=device)
    inputs["mass"][0] = torch.tensor([1.0, 20.0], device=device)

    result = resolve_fast_collision_navigation(**inputs)

    light = abs(int(result.x_units[0, 0]) - 8_000)
    heavy = abs(int(result.x_units[0, 1]) - 8_400)
    assert light > heavy > 0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_exact_overlap_uses_stable_identity_not_slot(device_name: str) -> None:
    inputs = _inputs(device_name, entities=2)
    device = inputs["active"].device
    inputs["x_units"].fill_(9_000)
    inputs["y_units"].fill_(10_000)
    inputs["stable_id"][0] = torch.tensor([17, 3], device=device)
    inputs["owner"][0] = torch.tensor([0, 1], dtype=torch.int8, device=device)

    first = resolve_fast_collision_navigation(**inputs)
    swapped = {name: value.flip(1) for name, value in inputs.items()}
    second = resolve_fast_collision_navigation(**swapped)

    assert not torch.equal(
        first.x_units[0, 0:1], first.x_units[0, 1:2]
    ) or not torch.equal(first.y_units[0, 0:1], first.y_units[0, 1:2])
    assert torch.equal(first.x_units, second.x_units.flip(1))
    assert torch.equal(first.y_units, second.y_units.flip(1))

    mirrored = {name: value.clone() for name, value in inputs.items()}
    mirrored["x_units"] = 18_000 - inputs["x_units"]
    mirrored["y_units"] = 32_000 - inputs["y_units"]
    mirrored["owner"] = 1 - inputs["owner"]
    mirrored_result = resolve_fast_collision_navigation(**mirrored)
    assert torch.equal(mirrored_result.x_units, 18_000 - first.x_units)
    assert torch.equal(mirrored_result.y_units, 32_000 - first.y_units)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_building_is_immobile_and_mover_steers_while_progressing(
    device_name: str,
) -> None:
    inputs = _inputs(device_name, entities=2)
    device = inputs["active"].device
    inputs["kind"][0, 1] = FAST_KIND_BUILDING
    inputs["x_units"][0] = torch.tensor([8_000, 9_000], device=device)
    inputs["intended_x_units"][0, 0] = 200
    inputs["movement_enabled"][0, 1] = False
    inputs["mass"][0, 1] = 20.0

    result = resolve_fast_collision_navigation(**inputs)

    assert result.x_units[0, 1].item() == 9_000
    assert result.y_units[0, 1].item() == 10_000
    assert result.x_units[0, 0].item() >= 8_000
    assert result.y_units[0, 0].item() != 10_000
    assert result.building_contact_count[0, 0].item() == 1


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_air_ignores_ground_and_hover_uses_air_contact_plane(
    device_name: str,
) -> None:
    inputs = _inputs(device_name, entities=4)
    inputs["x_units"].fill_(9_000)
    inputs["y_units"].fill_(10_000)
    inputs["airborne"][0, 1] = True
    inputs["hover"][0, 2] = True
    inputs["kind"][0, 3] = FAST_KIND_BUILDING

    result = resolve_fast_collision_navigation(**inputs)

    # Ground troop sees only the building. Air and hover see each other, while
    # hover passes through the ground building despite staying ground-targetable.
    assert result.troop_contact_count[0, 0].item() == 0
    assert result.building_contact_count[0, 0].item() == 1
    assert result.troop_contact_count[0, 1].item() == 1
    assert result.troop_contact_count[0, 2].item() == 1
    assert result.building_contact_count[0, 2].item() == 0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_bridge_queue_is_constrained_but_hover_crosses_river_directly(
    device_name: str,
) -> None:
    inputs = _inputs(device_name, entities=3)
    device = inputs["active"].device
    inputs["x_units"][0] = torch.tensor([3_300, 3_700, 9_000], device=device)
    inputs["y_units"][0] = torch.tensor([14_800, 14_400, 14_450], device=device)
    inputs["intended_y_units"].fill_(200)
    inputs["hover"][0, 2] = True

    result = resolve_fast_collision_navigation(**inputs)

    assert result.x_units[0, :2].min().item() >= 2_500
    assert result.x_units[0, :2].max().item() <= 4_500
    assert result.y_units[0, 2].item() == 14_650
    assert not result.terrain_constrained[0, 2]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_replay_exclusion_reset_and_slot_reuse_are_deterministic(
    device_name: str,
) -> None:
    inputs = _inputs(device_name, entities=3)
    inputs["x_units"].fill_(8_000)
    inputs["collision_excluded"][0, 2] = True

    first = resolve_fast_collision_navigation(**inputs)
    replay = resolve_fast_collision_navigation(**inputs)
    assert torch.equal(first.x_units, replay.x_units)
    assert torch.equal(first.y_units, replay.y_units)
    assert first.x_units[0, 2].item() == 8_000
    assert first.y_units[0, 2].item() == 10_000

    # A recycled physical slot gets its direction from the new stable ID.
    inputs["stable_id"][0, 0] = 101
    reused = resolve_fast_collision_navigation(**inputs)
    fresh = {name: value.clone() for name, value in inputs.items()}
    reset = resolve_fast_collision_navigation(**fresh)
    assert torch.equal(reused.x_units, reset.x_units)
    assert torch.equal(reused.y_units, reset.y_units)


def test_collision_hot_path_has_no_host_sync_card_dispatch_or_dynamic_compaction() -> (
    None
):
    source = inspect.getsource(resolve_fast_collision_navigation)
    source += inspect.getsource(
        __import__(
            "clasher.torch_sim.simple_collision_navigation",
            fromlist=["_stable_overlap_normal"],
        )._stable_overlap_normal
    )
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".numpy(",
        ".nonzero(",
        "card_id",
        "card_name",
    ):
        assert forbidden not in source


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_engine_steers_around_friendly_building_toward_actual_target(
    device_name: str,
) -> None:
    device = _device(device_name)
    loader = CardDataLoader()
    cards = TensorCardCatalog.compile(loader, ("Cannon", "Knight"), device=device)
    catalog = FastCardCatalog.from_tensor_catalog(cards, loader=loader)
    state = FastGymState.empty(1, max_entities=4, device=device)
    cannon = cards.name_to_id["Cannon"]
    knight = cards.name_to_id["Knight"]
    card_ids = torch.tensor([knight, cannon, knight], device=device)
    state.active[0, :3] = True
    state.stable_id[0, :3] = torch.tensor([10, 11, 12], device=device)
    state.owner[0, :3] = torch.tensor([0, 0, 1], dtype=torch.int8, device=device)
    state.card_id[0, :3] = card_ids
    state.kind[0, :3] = catalog.kind[card_ids]
    state.x_units[0, :3] = torch.tensor([7_900, 9_000, 12_000], device=device)
    state.y_units[0, :3] = 10_000
    state.hp[0, :3] = catalog.hitpoints[card_ids]
    state.max_hp[0, :3] = catalog.hitpoints[card_ids]
    state.damage[0, :3] = catalog.damage[card_ids]
    state.range_units[0, :3] = catalog.range_units[card_ids]
    state.sight_range_units[0, :3] = catalog.sight_range_units[card_ids]
    state.speed_units_per_tick[0, :3] = catalog.speed_units_per_tick[card_ids]
    state.hit_cooldown_ticks[0, :3] = catalog.hit_cooldown_ticks[card_ids]
    # Pending buildings already occupy arena space even though they cannot act.
    state.deploy_ticks[0, 1] = 10

    FastTensorGym(state, catalog).step_tick()

    assert state.target_id[0, 0].item() == 12
    assert state.x_units[0, 1].item() == 9_000
    assert state.y_units[0, 1].item() == 10_000
    assert state.deploy_ticks[0, 1].item() == 9
    assert state.x_units[0, 0].item() >= 7_900
    assert state.y_units[0, 0].item() != 10_000


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_river_jump_flows_route_jump_collision_and_resets(
    device_name: str,
) -> None:
    device = _device(device_name)
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("HogRider", "Knight"),
        device=device,
        canonical_lane_globals=True,
    )
    fast = setup.spawn_blueprints.fast_cards
    entity_tokens = torch.zeros((2, fast.size), dtype=torch.int64, device=device)
    hand_tokens = torch.zeros(fast.size, dtype=torch.int64, device=device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id])
        if kind >= 0:
            entity_tokens[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id]):
            hand_tokens[card_id] = 2_000 + card_id
    runtime = setup.create_runtime(
        [[("HogRider",) * 8, ("Knight",) * 8]],
        entity_token_lookup=entity_tokens,
        hand_token_lookup=hand_tokens,
        canonical_lane_globals=True,
        max_entities=16,
        max_effects=16,
    )
    assert runtime.river_jumps is not None
    hog = setup.cards.name_to_id["HogRider"]
    slot = 6
    state = runtime.state
    state.active[0, slot] = True
    state.stable_id[0, slot] = 50
    state.next_stable_id[0] = 51
    state.owner[0, slot] = 0
    state.card_id[0, slot] = hog
    state.kind[0, slot] = fast.kind[hog]
    state.x_units[0, slot] = 1_250
    state.y_units[0, slot] = 14_000
    state.hp[0, slot] = fast.hitpoints[hog]
    state.max_hp[0, slot] = fast.hitpoints[hog]
    state.damage[0, slot] = fast.damage[hog]
    state.range_units[0, slot] = fast.range_units[hog]
    state.sight_range_units[0, slot] = fast.sight_range_units[hog]
    state.speed_units_per_tick[0, slot] = fast.speed_units_per_tick[hog]
    state.hit_cooldown_ticks[0, slot] = fast.hit_cooldown_ticks[hog]
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=device)

    runtime.step_tick(noop)
    jump = runtime.combat.last_river_jump_step
    assert jump is not None
    assert jump.started[0, slot]
    assert runtime.river_jumps.active[0, slot]
    assert runtime._entity_airborne_target()[0, slot]
    assert not runtime.combat._body_traits().airborne[0, slot]
    assert runtime._entity_special[0, slot]
    assert state.x_units[0, slot].item() == 1_250
    assert state.y_units[0, slot].item() == 14_000

    runtime.step_tick(noop)
    assert state.y_units[0, slot].item() > 14_000
    assert runtime.river_jumps.active[0, slot]
    runtime.reset_rows(torch.ones(1, dtype=torch.bool, device=device))
    assert not runtime.river_jumps.active.any()
    assert not runtime.river_jumps.bound_stable_id.any()
