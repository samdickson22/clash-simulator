import copy

from clasher.battle import BattleState
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _assert_players_match(left: BattleState, right: BattleState) -> None:
    for pid in (0, 1):
        lp = left.players[pid]
        rp = right.players[pid]
        assert abs(lp.elixir - rp.elixir) < 1e-6
        assert lp.left_tower_hp == rp.left_tower_hp
        assert lp.right_tower_hp == rp.right_tower_hp
        assert lp.king_tower_hp == rp.king_tower_hp


def test_fast_forward_idle_ticks_matches_step_for_static_towers():
    battle = BattleState()
    manual = copy.deepcopy(battle)
    ticks = 8

    assert battle.can_fast_forward_idle()
    advanced = battle.fast_forward_idle_ticks(ticks)
    assert advanced == ticks
    for _ in range(ticks):
        manual.step()

    assert battle.tick == manual.tick
    assert abs(battle.time - manual.time) < 1e-9
    _assert_players_match(battle, manual)


def test_env_idle_fast_forward_matches_manual_tick_advance():
    env = SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=9090,
        decks_path="decks.json",
        seed=123,
        mirror_match=True,
        canonical_perspective=True,
        engine_fast_path="off",
        idle_fast_forward=True,
    )
    env.reset()
    assert env.battle is not None
    manual = copy.deepcopy(env.battle)
    no_op = env.action_space.no_op_action

    _, done, info = env.step({0: no_op, 1: no_op})
    assert not done
    assert info.ticks_advanced == 8
    for _ in range(8):
        manual.step()

    assert env.battle.tick == manual.tick
    assert abs(env.battle.time - manual.time) < 1e-9
    _assert_players_match(env.battle, manual)
