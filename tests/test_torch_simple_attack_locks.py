from __future__ import annotations

import inspect
import json
from dataclasses import fields, replace
from pathlib import Path

import pytest
import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_attack_locks import (
    FastAttackLockState,
    FastAttackTimingCatalog,
    advance_fast_attack_lock_clocks_,
    commit_fast_attack_locks_,
    reset_fast_attack_locks_,
    step_fast_attack_locks_,
)
from clasher.torch_sim.simple_state import FAST_KIND_BUILDING, FastGymState
from clasher.torch_sim.simple_targeting import FastTargetTraits


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _enabled_names(loader: CardDataLoader) -> tuple[str, ...]:
    definitions = loader.load_card_definitions()
    decks = json.loads(Path("decks.json").read_text())["decks"]
    return tuple(
        sorted(
            {
                resolve_card_name(card, definitions)
                for deck in decks
                for card in deck["cards"]
            }
        )
    )


def _catalogs(
    device_name: str,
) -> tuple[CardDataLoader, TensorCardCatalog, FastAttackTimingCatalog]:
    device = _device(device_name)
    loader = CardDataLoader()
    catalog = TensorCardCatalog.compile(loader, _enabled_names(loader), device=device)
    return loader, catalog, FastAttackTimingCatalog.compile(catalog, loader)


def _combat_fixture(
    device_name: str,
    source_name: str,
    *,
    entities: int = 4,
) -> tuple[
    FastGymState,
    FastTargetTraits,
    FastAttackLockState,
    FastAttackTimingCatalog,
    TensorCardCatalog,
    torch.Tensor,
    torch.Tensor,
]:
    _, catalog, timings = _catalogs(device_name)
    state = FastGymState.empty(1, max_entities=entities, device=catalog.device)
    state.active[0] = True
    state.stable_id[0] = torch.arange(1, entities + 1, device=catalog.device)
    state.next_stable_id[0] = entities + 1
    state.owner[0] = torch.tensor([0, *([1] * (entities - 1))], device=catalog.device)
    state.card_id[0] = catalog.name_to_id["Knight"]
    state.card_id[0, 0] = catalog.name_to_id[source_name]
    state.hp[0] = 1_000
    state.max_hp[0] = 1_000
    state.damage[0, 0] = 100
    source_id = catalog.name_to_id[source_name]
    state.range_units[0, 0] = catalog.range_units[source_id]
    state.sight_range_units[0, 0] = catalog.sight_range_units[source_id]
    state.x_units[0] = torch.arange(entities, device=catalog.device) * 1_000
    traits = FastTargetTraits(
        airborne=torch.zeros_like(state.active),
        building=state.kind == FAST_KIND_BUILDING,
        attacks_air=torch.ones_like(state.active),
        attacks_ground=torch.ones_like(state.active),
        buildings_only=torch.zeros_like(state.active),
        collision_radius=torch.zeros_like(state.x_units),
    )
    locks = FastAttackLockState.empty(1, entities, device=catalog.device)
    return (
        state,
        traits,
        locks,
        timings,
        catalog,
        torch.zeros_like(state.active),
        torch.zeros_like(state.active),
    )


def _step(
    state: FastGymState,
    traits: FastTargetTraits,
    locks: FastAttackLockState,
    timings: FastAttackTimingCatalog,
    disabled: torch.Tensor,
    unavailable: torch.Tensor,
    *,
    decrement: int = 0,
    clear: torch.Tensor | None = None,
):
    return step_fast_attack_locks_(
        locks,
        timings,
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
        clear_source_lock=clear,
        cooldown_decrement=torch.full_like(state.cooldown_ticks, decrement),
    )


