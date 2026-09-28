from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_attack_effects import allocate_fast_attack_effects_
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import step_fast_effects
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep

LINE_CARDS = ("Bats", "Bowler", "Knight", "MagicArcher")


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _runtime(
    device_name: str,
    source_card: str,
) -> tuple[SimpleGymRuntime, dict[str, int]]:
    device = _device(device_name)
    loader = BattleState().card_loader
    full = TensorCardCatalog.compile(loader, LINE_CARDS, device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=loader)
    ids = full.name_to_id
    decks = torch.empty((1, 2, 8), dtype=torch.int64, device=device)
    decks[:, 0] = ids[source_card]
    decks[:, 1] = ids["Knight"]
    tower_spec = FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]],
            dtype=torch.int32,
            device=device,
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]],
            dtype=torch.int32,
            device=device,
        ),
        hitpoints=torch.full((2, 3), 50_000.0, device=device),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.zeros((2, 3), dtype=torch.int32, device=device),
        sight_range_units=torch.zeros((2, 3), dtype=torch.int32, device=device),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )
    entity_lookup = (
        torch.arange(2 * catalog.size, dtype=torch.int64, device=device)
        .view(2, catalog.size)
        .add_(100)
    )
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device) + 500
    return (
        SimpleGymRuntime(
            decks,
            catalog,
            tower_spec,
            FastMatchRules(regulation_ticks=200, tiebreak_ticks=400),
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            max_entities=20,
            max_effects=8,
            starting_elixir=10.0,
        ),
        ids,
    )


def _seed_entity(
    runtime: SimpleGymRuntime,
    *,
    slot: int,
    stable_id: int,
    owner: int,
    card_id: int,
    x_units: int,
    y_units: int,
) -> None:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    state.active[0, slot] = True
    state.stable_id[0, slot] = stable_id
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.kind[0, slot] = catalog.kind[card_id]
    state.x_units[0, slot] = x_units
    state.y_units[0, slot] = y_units
    state.hp[0, slot] = 1_000.0
    state.max_hp[0, slot] = 1_000.0
    state.damage[0, slot] = 0.0 if owner == 1 else catalog.damage[card_id]
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = (
        0 if owner == 1 else catalog.speed_units_per_tick[card_id]
    )
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]
    state.cooldown_ticks[0, slot] = 0
    state.deploy_ticks[0, slot] = 0
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), stable_id + 1)


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )


def _assert_runtime_equal(
    first: SimpleGymRuntime,
    replay: SimpleGymRuntime,
    first_step: SimpleGymRuntimeStep,
    replay_step: SimpleGymRuntimeStep,
) -> None:
    for owner_name in ("state", "effects"):
        first_owner = getattr(first, owner_name)
        replay_owner = getattr(replay, owner_name)
        for descriptor in fields(first_owner):
            if descriptor.name != "device":
                assert torch.equal(
                    getattr(first_owner, descriptor.name),
                    getattr(replay_owner, descriptor.name),
                )
    assert torch.equal(first_step.reward, replay_step.reward)
    assert torch.equal(first_step.effects.targets_hit, replay_step.effects.targets_hit)


