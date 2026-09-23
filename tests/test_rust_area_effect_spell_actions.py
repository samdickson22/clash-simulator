from __future__ import annotations

import json
import random
from collections import deque
from dataclasses import replace

import numpy as np
import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot
from clasher.entities import (
    AreaEffect,
    Building,
    PeriodicDamageEffect,
    SpawnProjectile,
    Troop,
)
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_DELTA_CONSUMER,
    _PREPARED_PUBLICATION_RAW_CONSUMER,
    ResidentRustBattle,
    RustBattleMode,
    rust_core_available,
)
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    _build_direct_delta_publication_plan,
    _build_direct_publication_plan,
    _typed_publication_projection,
    publish_complete_tick_state,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime, _causal_boundary_snapshot
from clasher.spells import SPELL_REGISTRY, SpawnProjectileSpell

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _set_earthquake_hand(battle: BattleState) -> None:
    for player in battle.players:
        player.hand = ["Earthquake", "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir


def _set_freeze_hand(battle: BattleState) -> None:
    for player in battle.players:
        player.hand = ["Freeze", "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir


def _set_poison_hand(battle: BattleState) -> None:
    for player in battle.players:
        player.hand = ["Poison", "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir


def _finish_deploy(entity: Troop) -> None:
    entity.deploy_delay_remaining = 0.0
    entity.placement_delay_total = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True


def _spawn_ready_building(
    battle: BattleState, card_name: str, position: Position
) -> Building:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    entity = battle._spawn_entity(Building, position, 1, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_delay_total = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _earthquake_battle(seed: int, *, dt: float = 0.05) -> BattleState:
    battle = BattleState(rng=random.Random(seed), dt=dt, fast_path=True)
    _set_earthquake_hand(battle)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.5, 16.5), 1, stats)
    _finish_deploy(target)
    target.apply_stun(20.0)
    return battle


def _actions() -> tuple[int, int]:
    action_space = DiscreteTileActionSpace()
    return (
        action_space.encode_action(0, 9, 16, 0),
        action_space.no_op_action,
    )


def _freeze_battle(seed: int, *, dt: float = 0.05) -> tuple[BattleState, Troop]:
    battle = BattleState(rng=random.Random(seed), dt=dt, fast_path=True)
    _set_freeze_hand(battle)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.5, 16.5), 1, stats)
    _finish_deploy(target)
    return battle, target


def _poison_battle(seed: int, *, dt: float = 0.05) -> tuple[BattleState, Troop]:
    battle = BattleState(rng=random.Random(seed), dt=dt, fast_path=True)
    _set_poison_hand(battle)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.5, 16.5), 1, stats)
    _finish_deploy(target)
    target.apply_stun(30.0)
    return battle, target


def _apply_python_actions(
    battle: BattleState, actions: tuple[int, int]
) -> tuple[dict[int, bool], tuple[int, int]]:
    action_space = DiscreteTileActionSpace()
    order = [0, 1]
    battle.rng.shuffle(order)
    success = {
        player_id: action_space.apply_action(
            battle, player_id, actions[player_id]
        )
        for player_id in order
    }
    return success, (order[0], order[1])


def _assert_semantic_parity(
    battle: BattleState, resident: ResidentRustBattle
) -> None:
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(battle)
    )


@pytest.mark.parametrize(
    ("spell_name", "child_name", "expected_children"),
    [
        ("GoblinBarrel", "Goblin", 3),
        ("RoyalDelivery", "DeliveryRecruit", 1),
    ],
)
def test_freeze_snapshot_skips_spawn_projectile_carriers_and_later_children(
    spell_name: str,
    child_name: str,
    expected_children: int,
) -> None:
    battle = BattleState(rng=random.Random(190_001), fast_path=True)
    spell = SPELL_REGISTRY[spell_name]
    if spell_name == "GoblinBarrel":
        assert isinstance(spell, SpawnProjectileSpell)
        target = spell._get_launch_position(battle, 1)
    else:
        target = Position(9.0, 16.0)
    assert SPELL_REGISTRY["Freeze"].cast(battle, 0, target)
    carrier_id = battle.next_entity_id
    assert spell.cast(battle, 1, target)
    carrier = battle.entities[carrier_id]
    assert type(carrier) is SpawnProjectile
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(90):
        battle._step_logic_tick(refresh_fast_path_end=False)
        assert resident.advance_complete_tick()
        _assert_semantic_parity(battle, resident)
        assert carrier.freeze_expiry_time == 0.0
        children = [
            entity
            for entity in battle.entities.values()
            if type(entity) is Troop and str(entity.card_stats.name) == child_name
        ]
        if not children:
            continue
        assert len(children) == expected_children
        assert all(child.freeze_expiry_time == 0.0 for child in children)
        assert all(child.stun_timer == 0.0 for child in children)
        assert all(child.slow_timer == 0.0 for child in children)
        break
    else:  # pragma: no cover - fixture invariant
        raise AssertionError("spawn-projectile carrier did not create children")


