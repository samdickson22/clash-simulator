from __future__ import annotations

import inspect

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import (
    FAST_CARD_EFFECT_AREA,
    FAST_CARD_EFFECT_UNSUPPORTED,
    FastCardCatalog,
)
from clasher.torch_sim.simple_effects import (
    FAST_EFFECT_AREA,
    FAST_STATUS_SLOW,
    FAST_STATUS_STUN,
    step_fast_effects,
)
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_state import FAST_KIND_BUILDING, FAST_KIND_TROOP


def _device(request: pytest.FixtureRequest) -> torch.device:
    name = str(request.param)
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> torch.device:
    return _device(request)


def _runtime(
    spell_name: str, device: torch.device
) -> tuple[SimpleGymRuntime, FastCardCatalog, dict[str, int]]:
    battle = BattleState()
    names = [spell_name, "Knight", "Minions"]
    full = TensorCardCatalog.compile(battle.card_loader, names, device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    ids = full.name_to_id
    deck = torch.stack(
        (
            torch.full((8,), ids[spell_name], dtype=torch.int64, device=device),
            torch.full((8,), ids["Knight"], dtype=torch.int64, device=device),
        )
    ).unsqueeze(0)
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), ids["Knight"], dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.tensor(
            [[2_000.0, 2_000.0, 3_000.0], [2_000.0, 2_000.0, 3_000.0]],
            device=device,
        ),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    size = catalog.size
    return (
        SimpleGymRuntime(
            deck,
            catalog,
            tower_spec,
            FastMatchRules(regulation_ticks=400, tiebreak_ticks=600),
            entity_token_lookup=torch.zeros(
                (2, size), dtype=torch.int64, device=device
            ),
            hand_token_lookup=torch.arange(size, dtype=torch.int64, device=device),
            max_entities=12,
            starting_elixir=10.0,
        ),
        catalog,
        ids,
    )


def _add_target(
    runtime: SimpleGymRuntime,
    *,
    slot: int,
    card_id: int,
    kind: int = FAST_KIND_TROOP,
    x: int = 4_000,
    y: int = 25_000,
) -> None:
    state = runtime.state
    state.active[0, slot] = True
    state.stable_id[0, slot] = slot + 1
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), slot + 2)
    state.kind[0, slot] = kind
    state.owner[0, slot] = 1
    state.card_id[0, slot] = card_id
    state.x_units[0, slot] = x
    state.y_units[0, slot] = y
    state.hp[0, slot] = 2_000.0
    state.max_hp[0, slot] = 2_000.0


def _cast(runtime: SimpleGymRuntime) -> torch.Tensor:
    target_tile = 25 * BOARD_WIDTH + 3
    action = torch.tensor([[target_tile, NO_OP_ACTION]], device=runtime.device)
    result = runtime.step_tick(action)
    assert result.action_success.tolist() == [[True, True]]
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


def _install_serialized_status_effect(
    runtime: SimpleGymRuntime,
    catalog: FastCardCatalog,
    *,
    source_card_id: int,
    target_slot: int = 6,
) -> None:
    """Queue one catalog-backed status through the complete runtime tick."""

    effect = runtime.effects
    effect.active[0, 0] = True
    effect.kind[0, 0] = FAST_EFFECT_AREA
    effect.source_owner[0, 0] = 0
    effect.source_card_id[0, 0] = source_card_id
    effect.x_units[0, 0] = runtime.state.x_units[0, target_slot]
    effect.y_units[0, 0] = runtime.state.y_units[0, target_slot]
    effect.radius_units[0, 0] = 1_000
    effect.status_kind[0, 0] = catalog.status_kind[source_card_id]
    effect.status_duration_ticks[0, 0] = catalog.status_duration_ticks[source_card_id]
    effect.lifetime_ticks[0, 0] = 1
    effect.damage_hits_remaining[0, 0] = 1
    effect.status_scans_remaining[0, 0] = 1
    effect.next_damage_tick[0, 0] = 0
    effect.next_status_tick[0, 0] = 0
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    runtime.step_tick(noop)