def test_enabled_card_timing_catalog_audits_all_66_serialized_rows() -> None:
    loader, catalog, timings = _catalogs("cpu")

    assert catalog.card_count == 66
    assert timings.size == 67
    for name in catalog.names[1:]:
        card_id = catalog.name_to_id[name]
        stats = loader.get_card(name)
        assert stats is not None
        hit_speed = int(stats.hit_speed or 0)
        load_time = int(stats.load_time or 0)
        first_hit = (
            hit_speed if load_time > hit_speed else max(0, hit_speed - load_time)
        )
        retarget = load_time - hit_speed if load_time > hit_speed else first_hit
        ceil_ticks = lambda value: (value + 49) // 50
        assert int(timings.hit_cycle_ticks[card_id]) == ceil_ticks(hit_speed)
        assert int(timings.serialized_load_ticks[card_id]) == ceil_ticks(load_time)
        assert int(timings.first_hit_delay_ticks[card_id]) == ceil_ticks(first_hit)
        assert int(timings.retarget_delay_ticks[card_id]) == ceil_ticks(retarget)
        assert bool(timings.load_first_hit[card_id]) is bool(stats.load_first_hit)

    expected = {
        "Knight": (24, 14, 10, 10),
        "Musketeer": (20, 6, 14, 14),
        "Giant": (30, 20, 10, 10),
        "InfernoDragon": (8, 24, 8, 16),
        "InfernoTower": (8, 24, 8, 16),
    }
    for name, values in expected.items():
        card_id = catalog.name_to_id[name]
        actual = (
            int(timings.hit_cycle_ticks[card_id]),
            int(timings.serialized_load_ticks[card_id]),
            int(timings.first_hit_delay_ticks[card_id]),
            int(timings.retarget_delay_ticks[card_id]),
        )
        assert actual == values


def test_distinct_load_first_hit_flag_is_compiled_without_timing_heuristic() -> None:
    loader = CardDataLoader()
    catalog = TensorCardCatalog.compile(loader, ["Knight"])
    stats = loader.get_card("Knight")
    assert stats is not None
    # Current enabled data has no LoadFirstHit weapons. Mutating this isolated
    # loader fixture proves the compiler consumes the explicit serialized bit
    # rather than inferring it from a nonzero load time.
    stats.load_first_hit = True
    timings = FastAttackTimingCatalog.compile(catalog, loader)
    card_id = catalog.name_to_id["Knight"]

    assert timings.load_first_hit[card_id]
    assert int(timings.serialized_load_ticks[card_id]) > 0


