"""Scalar lifecycle evidence and bounded ownership tests for attached damage."""

import pytest
import torch

from clasher.arena import Position
from clasher.entities import AreaEffect
from clasher.torch_sim.actions import NO_OP_ACTION
from scripts.probe_hog26_poison_scalar_lifecycle_20260909 import (
    native_fixture,
    scalar_fixture,
)


@pytest.fixture(params=["cpu", "mps:0"])
def device(request):
    if request.param == "mps:0" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    torch.set_num_threads(1)
    return request.param


def action(runtime, cast=False):
    value = torch.full((runtime.batch_size, 2), NO_OP_ACTION,
                       dtype=torch.int64, device=runtime.device)
    if cast:
        value[:, 0] = 25 * 18 + 3
    return value


@pytest.mark.parametrize("scenario", ["stationary", "exit", "late_entry", "overlap"])
def test_target_and_source_clocks_match_scalar(device, scenario):
    runtime = native_fixture(device)
    battle, troop, tower, area, spell = scalar_fixture()
    areas = [area]
    if scenario == "late_entry":
        troop.position = Position(17.0, 25.0)
        runtime.state.x_units[0, 6] = 17000
    troop_hits = []
    previous = 2000.0
    for tick in range(1, 51):
        second_cast = scenario == "overlap" and tick == 11
        if second_cast:
            assert spell.cast(battle, 0, Position(3.5, 25.5))
            areas = [e for e in battle.entities.values() if isinstance(e, AreaEffect)]
        result = runtime.step_tick(action(runtime, tick == 1 or second_cast))
        if tick == 1 or second_cast:
            assert result.action_success.tolist() == [[True, True]]
        for target in (troop, tower):
            target._update_periodic_damage_effects(0.05)
        for source in areas:
            source.update(0.05, battle)
        assert float(runtime.state.hp[0, 6]) == troop.hitpoints, (scenario, tick)
        assert float(runtime.state.hp[0, 3]) == tower.hitpoints, (scenario, tick)
        if troop.hitpoints != previous:
            troop_hits.append(tick)
        previous = troop.hitpoints
        if scenario == "exit" and tick == 5:
            troop.position = Position(17.0, 25.0)
            runtime.state.x_units[0, 6] = 17000
        if scenario == "late_entry" and tick == 8:
            troop.position = Position(4.0, 25.0)
            runtime.state.x_units[0, 6] = 4000
    assert troop_hits == {"stationary": [25, 45], "exit": [25],
                          "late_entry": [30, 50], "overlap": [25, 35, 45]}[scenario]


def test_stable_id_reuse_cannot_inherit_attached_damage(device):
    runtime = native_fixture(device)
    for tick in range(1, 6):
        runtime.step_tick(action(runtime, tick == 1))
    assert int(runtime.effects.periodic_target_id[0, 0, 6]) == 7
    runtime.state.stable_id[0, 6] = 99
    runtime.state.x_units[0, 6] = 17000
    for _ in range(20):
        runtime.step_tick(action(runtime))
    assert float(runtime.state.hp[0, 6]) == 2000.0
    assert int(runtime.effects.periodic_target_id[0, 0, 6]) == 0


@pytest.mark.parametrize("behavior", ["attack", "movement"])
def test_same_tick_combat_precedes_lethal_attached_hit(device, behavior, monkeypatch):
    runtime = native_fixture(device)
    for tick in range(1, 25):
        runtime.step_tick(action(runtime, tick == 1))
    # BattleState runs combat/movement before CharacterBuff damage. A target
    # dying to Poison still commits this frame's already-ready attack/movement.
    state = runtime.state
    state.hp[0, 6] = 92.0
    state.damage[0, 6] = 100.0
    state.range_units[0, 6] = 5000 if behavior == "attack" else 0
    state.sight_range_units[0, 6] = 6000
    state.cooldown_ticks[0, 6] = 0
    state.speed_units_per_tick[0, 6] = 100
    state.active[0, 7] = True
    state.stable_id[0, 7] = 8
    state.next_stable_id[0] = 9
    state.owner[0, 7] = 0
    state.card_id[0, 7] = state.card_id[0, 6]
    state.x_units[0, 7], state.y_units[0, 7] = (
        (4500, 25000) if behavior == "attack" else (7000, 21000)
    )
    state.hp[0, 7] = state.max_hp[0, 7] = 2000.0
    state.target_id[0, 6] = 8
    control = native_fixture(device)
    control.fanout_from_(runtime)
    control.effects.periodic_damage[0, 0, 6] = 0
    control.step_tick(action(control))
    if behavior == "attack":
        assert float(control.state.hp[0, 7]) < 2000
    else:
        assert (int(control.state.x_units[0, 6]), int(control.state.y_units[0, 6])) != (4000, 25000)
    recorded = {}
    step = runtime.combat.step_tick

    def observe_combat(**kwargs):
        value = step(**kwargs)
        recorded["moved"] = int(value.moved_distance_units[0, 6])
        recorded["attack"] = bool(value.attack_ready[0, 6])
        return value

    monkeypatch.setattr(runtime.combat, "step_tick", observe_combat)
    result = runtime.step_tick(action(runtime))
    assert float(runtime.state.hp[0, 7]) == float(control.state.hp[0, 7])
    if behavior == "attack":
        assert bool(result.effect_allocation.accepted[0, 8])
        assert recorded["attack"]
    else:
        assert recorded["moved"] > 0
    assert not bool(runtime.state.active[0, 6])


