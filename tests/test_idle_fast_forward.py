import copy

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _assert_players_match(left: BattleState, right: BattleState) -> None:
    for pid in (0, 1):
        lp = left.players[pid]
        rp = right.players[pid]
        assert abs(lp.elixir - rp.elixir) < 1e-6
        assert lp.hand == rp.hand
        assert lp.cycle_queue == rp.cycle_queue
        assert (
            lp.next_card_refill_cooldown_ms
            == rp.next_card_refill_cooldown_ms
        )
        assert lp.left_tower_hp == rp.left_tower_hp
        assert lp.right_tower_hp == rp.right_tower_hp
        assert lp.king_tower_hp == rp.king_tower_hp


def _assert_tower_clocks_match(left: BattleState, right: BattleState) -> None:
    left_towers = [
        entity
        for entity in left.entities.values()
        if isinstance(entity, Building)
    ]
    right_towers = [
        entity
        for entity in right.entities.values()
        if isinstance(entity, Building)
    ]
    assert len(left_towers) == len(right_towers)
    for left_tower, right_tower in zip(left_towers, right_towers, strict=True):
        assert left_tower.last_attack_time == right_tower.last_attack_time
        assert left_tower.attack_cooldown == right_tower.attack_cooldown
        assert left_tower.stun_timer == right_tower.stun_timer
        assert left_tower.activation_delay_remaining == right_tower.activation_delay_remaining
        assert (
            left_tower.activation_first_hit_delay_remaining
            == right_tower.activation_first_hit_delay_remaining
        )


def test_fast_forward_idle_ticks_matches_step_for_static_towers():
    battle = BattleState()
    battle.players[0].hand[0] = None
    battle.players[0].next_card_refill_cooldown_ms = 100
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
    _assert_tower_clocks_match(battle, manual)


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
    _assert_tower_clocks_match(env.battle, manual)


def test_idle_fast_forward_rejects_active_static_tower_clocks():
    cases = []

    stunned = BattleState()
    stunned_tower = next(
        entity
        for entity in stunned.entities.values()
        if entity.card_stats.name == "Tower"
    )
    stunned_tower.apply_stun(0.5)
    cases.append(stunned)

    recovering = BattleState()
    recovering_tower = next(
        entity
        for entity in recovering.entities.values()
        if entity.card_stats.name == "Tower"
    )
    recovering_tower.attack_cooldown = (
        recovering_tower.get_preloaded_attack_time_seconds() + 0.4
    )
    cases.append(recovering)

    activating = BattleState()
    king = next(
        entity
        for entity in activating.entities.values()
        if entity.card_stats.name == "KingTower"
    )
    king.activate()
    cases.append(activating)

    for battle in cases:
        assert not battle.can_fast_forward_idle()
        assert battle.fast_forward_idle_ticks(8) == 0


def test_tower_clocks_reenable_idle_fast_forward_after_normal_expiry():
    battle = BattleState()
    tower = next(
        entity
        for entity in battle.entities.values()
        if entity.card_stats.name == "Tower"
    )
    tower.apply_stun(0.1)
    tower.attack_cooldown = tower.get_preloaded_attack_time_seconds() + 0.1

    assert not battle.can_fast_forward_idle()
    battle.step()
    assert not battle.can_fast_forward_idle()
    battle.step()
    assert not battle.can_fast_forward_idle()
    battle.step()
    assert not battle.can_fast_forward_idle()
    battle.step()
    assert battle.can_fast_forward_idle()


def test_idle_fast_forward_stops_at_tiebreaker_like_normal_step():
    battle = BattleState()
    manual = copy.deepcopy(battle)
    battle.time = manual.time = 299.97
    battle.tick = manual.tick = 9090

    advanced = battle.fast_forward_idle_ticks(8)
    manual.step()

    assert advanced == 1
    assert battle.game_over and manual.game_over
    assert battle.winner is None and manual.winner is None
    assert battle.tick == manual.tick
    assert abs(battle.time - manual.time) < 1e-9
