from __future__ import annotations

import json
import random
from collections import deque

import numpy as np
import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import ResidentRustBattle, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    publish_complete_tick_state,
)
from clasher.rust_runtime import _causal_boundary_snapshot

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)

QUALIFIED_BUILDINGS = (
    "BarbarianLauncher",
    "Cannon",
    "Elixir Collector",
    "FirespiritHut",
    "GoblinDrill",
    "InfernoTower",
    "Mortar",
    "X-Bow",
    "Xbow",
)
SUPPORTED_DECK = (
    "Archers",
    "Arrows",
    "Fireball",
    "Giant",
    "Knight",
    "MiniPekka",
    "Minions",
    "Musketeer",
)


def _set_supported_decks(battle: BattleState) -> None:
    for player in battle.players:
        player.hand = list(SUPPORTED_DECK[:4])
        player.cycle_queue = deque(SUPPORTED_DECK[4:])
        player.elixir = player.max_elixir


def _apply_python_joint_actions(
    battle: BattleState,
    actions: tuple[int, int],
) -> tuple[dict[int, bool], tuple[int, int]]:
    action_space = DiscreteTileActionSpace()
    order = [0, 1]
    battle.rng.shuffle(order)
    successes: dict[int, bool] = {}
    for player_id in order:
        successes[player_id] = action_space.apply_action(
            battle,
            player_id,
            actions[player_id],
        )
    return successes, (order[0], order[1])


def _dead_left_tower(battle: BattleState, player_id: int) -> None:
    battle.players[player_id].left_tower_hp = 0.0
    tower = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == player_id
        and entity._crown_tower_slot == "left"
    )
    tower.hitpoints = 0.0


def test_catalog_building_qualification_is_data_driven() -> None:
    battle = BattleState()
    resident = ResidentRustBattle.from_battle(battle)
    supported = set(resident.resident_supported_action_cards())
    definitions = battle.card_loader.load_card_definitions()
    building_lookups = {
        name
        for name, definition in definitions.items()
        if str(definition.kind).casefold() == "building"
    }
    building_lookups.add("X-Bow")

    assert supported & building_lookups == set(QUALIFIED_BUILDINGS)
    for card_name in ("BombTower", "Tesla", "Tombstone"):
        assert "executable_mechanics" in (
            resident.resident_action_card_capability_reasons(card_name)
        )
    assert "missing_character_data" in (
        resident.resident_action_card_capability_reasons("GoblinRocketSilo")
    )


@pytest.mark.parametrize(
    ("tamper", "expected_reason"),
    [
        ("action_kind", "native_formation_preflight"),
        ("footprint", "native_ordinary_building_preflight"),
        ("unit_mass", "native_ordinary_building_preflight"),
    ],
)
def test_catalog_rejects_building_action_kind_and_footprint_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
    expected_reason: str,
) -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()),
        data_stat.st_mtime_ns,
        data_stat.st_size,
    )
    payload = json.loads(bundle.payload)
    cannon = next(
        card for card in payload["cards"] if card["lookup_name"] == "Cannon"
    )
    if tamper == "action_kind":
        cannon["action_kind"] = "troop"
        cannon["building_footprint_size"] = None
    elif tamper == "footprint":
        cannon["building_footprint_size"] = 2
    else:
        fields = cannon["template_snapshot"]["$object"]["fields"]
        fields["_unit_mass"] = {"$float": "0x0.0p+0"}
        cannon["template_fingerprint"] = rust_core._canonical_json_sha256(
            cannon["template_snapshot"]
        )
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii"),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
    )
    monkeypatch.setattr(
        rust_core,
        "_resident_card_catalog_bundle",
        lambda *_args: tampered,
    )

    if tamper == "unit_mass":
        _set_supported_decks(battle)
        battle.players[0].hand[0] = "Cannon"
    resident = ResidentRustBattle.from_battle(battle)

    assert expected_reason in (
        resident.resident_action_card_capability_reasons("Cannon")
    )
    if tamper == "unit_mass":
        before = (
            resident.rng_state_bytes(),
            resident.player_states(),
            resident.entity_state_bytes(),
            resident.next_entity_id,
        )
        action = DiscreteTileActionSpace().encode_action(0, 8, 10, 0)
        with pytest.raises(RuntimeError, match="unsupported hand card"):
            resident.apply_resident_joint_actions(
                action,
                DiscreteTileActionSpace().no_op_action,
            )
        assert (
            resident.rng_state_bytes(),
            resident.player_states(),
            resident.entity_state_bytes(),
            resident.next_entity_id,
        ) == before


