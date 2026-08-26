from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> torch.device:
    name = str(request.param)
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _runtime(
    device: torch.device,
    source_name: str,
) -> tuple[SimpleGymRuntime, dict[str, int]]:
    loader = CardDataLoader()
    cards = TensorCardCatalog.compile(
        loader,
        ("InfernoDragon", "InfernoTower", "Knight"),
        device=device,
    )
    catalog = FastCardCatalog.from_tensor_catalog(cards, loader=loader)
    source = cards.name_to_id[source_name]
    decks = torch.full((1, 2, 8), source, dtype=torch.int64, device=device)
    tower_spec = FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=device),
        x_units=torch.tensor(
            ((3_500, 14_500, 9_000), (3_500, 14_500, 9_000)),
            dtype=torch.int32,
            device=device,
        ),
        y_units=torch.tensor(
            ((6_500, 6_500, 2_500), (25_500, 25_500, 29_500)),
            dtype=torch.int32,
            device=device,
        ),
        hitpoints=torch.full((2, 3), 100_000.0, device=device),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full(
            (2, 3), 7_500, dtype=torch.int32, device=device
        ),
        sight_range_units=torch.full(
            (2, 3), 9_500, dtype=torch.int32, device=device
        ),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )
    entity_lookup = torch.arange(
        2 * catalog.size, dtype=torch.int64, device=device
    ).view(2, catalog.size)
    runtime = SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=500, tiebreak_ticks=1_000),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=torch.arange(catalog.size, device=device),
        max_entities=12,
        max_effects=16,
        starting_elixir=10.0,
    )
    return runtime, cards.name_to_id


def _seed_connected_pair(
    runtime: SimpleGymRuntime,
    ids: dict[str, int],
    source_name: str,
) -> tuple[int, int]:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    source_slot, target_slot = 6, 7
    source = ids[source_name]
    target = ids["Knight"]
    state.active[0, source_slot : target_slot + 1] = True
    state.stable_id[0, source_slot : target_slot + 1] = torch.tensor(
        (7, 8), dtype=torch.int64, device=runtime.device
    )
    state.next_stable_id[0] = 9
    state.owner[0, source_slot : target_slot + 1] = torch.tensor(
        (0, 1), dtype=torch.int8, device=runtime.device
    )
    state.card_id[0, source_slot : target_slot + 1] = torch.tensor(
        (source, target), dtype=torch.int64, device=runtime.device
    )
    state.kind[0, source_slot : target_slot + 1] = torch.stack(
        (catalog.kind[source], catalog.kind[target])
    )
    state.x_units[0, source_slot : target_slot + 1] = 9_000
    state.y_units[0, source_slot : target_slot + 1] = torch.tensor(
        (12_000, 14_000), dtype=torch.int32, device=runtime.device
    )
    state.hp[0, source_slot] = catalog.hitpoints[source]
    state.max_hp[0, source_slot] = catalog.hitpoints[source]
    state.hp[0, target_slot] = 100_000.0
    state.max_hp[0, target_slot] = 100_000.0
    for field_name, table in (
        ("damage", catalog.damage),
        ("range_units", catalog.range_units),
        ("sight_range_units", catalog.sight_range_units),
        ("speed_units_per_tick", catalog.speed_units_per_tick),
        ("hit_cooldown_ticks", catalog.hit_cooldown_ticks),
    ):
        field = getattr(state, field_name)
        field[0, source_slot : target_slot + 1] = torch.stack(
            (table[source], table[target])
        )
    runtime.entity_status_ticks[0, target_slot] = 1_000
    return source_slot, target_slot


@pytest.mark.parametrize("source_name", ("InfernoTower", "InfernoDragon"))
def test_serialized_ramp_catalog_and_full_runtime_damage_trace(
    tensor_device: torch.device,
    source_name: str,
) -> None:
    runtime, ids = _runtime(tensor_device, source_name)
    replay, replay_ids = _runtime(tensor_device, source_name)
    source_slot, target_slot = _seed_connected_pair(runtime, ids, source_name)
    _seed_connected_pair(replay, replay_ids, source_name)
    catalog = runtime.action_kernel.catalog
    source = ids[source_name]

    assert bool(catalog.damage_ramp_enabled[source])
    assert (
        int(catalog.damage_ramp_stage_1_ticks[source]),
        int(catalog.damage_ramp_stage_2_ticks[source]),
        int(catalog.damage_ramp_retarget_grace_ticks[source]),
    ) == (40, 80, 16)
    expected_damage = (
        (43.0, 158.0, 847.0)
        if source_name == "InfernoTower"
        else (35.0, 120.0, 422.0)
    )
    base = float(catalog.effect_damage[source])
    compiled_damage = tuple(
        base * float(multiplier[source])
        for multiplier in (
            catalog.damage_ramp_stage_0_multiplier,
            catalog.damage_ramp_stage_1_multiplier,
            catalog.damage_ramp_stage_2_multiplier,
        )
    )
    assert compiled_damage == pytest.approx(expected_damage)

    noop = torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )
    attacks: list[tuple[int, float]] = []
    initial_hp = float(runtime.state.hp[0, target_slot])
    for tick in range(1, 82):
        result = runtime.step_tick(noop)
        replay_result = replay.step_tick(noop)
        command = 2 + source_slot
        if bool(result.effect_allocation.accepted[0, command]):
            effect_slot = int(result.effect_allocation.effect_slot[0, command])
            attacks.append((tick, float(runtime.effects.damage[0, effect_slot])))
        assert torch.equal(result.committed, replay_result.committed)

    assert attacks == [
        *((tick, expected_damage[0]) for tick in (1, 9, 17, 25, 33)),
        *((tick, expected_damage[1]) for tick in (41, 49, 57, 65, 73)),
        (81, expected_damage[2]),
    ]
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 81
    assert int(runtime.damage_ramp.stage[0, source_slot]) == 2
    assert int(runtime.damage_ramp.observed_target_stable_id[0, source_slot]) == 8
    expected_total = sum(damage for _, damage in attacks)
    assert initial_hp - float(runtime.state.hp[0, target_slot]) == pytest.approx(
        expected_total
    )
    for owner_name in ("state", "damage_ramp", "effects"):
        owner = getattr(runtime, owner_name)
        replay_owner = getattr(replay, owner_name)
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if isinstance(value, torch.Tensor):
                assert torch.equal(value, getattr(replay_owner, descriptor.name))


