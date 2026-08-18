from __future__ import annotations

import random
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_differential import (
    ResidentEpisodeDifferential,
    no_op_actions,
)

DEPLOY_KNIGHT_FAR_FROM_COMBAT = 1 * 18 + 6


def _accelerate_episode(battle: BattleState) -> None:
    battle.overtime_start_time = 0.05
    battle.tiebreaker_time = 0.10


def _inert_battle(seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    _accelerate_episode(battle)
    return battle


def _combat_battle(seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(
        Position(14.5, 14.5),
        1,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[1]
    target.hitpoints = 100.0
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    battle._spawn_unit_at_position(
        Position(14.5, 12.76),
        0,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    attacker = battle.entities[2]
    attacker.target_id = 1
    attacker._movement_target_id = 1
    attacker.attack_cooldown = 0.0
    player = battle.players[0]
    player.hand = ["Knight", "Zap", "Cannon", "Fireball"]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 10.0
    _accelerate_episode(battle)
    return battle


def _combat_actions(
    tick: int, battles: tuple[BattleState, ...]
) -> tuple[tuple[int, int], ...]:
    action = DEPLOY_KNIGHT_FAR_FROM_COMBAT if tick == 0 else NO_OP_ACTION
    return tuple((action, NO_OP_ACTION) for _ in battles)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_full_inert_episodes_match_the_represented_resident_subset(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    sources = [_inert_battle(410_000 + row) for row in range(4)]
    source_rng = [battle.rng.getstate() for battle in sources]
    report = ResidentEpisodeDifferential(
        device=device, max_entities=8, max_objects=8, event_capacity=32
    ).run(
        sources,
        no_op_actions,
        max_ticks=4,
    )

    assert report.divergence is None
    assert report.ticks_executed == 2
    assert report.resident_rows == (0, 1, 2, 3)
    assert report.completed_rows == (0, 1, 2, 3)
    assert report.parity_rows == (0, 1, 2, 3)
    assert report.fallback_only_rows == ()
    assert report.parity_passed
    assert [battle.tick for battle in sources] == [0, 0, 0, 0]
    assert [battle.rng.getstate() for battle in sources] == source_rng


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_supported_deployment_combat_episode_matches_represented_subset(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    report = ResidentEpisodeDifferential(
        device=device, max_entities=16, max_objects=16, event_capacity=64
    ).run(
        [_combat_battle(420_000 + row) for row in range(3)],
        _combat_actions,
        max_ticks=4,
    )

    assert report.divergence is None
    assert report.ticks_executed == 2
    assert report.parity_rows == (0, 1, 2)
    assert report.fallback_only_rows == ()


def test_preflight_rejected_row_is_fallback_only_not_parity() -> None:
    supported = _inert_battle(430_000)
    rejected = _inert_battle(430_001)
    player = rejected.players[0]
    player.hand = ["Golem", "Zap", "Cannon", "Fireball"]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 10.0

    def actions(tick: int, _battles: tuple[BattleState, ...]):
        return (
            (NO_OP_ACTION, NO_OP_ACTION),
            (
                DEPLOY_KNIGHT_FAR_FROM_COMBAT if tick == 0 else NO_OP_ACTION,
                NO_OP_ACTION,
            ),
        )

    report = ResidentEpisodeDifferential(
        max_entities=16, max_objects=16, event_capacity=32
    ).run([supported, rejected], actions, max_ticks=4)

    assert report.divergence is None
    assert report.preflight_rejected_rows == (1,)
    assert report.fallback_only_rows == (1,)
    assert report.parity_rows == (0,)
    assert 1 not in report.parity_rows


def test_cross_phase_rejected_row_is_fallback_only_not_parity() -> None:
    supported = _inert_battle(435_000)
    overflow = _combat_battle(435_001)

    def actions(tick: int, _battles: tuple[BattleState, ...]):
        combat_action = DEPLOY_KNIGHT_FAR_FROM_COMBAT if tick == 0 else NO_OP_ACTION
        return (
            (NO_OP_ACTION, NO_OP_ACTION),
            (combat_action, NO_OP_ACTION),
        )

    report = ResidentEpisodeDifferential(
        max_entities=16, max_objects=16, event_capacity=1
    ).run([supported, overflow], actions, max_ticks=4)

    assert report.divergence is None
    assert report.runtime_rejected_rows == (1,)
    assert report.fallback_only_rows == (1,)
    assert report.parity_rows == (0,)


def test_first_divergence_captures_tick_action_rng_and_event_context() -> None:
    def corrupt(_tick: int, engine) -> None:
        engine.runtime.battle.elixir[0, 0] += 1.0

    report = ResidentEpisodeDifferential(
        max_entities=8, max_objects=8, event_capacity=32
    ).run(
        [_inert_battle(440_000)],
        no_op_actions,
        max_ticks=4,
        resident_mutator=corrupt,
    )

    divergence = report.divergence
    assert divergence is not None
    assert divergence.row == 0
    assert divergence.tick == 0
    assert divergence.action == (NO_OP_ACTION, NO_OP_ACTION)
    assert divergence.path == "rows[0].players[0].elixir"
    assert divergence.expected_rng == divergence.actual_rng
    assert divergence.expected_events == divergence.actual_events == ()
