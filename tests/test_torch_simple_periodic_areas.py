from __future__ import annotations

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import (
    FAST_CARD_EFFECT_AREA,
    FAST_CARD_EFFECT_UNSUPPORTED,
    FastCardCatalog,
)
from clasher.torch_sim.simple_effects import FAST_STATUS_SLOW, FAST_STATUS_STUN
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_state import FAST_KIND_BUILDING, FAST_KIND_TROOP


def _device(request: pytest.FixtureRequest) -> torch.device:
    name = str(request.param)
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> torch.device:
    return _device(request)


def _runtime(
    spell_name: str, device: torch.device
) -> tuple[SimpleGymRuntime, FastCardCatalog, dict[str, int]]:
    battle = BattleState()
    names = [spell_name, "Knight", "Minions"]
    full = TensorCardCatalog.compile(battle.card_loader, names, device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    ids = full.name_to_id
    deck = torch.stack(
        (
            torch.full((8,), ids[spell_name], dtype=torch.int64, device=device),
            torch.full((8,), ids["Knight"], dtype=torch.int64, device=device),
        )
    ).unsqueeze(0)
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), ids["Knight"], dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.tensor(
            [[2_000.0, 2_000.0, 3_000.0], [2_000.0, 2_000.0, 3_000.0]],
            device=device,
        ),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )
    size = catalog.size
    return (
        SimpleGymRuntime(
            deck,
            catalog,
            tower_spec,
            FastMatchRules(regulation_ticks=400, tiebreak_ticks=600),
            entity_token_lookup=torch.zeros(
                (2, size), dtype=torch.int64, device=device
            ),
            hand_token_lookup=torch.arange(size, dtype=torch.int64, device=device),
            max_entities=12,
            starting_elixir=10.0,
        ),
        catalog,
        ids,
    )


def _add_target(
    runtime: SimpleGymRuntime,
    *,
    slot: int,
    card_id: int,
    kind: int = FAST_KIND_TROOP,
    x: int = 4_000,
    y: int = 25_000,
) -> None:
    state = runtime.state
    state.active[0, slot] = True
    state.stable_id[0, slot] = slot + 1
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), slot + 2)
    state.kind[0, slot] = kind
    state.owner[0, slot] = 1
    state.card_id[0, slot] = card_id
    state.x_units[0, slot] = x
    state.y_units[0, slot] = y
    state.hp[0, slot] = 2_000.0
    state.max_hp[0, slot] = 2_000.0


def _cast(runtime: SimpleGymRuntime) -> torch.Tensor:
    target_tile = 25 * BOARD_WIDTH + 3
    action = torch.tensor([[target_tile, NO_OP_ACTION]], device=runtime.device)
    result = runtime.step_tick(action)
    assert result.action_success.tolist() == [[True, True]]
    return torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )


def test_periodic_area_catalog_admits_only_truthful_primitives() -> None:
    battle = BattleState()
    names = (
        "Earthquake",
        "Freeze",
        "Poison",
        "Tornado",
        "Zap",
        "Graveyard",
        "RoyalDelivery",
    )
    full = TensorCardCatalog.compile(battle.card_loader, names)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)

    for name in ("Earthquake", "Freeze", "Poison", "Tornado", "Zap"):
        card = full.name_to_id[name]
        assert int(catalog.effect_kind[card]) == FAST_CARD_EFFECT_AREA
        assert bool(catalog.training_supported[card])
    for name in ("Graveyard", "RoyalDelivery"):
        card = full.name_to_id[name]
        assert int(catalog.effect_kind[card]) == FAST_CARD_EFFECT_UNSUPPORTED
        assert not bool(catalog.training_supported[card])

    earthquake = full.name_to_id["Earthquake"]
    freeze = full.name_to_id["Freeze"]
    poison = full.name_to_id["Poison"]
    tornado = full.name_to_id["Tornado"]
    assert catalog.max_damage_hits[[earthquake, poison]].tolist() == [3, 8]
    assert int(catalog.status_kind[earthquake]) == FAST_STATUS_SLOW
    assert int(catalog.status_kind[freeze]) == FAST_STATUS_STUN
    assert int(catalog.max_status_scans[freeze]) == 1
    assert bool(catalog.damage_on_spawn[freeze])
    assert not bool(catalog.damage_on_spawn[poison])
    assert not bool(catalog.hits_air[earthquake])
    assert bool(catalog.omits_displacement[tornado])