def _initialize_moving_knight(
    runtime: SimpleGymRuntime,
    catalog: FastCardCatalog,
    knight: int,
) -> None:
    _add_target(runtime, slot=6, card_id=knight, x=3_500, y=20_000)
    state = runtime.state
    state.speed_units_per_tick[0, 6] = catalog.speed_units_per_tick[knight]
    state.damage[0, 6] = catalog.damage[knight]
    state.range_units[0, 6] = catalog.range_units[knight]
    state.sight_range_units[0, 6] = catalog.sight_range_units[knight]
    state.hit_cooldown_ticks[0, 6] = catalog.hit_cooldown_ticks[knight]


def test_periodic_area_catalog_admits_only_truthful_primitives() -> None:
    battle = BattleState()
    names = (
        "Earthquake",
        "Freeze",
        "Poison",
        "Tornado",
        "Zap",
        "Snowball",
        "IceWizard",
        "Graveyard",
        "RoyalDelivery",
    )
    full = TensorCardCatalog.compile(battle.card_loader, names)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)

    for name in ("Earthquake", "Freeze", "Poison", "Tornado", "Zap"):
        card = full.name_to_id[name]
        assert int(catalog.effect_kind[card]) == FAST_CARD_EFFECT_AREA
        assert bool(catalog.training_supported[card])
    for name in ("Graveyard", "RoyalDelivery"):
        card = full.name_to_id[name]
        assert int(catalog.effect_kind[card]) == FAST_CARD_EFFECT_UNSUPPORTED
        assert not bool(catalog.training_supported[card])

    earthquake = full.name_to_id["Earthquake"]
    freeze = full.name_to_id["Freeze"]
    poison = full.name_to_id["Poison"]
    tornado = full.name_to_id["Tornado"]
    assert catalog.max_damage_hits[[earthquake, poison]].tolist() == [3, 0]
    assert bool(catalog.target_local_damage[poison])
    assert int(catalog.periodic_buff_duration_ticks[poison]) == 20
    assert int(catalog.status_kind[earthquake]) == FAST_STATUS_SLOW
    assert int(catalog.status_kind[freeze]) == FAST_STATUS_STUN
    assert int(catalog.max_status_scans[freeze]) == 1
    assert bool(catalog.damage_on_spawn[freeze])
    assert not bool(catalog.damage_on_spawn[poison])
    assert not bool(catalog.hits_air[earthquake])
    assert bool(catalog.omits_displacement[tornado])

    snowball = full.name_to_id["Snowball"]
    ice_wizard = full.name_to_id["IceWizard"]
    assert int(catalog.status_kind[poison]) == FAST_STATUS_SLOW
    assert int(catalog.status_kind[snowball]) == FAST_STATUS_SLOW
    assert int(catalog.status_kind[ice_wizard]) == FAST_STATUS_SLOW
    assert catalog.slow_movement_multiplier[
        [earthquake, poison, snowball, ice_wizard]
    ].tolist() == pytest.approx([0.50, 0.85, 0.70, 0.70])
    assert catalog.slow_attack_multiplier[
        [earthquake, poison, snowball, ice_wizard]
    ].tolist() == pytest.approx([1.0, 1.0, 0.70, 0.70])


