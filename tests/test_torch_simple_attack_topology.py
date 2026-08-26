from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_attack_effects import (
    FastEffectCommands,
    allocate_fast_attack_effects_,
)
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import FastEffectState, step_fast_effects
from clasher.torch_sim.simple_state import FastGymState

TOPOLOGY_CARDS = (
    "DarkPrince",
    "ElectroWizard",
    "Knight",
    "MegaKnight",
    "Princess",
    "RoyalGhost",
    "Valkyrie",
)


def _catalog(device: str) -> tuple[FastCardCatalog, dict[str, int]]:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    loader = BattleState().card_loader
    full = TensorCardCatalog.compile(loader, TOPOLOGY_CARDS, device=device)
    return (
        FastCardCatalog.from_tensor_catalog(full, loader=loader),
        full.name_to_id,
    )


def _seed_entity(
    state: FastGymState,
    catalog: FastCardCatalog,
    *,
    slot: int,
    stable_id: int,
    owner: int,
    card_id: int,
    x_units: int,
    y_units: int,
) -> None:
    state.active[0, slot] = True
    state.stable_id[0, slot] = stable_id
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.kind[0, slot] = catalog.kind[card_id]
    state.x_units[0, slot] = x_units
    state.y_units[0, slot] = y_units
    state.hp[0, slot] = 1_000.0
    state.max_hp[0, slot] = 1_000.0


def _run_attack(
    state: FastGymState,
    catalog: FastCardCatalog,
    *,
    source_slot: int = 0,
    primary_slot: int = 1,
) -> tuple[FastGymState, FastEffectState, torch.Tensor, torch.Tensor]:
    effects = FastEffectState.empty(1, max_effects=1, device=state.device)
    consume = torch.zeros((1, 1), dtype=torch.int64, device=state.device)
    commands = FastEffectCommands(
        ready=torch.ones((1, 1), dtype=torch.bool, device=state.device),
        source_id=state.stable_id[:, source_slot : source_slot + 1],
        owner=state.owner[:, source_slot : source_slot + 1],
        card_id=state.card_id[:, source_slot : source_slot + 1],
        source_x_units=state.x_units[:, source_slot : source_slot + 1],
        source_y_units=state.y_units[:, source_slot : source_slot + 1],
        target_id=state.stable_id[:, primary_slot : primary_slot + 1],
        target_x_units=state.x_units[:, primary_slot : primary_slot + 1],
        target_y_units=state.y_units[:, primary_slot : primary_slot + 1],
        damage_multiplier=torch.ones((1, 1), dtype=torch.float32, device=state.device),
    )
    allocation = allocate_fast_attack_effects_(
        state, effects, consume, catalog, commands
    )
    status_kind = torch.zeros_like(state.kind)
    status_ticks = torch.zeros_like(state.x_units)
    safe_card = state.card_id.clamp(0, catalog.size - 1)
    result = step_fast_effects(
        state,
        effects,
        status_kind,
        status_ticks,
        consume_source_id=consume,
        entity_is_air=catalog.is_air[safe_card],
        entity_collision_radius_units=catalog.collision_radius_units[safe_card],
    )
    assert allocation.accepted.tolist() == [[True]]
    assert result.impacted.tolist() == [[True]]
    return state, effects, status_kind, status_ticks


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_serialized_circle_and_multi_target_tables(device: str) -> None:
    catalog, ids = _catalog(device)

    assert int(catalog.effect_radius_units[ids["Valkyrie"]]) == 2_000
    assert bool(catalog.effect_center_on_source[ids["Valkyrie"]])
    assert int(catalog.effect_radius_units[ids["DarkPrince"]]) == 1_100
    assert not bool(catalog.effect_center_on_source[ids["DarkPrince"]])
    assert int(catalog.effect_radius_units[ids["Princess"]]) == 2_500
    assert not bool(catalog.effect_center_on_source[ids["Princess"]])
    assert int(catalog.effect_radius_units[ids["RoyalGhost"]]) == 1_000
    assert not bool(catalog.effect_center_on_source[ids["RoyalGhost"]])
    assert int(catalog.effect_radius_units[ids["MegaKnight"]]) == 1_300
    assert not bool(catalog.effect_center_on_source[ids["MegaKnight"]])
    assert int(catalog.multi_target_count[ids["ElectroWizard"]]) == 2
    assert bool(catalog.multi_repeat_primary[ids["ElectroWizard"]])
    assert int(catalog.status_duration_ticks[ids["ElectroWizard"]]) == 10