def test_runtime_retarget_loss_stun_and_slot_reuse_reset_ramp(
    tensor_device: torch.device,
) -> None:
    runtime, ids = _runtime(tensor_device, "InfernoTower")
    source_slot, target_slot = _seed_connected_pair(
        runtime, ids, "InfernoTower"
    )
    noop = torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )
    for _ in range(4):
        runtime.step_tick(noop)
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 4

    replacement_slot = 8
    runtime.state.active[0, replacement_slot] = True
    runtime.state.stable_id[0, replacement_slot] = 9
    runtime.state.next_stable_id[0] = 10
    runtime.state.owner[0, replacement_slot] = 1
    runtime.state.card_id[0, replacement_slot] = ids["Knight"]
    runtime.state.kind[0, replacement_slot] = 0
    runtime.state.x_units[0, replacement_slot] = 9_000
    runtime.state.y_units[0, replacement_slot] = 12_100
    runtime.state.hp[0, replacement_slot] = 100_000.0
    runtime.state.max_hp[0, replacement_slot] = 100_000.0
    runtime.entity_status_ticks[0, replacement_slot] = 1_000
    runtime.state.cooldown_ticks[0, source_slot] = 0

    retarget = runtime.step_tick(noop)
    command = 2 + source_slot
    assert not bool(retarget.effect_allocation.accepted[0, command])
    assert int(runtime.damage_ramp.observed_target_stable_id[0, source_slot]) == 9
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 1
    assert int(runtime.damage_ramp.stage[0, source_slot]) == 0
    assert int(runtime.state.cooldown_ticks[0, source_slot]) == 16

    runtime.state.active[0, replacement_slot] = False
    runtime.state.y_units[0, target_slot] = 30_000
    runtime.step_tick(noop)
    assert int(runtime.damage_ramp.observed_target_stable_id[0, source_slot]) == 0
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 0
    assert int(runtime.damage_ramp.stage[0, source_slot]) == 0
    runtime.state.y_units[0, target_slot] = 14_000
    runtime.step_tick(noop)
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 1
    runtime.entity_status_ticks[0, source_slot] = 2
    runtime.step_tick(noop)
    assert int(runtime.damage_ramp.observed_target_stable_id[0, source_slot]) == 0
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 0

    # Lifecycle resolution and a subsequent deployment into the same physical
    # slot must not preserve a prior entity's beam history.
    runtime.entity_status_ticks[0, source_slot] = 0
    runtime.damage_ramp.observed_target_stable_id[0, source_slot] = 8
    runtime.damage_ramp.connected_ticks[0, source_slot] = 80
    runtime.damage_ramp.stage[0, source_slot] = 2
    runtime.state.hp[0, source_slot] = 0
    runtime.step_tick(noop)
    assert not bool(runtime.state.active[0, source_slot])
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 0

    deploy_tile = 10 * 18 + 8
    deployed = runtime.step_tick(
        torch.tensor(
            ((deploy_tile, NO_OP_ACTION),),
            dtype=torch.int64,
            device=runtime.device,
        )
    )
    assert bool(deployed.action_success[0, 0])
    assert bool(runtime.state.active[0, source_slot])
    assert int(runtime.damage_ramp.observed_target_stable_id[0, source_slot]) == 0
    assert int(runtime.damage_ramp.connected_ticks[0, source_slot]) == 0
    assert int(runtime.damage_ramp.stage[0, source_slot]) == 0


def test_runtime_ramp_seam_has_no_card_name_tick_dispatch() -> None:
    source = inspect.getsource(SimpleGymRuntime.step_tick)
    assert "InfernoTower" not in source
    assert "InfernoDragon" not in source