def test_timing_catalog_fails_closed_on_catalog_source_mismatch() -> None:
    loader = CardDataLoader()
    catalog = TensorCardCatalog.compile(loader, ["Knight"])
    malformed = catalog.load_time_ms.clone()
    malformed[catalog.name_to_id["Knight"]] += 1

    with pytest.raises(ValueError, match="loadTime mismatch"):
        FastAttackTimingCatalog.compile(
            replace(catalog, load_time_ms=malformed), loader
        )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_melee_first_hit_preload_and_effect_commit_cycle(device_name: str) -> None:
    state, traits, locks, timings, catalog, disabled, unavailable = _combat_fixture(
        device_name, "Knight", entities=2
    )
    state.x_units[0] = torch.tensor([0, 1_000], device=state.device)

    first = _step(state, traits, locks, timings, disabled, unavailable, decrement=1)
    knight = catalog.name_to_id["Knight"]
    assert int(first.cooldown_preload_floor_ticks[0, 0]) == 10
    assert int(first.cooldown_ticks[0, 0]) == 9
    assert first.acquired[0, 0]
    assert not first.attack_allowed[0, 0]

    latest = first
    for _ in range(9):
        state.tick.add_(1)
        latest = _step(
            state, traits, locks, timings, disabled, unavailable, decrement=1
        )
    assert latest.attack_allowed[0, 0]
    committed = commit_fast_attack_locks_(
        locks,
        timings,
        state,
        attack_allowed=latest.attack_allowed,
        effect_allocated=latest.attack_allowed,
    )
    assert committed[0, 0]
    assert int(locks.cooldown_ticks[0, 0]) == int(timings.hit_cycle_ticks[knight])


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_pending_body_is_lockable_but_pending_source_cannot_acquire(
    device_name: str,
) -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        device_name, "Knight", entities=2
    )
    state.x_units[0] = torch.tensor([0, 1_000], device=state.device)
    state.deploy_ticks[0, 1] = 10

    selected = _step(state, traits, locks, timings, disabled, unavailable)
    assert selected.target_stable_id[0, 0].item() == 2

    reset_fast_attack_locks_(
        locks, torch.ones(1, dtype=torch.bool, device=state.device)
    )
    state.deploy_ticks[0, 0] = 10
    blocked = _step(state, traits, locks, timings, disabled, unavailable)
    assert not blocked.target_found[0, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_split_seam_consumes_clock_against_post_movement_range(
    device_name: str,
) -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        device_name, "Knight", entities=2
    )
    state.x_units[0] = torch.tensor([0, 1_500], device=state.device)
    resolved = _step(state, traits, locks, timings, disabled, unavailable)
    assert resolved.target_found[0, 0]
    assert not resolved.target_in_attack_range[0, 0]
    assert int(locks.cooldown_ticks[0, 0]) == 10

    # The engine moves after resolving the lock and supplies its recomputed
    # post-movement range plane to the split clock seam.
    state.x_units[0, 0] = 300
    post_move_range = torch.zeros_like(state.active)
    post_move_range[0, 0] = True
    clock = advance_fast_attack_lock_clocks_(
        locks,
        timings,
        state,
        target_in_attack_range=post_move_range,
        source_disabled=disabled,
        cooldown_decrement=torch.ones_like(state.cooldown_ticks),
    )
    assert int(clock.cooldown_ticks[0, 0]) == 9
    assert not clock.attack_allowed[0, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_ranged_source_retains_valid_lock_when_nearer_enemy_arrives(
    device_name: str,
) -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        device_name, "Musketeer", entities=3
    )
    state.x_units[0] = torch.tensor([0, 3_000, 5_000], device=state.device)
    first = _step(state, traits, locks, timings, disabled, unavailable)
    assert int(first.target_stable_id[0, 0]) == 2

    state.tick.add_(1)
    state.x_units[0, 2] = 500
    retained = _step(state, traits, locks, timings, disabled, unavailable)

    assert int(retained.target_stable_id[0, 0]) == 2
    assert not retained.acquired[0, 0]
    assert not retained.switched[0, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_buildings_only_source_ignores_nearer_troop(device_name: str) -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        device_name, "Giant", entities=3
    )
    state.x_units[0] = torch.tensor([0, 500, 2_000], device=state.device)
    state.kind[0, 2] = FAST_KIND_BUILDING
    traits.building[0, 2] = True
    traits.buildings_only[0, 0] = True

    result = _step(state, traits, locks, timings, disabled, unavailable)

    assert int(result.target_stable_id[0, 0]) == 3
    assert int(result.target_slot[0, 0]) == 2


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_inferno_switch_installs_inverted_retarget_clock(device_name: str) -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        device_name, "InfernoDragon", entities=3
    )
    state.x_units[0] = torch.tensor([0, 1_000, 2_000], device=state.device)
    first = _step(state, traits, locks, timings, disabled, unavailable)
    assert int(first.cooldown_ticks[0, 0]) == 8
    assert int(first.target_stable_id[0, 0]) == 2

    state.tick.fill_(7)
    unavailable[0, 1] = True
    switched = _step(state, traits, locks, timings, disabled, unavailable)

    assert switched.switched[0, 0]
    assert int(switched.target_stable_id[0, 0]) == 3
    assert int(switched.cooldown_ticks[0, 0]) == 16
    assert int(locks.last_switch_tick[0, 0]) == 7


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_target_death_unavailable_and_out_of_sight_cancel_lock(
    device_name: str,
) -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        device_name, "Musketeer", entities=2
    )
    state.x_units[0] = torch.tensor([0, 5_000], device=state.device)
    assert _step(state, traits, locks, timings, disabled, unavailable).target_found[
        0, 0
    ]

    state.tick.fill_(1)
    state.x_units[0, 1] = 7_000
    out_of_sight = _step(state, traits, locks, timings, disabled, unavailable)
    assert out_of_sight.lost[0, 0]
    assert not out_of_sight.target_found[0, 0]

    state.tick.fill_(2)
    state.x_units[0, 1] = 5_000
    returned = _step(state, traits, locks, timings, disabled, unavailable)
    assert returned.acquired[0, 0]

    state.tick.fill_(3)
    unavailable[0, 1] = True
    hidden = _step(state, traits, locks, timings, disabled, unavailable)
    assert hidden.lost[0, 0]

    state.tick.fill_(4)
    unavailable[0, 1] = False
    state.hp[0, 1] = 0
    dead = _step(state, traits, locks, timings, disabled, unavailable)
    assert not dead.target_found[0, 0]
    assert int(locks.target_stable_id[0, 0]) == 0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_target_and_source_slot_reuse_are_stable_id_safe(device_name: str) -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        device_name, "Knight", entities=2
    )
    state.x_units[0] = torch.tensor([0, 1_000], device=state.device)
    first = _step(state, traits, locks, timings, disabled, unavailable)
    assert int(first.target_stable_id[0, 0]) == 2

    state.tick.fill_(8)
    state.stable_id[0, 1] = 9
    target_reused = _step(state, traits, locks, timings, disabled, unavailable)
    assert target_reused.switched[0, 0]
    assert int(target_reused.target_stable_id[0, 0]) == 9

    state.tick.fill_(9)
    state.stable_id[0, 0] = 10
    source_reused = _step(state, traits, locks, timings, disabled, unavailable)
    assert source_reused.acquired[0, 0]
    assert not source_reused.switched[0, 0]
    assert int(locks.source_stable_id[0, 0]) == 10
    assert int(locks.last_switch_tick[0, 0]) == -1