@pytest.mark.parametrize("device", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("card_name", "source_x", "primary_x", "splash_x", "miss_x"),
    (
        ("Valkyrie", 0, 1_000, -1_500, 2_500),
        ("DarkPrince", 0, 1_000, 1_900, -500),
        ("Princess", 0, 500, 2_700, 3_100),
    ),
)
def test_serialized_attack_circles_hit_only_their_source_or_target_neighborhood(
    device: str,
    card_name: str,
    source_x: int,
    primary_x: int,
    splash_x: int,
    miss_x: int,
) -> None:
    catalog, ids = _catalog(device)
    state = FastGymState.empty(1, max_entities=4, device=device)
    _seed_entity(
        state,
        catalog,
        slot=0,
        stable_id=10,
        owner=0,
        card_id=ids[card_name],
        x_units=source_x,
        y_units=1_000,
    )
    for slot, stable_id, x_units in (
        (1, 20, primary_x),
        (2, 21, splash_x),
        (3, 22, miss_x),
    ):
        _seed_entity(
            state,
            catalog,
            slot=slot,
            stable_id=stable_id,
            owner=1,
            card_id=ids["Knight"],
            x_units=x_units,
            y_units=1_000,
        )

    replay = state.clone()
    result, effects, _, _ = _run_attack(state, catalog)
    replay_result, replay_effects, _, _ = _run_attack(replay, catalog)

    expected_damage = float(catalog.effect_damage[ids[card_name]])
    assert result.hp[0, 1].item() == pytest.approx(1_000.0 - expected_damage)
    assert result.hp[0, 2].item() == pytest.approx(1_000.0 - expected_damage)
    assert result.hp[0, 3].item() == pytest.approx(1_000.0)
    for descriptor in fields(result):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(result, descriptor.name),
                getattr(replay_result, descriptor.name),
            )
    assert torch.equal(effects.active, replay_effects.active)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_multi_target_selects_stable_nearest_and_repeats_lone_primary(
    device: str,
) -> None:
    catalog, ids = _catalog(device)
    state = FastGymState.empty(1, max_entities=4, device=device)
    _seed_entity(
        state,
        catalog,
        slot=0,
        stable_id=10,
        owner=0,
        card_id=ids["ElectroWizard"],
        x_units=0,
        y_units=0,
    )
    for slot, stable_id, x_units in (
        (1, 20, 0),
        (2, 30, -1_000),
        (3, 21, 1_000),
    ):
        _seed_entity(
            state,
            catalog,
            slot=slot,
            stable_id=stable_id,
            owner=1,
            card_id=ids["Knight"],
            x_units=x_units,
            y_units=4_000,
        )

    replay = state.clone()
    result, _, status_kind, status_ticks = _run_attack(state, catalog)
    replay_result, _, replay_status_kind, replay_status_ticks = _run_attack(
        replay, catalog
    )
    damage = float(catalog.effect_damage[ids["ElectroWizard"]])

    assert result.hp[0].tolist() == pytest.approx(
        [1_000.0, 1_000.0 - damage, 1_000.0, 1_000.0 - damage]
    )
    assert status_ticks[0].tolist() == [0, 10, 0, 10]
    assert torch.equal(result.hp, replay_result.hp)
    assert torch.equal(status_kind, replay_status_kind)
    assert torch.equal(status_ticks, replay_status_ticks)

    lone = FastGymState.empty(1, max_entities=2, device=device)
    _seed_entity(
        lone,
        catalog,
        slot=0,
        stable_id=10,
        owner=0,
        card_id=ids["ElectroWizard"],
        x_units=0,
        y_units=0,
    )
    _seed_entity(
        lone,
        catalog,
        slot=1,
        stable_id=20,
        owner=1,
        card_id=ids["Knight"],
        x_units=0,
        y_units=4_000,
    )
    lone, _, _, lone_status_ticks = _run_attack(lone, catalog)
    assert lone.hp[0, 1].item() == pytest.approx(1_000.0 - 2.0 * damage)
    assert int(lone_status_ticks[0, 1]) == 10


def test_topology_hot_path_has_no_sync_or_card_dispatch() -> None:
    source = inspect.getsource(step_fast_effects)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in (
        "Valkyrie",
        "DarkPrince",
        "Princess",
        "RoyalGhost",
        "MegaKnight",
        "ElectroWizard",
    ):
        assert card_name not in source
