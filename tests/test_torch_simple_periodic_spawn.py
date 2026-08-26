from __future__ import annotations

from dataclasses import fields, replace
import inspect

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_periodic_spawn import (
    FAST_PERIODIC_UNLIMITED,
    FastPeriodicSpawnCatalog,
    FastPeriodicSpawnState,
    step_periodic_spawns_,
)
from clasher.torch_sim.simple_spawn_blueprints import (
    FastSpawnBlueprintCatalog,
)

ROOTS = ("Witch", "NightWitch", "Tombstone")


def _catalog(device_name: str) -> tuple[FastPeriodicSpawnCatalog, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    loader = CardDataLoader()
    base = TensorCardCatalog.compile(loader, ROOTS, device=device_name)
    blueprints = FastSpawnBlueprintCatalog.compile(loader, base)
    catalog = FastPeriodicSpawnCatalog.from_spawn_blueprints(blueprints)
    return catalog, {name: blueprints.cards.name_to_id[name] for name in ROOTS}


def _inputs(
    card_ids: list[int],
    stable_ids: list[int],
    *,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    shape = (1, len(card_ids))
    return (
        torch.ones(shape, dtype=torch.bool, device=device),
        torch.tensor([stable_ids], dtype=torch.int64, device=device),
        torch.tensor([card_ids], dtype=torch.int64, device=device),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_serialized_witch_night_witch_and_tombstone_cadence(
    device_name: str,
) -> None:
    catalog, ids = _catalog(device_name)
    state = FastPeriodicSpawnState.empty(1, 3, device=catalog.device)
    active, stable, cards = _inputs(
        [ids["Witch"], ids["NightWitch"], ids["Tombstone"]],
        [30, 10, 20],
        device=catalog.device,
    )

    initial = step_periodic_spawns_(
        catalog,
        state,
        tick=0,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    assert not bool(initial.ready.any())
    assert state.next_tick.tolist() == [[20, 20, 70]]
    assert state.waves_remaining.tolist() == [[FAST_PERIODIC_UNLIMITED] * 3]

    simultaneous = step_periodic_spawns_(
        catalog,
        state,
        tick=20,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    # Source IDs, not storage slots or card names, define command order.
    assert simultaneous.ready.tolist() == [[True, True, False]]
    assert simultaneous.source_stable_id.tolist() == [[10, 30, 0]]
    assert simultaneous.source_slot.tolist() == [[1, 0, -1]]
    assert simultaneous.count.tolist() == [[2, 4, 0]]
    assert state.next_tick.tolist() == [[160, 120, 70]]

    tombstone = step_periodic_spawns_(
        catalog,
        state,
        tick=70,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    assert tombstone.ready.tolist() == [[True, False, False]]
    assert tombstone.source_stable_id.tolist() == [[20, 0, 0]]
    assert tombstone.count.tolist() == [[2, 0, 0]]
    assert state.next_tick.tolist() == [[160, 120, 140]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_finite_and_unlimited_waves_advance_without_host_events(
    device_name: str,
) -> None:
    catalog, ids = _catalog(device_name)
    witch_row = int(catalog.periodic_blueprint_by_card[ids["Witch"]].cpu())
    finite_waves = catalog.max_waves.clone()
    finite_waves[witch_row] = 2
    catalog = replace(catalog, max_waves=finite_waves)
    state = FastPeriodicSpawnState.empty(1, 2, device=catalog.device)
    active, stable, cards = _inputs(
        [ids["Witch"], ids["NightWitch"]],
        [4, 8],
        device=catalog.device,
    )
    step_periodic_spawns_(
        catalog,
        state,
        tick=0,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    emitted: list[list[int]] = []
    for tick in (20, 120, 160, 220, 300):
        command = step_periodic_spawns_(
            catalog,
            state,
            tick=tick,
            active=active,
            source_stable_id=stable,
            source_card_id=cards,
        )
        emitted.append(command.source_stable_id[command.ready].cpu().tolist())
    assert emitted == [[4, 8], [8], [4], [8], []]
    assert int(state.waves_remaining[0, 0].cpu()) == 0
    assert int(state.waves_remaining[0, 1].cpu()) == FAST_PERIODIC_UNLIMITED


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_death_stun_policy_and_slot_reuse_reset_deadlines(device_name: str) -> None:
    catalog, ids = _catalog(device_name)
    witch_row = int(catalog.periodic_blueprint_by_card[ids["Witch"]].cpu())
    pause = catalog.pause_while_stunned.clone()
    pause[witch_row] = True
    catalog = replace(catalog, pause_while_stunned=pause)
    state = FastPeriodicSpawnState.empty(1, 2, device=catalog.device)
    active, stable, cards = _inputs(
        [ids["Witch"], ids["NightWitch"]],
        [11, 12],
        device=catalog.device,
    )
    step_periodic_spawns_(
        catalog,
        state,
        tick=0,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    stunned = torch.ones_like(active)
    due = step_periodic_spawns_(
        catalog,
        state,
        tick=20,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
        stunned=stunned,
    )
    # Night Witch has no pause flag and produces through stun; Witch pauses.
    assert due.source_stable_id.tolist() == [[12, 0]]
    assert state.next_tick.tolist() == [[21, 120]]
    unstunned = step_periodic_spawns_(
        catalog,
        state,
        tick=21,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    assert unstunned.source_stable_id.tolist() == [[11, 0]]

    active[0, 0] = False
    step_periodic_spawns_(
        catalog,
        state,
        tick=30,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    assert int(state.source_stable_id[0, 0].cpu()) == 0
    assert int(state.blueprint_row[0, 0].cpu()) == -1
    assert int(state.next_tick[0, 0].cpu()) == 0

    # Reusing the physical slot with a new stable source starts a fresh clock.
    active[0, 0] = True
    stable[0, 0] = 99
    cards[0, 0] = ids["Tombstone"]
    reused = step_periodic_spawns_(
        catalog,
        state,
        tick=50,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    assert not bool(reused.ready.any())
    assert int(state.source_stable_id[0, 0].cpu()) == 99
    assert int(state.next_tick[0, 0].cpu()) == 120
    wave = step_periodic_spawns_(
        catalog,
        state,
        tick=120,
        active=active,
        source_stable_id=stable,
        source_card_id=cards,
    )
    assert wave.source_stable_id.tolist() == [[12, 99]]
    assert wave.count.tolist() == [[2, 2]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_periodic_scheduler_replays_exactly(device_name: str) -> None:
    catalog, ids = _catalog(device_name)
    left = FastPeriodicSpawnState.empty(2, 4, device=catalog.device)
    right = left.clone()
    active = torch.tensor(
        [[True, True, False, True], [True, False, True, True]],
        dtype=torch.bool,
        device=catalog.device,
    )
    stable = torch.tensor(
        [[40, 10, 0, 30], [8, 0, 5, 2]],
        dtype=torch.int64,
        device=catalog.device,
    )
    cards = torch.tensor(
        [
            [ids["Witch"], ids["NightWitch"], 0, ids["Tombstone"]],
            [ids["NightWitch"], 0, ids["Witch"], ids["Tombstone"]],
        ],
        dtype=torch.int64,
        device=catalog.device,
    )
    stunned = torch.zeros_like(active)
    for tick in (0, 20, 70, 120, 140, 160, 220):
        left_command = step_periodic_spawns_(
            catalog,
            left,
            tick=torch.tensor([tick, tick], device=catalog.device),
            active=active,
            source_stable_id=stable,
            source_card_id=cards,
            stunned=stunned,
        )
        right_command = step_periodic_spawns_(
            catalog,
            right,
            tick=torch.tensor([tick, tick], device=catalog.device),
            active=active,
            source_stable_id=stable,
            source_card_id=cards,
            stunned=stunned,
        )
        for descriptor in fields(left_command):
            assert torch.equal(
                getattr(left_command, descriptor.name),
                getattr(right_command, descriptor.name),
            )
    for descriptor in fields(left):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(left, descriptor.name), getattr(right, descriptor.name)
            )


def test_runtime_step_has_no_host_reads_or_dynamic_event_compaction() -> None:
    source = inspect.getsource(step_periodic_spawns_)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in ROOTS:
        assert card_name not in source

    catalog, ids = _catalog("cpu")
    periodic_rows = catalog.periodic_blueprint_by_card[
        torch.tensor([ids[name] for name in ROOTS])
    ]
    assert bool((periodic_rows >= 0).all())
    assert bool(catalog.row_supported[periodic_rows].all())
    assert catalog.count[periodic_rows].tolist() == [4, 2, 2]
    assert catalog.first_delay_ticks[periodic_rows].tolist() == [20, 20, 70]
    assert catalog.interval_ticks[periodic_rows].tolist() == [140, 100, 70]
