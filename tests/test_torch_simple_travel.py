from __future__ import annotations

import inspect
from dataclasses import fields, replace
from typing import TypedDict

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import MECHANIC_OPCODE, TensorCardCatalog
from clasher.torch_sim.simple_impulse import compute_fast_radial_impulse
from clasher.torch_sim.simple_travel import (
    FAST_TRAVEL_DASH,
    FAST_TRAVEL_EMERGENCE,
    FAST_TRAVEL_IDLE,
    FAST_TRAVEL_IMPACT_AREA,
    FAST_TRAVEL_LANDING,
    FAST_TRAVEL_LEAP,
    FAST_TRAVEL_TRANSIT,
    FAST_TRAVEL_UNDERGROUND,
    FAST_TRAVEL_UNSUPPORTED,
    FAST_TRAVEL_WINDUP,
    FastTravelCatalog,
    FastTravelState,
    advance_fast_travel_,
    fast_travel_view,
    travel_impact_radial_impulse_inputs,
)

CARD_NAMES = ("Bandit", "MegaKnight", "Miner")


class TravelInputs(TypedDict):
    active: torch.Tensor
    stable_id: torch.Tensor
    card_id: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    spawned: torch.Tensor
    trigger: torch.Tensor
    target_stable_id: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    target_distance_units: torch.Tensor
    target_valid: torch.Tensor
    interrupted: torch.Tensor


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _catalog(device: str = "cpu") -> tuple[TensorCardCatalog, FastTravelCatalog]:
    loader = CardDataLoader()
    cards = TensorCardCatalog.compile(loader, CARD_NAMES, device=_device(device))
    return cards, FastTravelCatalog.compile(cards, loader)


def _planes(
    state: FastTravelState,
    *,
    stable_id: list[list[int]],
    card_id: list[list[int]],
    owner: list[list[int]] | None = None,
    x: list[list[int]] | None = None,
    y: list[list[int]] | None = None,
) -> TravelInputs:
    device = state.device
    shape = (state.batch_size, state.max_entities)
    owner = owner or [[0] * shape[1] for _ in range(shape[0])]
    x = x or [[0] * shape[1] for _ in range(shape[0])]
    y = y or [[0] * shape[1] for _ in range(shape[0])]
    stable = torch.tensor(stable_id, dtype=torch.int64, device=device)
    return {
        "active": stable > 0,
        "stable_id": stable,
        "card_id": torch.tensor(card_id, dtype=torch.int64, device=device),
        "owner": torch.tensor(owner, dtype=torch.int8, device=device),
        "x_units": torch.tensor(x, dtype=torch.int32, device=device),
        "y_units": torch.tensor(y, dtype=torch.int32, device=device),
        "spawned": torch.zeros(shape, dtype=torch.bool, device=device),
        "trigger": torch.zeros(shape, dtype=torch.bool, device=device),
        "target_stable_id": torch.zeros(shape, dtype=torch.int64, device=device),
        "target_x_units": torch.zeros(shape, dtype=torch.int32, device=device),
        "target_y_units": torch.zeros(shape, dtype=torch.int32, device=device),
        "target_distance_units": torch.zeros(shape, dtype=torch.int32, device=device),
        "target_valid": torch.zeros(shape, dtype=torch.bool, device=device),
        "interrupted": torch.zeros(shape, dtype=torch.bool, device=device),
    }


