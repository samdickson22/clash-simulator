from __future__ import annotations

import inspect

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_engine import FastTensorGym
from clasher.torch_sim.simple_outcomes import FAST_TOWER_SLOT_COUNT
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import compile_standard_simple_setup

ROOTS = (
    "Giant",
    "InfernoTower",
    "Knight",
    "Musketeer",
    "RoyalGhost",
)


def _runtime(
    device_name: str,
    *,
    max_effects: int = 32,
) -> tuple[SimpleGymRuntime, dict[str, int]]:
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
    deck = [list(ROOTS) + ["Knight"] * 3] * 2
    runtime = setup.create_runtime(
        [[deck[0], deck[1]]],
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        max_entities=20,
        max_effects=max_effects,
    )
    runtime.state.damage[:, :FAST_TOWER_SLOT_COUNT] = 0.0
    return runtime, setup.cards.name_to_id


def _seed(
    runtime: SimpleGymRuntime,
    ids: dict[str, int],
    *,
    slot: int,
    name: str,
    stable_id: int,
    owner: int,
    x_units: int,
    y_units: int = 15_000,
    damage: bool,
    building: bool = False,
) -> None:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    card_id = ids[name]
    state.active[0, slot] = True
    state.stable_id[0, slot] = stable_id
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), stable_id + 1)
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.kind[0, slot] = 1 if building else catalog.kind[card_id]
    state.x_units[0, slot] = x_units
    state.y_units[0, slot] = y_units
    state.hp[0, slot] = 1_000_000.0
    state.max_hp[0, slot] = 1_000_000.0
    state.damage[0, slot] = catalog.damage[card_id] if damage else 0.0
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = 0
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]
    state.deploy_ticks[0, slot] = 0
    state.cooldown_ticks[0, slot] = 0


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full(
        (1, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=runtime.device,
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("source_name", "expected_first_tick", "target_building"),
    (
        ("Knight", 10, False),
        ("Musketeer", 14, False),
        ("Giant", 10, True),
        ("InfernoTower", 8, False),
    ),
)
def test_standard_runtime_uses_serialized_first_hit_and_full_commit_cycle(
    device_name: str,
    source_name: str,
    expected_first_tick: int,
    target_building: bool,
) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        ids,
        slot=6,
        name=source_name,
        stable_id=7,
        owner=0,
        x_units=9_000,
        damage=True,
    )
    _seed(
        runtime,
        ids,
        slot=7,
        name="Knight",
        stable_id=8,
        owner=1,
        x_units=9_500,
        damage=False,
        building=target_building,
    )
    assert runtime.attack_locks is not None
    assert runtime.attack_timings is not None
    accepted_ticks: list[int] = []
    for tick in range(1, expected_first_tick + 1):
        result = runtime.step_tick(_noop(runtime))
        if bool(result.effect_allocation.accepted[0, 2 + 6]):
            accepted_ticks.append(tick)

    source_id = ids[source_name]
    assert accepted_ticks == [expected_first_tick]
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 8
    assert int(runtime.attack_locks.cooldown_ticks[0, 6]) == int(
        runtime.attack_timings.hit_cycle_ticks[source_id]
    )
    assert torch.equal(
        runtime.state.cooldown_ticks[0, 6],
        runtime.attack_locks.cooldown_ticks[0, 6],
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_retains_then_switches_and_loses_stable_lock(device_name: str) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        ids,
        slot=6,
        name="Musketeer",
        stable_id=7,
        owner=0,
        x_units=9_000,
        damage=True,
    )
    _seed(
        runtime,
        ids,
        slot=7,
        name="Knight",
        stable_id=8,
        owner=1,
        x_units=12_000,
        damage=False,
    )
    runtime.step_tick(_noop(runtime))
    assert runtime.attack_locks is not None
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 8

    _seed(
        runtime,
        ids,
        slot=8,
        name="Knight",
        stable_id=9,
        owner=1,
        x_units=9_500,
        damage=False,
    )
    runtime.step_tick(_noop(runtime))
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 8
    assert int(runtime.attack_locks.last_switch_tick[0, 6]) == -1

    runtime.state.hp[0, 7] = 0
    switch_tick = int(runtime.state.tick[0])
    runtime.step_tick(_noop(runtime))
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 9
    assert int(runtime.attack_locks.last_switch_tick[0, 6]) == switch_tick

    runtime.state.hp[0, 8] = 0
    loss_tick = int(runtime.state.tick[0])
    runtime.step_tick(_noop(runtime))
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 0
    assert int(runtime.attack_locks.last_loss_tick[0, 6]) == loss_tick
    # The public target plane may carry a far Crown Tower navigation goal, but
    # the combat lock remains empty until an enemy actually enters sight.
    assert int(runtime.state.target_id[0, 6]) > 0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_invisible_target_breaks_lock_and_visible_target_reacquires(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        ids,
        slot=6,
        name="Musketeer",
        stable_id=7,
        owner=0,
        x_units=9_000,
        damage=True,
    )
    _seed(
        runtime,
        ids,
        slot=7,
        name="RoyalGhost",
        stable_id=8,
        owner=1,
        x_units=10_000,
        damage=False,
    )
    spawned = torch.zeros_like(runtime.state.active)
    spawned[0, 7] = True
    runtime._initialize_policy_mechanics_(spawned)
    assert bool(runtime.policy_mechanics.invisible[0, 7])

    runtime.step_tick(_noop(runtime))
    assert runtime.attack_locks is not None
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 0

    runtime.policy_mechanics.invisible[0, 7] = False
    runtime.policy_mechanics.fade_elapsed_ticks[0, 7] = 0
    runtime.step_tick(_noop(runtime))
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 8

    runtime.policy_mechanics.invisible[0, 7] = True
    loss_tick = int(runtime.state.tick[0])
    runtime.step_tick(_noop(runtime))
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 0
    assert int(runtime.attack_locks.last_loss_tick[0, 6]) == loss_tick


