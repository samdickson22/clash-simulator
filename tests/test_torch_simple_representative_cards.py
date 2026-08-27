from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import FAST_STATUS_STUN
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep

ACCEPTANCE_CARDS = (
    "Knight",
    "Archers",
    "Giant",
    "Cannon",
    "Fireball",
    "Arrows",
    "BabyDragon",
    "Prince",
    "IceSpirit",
    "SkeletonArmy",
)


def _device(device_name: str) -> torch.device:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(device_name)


def _runtime(
    device_name: str,
    player_zero_card: str,
    player_one_card: str = "Knight",
    *,
    max_entities: int = 40,
) -> tuple[SimpleGymRuntime, dict[str, int]]:
    device = _device(device_name)
    loader = BattleState().card_loader
    full = TensorCardCatalog.compile(loader, ACCEPTANCE_CARDS, device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=loader)
    ids = {name: full.name_to_id[name] for name in ACCEPTANCE_CARDS}
    decks = torch.empty((1, 2, 8), dtype=torch.int64, device=device)
    decks[:, 0] = ids[player_zero_card]
    decks[:, 1] = ids[player_one_card]
    tower_spec = FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.tensor(
            [[20_000.0, 20_000.0, 30_000.0], [20_000.0, 20_000.0, 30_000.0]],
            device=device,
        ),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
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
        FastMatchRules(regulation_ticks=2_000, tiebreak_ticks=3_000),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=max_entities,
        max_effects=64,
        starting_elixir=10.0,
    )
    return runtime, ids


def _action(
    runtime: SimpleGymRuntime,
    *,
    tile: int = 14 * BOARD_WIDTH + 8,
    player_one: bool = False,
) -> torch.Tensor:
    return torch.tensor(
        [[tile, tile if player_one else NO_OP_ACTION]],
        dtype=torch.int64,
        device=runtime.device,
    )


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


def _assert_native(result: SimpleGymRuntimeStep) -> None:
    assert result.committed.tolist() == [True]
    assert result.native_ticks.tolist() == [1]


def _assert_replay_equal(
    first: SimpleGymRuntime,
    replay: SimpleGymRuntime,
    first_result: SimpleGymRuntimeStep,
    replay_result: SimpleGymRuntimeStep,
) -> None:
    for descriptor in fields(first.state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.state, descriptor.name),
                getattr(replay.state, descriptor.name),
            )
    assert torch.equal(first.action_state.hand_ids, replay.action_state.hand_ids)
    assert torch.equal(first.action_state.cycle_ids, replay.action_state.cycle_ids)
    assert torch.equal(first.effects.active, replay.effects.active)
    assert torch.equal(first.entity_status_ticks, replay.entity_status_ticks)
    assert torch.equal(first_result.action_success, replay_result.action_success)
    assert torch.equal(first_result.reward, replay_result.reward)
    assert torch.equal(
        first_result.observation.actor.entity_ids,
        replay_result.observation.actor.entity_ids,
    )
    torch.testing.assert_close(
        first_result.observation.actor.entity_features,
        replay_result.observation.actor.entity_features,
    )


def _seed_entity(
    runtime: SimpleGymRuntime,
    ids: dict[str, int],
    card_name: str,
    *,
    slot: int,
    owner: int,
    x_units: int,
    y_units: int,
    hp: float | None = None,
) -> None:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    card_id = ids[card_name]
    state.active[0, slot] = True
    state.stable_id[0, slot] = slot + 1
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), slot + 2)
    state.kind[0, slot] = catalog.kind[card_id]
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.x_units[0, slot] = x_units
    state.y_units[0, slot] = y_units
    state.hp[0, slot] = catalog.hitpoints[card_id] if hp is None else hp
    state.max_hp[0, slot] = state.hp[0, slot]
    state.damage[0, slot] = catalog.damage[card_id]
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = catalog.speed_units_per_tick[card_id]
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]
    state.cooldown_ticks[0, slot] = 0
    state.deploy_ticks[0, slot] = 0
    mask = torch.zeros_like(state.active)
    mask[0, slot] = True
    runtime._initialize_lifecycle_(mask)
    runtime._initialize_modifiers_(mask)


