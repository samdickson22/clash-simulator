from __future__ import annotations

import copy
import json
import random
from collections import deque
from dataclasses import replace
from typing import Any, cast

import numpy as np
import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot, first_snapshot_difference
from clasher.entities import SpawnProjectile, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_DELTA_CONSUMER,
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
)
from clasher.rust_runtime import ResidentCompleteTickRuntime
from clasher.spells import SPELL_REGISTRY

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _set_card_hands(battle: BattleState, player_id: int, card_name: str) -> None:
    for candidate_id, player in enumerate(battle.players):
        name = card_name if candidate_id == player_id else "Knight"
        player.hand = [name] * 4
        player.deck = [name] * 8
        player.cycle_queue = deque(player.deck[4:])
        player.elixir = player.max_elixir


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
    difference = first_snapshot_difference(
        python_resident_semantic_snapshot(battle),
        rust_resident_semantic_snapshot(resident),
    )
    assert difference is None, difference


def _catalog_bundle(battle: BattleState) -> rust_core._ResidentCardCatalogBundle:
    path = battle.card_loader.data_file
    stat = path.stat()
    return rust_core._resident_card_catalog_bundle(
        str(path.resolve()), stat.st_mtime_ns, stat.st_size
    )


def test_spawn_projectile_catalog_is_structural_and_attests_inherited_payload() -> None:
    battle = BattleState()
    bundle = _catalog_bundle(battle)
    payload = json.loads(bundle.payload)
    rows = {
        row["lookup_name"]: row
        for row in payload["cards"]
        if row["action_kind"] == "spawn_projectile_spell"
    }

    assert payload["schema_version"] == 13
    assert set(rows) == {"GoblinBarrel", "Royal Delivery", "RoyalDelivery"}
    assert all(not row["capability_reasons"] for row in rows.values())
    assert rows["Royal Delivery"]["effective_name"] == "RoyalDelivery"
    assert rows["GoblinBarrel"]["spawn_projectile_spell"]["spawn_radius"] is None
    assert rows["RoyalDelivery"]["spawn_projectile_spell"]["spawn_radius"] == 0.0
    for row in rows.values():
        spell = row["spawn_projectile_spell"]
        assert spell["damage_waves"] == spell["multiple_projectiles"] == 1
        assert spell["projectile_pattern"] == "native_radial"
        assert not spell["pierces"]
        assert not spell["homing"]
        assert not spell["spawn_projectile_data_present"]


@pytest.mark.parametrize(
    ("card_name", "field", "value"),
    [
        ("GoblinBarrel", "homing", True),
        ("GoblinBarrel", "damage_waves", 2),
        ("GoblinBarrel", "stun_duration", 0.5),
        ("GoblinBarrel", "spawn_projectile_data_present", True),
        ("GoblinBarrel", "activation_delay", 2.05),
        ("GoblinBarrel", "ignore_buildings", True),
        ("RoyalDelivery", "spawn_radius", None),
        ("RoyalDelivery", "spawn_const_priority", True),
    ],
)
def test_spawn_projectile_catalog_rejects_inherited_projectile_tamper(
    monkeypatch: pytest.MonkeyPatch,
    card_name: str,
    field: str,
    value: object,
) -> None:
    battle = BattleState(rng=random.Random(170_001))
    bundle = _catalog_bundle(battle)
    payload = json.loads(bundle.payload)
    row = next(
        item for item in payload["cards"] if item["lookup_name"] == card_name
    )
    row["spawn_projectile_spell"][field] = value
    tampered = replace(
        bundle,
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "ascii"
        ),
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)
    before = canonical_battle_snapshot(battle)

    resident = ResidentRustBattle.from_battle(battle)

    assert canonical_battle_snapshot(battle) == before
    assert "native_spawn_projectile_spell_preflight" in (
        resident.resident_action_card_capability_reasons(card_name)
    )
    assert card_name not in resident.resident_supported_action_cards()


@pytest.mark.parametrize(
    ("card_name", "extra_fields", "expected"),
    [
        (
            "GoblinBarrel",
            {"impact_delay": 2.05, "ignore_buildings": True},
            {"activation_delay": 0.0, "ignore_buildings": False},
        ),
        (
            "RoyalDelivery",
            {"spawn_radius": None, "spawn_const_priority": True},
            {"spawn_radius": 0.0, "spawn_const_priority": False},
        ),
    ],
)
def test_spawn_projectile_catalog_ignores_cross_class_runtime_attributes(
    monkeypatch: pytest.MonkeyPatch,
    card_name: str,
    extra_fields: dict[str, object],
    expected: dict[str, object],
) -> None:
    battle = BattleState()
    spell = copy.deepcopy(SPELL_REGISTRY[card_name])
    for field, value in extra_fields.items():
        setattr(spell, field, value)
    registry = cast(Any, SPELL_REGISTRY)._get_registry()
    monkeypatch.setitem(registry, card_name, spell)
    path = battle.card_loader.data_file
    stat = path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(path.resolve()),
        stat.st_mtime_ns + (17 if card_name == "GoblinBarrel" else 18),
        stat.st_size,
    )
    row = next(
        item
        for item in json.loads(bundle.payload)["cards"]
        if item["lookup_name"] == card_name
    )["spawn_projectile_spell"]

    for field, value in expected.items():
        assert row[field] == value


