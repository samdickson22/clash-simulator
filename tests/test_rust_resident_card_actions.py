from __future__ import annotations

import random

import pytest

from clasher.battle import BattleState
from clasher.card_aliases import CARD_NAME_ALIASES
from clasher.entities import Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    ResidentRustBattle,
    _single_troop_capability_reasons,
    compare_building_lifetime_phase,
    compare_character_object_phase,
    compare_clock_phase,
    compare_death_opcode_state,
    compare_ground_movement_phase,
    compare_idle_state,
    compare_locked_direct_combat_phase,
    compare_modifier_phase,
    compare_player_phase,
    compare_point_projectile_phase,
    compare_resident_entities,
    compare_resident_rng,
    compare_shield_state,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _compare_resident_state(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    compare_clock_phase(battle, resident)
    compare_player_phase(battle, resident)
    compare_locked_direct_combat_phase(battle, resident)
    compare_ground_movement_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_modifier_phase(battle, resident)
    compare_character_object_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_death_opcode_state(battle, resident)
    compare_shield_state(battle, resident)
    compare_resident_entities(battle, resident)
    compare_resident_rng(battle.rng, resident)
    compare_idle_state(battle, resident)
    assert resident.next_entity_id == battle.next_entity_id


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


def test_catalog_is_fingerprinted_immutable_and_shared_across_forks() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())
    original_fingerprint = resident.resident_catalog_fingerprint
    original_source = resident.resident_catalog_source_fingerprint
    supported = resident.resident_supported_action_cards()

    forked = resident.fork()

    assert resident.resident_catalog_schema_version == 18
    assert len(original_fingerprint) == 64
    assert len(original_source) == 64
    assert supported
    assert forked.resident_catalog_fingerprint == original_fingerprint
    assert forked.resident_catalog_source_fingerprint == original_source
    assert forked.resident_supported_action_cards() == supported
    assert resident.resident_catalog_strong_count == 2
    assert forked.resident_catalog_strong_count == 2


def test_joint_single_troop_actions_match_python_and_continue_in_lockstep() -> None:
    battle = BattleState(rng=random.Random(81_231))
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    supported = set(resident.resident_supported_action_cards())
    assert all(card in supported for card in (battle.players[0].hand[0], battle.players[1].hand[0]))
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 9, 21, 1),
    )

    expected_success, expected_order = _apply_python_joint_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == expected_order
    assert actual_success == expected_success == {0: True, 1: True}
    _compare_resident_state(battle, resident)
    for _ in range(5):
        assert resident.supports_complete_tick
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _compare_resident_state(battle, resident)


def test_every_capability_qualified_template_matches_fresh_python_deployment() -> None:
    supported = ResidentRustBattle.from_battle(
        BattleState()
    ).resident_supported_action_cards()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    for index, card_name in enumerate(supported):
        battle = BattleState(rng=random.Random(82_000 + index))
        battle.players[0].hand = [card_name, None, None, None]
        battle.players[0].elixir = battle.players[0].max_elixir
        resident = ResidentRustBattle.from_battle(battle)
        actions = (action, action_space.no_op_action)

        expected_success, expected_order = _apply_python_joint_actions(battle, actions)
        actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

        assert actual_order == expected_order
        assert actual_success == expected_success == {0: True, 1: True}
        _compare_resident_state(battle, resident)
        assert resident.supports_complete_tick


def test_alias_and_duplicate_hand_use_first_matching_slot_exactly() -> None:
    probe = ResidentRustBattle.from_battle(BattleState())
    supported = set(probe.resident_supported_action_cards())
    alias = next(
        alias
        for alias, target in sorted(CARD_NAME_ALIASES.items())
        if alias != target and alias in supported
    )
    battle = BattleState(rng=random.Random(81_232))
    battle.players[0].hand = [alias, alias, None, None]
    battle.players[0].cycle_queue.clear()
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(1, 8, 10, 0),
        action_space.no_op_action,
    )

    expected_success, expected_order = _apply_python_joint_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == expected_order
    assert actual_success == expected_success == {0: True, 1: True}
    assert battle.players[0].hand == [None, alias, None, None]
    assert tuple(battle.players[0].cycle_queue) == (alias,)
    _compare_resident_state(battle, resident)


def test_unsupported_card_rejects_transaction_before_rng_or_player_mutation() -> None:
    battle = BattleState(rng=random.Random(81_233))
    definitions = battle.card_loader.load_card_definitions()
    unsupported = next(
        name
        for name, definition in sorted(definitions.items())
        if (stats := battle.card_loader.get_card(name)) is not None
        and _single_troop_capability_reasons(stats, definition)
    )
    battle.players[0].hand[0] = unsupported
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    before_rng = resident.rng_state_bytes()
    before_players = resident.player_states()
    before_entities = resident.entity_state_bytes()
    before_next_id = resident.next_entity_id

    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(action, action_space.no_op_action)

    assert resident.rng_state_bytes() == before_rng
    assert resident.player_states() == before_players
    assert resident.entity_state_bytes() == before_entities
    assert resident.next_entity_id == before_next_id
    assert resident.checkpoint_is_current


