from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_effects import FAST_STATUS_STUN
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from clasher.torch_sim.simple_travel import (
    FAST_TRAVEL_IDLE,
    FAST_TRAVEL_TRANSIT,
    FAST_TRAVEL_WINDUP,
)
from clasher.torch_sim.simple_travel_effects import allocate_fast_travel_effects_

ROOTS = ("Bandit", "MegaKnight", "Miner", "Knight")


def _runtime(device_name: str) -> tuple[SimpleGymRuntime, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ROOTS,
        device=device_name,
        canonical_lane_globals=True,
    )
    fast = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((2, fast.size), dtype=torch.int64, device=setup.device)
    hand = torch.zeros(fast.size, dtype=torch.int64, device=setup.device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id])
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id]):
            hand[card_id] = 2_000 + card_id
    deck = [[list(ROOTS) * 2, list(reversed(ROOTS)) * 2]]
    runtime = setup.create_runtime(
        deck,
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        starting_elixir=10.0,
        max_entities=20,
        max_effects=32,
    )
    runtime.state.damage[:, :6].zero_()
    return runtime, setup.cards.name_to_id


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


def _seed(
    runtime: SimpleGymRuntime,
    *,
    slot: int,
    stable_id: int,
    owner: int,
    card_id: int,
    x_units: int,
    y_units: int,
    hp: float | None = None,
) -> None:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    state.active[0, slot] = True
    state.stable_id[0, slot] = stable_id
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), stable_id + 1)
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.kind[0, slot] = catalog.kind[card_id]
    state.x_units[0, slot] = x_units
    state.y_units[0, slot] = y_units
    hitpoints = float(catalog.hitpoints[card_id]) if hp is None else hp
    state.hp[0, slot] = hitpoints
    state.max_hp[0, slot] = hitpoints
    state.target_id[0, slot] = 0
    state.damage[0, slot] = catalog.damage[card_id]
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = catalog.speed_units_per_tick[card_id]
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]
    state.deploy_ticks[0, slot] = 0
    state.cooldown_ticks[0, slot] = 0
    mask = torch.zeros_like(state.active)
    mask[0, slot] = True
    runtime._clear_status_(mask)
    runtime._initialize_lifecycle_(mask)
    runtime._initialize_modifiers_(mask)
    runtime._clear_damage_ramp_(mask)
    runtime._initialize_policy_mechanics_(mask)
    runtime._queue_travel_spawned_(mask)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_bandit_dash_and_mega_knight_spawn_leap_use_common_runtime(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        slot=6,
        stable_id=20,
        owner=0,
        card_id=ids["MegaKnight"],
        x_units=9_000,
        y_units=10_000,
    )
    _seed(
        runtime,
        slot=7,
        stable_id=21,
        owner=1,
        card_id=ids["Knight"],
        x_units=10_000,
        y_units=10_000,
        hp=10_000.0,
    )
    runtime.state.speed_units_per_tick[0, 7] = 0
    spawn = runtime.step_tick(_noop(runtime))
    assert spawn.travel is not None
    assert spawn.travel_effect_allocation is not None
    assert spawn.travel_effects is not None
    assert spawn.travel_impulse is not None
    assert spawn.travel.impact.spawn_impact[0, 6]
    assert spawn.travel_effect_allocation.accepted[0, 6]
    assert float(runtime.state.hp[0, 7]) == 9_570.0
    assert int(runtime.state.x_units[0, 7]) == 11_000

    # Keep only a stationary crown target in the leap band.
    runtime.state.active[0, 7] = False
    runtime.state.hp[0, 7] = 0
    runtime.state.x_units[0, 6] = 3_500
    runtime.state.y_units[0, 6] = 21_000
    runtime.state.cooldown_ticks[0, 6] = 0
    before = float(runtime.state.hp[0, 3])
    landing = None
    for _ in range(50):
        step = runtime.step_tick(_noop(runtime))
        assert step.travel is not None
        if bool(step.travel.completed[0, 6]):
            landing = step
            break
    assert landing is not None
    assert landing.travel is not None
    assert landing.travel.impact.valid[0, 6]
    assert float(runtime.state.hp[0, 3]) == before - 537.0
    assert int(runtime.travel.phase[0, 6]) == FAST_TRAVEL_IDLE

    # Reuse the same slot as Bandit; the stable-ID binding cannot leak MK.
    runtime.state.active[0, 6] = False
    runtime.state.hp[0, 6] = 0
    runtime.step_tick(_noop(runtime))
    _seed(
        runtime,
        slot=6,
        stable_id=30,
        owner=0,
        card_id=ids["Bandit"],
        x_units=3_500,
        y_units=21_000,
    )
    tower_before = float(runtime.state.hp[0, 3])
    started = runtime.step_tick(_noop(runtime))
    assert started.travel is not None and started.travel.started[0, 6]
    assert int(runtime.travel.phase[0, 6]) == FAST_TRAVEL_WINDUP
    dash = None
    for _ in range(30):
        step = runtime.step_tick(_noop(runtime))
        if step.travel is not None and bool(step.travel.completed[0, 6]):
            dash = step
            break
    assert dash is not None
    assert dash.travel_effect_allocation is not None
    assert dash.travel_effect_allocation.accepted[0, 6]
    assert float(runtime.state.hp[0, 3]) == tower_before - 389.0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_miner_transport_mirrors_origin_and_scales_crown_damage(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        slot=6,
        stable_id=40,
        owner=0,
        card_id=ids["Miner"],
        x_units=3_500,
        y_units=25_000,
    )
    _seed(
        runtime,
        slot=7,
        stable_id=41,
        owner=1,
        card_id=ids["Miner"],
        x_units=3_500,
        y_units=7_000,
    )
    first = runtime.step_tick(_noop(runtime))
    assert first.travel is not None
    assert runtime.state.y_units[0, 6].item() == 2_500
    assert runtime.state.y_units[0, 7].item() == 29_500
    assert runtime.travel.phase[0, 6].item() == FAST_TRAVEL_TRANSIT
    assert runtime.travel.phase[0, 7].item() == FAST_TRAVEL_TRANSIT
    assert runtime.combat._target_unavailable[0, 6]
    assert runtime.combat._target_unavailable[0, 7]

    # Remove the mirrored fixture so the blue Miner acquires the red tower.
    runtime.state.active[0, 7] = False
    runtime.state.hp[0, 7] = 0
    tower_before = float(runtime.state.hp[0, 3])
    surfaced = None
    for _ in range(80):
        step = runtime.step_tick(_noop(runtime))
        if step.travel is not None and bool(step.travel.completed[0, 6]):
            surfaced = step
            break
    assert surfaced is not None
    assert int(runtime.travel.phase[0, 6]) == FAST_TRAVEL_IDLE
    assert not runtime.combat._target_unavailable[0, 6]
    # The first ordinary hit can land on the emergence tick; either way the
    # first crown delta is the serialized 39 rather than ordinary 194.
    for _ in range(4):
        if float(runtime.state.hp[0, 3]) < tower_before:
            break
        runtime.step_tick(_noop(runtime))
    assert tower_before - float(runtime.state.hp[0, 3]) == 39.0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_travel_cancellation_mixed_movers_replay_and_reset(device_name: str) -> None:
    left, ids = _runtime(device_name)
    right, _ = _runtime(device_name)
    for runtime in (left, right):
        _seed(
            runtime,
            slot=6,
            stable_id=50,
            owner=0,
            card_id=ids["Bandit"],
            x_units=3_500,
            y_units=21_000,
        )
        _seed(
            runtime,
            slot=7,
            stable_id=51,
            owner=0,
            card_id=ids["Knight"],
            x_units=14_500,
            y_units=20_000,
        )
    first_left = left.step_tick(_noop(left))
    right.step_tick(_noop(right))
    assert first_left.travel is not None and first_left.travel.started[0, 6]
    assert int(left.state.y_units[0, 6]) == 21_000
    assert int(left.state.y_units[0, 7]) > 20_000
    for descriptor in fields(left.travel):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(left.travel, descriptor.name),
                getattr(right.travel, descriptor.name),
            )

    windup_tick = int(left.travel.phase_ticks[0, 6])
    left.entity_status_kind[0, 6] = FAST_STATUS_STUN
    left.entity_status_ticks[0, 6] = 5
    paused = left.step_tick(_noop(left))
    assert paused.travel is not None
    assert int(left.travel.phase[0, 6]) == FAST_TRAVEL_WINDUP
    assert int(left.travel.phase_ticks[0, 6]) == windup_tick
    left.entity_status_kind[0, 6] = 0
    left.entity_status_ticks[0, 6] = 0

    # Removing the retained target during windup cancels the committed setup.
    left.state.active[0, 3] = False
    left.state.hp[0, 3] = 0
    cancelled = left.step_tick(_noop(left))
    assert cancelled.travel is not None and cancelled.travel.cancelled[0, 6]
    assert int(left.travel.phase[0, 6]) == FAST_TRAVEL_IDLE

    left.reset_rows(torch.ones(1, dtype=torch.bool, device=left.device))
    for descriptor in fields(left.travel):
        if descriptor.name != "device":
            assert not bool(getattr(left.travel, descriptor.name).any())
    assert not bool(left._travel_spawned.any())
    assert not bool(left._travel_interrupted.any())
    assert not bool(left.travel_effects.active.any())
    _seed(
        left,
        slot=6,
        stable_id=70,
        owner=0,
        card_id=ids["Bandit"],
        x_units=3_500,
        y_units=21_000,
    )
    reused = left.step_tick(_noop(left))
    assert reused.travel is not None and reused.travel.initialized[0, 6]
    assert int(left.travel.bound_stable_id[0, 6]) == 70