@pytest.mark.parametrize(
    ("player_id", "card_name"),
    [
        (0, "GoblinBarrel"),
        (1, "GoblinBarrel"),
        (0, "Royal Delivery"),
        (1, "RoyalDelivery"),
    ],
)
def test_spawn_projectile_legal_ids_match_scalar_and_fast_masks(
    player_id: int,
    card_name: str,
) -> None:
    battle = BattleState(rng=random.Random(170_010 + player_id))
    _set_card_hands(battle, player_id, card_name)
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


@pytest.mark.parametrize(
    ("player_id", "card_name", "tile_y", "child_name", "child_delay"),
    [
        (0, "GoblinBarrel", 20, "Goblin", 1.05),
        (1, "Royal Delivery", 21, "DeliveryRecruit", 0.20),
    ],
)
def test_spawn_projectile_action_and_object_trace_matches_python(
    player_id: int,
    card_name: str,
    tile_y: int,
    child_name: str,
    child_delay: float,
) -> None:
    battle = BattleState(rng=random.Random(170_020 + player_id))
    _set_card_hands(battle, player_id, card_name)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, tile_y, player_id)
    actions = (
        (action, action_space.no_op_action)
        if player_id == 0
        else (action_space.no_op_action, action)
    )
    resident = ResidentRustBattle.from_battle(battle)

    expected_success, expected_order = _apply_python_actions(
        battle, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert [cast.spell_name for cast in battle._pending_spell_casts] == [card_name]
    _assert_semantic_parity(battle, resident)

    carrier_id = battle.next_entity_id
    for tick in range(1, 90):
        battle._step_logic_tick(refresh_fast_path_end=False)
        assert resident.advance_complete_tick()
        _assert_semantic_parity(battle, resident)
        if tick == 20:
            carrier = battle.entities[carrier_id]
            assert type(carrier) is SpawnProjectile
            assert carrier.time_alive == 0.0
        children = [
            entity
            for entity in battle.entities.values()
            if type(entity) is Troop and str(entity.card_stats.name) == child_name
        ]
        if not children:
            continue
        assert all(
            child.deploy_delay_remaining == pytest.approx(child_delay)
            for child in children
        )
        assert carrier_id not in battle.entities
        if child_name == "Goblin":
            assert len(children) == 3
            assert children[0].card_stats is children[1].card_stats
            assert children[1].card_stats is children[2].card_stats
            assert len({id(child.mechanics) for child in children}) == 3
        else:
            # 20 command ticks plus the exact 41 carrier object updates.
            assert tick == 61
            assert len(children) == 1
        break
    else:  # pragma: no cover - fixture invariant
        raise AssertionError("spawn-projectile carrier did not create its children")


def test_spawn_projectile_helper_leaves_carrier_for_object_phase() -> None:
    battle = BattleState(rng=random.Random(170_025))
    assert SPELL_REGISTRY["Fireball"].cast(battle, 0, Position(9, 20))
    assert SPELL_REGISTRY["GoblinBarrel"].cast(battle, 0, Position(9, 20))
    resident = ResidentRustBattle.from_battle(battle)
    before = json.loads(resident.point_projectile_state_bytes())

    assert resident.supports_point_projectile_phase
    resident.advance_point_projectile_phase()
    after = json.loads(resident.point_projectile_state_bytes())
    ordinary_before = next(row for row in before if row["spawn_projectile_state"] is None)
    ordinary_after = next(row for row in after if row["spawn_projectile_state"] is None)
    carrier_before = next(row for row in before if row["spawn_projectile_state"])
    carrier_after = next(row for row in after if row["spawn_projectile_state"])

    assert ordinary_after["position_y"] != ordinary_before["position_y"]
    assert carrier_after == carrier_before


def test_royal_impact_death_callbacks_precede_delivery_recruit() -> None:
    battle = BattleState(rng=random.Random(170_026), fast_path=True)
    stats = battle.card_loader.get_card("Golem")
    assert stats is not None
    golem = battle._spawn_entity(Troop, Position(9.0, 10.0), 1, stats)
    golem.deploy_delay_remaining = 0.0
    golem.placement_delay_total = 0.0
    golem.placement_pending = False
    golem._spawn_hook_pending = False
    golem._spawn_hook_fired = True
    golem.hitpoints = 1
    assert SPELL_REGISTRY["RoyalDelivery"].cast(
        battle, 0, Position(9.0, 10.0)
    )
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(41):
        battle._step_logic_tick(refresh_fast_path_end=False)
        assert resident.advance_complete_tick()
        _assert_semantic_parity(battle, resident)

    recruit = next(
        entity
        for entity in battle.entities.values()
        if type(entity) is Troop and str(entity.card_stats.name) == "DeliveryRecruit"
    )
    assert recruit.hitpoints == recruit.max_hitpoints
    assert recruit.deploy_delay_remaining == pytest.approx(0.20)
    assert len(
        [
            entity
            for entity in battle.entities.values()
            if type(entity) is Troop and str(entity.card_stats.name) == "Golemite"
        ]
    ) == 2


@pytest.mark.parametrize(
    ("card_name", "tile_y"),
    [("GoblinBarrel", 20), ("Royal Delivery", 10)],
)
def test_spawn_projectile_action_matches_off_shadow_on(
    card_name: str,
    tile_y: int,
) -> None:
    base = BattleState(rng=random.Random(170_030), fast_path=True)
    _set_card_hands(base, 0, card_name)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, tile_y, 0)
    actions = (action, action_space.no_op_action)
    off = base.clone()
    shadow_battle = base.clone()
    on_battle = base.clone()
    expected_success, expected_order = _apply_python_actions(
        off, action_space, actions
    )
    assert off.step_logic_ticks(70) == 70
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

    shadow_result = shadow.apply_joint_actions_and_advance(*actions, 70)
    on_result = on.apply_joint_actions_and_advance(*actions, 70)

    assert shadow_result.action_success == on_result.action_success == expected_success
    assert shadow_result.action_order == on_result.action_order == expected_order
    assert canonical_battle_snapshot(shadow_battle) == canonical_battle_snapshot(off)
    assert canonical_battle_snapshot(on_battle) == canonical_battle_snapshot(off)
    assert shadow.status.shadow_mismatches == 0


