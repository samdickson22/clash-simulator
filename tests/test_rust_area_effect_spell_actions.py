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
from clasher.entities import AreaEffect, Building, Troop
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

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _set_earthquake_hand(battle: BattleState) -> None:
    for player in battle.players:
        player.hand = ["Earthquake", "Knight", "Knight", "Knight"]
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


def test_area_effect_catalog_structurally_qualifies_only_earthquake() -> None:
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

    assert payload["schema_version"] == 15
    assert {
        name
        for name, card in area_cards.items()
        if not card["capability_reasons"]
    } == {"Earthquake"}
    assert "nested_area_effect_payload" in area_cards["Lightning"][
        "capability_reasons"
    ]
    assert "unsupported_area_effect_clock" in area_cards["Poison"][
        "capability_reasons"
    ]
    assert "unsupported_area_effect_clock" in area_cards["Freeze"][
        "capability_reasons"
    ]
    earthquake = area_cards["Earthquake"]["area_effect_spell"]
    assert earthquake == {
        "affects_hidden": True,
        "building_damage": 287.0,
        "building_damage_multiplier": 3.5,
        "cap_buff_time_to_effect": True,
        "clock_kind": "source_periodic",
        "crown_tower_damage": 49.0,
        "crown_tower_damage_multiplier": 0.6,
        "damage": 84.0,
        "damage_tick_interval": 1.0,
        "duration": 3.0,
        "effect_tick_interval": 0.1,
        "hits_air": False,
        "hits_ground": True,
        "max_damage_ticks": 3,
        "movement_multiplier": 0.5,
        "periodic_damage_buff_duration": 1.0,
        "radius": 3.5,
        "slow_refresh_duration": 1.0,
    }
    assert resident.pending_spell_action_kind("Earthquake") == "area_effect_spell"
    assert set(resident.resident_supported_action_cards()) >= {"Earthquake"}


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


@pytest.mark.parametrize("player_id", [0, 1])
def test_earthquake_legal_actions_match_scalar_and_fast_masks(player_id: int) -> None:
    battle = BattleState(rng=random.Random(190_010 + player_id))
    _set_earthquake_hand(battle)
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