def test_nonstandard_arena_rejects_supported_action_before_shuffle() -> None:
    battle = BattleState(rng=random.Random(81_235))
    battle.arena.width = 19
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    before_rng = resident.rng_state_bytes()
    before_players = resident.player_states()

    with pytest.raises(RuntimeError, match="standard 18x32 arena"):
        resident.apply_resident_joint_actions(action, action_space.no_op_action)

    assert resident.rng_state_bytes() == before_rng
    assert resident.player_states() == before_players
    assert resident.checkpoint_is_current


def test_invalid_placement_and_invalid_action_still_match_shuffle_semantics() -> None:
    battle = BattleState(rng=random.Random(81_234))
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 0, 0, 0),
        action_space.num_actions + 17,
    )

    expected_success, expected_order = _apply_python_joint_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == expected_order
    assert actual_success == expected_success == {0: False, 1: False}
    _compare_resident_state(battle, resident)


@pytest.mark.parametrize(
    ("card_name", "count", "stagger_ms"),
    [("Archers", 2, 100), ("Minions", 3, 100), ("Skeletons", 3, 0)],
)
@pytest.mark.parametrize("player_id", [0, 1])
@pytest.mark.parametrize("world_x", [5, 12])
def test_primary_formations_match_both_players_and_native_lanes(
    card_name: str,
    count: int,
    stagger_ms: int,
    player_id: int,
    world_x: int,
) -> None:
    battle = BattleState(rng=random.Random(83_000 + player_id * 100 + world_x))
    battle.players[player_id].hand = [card_name, None, None, None]
    battle.players[player_id].elixir = battle.players[player_id].max_elixir
    initial_ids = set(battle.entities)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    world_y = 10 if player_id == 0 else 21
    action = action_space.encode_action(0, world_x, world_y, player_id)
    actions = (
        action if player_id == 0 else action_space.no_op_action,
        action if player_id == 1 else action_space.no_op_action,
    )

    expected_success, expected_order = _apply_python_joint_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == expected_order
    assert actual_success == expected_success == {0: True, 1: True}
    spawned = [
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in initial_ids and isinstance(entity, Troop)
    ]
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    assert len(spawned) == count
    assert [entity.card_stats.name for entity in spawned] == [stats.name] * count
    assert [entity.id for entity in spawned] == list(
        range(min(entity.id for entity in spawned), battle.next_entity_id)
    )
    assert [entity.deploy_delay_remaining for entity in spawned] == pytest.approx(
        [1.0 + index * stagger_ms / 1000.0 for index in range(count)]
    )
    assert all(entity.placement_pending for entity in spawned)
    assert all(entity._spawn_hook_pending for entity in spawned)
    assert not any(getattr(entity, "_spawn_hook_fired", False) for entity in spawned)
    _compare_resident_state(battle, resident)

    for _ in range(5):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _compare_resident_state(battle, resident)


def test_primary_formation_children_clamp_and_cross_terrain_without_relocation() -> None:
    battle = BattleState(rng=random.Random(83_101))
    battle.players[0].hand = ["Skeletons", None, None, None]
    battle.players[0].elixir = battle.players[0].max_elixir
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    river_action = action_space.encode_action(0, 9, 14, 0)

    expected_success, expected_order = _apply_python_joint_actions(
        battle, (river_action, action_space.no_op_action)
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(
        river_action, action_space.no_op_action
    )

    assert actual_order == expected_order
    assert actual_success == expected_success == {0: True, 1: True}
    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeletons"
    ]
    assert len(skeletons) == 3
    assert any(not battle.arena.is_walkable(entity.position) for entity in skeletons)
    _compare_resident_state(battle, resident)

    edge = BattleState(rng=random.Random(83_102))
    edge.players[0].hand = ["Archers", None, None, None]
    edge.players[0].elixir = edge.players[0].max_elixir
    edge_resident = ResidentRustBattle.from_battle(edge)
    edge_action = action_space.encode_action(0, 0, 10, 0)
    expected_success, expected_order = _apply_python_joint_actions(
        edge, (edge_action, action_space.no_op_action)
    )
    actual_success, actual_order = edge_resident.apply_resident_joint_actions(
        edge_action, action_space.no_op_action
    )
    assert actual_order == expected_order
    assert actual_success == expected_success == {0: True, 1: True}
    archers = [
        entity
        for entity in edge.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Archer"
    ]
    assert min(tiles_to_logic_units(entity.position.x) for entity in archers) == 250
    _compare_resident_state(edge, edge_resident)


def test_multi_formation_id_headroom_rejects_before_joint_shuffle() -> None:
    battle = BattleState(rng=random.Random(83_103))
    for player in battle.players:
        player.hand = ["Skeletons", None, None, None]
        player.elixir = player.max_elixir
    battle.next_entity_id = (1 << 63) - 1 - 5
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 9, 21, 1),
    )
    before = (
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.rng_state_bytes(),
        resident.next_entity_id,
        resident.checkpoint_is_current,
    )

    with pytest.raises(RuntimeError, match="entity-ID allocation headroom"):
        resident.apply_resident_joint_actions(*actions)

    assert (
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.rng_state_bytes(),
        resident.next_entity_id,
        resident.checkpoint_is_current,
    ) == before