def test_royal_delivery_alias_pending_publication_reuses_identity_at_0_1_8_ticks() -> None:
    base = BattleState(rng=random.Random(170_035), fast_path=True)
    _set_card_hands(base, 0, "Royal Delivery")
    control = base.clone()
    battle = base.clone()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 10, 0)
    actions = (action, action_space.no_op_action)
    expected_success, expected_order = _apply_python_actions(
        control, action_space, actions
    )
    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )

    result = runtime.apply_joint_actions_and_advance(*actions, 0)
    assert result.action_success == expected_success
    assert result.action_order == expected_order
    assert canonical_battle_snapshot(battle) == canonical_battle_snapshot(control)
    pending = battle._pending_spell_casts
    cast = pending[0]
    position = cast.position
    assert cast.spell_name == "Royal Delivery"

    for ticks in (1, 8):
        assert runtime.advance_ticks(ticks) == control.step_logic_ticks(ticks) == ticks
        assert canonical_battle_snapshot(battle) == canonical_battle_snapshot(control)
        assert battle._pending_spell_casts is pending
        assert battle._pending_spell_casts[0] is cast
        assert battle._pending_spell_casts[0].position is position


@pytest.mark.parametrize("tamper", ["child_fingerprint", "nested_slow"])
def test_spawn_projectile_delta_tamper_rejects_before_mutation(
    tamper: str,
) -> None:
    battle = BattleState(rng=random.Random(170_040), fast_path=True)
    assert SPELL_REGISTRY["RoyalDelivery"].cast(battle, 0, Position(9.0, 10.0))
    prior = ResidentRustBattle.from_battle(battle)
    for _ in range(40):
        assert prior.advance_complete_tick()
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    tampered = copy.deepcopy(raw)
    child = next(change["full"] for change in tampered["entities"] if change["full"])
    if tamper == "child_fingerprint":
        child["character_birth"]["template_fingerprint"] = "0" * 64
    else:
        carrier_change = next(
            change
            for change in tampered["entities"]
            if change["point_projectile_state"] is not None
        )
        carrier_change["point_projectile_state"]["slow_duration"] = 0.5
    before = canonical_battle_snapshot(battle)

    with pytest.raises(ResidentPublicationError):
        _build_direct_delta_publication_plan(
            tampered,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    assert canonical_battle_snapshot(battle) == before


def test_spawn_projectile_publication_failure_rolls_back_child_and_carrier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(170_050), fast_path=True)
    carrier_id = battle.next_entity_id
    assert SPELL_REGISTRY["RoyalDelivery"].cast(battle, 0, Position(9.0, 10.0))
    carrier = battle.entities[carrier_id]
    assert type(carrier) is SpawnProjectile
    carrier.time_alive = carrier.activation_delay
    before = canonical_battle_snapshot(battle)
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected spawn-projectile commit failure")

    monkeypatch.setattr(
        rust_publication,
        "_after_typed_publication_commit",
        reject_commit,
    )
    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert canonical_battle_snapshot(battle) == before
    assert battle.entities[carrier_id] is carrier
    assert runtime.entity_registry[carrier_id] is carrier
    assert set(runtime.entity_registry) == set(battle.entities)
