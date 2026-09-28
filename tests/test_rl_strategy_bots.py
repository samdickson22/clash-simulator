import copy

import numpy as np
import pytest

from clasher.arena import Position
from clasher.entities import Troop
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import (
    BRIDGE_PRESSURE,
    REACTIVE_DEFENSE,
    SLOW_PUSH,
    STRATEGY_NAMES,
    PFSPTable,
    StrategyBot,
    allocate_pfsp_slots,
    pfsp_weights,
)


def _env(seed: int = 23) -> SelfPlayBattleEnv:
    env = SelfPlayBattleEnv(seed=seed, canonical_perspective=True)
    env.reset(seed=seed)
    assert env.battle is not None
    env.battle.players[0].elixir = 10.0
    env.battle.players[1].elixir = 10.0
    return env


def _spawn_visible_threat(env: SelfPlayBattleEnv) -> Troop:
    assert env.battle is not None
    stats = copy.deepcopy(env.battle.card_loader.get_card("Knight"))
    assert stats is not None
    before = set(env.battle.entities)
    env.battle._spawn_unit_at_position(Position(3.5, 8.5), 1, stats)
    troop = next(
        entity
        for entity_id, entity in env.battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._visible_to_players = {0, 1}
    return troop


@pytest.mark.parametrize("strategy", STRATEGY_NAMES)
def test_strategy_roster_is_deterministic_and_always_legal(strategy: str):
    env = _env()
    bot = StrategyBot(strategy)

    first = bot.select_action(env, 0)
    second = bot.select_action(env, 0)

    assert first == second
    assert env.get_action_mask(0)[first]


def test_strategy_reuses_a_precomputed_action_mask(monkeypatch):
    env = _env(seed=29)
    mask = env.get_action_mask(0)

    def unexpected_mask_build(_player_id):
        raise AssertionError("precomputed action mask was not reused")

    monkeypatch.setattr(env, "get_action_mask", unexpected_mask_build)
    action = StrategyBot("balanced").select_action(env, 0, action_mask=mask)

    assert mask[action]


@pytest.mark.parametrize("strategy", STRATEGY_NAMES)
def test_strategy_never_reads_hidden_enemy_hand_or_elixir(strategy: str):
    env = _env()
    bot = StrategyBot(strategy)
    before = bot.select_action(env, 0)
    assert env.battle is not None

    env.battle.players[1].hand = list(reversed(env.battle.players[1].hand))
    env.battle.players[1].elixir = 0.0
    after = bot.select_action(env, 0)

    assert after == before


def test_reactive_defense_plays_into_a_visible_incoming_push():
    env = _env()
    _spawn_visible_threat(env)

    action = StrategyBot(REACTIVE_DEFENSE).select_action(env, 0)
    decoded = env.action_space.decode_action(action, 0)

    assert action != env.action_space.no_op_action
    assert decoded.position is not None
    assert decoded.position.y < 16.0


def test_bridge_pressure_deploys_farther_forward_than_slow_push():
    bridge_env = _env()
    slow_env = _env()

    bridge = bridge_env.action_space.decode_action(
        StrategyBot(BRIDGE_PRESSURE).select_action(bridge_env, 0),
        0,
    )
    slow = slow_env.action_space.decode_action(
        StrategyBot(SLOW_PUSH).select_action(slow_env, 0),
        0,
    )

    assert bridge.position is not None
    assert slow.position is not None
    assert bridge.position.y > slow.position.y + 4.0


def test_balanced_prefers_primary_tower_pressure_over_kiting_body() -> None:
    env = _env(seed=31)
    assert env.battle is not None
    env.battle.players[0].hand = [
        "HogRider",
        "IceGolem",
        "Skeletons",
        "IceSpirit",
    ]

    action = StrategyBot("balanced").select_action(env, 0)
    decoded = env.action_space.decode_action(action, 0)

    assert decoded.slot == 0
    assert decoded.position is not None
    assert decoded.position.y >= 11.0


def test_pfsp_prioritizes_hard_opponents_and_normalizes():
    weights = pfsp_weights({"easy": 0.9, "even": 0.5, "hard": 0.1}, power=2.0)

    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["hard"] > weights["even"] > weights["easy"] > 0.0


def test_pfsp_table_accumulates_auditable_match_counts():
    table = PFSPTable()
    table.record("balanced", wins=2, draws=1, losses=1)
    table.record("balanced", wins=0, draws=1, losses=1)
    table.record("reactive-defense", wins=1, draws=0, losses=3)

    assert table.results["balanced"] == [2, 2, 2]
    assert table.score_rates() == {
        "balanced": pytest.approx(0.5),
        "reactive-defense": pytest.approx(0.25),
    }
    assert np.isclose(sum(table.weights().values()), 1.0)


def test_pfsp_worker_allocation_uses_all_slots_deterministically():
    weights = {
        "bridge-pressure": 0.6,
        "reactive-defense": 0.3,
        "balanced": 0.1,
    }

    allocated = allocate_pfsp_slots(weights, 10)

    assert allocated.count("bridge-pressure") == 6
    assert allocated.count("reactive-defense") == 3
    assert allocated.count("balanced") == 1
    assert allocated == allocate_pfsp_slots(weights, 10)