def test_current_serialized_profiles_compile_exact_calibration() -> None:
    cards, travel = _catalog()
    bandit = cards.name_to_id["Bandit"]
    mega = cards.name_to_id["MegaKnight"]
    miner = cards.name_to_id["Miner"]

    assert travel.kind.tolist() == [
        0,
        FAST_TRAVEL_DASH,
        FAST_TRAVEL_LEAP,
        FAST_TRAVEL_UNDERGROUND,
    ]
    assert travel.profile_supported.all()
    assert (
        travel.min_range_units[bandit].item(),
        travel.max_range_units[bandit].item(),
    ) == (3_500, 6_000)
    assert travel.windup_ticks[bandit].item() == 16
    assert travel.speed_units_per_tick[bandit].item() == 500
    assert travel.direct_damage[bandit].item() == 389
    assert travel.post_immunity_ticks[bandit].item() == 2
    assert (
        travel.min_range_units[mega].item(),
        travel.max_range_units[mega].item(),
    ) == (3_500, 5_000)
    assert travel.windup_ticks[mega].item() == 18
    assert travel.transit_ticks[mega].item() == 16
    assert travel.landing_ticks[mega].item() == 6
    assert travel.direct_damage[mega].item() == 537
    assert travel.spawn_damage[mega].item() == 430
    assert travel.impact_radius_units[mega].item() == 2_200
    assert travel.impact_push_units[mega].item() == 1_000
    assert travel.speed_units_per_tick[miner].item() == 650
    assert travel.direct_damage[miner].item() == 194
    assert travel.tower_damage[miner].item() == 39
    assert travel.emergence_ticks[miner].item() == 20


def test_duplicate_travel_opcode_fails_closed() -> None:
    loader = CardDataLoader()
    cards = TensorCardCatalog.compile(loader, CARD_NAMES)
    bandit = cards.name_to_id["Bandit"]
    opcodes = cards.mechanic_opcode.clone()
    counts = cards.mechanic_count.clone()
    opcodes[bandit, 1] = int(MECHANIC_OPCODE["BanditDash"])
    counts[bandit] = 2
    malformed = replace(cards, mechanic_opcode=opcodes, mechanic_count=counts)
    travel = FastTravelCatalog.compile(malformed, loader)
    assert travel.declares_travel[bandit]
    assert not travel.profile_supported[bandit]
    assert travel.kind[bandit].item() == FAST_TRAVEL_UNSUPPORTED
    assert travel.direct_damage[bandit].item() == 0


def test_malformed_raw_profile_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = CardDataLoader()
    cards = TensorCardCatalog.compile(loader, CARD_NAMES)
    stats = loader.get_card("Bandit")
    assert stats is not None
    character = stats._raw_entry["summonCharacterData"]
    monkeypatch.setitem(character, "dashMaxRange", 0)
    travel = FastTravelCatalog.compile(cards, loader)
    bandit = cards.name_to_id["Bandit"]
    assert travel.kind[bandit].item() == FAST_TRAVEL_UNSUPPORTED
    assert not travel.profile_supported[bandit]


def test_dash_range_boundaries_windup_cancel_and_terminal_command() -> None:
    cards, catalog = _catalog()
    bandit = cards.name_to_id["Bandit"]
    state = FastTravelState.empty(4, max_entities=1)
    values = _planes(
        state,
        stable_id=[[11], [12], [13], [14]],
        card_id=[[bandit]] * 4,
    )
    values["spawned"].fill_(True)
    values["trigger"].fill_(True)
    values["target_stable_id"][:, 0] = torch.tensor([21, 22, 23, 24])
    values["target_x_units"][:, 0] = torch.tensor([3_499, 3_500, 6_000, 6_001])
    values["target_distance_units"][:, 0] = torch.tensor([3_499, 3_500, 6_000, 6_001])
    values["target_valid"].fill_(True)
    result = advance_fast_travel_(catalog, state, **values)
    assert result.started[:, 0].tolist() == [False, True, True, False]
    assert state.phase[:, 0].tolist() == [
        FAST_TRAVEL_IDLE,
        FAST_TRAVEL_WINDUP,
        FAST_TRAVEL_WINDUP,
        FAST_TRAVEL_IDLE,
    ]

    values["spawned"].zero_()
    values["trigger"].zero_()
    values["interrupted"][1, 0] = True
    result = advance_fast_travel_(catalog, state, **values)
    assert result.cancelled[:, 0].tolist() == [False, True, False, False]
    assert state.phase[1, 0].item() == FAST_TRAVEL_IDLE
    values["interrupted"].zero_()
    for _ in range(14):
        result = advance_fast_travel_(catalog, state, **values)
    assert state.phase[2, 0].item() == FAST_TRAVEL_TRANSIT
    assert result.view.target_unavailable[2, 0]
    assert result.view.immune[2, 0]
    values["interrupted"][2, 0] = True
    for _ in range(12):
        result = advance_fast_travel_(catalog, state, **values)
        values["x_units"] = result.x_units
        values["y_units"] = result.y_units
        if result.completed[2, 0]:
            break
    else:
        pytest.fail("dash did not complete")
    assert result.impact.valid[2, 0]
    assert result.impact.target_stable_id[2, 0].item() == 23
    assert result.impact.damage[2, 0].item() == 389
    assert state.post_immunity_ticks[2, 0].item() == 2


