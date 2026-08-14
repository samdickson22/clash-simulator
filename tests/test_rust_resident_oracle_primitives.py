from __future__ import annotations

import random
from collections import deque
from typing import Any

import numpy as np
import pytest

from clasher.arena import Position, TileGrid
from clasher.battle import BattleState
from clasher.entities import Building, Troop
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


def _supported_unique_deck(battle: BattleState) -> list[str]:
    probe = ResidentRustBattle.from_battle(battle)
    deck: list[str] = []
    effective_names: set[str] = set()
    for name in probe.resident_supported_action_cards():
        stats = battle.card_loader.get_card(name)
        assert stats is not None
        if stats.name in effective_names:
            continue
        effective_names.add(stats.name)
        deck.append(name)
        if len(deck) == 8:
            break
    assert len(deck) == 8
    return deck


def _oracle_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    deck = _supported_unique_deck(battle)
    for player in battle.players:
        hand: list[str | None] = list(deck[:4])
        player.hand = hand
        player.deck = deck.copy()
        player.cycle_queue = deque(deck[4:])
        player.elixir = player.max_elixir
    return battle


def _resident_state(resident: ResidentRustBattle) -> tuple[Any, ...]:
    return (
        resident.clock_state(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.locked_direct_combat_state_bytes(),
        resident.ground_movement_state_bytes(),
        resident.modifier_state_bytes(),
        resident.character_object_state_bytes(),
        resident.point_projectile_state_bytes(),
        resident.rng_state_bytes(),
        resident.next_entity_id,
        resident.checkpoint_is_current,
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


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_legal_ids_match_sorted_python_flatnonzero_without_mutation(
    fast_path: bool,
) -> None:
    battle = _oracle_battle(91_001)
    battle.fast_path = fast_path
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    before = _resident_state(resident)
    before_rng = battle.rng.getstate()

    for player_id in (0, 1):
        expected = tuple(
            int(action_id)
            for action_id in np.flatnonzero(
                action_space.legal_action_mask(battle, player_id)
            )
        )
        actual = resident.resident_legal_action_ids(player_id)

        assert actual == expected
        assert actual == tuple(sorted(actual))
        assert actual[-1] == action_space.no_op_action
        assert action_space.ability_action not in actual

    assert _resident_state(resident) == before
    assert battle.rng.getstate() == before_rng


def test_native_legal_ids_match_unaffordable_noop_only_state() -> None:
    battle = _oracle_battle(91_002)
    battle.players[0].elixir = 0.0
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()

    expected = tuple(
        int(action_id)
        for action_id in np.flatnonzero(action_space.legal_action_mask(battle, 0))
    )

    assert (
        resident.resident_legal_action_ids(0)
        == expected
        == (action_space.no_op_action,)
    )


def test_native_legal_ids_preserve_duplicate_hand_slots() -> None:
    battle = _oracle_battle(91_003)
    duplicate = battle.players[0].hand[0]
    battle.players[0].hand[1] = duplicate
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()

    expected = tuple(
        int(action_id)
        for action_id in np.flatnonzero(action_space.legal_action_mask(battle, 0))
    )
    actual = resident.resident_legal_action_ids(0)

    assert actual == expected
    assert any(0 <= action_id < 576 for action_id in actual)
    assert any(576 <= action_id < 1152 for action_id in actual)


def test_native_legal_ids_match_after_princess_tower_cleanup() -> None:
    battle = _oracle_battle(91_004)
    princess = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 0
        and entity._crown_tower_slot == "left"
    )
    princess.hitpoints = 0
    princess.is_alive = False
    battle._cleanup_dead_entities()
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()

    for player_id in (0, 1):
        expected = tuple(
            int(action_id)
            for action_id in np.flatnonzero(
                action_space.legal_action_mask(battle, player_id)
            )
        )
        assert resident.resident_legal_action_ids(player_id) == expected


def test_native_legality_rejects_same_size_noncanonical_arena() -> None:
    battle = _oracle_battle(91_005)
    assert isinstance(battle.arena, TileGrid)
    battle.arena.BLOCKED_TILES = []
    resident = ResidentRustBattle.from_battle(battle)

    with pytest.raises(RuntimeError, match="canonical 18x32 arena"):
        resident.resident_legal_action_ids(0)


@pytest.mark.parametrize("boundary_offset", [-1e-10, 0.0, 1e-10])
def test_native_payload_blocker_matches_python_power_distance(
    boundary_offset: float,
) -> None:
    battle = _oracle_battle(91_006)
    battle.players[0].hand[0] = "Knight"
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(Position(9.5, 10.5), 1, stats)
    blocker = next(
        entity
        for entity in reversed(tuple(battle.entities.values()))
        if isinstance(entity, Troop)
    )
    blocker.__dict__["blocks_deployment"] = True
    blocker.__dict__["deployment_collision_radius"] = 0.5
    blocker.position = Position(9.500000001 + boundary_offset, 10.5)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate = action_space.encode_action(0, 8, 10, 0)

    expected = tuple(
        int(action_id)
        for action_id in np.flatnonzero(action_space.legal_action_mask(battle, 0))
    )
    actual = resident.resident_legal_action_ids(0)

    assert actual == expected
    if boundary_offset < 0.0:
        assert candidate not in actual
    elif boundary_offset > 0.0:
        assert candidate in actual


@pytest.mark.parametrize("first_player", [0, 1])
def test_ordered_interval_matches_python_without_consuming_battle_rng(
    first_player: int,
) -> None:
    battle = _oracle_battle(91_100 + first_player)
    resident_root = ResidentRustBattle.from_battle(battle)
    resident_branch = resident_root.fork()
    root_before = _resident_state(resident_root)
    python_rng_before = battle.rng.getstate()
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 9, 21, 1),
    )

    expected_success: dict[int, bool] = {}
    for player_id in (first_player, 1 - first_player):
        expected_success[player_id] = action_space.apply_action(
            battle,
            player_id,
            actions[player_id],
        )
    for _ in range(4):
        battle._step_logic_tick(refresh_fast_path_end=False)

    actual_success, advanced = resident_branch.apply_resident_ordered_interval(
        *actions,
        first_player,
        4,
    )

    assert actual_success == expected_success == {0: True, 1: True}
    assert advanced == 4
    assert battle.rng.getstate() == python_rng_before
    _compare_resident_state(battle, resident_branch)
    assert _resident_state(resident_root) == root_before
    assert resident_root.checkpoint_is_current


