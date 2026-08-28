from __future__ import annotations

import inspect

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_engine import FastDeploymentRequest, FastTensorGym
from clasher.torch_sim.simple_state import (
    FAST_KIND_BUILDING,
    FAST_KIND_TROOP,
    FastGymState,
)


def _seed_catalog_entity(
    state: FastGymState,
    catalog: FastCardCatalog,
    *,
    slot: int,
    stable_id: int,
    owner: int,
    card_id: int,
    x_units: int,
) -> None:
    state.active[0, slot] = True
    state.stable_id[0, slot] = stable_id
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.kind[0, slot] = catalog.kind[card_id]
    state.x_units[0, slot] = x_units
    state.y_units[0, slot] = 10_000
    state.hp[0, slot] = catalog.hitpoints[card_id]
    state.max_hp[0, slot] = catalog.hitpoints[card_id]
    state.damage[0, slot] = catalog.damage[card_id]
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = catalog.speed_units_per_tick[card_id]
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_simple_noop_clock_and_deterministic_low_slot_deployment(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(2, max_entities=4, device=device)
    gym = FastTensorGym(state)

    noop = gym.step_tick()
    assert noop.committed.tolist() == [True, True]
    assert noop.action_success.tolist() == [[False, False], [False, False]]
    assert noop.native_ticks.tolist() == [1, 1]
    assert state.tick.tolist() == [1, 1]

    request = FastDeploymentRequest(
        valid=torch.tensor([True, False], device=device),
        owner=torch.tensor([1, 0], device=device),
        card_id=torch.tensor([17, 17], device=device),
        kind=torch.tensor([FAST_KIND_TROOP, FAST_KIND_TROOP], device=device),
        x_units=torch.tensor([4_500, 13_500], device=device),
        y_units=torch.tensor([20_500, 11_500], device=device),
        hp=torch.tensor([720.0, 720.0], device=device),
        deploy_ticks=torch.tensor([2, 2], device=device),
        summon_count=torch.ones(2, dtype=torch.int16, device=device),
        summon_radius_units=torch.full((2,), 500, dtype=torch.int32, device=device),
    )
    deployed = gym.step_tick(request)

    assert deployed.action_success.tolist() == [[False, True], [False, False]]
    assert deployed.native_ticks.tolist() == [1, 1]
    assert state.tick.tolist() == [2, 2]
    assert state.active.tolist() == [
        [True, False, False, False],
        [False, False, False, False],
    ]
    assert state.stable_id[0].tolist() == [1, 0, 0, 0]
    assert state.card_id[0].tolist() == [17, 0, 0, 0]
    assert state.owner[0, 0].item() == 1
    assert state.deploy_ticks[0, 0].item() == 1

    state.active[0, 0] = False
    state.hp[0, 0] = 0.0
    recycled = gym.step_tick(request)
    assert recycled.action_success.tolist() == [[False, True], [False, False]]
    assert state.stable_id[0].tolist() == [2, 0, 0, 0]
    assert state.next_stable_id.tolist() == [3, 1]


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_simple_knights_acquire_move_and_emit_one_committable_attack(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = BattleState()
    full_catalog = TensorCardCatalog.compile(
        battle.card_loader, ["Knight"], device=device
    )
    catalog = FastCardCatalog.from_tensor_catalog(full_catalog)
    knight = full_catalog.name_to_id["Knight"]
    state = FastGymState.empty(1, max_entities=4, device=device)
    state.active[0, :2] = True
    state.stable_id[0, :2] = torch.tensor([1, 2], device=device)
    state.next_stable_id[0] = 3
    state.owner[0, :2] = torch.tensor([0, 1], device=device)
    state.card_id[0, :2] = knight
    state.kind[0, :2] = catalog.kind[knight]
    state.x_units[0, :2] = torch.tensor([5_000, 7_000], device=device)
    state.y_units[0, :2] = 10_000
    state.hp[0, :2] = catalog.hitpoints[knight]
    state.max_hp[0, :2] = catalog.hitpoints[knight]
    state.damage[0, :2] = catalog.damage[knight]
    state.range_units[0, :2] = catalog.range_units[knight]
    state.sight_range_units[0, :2] = catalog.sight_range_units[knight]
    state.speed_units_per_tick[0, :2] = catalog.speed_units_per_tick[knight]
    state.hit_cooldown_ticks[0, :2] = catalog.hit_cooldown_ticks[knight]
    gym = FastTensorGym(state, catalog)

    before_gap = int(state.x_units[0, 1] - state.x_units[0, 0])
    gym.step_tick()
    after_gap = int(state.x_units[0, 1] - state.x_units[0, 0])
    assert state.target_id[0, :2].tolist() == [2, 1]
    assert 0 < after_gap < before_gap

    for _ in range(80):
        result = gym.step_tick()
        if bool(result.attack_ready.all()):
            break
    assert result.attack_ready[0, :2].tolist() == [True, True]
    assert not result.attack_ready[0, 2:].any()
    assert state.hp[0, :2].tolist() == state.max_hp[0, :2].tolist()
    assert state.cooldown_ticks[0, :2].tolist() == [0, 0]

    committed = gym.commit_attacks_(result.attack_ready, result.attack_ready)
    assert committed[0, :2].tolist() == [True, True]
    assert not committed[0, 2:].any()
    assert state.cooldown_ticks[0, :2].tolist() == (
        state.hit_cooldown_ticks[0, :2].tolist()
    )
    following = gym.step_tick()
    assert not bool(following.attack_ready.any())
    assert state.cooldown_ticks[0, :2].tolist() == (
        state.hit_cooldown_ticks[0, :2].sub(1).tolist()
    )


def test_simple_combat_hot_path_has_no_host_sync_or_dynamic_compaction() -> None:
    source = inspect.getsource(FastTensorGym._ordinary_troop_phase)
    source += inspect.getsource(FastTensorGym.step_tick)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source


def test_simple_target_tie_uses_stable_id_not_reused_physical_slot() -> None:
    state = FastGymState.empty(1, max_entities=4)
    state.active[0, :3] = True
    state.stable_id[0, :3] = torch.tensor([1, 9, 2])
    state.next_stable_id[0] = 10
    state.owner[0, :3] = torch.tensor([0, 1, 1])
    state.x_units[0, :3] = torch.tensor([5_000, 4_000, 6_000])
    state.y_units[0, :3] = 10_000
    state.hp[0, :3] = 1_000
    state.max_hp[0, :3] = 1_000
    state.sight_range_units[0, :3] = 10_000

    FastTensorGym(state).step_tick()

    assert int(state.target_id[0, 0]) == 2


def _full_matrix_navigation_reference(
    state: FastGymState,
    can_act: torch.Tensor,
    *,
    reserved_slot_floor: int,
    target_unavailable: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Former [B, E, E] implementation retained as a test oracle."""

    slots = torch.arange(state.max_entities, device=state.device).view(1, -1)
    delta_x = state.x_units[:, :, None].to(torch.int64) - state.x_units[:, None, :].to(
        torch.int64
    )
    delta_y = state.y_units[:, :, None].to(torch.int64) - state.y_units[:, None, :].to(
        torch.int64
    )
    distance_sq = delta_x.square() + delta_y.square()
    reserved_building = (
        (slots < reserved_slot_floor)
        & state.active
        & (state.hp > 0)
        & (state.kind == FAST_KIND_BUILDING)
        & (state.stable_id > 0)
        & ~target_unavailable
    )
    candidate = (
        can_act[:, :, None]
        & (state.kind[:, :, None] == FAST_KIND_TROOP)
        & reserved_building[:, None, :]
        & (state.owner[:, :, None] != state.owner[:, None, :])
    )
    maximum = torch.iinfo(torch.int64).max
    nearest_distance = torch.where(
        candidate,
        distance_sq,
        torch.full_like(distance_sq, maximum),
    ).amin(dim=2)
    distance_tie = candidate & (distance_sq == nearest_distance[:, :, None])
    candidate_id = state.stable_id[:, None, :].expand_as(distance_sq)
    selected_id = torch.where(
        distance_tie,
        candidate_id,
        torch.full_like(candidate_id, maximum),
    ).amin(dim=2)
    found = distance_tie.any(dim=2)
    selected = distance_tie & (candidate_id == selected_id[:, :, None])
    slot = selected.to(torch.int64).argmax(dim=2)
    distance = torch.sqrt(
        distance_sq.gather(2, slot[:, :, None]).squeeze(2).to(torch.float32)
    )
    return (
        found,
        slot,
        torch.where(found, selected_id, 0),
        torch.where(found, distance, torch.inf),
    )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
@pytest.mark.parametrize("reserved_slot_floor", (0, 4))
def test_reserved_navigation_slice_matches_full_matrix_reference(
    device: str,
    reserved_slot_floor: int,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    generator = torch.Generator().manual_seed(20260827)
    batch_size = 64
    entities = 13
    state = FastGymState.empty(batch_size, max_entities=entities, device=device)
    active = torch.rand((batch_size, entities), generator=generator) > 0.2
    hp = torch.randint(
        0, 2_000, (batch_size, entities), generator=generator, dtype=torch.int32
    ).to(torch.float32)
    kind = torch.randint(
        0, 2, (batch_size, entities), generator=generator, dtype=torch.int8
    )
    owner = torch.randint(
        0, 2, (batch_size, entities), generator=generator, dtype=torch.int8
    )
    x_units = torch.randint(
        0, 18_001, (batch_size, entities), generator=generator, dtype=torch.int32
    )
    y_units = torch.randint(
        0, 32_001, (batch_size, entities), generator=generator, dtype=torch.int32
    )
    stable_id = torch.stack(
        tuple(
            torch.randperm(entities, generator=generator, dtype=torch.int64)
            + 1
            + row * entities
            for row in range(batch_size)
        )
    )
    unavailable = torch.rand((batch_size, entities), generator=generator) < 0.2
    can_act = torch.rand((batch_size, entities), generator=generator) > 0.35
    state.active.copy_(active.to(device))
    state.hp.copy_(hp.to(device))
    state.kind.copy_(kind.to(device))
    state.owner.copy_(owner.to(device))
    state.x_units.copy_(x_units.to(device))
    state.y_units.copy_(y_units.to(device))
    state.stable_id.copy_(stable_id.to(device))

    if reserved_slot_floor:
        # Exact-distance tie resolved by stable ID, not physical slot.
        state.active[0, :2] = True
        state.hp[0, :2] = 1_000
        state.kind[0, :2] = FAST_KIND_BUILDING
        state.owner[0, :2] = 1
        state.stable_id[0, :2] = torch.tensor([99, 2], device=device)
        state.x_units[0, :2] = torch.tensor([4_000, 6_000], device=device)
        state.y_units[0, :2] = 5_000
        state.active[0, 6] = True
        state.kind[0, 6] = FAST_KIND_TROOP
        state.owner[0, 6] = 0
        state.x_units[0, 6] = 5_000
        state.y_units[0, 6] = 5_000
        can_act[0, 6] = True
        unavailable[0, :2] = False
        # A dead nearer tower, hidden nearer tower, and nonreserved building
        # exercise every exclusion that used to be applied after E-wide work.
        state.active[1:4, :2] = True
        state.hp[1:4, :2] = 1_000
        state.kind[1:4, :2] = FAST_KIND_BUILDING
        state.owner[1:4, :2] = 1
        state.x_units[1:4, 0] = 4_900
        state.x_units[1:4, 1] = 8_000
        state.y_units[1:4, :2] = 5_000
        state.active[1:4, 6] = True
        state.kind[1:4, 6] = FAST_KIND_TROOP
        state.owner[1:4, 6] = 0
        state.x_units[1:4, 6] = 5_000
        state.y_units[1:4, 6] = 5_000
        can_act[1:4, 6] = True
        unavailable[1:4, :2] = False
        state.hp[1, 0] = 0
        unavailable[2, 0] = True
        state.active[3, 8] = True
        state.hp[3, 8] = 1_000
        state.kind[3, 8] = FAST_KIND_BUILDING
        state.owner[3, 8] = 1
        state.x_units[3, 8] = 5_001
        state.y_units[3, 8] = 5_000

    can_act = can_act.to(device)
    unavailable = unavailable.to(device)
    gym = FastTensorGym(state, reserved_slot_floor=reserved_slot_floor)
    gym._target_unavailable.copy_(unavailable)

    expected = _full_matrix_navigation_reference(
        state,
        can_act,
        reserved_slot_floor=reserved_slot_floor,
        target_unavailable=unavailable,
    )
    actual = gym._navigation_targets(can_act)

    for observed, reference in zip(actual, expected):
        assert torch.equal(observed, reference)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_full_engine_giant_ignores_nearer_troop_for_building(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = BattleState()
    full = TensorCardCatalog.compile(
        battle.card_loader, ["Giant", "Knight", "Cannon"], device=device
    )
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    state = FastGymState.empty(1, max_entities=4, device=device)
    _seed_catalog_entity(
        state,
        catalog,
        slot=0,
        stable_id=1,
        owner=0,
        card_id=full.name_to_id["Giant"],
        x_units=0,
    )
    _seed_catalog_entity(
        state,
        catalog,
        slot=1,
        stable_id=2,
        owner=1,
        card_id=full.name_to_id["Knight"],
        x_units=1_000,
    )
    _seed_catalog_entity(
        state,
        catalog,
        slot=2,
        stable_id=3,
        owner=1,
        card_id=full.name_to_id["Cannon"],
        x_units=3_000,
    )
    state.next_stable_id[0] = 4

    FastTensorGym(state, catalog).step_tick()

    assert state.target_id[0, 0].item() == 3


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_full_engine_baby_dragon_acquires_air_then_ground(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = BattleState()
    full = TensorCardCatalog.compile(
        battle.card_loader,
        ["BabyDragon", "Minions", "Knight"],
        device=device,
    )
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    state = FastGymState.empty(1, max_entities=4, device=device)
    _seed_catalog_entity(
        state,
        catalog,
        slot=0,
        stable_id=1,
        owner=0,
        card_id=full.name_to_id["BabyDragon"],
        x_units=0,
    )
    _seed_catalog_entity(
        state,
        catalog,
        slot=1,
        stable_id=2,
        owner=1,
        card_id=full.name_to_id["Minions"],
        x_units=1_000,
    )
    _seed_catalog_entity(
        state,
        catalog,
        slot=2,
        stable_id=3,
        owner=1,
        card_id=full.name_to_id["Knight"],
        x_units=2_000,
    )
    state.next_stable_id[0] = 4
    gym = FastTensorGym(state, catalog)

    gym.step_tick()
    assert state.target_id[0, 0].item() == 2

    state.active[0, 1] = False
    state.hp[0, 1] = 0
    gym.step_tick()
    assert state.target_id[0, 0].item() == 3


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_out_of_sight_troop_navigates_to_reserved_enemy_building(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = BattleState()
    full = TensorCardCatalog.compile(battle.card_loader, ["Knight"], device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    knight = full.name_to_id["Knight"]
    state = FastGymState.empty(1, max_entities=4, device=device)
    state.active[0, :3] = True
    state.stable_id[0, :3] = torch.tensor([1, 2, 3], device=state.device)
    state.owner[0, :3] = torch.tensor([0, 1, 0], device=state.device)
    state.kind[0, :2] = 1
    state.kind[0, 2] = catalog.kind[knight]
    state.card_id[0, 2] = knight
    state.x_units[0, :3] = torch.tensor([0, 20_000, 2_000], device=state.device)
    state.y_units[0, :3] = 10_000
    state.hp[0, :3] = 1_000
    state.max_hp[0, :3] = 1_000
    state.damage[0, 2] = catalog.damage[knight]
    state.range_units[0, 2] = catalog.range_units[knight]
    state.sight_range_units[0, 2] = catalog.sight_range_units[knight]
    state.speed_units_per_tick[0, 2] = catalog.speed_units_per_tick[knight]
    state.hit_cooldown_ticks[0, 2] = catalog.hit_cooldown_ticks[knight]
    gym = FastTensorGym(state, catalog, reserved_slot_floor=2)
    building_x = state.x_units[0, :2].clone()
    troop_x = state.x_units[0, 2].clone()

    result = gym.step_tick()

    assert state.target_id[0, 2].item() == 2
    assert state.x_units[0, 2] > troop_x
    assert torch.equal(state.x_units[0, :2], building_x)
    assert not result.attack_ready[0, 2]