def test_area_effect_catalog_structurally_qualifies_shared_clock_families() -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    area_cards = {
        card["lookup_name"]: card
        for card in payload["cards"]
        if card["action_kind"] == "area_effect_spell"
    }
    resident = ResidentRustBattle.from_battle(battle)

    assert payload["schema_version"] == 19
    assert {
        name
        for name, card in area_cards.items()
        if not card["capability_reasons"]
    } == {"Earthquake", "Freeze", "Poison"}
    assert "nested_area_effect_payload" in area_cards["Lightning"][
        "capability_reasons"
    ]
    earthquake = area_cards["Earthquake"]["area_effect_spell"]
    assert earthquake == {
        "affects_hidden": True,
        "attack_speed_multiplier": None,
        "building_damage": 287.0,
        "building_damage_multiplier": 3.5,
        "cap_buff_time_to_effect": True,
        "clock_kind": "source_periodic",
        "crown_tower_damage": 49.0,
        "crown_tower_damage_multiplier": 0.6,
        "damage": 84.0,
        "damage_on_spawn": False,
        "damage_tick_interval": 1.0,
        "duration": 3.0,
        "effect_tick_interval": 0.1,
        "freeze_effect": False,
        "hits_air": False,
        "hits_ground": True,
        "max_damage_ticks": 3,
        "movement_multiplier": 0.5,
        "periodic_damage_buff_duration": 1.0,
        "periodic_damage_controlled_by_parent": False,
        "radius": 3.5,
        "slow_refresh_duration": 1.0,
        "slows_attack_speed": False,
        "slows_spawn_speed": False,
        "spawn_speed_multiplier": None,
        "target_local_damage": False,
    }
    assert area_cards["Freeze"]["area_effect_spell"] == {
        "affects_hidden": True,
        "attack_speed_multiplier": None,
        "building_damage": None,
        "building_damage_multiplier": 1.0,
        "cap_buff_time_to_effect": False,
        "clock_kind": "freeze_snapshot",
        "crown_tower_damage": 37.0,
        "crown_tower_damage_multiplier": 0.25,
        "damage": 148.0,
        "damage_on_spawn": True,
        "damage_tick_interval": 0.0,
        "duration": 4.0,
        "effect_tick_interval": 0.05,
        "freeze_effect": True,
        "hits_air": True,
        "hits_ground": True,
        "max_damage_ticks": 1,
        "movement_multiplier": 0.0,
        "periodic_damage_buff_duration": 0.0,
        "periodic_damage_controlled_by_parent": False,
        "radius": 3.0,
        "slow_refresh_duration": 0.25,
        "slows_attack_speed": True,
        "slows_spawn_speed": True,
        "spawn_speed_multiplier": None,
        "target_local_damage": False,
    }
    assert area_cards["Poison"]["area_effect_spell"] == {
        "affects_hidden": False,
        "attack_speed_multiplier": None,
        "building_damage": 92.0,
        "building_damage_multiplier": 1.0,
        "cap_buff_time_to_effect": False,
        "clock_kind": "target_periodic",
        "crown_tower_damage": 21.0,
        "crown_tower_damage_multiplier": 0.22999999999999998,
        "damage": 92.0,
        "damage_on_spawn": False,
        "damage_tick_interval": 1.0,
        "duration": 8.0,
        "effect_tick_interval": 0.25,
        "freeze_effect": False,
        "hits_air": True,
        "hits_ground": True,
        "max_damage_ticks": 0,
        "movement_multiplier": 0.85,
        "periodic_damage_buff_duration": 1.0,
        "periodic_damage_controlled_by_parent": False,
        "radius": 3.5,
        "slow_refresh_duration": 1.0,
        "slows_attack_speed": False,
        "slows_spawn_speed": False,
        "spawn_speed_multiplier": None,
        "target_local_damage": True,
    }
    assert resident.pending_spell_action_kind("Earthquake") == "area_effect_spell"
    assert resident.pending_spell_action_kind("Freeze") == "area_effect_spell"
    assert resident.pending_spell_action_kind("Poison") == "area_effect_spell"
    assert set(resident.resident_supported_action_cards()) >= {
        "Earthquake",
        "Freeze",
        "Poison",
    }


def test_earthquake_catalog_tamper_fails_before_action_or_rng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(190_005))
    _set_earthquake_hand(battle)
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    earthquake = next(
        card for card in payload["cards"] if card["lookup_name"] == "Earthquake"
    )
    earthquake["area_effect_spell"]["damage_tick_interval"] = -1.0
    tampered = replace(
        bundle,
        payload=json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("ascii"),
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.pending_spell_state_bytes(),
    )

    assert "native_area_effect_spell_preflight" in (
        resident.resident_action_card_capability_reasons("Earthquake")
    )
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(*_actions())
    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.pending_spell_state_bytes(),
    ) == before