@pytest.mark.parametrize("card_name", QUALIFIED_BUILDINGS)
@pytest.mark.parametrize("player_id", [0, 1])
def test_building_legal_ids_match_scalar_and_fast_masks(
    card_name: str,
    player_id: int,
) -> None:
    battle = BattleState(fast_path=True)
    _set_supported_decks(battle)
    battle.players[player_id].hand[0] = card_name
    action_space = DiscreteTileActionSpace()
    resident = ResidentRustBattle.from_battle(battle)

    scalar = np.flatnonzero(
        action_space.legal_action_mask(battle, player_id, fast_path=False)
    )
    fast = np.flatnonzero(
        action_space.legal_action_mask(battle, player_id, fast_path=True)
    )
    native = np.asarray(resident.resident_legal_action_ids(player_id))

    np.testing.assert_array_equal(fast, scalar)
    np.testing.assert_array_equal(native, scalar)


def test_building_footprint_edge_touch_dead_release_and_payload_tangent() -> None:
    action_space = DiscreteTileActionSpace()
    battle = BattleState(fast_path=True)
    _set_supported_decks(battle)
    battle.players[0].hand[0] = "Cannon"
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    existing = battle._spawn_entity(Building, Position(8.5, 10.5), 1, stats)
    overlap = action_space.encode_action(0, 10, 10, 0)
    edge_touch = action_space.encode_action(0, 11, 10, 0)

    resident = ResidentRustBattle.from_battle(battle)
    legal = set(resident.resident_legal_action_ids(0))
    assert overlap not in legal
    assert edge_touch in legal

    existing.hitpoints = 0.0
    existing.is_alive = False
    resident = ResidentRustBattle.from_battle(battle)
    assert overlap in set(resident.resident_legal_action_ids(0))

    troop_stats = battle.card_loader.get_card("Knight")
    assert troop_stats is not None
    battle._spawn_unit_at_position(Position(12.500000001, 10.5), 1, troop_stats)
    blocker = next(
        entity
        for entity in reversed(tuple(battle.entities.values()))
        if isinstance(entity, Troop)
    )
    blocker.__dict__["blocks_deployment"] = True
    blocker.__dict__["deployment_collision_radius"] = 0.5
    resident = ResidentRustBattle.from_battle(battle)
    assert overlap not in set(resident.resident_legal_action_ids(0))

    blocker.position.x += 1e-8
    resident = ResidentRustBattle.from_battle(battle)
    assert overlap in set(resident.resident_legal_action_ids(0))