def test_poison_uses_serialized_periodic_cadence_and_tower_scale(
    tensor_device: torch.device,
) -> None:
    runtime, _, ids = _runtime("Poison", tensor_device)
    _add_target(runtime, slot=6, card_id=ids["Knight"])
    noop = _cast(runtime)
    tower_before = 2_000.0
    troop_before = 2_000.0

    for _ in range(18):
        runtime.step_tick(noop)
    assert float(runtime.state.hp[0, 3]) == tower_before
    assert float(runtime.state.hp[0, 6]) == troop_before
    runtime.step_tick(noop)
    assert float(runtime.state.hp[0, 3]) == pytest.approx(tower_before - 21.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(troop_before - 92.0)

    for _ in range(140):
        runtime.step_tick(noop)
    assert float(runtime.state.hp[0, 3]) == pytest.approx(tower_before - 8 * 21.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(troop_before - 8 * 92.0)
    assert not bool(runtime.effects.active.any())


def test_earthquake_scales_buildings_and_respects_ground_plane(
    tensor_device: torch.device,
) -> None:
    runtime, _, ids = _runtime("Earthquake", tensor_device)
    _add_target(
        runtime, slot=6, card_id=ids["Knight"], kind=FAST_KIND_BUILDING
    )
    _add_target(runtime, slot=7, card_id=ids["Minions"])
    noop = _cast(runtime)
    for _ in range(59):
        runtime.step_tick(noop)

    assert float(runtime.state.hp[0, 3]) == pytest.approx(2_000.0 - 3 * 49.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(2_000.0 - 3 * 287.0)
    assert float(runtime.state.hp[0, 7]) == 2_000.0
    assert not bool(runtime.effects.active.any())


def test_freeze_is_one_shot_damage_and_status_snapshot(
    tensor_device: torch.device,
) -> None:
    runtime, _, ids = _runtime("Freeze", tensor_device)
    _add_target(runtime, slot=6, card_id=ids["Knight"])
    noop = _cast(runtime)

    assert float(runtime.state.hp[0, 3]) == pytest.approx(2_000.0 - 37.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(2_000.0 - 148.0)
    assert int(runtime.entity_status_kind[0, 6]) == FAST_STATUS_STUN
    assert int(runtime.entity_status_ticks[0, 6]) == 80
    _add_target(runtime, slot=7, card_id=ids["Knight"])
    for _ in range(79):
        runtime.step_tick(noop)

    assert float(runtime.state.hp[0, 6]) == pytest.approx(2_000.0 - 148.0)
    assert int(runtime.entity_status_kind[0, 7]) == 0
    assert int(runtime.entity_status_ticks[0, 7]) == 0
    assert not bool(runtime.effects.active.any())


def test_zap_runtime_is_legal_and_deterministic() -> None:
    left, _, left_ids = _runtime("Zap", torch.device("cpu"))
    right, _, right_ids = _runtime("Zap", torch.device("cpu"))
    _add_target(left, slot=6, card_id=left_ids["Knight"])
    _add_target(right, slot=6, card_id=right_ids["Knight"])
    assert bool(left.observe().legal_mask[0, 0, 25 * BOARD_WIDTH + 3])
    _cast(left)
    _cast(right)

    for name in ("active", "hp", "stable_id", "tick"):
        torch.testing.assert_close(
            getattr(left.state, name), getattr(right.state, name)
        )
    torch.testing.assert_close(left.entity_status_ticks, right.entity_status_ticks)
    assert float(left.state.hp[0, 6]) == pytest.approx(2_000.0 - 192.0)
    assert int(left.entity_status_ticks[0, 6]) == 10
