from __future__ import annotations

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_attack_effects import (
    FastEffectCommands,
    allocate_fast_attack_effects_,
)
from clasher.torch_sim.simple_effects import FAST_STATUS_STUN
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from clasher.torch_sim.simple_triggered_impacts import (
    FAST_TRIGGER_ATTACK_COMMIT,
    FAST_TRIGGER_DEATH,
    FAST_TRIGGER_DEPLOY_COMPLETE,
    FAST_TRIGGER_IMPACT,
)

ROOTS = (
    "Bowler",
    "ElectroWizard",
    "Fireball",
    "Firecracker",
    "Golem",
    "IceGolem",
    "IceWizard",
    "Knight",
    "MegaKnight",
    "Rocket",
    "Snowball",
    "Tornado",
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _runtime(device_name: str = "cpu") -> tuple[SimpleGymRuntime, dict[str, int]]:
    device = _device(device_name)
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ROOTS,
        device=device,
        canonical_lane_globals=True,
    )
    fast = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((2, fast.size), dtype=torch.int64, device=device)
    hand = torch.zeros(fast.size, dtype=torch.int64, device=device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id])
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id]):
            hand[card_id] = 2_000 + card_id
    deck = [[list(ROOTS[:8]), list(ROOTS[:8])]]
    runtime = setup.create_runtime(
        deck,
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        max_entities=20,
        max_effects=24,
        starting_elixir=10.0,
    )
    runtime.state.damage[:, :6].zero_()
    return runtime, setup.cards.name_to_id


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


def _seed(
    runtime: SimpleGymRuntime,
    ids: dict[str, int],
    name: str,
    *,
    slot: int,
    stable_id: int,
    owner: int,
    x: int,
    y: int,
    hp: float = 10_000.0,
    deploy_ticks: int = 0,
) -> None:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    card_id = ids[name]
    state.active[0, slot] = True
    state.stable_id[0, slot] = stable_id
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), stable_id + 1)
    state.kind[0, slot] = catalog.kind[card_id]
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.x_units[0, slot] = x
    state.y_units[0, slot] = y
    state.hp[0, slot] = hp
    state.max_hp[0, slot] = hp
    state.target_id[0, slot] = 0
    state.damage[0, slot] = catalog.damage[card_id]
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = catalog.speed_units_per_tick[card_id]
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]
    state.cooldown_ticks[0, slot] = 0
    state.deploy_ticks[0, slot] = deploy_ticks
    mask = torch.zeros_like(state.active)
    mask[0, slot] = True
    runtime._initialize_lifecycle_(mask)
    runtime._initialize_modifiers_(mask)
    runtime._initialize_policy_mechanics_(mask)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_deploy_area_fires_only_on_exact_deploy_crossing(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        ids,
        "ElectroWizard",
        slot=6,
        stable_id=20,
        owner=0,
        x=9_000,
        y=12_000,
        deploy_ticks=2,
    )
    runtime.state.damage[0, 6:8] = 0.0
    _seed(
        runtime,
        ids,
        "Knight",
        slot=7,
        stable_id=21,
        owner=1,
        x=10_000,
        y=12_000,
    )

    first = runtime.step_tick(_noop(runtime))
    assert first.triggered is not None
    assert not bool(first.triggered.commands.active.any())
    assert float(runtime.state.hp[0, 7]) == 10_000.0

    crossed = runtime.step_tick(_noop(runtime))
    assert crossed.triggered is not None
    command = crossed.triggered.commands
    selected = command.active & (command.trigger == FAST_TRIGGER_DEPLOY_COMPLETE)
    assert int(selected.sum()) == 1
    assert float(runtime.state.hp[0, 7]) == pytest.approx(10_000.0 - 192.0)
    assert int(runtime.entity_status_kind[0, 7]) == FAST_STATUS_STUN
    assert int(runtime.entity_status_ticks[0, 7]) == 10

    third = runtime.step_tick(_noop(runtime))
    assert third.triggered is not None
    assert not bool(
        (
            third.triggered.commands.active
            & (third.triggered.commands.trigger == FAST_TRIGGER_DEPLOY_COMPLETE)
        ).any()
    )
    assert float(runtime.state.hp[0, 7]) == pytest.approx(10_000.0 - 192.0)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_firecracker_recoil_runs_on_committed_attack(device_name: str) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        ids,
        "Firecracker",
        slot=6,
        stable_id=20,
        owner=0,
        x=9_000,
        y=10_000,
    )
    _seed(
        runtime,
        ids,
        "Knight",
        slot=7,
        stable_id=21,
        owner=1,
        x=9_000,
        y=14_000,
    )
    runtime.state.speed_units_per_tick[0, 7] = 0

    assert runtime.attack_timings is not None
    first_hit_ticks = int(
        runtime.attack_timings.first_hit_delay_ticks[ids["Firecracker"]]
    )
    step = None
    for _ in range(first_hit_ticks):
        candidate = runtime.step_tick(_noop(runtime))
        if candidate.triggered is not None and bool(
            (
                candidate.triggered.commands.active
                & (
                    candidate.triggered.commands.trigger
                    == FAST_TRIGGER_ATTACK_COMMIT
                )
            ).any()
        ):
            step = candidate
            break

    assert step is not None
    assert step.triggered is not None
    selected = step.triggered.commands.active & (
        step.triggered.commands.trigger == FAST_TRIGGER_ATTACK_COMMIT
    )
    assert int(selected.sum()) == 1
    assert int(runtime.state.y_units[0, 6]) == 9_000
    assert bool(step.triggered.impulse.affected[0, 6])


