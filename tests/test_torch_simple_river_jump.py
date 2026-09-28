from __future__ import annotations

import copy
import inspect
import math
from typing import Any

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_river_jump import (
    FAST_RIVER_JUMP_TICK_MS,
    FastRiverJumpCatalog,
    FastRiverJumpState,
    _integer_sqrt,
    fast_river_jump_target_eligible,
    step_fast_river_jump_,
)
from clasher.torch_sim.simple_standard import compile_standard_simple_setup


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    if name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    return torch.device(name)


def _catalog(
    device_name: str,
) -> tuple[FastRiverJumpCatalog, TensorCardCatalog, dict[str, int]]:
    device = _device(device_name)
    loader = CardDataLoader()
    names = ("Bandit", "DarkPrince", "HogRider", "Knight", "Prince", "RoyalHogs")
    if device.type == "mps":
        setup = compile_standard_simple_setup(
            loader,
            names,
            device=device,
            canonical_lane_globals=True,
        )
        return setup.river_jump_catalog, setup.cards, setup.cards.name_to_id
    core = TensorCardCatalog.compile(
        loader,
        names,
        device=device,
    )
    return FastRiverJumpCatalog.compile(core, loader), core, core.name_to_id


def _planes(
    device_name: str,
    *,
    entities: int = 1,
    card_name: str = "HogRider",
) -> tuple[
    FastRiverJumpCatalog,
    FastRiverJumpState,
    dict[str, int],
    dict[str, torch.Tensor],
]:
    catalog, _, ids = _catalog(device_name)
    device = catalog.device
    state = FastRiverJumpState.empty(1, entities, device=device)
    planes = {
        "entity_active": torch.ones((1, entities), dtype=torch.bool, device=device),
        "stable_id": torch.arange(
            11, 11 + entities, dtype=torch.int64, device=device
        ).view(1, -1),
        "card_id": torch.full(
            (1, entities), ids[card_name], dtype=torch.int64, device=device
        ),
        "owner": torch.zeros((1, entities), dtype=torch.int8, device=device),
        "permanent_airborne": torch.zeros(
            (1, entities), dtype=torch.bool, device=device
        ),
        "stunned": torch.zeros((1, entities), dtype=torch.bool, device=device),
        "x_units": torch.full((1, entities), 1_250, dtype=torch.int32, device=device),
        "y_units": torch.full((1, entities), 14_000, dtype=torch.int32, device=device),
        "route_x_units": torch.full(
            (1, entities), 1_250, dtype=torch.int32, device=device
        ),
        "route_y_units": torch.full(
            (1, entities), 18_000, dtype=torch.int32, device=device
        ),
    }
    return catalog, state, ids, planes


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_integer_sqrt_is_exact_at_every_arena_discontinuity(
    device_name: str,
) -> None:
    device = _device(device_name)
    # The standard 18x32-tile arena uses 1,000 logic units per tile.  An
    # arena-contained displacement therefore cannot exceed this diagonal.
    maximum_squared_distance = 18_000**2 + 32_000**2
    maximum_root = math.isqrt(maximum_squared_distance)
    roots = torch.arange(maximum_root + 1, dtype=torch.int64)
    squares = roots.square()
    values = torch.cat(
        (
            (squares - 1).clamp_min(0),
            squares,
            (squares + 1).clamp_max(maximum_squared_distance),
            torch.tensor([maximum_squared_distance], dtype=torch.int64),
        )
    )
    expected = torch.tensor(
        [math.isqrt(int(value)) for value in values], dtype=torch.int64
    )

    actual = _integer_sqrt(values.to(device)).cpu()

    assert torch.equal(actual, expected)


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_catalog_compiles_exact_enabled_serialized_profiles(device_name: str) -> None:
    catalog, _, ids = _catalog(device_name)

    for name in ("DarkPrince", "HogRider", "Prince", "RoyalHogs"):
        card_id = ids[name]
        assert bool(catalog.declares_jump[card_id])
        assert bool(catalog.profile_supported[card_id])
        assert bool(catalog.jump_capable[card_id])
        assert int(catalog.jump_height_units[card_id]) == 4_000
        assert int(catalog.jump_speed_units_per_tick[card_id]) == 160

    ordinary = ids["Knight"]
    assert not bool(catalog.declares_jump[ordinary])
    assert bool(catalog.profile_supported[ordinary])
    assert not bool(catalog.jump_capable[ordinary])
    dash_only = ids["Bandit"]
    assert not bool(catalog.declares_jump[dash_only])
    assert bool(catalog.profile_supported[dash_only])
    assert not bool(catalog.jump_capable[dash_only])


