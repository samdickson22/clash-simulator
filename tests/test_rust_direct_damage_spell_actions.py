from __future__ import annotations

import copy
import json
import random
from collections import deque

import numpy as np
import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot
from clasher.entities import Building, Troop
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
    publish_complete_tick_state,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime, _causal_boundary_snapshot

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _set_zap_hands(battle: BattleState) -> None:
    for player in battle.players:
        player.hand = ["Zap", "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir


def _set_single_card_hand(battle: BattleState, card_name: str) -> None:
    battle.players[0].hand = [card_name, "Knight", "Knight", "Knight"]
    battle.players[0].cycle_queue = deque(["Knight"] * 4)
    battle.players[0].elixir = battle.players[0].max_elixir


def _finish_deploy(entity: Troop | Building) -> None:
    entity.deploy_delay_remaining = 0.0
    entity.placement_delay_total = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True


def _spawn_ready_troop(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player_id, stats)
    _finish_deploy(entity)
    return entity


def _apply_python_actions(
    battle: BattleState,
    action_space: DiscreteTileActionSpace,
    actions: tuple[int, int],
) -> tuple[dict[int, bool], tuple[int, int]]:
    order = [0, 1]
    battle.rng.shuffle(order)
    success = {
        player_id: action_space.apply_action(battle, player_id, actions[player_id])
        for player_id in order
    }
    return success, (order[0], order[1])


def _assert_semantic_parity(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(battle)
    )


def test_direct_damage_catalog_structurally_qualifies_only_zap() -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    direct = {
        card["lookup_name"]: tuple(card["capability_reasons"])
        for card in payload["cards"]
        if card["action_kind"] == "direct_damage_spell"
    }
    resident = ResidentRustBattle.from_battle(battle)

    assert payload["schema_version"] == 9
    assert direct["Zap"] == ()
    assert {
        name for name, reasons in direct.items() if not reasons
    } == {"Zap"}
    assert all(
        direct[name]
        for name in ("Mirror", "MergeMaiden", "Rage", "WarmSpell")
    )
    assert resident.resident_action_card_capability_reasons("Zap") == ()
    assert "Zap" in resident.resident_supported_action_cards()


@pytest.mark.parametrize("field", ["radius", "damage", "stun_duration"])
def test_direct_damage_catalog_tamper_fails_closed(
    field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(160_010))
    _set_zap_hands(battle)
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    zap = next(card for card in payload["cards"] if card["lookup_name"] == "Zap")
    zap["direct_damage_spell"][field] = -1.0
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "ascii"
        ),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
        rolling_spawn_recipes=bundle.rolling_spawn_recipes,
        rolling_projectile_recipes=bundle.rolling_projectile_recipes,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.pending_spell_state_bytes(),
    )
    action_space = DiscreteTileActionSpace()

    assert "native_direct_damage_spell_preflight" in (
        resident.resident_action_card_capability_reasons("Zap")
    )
    assert resident.pending_spell_action_kind("Zap") is None
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(
            action_space.encode_action(0, 9, 20, 0),
            action_space.no_op_action,
        )
    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.pending_spell_state_bytes(),
    ) == before


@pytest.mark.parametrize("player_id", [0, 1])
def test_zap_legal_actions_match_scalar_and_fast_masks(player_id: int) -> None:
    battle = BattleState(rng=random.Random(160_020 + player_id))
    _set_zap_hands(battle)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    native = np.asarray(resident.resident_legal_action_ids(player_id), dtype=np.int64)

    for fast_path in (False, True):
        mask = action_space.legal_action_mask(
            battle,
            player_id,
            fast_path=fast_path,
        )
        assert np.array_equal(native, np.flatnonzero(mask))


