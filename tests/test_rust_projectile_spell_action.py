from __future__ import annotations

import random
from collections import deque

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import first_snapshot_difference
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import ResidentRustBattle, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _ready_target(battle: BattleState, player_id: int, position: Position):
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(position, player_id, stats)
    target = battle.entities[battle.next_entity_id - 1]
    target.deploy_delay_remaining = 0.0
    target.placement_delay_total = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    return target


def _assert_semantic_parity(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    expected = python_resident_semantic_snapshot(battle)
    actual = rust_resident_semantic_snapshot(resident)
    difference = first_snapshot_difference(expected, actual)
    assert difference is None, difference


def _apply_joint(
    battle: BattleState,
    resident: ResidentRustBattle,
    actions: tuple[int, int],
) -> None:
    action_space = DiscreteTileActionSpace()
    order = [0, 1]
    battle.rng.shuffle(order)
    expected: dict[int, bool] = {}
    for player_id in order:
        expected[player_id] = action_space.apply_action(
            battle,
            player_id,
            actions[player_id],
        )
    actual, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual == expected
    assert actual_order == tuple(order)


def test_projectile_spell_catalog_is_data_driven_and_fail_closed() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())
    supported = set(resident.resident_supported_action_cards())

    assert "Fireball" in supported
    assert "Rocket" in supported
    assert "Arrows" in supported
    assert resident.resident_action_card_capability_reasons("Fireball") == ()
    assert resident.resident_action_card_capability_reasons("Arrows") == ()


@pytest.mark.parametrize("player_id", [0, 1])
def test_fireball_legal_actions_match_scalar_and_fast_masks(player_id: int) -> None:
    battle = BattleState(rng=random.Random(94_100 + player_id))
    deck = [
        "Fireball",
        "Knight",
        "MiniPekka",
        "Musketeer",
        "Giant",
        "Archers",
        "Minions",
        "Skeletons",
    ]
    for player in battle.players:
        player.hand = list(deck[:4])
        player.cycle_queue = deque(deck[4:])
        player.elixir = player.max_elixir
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


def test_fireball_queue_acceptance_and_birth_frame_exclusion_are_exact() -> None:
    battle = BattleState(rng=random.Random(94_120))
    battle.players[0].hand = ["Fireball", None, None, None]
    battle.players[0].cycle_queue.clear()
    battle.players[0].elixir = battle.players[0].max_elixir
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 16, 0)

    _apply_joint(battle, resident, (action, action_space.no_op_action))
    _assert_semantic_parity(battle, resident)
    assert len(battle._pending_spell_casts) == 1
    assert not [
        entity for entity in battle.entities.values() if entity.entity_kind == 2
    ]

    for _ in range(19):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)
    assert len(battle._pending_spell_casts) == 1

    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)
    _assert_semantic_parity(battle, resident)
    projectile = next(
        entity for entity in battle.entities.values() if entity.entity_kind == 2
    )
    assert projectile.position == Position(9.0, 2.5)
    assert projectile.target_position == Position(9.5, 16.5)

    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)
    _assert_semantic_parity(battle, resident)
    assert projectile.position != Position(9.0, 2.5)


@pytest.mark.parametrize("player_id", [0, 1])
def test_fireball_full_impact_and_knockback_trace_match(player_id: int) -> None:
    battle = BattleState(rng=random.Random(94_140 + player_id))
    battle.players[player_id].hand = ["Fireball", None, None, None]
    battle.players[player_id].cycle_queue.clear()
    battle.players[player_id].elixir = battle.players[player_id].max_elixir
    target_position = Position(9.5, 16.5 if player_id == 0 else 15.5)
    target = _ready_target(battle, 1 - player_id, target_position)
    initial_hp = float(target.hitpoints)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(
        0,
        int(target_position.x),
        int(target_position.y),
        player_id,
    )
    actions = (
        action if player_id == 0 else action_space.no_op_action,
        action if player_id == 1 else action_space.no_op_action,
    )

    _apply_joint(battle, resident, actions)
    for _ in range(65):
        _assert_semantic_parity(battle, resident)
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
    _assert_semantic_parity(battle, resident)

    assert float(target.hitpoints) == initial_hp - 688.0
    assert target._knockback_target is None


def test_due_spell_id_overflow_rejects_the_whole_tick_atomically() -> None:
    battle = BattleState(rng=random.Random(94_160))
    battle.players[0].hand = ["Fireball", None, None, None]
    battle.players[0].cycle_queue.clear()
    battle.players[0].elixir = battle.players[0].max_elixir
    assert battle.deploy_card(0, "Fireball", Position(9.5, 16.5))
    battle.time = 0.95
    battle.tick = 19
    battle.next_entity_id = (1 << 63) - 2
    resident = ResidentRustBattle.from_battle(battle)
    before = rust_resident_semantic_snapshot(resident)

    with pytest.raises(RuntimeError, match="allocation headroom"):
        resident.advance_complete_tick()

    assert rust_resident_semantic_snapshot(resident) == before
    assert resident.checkpoint_is_current


def test_existing_cardless_fireball_projectile_hydrates_and_continues() -> None:
    from clasher.spells import SPELL_REGISTRY

    battle = BattleState(rng=random.Random(94_180))
    assert SPELL_REGISTRY["Fireball"].cast(battle, 0, Position(9.5, 16.5))
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    for _ in range(5):
        _assert_semantic_parity(battle, resident)
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
    _assert_semantic_parity(battle, resident)


def test_simultaneous_fireballs_preserve_shuffle_sequence_ids_and_rng() -> None:
    battle = BattleState(rng=random.Random(94_200))
    for player in battle.players:
        player.hand = ["Fireball", None, None, None]
        player.cycle_queue.clear()
        player.elixir = player.max_elixir
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 15, 0),
        action_space.encode_action(0, 9, 16, 1),
    )

    _apply_joint(battle, resident, actions)
    assert [cast.sequence for cast in battle._pending_spell_casts] == [0, 1]
    for _ in range(50):
        _assert_semantic_parity(battle, resident)
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
    _assert_semantic_parity(battle, resident)
