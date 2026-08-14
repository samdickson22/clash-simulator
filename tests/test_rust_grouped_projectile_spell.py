from __future__ import annotations

import random
from collections import deque

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import first_snapshot_difference
from clasher.entities import Projectile, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import ResidentRustBattle, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.spells import SPELL_REGISTRY

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _assert_semantic_parity(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    difference = first_snapshot_difference(
        python_resident_semantic_snapshot(battle),
        rust_resident_semantic_snapshot(resident),
    )
    assert difference is None, difference


def _apply_arrows(
    battle: BattleState,
    resident: ResidentRustBattle,
    *,
    player_id: int,
    x: int,
    y: int,
) -> None:
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, x, y, player_id)
    actions = (
        action if player_id == 0 else action_space.no_op_action,
        action if player_id == 1 else action_space.no_op_action,
    )
    order = [0, 1]
    battle.rng.shuffle(order)
    expected: dict[int, bool] = {}
    for current_player in order:
        expected[current_player] = action_space.apply_action(
            battle,
            current_player,
            actions[current_player],
        )
    actual, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual == expected
    assert actual_order == tuple(order)


@pytest.mark.parametrize("player_id", [0, 1])
def test_arrows_legal_actions_match_scalar_and_fast_masks(player_id: int) -> None:
    battle = BattleState(rng=random.Random(95_000 + player_id))
    deck = [
        "Arrows",
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

    native = np.asarray(
        resident.resident_legal_action_ids(player_id),
        dtype=np.int64,
    )
    for fast_path in (False, True):
        mask = action_space.legal_action_mask(
            battle,
            player_id,
            fast_path=fast_path,
        )
        assert np.array_equal(native, np.flatnonzero(mask))


@pytest.mark.parametrize("player_id", [0, 1])
def test_arrows_acceptance_geometry_groups_delays_and_rng_are_exact(
    player_id: int,
) -> None:
    battle = BattleState(rng=random.Random(95_020 + player_id))
    battle.players[player_id].hand = ["Arrows", None, None, None]
    battle.players[player_id].cycle_queue.clear()
    battle.players[player_id].elixir = battle.players[player_id].max_elixir
    resident = ResidentRustBattle.from_battle(battle)

    _apply_arrows(battle, resident, player_id=player_id, x=9, y=16)
    for _ in range(20):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    projectiles = [
        entity for entity in battle.entities.values() if type(entity) is Projectile
    ]
    assert len(projectiles) == 30
    assert [projectile.id for projectile in projectiles] == list(
        range(projectiles[0].id, projectiles[0].id + 30)
    )
    assert [projectile.launch_delay for projectile in projectiles] == (
        [0.0] * 10 + [0.2] * 10 + [0.4] * 10
    )
    assert (
        len({id(projectile.damage_group_hit_entity_ids) for projectile in projectiles})
        == 3
    )
    assert all(
        projectile.position == Position(9.0, 2.5 if player_id == 0 else 29.5)
        for projectile in projectiles
    )
    groups = rust_resident_semantic_snapshot(resident)["projectile_damage_groups"]
    assert [group["group_id"] for group in groups] == [
        projectiles[0].id,
        projectiles[10].id,
        projectiles[20].id,
    ]


def test_arrows_hits_each_target_once_per_wave_and_crown_damage_is_exact() -> None:
    battle = BattleState(rng=random.Random(95_040))
    battle.players[0].hand = ["Arrows", None, None, None]
    battle.players[0].cycle_queue.clear()
    battle.players[0].elixir = battle.players[0].max_elixir
    princess = next(
        entity
        for entity in battle.entities.values()
        if entity.player_id == 1 and entity._crown_tower_slot == "left"
    )
    initial_hp = float(princess.hitpoints)
    resident = ResidentRustBattle.from_battle(battle)

    _apply_arrows(battle, resident, player_id=0, x=3, y=25)
    for _ in range(80):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert float(princess.hitpoints) == initial_hp - 75.0
    assert not [
        entity for entity in battle.entities.values() if type(entity) is Projectile
    ]
    assert rust_resident_semantic_snapshot(resident)["projectile_damage_groups"] == []


def test_existing_arrows_volley_hydrates_shared_groups_and_continues() -> None:
    battle = BattleState(rng=random.Random(95_060))
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    _assert_semantic_parity(battle, resident)
    for _ in range(55):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)


