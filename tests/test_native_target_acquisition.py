import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
def test_pending_duration_counts_down_on_tower_object_ticks(fast_path):
    battle = BattleState(fast_path=fast_path)
    tower = next(e for e in battle.entities.values() if e.card_stats.name == "Tower")
    # Native target-owned duration is 100 at tick696 and 50 at tick697.
    # Its shared character object clock must also run in tower-only states.
    tower._pending_projectile_max_duration_ms = 100
    assert not battle.can_fast_forward_idle()
    battle.step()
    assert tower._pending_projectile_max_duration_ms == 50
    assert not battle.can_fast_forward_idle()
    battle.step()
    assert tower._pending_projectile_max_duration_ms == 0
    battle.step()
    assert tower._pending_projectile_max_duration_ms == 0


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("card", ["Prince", "Knight", "BabyDragon"])
def test_initial_cannon_lock_matches_native_public_target(card, fast_path):
    # Atomic native captures at tick112 validate all three targetEntityKey
    # values as the opposing Cannon, including the edge of sight range.
    battle = BattleState(fast_path=fast_path)
    for owner, name, point in [
        (0, card, Position(3.5, 14.5)),
        (1, "Cannon", Position(7.5, 19.5)),
    ]:
        battle.players[owner].hand = [name]
        assert battle.deploy_card(owner, name, point)
    actor = next(e for e in battle.entities.values() if e.card_stats.name == card)
    cannon = next(e for e in battle.entities.values() if e.card_stats.name == "Cannon")
    for _ in range(21):
        battle.step()
    assert actor.target_id == cannon.id


@pytest.mark.parametrize("fast_path", [False, True])
def test_baby_dragon_approach_matches_native_without_idle_hit_leash(fast_path):
    reference = json.loads(
        (
            Path(__file__).parent
            / "fixtures/native_baby_dragon_cannon_movement_15_535_86.json"
        ).read_text()
    )
    battle = BattleState(fast_path=fast_path)
    for owner, name, point in [
        (0, "BabyDragon", Position(3.5, 14.5)),
        (1, "Cannon", Position(7.5, 19.5)),
    ]:
        battle.players[owner].hand = [name]
        assert battle.deploy_card(owner, name, point)
    actor = next(
        e for e in battle.entities.values() if e.card_stats.name == "BabyDragon"
    )
    cannon = next(e for e in battle.entities.values() if e.card_stats.name == "Cannon")
    for tick in range(1, 121):
        battle.step()
        if 21 <= tick <= 41:
            assert not actor.has_started_projectile_hit_cycle()
        if tick >= 21:
            assert actor.hitpoints == reference["actor_health"][tick - 21], tick
            assert cannon.hitpoints == reference["building_health"][tick - 21], tick
            assert [
                round(actor.position.x * 1000),
                round(actor.position.y * 1000),
            ] == reference["positions"][tick - 21], tick


@pytest.mark.parametrize("fast_path", [False, True])
def test_prince_target_removal_matches_native_finish_and_reacquisition_frames(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    for owner, name, point in [
        (0, "Prince", Position(3.5, 14.5)),
        (1, "Cannon", Position(7.5, 19.5)),
    ]:
        battle.players[owner].hand = [name]
        assert battle.deploy_card(owner, name, point)
    prince = next(e for e in battle.entities.values() if e.card_stats.name == "Prince")
    for _ in range(89):
        battle.step()
    # Native tick180: target removed, callback installs1ms, state stays2.
    assert prince.target_id is None
    assert prince._attack_finish_elapsed_ms == 1
    position = Position(prince.position.x, prince.position.y)
    for expected in [51, 101, 151, 201, 0]:
        battle.step()
        assert prince.target_id is None
        assert prince.position == position
        assert prince._attack_finish_elapsed_ms == expected
    battle.step()  # Native186: first new target and movement, after expiry185.
    assert prince.target_id == 4
    assert prince.position != position