def test_public_target_snapshot_and_travel_capacity_fail_closed() -> None:
    runtime, ids = _runtime("cpu")
    _seed(
        runtime,
        slot=6,
        stable_id=80,
        owner=0,
        card_id=ids["Bandit"],
        x_units=3_500,
        y_units=21_000,
    )
    runtime._publish_policy_visibility_(runtime._policy_visibility_view())
    runtime._publish_travel_mechanics_(runtime._travel_view())
    snapshot = runtime.combat.target_snapshot()
    assert snapshot.found[0, 6]
    assert snapshot.target_stable_id[0, 6].item() == 4
    assert snapshot.target_x_units[0, 6].item() == 3_500
    assert snapshot.target_y_units[0, 6].item() == 25_500
    assert snapshot.edge_distance_units[0, 6].item() == 4_500
    assert snapshot.destination_y_units[0, 6].item() == 24_750

    blocked, blocked_ids = _runtime("cpu")
    _seed(
        blocked,
        slot=6,
        stable_id=90,
        owner=0,
        card_id=blocked_ids["MegaKnight"],
        x_units=9_000,
        y_units=10_000,
    )
    _seed(
        blocked,
        slot=7,
        stable_id=91,
        owner=1,
        card_id=blocked_ids["Knight"],
        x_units=10_000,
        y_units=10_000,
        hp=10_000.0,
    )
    blocked.travel_effects.active.fill_(True)
    before_target = float(blocked.state.hp[0, 7])
    result = blocked.step_tick(_noop(blocked))
    assert result.travel_effect_allocation is not None
    assert result.travel_effect_allocation.capacity_rejected[0, 6]
    assert not result.travel_effect_allocation.accepted[0, 6]
    assert float(blocked.state.hp[0, 7]) == before_target
    assert result.travel_impulse is not None
    assert not bool(result.travel_impulse.affected.any())