def test_poison_clock_shape_tamper_fails_before_action_or_rng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle, _target = _poison_battle(192_050)
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    poison = next(card for card in payload["cards"] if card["lookup_name"] == "Poison")
    poison["area_effect_spell"]["target_local_damage"] = False
    tampered = replace(
        bundle,
        payload=json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("ascii"),
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.pending_spell_state_bytes(),
    )

    assert "native_area_effect_spell_preflight" in (
        resident.resident_action_card_capability_reasons("Poison")
    )
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(*_actions())
    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.pending_spell_state_bytes(),
    ) == before


@pytest.mark.parametrize("spell_name", ["Earthquake", "Freeze", "Poison"])
@pytest.mark.parametrize("player_id", [0, 1])
def test_area_effect_spell_legal_actions_match_scalar_and_fast_masks(
    player_id: int, spell_name: str
) -> None:
    battle = BattleState(rng=random.Random(190_010 + player_id))
    {
        "Earthquake": _set_earthquake_hand,
        "Freeze": _set_freeze_hand,
        "Poison": _set_poison_hand,
    }[spell_name](battle)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    native = np.asarray(resident.resident_legal_action_ids(player_id), dtype=np.int64)

    for fast_path in (False, True):
        mask = action_space.legal_action_mask(
            battle, player_id, fast_path=fast_path
        )
        assert np.array_equal(native, np.flatnonzero(mask))


@pytest.mark.parametrize("dt", [0.05, 0.0333])
def test_earthquake_queue_pulses_and_slow_match_python(dt: float) -> None:
    battle = _earthquake_battle(190_020, dt=dt)
    resident = ResidentRustBattle.from_battle(battle)
    actions = _actions()
    expected_success, expected_order = _apply_python_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert battle.next_entity_id == resident.next_entity_id == 8
    _assert_semantic_parity(battle, resident)

    saw_birth = False
    max_damage_ticks = 0
    for tick in range(1, 141):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
        areas = [
            entity for entity in battle.entities.values() if type(entity) is AreaEffect
        ]
        if areas:
            area = areas[0]
            max_damage_ticks = max(max_damage_ticks, area.damage_ticks_applied)
            if not saw_birth:
                saw_birth = True
                assert area.time_alive == 0.0
                assert area.damage_ticks_applied == 0
                assert area.next_damage_time is None
                assert area.next_effect_time is None
    assert saw_birth
    # The final pulse and object cleanup are synchronous, so only the first two
    # counters are externally visible. The target HP pins all three pulses.
    assert max_damage_ticks == 2
    target = next(
        entity
        for entity in battle.entities.values()
        if type(entity) is Troop and entity.player_id == 1
    )
    assert target.hitpoints == target.max_hitpoints - 84.0 * 3


def test_earthquake_stealth_expiry_uses_ties_even_logic_clock() -> None:
    battle = _earthquake_battle(190_023, dt=0.0333)
    target = next(
        entity
        for entity in battle.entities.values()
        if type(entity) is Troop and entity.player_id == 1
    )
    initial_hp = target.hitpoints
    # The first pulse lands at accumulated time 2.064600... seconds. Python's
    # shared native clock rounds this to 2065 ms; flooring to 2064 would
    # incorrectly keep the target hidden for the committed pulse.
    target._stealth_until = 2065
    resident = ResidentRustBattle.from_battle(battle)
    actions = _actions()
    expected_success, expected_order = _apply_python_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order

    for _ in range(62):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert battle.time * 1000.0 == pytest.approx(2064.6)
    assert round(battle.time * 1000.0) == target._stealth_until
    assert target.hitpoints == initial_hp - 84.0


def test_earthquake_crown_and_ordinary_building_damage_are_exact() -> None:
    battle = BattleState(rng=random.Random(190_025), fast_path=True)
    _set_earthquake_hand(battle)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 3, 23, 0),
        action_space.no_op_action,
    )
    target_tower = battle.entities[4]
    initial_tower_hp = target_tower.hitpoints
    expected_success, expected_order = _apply_python_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success
    assert actual_order == expected_order
    for _ in range(85):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
    assert target_tower.hitpoints == initial_tower_hp - 49.0 * 3

    quake = BattleState(rng=random.Random(190_026), fast_path=True)
    baseline = BattleState(rng=random.Random(190_026), fast_path=True)
    _set_earthquake_hand(quake)
    _set_earthquake_hand(baseline)
    quake_target = _spawn_ready_building(quake, "Xbow", Position(9.5, 16.5))
    base_target = _spawn_ready_building(baseline, "Xbow", Position(9.5, 16.5))
    quake_resident = ResidentRustBattle.from_battle(quake)
    quake_actions = _actions()
    _apply_python_actions(quake, quake_actions)
    quake_resident.apply_resident_joint_actions(*quake_actions)
    for _ in range(85):
        baseline._step_logic_tick(refresh_fast_path_end=False)
        quake._step_logic_tick(refresh_fast_path_end=False)
        assert quake_resident.advance_complete_tick()
        _assert_semantic_parity(quake, quake_resident)
    assert quake_target.is_alive and base_target.is_alive
    assert base_target.hitpoints - quake_target.hitpoints == 287.0 * 3


