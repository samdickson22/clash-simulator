import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_terminal_commands_15_535_86.json").read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_native_last_command_boundary_and_terminal_rejection(fast_path, case):
    battle = BattleState(fast_path=fast_path)
    if case["kind"] == "regulation":
        battle.entities[4].take_damage(battle.entities[4].hitpoints)
        battle._cleanup_dead_entities()
    battle.tick = case["submitted"]
    battle.time = battle.tick * battle.dt
    owner = case["owner"]
    battle.players[owner].hand = ["Zap"]
    battle.players[owner].elixir = 10
    battle._check_win_conditions()
    target = battle.entities[5 if owner == 0 else 2]
    assert target.hitpoints == case["before_hp"]
    accepted = battle.deploy_card(owner, "Zap", Position(14.5, 25.5 if owner == 0 else 6.5))
    assert accepted == case["accepted"]
    battle.step()
    assert target.hitpoints == case["after_hp"]
    if not accepted:
        assert battle.game_over
        assert battle.players[owner].elixir == 10
        assert not battle._pending_spell_casts
    while not battle.game_over:
        battle.step()
    assert battle.winner == case["native_winner"]


@pytest.mark.parametrize("idle", [False, True])
def test_native_deadline_keeps_last_playable_frame_despite_float_noise(idle):
    battle = BattleState()
    battle.tick = 5999
    battle.time = 299.95 + 1e-10
    if idle:
        assert battle.fast_forward_idle_ticks(1) == 1
    else:
        battle.step()
    assert battle.tick == 6000
    assert not battle.game_over
    if idle:
        assert battle.fast_forward_idle_ticks(5) == 1
    else:
        battle.step()
    assert battle.tick == 6001
    assert battle.game_over