def test_poison_uses_serialized_periodic_cadence_and_tower_scale(
    tensor_device: torch.device,
) -> None:
    runtime, _, ids = _runtime("Poison", tensor_device)
    _add_target(runtime, slot=6, card_id=ids["Knight"])
    noop = _cast(runtime)
    tower_before = 2_000.0
    troop_before = 2_000.0

    for _ in range(23):
        runtime.step_tick(noop)
    assert float(runtime.state.hp[0, 3]) == tower_before
    assert float(runtime.state.hp[0, 6]) == troop_before
    runtime.step_tick(noop)
    assert float(runtime.state.hp[0, 3]) == pytest.approx(tower_before - 21.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(troop_before - 92.0)

    for _ in range(140):
        runtime.step_tick(noop)
    assert float(runtime.state.hp[0, 3]) == pytest.approx(tower_before - 8 * 21.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(troop_before - 8 * 92.0)
    assert not bool(runtime.effects.active.any())


def test_earthquake_scales_buildings_and_respects_ground_plane(
    tensor_device: torch.device,
) -> None:
    runtime, _, ids = _runtime("Earthquake", tensor_device)
    _add_target(runtime, slot=6, card_id=ids["Knight"], kind=FAST_KIND_BUILDING)
    _add_target(runtime, slot=7, card_id=ids["Minions"])
    noop = _cast(runtime)
    for _ in range(59):
        runtime.step_tick(noop)

    assert float(runtime.state.hp[0, 3]) == pytest.approx(2_000.0 - 3 * 49.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(2_000.0 - 3 * 287.0)
    assert float(runtime.state.hp[0, 7]) == 2_000.0
    assert not bool(runtime.effects.active.any())


def test_freeze_is_one_shot_damage_and_status_snapshot(
    tensor_device: torch.device,
) -> None:
    runtime, _, ids = _runtime("Freeze", tensor_device)
    _add_target(runtime, slot=6, card_id=ids["Knight"])
    noop = _cast(runtime)

    assert float(runtime.state.hp[0, 3]) == pytest.approx(2_000.0 - 37.0)
    assert float(runtime.state.hp[0, 6]) == pytest.approx(2_000.0 - 148.0)
    assert int(runtime.entity_status_kind[0, 6]) == FAST_STATUS_STUN
    assert int(runtime.entity_status_ticks[0, 6]) == 80
    _add_target(runtime, slot=7, card_id=ids["Knight"])
    for _ in range(79):
        runtime.step_tick(noop)

    assert float(runtime.state.hp[0, 6]) == pytest.approx(2_000.0 - 148.0)
    assert int(runtime.entity_status_kind[0, 7]) == 0
    assert int(runtime.entity_status_ticks[0, 7]) == 0
    assert not bool(runtime.effects.active.any())


def test_zap_runtime_is_legal_and_deterministic() -> None:
    left, _, left_ids = _runtime("Zap", torch.device("cpu"))
    right, _, right_ids = _runtime("Zap", torch.device("cpu"))
    _add_target(left, slot=6, card_id=left_ids["Knight"])
    _add_target(right, slot=6, card_id=right_ids["Knight"])
    assert bool(left.observe().legal_mask[0, 0, 25 * BOARD_WIDTH + 3])
    _cast(left)
    _cast(right)

    for name in ("active", "hp", "stable_id", "tick"):
        torch.testing.assert_close(
            getattr(left.state, name), getattr(right.state, name)
        )
    torch.testing.assert_close(left.entity_status_ticks, right.entity_status_ticks)
    assert float(left.state.hp[0, 6]) == pytest.approx(2_000.0 - 192.0)
    assert int(left.entity_status_ticks[0, 6]) == 10


@pytest.mark.parametrize(
    ("source_name", "movement_multiplier", "attack_multiplier"),
    (
        ("Earthquake", 0.50, 1.0),
        ("Poison", 0.85, 1.0),
        ("Snowball", 0.70, 0.70),
        ("IceWizard", 0.70, 0.70),
    ),
)
def test_serialized_slow_scales_movement_and_attack_clock_without_disabling(
    tensor_device: torch.device,
    source_name: str,
    movement_multiplier: float,
    attack_multiplier: float,
) -> None:
    runtime, catalog, ids = _runtime(source_name, tensor_device)
    knight = ids["Knight"]
    source = ids[source_name]
    _initialize_moving_knight(runtime, catalog, knight)
    _install_serialized_status_effect(
        runtime,
        catalog,
        source_card_id=source,
    )

    assert int(runtime.entity_status_kind[0, 6]) == FAST_STATUS_SLOW
    assert int(runtime.entity_slow_ticks[0, 6, source]) == int(
        catalog.status_duration_ticks[source]
    )
    runtime.state.x_units[0, 6] = 3_500
    runtime.state.y_units[0, 6] = 20_000
    runtime.state.cooldown_ticks[0, 6] = 20
    runtime.entity_attack_clock_fraction[0, 6] = 0.0
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    for _ in range(10):
        runtime.step_tick(noop)

    base_speed = int(catalog.speed_units_per_tick[knight])
    expected_travel = round(base_speed * movement_multiplier) * 10
    assert int(runtime.state.y_units[0, 6]) == 20_000 - expected_travel
    assert int(runtime.state.cooldown_ticks[0, 6]) == 20 - round(10 * attack_multiplier)
    assert int(runtime.state.target_id[0, 6]) > 0


def test_stun_disables_while_slow_remains_compositionally_timed(
    tensor_device: torch.device,
) -> None:
    runtime, catalog, ids = _runtime("Freeze", tensor_device)
    knight = ids["Knight"]
    freeze = ids["Freeze"]
    _initialize_moving_knight(runtime, catalog, knight)
    _install_serialized_status_effect(
        runtime,
        catalog,
        source_card_id=freeze,
    )
    runtime.state.x_units[0, 6] = 3_500
    runtime.state.y_units[0, 6] = 20_000
    runtime.state.cooldown_ticks[0, 6] = 20
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)

    for _ in range(3):
        runtime.step_tick(noop)

    assert int(runtime.entity_status_kind[0, 6]) == FAST_STATUS_STUN
    assert int(runtime.state.y_units[0, 6]) == 20_000
    assert int(runtime.state.cooldown_ticks[0, 6]) == 20
    assert int(runtime.state.target_id[0, 6]) == 0


def test_overlapping_slow_sources_reveal_weaker_remainder_after_stronger_expires(
    tensor_device: torch.device,
) -> None:
    # This fixture compiles only one spell. Build the second serialized source
    # into one catalog so source-card keyed status planes remain authoritative.
    battle = BattleState()
    full = TensorCardCatalog.compile(
        battle.card_loader,
        ["Earthquake", "Poison", "Knight", "Minions"],
        device=tensor_device,
    )
    combined = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    # Runtime tensor dimensions must match the catalog that supplies source IDs.
    # Construct the equivalent runtime directly from the combined deck tables.
    deck = torch.stack(
        (
            torch.full((8,), full.name_to_id["Earthquake"], device=tensor_device),
            torch.full((8,), full.name_to_id["Knight"], device=tensor_device),
        )
    ).unsqueeze(0)
    runtime = SimpleGymRuntime(
        deck,
        combined,
        FastTowerSpec(
            card_id=torch.full((2, 3), full.name_to_id["Knight"], device=tensor_device),
            x_units=torch.tensor(
                [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]],
                device=tensor_device,
            ),
            y_units=torch.tensor(
                [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]],
                device=tensor_device,
            ),
            hitpoints=torch.full((2, 3), 2_000.0, device=tensor_device),
            damage=torch.zeros((2, 3), device=tensor_device),
            range_units=torch.full((2, 3), 7_500, device=tensor_device),
            sight_range_units=torch.full((2, 3), 9_500, device=tensor_device),
            hit_cooldown_ticks=torch.full(
                (2, 3), 16, dtype=torch.int32, device=tensor_device
            ),
        ),
        FastMatchRules(regulation_ticks=400, tiebreak_ticks=600),
        entity_token_lookup=torch.zeros(
            (2, combined.size), dtype=torch.int64, device=tensor_device
        ),
        hand_token_lookup=torch.arange(
            combined.size, dtype=torch.int64, device=tensor_device
        ),
        max_entities=12,
        starting_elixir=10.0,
    )
    knight = full.name_to_id["Knight"]
    earthquake = full.name_to_id["Earthquake"]
    poison = full.name_to_id["Poison"]
    _initialize_moving_knight(runtime, combined, knight)
    _install_serialized_status_effect(runtime, combined, source_card_id=earthquake)
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=tensor_device)
    for _ in range(5):
        runtime.step_tick(noop)
    _install_serialized_status_effect(runtime, combined, source_card_id=poison)

    # A stun overlays action gating but does not discard either independently
    # timed slow. Both clocks continue, then the aggregate view reveals slow.
    runtime.entity_status_kind[0, 6] = FAST_STATUS_STUN
    runtime.entity_status_ticks[0, 6] = 2
    before_y = runtime.state.y_units[0, 6].clone()
    runtime.state.cooldown_ticks[0, 6] = 10
    runtime.step_tick(noop)
    assert torch.equal(runtime.state.y_units[0, 6], before_y)
    assert int(runtime.state.cooldown_ticks[0, 6]) == 10
    runtime.step_tick(noop)
    assert int(runtime.entity_status_kind[0, 6]) == FAST_STATUS_SLOW

    for _ in range(12):
        runtime.step_tick(noop)
    movement, attack = runtime._slow_multipliers()
    assert int(runtime.entity_slow_ticks[0, 6, earthquake]) == 0
    assert int(runtime.entity_slow_ticks[0, 6, poison]) == 6
    assert float(movement[0, 6]) == pytest.approx(0.85)
    assert float(attack[0, 6]) == 1.0
    assert int(runtime.entity_status_kind[0, 6]) == FAST_STATUS_SLOW

    for _ in range(6):
        runtime.step_tick(noop)
    assert int(runtime.entity_status_kind[0, 6]) == 0
    assert not bool(runtime.entity_slow_ticks[0, 6].any())