def test_earthquake_pending_full_and_delta_publication_is_authenticated() -> None:
    battle = _earthquake_battle(190_026)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *_actions(), 0
    )
    assert success == {0: True, 1: True}
    assert advanced == 0
    full_raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    delta_raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    registry: dict[int, object] = dict(battle.entities)
    full_plan = _build_direct_publication_plan(
        full_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    delta_plan = _build_direct_delta_publication_plan(
        delta_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    assert [cast["spell_name"] for cast in full_plan.pending_spells["casts"]] == [
        "Earthquake"
    ]
    assert delta_plan.pending_spells is not None
    assert [
        cast["spell_name"] for cast in delta_plan.pending_spells["casts"]
    ] == ["Earthquake"]


def test_lethal_earthquake_fresh_slow_scan_matches_off_shadow_on() -> None:
    base = BattleState(rng=random.Random(190_027), fast_path=True)
    _set_earthquake_hand(base)
    stats = base.card_loader.get_card("Golem")
    assert stats is not None
    golem = base._spawn_entity(Troop, Position(9.5, 16.5), 1, stats)
    _finish_deploy(golem)
    golem.hitpoints = 1
    golem.apply_stun(20.0)
    actions = _actions()
    off = base.clone()
    shadow_battle = base.clone()
    on_battle = base.clone()
    expected_success, expected_order = _apply_python_actions(off, actions)
    assert off.step_logic_ticks(40) == 40
    action_space = DiscreteTileActionSpace()
    shadow = ResidentCompleteTickRuntime(
        shadow_battle,
        RustBattleMode.SHADOW,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    on = ResidentCompleteTickRuntime(
        on_battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )

    shadow_result = shadow.apply_joint_actions_and_advance(*actions, 40)
    on_result = on.apply_joint_actions_and_advance(*actions, 40)

    assert shadow_result.action_success == on_result.action_success == expected_success
    assert shadow_result.action_order == on_result.action_order == expected_order
    assert python_resident_semantic_snapshot(shadow_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert python_resident_semantic_snapshot(on_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert shadow.status.shadow_mismatches == 0
    golemites = [
        entity
        for entity in off.entities.values()
        if type(entity) is Troop and str(entity.card_stats.name) == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(entity.hitpoints == entity.max_hitpoints for entity in golemites)
    assert all(entity.slow_timer == pytest.approx(1.0) for entity in golemites)
    assert all(entity.slow_multiplier == pytest.approx(0.5) for entity in golemites)


def test_earthquake_full_and_delta_publication_continue_exactly() -> None:
    battle = _earthquake_battle(190_030)
    control = _earthquake_battle(190_030)
    actions = _actions()
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *actions, 20
    )
    expected_success, _expected_order = _apply_python_actions(control, actions)
    assert control.step_logic_ticks(20) == 20
    assert success == expected_success == {0: True, 1: True}
    assert advanced == 20

    diagnostic_projection = _typed_publication_projection(
        candidate.prepare_publication(prior).parts()
    )
    assert diagnostic_projection.snapshot == rust_resident_semantic_snapshot(candidate)

    full_raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    delta_raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    registry: dict[int, object] = dict(battle.entities)
    full_plan = _build_direct_publication_plan(
        full_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    delta_plan = _build_direct_delta_publication_plan(
        delta_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    full_area = next(
        entity for entity in full_plan.entities if entity.raw["area_effect_state"]
    )
    delta_area = next(
        entity.full
        for entity in delta_plan.entities
        if entity.full is not None and entity.full.raw["area_effect_state"]
    )
    assert full_area.raw["area_effect_state"]["persistent_spell"] is not None
    assert delta_area.raw["area_effect_state"]["persistent_spell"] is not None

    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    area = next(entity for entity in battle.entities.values() if type(entity) is AreaEffect)
    assert area.card_stats is None
    assert area.time_alive == 0.0

    next_candidate = candidate.fork()
    assert next_candidate.advance_complete_ticks(20) == 20
    assert control.step_logic_ticks(20) == 20
    publish_complete_tick_state(
        battle,
        next_candidate,
        prior_resident=candidate,
        entity_registry=registry,
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    area = next(entity for entity in battle.entities.values() if type(entity) is AreaEffect)
    assert area.damage_ticks_applied == 1
    assert area.next_damage_time == pytest.approx(2.0)
    assert area.next_effect_time == pytest.approx(1.1)

    area_identity = area
    final_candidate = next_candidate.fork()
    assert final_candidate.advance_complete_ticks(41) == 41
    assert control.step_logic_ticks(41) == 41
    publish_complete_tick_state(
        battle,
        final_candidate,
        prior_resident=next_candidate,
        entity_registry=registry,
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert area_identity.id not in battle.entities
    assert registry[area_identity.id] is area_identity
    assert not area_identity.is_alive
    assert area_identity.damage_ticks_applied == 3


@pytest.mark.parametrize("projection_kind", ["full", "delta"])
@pytest.mark.parametrize("tamper_field", ["damage", "area_name"])
def test_earthquake_publication_constructor_tamper_fails_pre_live(
    projection_kind: str,
    tamper_field: str,
) -> None:
    battle = _earthquake_battle(190_035)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *_actions(), 20
    )
    assert success == {0: True, 1: True}
    assert advanced == 20
    if projection_kind == "full":
        raw = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
        row = next(entity for entity in raw["entities"] if entity["area_effect_state"])
    else:
        raw = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )
        change = next(entity for entity in raw["entities"] if entity["full"])
        row = change["full"]
    area = row["area_effect_state"]
    if tamper_field == "damage":
        area["persistent_spell"]["damage"] = 85.0
    else:
        area["spec"]["area_name"] = "Poison"
    before = canonical_battle_snapshot(battle)

    with pytest.raises(ResidentPublicationError, match="catalog area"):
        if projection_kind == "full":
            _build_direct_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
        else:
            _build_direct_delta_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
    assert canonical_battle_snapshot(battle) == before


def test_earthquake_publication_rollback_restores_area_identity_and_clocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = _earthquake_battle(190_040)
    registry: dict[int, object] = dict(battle.entities)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *_actions(), 20
    )
    assert success == {0: True, 1: True}
    assert advanced == 20
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    area = next(entity for entity in battle.entities.values() if type(entity) is AreaEffect)
    canonical_before = canonical_battle_snapshot(battle)
    causal_before = _causal_boundary_snapshot(battle)
    registry_before = tuple(registry.items())
    attrs_before = dict(vars(area))
    next_candidate = candidate.fork()
    assert next_candidate.advance_complete_ticks(20) == 20

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected Earthquake publication failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", reject_commit
    )
    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            next_candidate,
            prior_resident=candidate,
            entity_registry=registry,
        )

    assert canonical_battle_snapshot(battle) == canonical_before
    assert _causal_boundary_snapshot(battle) == causal_before
    assert tuple(registry.items()) == registry_before
    assert registry[area.id] is area
    assert vars(area) == attrs_before


@pytest.mark.parametrize("dt", [0.05, 0.0333])
def test_poison_target_owned_periodic_clock_and_lingering_match_python(
    dt: float,
) -> None:
    battle, target = _poison_battle(192_000, dt=dt)
    resident = ResidentRustBattle.from_battle(battle)
    actions = _actions()
    expected_success, expected_order = _apply_python_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order

    area_id: int | None = None
    effect_identity: PeriodicDamageEffect | None = None
    effect_map = target._periodic_damage_effects
    saw_area_cleanup_with_lingering_effect = False
    rehydrated_after_cleanup = False
    initial_hp = target.hitpoints
    for _ in range(int(11.0 / dt) + 2):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
        areas = [entity for entity in battle.entities.values() if type(entity) is AreaEffect]
        if areas and area_id is None:
            area_id = areas[0].id
            assert areas[0].target_local_damage
            assert areas[0].max_damage_ticks == 0
            assert areas[0].next_damage_time is None
        if area_id is not None and area_id in effect_map:
            effect = effect_map[area_id]
            if effect_identity is None:
                effect_identity = effect
            else:
                assert effect is effect_identity
            assert effect_map is target._periodic_damage_effects
            assert effect.source_kind == "Poison"
            assert effect.hit_interval == 1.0
            assert effect.damage == 92.0
        if area_id is not None and not areas and area_id in effect_map:
            saw_area_cleanup_with_lingering_effect = True
            if not rehydrated_after_cleanup:
                fresh = ResidentRustBattle.from_battle(battle)
                _assert_semantic_parity(battle, fresh)
                rehydrated_after_cleanup = True
        if saw_area_cleanup_with_lingering_effect and area_id not in effect_map:
            break

    assert area_id is not None
    assert effect_identity is not None
    assert saw_area_cleanup_with_lingering_effect
    assert rehydrated_after_cleanup
    assert target.hitpoints < initial_hp
    assert not effect_map


def test_poison_multiple_sources_preserve_effect_order_and_refresh_phase() -> None:
    battle, target = _poison_battle(192_010)
    second = SPELL_REGISTRY["Poison"]
    assert second.cast(battle, 0, Position(9.5, 16.5))
    first_area_id = battle.next_entity_id - 1
    for _ in range(5):
        battle._step_logic_tick(refresh_fast_path_end=False)
    assert second.cast(battle, 0, Position(9.5, 16.5))
    second_area_id = battle.next_entity_id - 1
    resident = ResidentRustBattle.from_battle(battle)

    saw_both = False
    first_phase: float | None = None
    for _ in range(40):
        battle._step_logic_tick(refresh_fast_path_end=False)
        assert resident.advance_complete_tick()
        _assert_semantic_parity(battle, resident)
        effects = target._periodic_damage_effects
        if list(effects) == [first_area_id, second_area_id]:
            saw_both = True
            current = effects[first_area_id].time_to_next_hit
            if first_phase is not None:
                # Refreshing duration must not reset the independent damage phase.
                assert current <= first_phase + 1e-9 or current > 0.9
            first_phase = current
    assert saw_both


def test_poison_continuous_slow_uses_effect_interval_as_minimum_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poison = SPELL_REGISTRY["Poison"]
    monkeypatch.setattr(poison, "slow_refresh_duration", 0.1)
    monkeypatch.setattr(poison, "effect_tick_interval", 0.25)
    rust_core._resident_card_catalog_bundle.cache_clear()
    try:
        battle, target = _poison_battle(192_012)
        resident = ResidentRustBattle.from_battle(battle)
        actions = _actions()
        expected_success, expected_order = _apply_python_actions(battle, actions)
        actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
        assert actual_success == expected_success == {0: True, 1: True}
        assert actual_order == expected_order

        for _ in range(25):
            battle._step_logic_tick(refresh_fast_path_end=False)
            assert resident.advance_complete_tick()
            _assert_semantic_parity(battle, resident)

        assert target.slow_timer == 0.25
        assert target.slow_multiplier == 0.85
    finally:
        # Avoid retaining a recipe built while the synthetic spell is patched.
        rust_core._resident_card_catalog_bundle.cache_clear()


def test_poison_checkpoint_preserves_non_id_periodic_effect_order() -> None:
    battle, target = _poison_battle(192_015)
    assert SPELL_REGISTRY["Poison"].cast(battle, 0, Position(9.5, 16.5))
    first_id = battle.next_entity_id - 1
    assert SPELL_REGISTRY["Poison"].cast(battle, 0, Position(9.5, 16.5))
    second_id = battle.next_entity_id - 1
    target._periodic_damage_effects = {
        second_id: PeriodicDamageEffect(
            source_id=second_id,
            source_kind="Poison",
            remaining=0.9,
            hit_interval=1.0,
            time_to_next_hit=0.4,
            damage=92.0,
        ),
        first_id: PeriodicDamageEffect(
            source_id=first_id,
            source_kind="Poison",
            remaining=0.8,
            hit_interval=1.0,
            time_to_next_hit=0.3,
            damage=92.0,
        ),
    }
    resident = ResidentRustBattle.from_battle(battle)
    _assert_semantic_parity(battle, resident)

    battle._step_logic_tick(refresh_fast_path_end=False)
    assert resident.advance_complete_tick()
    _assert_semantic_parity(battle, resident)
    assert list(target._periodic_damage_effects) == [second_id, first_id]


def test_poison_full_delta_publication_reuses_nested_effect_identity_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle, target = _poison_battle(192_020)
    control, control_target = _poison_battle(192_020)
    registry: dict[int, object] = dict(battle.entities)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *_actions(), 25
    )
    expected_success, _expected_order = _apply_python_actions(control, _actions())
    assert control.step_logic_ticks(25) == 25
    assert success == expected_success == {0: True, 1: True}
    assert advanced == 25

    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    effects = target._periodic_damage_effects
    assert len(effects) == 1
    source_id, effect = next(iter(effects.items()))
    control_effect = control_target._periodic_damage_effects[source_id]
    assert effect.time_to_next_hit == control_effect.time_to_next_hit

    next_candidate = candidate.fork()
    assert next_candidate.advance_complete_ticks(5) == 5
    assert control.step_logic_ticks(5) == 5
    publish_complete_tick_state(
        battle,
        next_candidate,
        prior_resident=candidate,
        entity_registry=registry,
    )
    assert target._periodic_damage_effects is effects
    assert target._periodic_damage_effects[source_id] is effect
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )

    canonical_before = canonical_battle_snapshot(battle)
    causal_before = _causal_boundary_snapshot(battle)
    attrs_before = dict(vars(effect))
    final_candidate = next_candidate.fork()
    assert final_candidate.advance_complete_ticks(5) == 5

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected Poison publication failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", reject_commit
    )
    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            final_candidate,
            prior_resident=next_candidate,
            entity_registry=registry,
        )
    assert canonical_battle_snapshot(battle) == canonical_before
    assert _causal_boundary_snapshot(battle) == causal_before
    assert target._periodic_damage_effects is effects
    assert target._periodic_damage_effects[source_id] is effect
    assert vars(effect) == attrs_before