def test_zap_queues_for_one_second_then_damages_and_stuns_exactly() -> None:
    battle = BattleState(rng=random.Random(160_030), fast_path=True)
    _set_zap_hands(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 20, 0)
    position = action_space.decode_action(action, 0).position
    assert position is not None
    target = _spawn_ready_troop(battle, "Knight", 1, position)
    before_hp = target.hitpoints
    resident = ResidentRustBattle.from_battle(battle)
    actions = (action, action_space.no_op_action)

    expected_success, expected_order = _apply_python_actions(
        battle, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    _assert_semantic_parity(battle, resident)
    assert len(battle._pending_spell_casts) == 1

    for _ in range(19):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
        assert target.hitpoints == before_hp
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)
    _assert_semantic_parity(battle, resident)
    assert not battle._pending_spell_casts
    assert target.hitpoints == before_hp - 192
    assert target.stun_timer == pytest.approx(0.45)


def test_zap_crown_damage_and_shield_absorption_match_python() -> None:
    battle = BattleState(rng=random.Random(160_035), fast_path=True)
    _set_zap_hands(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 3, 25, 0)
    position = action_space.decode_action(action, 0).position
    assert position is not None
    guard = _spawn_ready_troop(battle, "Guards", 1, Position(4.0, 25.5))
    shield = next(
        mechanic for mechanic in guard.mechanics if hasattr(mechanic, "current_shield")
    )
    shield_before = shield.current_shield
    guard_hp = guard.hitpoints
    tower = next(
        entity
        for entity in battle.entities.values()
        if type(entity) is Building
        and entity.player_id == 1
        and entity._crown_tower_slot == "left"
    )
    tower_hp = tower.hitpoints
    resident = ResidentRustBattle.from_battle(battle)
    actions = (action, action_space.no_op_action)

    expected_success, expected_order = _apply_python_actions(
        battle, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    for _ in range(20):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert tower.hitpoints == tower_hp - 48
    assert shield.current_shield == shield_before - 192
    assert guard.hitpoints == guard_hp
    assert guard.stun_timer == pytest.approx(0.45)


def test_zap_strict_tangent_and_rounded_building_corner_match_python() -> None:
    battle = BattleState(rng=random.Random(160_036), fast_path=True)
    _set_zap_hands(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 20, 0)
    center = action_space.decode_action(action, 0).position
    assert center is not None
    tangent = _spawn_ready_troop(
        battle,
        "Knight",
        1,
        Position(center.x + 3.0, center.y),
    )
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    corner_offset = float(cannon_stats.collision_radius) + 2.5 * 0.7
    cannon = battle._spawn_entity(
        Building,
        Position(center.x + corner_offset, center.y + corner_offset),
        1,
        cannon_stats,
    )
    _finish_deploy(cannon)
    tangent_hp = tangent.hitpoints
    cannon_hp = cannon.hitpoints
    resident = ResidentRustBattle.from_battle(battle)
    actions = (action, action_space.no_op_action)

    _apply_python_actions(battle, action_space, actions)
    resident.apply_resident_joint_actions(*actions)
    for _ in range(20):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert tangent.hitpoints == tangent_hp
    assert tangent.stun_timer == 0.0
    assert cannon.hitpoints < cannon_hp - 192
    assert cannon.stun_timer == pytest.approx(0.45)


def test_zap_stealth_suppresses_damage_but_not_status() -> None:
    battle = BattleState(rng=random.Random(160_037), fast_path=True)
    _set_zap_hands(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 20, 0)
    position = action_space.decode_action(action, 0).position
    assert position is not None
    target = _spawn_ready_troop(battle, "Knight", 1, position)
    target._stealth_until = 100_000
    before_hp = target.hitpoints
    resident = ResidentRustBattle.from_battle(battle)
    actions = (action, action_space.no_op_action)

    _apply_python_actions(battle, action_space, actions)
    resident.apply_resident_joint_actions(*actions)
    for _ in range(20):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert target.hitpoints == before_hp
    assert target.stun_timer == pytest.approx(0.45)


def test_zap_mechanics_free_hidden_building_still_receives_damage_and_status() -> None:
    battle = BattleState(rng=random.Random(160_037_1), fast_path=True)
    _set_zap_hands(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 20, 0)
    position = action_space.decode_action(action, 0).position
    assert position is not None
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    target = battle._spawn_entity(Building, position, 1, cannon_stats)
    _finish_deploy(target)
    assert not target.mechanics
    target._hidden_building = True
    before_hp = target.hitpoints
    resident = ResidentRustBattle.from_battle(battle)
    actions = (action, action_space.no_op_action)

    _apply_python_actions(battle, action_space, actions)
    resident.apply_resident_joint_actions(*actions)
    for _ in range(20):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert target.hitpoints < before_hp - 192
    assert target.stun_timer == pytest.approx(0.45)


def test_simultaneous_zaps_preserve_shuffle_and_due_sequence_order() -> None:
    battle = BattleState(rng=random.Random(160_038), fast_path=True)
    _set_zap_hands(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 9, 15, 0),
        action_space.encode_action(0, 9, 15, 1),
    )
    center = action_space.decode_action(actions[0], 0).position
    assert center == action_space.decode_action(actions[1], 1).position
    assert center is not None
    targets = [
        _spawn_ready_troop(
            battle,
            "Knight",
            player_id,
            Position(center.x + (-2.0 if player_id == 0 else 2.0), center.y),
        )
        for player_id in (0, 1)
    ]
    for target in targets:
        target.deploy_delay_remaining = 2.0
        target.placement_delay_total = 2.0
        target.placement_pending = True
        target._spawn_hook_pending = True
        target._spawn_hook_fired = False
    before_hp = [target.hitpoints for target in targets]
    resident = ResidentRustBattle.from_battle(battle)

    expected_success, expected_order = _apply_python_actions(
        battle, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert [cast.player_id for cast in battle._pending_spell_casts] == list(
        expected_order
    )
    _assert_semantic_parity(battle, resident)
    for _ in range(20):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert [target.hitpoints for target in targets] == [hp - 192 for hp in before_hp]
    assert all(target.stun_timer == pytest.approx(0.45) for target in targets)


def _lethal_golem_zap_battle(seed: int) -> tuple[BattleState, int]:
    battle = BattleState(rng=random.Random(seed), fast_path=True)
    _set_zap_hands(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 20, 0)
    position = action_space.decode_action(action, 0).position
    assert position is not None
    golem = _spawn_ready_troop(battle, "Golem", 1, position)
    golem.hitpoints = 1
    return battle, action


def test_lethal_zap_damage_then_fresh_status_scan_matches_off_shadow_on() -> None:
    base, action = _lethal_golem_zap_battle(160_040)
    action_space = DiscreteTileActionSpace()
    actions = (action, action_space.no_op_action)
    off = base.clone()
    shadow_battle = base.clone()
    on_battle = base.clone()
    expected_success, expected_order = _apply_python_actions(off, action_space, actions)
    assert off.step_logic_ticks(20) == 20
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

    shadow_result = shadow.apply_joint_actions_and_advance(*actions, 20)
    on_result = on.apply_joint_actions_and_advance(*actions, 20)

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
    assert all(entity.stun_timer == pytest.approx(0.5) for entity in golemites)

    assert off.step_logic_ticks(8) == 8
    assert shadow.advance_ticks(8) == on.advance_ticks(8) == 8
    assert python_resident_semantic_snapshot(on_battle) == (
        python_resident_semantic_snapshot(off)
    )


def test_due_zap_validates_direct_full_and_delta_publication() -> None:
    battle, action = _lethal_golem_zap_battle(160_050)
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action,
        action_space.no_op_action,
        20,
    )
    assert success == {0: True, 1: True}
    assert advanced == 20
    registry = dict(battle.entities)
    full_raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    delta_raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )

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

    assert full_plan.pending_spells["casts"] == []
    assert delta_plan.pending_spells is not None
    assert delta_plan.pending_spells["casts"] == []
    assert any(
        entity.raw["character_birth"] is not None
        and entity.raw["character_birth"]["kind"] == 1
        for entity in full_plan.entities
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execute_at", float("inf")),
        ("player_id", 2),
        ("position_x", -1.0),
        ("sequence", 1),
    ],
)
def test_pending_delta_tamper_rejects_before_live_mutation(
    field: str,
    value: object,
) -> None:
    battle = BattleState(rng=random.Random(160_060), fast_path=True)
    _set_zap_hands(battle)
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action_space.encode_action(0, 9, 20, 0),
        action_space.no_op_action,
        0,
    )
    assert success == {0: True, 1: True}
    assert advanced == 0
    raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    tampered = copy.deepcopy(raw)
    casts = tampered["pending_spells"]["casts"]
    assert casts
    casts[0][field] = value
    before = canonical_battle_snapshot(battle)

    with pytest.raises(ResidentPublicationError, match="pending"):
        _build_direct_delta_publication_plan(
            tampered,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )
    assert canonical_battle_snapshot(battle) == before