def test_slow_runtime_replay_and_selective_reset_are_exact() -> None:
    left, left_catalog, left_ids = _runtime("Poison", torch.device("cpu"))
    right, right_catalog, right_ids = _runtime("Poison", torch.device("cpu"))
    for runtime, catalog, ids in (
        (left, left_catalog, left_ids),
        (right, right_catalog, right_ids),
    ):
        _initialize_moving_knight(runtime, catalog, ids["Knight"])
        _install_serialized_status_effect(
            runtime,
            catalog,
            source_card_id=ids["Poison"],
        )
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64)
    for _ in range(12):
        left.step_tick(noop)
        right.step_tick(noop)

    assert torch.equal(left.state.x_units, right.state.x_units)
    assert torch.equal(left.state.y_units, right.state.y_units)
    assert torch.equal(left.entity_status_kind, right.entity_status_kind)
    assert torch.equal(left.entity_status_ticks, right.entity_status_ticks)
    assert torch.equal(left.entity_slow_ticks, right.entity_slow_ticks)
    assert torch.equal(
        left.entity_attack_clock_fraction,
        right.entity_attack_clock_fraction,
    )

    left.state.hp[0, 6] = 0.0
    left.step_tick(noop)
    assert not bool(left.entity_slow_ticks[0, 6].any())
    assert int(left.entity_status_ticks[0, 6]) == 0

    left.reset_rows(torch.tensor([True]))
    assert not bool(left.entity_slow_ticks.any())
    assert not bool(left.entity_status_ticks.any())
    assert not bool(left.entity_attack_clock_fraction.any())


def test_status_hot_paths_have_no_host_sync_or_card_name_dispatch() -> None:
    source = "\n".join(
        (
            inspect.getsource(step_fast_effects),
            inspect.getsource(SimpleGymRuntime._slow_multipliers),
            inspect.getsource(SimpleGymRuntime._attack_clock_decrement_),
        )
    )
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in ("Earthquake", "Poison", "Snowball", "IceWizard"):
        assert card_name not in source
