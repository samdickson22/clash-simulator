from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_attack_effects import allocate_fast_attack_effects_
from clasher.torch_sim.simple_catalog import FAST_CARD_EFFECT_DIRECT
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_effects import (
    FAST_EFFECT_AREA,
    FAST_EFFECT_PROJECTILE,
    step_fast_effects,
)
from clasher.torch_sim.simple_outcomes import FAST_TOWER_SLOT_COUNT
from clasher.torch_sim.simple_policy_mechanics import FAST_VISIBILITY_HIDE_WHEN_IDLE
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from clasher.torch_sim.simple_travel import FAST_TRAVEL_DASH, FAST_TRAVEL_TRANSIT


def _runtime(
    device_name: str,
    *,
    batch_size: int = 1,
    max_effects: int = 16,
) -> tuple[SimpleGymRuntime, int]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("Knight",),
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
    decks = [
        [
            [
                "Knight",
            ]
            * 8,
            ["Knight"] * 8,
        ]
        for _ in range(batch_size)
    ]
    runtime = setup.create_runtime(
        decks,
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        max_entities=16,
        max_effects=max_effects,
    )
    return runtime, setup.cards.name_to_id["Knight"]


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full(
        (runtime.batch_size, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=runtime.device,
    )


def _seed_stationary_knight(
    runtime: SimpleGymRuntime,
    card_id: int,
    *,
    row: int,
    slot: int,
    stable_id: int,
    owner: int,
    x_units: int,
    y_units: int,
    hp: float = 10_000.0,
) -> None:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    state.active[row, slot] = True
    state.stable_id[row, slot] = stable_id
    state.next_stable_id[row] = max(int(state.next_stable_id[row]), stable_id + 1)
    state.owner[row, slot] = owner
    state.card_id[row, slot] = card_id
    state.kind[row, slot] = catalog.kind[card_id]
    state.x_units[row, slot] = x_units
    state.y_units[row, slot] = y_units
    state.hp[row, slot] = hp
    state.max_hp[row, slot] = hp
    state.target_id[row, slot] = 0
    state.damage[row, slot] = catalog.damage[card_id]
    state.range_units[row, slot] = catalog.range_units[card_id]
    state.sight_range_units[row, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[row, slot] = 0
    state.hit_cooldown_ticks[row, slot] = catalog.hit_cooldown_ticks[card_id]
    state.deploy_ticks[row, slot] = 0
    state.cooldown_ticks[row, slot] = 10_000


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_standard_princess_projectile_first_hit_damage_cadence_and_mirror(
    device_name: str,
) -> None:
    runtime, knight = _runtime(device_name, batch_size=2)
    state = runtime.state
    state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
    state.damage[0, 0] = 109.0
    state.damage[1, 3] = 109.0
    _seed_stationary_knight(
        runtime,
        knight,
        row=0,
        slot=6,
        stable_id=20,
        owner=1,
        x_units=3_500,
        y_units=8_000,
    )
    _seed_stationary_knight(
        runtime,
        knight,
        row=1,
        slot=6,
        stable_id=20,
        owner=0,
        x_units=3_500,
        y_units=24_000,
    )
    no_op = _noop(runtime)

    for _ in range(15):
        step = runtime.step_tick(no_op)
        assert not bool(step.effect_allocation.accepted[:, 2:8].any())
    assert state.hp[:, 6].tolist() == [10_000.0, 10_000.0]
    assert state.cooldown_ticks[0, 0].item() == 1
    assert state.cooldown_ticks[1, 3].item() == 1

    launched = runtime.step_tick(no_op)
    assert launched.effect_allocation.accepted[0, 2]
    assert launched.effect_allocation.accepted[1, 5]
    effect_slots = launched.effect_allocation.effect_slot[:, 2:8]
    first_slot = int(effect_slots[0, 0])
    mirrored_slot = int(effect_slots[1, 3])
    assert int(runtime.effects.source_card_id[0, first_slot]) == 0
    assert int(runtime.effects.source_card_id[1, mirrored_slot]) == 0
    assert int(runtime.effects.kind[0, first_slot]) == FAST_EFFECT_PROJECTILE
    assert int(runtime.effects.kind[1, mirrored_slot]) == FAST_EFFECT_PROJECTILE
    assert int(runtime.effects.y_units[0, first_slot]) == 7_400
    assert int(runtime.effects.y_units[1, mirrored_slot]) == 24_600
    assert state.hp[:, 6].tolist() == [10_000.0, 10_000.0]
    assert state.cooldown_ticks[0, 0].item() == 16
    assert state.cooldown_ticks[1, 3].item() == 16

    runtime.step_tick(no_op)
    assert state.hp[:, 6].tolist() == [9_891.0, 9_891.0]
    for _ in range(14):
        no_second = runtime.step_tick(no_op)
        assert not bool(no_second.effect_allocation.accepted[:, 2:8].any())
    second = runtime.step_tick(no_op)
    assert second.effect_allocation.accepted[0, 2]
    assert second.effect_allocation.accepted[1, 5]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_numeric_tower_profile_supports_serialized_direct_hit(
    device_name: str,
) -> None:
    runtime, knight = _runtime(device_name)
    runtime.state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
    runtime.state.damage[0, 0] = 109.0
    runtime.state.cooldown_ticks[0, 0] = 0
    runtime._tower_effect_kind[0, 0] = FAST_CARD_EFFECT_DIRECT
    runtime._tower_projectile_speed[0, 0] = 0
    _seed_stationary_knight(
        runtime,
        knight,
        row=0,
        slot=6,
        stable_id=20,
        owner=1,
        x_units=3_500,
        y_units=8_000,
    )

    step = runtime.step_tick(_noop(runtime))

    assert step.effect_allocation.accepted[0, 2]
    assert step.effect_allocation.direct[0, 2]
    effect_slot = int(step.effect_allocation.effect_slot[0, 2])
    assert int(runtime.effects.source_card_id[0, effect_slot]) == 0
    assert int(runtime.effects.kind[0, effect_slot]) == FAST_EFFECT_AREA
    assert step.effects.impacted[0, effect_slot]
    assert float(runtime.state.hp[0, 6]) == 9_891.0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_tower_hit_uses_common_shield_interception(device_name: str) -> None:
    runtime, knight = _runtime(device_name)
    runtime.state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
    runtime.state.damage[0, 0] = 109.0
    runtime.state.cooldown_ticks[0, 0] = 0
    runtime._tower_effect_kind[0, 0] = FAST_CARD_EFFECT_DIRECT
    _seed_stationary_knight(
        runtime,
        knight,
        row=0,
        slot=6,
        stable_id=20,
        owner=1,
        x_units=3_500,
        y_units=8_000,
    )
    runtime.modifiers.shield[0, 6] = 50.0
    runtime.modifiers.max_shield[0, 6] = 50.0

    step = runtime.step_tick(_noop(runtime))

    assert step.effect_allocation.accepted[0, 2]
    assert float(runtime.modifiers.shield[0, 6]) == 0.0
    # Clash shields consume the hit, including overkill, rather than spilling
    # the residual 59 damage into HP.
    assert float(runtime.state.hp[0, 6]) == 10_000.0


@pytest.mark.parametrize("activation", ("king-chip", "princess-death"))
@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_king_is_inactive_then_latches_owner_local_activation(
    device_name: str,
    activation: str,
) -> None:
    runtime, knight = _runtime(device_name, batch_size=2)
    state = runtime.state
    state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
    state.damage[0, 2] = 109.0
    state.damage[1, 5] = 109.0
    _seed_stationary_knight(
        runtime,
        knight,
        row=0,
        slot=6,
        stable_id=20,
        owner=1,
        x_units=9_000,
        y_units=3_000,
    )
    _seed_stationary_knight(
        runtime,
        knight,
        row=1,
        slot=6,
        stable_id=20,
        owner=0,
        x_units=9_000,
        y_units=29_000,
    )
    first = runtime.step_tick(_noop(runtime))
    assert not bool(first.effect_allocation.accepted[0, 4])
    assert not bool(first.effect_allocation.accepted[1, 7])
    assert not bool(state.king_active.any())

    if activation == "king-chip":
        state.hp[0, 2] -= 1.0
        state.hp[1, 5] -= 1.0
    else:
        state.hp[0, 0] = 0.0
        state.hp[1, 3] = 0.0
    activated = runtime.step_tick(_noop(runtime))
    assert state.king_active.tolist() == [[True, False], [False, True]]
    assert state.king_activation_ticks.tolist() == [[80, 0], [0, 80]]
    assert not bool(activated.effect_allocation.accepted[0, 4])
    assert not bool(activated.effect_allocation.accepted[1, 7])

    state.king_activation_ticks[0, 0] = 1
    state.king_activation_ticks[1, 1] = 1
    ready = runtime.step_tick(_noop(runtime))
    assert ready.effect_allocation.accepted[0, 4]
    assert ready.effect_allocation.accepted[1, 7]
    assert state.hp[:, 6].tolist() == [9_891.0, 9_891.0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_tower_lock_survives_new_closer_target_and_capacity_rejection_rolls_back(
    device_name: str,
) -> None:
    runtime, knight = _runtime(device_name, max_effects=1)
    state = runtime.state
    state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
    state.damage[0, 0] = 109.0
    state.cooldown_ticks[0, 0] = 0
    _seed_stationary_knight(
        runtime,
        knight,
        row=0,
        slot=6,
        stable_id=30,
        owner=1,
        x_units=3_500,
        y_units=8_500,
    )
    _seed_stationary_knight(
        runtime,
        knight,
        row=0,
        slot=7,
        stable_id=20,
        owner=1,
        x_units=3_500,
        y_units=8_000,
    )
    # Acquire stable ID 20, then make stable ID 30 closer. The established
    # target remains locked while it is live, visible, and in sight.
    runtime.step_tick(_noop(runtime))
    assert int(state.target_id[0, 0]) == 20
    state.y_units[0, 6] = 7_000
    state.cooldown_ticks[0, 0] = 0

    effects = runtime.effects
    effects.active[0, 0] = True
    effects.kind[0, 0] = FAST_EFFECT_PROJECTILE
    effects.lifetime_ticks[0, 0] = 100
    effects.speed_units_per_tick[0, 0] = 0
    effects.tracks_target[0, 0] = False
    effects.x_units[0, 0] = 0
    effects.y_units[0, 0] = 0
    effects.target_x_units[0, 0] = 100_000
    effects.target_y_units[0, 0] = 100_000
    blocked = runtime.step_tick(_noop(runtime))

    assert int(state.target_id[0, 0]) == 20
    assert blocked.effect_allocation.capacity_rejected[0, 2]
    assert not blocked.effect_allocation.accepted[0, 2]
    assert int(state.cooldown_ticks[0, 0]) == 0


@pytest.mark.parametrize("blocked_reason", ("hidden", "travel-immune"))
@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_committed_tower_projectile_obeys_common_receivability_gate(
    device_name: str,
    blocked_reason: str,
) -> None:
    runtime, knight = _runtime(device_name)
    state = runtime.state
    state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
    state.damage[0, 0] = 109.0
    state.cooldown_ticks[0, 0] = 0
    _seed_stationary_knight(
        runtime,
        knight,
        row=0,
        slot=6,
        stable_id=20,
        owner=1,
        x_units=3_500,
        y_units=8_000,
    )
    launched = runtime.step_tick(_noop(runtime))
    assert launched.effect_allocation.accepted[0, 2]
    before = state.hp.clone()
    if blocked_reason == "hidden":
        runtime.policy_catalog.declares_visibility[knight] = True
        runtime.policy_catalog.visibility_kind[knight] = FAST_VISIBILITY_HIDE_WHEN_IDLE
        runtime.policy_mechanics.bound_stable_id[0, 6] = state.stable_id[0, 6]
        runtime.policy_mechanics.bound_card_id[0, 6] = knight
        runtime.policy_mechanics.visibility_kind[0, 6] = FAST_VISIBILITY_HIDE_WHEN_IDLE
        runtime.policy_mechanics.hidden[0, 6] = True
    else:
        runtime.travel.bound_stable_id[0, 6] = state.stable_id[0, 6]
        runtime.travel.bound_card_id[0, 6] = knight
        runtime.travel.kind[0, 6] = FAST_TRAVEL_DASH
        runtime.travel.phase[0, 6] = FAST_TRAVEL_TRANSIT
    visibility = runtime._policy_visibility_view()
    travel = runtime._travel_view()
    receivable = visibility.direct_effect_receivable & ~travel.immune
    assert not bool(receivable[0, 6])
    safe_card = state.card_id.clamp(0, runtime.action_kernel.catalog.size - 1)

    result = step_fast_effects(
        state,
        runtime.effects,
        runtime.entity_status_kind,
        runtime.entity_status_ticks,
        consume_source_id=runtime.effect_consume_source_id,
        cleanup_dead=False,
        modifiers=runtime.modifiers,
        entity_is_air=runtime.action_kernel.catalog.is_air[safe_card],
        entity_collision_radius_units=(
            runtime.action_kernel.catalog.collision_radius_units[safe_card]
        ),
        tick_status=False,
        entity_committed_direct_receivable=receivable,
        entity_secondary_targetable=receivable,
        entity_area_receivable=receivable,
        entity_effect_receivable_affects_hidden=receivable,
    )

    assert bool(result.impacted.any())
    assert torch.equal(state.hp, before)
    assert not bool(runtime.effects.active.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_tower_combat_replay_and_selective_reset(device_name: str) -> None:
    left, knight = _runtime(device_name)
    right, _ = _runtime(device_name)
    for runtime in (left, right):
        runtime.state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
        runtime.state.damage[0, 0] = 109.0
        _seed_stationary_knight(
            runtime,
            knight,
            row=0,
            slot=6,
            stable_id=20,
            owner=1,
            x_units=3_500,
            y_units=8_000,
        )
    for _ in range(35):
        left.step_tick(_noop(left))
        right.step_tick(_noop(right))
    for descriptor in fields(left.state):
        value = getattr(left.state, descriptor.name)
        if isinstance(value, torch.Tensor):
            assert torch.equal(value, getattr(right.state, descriptor.name))
    for descriptor in fields(left.effects):
        value = getattr(left.effects, descriptor.name)
        if isinstance(value, torch.Tensor):
            assert torch.equal(value, getattr(right.effects, descriptor.name))

    left.state.hp[0, 0] = 0.0
    left.step_tick(_noop(left))
    assert left.state.king_active[0, 0]
    left.reset_rows(torch.ones(1, dtype=torch.bool, device=left.device))
    assert left.state.king_active.tolist() == [[False, False]]
    assert left.state.king_activation_ticks.tolist() == [[0, 0]]
    assert left.state.cooldown_ticks[0, :6].tolist() == [16, 16, 0, 16, 16, 0]
    assert not bool(left.effects.active.any())


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_tower_combat_cuda_graph_matches_eager() -> None:
    runtime, knight = _runtime("cuda")
    reference, _ = _runtime("cuda")
    for candidate in (runtime, reference):
        candidate.state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
        candidate.state.damage[0, 0] = 109.0
        _seed_stationary_knight(
            candidate,
            knight,
            row=0,
            slot=6,
            stable_id=20,
            owner=1,
            x_units=3_500,
            y_units=8_000,
        )
    actions = _noop(runtime)
    runner = SimpleCudaGraphRunner(runtime, actions)
    for _ in range(20):
        graph_step = runner.step_tick(actions)
        eager_step = reference.step_tick(_noop(reference))
        torch.cuda.synchronize(runtime.device)
        assert torch.equal(runtime.state.hp, reference.state.hp)
        assert torch.equal(runtime.state.cooldown_ticks, reference.state.cooldown_ticks)
        assert torch.equal(runtime.state.king_active, reference.state.king_active)
        assert torch.equal(
            graph_step.effect_allocation.accepted,
            eager_step.effect_allocation.accepted,
        )


def test_tower_numeric_effect_hot_path_has_no_host_round_trip() -> None:
    source = inspect.getsource(allocate_fast_attack_effects_)
    source += inspect.getsource(SimpleGymRuntime._effect_commands)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