def _allocate_spell(
    runtime: SimpleGymRuntime,
    card_id: int,
    *,
    x: int,
    y: int,
) -> None:
    shape = (1, 1)
    zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
    commands = FastEffectCommands(
        ready=torch.ones(shape, dtype=torch.bool, device=runtime.device),
        source_id=zeros_i64,
        owner=torch.zeros(shape, dtype=torch.int8, device=runtime.device),
        card_id=torch.full(shape, card_id, dtype=torch.int64, device=runtime.device),
        source_x_units=torch.full(
            shape, 9_000, dtype=torch.int32, device=runtime.device
        ),
        source_y_units=torch.full(
            shape, 5_000, dtype=torch.int32, device=runtime.device
        ),
        target_id=zeros_i64,
        target_x_units=torch.full(shape, x, dtype=torch.int32, device=runtime.device),
        target_y_units=torch.full(shape, y, dtype=torch.int32, device=runtime.device),
        damage_multiplier=torch.ones(shape, device=runtime.device),
    )
    allocation = allocate_fast_attack_effects_(
        runtime.state,
        runtime.effects,
        runtime.effect_consume_source_id,
        runtime.action_kernel.catalog,
        commands,
    )
    assert bool(allocation.accepted[0, 0])


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_projectile_impact_adds_push_without_duplicate_damage(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        ids,
        "Knight",
        slot=6,
        stable_id=20,
        owner=1,
        x=10_000,
        y=15_000,
    )
    runtime.state.damage[0, 6] = 0.0
    runtime.state.speed_units_per_tick[0, 6] = 0
    _allocate_spell(runtime, ids["Fireball"], x=9_000, y=15_000)

    impact = None
    for _ in range(80):
        step = runtime.step_tick(_noop(runtime))
        assert step.triggered is not None
        selected = step.triggered.commands.active & (
            step.triggered.commands.trigger == FAST_TRIGGER_IMPACT
        )
        if bool(selected.any()):
            impact = step
            break

    assert impact is not None
    expected_damage = float(
        runtime.action_kernel.catalog.effect_damage[ids["Fireball"]]
    )
    assert float(runtime.state.hp[0, 6]) == pytest.approx(10_000.0 - expected_damage)
    assert int(runtime.state.x_units[0, 6]) == 11_000
    assert impact.triggered is not None
    assert not bool(impact.triggered.effect_allocation.accepted.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_death_secondary_effects_compose_without_double_burst_damage(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    _seed(
        runtime,
        ids,
        "Golem",
        slot=6,
        stable_id=20,
        owner=0,
        x=9_000,
        y=12_000,
        hp=0.0,
    )
    _seed(
        runtime,
        ids,
        "Knight",
        slot=7,
        stable_id=21,
        owner=1,
        x=10_000,
        y=12_000,
    )
    runtime.state.speed_units_per_tick[0, 7] = 0

    step = runtime.step_tick(_noop(runtime))

    assert step.triggered is not None
    selected = step.triggered.commands.active & (
        step.triggered.commands.trigger == FAST_TRIGGER_DEATH
    )
    assert int(selected.sum()) >= 1
    assert float(runtime.state.hp[0, 7]) == pytest.approx(10_000.0 - 225.0)
    assert int(runtime.state.x_units[0, 7]) == 11_800