def _step_pair(
    first: SimpleGymRuntime,
    replay: SimpleGymRuntime,
    actions: torch.Tensor,
) -> tuple[SimpleGymRuntimeStep, SimpleGymRuntimeStep]:
    first_result = first.step_tick(actions)
    replay_result = replay.step_tick(actions)
    _assert_native(first_result)
    _assert_native(replay_result)
    _assert_replay_equal(first, replay, first_result, replay_result)
    return first_result, replay_result


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize("card_name", ACCEPTANCE_CARDS)
def test_representative_card_action_commits_projects_and_replays(
    device_name: str,
    card_name: str,
) -> None:
    """Every acceptance card crosses the actual action/runtime/projection seam."""

    first, ids = _runtime(device_name, card_name)
    replay, _ = _runtime(device_name, card_name)
    action = _action(first)
    first_result = first.step_tick(action)
    replay_result = replay.step_tick(action)

    _assert_native(first_result)
    _assert_native(replay_result)
    assert first_result.action_success.tolist() == [[True, True]]
    card_id = ids[card_name]
    catalog = first.action_kernel.catalog
    if int(catalog.kind[card_id]) >= 0:
        count = int(catalog.summon_count[card_id])
        card_slots = first.state.active & (first.state.card_id == card_id)
        assert int(card_slots.sum()) == count
        stable_ids = first.state.stable_id[card_slots]
        assert stable_ids.tolist() == list(range(7, 7 + count))
        assert first_result.observation.actor.entity_mask[0, :, 6 : 6 + count].all()
        kind = int(catalog.kind[card_id])
        expected_token = int(first.projector.inputs.entity_token_lookup[kind, card_id])
        assert (
            first_result.observation.actor.entity_ids[0, :, 6 : 6 + count]
            == expected_token
        ).all()
    else:
        assert bool(first_result.effect_allocation.accepted[0, 0])
        assert not bool((first.state.card_id == card_id).any())

    _assert_replay_equal(first, replay, first_result, replay_result)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_knight_direct_hit_and_giant_building_only_navigation(
    device_name: str,
) -> None:
    knight, ids = _runtime(device_name, "Knight")
    knight_replay, replay_ids = _runtime(device_name, "Knight")
    for runtime, runtime_ids in ((knight, ids), (knight_replay, replay_ids)):
        _seed_entity(
            runtime,
            runtime_ids,
            "Knight",
            slot=6,
            owner=0,
            x_units=9_000,
            y_units=14_000,
        )
        _seed_entity(
            runtime,
            runtime_ids,
            "Knight",
            slot=7,
            owner=1,
            x_units=9_000,
            y_units=15_500,
        )
    hp_before = knight.state.hp[0, 7].clone()
    result, _ = _step_pair(knight, knight_replay, _noop(knight))
    assert bool(result.effect_allocation.direct[0, 2 + 6])
    assert bool(result.effect_allocation.accepted[0, 2 + 6])
    assert knight.state.hp[0, 7] < hp_before
    assert not bool(knight.effects.active.any())
    assert result.observation.actor.entity_mask[0, :, 6:8].all()

    giant, ids = _runtime(device_name, "Giant")
    giant_replay, replay_ids = _runtime(device_name, "Giant")
    for runtime, runtime_ids in ((giant, ids), (giant_replay, replay_ids)):
        _seed_entity(
            runtime,
            runtime_ids,
            "Giant",
            slot=6,
            owner=0,
            x_units=9_000,
            y_units=10_000,
        )
        _seed_entity(
            runtime,
            runtime_ids,
            "Knight",
            slot=7,
            owner=1,
            x_units=9_000,
            y_units=10_500,
        )
    troop_hp = giant.state.hp[0, 7].clone()
    y_before = int(giant.state.y_units[0, 6])
    result, _ = _step_pair(giant, giant_replay, _noop(giant))
    # Slots 3--5 are the enemy Crown buildings; the nearby troop is slot 7.
    assert int(giant.state.target_id[0, 6]) in (4, 5, 6)
    assert int(giant.state.target_id[0, 6]) != 8
    # The fixture starts the Giant and Knight with deeply overlapping bodies.
    # Building-only acquisition remains correct, while the new mass-weighted
    # contact pass first increases physical separation instead of allowing the
    # Giant to phase forward through the troop.
    assert int(giant.state.y_units[0, 6]) != y_before
    assert abs(int(giant.state.y_units[0, 7]) - int(giant.state.y_units[0, 6])) > 500
    torch.testing.assert_close(giant.state.hp[0, 7], troop_hp)
    assert result.observation.actor.entity_mask[0, :, 6:8].all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("card_name", "second_target", "expected_radius"),
    (("Archers", None, 0), ("BabyDragon", "BabyDragon", 1_500)),
)
def test_representative_projectiles_travel_and_respect_target_planes(
    device_name: str,
    card_name: str,
    second_target: str | None,
    expected_radius: int,
) -> None:
    first, ids = _runtime(device_name, card_name)
    replay, replay_ids = _runtime(device_name, card_name)
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            runtime_ids,
            card_name,
            slot=6,
            owner=0,
            x_units=9_000,
            y_units=10_000,
        )
        _seed_entity(
            runtime,
            runtime_ids,
            "Knight",
            slot=7,
            owner=1,
            x_units=9_000,
            y_units=14_000,
            hp=5_000.0,
        )
        if second_target is not None:
            _seed_entity(
                runtime,
                runtime_ids,
                second_target,
                slot=8,
                owner=1,
                x_units=10_000,
                y_units=14_000,
                hp=5_000.0,
            )
        # Hold recipients in the splash fixture without installing an
        # unrelated pre-existing stun that would correctly outlast the hit.
        runtime.state.speed_units_per_tick[0, 7:9] = 0
    catalog = first.action_kernel.catalog
    card_id = ids[card_name]
    assert bool(catalog.attacks_ground[card_id])
    assert bool(catalog.attacks_air[card_id])
    hp_before = first.state.hp[0, 7:9].clone()

    launched, _ = _step_pair(first, replay, _noop(first))
    command = 2 + 6
    assert bool(launched.effect_allocation.projectile[0, command])
    assert bool(launched.effect_allocation.accepted[0, command])
    effect_slot = int(launched.effect_allocation.effect_slot[0, command])
    assert bool(first.effects.active[0, effect_slot])
    assert int(first.effects.radius_units[0, effect_slot]) == expected_radius

    impact = None
    for _ in range(12):
        result, _ = _step_pair(first, replay, _noop(first))
        if bool(result.effects.impacted[0, effect_slot]):
            impact = result
            break
    assert impact is not None
    assert first.state.hp[0, 7] < hp_before[0]
    if card_name == "BabyDragon":
        assert bool(catalog.is_air[card_id])
        assert first.state.hp[0, 8] < hp_before[1]
    assert impact.observation.actor.entity_mask[0, :, 6].all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_cannon_catalog_lifetime_expires_with_one_tick_tolerance(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name, "Cannon", max_entities=7)
    replay, _ = _runtime(device_name, "Cannon", max_entities=7)
    deployed, _ = _step_pair(first, replay, _action(first))
    assert deployed.action_success.tolist() == [[True, True]]
    cannon = ids["Cannon"]
    expected = int(first.action_kernel.catalog.lifetime_ticks[cannon])
    assert expected == 600
    assert int(first.lifecycle.lifetime_ticks[0, 6]) == expected - 1

    elapsed = 1
    while bool(first.state.active[0, 6]) and elapsed <= expected + 1:
        result, _ = _step_pair(first, replay, _noop(first))
        elapsed += 1
    assert abs(elapsed - expected) <= 1
    assert not bool(first.state.active[0, 6])
    assert not bool(result.observation.actor.entity_mask[0, :, 6].any())
    assert result.observation.legal_mask[:, :, :NO_OP_ACTION].any()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("spell_name", "travels", "damage", "tower_scale"),
    (("Fireball", True, 269.0, 0.25), ("Arrows", False, 144.0, 0.20)),
)
def test_representative_spells_area_timing_and_tower_scaling(
    device_name: str,
    spell_name: str,
    travels: bool,
    damage: float,
    tower_scale: float,
) -> None:
    first, ids = _runtime(device_name, spell_name)
    replay, replay_ids = _runtime(device_name, spell_name)
    target_tile = 25 * BOARD_WIDTH + 3
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            runtime_ids,
            "Knight",
            slot=6,
            owner=1,
            x_units=4_000,
            y_units=25_000,
            hp=5_000.0,
        )
        runtime.entity_status_ticks[0, 6] = 1_000
        runtime.entity_status_kind[0, 6] = FAST_STATUS_STUN
    tower_before = first.state.hp[0, 3].clone()
    troop_before = first.state.hp[0, 6].clone()

    cast, _ = _step_pair(
        first,
        replay,
        torch.tensor(
            [[target_tile, NO_OP_ACTION]], dtype=torch.int64, device=first.device
        ),
    )
    assert cast.action_success.tolist() == [[True, True]]
    assert bool(cast.effect_allocation.accepted[0, 0])
    assert bool(cast.effect_allocation.projectile[0, 0]) == travels
    assert bool(cast.effect_allocation.area[0, 0]) != travels
    if travels:
        assert bool(first.effects.active[0, 0])
        torch.testing.assert_close(first.state.hp[0, 6], troop_before)
        for _ in range(50):
            impact, _ = _step_pair(first, replay, _noop(first))
            if bool(impact.effects.impacted[0, 0]):
                break
        else:
            pytest.fail("Fireball did not impact within its calibrated travel window")
    else:
        assert bool(cast.effects.impacted[0, 0])
        assert not bool(first.effects.active[0, 0])

    torch.testing.assert_close(first.state.hp[0, 6], troop_before - damage)
    torch.testing.assert_close(
        first.state.hp[0, 3],
        tower_before - damage * tower_scale,
    )
    assert not bool(first.effects.active[0, 0])
    assert cast.observation.actor.entity_mask[0, :, 6].all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_prince_charge_speed_damage_and_reset(device_name: str) -> None:
    first, ids = _runtime(device_name, "Prince")
    replay, replay_ids = _runtime(device_name, "Prince")
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            runtime_ids,
            "Prince",
            slot=6,
            owner=0,
            x_units=9_000,
            y_units=10_000,
        )
        _seed_entity(
            runtime,
            runtime_ids,
            "Knight",
            slot=7,
            owner=1,
            x_units=9_000,
            y_units=15_000,
            hp=5_000.0,
        )
        runtime.entity_status_ticks[0, 7] = 1_000
        runtime.entity_status_kind[0, 7] = FAST_STATUS_STUN
    catalog = first.action_kernel.catalog
    prince = ids["Prince"]
    threshold = int(catalog.charge_threshold_distance_units[prince])
    assert threshold == 2_500

    for _ in range(42):
        result, _ = _step_pair(first, replay, _noop(first))
    assert bool(first.modifiers.charge_ready[0, 6])
    assert (
        abs(int(first.modifiers.charge_progress_distance_units[0, 6]) - threshold)
        <= 250
    )
    before_y = int(first.state.y_units[0, 6])
    result, _ = _step_pair(first, replay, _noop(first))
    charged_step = int(first.state.y_units[0, 6]) - before_y
    base_step = int(catalog.speed_units_per_tick[prince])
    assert abs(charged_step - 2 * base_step) <= 1

    before_hp = float(first.state.hp[0, 7])
    accepted = False
    for _ in range(20):
        result, _ = _step_pair(first, replay, _noop(first))
        if bool(result.effect_allocation.accepted[0, 2 + 6]):
            accepted = True
            break
    assert accepted
    charged_damage = float(catalog.effect_damage[prince]) * float(
        catalog.charge_ready_damage_multiplier[prince]
    )
    assert before_hp - float(first.state.hp[0, 7]) == pytest.approx(
        charged_damage, abs=1.0
    )
    assert not bool(first.modifiers.charge_ready[0, 6])
    assert int(first.modifiers.charge_progress_distance_units[0, 6]) == 0
    assert result.observation.actor.entity_mask[0, :, 6:8].all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_ice_spirit_homing_splash_freezes_and_consumes_source(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name, "IceSpirit")
    replay, replay_ids = _runtime(device_name, "IceSpirit")
    for runtime, runtime_ids in ((first, ids), (replay, replay_ids)):
        _seed_entity(
            runtime,
            runtime_ids,
            "IceSpirit",
            slot=6,
            owner=0,
            x_units=9_000,
            y_units=10_000,
        )
        _seed_entity(
            runtime,
            runtime_ids,
            "Knight",
            slot=7,
            owner=1,
            x_units=9_000,
            y_units=13_000,
            hp=5_000.0,
        )
        _seed_entity(
            runtime,
            runtime_ids,
            "BabyDragon",
            slot=8,
            owner=1,
            x_units=10_000,
            y_units=13_000,
            hp=5_000.0,
        )
        # Keep the intended splash recipients fixed without preloading a
        # stronger stun that would win the duration-max composition rule.
        runtime.state.speed_units_per_tick[0, 7:9] = 0
    catalog = first.action_kernel.catalog
    spirit = ids["IceSpirit"]
    assert bool(catalog.consume_source_on_impact[spirit])
    hp_before = first.state.hp[0, 7:9].clone()

    launched, _ = _step_pair(first, replay, _noop(first))
    command = 2 + 6
    assert bool(launched.effect_allocation.projectile[0, command])
    assert bool(launched.effect_allocation.accepted[0, command])
    effect_slot = int(launched.effect_allocation.effect_slot[0, command])
    assert int(first.effect_consume_source_id[0, effect_slot]) == 7

    for _ in range(12):
        impact, _ = _step_pair(first, replay, _noop(first))
        if bool(impact.effects.impacted[0, effect_slot]):
            break
    else:
        pytest.fail("Ice Spirit did not impact within its homing travel window")
    assert not bool(first.state.active[0, 6])
    assert first.state.hp[0, 7] < hp_before[0]
    assert first.state.hp[0, 8] < hp_before[1]
    expected_freeze = int(catalog.status_duration_ticks[spirit])
    assert first.entity_status_ticks[0, 7:9].tolist() == [expected_freeze] * 2
    assert not bool(impact.observation.actor.entity_mask[0, :, 6].any())
    assert impact.observation.actor.entity_mask[0, :, 7:9].all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_skeleton_army_capacity_fails_closed_without_partial_ids(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name, "SkeletonArmy", max_entities=20)
    replay, _ = _runtime(device_name, "SkeletonArmy", max_entities=20)
    before = first.observe()
    assert not bool(before.legal_mask[0, 0, :NO_OP_ACTION].any())
    assert bool(before.legal_mask[0, 0, NO_OP_ACTION])
    result, _ = _step_pair(first, replay, _action(first))
    assert result.action_success.tolist() == [[False, True]]
    assert not bool((first.state.card_id == ids["SkeletonArmy"]).any())
    assert int(first.state.next_stable_id[0]) == 7
    assert result.committed.tolist() == [True]
