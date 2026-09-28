import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, RollingProjectile


@pytest.mark.parametrize("fast_path", [False, True])
def test_fireball_first_frame_matches_native_command_prefix(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.players[1].hand = ["Fireball"]
    assert battle.deploy_card(1, "Fireball", Position(3.5, 18.5))
    battle.step()
    projectile = next(e for e in battle.entities.values() if isinstance(e, Projectile))
    # Recorded native command1020, visible boundary1021.
    assert [
        round(projectile.position.x * 1000),
        round(projectile.position.y * 1000),
    ] == [8722, 28469]


@pytest.mark.parametrize("fast_path", [False, True])
def test_log_child_landing_and_first_movement_match_native(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.players[0].hand = ["Log"]
    assert battle.deploy_card(0, "Log", Position(3.5, 13.5))
    roller = next(
        e for e in battle.entities.values() if isinstance(e, RollingProjectile)
    )
    for _ in range(9):
        battle.step()
    # Native parent starts three tiles behind placement; child appears at
    # boundary1449 and first moves200 units at1450 after command1440.
    assert roller.time_alive >= roller.spawn_delay
    assert roller.position == Position(3.5, 13.5)
    battle.step()
    assert roller.position == Position(3.5, 13.7)


@pytest.mark.parametrize("fast_path", [False, True])
def test_zap_damage_matches_first_native_command_frame(fast_path):
    battle = BattleState(fast_path=fast_path)
    tower = next(e for e in battle.entities.values() if e.id == 2)
    before = tower.hitpoints
    battle.players[1].hand = ["Zap"]
    assert battle.deploy_card(1, "Zap", Position(14.5, 6.5))
    battle.step()
    assert before - tower.hitpoints == 48


@pytest.mark.parametrize("fast_path", [False, True])
def test_fireball_full_recorded_flight_and_terminal_frame(fast_path):
    import json
    from pathlib import Path

    case = json.loads(
        (
            Path(__file__).parent / "fixtures/native_fireball_travel_15_535_86.json"
        ).read_text()
    )
    battle = BattleState(fast_path=fast_path)
    battle.players[case["owner"]].hand = ["Fireball"]
    assert battle.deploy_card(
        case["owner"], "Fireball", Position(*(v / 1000 for v in case["destination"]))
    )
    for row in case["frames"]:
        battle.step()
        assert battle.tick == row["tick"] - case["submitted_tick"]
        shots = [e for e in battle.entities.values() if isinstance(e, Projectile)]
        if row["position"] is None:
            assert not shots, row["tick"]
        else:
            assert len(shots) == 1
            assert [
                round(shots[0].position.x * 1000),
                round(shots[0].position.y * 1000),
            ] == row["position"], row["tick"]