def test_leap_spawn_slam_and_phase_boundaries() -> None:
    cards, catalog = _catalog()
    mega = cards.name_to_id["MegaKnight"]
    state = FastTravelState.empty(1, max_entities=1)
    values = _planes(
        state, stable_id=[[31]], card_id=[[mega]], x=[[1_000]], y=[[2_000]]
    )
    values["spawned"].fill_(True)
    result = advance_fast_travel_(catalog, state, **values)
    assert result.impact.valid[0, 0]
    assert result.impact.spawn_impact[0, 0]
    assert result.impact.kind[0, 0].item() == FAST_TRAVEL_IMPACT_AREA
    assert result.impact.damage[0, 0].item() == 430

    values["spawned"].zero_()
    values["trigger"].fill_(True)
    values["target_valid"].fill_(True)
    values["target_stable_id"].fill_(41)
    values["target_x_units"].fill_(5_000)
    values["target_y_units"].fill_(2_000)
    values["target_distance_units"].fill_(4_000)
    for tick in range(18):
        result = advance_fast_travel_(catalog, state, **values)
        values["trigger"].zero_()
    assert tick == 17
    assert state.phase[0, 0].item() == FAST_TRAVEL_TRANSIT
    for _ in range(16):
        result = advance_fast_travel_(catalog, state, **values)
        values["x_units"] = result.x_units
        values["y_units"] = result.y_units
    assert state.phase[0, 0].item() == FAST_TRAVEL_LANDING
    assert result.x_units[0, 0].item() == 5_000
    assert result.view.immune[0, 0]
    for _ in range(6):
        result = advance_fast_travel_(catalog, state, **values)
    assert state.phase[0, 0].item() == FAST_TRAVEL_IDLE
    assert result.impact.valid[0, 0]
    assert result.impact.damage[0, 0].item() == 537
    assert result.impact.radius_units[0, 0].item() == 2_200
    assert result.impact.push_units[0, 0].item() == 1_000


def test_miner_mirrored_origin_and_unavailable_until_emergence() -> None:
    cards, catalog = _catalog()
    miner = cards.name_to_id["Miner"]
    state = FastTravelState.empty(2, max_entities=1)
    values = _planes(
        state,
        stable_id=[[51], [52]],
        card_id=[[miner], [miner]],
        owner=[[0], [1]],
        x=[[9_000], [9_000]],
        y=[[3_150], [28_850]],
    )
    values["spawned"].fill_(True)
    result = advance_fast_travel_(catalog, state, **values)
    assert result.y_units[:, 0].tolist() == [2_500, 29_500]
    assert state.destination_y_units[:, 0].tolist() == [3_150, 28_850]
    assert result.view.target_unavailable[:, 0].all()
    assert result.view.immune[:, 0].all()
    assert result.view.combat_blocked[:, 0].all()
    assert result.view.movement_blocked[:, 0].all()
    values["spawned"].zero_()
    values["x_units"] = result.x_units
    values["y_units"] = result.y_units
    result = advance_fast_travel_(catalog, state, **values)
    values["x_units"] = result.x_units
    values["y_units"] = result.y_units
    assert state.phase[:, 0].tolist() == [FAST_TRAVEL_EMERGENCE] * 2
    assert result.view.immune[:, 0].all()
    for _ in range(19):
        result = advance_fast_travel_(catalog, state, **values)
    assert result.view.immune[:, 0].all()
    result = advance_fast_travel_(catalog, state, **values)
    assert state.phase[:, 0].tolist() == [FAST_TRAVEL_IDLE] * 2
    assert not result.view.target_unavailable.any()