def test_oracle_primitives_fail_closed_and_roll_back_before_rng_mutation() -> None:
    battle = _oracle_battle(91_200)
    definitions = battle.card_loader.load_card_definitions()
    unsupported = next(
        name
        for name, definition in sorted(definitions.items())
        if (stats := battle.card_loader.get_card(name)) is not None
        and _single_troop_capability_reasons(stats, definition)
    )
    battle.players[0].cycle_queue[0] = unsupported
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    before = _resident_state(resident)

    with pytest.raises(RuntimeError, match="unsupported hand/cycle card"):
        resident.resident_legal_action_ids(0)
    with pytest.raises(RuntimeError, match="unsupported hand/cycle card"):
        resident.apply_resident_ordered_interval(
            action,
            action_space.no_op_action,
            0,
            4,
        )

    assert _resident_state(resident) == before


def test_native_legality_rejects_live_ability_mechanic_without_rng_drift() -> None:
    battle = _oracle_battle(91_202)
    champion_name = next(
        name
        for name, definition in sorted(
            battle.card_loader.load_card_definitions().items()
        )
        if definition.kind == "champion"
    )
    champion = battle.card_loader.get_card(champion_name)
    assert champion is not None
    battle._spawn_unit_at_position(Position(8.0, 10.0), 0, champion)
    resident = ResidentRustBattle.from_battle(battle)
    before = _resident_state(resident)

    with pytest.raises(RuntimeError, match="active ability or unsupported mechanic"):
        resident.resident_legal_action_ids(0)

    assert _resident_state(resident) == before


def test_ordered_interval_rejects_ability_and_invalid_order_atomically() -> None:
    battle = _oracle_battle(91_201)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    before = _resident_state(resident)

    with pytest.raises(RuntimeError, match="champion abilities"):
        resident.apply_resident_ordered_interval(
            action_space.ability_action,
            action_space.no_op_action,
            0,
            1,
        )
    with pytest.raises(ValueError, match="first_player 0 or 1"):
        resident.apply_resident_ordered_interval(
            action_space.no_op_action,
            action_space.no_op_action,
            2,
            1,
        )
    assert _resident_state(resident) == before


def test_ordered_interval_rolls_back_after_partial_native_tick() -> None:
    battle = _oracle_battle(91_250)
    source_stats = battle.card_loader.get_card("Musketeer")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None
    assert target_stats is not None
    before_ids = set(battle.entities)
    battle._spawn_unit_at_position(Position(9.0, 12.0), 0, source_stats)
    source = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before_ids and isinstance(entity, Troop)
    )
    before_ids = set(battle.entities)
    battle._spawn_unit_at_position(Position(9.0, 14.0), 1, target_stats)
    target = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before_ids and isinstance(entity, Troop)
    )
    for troop in (source, target):
        troop.deploy_delay_remaining = 0.0
        troop.placement_pending = False
        troop._spawn_hook_pending = False
        troop._spawn_hook_fired = True
    source.target_id = target.id
    source.__dict__["_last_combat_target_id"] = target.id
    source.attack_cooldown = 0.0
    battle.next_entity_id = (1 << 63) - 2
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    before = _resident_state(resident)
    assert resident.resident_legal_action_ids(0)

    with pytest.raises(RuntimeError):
        resident.apply_resident_ordered_interval(
            action_space.no_op_action,
            action_space.no_op_action,
            0,
            2,
        )

    assert _resident_state(resident) == before


@pytest.mark.parametrize("ticks", [-1, 0])
def test_nonpositive_ordered_interval_still_applies_actions(ticks: int) -> None:
    battle = _oracle_battle(91_300 + ticks)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.no_op_action,
    )

    expected_success = {
        0: action_space.apply_action(battle, 0, actions[0]),
        1: action_space.apply_action(battle, 1, actions[1]),
    }
    actual_success, advanced = resident.apply_resident_ordered_interval(
        *actions,
        0,
        ticks,
    )

    assert actual_success == expected_success == {0: True, 1: True}
    assert advanced == 0
    _compare_resident_state(battle, resident)
