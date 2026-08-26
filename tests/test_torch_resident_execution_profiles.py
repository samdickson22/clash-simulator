from __future__ import annotations

import random
from collections import deque
from dataclasses import fields
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_outputs import ResidentOutputProjector
from clasher.torch_sim.runtime_state import (
    RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    RESIDENT_EXECUTION_PROFILE_GYM_FAST,
    TensorRuntimeEvents,
)

DEPLOY_KNIGHT = 1 * 18 + 6


def _set_hand(battle: BattleState, first: str) -> None:
    player = battle.players[0]
    player.hand = [first, "Zap", "Cannon", "Fireball"]
    player.deck = [str(card) for card in player.hand if card is not None]
    player.cycle_queue = deque()
    player.elixir = 10.0


def _knight_battle() -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(826_101))
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
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    _set_hand(battle, "Knight")
    return battle


def _electro_dragon_battle() -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(826_202))
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card("ElectroDragon")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    battle._spawn_unit_at_position(
        Position(9.0, 12.0),
        0,
        source_stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    for x in (12.0, 13.0, 14.0):
        battle._spawn_unit_at_position(
            Position(x, 12.0),
            1,
            target_stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
    source = battle.entities[1]
    source.attack_cooldown = 0.0
    source.target_id = 2
    for entity_id in (2, 3, 4):
        target = battle.entities[entity_id]
        target.attack_cooldown = 10.0
        target.stun_timer = 100.0
    _set_hand(battle, "ElectroDragon")
    return battle


def _assert_tensor_dataclass_equal(left: object, right: object) -> None:
    for descriptor in fields(left):  # type: ignore[arg-type]
        left_value = getattr(left, descriptor.name)
        right_value = getattr(right, descriptor.name)
        if isinstance(left_value, torch.Tensor):
            assert torch.equal(left_value, right_value), descriptor.name


def test_gym_fast_knight_tick_never_enters_checked_diagnostic_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked_calls = 0
    original = TensorRuntimeEvents.append

    def counted(self: TensorRuntimeEvents, **kwargs: Any) -> None:
        nonlocal checked_calls
        checked_calls += 1
        original(self, **kwargs)

    monkeypatch.setattr(TensorRuntimeEvents, "append", counted)
    engine = TensorResidentEngine.from_battles(
        [_knight_battle()],
        max_entities=16,
        max_objects=16,
        event_capacity=64,
        execution_profile=RESIDENT_EXECUTION_PROFILE_GYM_FAST,
    )

    result = engine.step(torch.tensor([[DEPLOY_KNIGHT, NO_OP_ACTION]]))

    assert result.committed.tolist() == [True]
    assert checked_calls == 0
    assert engine.execution_profile == RESIDENT_EXECUTION_PROFILE_GYM_FAST


def test_gym_fast_preserves_policy_command_history_without_runtime_ledger() -> None:
    battle = _knight_battle()
    engine = TensorResidentEngine.from_battles(
        [battle],
        max_entities=16,
        max_objects=16,
        event_capacity=64,
        execution_profile=RESIDENT_EXECUTION_PROFILE_GYM_FAST,
    )
    projector = ResidentOutputProjector.from_engine(
        engine,
        [battle],
        structured_builder=StructuredObservationBuilder(max_entities=16),
        cv_builder=CvObservationBuilder(),
    )

    result = projector.step_and_capture(
        torch.tensor([[DEPLOY_KNIGHT, NO_OP_ACTION]])
    )
    public = projector.consume_public_events()

    assert result.deployment.ingress.accepted.tolist() == [[True, True]]
    assert public.valid.sum().item() == 2
    assert public.valid[0, :, 0].tolist() == [True, True]
    assert public.owner[0, :, 0].tolist() == [0, 0]
    assert public.own[0, :, 0].tolist() == [True, False]
    assert engine.runtime.events.count.tolist() == [0]


def test_electro_dragon_chain_gameplay_matches_exact_debug_in_gym_fast() -> None:
    battle = _electro_dragon_battle()
    exact = TensorResidentEngine.from_battles(
        [battle.clone()],
        max_entities=32,
        max_objects=32,
        event_capacity=1_024,
        execution_profile=RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    )
    fast = TensorResidentEngine.from_battles(
        [battle.clone()],
        max_entities=32,
        max_objects=32,
        # Diagnostic capacity is intentionally too small for the exact chain
        # ledger. Gym gameplay must not fall back because debug output cannot
        # fit.
        event_capacity=1,
        execution_profile=RESIDENT_EXECUTION_PROFILE_GYM_FAST,
    )

    exact_result = exact.step()
    fast_result = fast.step()

    assert exact_result.committed.tolist() == fast_result.committed.tolist() == [True]
    assert exact_result.chain_impacts is not None
    assert fast_result.chain_impacts is not None
    assert exact_result.chain_impacts.materialized.any().item()
    assert fast.runtime.supported.tolist() == [True]
    assert fast.runtime.events.count.tolist() == [0]
    _assert_tensor_dataclass_equal(exact.runtime.battle, fast.runtime.battle)
    _assert_tensor_dataclass_equal(exact.runtime.status, fast.runtime.status)
    _assert_tensor_dataclass_equal(exact.chain_impacts, fast.chain_impacts)


def test_implicit_execution_profile_remains_exact_debug() -> None:
    implicit = TensorResidentEngine.from_battles(
        [_knight_battle()], max_entities=16, max_objects=16, event_capacity=64
    )
    explicit = TensorResidentEngine.from_battles(
        [_knight_battle()],
        max_entities=16,
        max_objects=16,
        event_capacity=64,
        execution_profile=RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    )

    implicit_result = implicit.step(torch.tensor([[DEPLOY_KNIGHT, NO_OP_ACTION]]))
    explicit_result = explicit.step(torch.tensor([[DEPLOY_KNIGHT, NO_OP_ACTION]]))

    assert implicit.execution_profile == RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG
    assert implicit_result.committed.tolist() == explicit_result.committed.tolist()
    _assert_tensor_dataclass_equal(implicit.runtime.battle, explicit.runtime.battle)
    _assert_tensor_dataclass_equal(implicit.runtime.events, explicit.runtime.events)