def test_poison_publication_keeps_cleaned_source_as_periodic_tombstone() -> None:
    battle, target = _poison_battle(192_025)
    control, control_target = _poison_battle(192_025)
    registry: dict[int, object] = dict(battle.entities)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *_actions(), 180
    )
    expected_success, _expected_order = _apply_python_actions(control, _actions())
    assert control.step_logic_ticks(180) == 180
    assert success == expected_success == {0: True, 1: True}
    assert advanced == 180

    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert len(target._periodic_damage_effects) == 1
    source_id = next(iter(target._periodic_damage_effects))
    assert source_id == next(iter(control_target._periodic_damage_effects))
    assert source_id not in battle.entities
    source = registry[source_id]
    assert type(source) is AreaEffect
    assert not source.is_alive


@pytest.mark.parametrize("projection_kind", ["full", "delta"])
def test_poison_publication_rejects_future_periodic_source_pre_live(
    projection_kind: str,
) -> None:
    battle, _target = _poison_battle(192_030)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *_actions(), 25
    )
    assert success == {0: True, 1: True}
    assert advanced == 25
    if projection_kind == "full":
        raw = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
        entity = next(
            row
            for row in raw["entities"]
            if row["modifier_state"]
            and row["modifier_state"]["periodic_damage_effects"]
        )
    else:
        raw = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )
        entity = next(
            row
            for row in raw["entities"]
            if row["modifier_state"]
            and row["modifier_state"]["periodic_damage_effects"]
        )
    entity["modifier_state"]["periodic_damage_effects"][0]["source_id"] = raw[
        "battle"
    ]["next_entity_id"]
    before = canonical_battle_snapshot(battle)

    with pytest.raises(ResidentPublicationError, match="future periodic source"):
        if projection_kind == "full":
            _build_direct_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
        else:
            _build_direct_delta_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
    assert canonical_battle_snapshot(battle) == before


