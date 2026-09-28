from __future__ import annotations

import inspect

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_attack_effects import (
    FastEffectCommands,
    allocate_fast_attack_effects_,
)
from clasher.torch_sim.simple_catalog import (
    FAST_CARD_EFFECT_AREA,
    FAST_CARD_EFFECT_DIRECT,
    FAST_CARD_EFFECT_PROJECTILE,
    FastCardCatalog,
)
from clasher.torch_sim.simple_effects import (
    FAST_EFFECT_AREA,
    FAST_EFFECT_PROJECTILE,
    FAST_STATUS_STUN,
    FastEffectState,
)
from clasher.torch_sim.simple_state import FastGymState


def _catalog(device: str) -> tuple[FastCardCatalog, dict[str, int]]:
    battle = BattleState()
    full = TensorCardCatalog.compile(
        battle.card_loader,
        ["Archers", "Arrows", "Fireball", "IceSpirit", "Knight"],
        device=device,
    )
    fast = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    return fast, full.name_to_id


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_serialized_representative_effect_primitives(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    catalog, ids = _catalog(device)
    archer = ids["Archers"]
    arrows = ids["Arrows"]
    fireball = ids["Fireball"]
    ice = ids["IceSpirit"]
    knight = ids["Knight"]

    assert int(catalog.effect_kind[archer]) == FAST_CARD_EFFECT_PROJECTILE
    assert int(catalog.projectile_speed_units_per_tick[archer]) == 600
    assert int(catalog.effect_kind[fireball]) == FAST_CARD_EFFECT_PROJECTILE
    assert int(catalog.projectile_speed_units_per_tick[fireball]) == 600
    assert int(catalog.effect_radius_units[fireball]) == 2500
    assert float(catalog.tower_damage_multiplier[fireball]) == 0.25
    assert int(catalog.effect_kind[arrows]) == FAST_CARD_EFFECT_AREA
    assert int(catalog.effect_radius_units[arrows]) == 3500
    assert float(catalog.effect_damage[arrows]) == 144.0
    assert int(catalog.effect_kind[ice]) == FAST_CARD_EFFECT_PROJECTILE
    assert int(catalog.effect_radius_units[ice]) == 1500
    assert int(catalog.status_kind[ice]) == FAST_STATUS_STUN
    assert int(catalog.status_duration_ticks[ice]) == 24
    assert bool(catalog.consume_source_on_impact[ice])
    assert int(catalog.effect_kind[knight]) == FAST_CARD_EFFECT_DIRECT


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_ready_attacks_and_spell_commands_allocate_effects(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    catalog, ids = _catalog(device)
    state = FastGymState.empty(5, max_entities=8, device=device)
    effects = FastEffectState.empty(5, max_effects=3, device=device)
    consumed = torch.zeros((5, 3), dtype=torch.int64, device=state.device)

    # Rows: Archer attack, Fireball at Crown Tower, Arrows cast, Ice Spirit
    # jump, and ordinary direct Knight hit.
    source_cards = torch.tensor(
        [ids["Archers"], 0, 0, ids["IceSpirit"], ids["Knight"]],
        dtype=torch.int64,
        device=state.device,
    )
    target_ids = torch.tensor([8, 1, 0, 8, 8], device=state.device)
    for row in (0, 3, 4):
        state.active[row, 6:8] = True
        state.stable_id[row, 6:8] = torch.tensor([7, 8], device=state.device)
        state.owner[row, 6:8] = torch.tensor([0, 1], device=state.device)
        state.card_id[row, 6] = source_cards[row]
        state.card_id[row, 7] = ids["Knight"]
        state.hp[row, 6:8] = 1000.0
        state.x_units[row, 6:8] = torch.tensor([100, 400], device=state.device)
        state.y_units[row, 6:8] = 500
    state.active[1, 0] = True
    state.stable_id[1, 0] = 1
    state.owner[1, 0] = 1
    state.hp[1, 0] = 3000.0
    state.x_units[1, 0] = 1000
    state.y_units[1, 0] = 1500

    commands = FastEffectCommands(
        ready=torch.ones((5, 1), dtype=torch.bool, device=state.device),
        source_id=torch.tensor([[7], [0], [0], [7], [7]], device=state.device),
        owner=torch.zeros((5, 1), dtype=torch.int8, device=state.device),
        card_id=torch.tensor(
            [
                [ids["Archers"]],
                [ids["Fireball"]],
                [ids["Arrows"]],
                [ids["IceSpirit"]],
                [ids["Knight"]],
            ],
            device=state.device,
        ),
        source_x_units=torch.zeros((5, 1), dtype=torch.int32, device=state.device),
        source_y_units=torch.zeros((5, 1), dtype=torch.int32, device=state.device),
        target_id=target_ids[:, None],
        target_x_units=torch.tensor(
            [[400], [1000], [9000], [400], [400]],
            dtype=torch.int32,
            device=state.device,
        ),
        target_y_units=torch.tensor(
            [[500], [1500], [16000], [500], [500]],
            dtype=torch.int32,
            device=state.device,
        ),
        damage_multiplier=torch.tensor(
            [[1.0], [1.0], [1.0], [1.0], [2.0]],
            dtype=torch.float32,
            device=state.device,
        ),
    )

    result = allocate_fast_attack_effects_(state, effects, consumed, catalog, commands)

    assert result.accepted.tolist() == [[True]] * 5
    assert result.projectile[:, 0].tolist() == [True, True, False, True, False]
    assert result.area[:, 0].tolist() == [False, False, True, False, False]
    assert result.direct[:, 0].tolist() == [False, False, False, False, True]
    assert effects.kind[:, 0].tolist() == [
        FAST_EFFECT_PROJECTILE,
        FAST_EFFECT_PROJECTILE,
        FAST_EFFECT_AREA,
        FAST_EFFECT_PROJECTILE,
        FAST_EFFECT_AREA,
    ]
    assert effects.speed_units_per_tick[:, 0].tolist() == [600, 600, 0, 400, 0]
    assert effects.radius_units[:, 0].tolist() == [0, 2500, 3500, 1500, 0]
    assert effects.damage[1, 0].item() == pytest.approx(688.0)
    assert effects.tower_damage_multiplier[1, 0].item() == pytest.approx(0.25)
    assert effects.damage[2, 0].item() == pytest.approx(144.0)
    assert effects.damage[4, 0].item() == pytest.approx(
        float(catalog.effect_damage[ids["Knight"]]) * 2.0
    )
    assert effects.tower_damage_multiplier[2, 0].item() == pytest.approx(0.20)
    assert effects.tracks_target[:, 0].tolist() == [True, False, False, True, False]
    assert effects.target_x_units[1:3, 0].tolist() == [1000, 9000]
    assert effects.target_y_units[1:3, 0].tolist() == [1500, 16000]
    assert int(effects.status_kind[3, 0]) == FAST_STATUS_STUN
    assert int(effects.status_duration_ticks[3, 0]) == 24
    assert consumed[:, 0].tolist() == [0, 0, 0, 7, 0]


def test_attack_effect_allocation_fails_closed_and_preserves_live_pool() -> None:
    catalog, ids = _catalog("cpu")
    state = FastGymState.empty(1, max_entities=2)
    effects = FastEffectState.empty(1, max_effects=1)
    effects.active[0, 0] = True
    effects.source_card_id[0, 0] = 99
    consumed = torch.zeros((1, 1), dtype=torch.int64)
    commands = FastEffectCommands(
        ready=torch.ones((1, 2), dtype=torch.bool),
        source_id=torch.zeros((1, 2), dtype=torch.int64),
        owner=torch.zeros((1, 2), dtype=torch.int8),
        card_id=torch.tensor([[ids["Arrows"], catalog.size + 1]]),
        source_x_units=torch.zeros((1, 2), dtype=torch.int32),
        source_y_units=torch.zeros((1, 2), dtype=torch.int32),
        target_id=torch.zeros((1, 2), dtype=torch.int64),
        target_x_units=torch.zeros((1, 2), dtype=torch.int32),
        target_y_units=torch.zeros((1, 2), dtype=torch.int32),
        damage_multiplier=torch.ones((1, 2), dtype=torch.float32),
    )

    result = allocate_fast_attack_effects_(state, effects, consumed, catalog, commands)

    assert result.accepted.tolist() == [[False, False]]
    assert result.capacity_rejected.tolist() == [[True, False]]
    assert result.unsupported.tolist() == [[False, True]]
    assert int(effects.source_card_id[0, 0]) == 99


def test_attack_effect_hot_path_has_no_sync_or_name_dispatch() -> None:
    source = inspect.getsource(allocate_fast_attack_effects_)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in ("Archer", "Arrows", "Fireball", "IceSpirit"):
        assert card_name not in source
