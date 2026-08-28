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
from clasher.torch_sim.simple_targeting import FastTargetTraits, select_nearest_targets


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


def _legacy_full_scan_step_reference(
    state: FastGymState,
    traits: FastTargetTraits,
    locks: FastAttackLockState,
    timings: FastAttackTimingCatalog,
    disabled: torch.Tensor,
    unavailable: torch.Tensor,
    clear: torch.Tensor,
    decrement: torch.Tensor,
) -> dict[str, torch.Tensor]:
    """Former O(E^2) retained-ID algorithm for valid-state parity tests."""

    safe_card = state.card_id.clamp(0, timings.size - 1)
    known_card = (state.card_id > 0) & (state.card_id < timings.size)
    body_present = state.active & (state.hp > 0) & (state.stable_id > 0)
    source_ready = body_present & (state.deploy_ticks == 0)
    identity_match = state.stable_id[:, :, None] == state.stable_id[:, None, :]
    unique_identity = (identity_match & body_present[:, None, :]).sum(dim=2) == 1
    supported = known_card & timings.ordinary_attack_supported[safe_card]
    source_present = source_ready & supported & unique_identity
    same_source = source_present & (locks.source_stable_id == state.stable_id)
    new_source = source_present & ~same_source
    previous_target_id = torch.where(
        same_source, locks.target_stable_id, torch.zeros_like(locks.target_stable_id)
    )
    cooldown = torch.where(
        new_source,
        timings.first_hit_delay_ticks[safe_card],
        torch.where(
            same_source,
            locks.cooldown_ticks.clamp(min=0),
            torch.zeros_like(locks.cooldown_ticks),
        ),
    )
    target_present = body_present & ~unavailable
    target_plane_allowed = torch.where(
        traits.airborne[:, None, :],
        traits.attacks_air[:, :, None],
        traits.attacks_ground[:, :, None],
    )
    target_category_allowed = (
        ~traits.buildings_only[:, :, None] | traits.building[:, None, :]
    )
    delta_x = state.x_units[:, :, None].to(torch.int64) - state.x_units[:, None, :].to(
        torch.int64
    )
    delta_y = state.y_units[:, :, None].to(torch.int64) - state.y_units[:, None, :].to(
        torch.int64
    )
    edge_distance = (
        torch.sqrt((delta_x.square() + delta_y.square()).to(torch.float32))
        - traits.collision_radius.clamp(min=0).to(torch.float32)[:, None, :]
    ).clamp_min(0.0)
    legal_target = (
        source_present[:, :, None]
        & target_present[:, None, :]
        & (state.owner[:, :, None] != state.owner[:, None, :])
        & target_plane_allowed
        & target_category_allowed
        & (edge_distance <= state.sight_range_units.clamp(min=0)[:, :, None])
    )
    retained_match = (
        (previous_target_id[:, :, None] > 0)
        & (previous_target_id[:, :, None] == state.stable_id[:, None, :])
        & legal_target
    )
    retained_valid = retained_match.sum(dim=2) == 1
    retained_slot = retained_match.to(torch.int64).argmax(dim=2)
    acquisition = select_nearest_targets(
        state,
        traits,
        source_disabled=(disabled | ~source_present | clear),
        target_unavailable=unavailable,
    )
    acquisition_identity_match = (
        (acquisition.target_id[:, :, None] > 0)
        & (acquisition.target_id[:, :, None] == state.stable_id[:, None, :])
        & target_present[:, None, :]
    )
    acquisition_found = acquisition.found & (acquisition_identity_match.sum(dim=2) == 1)
    use_retained = retained_valid & ~clear
    target_found = use_retained | (~use_retained & acquisition_found)
    target_slot = torch.where(
        use_retained,
        retained_slot,
        torch.where(acquisition_found, acquisition.target_slot, -1),
    )
    target_id = torch.where(
        use_retained,
        previous_target_id,
        torch.where(acquisition_found, acquisition.target_id, 0),
    )
    had_target = previous_target_id > 0
    has_target = target_id > 0
    switched = had_target & has_target & (previous_target_id != target_id)
    acquired = ~had_target & has_target
    lost = had_target & ~has_target
    cooldown = torch.where(
        lost | switched,
        torch.maximum(cooldown, timings.retarget_delay_ticks[safe_card]),
        cooldown,
    )
    selected_edge = edge_distance.gather(
        2, target_slot.clamp(min=0)[:, :, None]
    ).squeeze(2)
    in_range = target_found & (
        selected_edge <= state.range_units.clamp(min=0).to(torch.float32)
    )
    can_advance = source_present & ~disabled & ~clear
    decremented = (cooldown - decrement.clamp(min=0)).clamp(min=0)
    preload_floor = timings.first_hit_delay_ticks[safe_card]
    cooldown = torch.where(
        can_advance & (cooldown > 0),
        torch.where(
            in_range,
            decremented,
            torch.maximum(preload_floor, decremented),
        ),
        cooldown,
    )
    cooldown = torch.where(source_present, cooldown, 0)
    return {
        "target_found": target_found,
        "target_slot": target_slot,
        "target_stable_id": target_id,
        "target_in_attack_range": in_range,
        "attack_allowed": (
            can_advance & in_range & (cooldown == 0) & (state.damage > 0)
        ),
        "cooldown_ticks": cooldown,
        "acquired": acquired,
        "lost": lost,
        "switched": switched,
        "source_stable_id": torch.where(source_present, state.stable_id, 0),
    }


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
def test_slot_retention_matches_full_id_scan_on_random_valid_states(
    device_name: str,
) -> None:
    _, catalog, timings = _catalogs(device_name)
    device = catalog.device
    generator = torch.Generator().manual_seed(20260827)
    batch_size = 32
    entities = 12
    shape = (batch_size, entities)
    state = FastGymState.empty(batch_size, max_entities=entities, device=device)

    active = torch.rand(shape, generator=generator) > 0.12
    hp = torch.randint(0, 2_000, shape, generator=generator).to(torch.float32)
    stable_id = torch.arange(1, batch_size * entities + 1, dtype=torch.int64).view(
        shape
    )
    owner = torch.randint(0, 2, shape, generator=generator, dtype=torch.int8)
    card_choices = torch.tensor(
        [
            catalog.name_to_id["Knight"],
            catalog.name_to_id["Musketeer"],
            catalog.name_to_id["Giant"],
            catalog.name_to_id["InfernoDragon"],
        ],
        dtype=torch.int64,
    )
    card_id = card_choices[
        torch.randint(0, len(card_choices), shape, generator=generator)
    ]
    state.active.copy_(active.to(device))
    state.hp.copy_(hp.to(device))
    state.stable_id.copy_(stable_id.to(device))
    state.owner.copy_(owner.to(device))
    state.card_id.copy_(card_id.to(device))
    state.deploy_ticks.copy_(
        torch.randint(0, 3, shape, generator=generator, dtype=torch.int32).to(device)
    )
    state.x_units.copy_(
        torch.randint(0, 18_001, shape, generator=generator, dtype=torch.int32).to(
            device
        )
    )
    state.y_units.copy_(
        torch.randint(0, 32_001, shape, generator=generator, dtype=torch.int32).to(
            device
        )
    )
    state.sight_range_units.copy_(
        torch.randint(1_000, 12_001, shape, generator=generator, dtype=torch.int32).to(
            device
        )
    )
    state.range_units.copy_(
        torch.randint(0, 6_001, shape, generator=generator, dtype=torch.int32).to(
            device
        )
    )
    state.damage.fill_(100.0)

    building = (torch.rand(shape, generator=generator) < 0.25).to(device)
    traits = FastTargetTraits(
        airborne=(torch.rand(shape, generator=generator) < 0.2).to(device),
        building=building,
        attacks_air=(torch.rand(shape, generator=generator) > 0.25).to(device),
        attacks_ground=(torch.rand(shape, generator=generator) > 0.1).to(device),
        buildings_only=(torch.rand(shape, generator=generator) < 0.15).to(device),
        collision_radius=torch.randint(
            0, 1_001, shape, generator=generator, dtype=torch.int32
        ).to(device),
    )
    disabled = (torch.rand(shape, generator=generator) < 0.1).to(device)
    unavailable = (torch.rand(shape, generator=generator) < 0.1).to(device)
    clear = (torch.rand(shape, generator=generator) < 0.05).to(device)
    decrement = torch.randint(0, 3, shape, generator=generator, dtype=torch.int32).to(
        device
    )

    locks = FastAttackLockState.empty(batch_size, entities, device=device)
    same_source = (torch.rand(shape, generator=generator) > 0.25).to(device)
    locks.source_stable_id.copy_(torch.where(same_source, state.stable_id, 0))
    initial_slot = torch.randint(
        0, entities, shape, generator=generator, dtype=torch.int64
    ).to(device)
    initial_id = state.stable_id.gather(1, initial_slot)
    has_lock = (torch.rand(shape, generator=generator) > 0.35).to(device)
    locks.target_slot.copy_(torch.where(has_lock, initial_slot, -1))
    locks.target_stable_id.copy_(torch.where(has_lock, initial_id, 0))
    locks.cooldown_ticks.copy_(
        torch.randint(0, 31, shape, generator=generator, dtype=torch.int32).to(device)
    )
    before = locks.clone()
    expected = _legacy_full_scan_step_reference(
        state,
        traits,
        before,
        timings,
        disabled,
        unavailable,
        clear,
        decrement,
    )

    actual = step_fast_attack_locks_(
        locks,
        timings,
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
        clear_source_lock=clear,
        cooldown_decrement=decrement,
    )

    for name in (
        "target_found",
        "target_slot",
        "target_stable_id",
        "target_in_attack_range",
        "attack_allowed",
        "cooldown_ticks",
        "acquired",
        "lost",
        "switched",
    ):
        assert torch.equal(getattr(actual, name), expected[name]), name
    assert torch.equal(locks.source_stable_id, expected["source_stable_id"])
    expected_slot = torch.where(
        (expected["source_stable_id"] > 0) & expected["target_found"],
        expected["target_slot"],
        -1,
    )
    assert torch.equal(locks.target_slot, expected_slot)
    assert torch.equal(locks.target_stable_id, expected["target_stable_id"])
    assert torch.equal(locks.cooldown_ticks, expected["cooldown_ticks"])


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
    assert int(locks.target_slot[0, 0]) == 2
    assert int(switched.cooldown_ticks[0, 0]) == 16


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
    assert int(locks.target_slot[0, 0]) == -1
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
    assert int(locks.target_slot[0, 0]) == 1
    assert int(target_reused.target_stable_id[0, 0]) == 9

    state.tick.fill_(9)
    state.stable_id[0, 0] = 10
    source_reused = _step(state, traits, locks, timings, disabled, unavailable)
    assert source_reused.acquired[0, 0]
    assert not source_reused.switched[0, 0]
    assert int(locks.source_stable_id[0, 0]) == 10
    assert int(locks.target_slot[0, 0]) == 1


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
    assert locks.target_slot[0].eq(-1).all()
    assert locks.target_slot[1].eq(5).all()


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
                locks.target_slot.clone(),
                locks.target_stable_id.clone(),
                locks.cooldown_ticks.clone(),
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
    for removed_pairwise_scan in (
        "[:, :, None]",
        "[:, None, :]",
        ".sum(dim=2)",
        ".argmax(dim=2)",
    ):
        assert removed_pairwise_scan not in source


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


def test_duplicate_live_stable_ids_are_outside_production_state_contract() -> None:
    state, traits, locks, timings, _, disabled, unavailable = _combat_fixture(
        "cpu", "Musketeer", entities=3
    )
    state.stable_id[0] = torch.tensor([1, 2, 2])
    state.x_units[0] = torch.tensor([0, 1_000, 2_000])

    result = _step(state, traits, locks, timings, disabled, unavailable)

    # FastGymState's allocator guarantees unique positive generations. The
    # production lock therefore need not pay an O(E^2) uniqueness scan for a
    # malformed state; deterministic nearest-slot acquisition remains defined.
    assert result.target_found[0, 0]
    assert int(result.target_slot[0, 0]) == 1
    assert int(result.target_stable_id[0, 0]) == 2