@pytest.mark.parametrize("projection_kind", ["full", "delta"])
@pytest.mark.parametrize("tamper_kind", ["unsupported_name", "rolling_territory"])
def test_pending_spell_authority_tamper_rejects_before_live_mutation(
    projection_kind: str,
    tamper_kind: str,
) -> None:
    battle = BattleState(rng=random.Random(160_065), fast_path=True)
    card_name = "Zap" if tamper_kind == "unsupported_name" else "The Log"
    _set_single_card_hand(battle, card_name)
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action_space.encode_action(0, 9, 10, 0),
        action_space.no_op_action,
        0,
    )
    assert success == {0: True, 1: True}
    assert advanced == 0
    if projection_kind == "full":
        raw = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
    else:
        raw = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )
    tampered = copy.deepcopy(raw)
    casts = tampered["pending_spells"]["casts"]
    assert len(casts) == 1
    if tamper_kind == "unsupported_name":
        casts[0]["spell_name"] = "UnsupportedSpell"
    else:
        casts[0]["position_x"] = 9.5
        casts[0]["position_y"] = 25.5
        assert not any(
            x1 <= 9.5 < x2 and y1 <= 25.5 < y2
            for x1, y1, x2, y2 in battle.arena.get_deploy_zones(0, battle)
        )
        assert (9, 25) not in battle.arena.BLOCKED_TILES
    before = canonical_battle_snapshot(battle)

    with pytest.raises(ResidentPublicationError, match="pending"):
        if projection_kind == "full":
            _build_direct_publication_plan(
                tampered,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
        else:
            _build_direct_delta_publication_plan(
                tampered,
                battle=battle,
                resident=candidate,
                entity_registry=dict(battle.entities),
            )
    assert canonical_battle_snapshot(battle) == before


def test_the_log_alias_pending_name_and_resolution_match_python() -> None:
    battle = BattleState(rng=random.Random(160_066), fast_path=True)
    _set_single_card_hand(battle, "The Log")
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 10, 0)
    resident = ResidentRustBattle.from_battle(battle)
    actions = (action, action_space.no_op_action)

    expected_success, expected_order = _apply_python_actions(
        battle, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert [cast.spell_name for cast in battle._pending_spell_casts] == ["The Log"]
    assert json.loads(resident.pending_spell_state_bytes())["casts"][0][
        "spell_name"
    ] == "The Log"
    _assert_semantic_parity(battle, resident)

    for _ in range(28):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)


def test_due_lethal_zap_publication_rollback_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle, action = _lethal_golem_zap_battle(160_070)
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action,
        action_space.no_op_action,
        20,
    )
    assert success == {0: True, 1: True}
    assert advanced == 20
    registry: dict[int, object] = dict(battle.entities)
    causal_before = _causal_boundary_snapshot(battle)
    canonical_before = canonical_battle_snapshot(battle)
    entities_before = tuple(battle.entities.items())
    registry_before = tuple(registry.items())

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected direct-spell publication failure")

    monkeypatch.setattr(
        rust_publication,
        "_after_typed_publication_commit",
        reject_commit,
    )
    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert _causal_boundary_snapshot(battle) == causal_before
    assert canonical_battle_snapshot(battle) == canonical_before
    assert tuple(battle.entities.items()) == entities_before
    assert tuple(registry.items()) == registry_before