@pytest.mark.parametrize(
    "bad_speed",
    (None, 0, -1, float("nan"), 160.5, True, "160", pytest.param("missing")),
)
def test_partial_or_malformed_serialized_declaration_fails_closed(
    bad_speed: object,
) -> None:
    loader = CardDataLoader()
    core = TensorCardCatalog.compile(loader, ["HogRider"])
    original = loader.get_card("HogRider")
    assert original is not None
    malformed = copy.deepcopy(original)
    raw = copy.deepcopy(malformed._raw_entry)
    if bad_speed == "missing":
        raw["summonCharacterData"].pop("jumpSpeed")
    else:
        raw["summonCharacterData"]["jumpSpeed"] = bad_speed
    malformed._raw_entry = raw

    class Loader:
        def get_card(self, _name: str) -> Any:
            return malformed

    catalog = FastRiverJumpCatalog.compile(core, Loader())  # type: ignore[arg-type]
    card_id = core.name_to_id["HogRider"]

    assert bool(catalog.declares_jump[card_id])
    assert not bool(catalog.profile_supported[card_id])
    assert not bool(catalog.jump_capable[card_id])
    assert int(catalog.jump_height_units[card_id]) == 0
    assert int(catalog.jump_speed_units_per_tick[card_id]) == 0


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_off_bridge_crossing_starts_mirrored_committed_jump(device_name: str) -> None:
    catalog, state, _, planes = _planes(device_name, entities=2)
    device = state.device
    planes["stable_id"][0] = torch.tensor([11, 12], device=device)
    planes["owner"][0] = torch.tensor([0, 1], dtype=torch.int8, device=device)
    planes["x_units"][0] = torch.tensor(
        [1_250, 16_750], dtype=torch.int32, device=device
    )
    planes["y_units"][0] = torch.tensor(
        [14_000, 18_000], dtype=torch.int32, device=device
    )
    planes["route_x_units"][0] = torch.tensor(
        [1_250, 16_750], dtype=torch.int32, device=device
    )
    planes["route_y_units"][0] = torch.tensor(
        [18_000, 14_000], dtype=torch.int32, device=device
    )

    result = step_fast_river_jump_(state, catalog, **planes)

    assert result.started.all()
    assert result.active.all()
    assert result.airborne_target.all()
    assert result.ordinary_movement_blocked.all()
    assert result.combat_blocked.all()
    assert torch.equal(result.x_units, planes["x_units"])
    assert torch.equal(result.y_units, planes["y_units"])
    assert state.origin_x_units.tolist() == [[1_250, 16_750]]
    assert state.origin_y_units.tolist() == [[14_000, 18_000]]
    assert state.landing_x_units.tolist() == [[1_250, 16_750]]
    assert state.landing_y_units.tolist() == [[17_250, 14_750]]
    assert state.duration_ticks.tolist() == [[21, 21]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_bridge_route_and_nonjump_character_remain_ordinary(device_name: str) -> None:
    catalog, state, ids, planes = _planes(device_name, entities=2)
    device = state.device
    planes["stable_id"][0] = torch.tensor([11, 12], device=device)
    planes["x_units"][0] = torch.tensor(
        [3_500, 1_250], dtype=torch.int32, device=device
    )
    planes["route_x_units"][0] = torch.tensor(
        [3_500, 1_250], dtype=torch.int32, device=device
    )
    planes["card_id"][0] = torch.tensor([ids["HogRider"], ids["Knight"]], device=device)

    result = step_fast_river_jump_(state, catalog, **planes)

    assert not result.started.any()
    assert not result.active.any()
    assert not result.ordinary_movement_blocked.any()
    assert not result.profile_rejected.any()


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_committed_flight_timing_landing_and_attack_plane(device_name: str) -> None:
    catalog, state, _, planes = _planes(device_name)
    started = step_fast_river_jump_(state, catalog, **planes)
    assert started.started.all()

    # Route changes and stun after takeoff do not cancel a committed jump.
    planes["route_x_units"].fill_(17_000)
    planes["route_y_units"].fill_(14_000)
    planes["stunned"].fill_(True)
    for tick in range(1, 22):
        step = step_fast_river_jump_(state, catalog, **planes)
        if tick < 21:
            assert step.active.all()
            assert not step.landed.any()
            assert step.airborne_target.all()
            assert step.ground_collision_blocked.all()
        else:
            assert step.landed.all()
            assert not step.active.any()
            assert step.special_consumed_tick.all()
            assert step.ordinary_movement_blocked.all()
            assert step.combat_blocked.all()
            assert step.x_units.tolist() == [[1_250]]
            assert step.y_units.tolist() == [[17_250]]

    target_active = torch.ones((1, 3), dtype=torch.bool, device=state.device)
    jump_active = torch.tensor([[True, True, False]], device=state.device)
    eligible = fast_river_jump_target_eligible(
        target_active=target_active,
        target_river_jump_active=jump_active,
        source_hits_air=torch.tensor([[False, True, False]], device=state.device),
        source_hits_ground=torch.tensor([[True, False, True]], device=state.device),
    )
    assert eligible.tolist() == [[False, True, True]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_only_removal_or_stable_slot_reuse_cancels_flight(device_name: str) -> None:
    catalog, state, _, planes = _planes(device_name)
    step_fast_river_jump_(state, catalog, **planes)

    planes["entity_active"].zero_()
    removed = step_fast_river_jump_(state, catalog, **planes)
    assert removed.cancelled.all()
    assert not state.active.any()
    assert not state.bound_stable_id.any()

    planes["entity_active"].fill_(True)
    planes["stable_id"].fill_(12)
    restarted = step_fast_river_jump_(state, catalog, **planes)
    assert restarted.started.all()
    planes["stable_id"].fill_(13)
    reused = step_fast_river_jump_(state, catalog, **planes)
    assert reused.cancelled.all()
    assert reused.started.all()
    assert state.bound_stable_id.tolist() == [[13]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_reset_reuse_and_replay_are_deterministic(device_name: str) -> None:
    catalog, first, _, first_planes = _planes(device_name)
    second = FastRiverJumpState.empty(1, 1, device=first.device)
    second_planes = {name: value.clone() for name, value in first_planes.items()}

    for _ in range(23):
        one = step_fast_river_jump_(first, catalog, **first_planes)
        two = step_fast_river_jump_(second, catalog, **second_planes)
        for field in (
            "x_units",
            "y_units",
            "started",
            "landed",
            "active",
            "ordinary_movement_blocked",
            "combat_blocked",
        ):
            assert torch.equal(getattr(one, field), getattr(two, field))
        first_planes["x_units"].copy_(one.x_units)
        first_planes["y_units"].copy_(one.y_units)
        second_planes["x_units"].copy_(two.x_units)
        second_planes["y_units"].copy_(two.y_units)

    first.reset_rows_(torch.ones(1, dtype=torch.bool, device=first.device))
    assert not first.active.any()
    assert not first.bound_stable_id.any()
    assert not first.duration_ticks.any()


def test_tick_contract_input_validation_and_hot_path_are_explicit() -> None:
    catalog, state, _, planes = _planes("cpu")
    with pytest.raises(ValueError, match="50 ms"):
        step_fast_river_jump_(state, catalog, **planes, dt_ms=100)

    assert FAST_RIVER_JUMP_TICK_MS == 50
    source = inspect.getsource(step_fast_river_jump_)
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".numpy(",
        ".nonzero(",
        "card_name",
    ):
        assert forbidden not in source
