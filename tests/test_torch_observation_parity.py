from __future__ import annotations

from collections import deque
from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.executor import step_idle_tensor_ticks
from clasher.torch_sim.observations import TensorObservationProjector
from clasher.torch_sim.state import TensorBattleState


def _assert_structured_exact(
    projector: TensorObservationProjector,
    battles: list[BattleState],
) -> None:
    actual = projector.project_structured()
    for batch_index, battle in enumerate(battles):
        for player_id in range(2):
            expected = projector.structured_builder.build(battle, player_id)
            for field in fields(expected):
                expected_value = getattr(expected, field.name)
                actual_value = getattr(actual, field.name)[batch_index, player_id]
                assert np.array_equal(actual_value.cpu().numpy(), expected_value), (
                    batch_index,
                    player_id,
                    field.name,
                    actual_value.cpu().numpy(),
                    expected_value,
                )


def _assert_cv_exact(
    projector: TensorObservationProjector,
    battles: list[BattleState],
) -> None:
    actual = projector.project_cv()
    for batch_index, battle in enumerate(battles):
        for player_id in range(2):
            expected = projector.cv_builder.build(battle, player_id)
            assert np.array_equal(
                actual.board[batch_index, player_id].cpu().numpy(), expected.board
            ), (batch_index, player_id, "board")
            assert np.array_equal(
                actual.hud[batch_index, player_id].cpu().numpy(), expected.hud
            ), (batch_index, player_id, "hud")


def _varied_battles() -> list[BattleState]:
    idle = BattleState()
    idle.time = 179.95
    idle.double_elixir = True
    idle.players[0].elixir = 7.25
    idle.players[0].max_elixir = 10.0
    idle.players[0].hand = ["Knight", None, "Fireball", None]
    idle.players[0].cycle_queue = deque(["Baby Dragon"])
    idle.players[0].next_card_refill_cooldown_ms = 650
    idle.players[1].hand = [None, "Baby Dragon", None, "Knight"]
    idle.players[1].cycle_queue = deque(["Fireball"])
    idle.players[1].left_tower_hp -= 123
    idle.entities[4].hitpoints = idle.players[1].left_tower_hp

    deploying = BattleState()
    deploying.players[0].elixir = 10.0
    deploying.players[0].hand = ["Knight", None, None, None]
    deploying.players[0].deck = ["Knight"]
    deploying.players[0].cycle_queue = deque()
    assert deploying.deploy_card(0, "Knight", Position(9.0, 10.0))
    knight = max(deploying.entities.values(), key=lambda entity: entity.id)
    knight.hitpoints -= 17
    knight.mechanics.extend(
        [
            SimpleNamespace(max_shield=0.5, current_shield=0.25),
            SimpleNamespace(max_shield=2.0, current_shield=0.9),
        ]
    )
    knight.placement_delay_total = 1e-320
    knight.deploy_delay_remaining = 5e-321
    vars(knight).update(time_alive=5e-321, duration=1e-320)
    knight.stun_timer = 0.75
    knight.slow_timer = 1.25
    knight.haste_timer = 2.5
    vars(knight).update(_special_move_active=True, _stealth_until=500)
    # Structured observations expose this generic flag, while CV exposes it
    # only for buildings.
    vars(knight)["_hidden_building"] = True
    return [idle, deploying]


@pytest.mark.parametrize("canonical", [False, True])
def test_batched_tensor_observations_match_python_oracles_exactly(
    canonical: bool,
) -> None:
    battles = _varied_battles()
    cards = ["Knight", "Baby Dragon", "Fireball"]
    structured = StructuredObservationBuilder(
        card_vocab=cards,
        max_entities=16,
        canonical_perspective=canonical,
    )
    cv = CvObservationBuilder(card_vocab=cards, canonical_perspective=canonical)
    state = TensorBattleState.from_battles(battles, max_entities=16)
    projector = TensorObservationProjector(
        state,
        battles,
        structured_builder=structured,
        cv_builder=cv,
    )

    _assert_structured_exact(projector, battles)
    _assert_cv_exact(projector, battles)


def test_short_noop_episode_observations_remain_exact_with_tensor_ticks() -> None:
    env = SelfPlayBattleEnv(
        decision_interval_ticks=3,
        max_ticks=12,
        simulation_backend="pytorch",
    )
    env.reset(seed=2301)
    assert env.battle is not None
    no_op = env.action_space.no_op_action

    done = False
    while not done:
        battle = env.battle
        state = TensorBattleState.from_battles([battle])
        projector = TensorObservationProjector(
            state,
            [battle],
            structured_builder=env.structured_obs_builder,
            cv_builder=env.obs_builder,
        )
        _assert_structured_exact(projector, [battle])
        _assert_cv_exact(projector, [battle])
        _, done, _ = env.step({0: no_op, 1: no_op})

    metrics = env.simulator_backend_metrics()
    assert metrics["tensor_ticks"] == 12
    assert metrics["python_ticks"] == 0
    assert metrics["unsupported_fallbacks"] == 0


def test_retained_projector_tracks_resident_idle_and_deployment_ticks_exactly() -> None:
    idle = BattleState()
    deploying = BattleState()
    deploying.players[0].elixir = 10.0
    deploying.players[0].hand = ["Knight", None, None, None]
    deploying.players[0].deck = ["Knight"]
    deploying.players[0].cycle_queue = deque()
    assert deploying.deploy_card(0, "Knight", Position(9.0, 10.0))
    sources = [idle, deploying]
    expected = [battle.clone() for battle in sources]

    structured = StructuredObservationBuilder(
        card_vocab=["Knight"],
        max_entities=16,
    )
    cv = CvObservationBuilder(card_vocab=["Knight"])
    state = TensorBattleState.from_battles(sources, max_entities=16)
    projector = TensorObservationProjector(
        state,
        sources,
        structured_builder=structured,
        cv_builder=cv,
    )

    for battle in expected:
        battle.step_logic_ticks(3)
    advanced = step_idle_tensor_ticks(state, 3)

    assert advanced.tolist() == [3, 3]
    _assert_structured_exact(projector, expected)
    _assert_cv_exact(projector, expected)


def test_cv_projection_supports_empty_vocab_and_configurable_status_scale() -> None:
    battle = BattleState()
    battle.entities[1].stun_timer = 3.0
    structured = StructuredObservationBuilder(card_vocab=[], max_entities=16)
    cv = CvObservationBuilder(card_vocab=[])
    cv.MAX_VISIBLE_STATUS_SECONDS = 12.0
    projector = TensorObservationProjector(
        TensorBattleState.from_battles([battle], max_entities=16),
        [battle],
        structured_builder=structured,
        cv_builder=cv,
    )

    _assert_structured_exact(projector, [battle])
    _assert_cv_exact(projector, [battle])