def test_poison_action_interval_matches_off_shadow_on() -> None:
    base, _target = _poison_battle(192_040)
    off = base.clone()
    shadow_battle = base.clone()
    on_battle = base.clone()
    actions = _actions()
    expected_success, expected_order = _apply_python_actions(off, actions)
    assert off.step_logic_ticks(65) == 65
    action_space = DiscreteTileActionSpace()
    shadow = ResidentCompleteTickRuntime(
        shadow_battle,
        RustBattleMode.SHADOW,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    on = ResidentCompleteTickRuntime(
        on_battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )

    shadow_result = shadow.apply_joint_actions_and_advance(*actions, 65)
    on_result = on.apply_joint_actions_and_advance(*actions, 65)
    assert shadow_result.action_success == on_result.action_success == expected_success
    assert shadow_result.action_order == on_result.action_order == expected_order
    assert python_resident_semantic_snapshot(shadow_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert python_resident_semantic_snapshot(on_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert shadow.status.shadow_mismatches == 0


@pytest.mark.parametrize("dt", [0.05, 0.0333])
def test_freeze_immediate_damage_and_one_time_status_snapshot_match_python(
    dt: float,
) -> None:
    battle, target = _freeze_battle(191_000, dt=dt)
    resident = ResidentRustBattle.from_battle(battle)
    actions = _actions()
    expected_success, expected_order = _apply_python_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    initial_hp = target.hitpoints
    saw_birth = False
    saw_snapshot = False
    snapshot_hp = 0.0
    for _ in range(160):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
        areas = [entity for entity in battle.entities.values() if type(entity) is AreaEffect]
        if not areas:
            continue
        area = areas[0]
        if not saw_birth:
            saw_birth = True
            assert area.time_alive == 0.0
            assert area.freeze_effect
            assert area.attack_speed_multiplier is None
            assert area.spawn_speed_multiplier is None
            assert area.building_damage is None
            assert not area.freeze_targets_applied
            continue
        if not saw_snapshot:
            saw_snapshot = True
            snapshot_hp = target.hitpoints
            assert snapshot_hp == initial_hp - 148.0
            assert area.damage_ticks_applied == 1
            assert area.next_damage_time == 0.0
            assert area.freeze_targets_applied
            assert target.stun_timer == pytest.approx(4.0)
            assert target.slow_timer == pytest.approx(4.0)
            assert target.slow_multiplier == 0.0
            assert target.freeze_expiry_time == pytest.approx(battle.time + 4.0)
        elif area.time_alive > dt * 2.5:
            assert target.hitpoints == snapshot_hp
            break
    assert saw_birth and saw_snapshot


def test_freeze_crown_and_ordinary_building_damage_are_exact() -> None:
    crown = BattleState(rng=random.Random(191_010), fast_path=True)
    _set_freeze_hand(crown)
    crown_resident = ResidentRustBattle.from_battle(crown)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 3, 23, 0),
        action_space.no_op_action,
    )
    tower = crown.entities[4]
    initial_tower_hp = tower.hitpoints
    _apply_python_actions(crown, actions)
    crown_resident.apply_resident_joint_actions(*actions)
    for _ in range(22):
        assert crown_resident.advance_complete_tick()
        crown._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(crown, crown_resident)
    assert tower.hitpoints == initial_tower_hp - 37.0

    battle = BattleState(rng=random.Random(191_011), fast_path=True)
    baseline = BattleState(rng=random.Random(191_011), fast_path=True)
    _set_freeze_hand(battle)
    _set_freeze_hand(baseline)
    building = _spawn_ready_building(battle, "Xbow", Position(9.5, 16.5))
    baseline_building = _spawn_ready_building(
        baseline, "Xbow", Position(9.5, 16.5)
    )
    resident = ResidentRustBattle.from_battle(battle)
    _apply_python_actions(battle, _actions())
    resident.apply_resident_joint_actions(*_actions())
    for _ in range(22):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        baseline._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
    assert baseline_building.hitpoints - building.hitpoints == 148.0


def test_freeze_lethal_damage_births_enter_fresh_status_snapshot() -> None:
    battle = BattleState(rng=random.Random(191_015), fast_path=True)
    _set_freeze_hand(battle)
    stats = battle.card_loader.get_card("Golem")
    assert stats is not None
    golem = battle._spawn_entity(Troop, Position(9.5, 16.5), 1, stats)
    _finish_deploy(golem)
    golem.hitpoints = 100.0
    resident = ResidentRustBattle.from_battle(battle)
    _apply_python_actions(battle, _actions())
    resident.apply_resident_joint_actions(*_actions())
    for _ in range(21):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
    assert not golem.is_alive
    golemites = [
        entity
        for entity in battle.entities.values()
        if type(entity) is Troop and str(entity.card_stats.name) == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(entity.hitpoints == entity.max_hitpoints for entity in golemites)
    assert all(entity.stun_timer == pytest.approx(4.0) for entity in golemites)
    assert all(entity.slow_timer == pytest.approx(4.0) for entity in golemites)
    assert all(entity.freeze_expiry_time == pytest.approx(battle.time + 4.0) for entity in golemites)


def test_lethal_freeze_fresh_status_snapshot_matches_off_shadow_on() -> None:
    base = BattleState(rng=random.Random(191_016), fast_path=True)
    _set_freeze_hand(base)
    stats = base.card_loader.get_card("Golem")
    assert stats is not None
    golem = base._spawn_entity(Troop, Position(9.5, 16.5), 1, stats)
    _finish_deploy(golem)
    golem.hitpoints = 100.0
    actions = _actions()
    off = base.clone()
    shadow_battle = base.clone()
    on_battle = base.clone()
    expected_success, expected_order = _apply_python_actions(off, actions)
    assert off.step_logic_ticks(21) == 21
    action_space = DiscreteTileActionSpace()
    shadow = ResidentCompleteTickRuntime(
        shadow_battle,
        RustBattleMode.SHADOW,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    on = ResidentCompleteTickRuntime(
        on_battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    shadow_result = shadow.apply_joint_actions_and_advance(*actions, 21)
    on_result = on.apply_joint_actions_and_advance(*actions, 21)
    assert shadow_result.action_success == on_result.action_success == expected_success
    assert shadow_result.action_order == on_result.action_order == expected_order
    assert python_resident_semantic_snapshot(shadow_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert python_resident_semantic_snapshot(on_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert shadow.status.shadow_mismatches == 0


def test_freeze_full_delta_publication_and_rollback_preserve_area_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle, _target = _freeze_battle(191_020)
    control, _control_target = _freeze_battle(191_020)
    actions = _actions()
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        *actions, 20
    )
    expected_success, _expected_order = _apply_python_actions(control, actions)
    assert control.step_logic_ticks(20) == 20
    assert success == expected_success == {0: True, 1: True}
    assert advanced == 20
    registry: dict[int, object] = dict(battle.entities)
    publish_complete_tick_state(
        battle, candidate, prior_resident=prior, entity_registry=registry
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    area = next(entity for entity in battle.entities.values() if type(entity) is AreaEffect)
    assert area.freeze_effect
    assert area.attack_speed_multiplier is None
    assert area.spawn_speed_multiplier is None
    assert area.building_damage is None
    assert not area.freeze_targets_applied

    snapshot_candidate = candidate.fork()
    assert snapshot_candidate.advance_complete_tick()
    assert control.step_logic_ticks(1) == 1
    publish_complete_tick_state(
        battle,
        snapshot_candidate,
        prior_resident=candidate,
        entity_registry=registry,
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert registry[area.id] is area
    assert area.freeze_targets_applied
    assert area.damage_ticks_applied == 1
    before = canonical_battle_snapshot(battle)
    attrs_before = dict(vars(area))
    failed_candidate = snapshot_candidate.fork()
    assert failed_candidate.advance_complete_tick()

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected Freeze publication failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", reject_commit
    )
    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            failed_candidate,
            prior_resident=snapshot_candidate,
            entity_registry=registry,
        )
    assert canonical_battle_snapshot(battle) == before
    assert registry[area.id] is area
    assert vars(area) == attrs_before


@pytest.mark.parametrize("projection_kind", ["full", "delta"])
def test_freeze_publication_clock_tamper_fails_before_live(
    projection_kind: str,
) -> None:
    battle, _target = _freeze_battle(191_030)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, _success, _order, _advanced = (
        prior.preview_resident_joint_action_interval(*_actions(), 21)
    )
    if projection_kind == "full":
        raw = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
        row = next(entity for entity in raw["entities"] if entity["area_effect_state"])
    else:
        raw = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )
        change = next(entity for entity in raw["entities"] if entity["full"])
        row = change["full"]
    row["area_effect_state"]["persistent_spell"]["clock_kind"] = "source_periodic"
    before = canonical_battle_snapshot(battle)
    with pytest.raises(ResidentPublicationError, match="catalog area"):
        if projection_kind == "full":
            _build_direct_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
        else:
            _build_direct_delta_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
    assert canonical_battle_snapshot(battle) == before
