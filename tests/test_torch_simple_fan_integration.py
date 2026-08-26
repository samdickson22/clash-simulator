from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import step_fast_effects
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep

FAN_CARDS = ("Bats", "Firecracker", "Knight")


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _runtime(device_name: str) -> tuple[SimpleGymRuntime, dict[str, int]]:
    device = _device(device_name)
    loader = BattleState().card_loader
    full = TensorCardCatalog.compile(loader, FAN_CARDS, device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=loader)
    ids = full.name_to_id
    decks = torch.empty((1, 2, 8), dtype=torch.int64, device=device)
    decks[:, 0] = ids["Firecracker"]
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
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
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
            max_entities=18,
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
    inert: bool = False,
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
    state.hp[0, slot] = 1_000.0 if inert else catalog.hitpoints[card_id]
    state.max_hp[0, slot] = state.hp[0, slot]
    state.damage[0, slot] = 0.0 if inert else catalog.damage[card_id]
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = (
        0 if inert else catalog.speed_units_per_tick[card_id]
    )
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]
    state.cooldown_ticks[0, slot] = 0
    state.deploy_ticks[0, slot] = 0
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), stable_id + 1)


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


def _assert_replay_equal(
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


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_firecracker_runtime_emits_one_scaled_fan_without_carrier_damage(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name)
    replay, replay_ids = _runtime(device_name)
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            slot=6,
            stable_id=7,
            owner=0,
            card_id=runtime_ids["Firecracker"],
            x_units=9_000,
            y_units=10_000,
        )
        for slot, card_name, owner, x_units, y_units in (
            (7, "Knight", 1, 9_000, 14_000),  # carrier impact / fan origin
            (8, "Knight", 1, 9_000, 18_500),  # center ray
            (9, "Bats", 1, 11_385, 17_816),  # -32-degree outer ray
            (10, "Knight", 0, 6_615, 17_816),  # friendly +32-degree ray
            (11, "Knight", 1, 14_000, 18_000),  # beyond every finite ray
        ):
            _seed_entity(
                runtime,
                slot=slot,
                stable_id=slot + 1,
                owner=owner,
                card_id=runtime_ids[card_name],
                x_units=x_units,
                y_units=y_units,
                inert=True,
            )
        runtime.entity_status_ticks[0, 7:12] = 1_000
        # Put an enemy Crown Tower on the same outer ray. It shares the normal
        # eligibility and tower-scaling path rather than a fan-specific path.
        runtime.state.x_units[0, 3] = 11_385
        runtime.state.y_units[0, 3] = 17_816

    catalog = first.action_kernel.catalog
    firecracker = ids["Firecracker"]
    assert int(catalog.fan_ray_count[firecracker]) == 5
    assert int(catalog.fan_range_units[firecracker]) == 5_000
    assert int(catalog.fan_radius_units[firecracker]) == 400
    assert float(catalog.fan_spread_degrees[firecracker]) == pytest.approx(80.0)
    assert float(catalog.effect_damage[firecracker]) == pytest.approx(64.0)
    assert bool(catalog.omits_recoil[firecracker])
    assert bool(catalog.training_supported[firecracker])

    command_slot = 2 + 6
    launch_count = 0
    effect_slot = -1
    impact: SimpleGymRuntimeStep | None = None
    for _ in range(12):
        first_step = first.step_tick(_noop(first))
        replay_step = replay.step_tick(_noop(replay))
        _assert_replay_equal(first, replay, first_step, replay_step)
        assert first_step.committed.tolist() == [True]
        assert first_step.native_ticks.tolist() == [1]
        assert not bool(first_step.effect_allocation.unsupported.any())
        assert not bool(first_step.effect_allocation.capacity_rejected.any())
        accepted = bool(first_step.effect_allocation.accepted[0, command_slot])
        launch_count += int(accepted)
        if accepted:
            effect_slot = int(first_step.effect_allocation.effect_slot[0, command_slot])
        if bool(first_step.effects.targets_hit.any()):
            impact = first_step
            break

    assert impact is not None
    assert launch_count == 1
    assert effect_slot >= 0
    assert int(first.effects.fan_ray_count[0, effect_slot]) == 5
    assert not bool(first.effects.active[0, effect_slot])
    damage = float(catalog.effect_damage[firecracker])

    # Primary, center, airborne outer target, and Crown Tower each receive one
    # scaled child payload. The carrier does not add another primary hit.
    assert first.state.hp[0, 7:12].tolist() == pytest.approx(
        [1_000.0 - damage, 1_000.0 - damage, 1_000.0 - damage, 1_000.0, 1_000.0]
    )
    assert float(first.state.hp[0, 3]) == pytest.approx(50_000.0 - damage)
    assert int(impact.effects.targets_hit[0, :, [3, 7, 8, 9]].sum()) == 4

    # Recoil is explicitly reported as omitted and is not conflated with the
    # fan payload or allowed to create a second effect/cooldown.
    assert first.state.x_units[0, 6].item() == 9_000
    assert first.state.y_units[0, 6].item() == 10_000
    assert int(first.state.cooldown_ticks[0, 6]) > 0


def test_fan_integration_hot_path_has_no_card_dispatch_or_host_sync() -> None:
    source = inspect.getsource(step_fast_effects)
    for forbidden in (
        "Firecracker",
        "spawnProjectileData",
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
    ):
        assert forbidden not in source
