from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.simple_effects import (
    FAST_EFFECT_AREA,
    FAST_EFFECT_PROJECTILE,
    FAST_STATUS_FREEZE,
    FAST_STATUS_NONE,
    FAST_STATUS_SLOW,
    FastEffectState,
    step_fast_effects,
)
from clasher.torch_sim.simple_state import FastGymState


def _entity_status(state: FastGymState) -> tuple[torch.Tensor, torch.Tensor]:
    shape = state.active.shape
    return (
        torch.zeros(shape, dtype=torch.int8, device=state.device),
        torch.zeros(shape, dtype=torch.int32, device=state.device),
    )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_grouped_fireball_area_damage_and_status_precedence(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(1, max_entities=5, device=device)
    state.active[0] = True
    state.stable_id[0] = torch.arange(1, 6, device=state.device)
    state.owner[0] = torch.tensor([0, 1, 1, 1, 0], device=state.device)
    state.x_units[0] = torch.tensor([1000, 1000, 1200, 1800, 1000], device=state.device)
    state.y_units[0] = 1000
    state.hp[0] = 500.0
    state.max_hp[0] = 500.0
    effects = FastEffectState.empty(1, max_effects=3, device=device)
    effects.active[0, :2] = True
    effects.kind[0, :2] = FAST_EFFECT_AREA
    effects.source_owner[0, :2] = 0
    effects.source_card_id[0, :2] = torch.tensor([41, 42], device=state.device)
    effects.x_units[0, :2] = 1000
    effects.y_units[0, :2] = 1000
    effects.damage[0, :2] = torch.tensor([100.0, 25.0], device=state.device)
    effects.radius_units[0, :2] = 300
    effects.status_kind[0, :2] = torch.tensor(
        [FAST_STATUS_SLOW, FAST_STATUS_FREEZE], device=state.device
    )
    effects.status_duration_ticks[0, :2] = torch.tensor(
        [8, 3], device=state.device
    )
    effects.lifetime_ticks[0, :2] = 1
    status_kind, status_ticks = _entity_status(state)

    result = step_fast_effects(state, effects, status_kind, status_ticks)

    assert result.impacted.tolist() == [[True, True, False]]
    assert result.targets_hit[0, :2].tolist() == [
        [False, True, True, False, False],
        [False, True, True, False, False],
    ]
    assert state.hp[0].tolist() == [500.0, 375.0, 375.0, 500.0, 500.0]
    assert status_kind[0].tolist() == [0, FAST_STATUS_FREEZE, FAST_STATUS_FREEZE, 0, 0]
    assert status_ticks[0].tolist() == [0, 3, 3, 0, 0]
    assert not bool(effects.active.any())
    assert result.cleaned.tolist() == [[True, True, False]]


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_homing_freeze_impact_consumes_ice_spirit_source(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(1, max_entities=4, device=device)
    state.active[0, :3] = True
    state.stable_id[0, :3] = torch.tensor([10, 20, 21], device=state.device)
    state.owner[0, :3] = torch.tensor([0, 1, 1], device=state.device)
    state.x_units[0, :3] = torch.tensor([0, 1000, 1100], device=state.device)
    state.y_units[0, :3] = 500
    state.hp[0, :3] = torch.tensor([190.0, 600.0, 600.0], device=state.device)
    state.max_hp[0, :3] = state.hp[0, :3]
    effects = FastEffectState.empty(1, max_effects=2, device=device)
    effects.active[0, 0] = True
    effects.kind[0, 0] = FAST_EFFECT_PROJECTILE
    effects.source_owner[0, 0] = 0
    effects.source_card_id[0, 0] = 77
    effects.x_units[0, 0] = 0
    effects.y_units[0, 0] = 500
    effects.target_id[0, 0] = 20
    effects.speed_units_per_tick[0, 0] = 1200
    effects.damage[0, 0] = 90.0
    effects.radius_units[0, 0] = 250
    effects.status_kind[0, 0] = FAST_STATUS_FREEZE
    effects.status_duration_ticks[0, 0] = 4
    effects.lifetime_ticks[0, 0] = 3
    consume_source_id = torch.tensor([[10, 0]], dtype=torch.int64, device=state.device)
    status_kind, status_ticks = _entity_status(state)

    result = step_fast_effects(
        state,
        effects,
        status_kind,
        status_ticks,
        consume_source_id=consume_source_id,
    )

    assert result.impacted.tolist() == [[True, False]]
    assert result.sources_consumed.tolist() == [[True, False, False, False]]
    assert not bool(state.active[0, 0])
    assert int(state.stable_id[0, 0]) == 0
    assert state.hp[0, 1:3].tolist() == [510.0, 510.0]
    assert status_kind[0, 1:3].tolist() == [FAST_STATUS_FREEZE] * 2
    assert status_ticks[0, 1:3].tolist() == [4, 4]
    assert not bool(effects.active[0, 0])


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_fireball_mixed_splash_scales_only_tower_slots(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(1, max_entities=8, device=device)
    # Slots 0..5 are reserved for towers; ordinary entities begin at slot 6.
    state.active[0, [0, 6, 7]] = True
    state.stable_id[0, [0, 6, 7]] = torch.tensor(
        [1, 20, 21], device=state.device
    )
    state.owner[0, [0, 6, 7]] = 1
    state.x_units[0, [0, 6, 7]] = torch.tensor(
        [1000, 1100, 1800], dtype=torch.int32, device=state.device
    )
    state.y_units[0, [0, 6, 7]] = 1000
    state.hp[0, [0, 6, 7]] = 1000.0
    state.max_hp[0, [0, 6, 7]] = 1000.0
    effects = FastEffectState.empty(1, max_effects=1, device=device)
    effects.active[0, 0] = True
    effects.kind[0, 0] = FAST_EFFECT_AREA
    effects.source_owner[0, 0] = 0
    effects.x_units[0, 0] = 1000
    effects.y_units[0, 0] = 1000
    effects.damage[0, 0] = 200.0
    effects.tower_damage_multiplier[0, 0] = 0.3
    effects.radius_units[0, 0] = 300
    effects.lifetime_ticks[0, 0] = 1
    status_kind, status_ticks = _entity_status(state)

    result = step_fast_effects(state, effects, status_kind, status_ticks)

    assert result.targets_hit[0, 0].tolist() == [
        True,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
    ]
    assert float(state.hp[0, 0]) == pytest.approx(940.0)
    assert float(state.hp[0, 6]) == pytest.approx(800.0)
    assert float(state.hp[0, 7]) == pytest.approx(1000.0)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_untracked_projectile_flies_to_fixed_absolute_target(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(1, max_entities=8, device=device)
    state.active[0, 6] = True
    state.stable_id[0, 6] = 31
    state.owner[0, 6] = 1
    state.x_units[0, 6] = 1000
    state.y_units[0, 6] = 500
    state.hp[0, 6] = 300.0
    state.max_hp[0, 6] = 300.0
    effects = FastEffectState.empty(1, max_effects=1, device=device)
    effects.active[0, 0] = True
    effects.kind[0, 0] = FAST_EFFECT_PROJECTILE
    effects.source_owner[0, 0] = 0
    effects.y_units[0, 0] = 500
    effects.target_id[0, 0] = 0
    effects.target_x_units[0, 0] = 1000
    effects.target_y_units[0, 0] = 500
    effects.speed_units_per_tick[0, 0] = 600
    effects.damage[0, 0] = 75.0
    effects.radius_units[0, 0] = 10
    effects.lifetime_ticks[0, 0] = 3
    status_kind, status_ticks = _entity_status(state)

    first = step_fast_effects(state, effects, status_kind, status_ticks)
    assert not bool(first.impacted[0, 0])
    assert int(effects.x_units[0, 0]) == 600
    assert bool(effects.active[0, 0])

    second = step_fast_effects(state, effects, status_kind, status_ticks)
    assert bool(second.impacted[0, 0])
    assert int(effects.x_units[0, 0]) == 1000
    assert float(state.hp[0, 6]) == pytest.approx(225.0)
    assert not bool(effects.active[0, 0])


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_projectile_homes_then_expires_and_statuses_tick(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(1, max_entities=2, device=device)
    state.active[0, 0] = True
    state.stable_id[0, 0] = 8
    state.owner[0, 0] = 1
    state.x_units[0, 0] = 1000
    state.hp[0, 0] = 100.0
    state.max_hp[0, 0] = 100.0
    effects = FastEffectState.empty(1, max_effects=1, device=device)
    effects.active[0, 0] = True
    effects.kind[0, 0] = FAST_EFFECT_PROJECTILE
    effects.source_owner[0, 0] = 0
    effects.target_id[0, 0] = 8
    effects.speed_units_per_tick[0, 0] = 400
    effects.damage[0, 0] = 10.0
    effects.radius_units[0, 0] = 1
    effects.lifetime_ticks[0, 0] = 2
    status_kind, status_ticks = _entity_status(state)
    status_kind[0, 0] = FAST_STATUS_SLOW
    status_ticks[0, 0] = 2

    first = step_fast_effects(state, effects, status_kind, status_ticks)
    assert not bool(first.impacted[0, 0])
    assert int(effects.x_units[0, 0]) == 400
    assert int(effects.lifetime_ticks[0, 0]) == 1
    assert int(status_ticks[0, 0]) == 1

    state.x_units[0, 0] = 1200
    second = step_fast_effects(state, effects, status_kind, status_ticks)
    assert not bool(second.impacted[0, 0])
    assert bool(second.cleaned[0, 0])
    assert not bool(effects.active[0, 0])
    assert int(status_kind[0, 0]) == FAST_STATUS_NONE
    assert int(status_ticks[0, 0]) == 0


def test_effect_hot_path_has_no_host_sync_or_dynamic_compaction() -> None:
    source = inspect.getsource(step_fast_effects)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