def _run_replay_to_impact(
    first: SimpleGymRuntime,
    replay: SimpleGymRuntime,
    *,
    source_slot: int = 6,
    max_ticks: int,
) -> tuple[SimpleGymRuntimeStep, int]:
    launches = 0
    command_slot = 2 + source_slot
    impact: SimpleGymRuntimeStep | None = None
    for _ in range(max_ticks):
        first_step = first.step_tick(_noop(first))
        replay_step = replay.step_tick(_noop(replay))
        _assert_runtime_equal(first, replay, first_step, replay_step)
        assert first_step.committed.tolist() == [True]
        assert first_step.native_ticks.tolist() == [1]
        assert not bool(first_step.effect_allocation.unsupported.any())
        assert not bool(first_step.effect_allocation.capacity_rejected.any())
        launches += int(first_step.effect_allocation.accepted[0, command_slot])
        if bool(first_step.effects.targets_hit.any()):
            impact = first_step
            break
    assert impact is not None
    return impact, launches


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_magic_archer_runtime_hits_primary_air_and_far_tower_once(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name, "MagicArcher")
    replay, replay_ids = _runtime(device_name, "MagicArcher")
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            slot=6,
            stable_id=7,
            owner=0,
            card_id=runtime_ids["MagicArcher"],
            x_units=3_500,
            y_units=14_500,
        )
        for slot, card_name, x_units, y_units in (
            (7, "Knight", 3_500, 18_000),  # committed primary
            (8, "Bats", 3_500, 22_000),  # air target behind primary
            (9, "Knight", 3_800, 22_000),  # outside 250-unit width
            (10, "Knight", 3_500, 10_000),  # behind source
        ):
            _seed_entity(
                runtime,
                slot=slot,
                stable_id=slot + 1,
                owner=1,
                card_id=runtime_ids[card_name],
                x_units=x_units,
                y_units=y_units,
            )

    catalog = first.action_kernel.catalog
    archer = ids["MagicArcher"]
    assert int(catalog.line_range_units[archer]) == 11_000
    assert int(catalog.line_half_width_units[archer]) == 250
    assert not bool(catalog.omits_displacement[archer])
    assert bool(catalog.training_supported[archer])

    impact, launches = _run_replay_to_impact(first, replay, max_ticks=16)

    damage = float(catalog.effect_damage[archer])
    assert launches == 1
    assert impact.effects.targets_hit[0, :, [3, 7, 8]].sum().item() == 3
    assert first.state.hp[0, 7:11].tolist() == pytest.approx(
        [1_000.0 - damage, 1_000.0 - damage, 1_000.0, 1_000.0]
    )
    assert float(first.state.hp[0, 3]) == pytest.approx(50_000.0 - damage)
    assert not bool(first.effects.active.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_bowler_runtime_hits_ground_line_and_flags_omitted_pushback(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name, "Bowler")
    replay, replay_ids = _runtime(device_name, "Bowler")
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            slot=6,
            stable_id=7,
            owner=0,
            card_id=runtime_ids["Bowler"],
            x_units=3_500,
            y_units=18_000,
        )
        for slot, card_name, x_units, y_units in (
            (7, "Knight", 3_500, 21_000),  # committed primary
            (8, "Knight", 3_500, 23_500),  # ground target behind primary
            (9, "Bats", 3_500, 23_000),  # air target on centerline
            (10, "Knight", 4_700, 22_500),  # outside 1,000-unit width
            (11, "Knight", 3_500, 14_000),  # behind source
        ):
            _seed_entity(
                runtime,
                slot=slot,
                stable_id=slot + 1,
                owner=1,
                card_id=runtime_ids[card_name],
                x_units=x_units,
                y_units=y_units,
            )

    catalog = first.action_kernel.catalog
    bowler = ids["Bowler"]
    assert int(catalog.line_range_units[bowler]) == 7_500
    assert int(catalog.line_half_width_units[bowler]) == 1_000
    assert bool(catalog.omits_displacement[bowler])
    assert bool(catalog.training_supported[bowler])
    initial_positions = first.state.y_units[0, 7:12].clone()

    impact, launches = _run_replay_to_impact(first, replay, max_ticks=52)

    damage = float(catalog.effect_damage[bowler])
    assert launches == 1
    assert impact.effects.targets_hit[0, :, [3, 7, 8]].sum().item() == 3
    assert first.state.hp[0, 7:12].tolist() == pytest.approx(
        [1_000.0 - damage, 1_000.0 - damage, 1_000.0, 1_000.0, 1_000.0]
    )
    assert float(first.state.hp[0, 3]) == pytest.approx(50_000.0 - damage)
    assert torch.equal(first.state.y_units[0, 7:12], initial_positions)
    assert not bool(first.effects.active.any())


def test_line_runtime_hot_paths_have_no_card_dispatch_or_host_sync() -> None:
    for function in (allocate_fast_attack_effects_, step_fast_effects):
        source = inspect.getsource(function)
        for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
            assert forbidden not in source
        for card_name in ("MagicArcher", "Bowler"):
            assert card_name not in source
