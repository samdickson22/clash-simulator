from __future__ import annotations

import random
import struct
from dataclasses import fields

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.reward_model import (
    REWARD_PROFILES,
    potential_breakdown_p0,
    reward_potential_p0,
    reward_win_prob_p0,
)
from clasher.rl.rust_oracle_leaf import (
    potential_breakdown_from_projection,
    projection_from_battle,
    reward_potential_from_projection,
    reward_win_prob_from_projection,
)
from clasher.rust_core import ResidentRustBattle, rust_core_available

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _spawn(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _activate(*troops: Troop) -> None:
    for troop in troops:
        troop.deploy_delay_remaining = 0.0
        troop.placement_pending = False
        troop._spawn_hook_pending = False
        troop._spawn_hook_fired = True


def _assert_leaf_parity(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    resident_before = (
        resident.entity_sha256(),
        resident.player_sha256(),
        resident.idle_sha256(),
        resident.rng_sha256(),
    )
    battle_rng_before = battle.rng.getstate()
    expected_projection = projection_from_battle(battle)
    actual_projection = resident.resident_oracle_leaf_projection()
    assert actual_projection == expected_projection

    expected_breakdown = potential_breakdown_p0(battle)
    actual_breakdown = potential_breakdown_from_projection(actual_projection)
    for field in fields(expected_breakdown):
        assert _bits(getattr(actual_breakdown, field.name)) == _bits(
            getattr(expected_breakdown, field.name)
        )
    for profile in REWARD_PROFILES:
        assert _bits(
            reward_potential_from_projection(actual_projection, profile)
        ) == _bits(reward_potential_p0(battle, profile))
        assert _bits(
            reward_win_prob_from_projection(actual_projection, profile)
        ) == _bits(reward_win_prob_p0(battle, profile))

    assert resident.resident_oracle_leaf_projection() == actual_projection
    assert (
        resident.entity_sha256(),
        resident.player_sha256(),
        resident.idle_sha256(),
        resident.rng_sha256(),
    ) == resident_before
    assert battle.rng.getstate() == battle_rng_before


def test_initial_leaf_projection_matches_every_reward_profile_bit_exactly() -> None:
    battle = BattleState(rng=random.Random(92_001))
    resident = ResidentRustBattle.from_battle(battle)

    _assert_leaf_parity(battle, resident)


def test_leaf_projection_preserves_starting_hp_material_and_danger_order() -> None:
    battle = BattleState(rng=random.Random(92_002))
    player0 = _spawn(battle, "Knight", 0, Position(3.5, 20.0))
    player1 = _spawn(battle, "Musketeer", 1, Position(14.5, 12.0))
    _activate(player0, player1)
    battle.players[0].left_tower_hp -= 317.5
    battle.players[1].king_tower_hp -= 211.25
    for entity in battle.entities.values():
        slot = getattr(entity, "_crown_tower_slot", None)
        if entity.player_id == 0 and slot == "left":
            entity.hitpoints = battle.players[0].left_tower_hp
        if entity.player_id == 1 and slot == "king":
            entity.hitpoints = battle.players[1].king_tower_hp
    resident = ResidentRustBattle.from_battle(battle)

    _assert_leaf_parity(battle, resident)
    projection = resident.resident_oracle_leaf_projection()
    assert projection.players[0].starting_hp != projection.players[0].current_hp
    assert projection.players[1].starting_hp != projection.players[1].current_hp


def test_leaf_projection_keeps_player_and_crown_entity_hp_sources_distinct() -> None:
    battle = BattleState(rng=random.Random(92_004))
    threat = _spawn(battle, "Knight", 1, Position(3.5, 8.0))
    _activate(threat)
    battle.players[0].left_tower_hp -= 500.5
    resident = ResidentRustBattle.from_battle(battle)

    _assert_leaf_parity(battle, resident)
    projection = resident.resident_oracle_leaf_projection()
    player_left = projection.players[0].current_hp[0]
    crown_left = next(
        tower.hp
        for tower in projection.crowns
        if tower.player_id == 0 and tower.slot == "left"
    )
    assert player_left != crown_left


def test_leaf_projection_tracks_zero_cost_death_children_across_ticks() -> None:
    battle = BattleState(rng=random.Random(92_003))
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 13.5))
    golem = _spawn(battle, "Golem", 0, Position(9.0, 14.0))
    _activate(attacker, golem)
    attacker.damage = golem.hitpoints + 1
    attacker.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(5):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _assert_leaf_parity(battle, resident)

    children = [
        row
        for row in resident.resident_oracle_leaf_projection().combat
        if row.player_id == 0 and not row.is_crown
    ]
    assert len(children) == 2
    assert [row.mana_cost for row in children] == [0.0, 0.0]


@pytest.mark.parametrize("winner", [0, 1, None])
def test_terminal_leaf_short_circuits_every_profile(winner: int | None) -> None:
    battle = BattleState(rng=random.Random(92_010 + (winner or 0)))
    battle.game_over = True
    battle.winner = winner
    resident = ResidentRustBattle.from_battle(battle)
    projection = resident.resident_oracle_leaf_projection()

    for profile in (*REWARD_PROFILES, "unknown-after-terminal"):
        assert _bits(reward_win_prob_from_projection(projection, profile)) == _bits(
            reward_win_prob_p0(battle, profile)
        )