def test_effect_capacity_rejection_does_not_commit_attack_cycle() -> None:
    runtime, ids = _runtime("cpu", max_effects=1)
    _seed(
        runtime,
        ids,
        slot=6,
        name="Knight",
        stable_id=7,
        owner=0,
        x_units=9_000,
        damage=True,
    )
    _seed(
        runtime,
        ids,
        slot=7,
        name="Knight",
        stable_id=8,
        owner=1,
        x_units=9_500,
        damage=False,
    )
    for _ in range(9):
        runtime.step_tick(_noop(runtime))
    runtime.effects.active.fill_(True)
    rejected = runtime.step_tick(_noop(runtime))
    assert runtime.attack_locks is not None
    assert not bool(rejected.effect_allocation.accepted[0, 2 + 6])
    assert int(runtime.attack_locks.cooldown_ticks[0, 6]) == 0

    runtime.effects.active.zero_()
    accepted = runtime.step_tick(_noop(runtime))
    assert bool(accepted.effect_allocation.accepted[0, 2 + 6])
    assert runtime.attack_timings is not None
    assert int(runtime.attack_locks.cooldown_ticks[0, 6]) == int(
        runtime.attack_timings.hit_cycle_ticks[ids["Knight"]]
    )


def test_stun_slot_reuse_selective_reset_and_tower_lock_coexistence() -> None:
    runtime, ids = _runtime("cpu")
    _seed(
        runtime,
        ids,
        slot=6,
        name="Knight",
        stable_id=7,
        owner=0,
        x_units=3_500,
        y_units=8_000,
        damage=True,
    )
    _seed(
        runtime,
        ids,
        slot=7,
        name="Knight",
        stable_id=8,
        owner=1,
        x_units=3_500,
        y_units=9_000,
        damage=False,
    )
    runtime.state.damage[0, 0] = 109.0
    runtime.step_tick(_noop(runtime))
    assert runtime.attack_locks is not None
    assert runtime.attack_timings is not None
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 8
    assert int(runtime.attack_locks.source_stable_id[0, :FAST_TOWER_SLOT_COUNT].sum()) == 0
    assert int(runtime.state.target_id[0, 0]) == 8

    runtime.entity_status_ticks[0, 6] = 2
    runtime.entity_status_kind[0, 6] = 1
    runtime.step_tick(_noop(runtime))
    assert int(runtime.attack_locks.target_stable_id[0, 6]) == 0
    assert int(runtime.attack_locks.cooldown_ticks[0, 6]) == int(
        runtime.attack_timings.hit_cycle_ticks[ids["Knight"]]
    )

    runtime.entity_status_ticks[0, 6] = 0
    runtime.entity_status_kind[0, 6] = 0
    runtime.state.stable_id[0, 6] = 20
    runtime.step_tick(_noop(runtime))
    assert int(runtime.attack_locks.source_stable_id[0, 6]) == 20
    assert int(runtime.attack_locks.last_switch_tick[0, 6]) == -1

    runtime.reset_rows(torch.tensor([True]))
    assert not bool(runtime.attack_locks.source_stable_id.any())
    assert not bool(runtime.attack_locks.target_stable_id.any())
    assert bool(runtime.attack_locks.last_acquire_tick.eq(-1).all())
    assert bool(runtime.state.active[0, :FAST_TOWER_SLOT_COUNT].all())


def test_integrated_attack_lock_hot_path_has_no_host_synchronization() -> None:
    source = inspect.getsource(FastTensorGym._ordinary_troop_phase)
    source += inspect.getsource(FastTensorGym.commit_attacks_)
    for forbidden in (".item(", ".cpu(", ".tolist(", ".numpy(", "nonzero("):
        assert forbidden not in source