def test_full_scalar_battle_orders_buff_damage_after_combat_and_movement(monkeypatch):
    battle, troop, _, _, _ = scalar_fixture()
    troop.hitpoints = 92.0
    troop.apply_periodic_damage(source_id=999, source_kind="Poison", duration=0.05,
                                hit_interval=0.05, damage=92.0)
    phases = []

    def observer(name, method):
        def wrapped(*args, **kwargs):
            phases.append((name, troop.hitpoints))
            return method(*args, **kwargs)
        return wrapped

    for name in ("update_combat_component", "update_movement_component", "update_buff_component"):
        monkeypatch.setattr(troop, name, observer(name, getattr(troop, name)))
    battle.step()
    assert phases == [("update_combat_component", 92.0),
                      ("update_movement_component", 92.0),
                      ("update_buff_component", 92.0)]
    assert troop.hitpoints == 0.0


def test_lingering_source_reserves_capacity_and_releases_after_expiry(device):
    runtime = native_fixture(device, max_effects=1)
    for tick in range(1, 161):
        runtime.step_tick(action(runtime, tick == 1))
    assert not bool(runtime.effects.active.any())
    assert not bool(runtime.effects.free_slots.any())
    elixir_before = runtime.action_state.elixir.clone()
    result = runtime.step_tick(action(runtime, True))
    assert not bool(result.action_success[0, 0])
    assert bool((runtime.action_state.elixir >= elixir_before).all())
    for _ in range(14):
        runtime.step_tick(action(runtime))
    assert bool(runtime.effects.free_slots.all())
    assert float(runtime.state.hp[0, 6]) == 2000 - 8 * 92
    result = runtime.step_tick(action(runtime, True))
    assert bool(result.action_success[0, 0])
    assert not bool(runtime.effects.periodic_remaining_ticks.any())


def test_reset_and_fanout_preserve_or_clear_entire_buff_ledger(device):
    source = native_fixture(device)
    for tick in range(1, 11):
        source.step_tick(action(source, tick == 1))
    fork = native_fixture(device, batch_size=2)
    fork.fanout_from_(source)
    names = ("periodic_target_id", "periodic_remaining_ticks", "periodic_next_hit_ticks",
             "periodic_damage", "target_local_damage", "periodic_buff_duration_ticks")
    for name in names:
        expected = getattr(source.effects, name).expand_as(getattr(fork.effects, name))
        assert torch.equal(getattr(fork.effects, name), expected)
    fork.reset_rows(torch.tensor([False, True], device=device))
    for name in names:
        assert torch.equal(getattr(fork.effects, name)[0], getattr(source.effects, name)[0])
        assert not bool(getattr(fork.effects, name)[1].any())
    for _ in range(15):
        source.step_tick(action(source))
        fork.step_tick(action(fork))
    assert float(source.state.hp[0, 6]) == 1908.0
    assert torch.equal(source.state.hp[0], fork.state.hp[0])
    assert float(fork.state.hp[1, 3]) == 2000.0


@pytest.mark.parametrize("kind", [0, 1])
def test_poison_scan_uses_strict_native_hitbox_overlap(device, kind):
    runtime = native_fixture(device)
    radius = int(runtime.action_kernel.catalog.collision_radius_units[
        runtime.state.card_id[0, 6]])
    runtime.state.kind[0, 6] = kind
    runtime.state.x_units[0, 6] = 3500 + 3500 + radius
    runtime.state.y_units[0, 6] = 25500
    for tick in range(1, 6):
        runtime.step_tick(action(runtime, tick == 1))
    assert int(runtime.effects.periodic_target_id[0, 0, 6]) == 0
    runtime.state.x_units[0, 6] -= 1
    for _ in range(5):
        runtime.step_tick(action(runtime))
    assert int(runtime.effects.periodic_target_id[0, 0, 6]) == 7