def test_slot_reuse_and_row_reset_clear_every_plane() -> None:
    cards, catalog = _catalog()
    bandit = cards.name_to_id["Bandit"]
    state = FastTravelState.empty(2, max_entities=1)
    values = _planes(state, stable_id=[[61], [62]], card_id=[[bandit], [bandit]])
    values["spawned"].fill_(True)
    values["trigger"].fill_(True)
    values["target_valid"].fill_(True)
    values["target_stable_id"].fill_(70)
    values["target_x_units"].fill_(4_000)
    values["target_distance_units"].fill_(4_000)
    advance_fast_travel_(catalog, state, **values)
    values["spawned"].zero_()
    values["trigger"].zero_()
    values["stable_id"][0, 0] = 99
    result = advance_fast_travel_(catalog, state, **values)
    assert result.stale_cleared[0, 0]
    assert state.bound_stable_id[0, 0].item() == 0
    state.reset_rows_(torch.tensor([False, True]))
    for descriptor in fields(state):
        if descriptor.name != "device":
            assert not getattr(state, descriptor.name)[1].any()


@pytest.mark.parametrize("device_name", ["cpu", "cuda"])
def test_seedless_replay_is_device_deterministic(device_name: str) -> None:
    device = _device(device_name)
    cards, catalog = _catalog(device_name)
    mega = cards.name_to_id["MegaKnight"]
    base = FastTravelState.empty(1, max_entities=2, device=device)
    values = _planes(
        base,
        stable_id=[[81, 82]],
        card_id=[[mega, mega]],
        x=[[0, 1_000]],
        y=[[0, 2_000]],
    )
    values["spawned"].fill_(True)
    left = base.clone()
    right = base.clone()
    left_result = advance_fast_travel_(catalog, left, **values)
    right_result = advance_fast_travel_(catalog, right, **values)
    for descriptor in fields(left):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(left, descriptor.name), getattr(right, descriptor.name)
            )
    for descriptor in fields(left_result.impact):
        assert torch.equal(
            getattr(left_result.impact, descriptor.name),
            getattr(right_result.impact, descriptor.name),
        )


def test_area_impact_structurally_adapts_to_shared_impulse() -> None:
    cards, catalog = _catalog()
    mega = cards.name_to_id["MegaKnight"]
    state = FastTravelState.empty(1, max_entities=1)
    values = _planes(
        state, stable_id=[[91]], card_id=[[mega]], x=[[1_000]], y=[[1_000]]
    )
    values["spawned"].fill_(True)
    result = advance_fast_travel_(catalog, state, **values)
    impulse = travel_impact_radial_impulse_inputs(
        result.impact,
        target_x_units=torch.tensor([[2_000, 4_000]], dtype=torch.int32),
        target_y_units=torch.tensor([[1_000, 1_000]], dtype=torch.int32),
        target_stable_id=torch.tensor([[101, 102]], dtype=torch.int64),
        eligible=torch.ones((1, 1, 2), dtype=torch.bool),
    )
    displaced = compute_fast_radial_impulse(impulse)
    assert displaced.dx_units.tolist() == [[1_000, 0]]
    assert displaced.dy_units.tolist() == [[0, 0]]


def test_hot_path_has_no_names_or_host_sync() -> None:
    source = inspect.getsource(advance_fast_travel_)
    for forbidden in ("Bandit", "MegaKnight", "Miner", ".item(", ".cpu(", ".tolist("):
        assert forbidden not in source
    view_source = inspect.getsource(fast_travel_view)
    for forbidden in (".item(", ".cpu(", ".tolist("):
        assert forbidden not in view_source