@pytest.mark.parametrize(
    ("existing_name", "expected_raw_radius", "overlap_world_x", "touch_world_x"),
    [
        ("GoblinRocketSilo", None, 10, 11),
        ("GoblinDrill", 0.0, 9, 10),
    ],
)
def test_existing_building_none_vs_zero_radius_matches_all_placement_paths(
    existing_name: str,
    expected_raw_radius: float | None,
    overlap_world_x: int,
    touch_world_x: int,
) -> None:
    battle = BattleState(fast_path=True)
    _set_supported_decks(battle)
    battle.players[0].hand[0] = "Cannon"
    existing_stats = battle.card_loader.get_card(existing_name)
    assert existing_stats is not None
    assert getattr(existing_stats, "collision_radius", None) == expected_raw_radius
    battle._spawn_entity(Building, Position(8.5, 10.5), 1, existing_stats)
    action_space = DiscreteTileActionSpace()
    overlap = action_space.encode_action(0, overlap_world_x, 10, 0)
    edge_touch = action_space.encode_action(0, touch_world_x, 10, 0)

    scalar = np.flatnonzero(
        action_space.legal_action_mask(battle, 0, fast_path=False)
    )
    fast = np.flatnonzero(action_space.legal_action_mask(battle, 0, fast_path=True))
    native = np.asarray(
        ResidentRustBattle.from_battle(battle).resident_legal_action_ids(0)
    )

    np.testing.assert_array_equal(fast, scalar)
    np.testing.assert_array_equal(native, scalar)
    legal = set(map(int, scalar))
    assert overlap not in legal
    assert edge_touch in legal


def test_joint_same_tile_buildings_observe_first_inserted_footprint() -> None:
    battle = BattleState(rng=random.Random(144_001), fast_path=True)
    _set_supported_decks(battle)
    for player in battle.players:
        player.hand[0] = "Cannon"
    _dead_left_tower(battle, 1)
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    world_x, world_y = 8, 18
    actions = (
        action_space.encode_action(0, world_x, world_y, 0),
        action_space.encode_action(0, world_x, world_y, 1),
    )
    resident = ResidentRustBattle.from_battle(battle)

    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == expected_order
    assert actual_success == expected_success
    assert sum(actual_success.values()) == 1
    assert resident.next_entity_id == battle.next_entity_id + 1
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )


@pytest.mark.parametrize(
    ("seed", "expected_success"),
    [(0, {0: True, 1: False}), (1, {0: True, 1: True})],
)
def test_joint_building_vs_troop_uses_ordered_asymmetric_placement(
    seed: int,
    expected_success: dict[int, bool],
) -> None:
    battle = BattleState(rng=random.Random(seed), fast_path=True)
    _set_supported_decks(battle)
    battle.players[0].hand[0] = "Cannon"
    battle.players[1].hand[0] = "Knight"
    _dead_left_tower(battle, 1)
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 18, 0),
        action_space.encode_action(0, 8, 18, 1),
    )
    resident = ResidentRustBattle.from_battle(battle)

    python_success, python_order = _apply_python_joint_actions(control, actions)
    rust_success, rust_order = resident.apply_resident_joint_actions(*actions)

    assert python_order == rust_order
    assert python_success == rust_success == expected_success
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )


@pytest.mark.parametrize("card_name", ["Cannon", "X-Bow", "Xbow"])
@pytest.mark.parametrize("player_id", [0, 1])
@pytest.mark.parametrize("ticks", [0, 8])
def test_building_action_publication_matches_python_boundary_and_future(
    card_name: str,
    player_id: int,
    ticks: int,
) -> None:
    battle = BattleState(rng=random.Random(144_100 + ticks + player_id), fast_path=True)
    _set_supported_decks(battle)
    battle.players[player_id].hand[0] = card_name
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10 if player_id == 0 else 21, player_id)
    actions = (
        action if player_id == 0 else action_space.no_op_action,
        action if player_id == 1 else action_space.no_op_action,
    )
    prior = ResidentRustBattle.from_battle(battle)
    prior_entities = prior.entity_state_bytes()
    prior_rng = prior.rng_state_bytes()
    candidate = prior.fork()

    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    actual_success, actual_order = candidate.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert prior.entity_state_bytes() == prior_entities
    assert prior.rng_state_bytes() == prior_rng
    if ticks:
        assert candidate.advance_complete_ticks(ticks) == control.step_logic_ticks(ticks)

    registry: dict[int, object] = dict(battle.entities)
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )

    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert _causal_boundary_snapshot(battle) == _causal_boundary_snapshot(control)
    assert battle.rng.getstate() == control.rng.getstate()
    for consumer_player_id in (0, 1):
        for fast_path in (False, True):
            np.testing.assert_array_equal(
                action_space.legal_action_mask(
                    battle,
                    consumer_player_id,
                    fast_path=fast_path,
                ),
                action_space.legal_action_mask(
                    control,
                    consumer_player_id,
                    fast_path=fast_path,
                ),
            )
    born = registry[max(registry)]
    assert type(born) is Building
    assert born.card_stats is battle.card_loader.get_card(card_name)

    native_advanced = candidate.advance_complete_tick()
    control_advanced = control.step_logic_ticks(1)
    published_advanced = battle.step_logic_ticks(1)
    assert native_advanced == control_advanced == published_advanced
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert rust_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_building_alias_duplicate_consumes_first_literal_and_cycles_alias() -> None:
    battle = BattleState(rng=random.Random(144_200))
    _set_supported_decks(battle)
    battle.players[0].hand[:2] = ["X-Bow", "X-Bow"]
    battle.players[0].cycle_queue.clear()
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(1, 8, 10, 0)
    actions = (action, action_space.no_op_action)

    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert control.players[0].hand[:2] == [None, "X-Bow"]
    assert tuple(control.players[0].cycle_queue) == ("X-Bow",)
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )


