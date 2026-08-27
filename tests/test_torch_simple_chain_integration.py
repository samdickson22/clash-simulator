from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep

CHAIN_CARDS = ("ElectroDragon", "ElectroSpirit", "Knight")


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
    full = TensorCardCatalog.compile(loader, CHAIN_CARDS, device=device)
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
        range_units=torch.full((2, 3), 7_500, dtype=torch.int32, device=device),
        sight_range_units=torch.full((2, 3), 9_500, dtype=torch.int32, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    entity_lookup = (
        torch.arange(2 * catalog.size, dtype=torch.int64, device=device)
        .view(2, catalog.size)
        .add_(100)
    )
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device) + 500
    runtime = SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=200, tiebreak_ticks=400),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=24,
        max_effects=8,
        starting_elixir=10.0,
    )
    return runtime, ids


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


def _assert_replay_equal(
    first: SimpleGymRuntime,
    replay: SimpleGymRuntime,
    first_step: SimpleGymRuntimeStep,
    replay_step: SimpleGymRuntimeStep,
) -> None:
    for descriptor in fields(first.state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.state, descriptor.name),
                getattr(replay.state, descriptor.name),
            )
    for descriptor in fields(first.effects):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.effects, descriptor.name),
                getattr(replay.effects, descriptor.name),
            )
    assert torch.equal(first.entity_status_kind, replay.entity_status_kind)
    assert torch.equal(first.entity_status_ticks, replay.entity_status_ticks)
    assert torch.equal(first_step.reward, replay_step.reward)
    assert torch.equal(first_step.effects.targets_hit, replay_step.effects.targets_hit)


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_electro_dragon_runtime_chains_three_once_and_respects_range(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name, "ElectroDragon")
    replay, replay_ids = _runtime(device_name, "ElectroDragon")
    catalog = first.action_kernel.catalog
    assert int(catalog.chain_target_count[ids["ElectroDragon"]]) == 3
    assert int(catalog.chain_hop_radius_units[ids["ElectroDragon"]]) == 4_000
    assert int(catalog.status_duration_ticks[ids["ElectroDragon"]]) == 10
    assert not bool(catalog.consume_source_on_impact[ids["ElectroDragon"]])
    assert bool(catalog.training_supported[ids["ElectroDragon"]])
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            slot=6,
            stable_id=7,
            owner=0,
            card_id=runtime_ids["ElectroDragon"],
            x_units=9_000,
            y_units=10_000,
        )
        # Backtracking to an already-hit lower stable ID would win each tie.
        # Reaching slots 8 and 9 therefore proves visited exclusion. Slot 10
        # is 4,500 units from slot 9 and proves the 4,000-unit cutoff.
        for slot, y_units in zip(
            range(7, 11),
            (13_000, 16_500, 20_000, 24_500),
            strict=True,
        ):
            _seed_entity(
                runtime,
                slot=slot,
                stable_id=slot + 1,
                owner=1,
                card_id=runtime_ids["Knight"],
                x_units=9_000,
                y_units=y_units,
                inert=True,
            )

    launch_count = 0
    impact: SimpleGymRuntimeStep | None = None
    for _ in range(6):
        first_step = first.step_tick(_noop(first))
        replay_step = replay.step_tick(_noop(replay))
        _assert_replay_equal(first, replay, first_step, replay_step)
        assert first_step.committed.tolist() == [True]
        assert first_step.native_ticks.tolist() == [1]
        assert not bool(first_step.effect_allocation.unsupported.any())
        assert not bool(first_step.effect_allocation.capacity_rejected.any())
        launch_count += int(first_step.effect_allocation.accepted[0, 2 + 6])
        if bool(first_step.effects.targets_hit.any()):
            impact = first_step
            break
    assert impact is not None
    assert launch_count == 1
    damage = float(first.action_kernel.catalog.effect_damage[ids["ElectroDragon"]])
    assert first.state.hp[0, 7:11].tolist() == pytest.approx(
        [1_000.0 - damage] * 3 + [1_000.0]
    )
    assert first.entity_status_ticks[0, 7:11].tolist() == [10, 10, 10, 0]
    assert int(impact.effects.targets_hit[0, :, 7:11].sum()) == 3
    assert not bool(first.effects.active.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_electro_spirit_runtime_chains_nine_stuns_and_consumes_source(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name, "ElectroSpirit")
    replay, replay_ids = _runtime(device_name, "ElectroSpirit")
    catalog = first.action_kernel.catalog
    assert int(catalog.chain_target_count[ids["ElectroSpirit"]]) == 9
    assert int(catalog.chain_hop_radius_units[ids["ElectroSpirit"]]) == 4_000
    assert int(catalog.status_duration_ticks[ids["ElectroSpirit"]]) == 10
    assert bool(catalog.consume_source_on_impact[ids["ElectroSpirit"]])
    assert bool(catalog.training_supported[ids["ElectroSpirit"]])
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            slot=6,
            stable_id=7,
            owner=0,
            card_id=runtime_ids["ElectroSpirit"],
            x_units=10_000,
            y_units=15_000,
        )
        for offset, slot in enumerate(range(7, 17)):
            _seed_entity(
                runtime,
                slot=slot,
                stable_id=slot + 1,
                owner=1,
                card_id=runtime_ids["Knight"],
                x_units=11_000 + 3_500 * offset,
                y_units=15_000,
                inert=True,
            )

    first_step = first.step_tick(_noop(first))
    replay_step = replay.step_tick(_noop(replay))
    _assert_replay_equal(first, replay, first_step, replay_step)

    assert first_step.committed.tolist() == [True]
    assert first_step.native_ticks.tolist() == [1]
    assert first_step.effect_allocation.accepted[0, 2 + 6]
    assert not bool(first_step.effect_allocation.unsupported.any())
    assert not bool(first_step.effect_allocation.capacity_rejected.any())
    damage = float(first.action_kernel.catalog.effect_damage[ids["ElectroSpirit"]])
    assert first.state.hp[0, 7:16].tolist() == pytest.approx([1_000.0 - damage] * 9)
    assert float(first.state.hp[0, 16]) == pytest.approx(1_000.0)
    assert first.entity_status_ticks[0, 7:16].tolist() == [10] * 9
    assert int(first.entity_status_ticks[0, 16]) == 0
    assert bool(first_step.effects.sources_consumed[0, 6])
    assert float(first.state.hp[0, 6]) == 0.0
    assert int(first_step.effects.targets_hit[0, :, 7:17].sum()) == 9
    assert not bool(first.effects.active.any())
