from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.simple_modifiers import (
    FastChargeParameters,
    FastModifierState,
    advance_fast_charge_,
    intercept_fast_shield_hits_,
    pre_move_charge_multipliers,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _charge_parameters(state: FastModifierState) -> FastChargeParameters:
    shape = (state.batch_size, state.max_entities)
    return FastChargeParameters(
        enabled=torch.ones(shape, dtype=torch.bool, device=state.device),
        threshold_ticks=torch.full(shape, 3, dtype=torch.int32, device=state.device),
        threshold_distance_units=torch.full(
            shape, 300, dtype=torch.int32, device=state.device
        ),
        ready_speed_multiplier=torch.full(
            shape, 2.0, dtype=torch.float32, device=state.device
        ),
        ready_damage_multiplier=torch.full(
            shape, 2.0, dtype=torch.float32, device=state.device
        ),
    )


def test_guards_like_shield_absorbs_whole_ordered_hits(
    tensor_device: str,
) -> None:
    modifiers = FastModifierState.empty(1, max_entities=2, device=tensor_device)
    modifiers.shield[0, 1] = 120.0
    modifiers.max_shield[0, 1] = 120.0
    result = intercept_fast_shield_hits_(
        modifiers,
        valid=torch.ones((1, 3), dtype=torch.bool, device=modifiers.device),
        target_slot=torch.tensor([[1, 1, 1]], device=modifiers.device),
        damage=torch.tensor(
            [[50.0, 500.0, 37.0]], dtype=torch.float32, device=modifiers.device
        ),
    )

    assert result.absorbed.tolist() == [[True, True, False]]
    assert result.broken.tolist() == [[False, True, False]]
    assert result.shield_damage.tolist() == [[0.0, 550.0]]
    assert result.hp_damage.tolist() == [[0.0, 37.0]]
    assert modifiers.shield.tolist() == [[0.0, 0.0]]
    assert modifiers.max_shield.tolist() == [[0.0, 120.0]]


def test_shield_interception_groups_unshielded_targets_and_ignores_bad_hits(
    tensor_device: str,
) -> None:
    modifiers = FastModifierState.empty(1, max_entities=2, device=tensor_device)
    result = intercept_fast_shield_hits_(
        modifiers,
        valid=torch.tensor([[True, True, True, False]], device=modifiers.device),
        target_slot=torch.tensor([[0, 0, 7, 1]], device=modifiers.device),
        damage=torch.tensor(
            [[7.0, 11.0, 100.0, 50.0]],
            dtype=torch.float32,
            device=modifiers.device,
        ),
    )

    assert result.absorbed.tolist() == [[False, False, False, False]]
    assert result.hp_damage.tolist() == [[18.0, 0.0]]
    assert result.shield_damage.tolist() == [[0.0, 0.0]]


def test_prince_like_charge_threshold_multipliers_and_attack_reset(
    tensor_device: str,
) -> None:
    modifiers = FastModifierState.empty(1, max_entities=2, device=tensor_device)
    parameters = _charge_parameters(modifiers)
    active = torch.tensor([[True, False]], device=modifiers.device)
    not_attacking = torch.zeros_like(active)
    movement = torch.tensor([[100, 500]], dtype=torch.int32, device=modifiers.device)

    initial = pre_move_charge_multipliers(modifiers, parameters)
    assert initial.ready.tolist() == [[False, False]]
    assert initial.speed.tolist() == [[1.0, 1.0]]
    assert initial.damage.tolist() == [[1.0, 1.0]]

    for step in range(3):
        result = advance_fast_charge_(
            modifiers,
            parameters,
            active=active,
            moved_distance_units=movement,
            attacked=not_attacking,
        )
        assert result.progressed.tolist() == [[True, False]]
        assert result.became_ready.tolist() == [[step == 2, False]]

    assert modifiers.charge_progress_ticks.tolist() == [[3, 0]]
    assert modifiers.charge_progress_distance_units.tolist() == [[300, 0]]
    charged = pre_move_charge_multipliers(modifiers, parameters)
    assert charged.ready.tolist() == [[True, False]]
    assert charged.speed.tolist() == [[2.0, 1.0]]
    assert charged.damage.tolist() == [[2.0, 1.0]]

    attacked = torch.tensor([[True, False]], device=modifiers.device)
    reset = advance_fast_charge_(
        modifiers,
        parameters,
        active=active,
        moved_distance_units=movement,
        attacked=attacked,
    )
    assert reset.reset.tolist() == [[True, False]]
    assert not bool(modifiers.charge_ready.any())
    assert not bool(modifiers.charge_progress_ticks.any())
    assert not bool(modifiers.charge_progress_distance_units.any())
    ordinary = pre_move_charge_multipliers(modifiers, parameters)
    assert ordinary.speed.tolist() == [[1.0, 1.0]]
    assert ordinary.damage.tolist() == [[1.0, 1.0]]


def test_charge_requires_every_configured_threshold_and_fails_closed() -> None:
    state = FastModifierState.empty(1, max_entities=3)
    parameters = FastChargeParameters(
        enabled=torch.tensor([[True, True, True]]),
        threshold_ticks=torch.tensor([[2, 0, 0]], dtype=torch.int32),
        threshold_distance_units=torch.tensor([[500, 200, 0]], dtype=torch.int32),
        ready_speed_multiplier=torch.tensor([[2.0, 2.0, 3.0]]),
        ready_damage_multiplier=torch.tensor([[2.0, 2.0, 3.0]]),
    )
    active = torch.ones((1, 3), dtype=torch.bool)
    movement = torch.tensor([[300, 200, 1_000]], dtype=torch.int32)
    no_attack = torch.zeros((1, 3), dtype=torch.bool)

    advance_fast_charge_(
        state,
        parameters,
        active=active,
        moved_distance_units=movement,
        attacked=no_attack,
    )
    assert state.charge_ready.tolist() == [[False, True, False]]
    advance_fast_charge_(
        state,
        parameters,
        active=active,
        moved_distance_units=movement,
        attacked=no_attack,
    )
    assert state.charge_ready.tolist() == [[True, True, False]]


def test_modifier_hot_paths_have_no_host_sync_or_card_dispatch() -> None:
    source = "\n".join(
        inspect.getsource(function)
        for function in (
            pre_move_charge_multipliers,
            advance_fast_charge_,
            intercept_fast_shield_hits_,
        )
    )
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in ("Guards", "Prince", "DarkPrince", "BattleRam"):
        assert card_name not in source