@pytest.mark.parametrize(("card_name", "ticks"), [("Cannon", 60), ("Xbow", 100)])
def test_building_deployment_combat_and_projectile_continuation(
    card_name: str,
    ticks: int,
) -> None:
    battle = BattleState(rng=random.Random(144_250), fast_path=True)
    _set_supported_decks(battle)
    battle.players[0].hand[0] = card_name
    knight_stats = battle.card_loader.get_card("Knight")
    assert knight_stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(8.5, 14.5), 1, knight_stats)
    knight = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    knight.deploy_delay_remaining = 0.0
    knight.placement_pending = False
    knight._spawn_hook_pending = False
    knight._spawn_hook_fired = True
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    actions = (action, action_space.no_op_action)
    first_birth_id = battle.next_entity_id

    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert resident.advance_complete_ticks(ticks) == control.step_logic_ticks(ticks)

    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    building = control.entities[first_birth_id]
    assert isinstance(building, Building)
    assert building.deploy_delay_remaining == 0.0
    assert control.next_entity_id > first_birth_id + 1


def test_unsupported_building_preflight_fails_before_rng_or_state_mutation() -> None:
    action_space = DiscreteTileActionSpace()
    battle = BattleState(rng=random.Random(144_300))
    _set_supported_decks(battle)
    battle.players[0].hand[0] = "BombTower"
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    )
    action = action_space.encode_action(0, 8, 10, 0)

    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(action, action_space.no_op_action)

    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    ) == before


def test_two_building_allocations_reject_i64_headroom_before_rng_or_state_mutation() -> None:
    action_space = DiscreteTileActionSpace()
    battle = BattleState(rng=random.Random(144_301))
    _set_supported_decks(battle)
    for player in battle.players:
        player.hand[0] = "Cannon"
    battle.next_entity_id = (1 << 63) - 2
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    )
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 8, 21, 1),
    )

    with pytest.raises(RuntimeError, match="allocation headroom"):
        resident.apply_resident_joint_actions(*actions)

    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    ) == before


def test_building_birth_commit_failure_rolls_back_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(144_400), fast_path=True)
    _set_supported_decks(battle)
    battle.players[0].hand[0] = "Cannon"
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    candidate.apply_resident_joint_actions(action, action_space.no_op_action)
    before = _causal_boundary_snapshot(battle)
    entities_before = tuple(battle.entities.items())
    cache_before = tuple(battle.card_loader._cards.items())
    registry: dict[int, object] = dict(battle.entities)

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected building commit failure")

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

    assert _causal_boundary_snapshot(battle) == before
    assert tuple(battle.entities.items()) == entities_before
    assert tuple(battle.card_loader._cards.items()) == cache_before
    assert tuple(registry.items()) == entities_before