def test_arrows_hydrates_after_first_group_member_cleanup() -> None:
    battle = BattleState(rng=random.Random(95_070))
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    initial_ids = {
        entity.id for entity in battle.entities.values() if type(entity) is Projectile
    }
    for _ in range(40):
        battle._step_logic_tick(refresh_fast_path_end=False)
        live_ids = {
            entity.id
            for entity in battle.entities.values()
            if type(entity) is Projectile
        }
        if live_ids and min(initial_ids) not in live_ids:
            break
    else:  # pragma: no cover - fixture invariant
        raise AssertionError("first Arrows projectile did not clean up before its wave")

    resident = ResidentRustBattle.from_battle(battle)
    assert resident.supports_complete_tick
    _assert_semantic_parity(battle, resident)
    for _ in range(20):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)


def test_two_arrows_casts_keep_independent_damage_groups() -> None:
    battle = BattleState(rng=random.Random(95_075))
    princess = next(
        entity
        for entity in battle.entities.values()
        if entity.player_id == 1 and entity._crown_tower_slot == "left"
    )
    initial_hp = float(princess.hitpoints)
    target = Position(princess.position.x, princess.position.y)
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, target)
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, target)
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(60):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_semantic_parity(battle, resident)

    assert float(princess.hitpoints) == initial_hp - 150.0


def test_malformed_grouped_projectile_state_fails_closed() -> None:
    battle = BattleState(rng=random.Random(95_077))
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    assert SPELL_REGISTRY["Arrows"].cast(battle, 1, Position(9.5, 15.5))
    projectiles = [
        entity for entity in battle.entities.values() if type(entity) is Projectile
    ]
    projectiles[30].damage_group_hit_entity_ids = projectiles[
        0
    ].damage_group_hit_entity_ids
    resident = ResidentRustBattle.from_battle(battle)
    before = rust_resident_semantic_snapshot(resident)

    assert not resident.supports_complete_tick
    with pytest.raises(RuntimeError, match="unsupported object"):
        resident.advance_complete_tick()
    assert rust_resident_semantic_snapshot(resident) == before


@pytest.mark.parametrize("launch_delay", [-0.1, 1.0])
def test_grouped_projectile_launch_delay_bounds_fail_closed(
    launch_delay: float,
) -> None:
    battle = BattleState(rng=random.Random(95_078))
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    projectiles = [
        entity for entity in battle.entities.values() if type(entity) is Projectile
    ]
    for projectile in projectiles[:10]:
        projectile.launch_delay = launch_delay
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_complete_tick


def test_primary_target_projectile_with_wave_interval_fails_closed() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(Position(9.0, 12.0), 1, stats)
    target = next(
        entity for entity in battle.entities.values() if isinstance(entity, Troop)
    )
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=42.0,
        range=5.0,
        sight_range=1.0,
        target_position=Position(9.0, 12.0),
        travel_speed=10.0,
        source_name="rust-parity-fixture",
        primary_target=target,
        tracks_target=True,
        damage_wave_interval=0.2,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_complete_tick


def test_due_arrows_id_overflow_rejects_the_whole_tick_atomically() -> None:
    battle = BattleState(rng=random.Random(95_080))
    battle.players[0].hand = ["Arrows", None, None, None]
    battle.players[0].cycle_queue.clear()
    battle.players[0].elixir = battle.players[0].max_elixir
    assert battle.deploy_card(0, "Arrows", Position(9.5, 16.5))
    battle.time = 0.95
    battle.tick = 19
    battle.next_entity_id = (1 << 63) - 31
    resident = ResidentRustBattle.from_battle(battle)
    before = rust_resident_semantic_snapshot(resident)

    with pytest.raises(RuntimeError, match="allocation headroom"):
        resident.advance_complete_tick()

    assert rust_resident_semantic_snapshot(resident) == before
    assert resident.checkpoint_is_current