def test_mega_knight_spawn_impact_waits_for_deployment_completion() -> None:
    runtime, ids = _runtime("cpu")
    _seed(
        runtime,
        slot=6,
        stable_id=95,
        owner=0,
        card_id=ids["MegaKnight"],
        x_units=9_000,
        y_units=10_000,
    )
    runtime.state.deploy_ticks[0, 6] = 2
    runtime._queue_travel_spawned_(
        runtime.state.active & (runtime.state.stable_id == 95)
    )
    first = runtime.step_tick(_noop(runtime))
    assert first.travel is not None
    assert not bool(first.travel.initialized[0, 6])
    assert not bool(first.travel.impact.spawn_impact[0, 6])
    second = runtime.step_tick(_noop(runtime))
    assert second.travel is not None
    assert second.travel.initialized[0, 6]
    assert second.travel.impact.spawn_impact[0, 6]


def test_integrated_travel_hot_path_has_no_card_dispatch_or_host_sync() -> None:
    for function in (
        SimpleGymRuntime._step_travel_,
        SimpleGymRuntime._resolve_travel_impacts_,
        SimpleGymRuntime._effect_commands,
        allocate_fast_travel_effects_,
    ):
        source = inspect.getsource(function)
        for forbidden in (
            "Bandit",
            "MegaKnight",
            "Miner",
            ".item(",
            ".cpu(",
            ".tolist(",
        ):
            assert forbidden not in source