def test_explicit_row_reset_clears_only_selected_battle() -> None:
    locks = FastAttackLockState.empty(2, 3)
    for descriptor in fields(locks):
        if descriptor.name == "device":
            continue
        value = getattr(locks, descriptor.name)
        value.fill_(5)

    reset_fast_attack_locks_(locks, torch.tensor([True, False]))

    assert not locks.source_stable_id[0].any()
    assert locks.source_stable_id[1].eq(5).all()
    assert locks.last_acquire_tick[0].eq(-1).all()
    assert locks.last_acquire_tick[1].eq(5).all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_seedless_replay_is_exact_on_each_device(device_name: str) -> None:
    def replay() -> tuple[torch.Tensor, ...]:
        state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
            device_name, "Musketeer", entities=4
        )
        state.x_units[0] = torch.tensor([0, 4_000, 5_000, 6_000], device=state.device)
        snapshots: list[torch.Tensor] = []
        for tick in range(12):
            state.tick.fill_(tick)
            state.x_units[0, 1] += 300
            state.x_units[0, 2] -= 250
            unavailable[0, 1] = tick in (4, 5)
            if tick == 8:
                state.stable_id[0, 2] = 20
            result = _step(
                state,
                traits,
                locks,
                timings,
                disabled,
                unavailable,
                decrement=1,
            )
            snapshots.extend(
                (
                    result.target_stable_id.clone(),
                    result.cooldown_ticks.clone(),
                    result.attack_allowed.clone(),
                    result.acquired.clone(),
                    result.lost.clone(),
                    result.switched.clone(),
                )
            )
        snapshots.extend(
            (
                locks.source_stable_id.clone(),
                locks.last_acquire_tick.clone(),
                locks.last_loss_tick.clone(),
                locks.last_switch_tick.clone(),
            )
        )
        return tuple(snapshots)

    left = replay()
    right = replay()
    assert len(left) == len(right)
    assert all(torch.equal(a, b) for a, b in zip(left, right))


def test_hot_path_has_no_card_names_or_host_synchronization() -> None:
    source = inspect.getsource(step_fast_attack_locks_)

    for forbidden in (
        ".item(",
        ".cpu(",
        ".tolist(",
        ".numpy(",
        "nonzero(",
        "Knight",
        "Musketeer",
        "Giant",
        "Inferno",
    ):
        assert forbidden not in source


def test_runtime_planes_fail_closed_on_malformed_dtype() -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        "cpu", "Knight", entities=2
    )

    with pytest.raises(ValueError, match="cooldown_decrement must use"):
        step_fast_attack_locks_(
            locks,
            timings,
            state,
            traits,
            source_disabled=disabled,
            target_unavailable=unavailable,
            cooldown_decrement=torch.ones_like(state.hp),
        )


def test_duplicate_live_stable_ids_fail_closed() -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        "cpu", "Musketeer", entities=3
    )
    state.stable_id[0] = torch.tensor([1, 2, 2])
    state.x_units[0] = torch.tensor([0, 1_000, 2_000])

    result = _step(state, traits, locks, timings, disabled, unavailable)

    assert not result.target_found[0, 0]
    assert int(result.target_stable_id[0, 0]) == 0
