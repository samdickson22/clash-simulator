from __future__ import annotations

import random
from collections import deque
from dataclasses import fields

import numpy as np
import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.diagnostics import battle_snapshot, first_divergence
from clasher.torch_sim.observations import (
    TensorCvObservation,
    TensorStructuredObservation,
)
from clasher.torch_sim.resident_selfplay import TensorResidentSelfPlay


def _safe_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    for player in battle.players:
        player.deck = []
        player.hand = [None, None, None, None]
        player.cycle_queue = deque()
        player.elixir = 5.0
    return battle


def _catalog(device: str = "cpu") -> TensorCardCatalog:
    battle = BattleState()
    return TensorCardCatalog.compile(
        battle.card_loader,
        ["Knight"],
        device=device,
    )


def _oracle_noop_decision(
    battle: BattleState,
    ticks: int,
) -> list[int]:
    order = [0, 1]
    battle.rng.shuffle(order)
    action_space = DiscreteTileActionSpace()
    for player_id in order:
        assert action_space.apply_action(battle, player_id, NO_OP_ACTION)
    battle.step_logic_ticks(ticks)
    return order


def _assert_observations_exact(
    bridge: TensorResidentSelfPlay,
    expected: list[BattleState],
    structured: TensorStructuredObservation,
    cv: TensorCvObservation,
) -> None:
    for row, battle in enumerate(expected):
        for player_id in (0, 1):
            expected_structured = bridge.projector.structured_builder.build(
                battle, player_id
            )
            for state in fields(expected_structured):
                actual = getattr(structured, state.name)[row, player_id]
                np.testing.assert_array_equal(
                    actual.cpu().numpy(), getattr(expected_structured, state.name)
                )
            expected_cv = bridge.projector.cv_builder.build(battle, player_id)
            np.testing.assert_array_equal(
                cv.board[row, player_id].cpu().numpy(), expected_cv.board
            )
            np.testing.assert_array_equal(
                cv.hud[row, player_id].cpu().numpy(), expected_cv.hud
            )


@pytest.mark.parametrize("device", ["cpu", "cuda"])
def test_resident_noop_decision_returns_exact_device_tensors_and_rng_order(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    sources = [_safe_battle(71_001), _safe_battle(71_002)]
    expected = [battle.clone() for battle in sources]
    builder = StructuredObservationBuilder(card_vocab=[], max_entities=16)
    cv_builder = CvObservationBuilder(card_vocab=[])
    bridge = TensorResidentSelfPlay.from_battles(
        sources,
        device=device,
        decision_interval_ticks=3,
        max_ticks=12,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(device),
        structured_builder=builder,
        cv_builder=cv_builder,
    )
    expected_orders = [_oracle_noop_decision(battle, 3) for battle in expected]

    result = bridge.step(
        torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64, device=device)
    )

    assert result.observation_valid.tolist() == [True, True]
    assert result.ticks_advanced.tolist() == [3, 3]
    assert result.player_order.tolist() == expected_orders
    assert result.action_success.tolist() == [[True, True], [True, True]]
    assert result.rewards.tolist() == [[0.0, -0.0], [0.0, -0.0]]
    assert not result.dones.any()
    assert not result.fallback.mask.any()
    assert result.structured.entity_ids.device.type == device
    assert result.cv.board.device.type == device
    assert result.rewards.device.type == device
    for row, battle in enumerate(expected):
        assert bridge.engine.runtime.battle.tick[row].item() == battle.tick
        assert bridge.engine.runtime.battle.time[row].item() == battle.time
        assert bridge.engine.runtime.battle.rng.python_state(row) == (
            battle.rng.getstate()
        )
    _assert_observations_exact(bridge, expected, result.structured, result.cv)


def test_unsupported_episode_is_routed_before_any_tensor_mutation() -> None:
    safe = _safe_battle(72_001)
    unsafe = BattleState(rng=random.Random(72_002))
    sources = [safe, unsafe]
    bridge = TensorResidentSelfPlay.from_battles(
        sources,
        decision_interval_ticks=2,
        max_entities=32,
        max_objects=32,
    )
    unsafe_before = battle_snapshot(unsafe)
    resident_tick_before = bridge.engine.runtime.battle.tick.clone()
    resident_rng_before = bridge.engine.runtime.battle.rng.python_state(1)
    resident_ids_before = bridge.engine.runtime.battle.entity_id[1].clone()

    result = bridge.step(torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64))

    assert result.observation_valid.tolist() == [True, False]
    assert result.ticks_advanced.tolist() == [2, 0]
    assert result.fallback.mask.tolist() == [False, True]
    assert result.fallback.row_indices.tolist() == [1]
    assert result.fallback.action_ids.tolist() == [[NO_OP_ACTION, NO_OP_ACTION]]
    assert result.fallback.ticks_completed.tolist() == [0]
    assert "outside guaranteed resident coverage" in str(result.fallback.reasons[0])
    assert len(result.fallback.scalar_battles) == 1
    assert (
        first_divergence(
            unsafe_before,
            battle_snapshot(result.fallback.scalar_battles[0]),
        )
        is None
    )
    assert bridge.engine.runtime.battle.tick[1].item() == resident_tick_before[1]
    assert bridge.engine.runtime.battle.rng.python_state(1) == resident_rng_before
    assert torch.equal(bridge.engine.runtime.battle.entity_id[1], resident_ids_before)


def test_invalid_action_penalty_and_max_tick_done_are_tensor_resident() -> None:
    source = _safe_battle(73_001)
    bridge = TensorResidentSelfPlay.from_battles(
        [source],
        decision_interval_ticks=4,
        max_ticks=2,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(),
    )

    result = bridge.step(torch.tensor([[0, NO_OP_ACTION]]))

    assert result.ticks_advanced.tolist() == [2]
    assert result.dones.tolist() == [True]
    assert result.action_success.tolist() == [[False, True]]
    assert result.rewards.tolist() == [[-0.01, 0.0]]
    assert not result.fallback.mask.any()


def test_reset_rows_replaces_only_selected_state_rng_and_episode_route() -> None:
    sources = [_safe_battle(74_001), _safe_battle(74_002)]
    bridge = TensorResidentSelfPlay.from_battles(
        sources,
        decision_interval_ticks=2,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(),
    )
    bridge.step(torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64))
    row_one_tick = bridge.engine.runtime.battle.tick[1].clone()
    row_one_time = bridge.engine.runtime.battle.time[1].clone()
    row_one_rng = bridge.engine.runtime.battle.rng.python_state(1)
    fresh = _safe_battle(74_101)
    ignored = _safe_battle(74_102)

    structured, cv, masks = bridge.reset_rows(
        [fresh, ignored], torch.tensor([True, False])
    )

    assert bridge.engine.runtime.battle.tick.tolist() == [0, int(row_one_tick)]
    assert bridge.engine.runtime.battle.time[0].item() == 0.0
    assert bridge.engine.runtime.battle.time[1].item() == row_one_time.item()
    assert bridge.engine.runtime.battle.rng.python_state(0) == fresh.rng.getstate()
    assert bridge.engine.runtime.battle.rng.python_state(1) == row_one_rng
    assert bridge._episode_resident.tolist() == [True, True]
    assert structured.entity_ids.shape[:2] == (2, 2)
    assert cv.board.shape[:2] == (2, 2)
    assert masks.shape[:2] == (2, 2)


def test_default_full_deck_route_is_stable_across_repeated_calls() -> None:
    source = BattleState(rng=random.Random(75_001))
    bridge = TensorResidentSelfPlay.from_battles(
        [source], max_entities=32, max_objects=32
    )
    before = bridge.engine.runtime.battle.rng.python_state(0)
    first = bridge.step(torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64))
    second = bridge.step(torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64))

    assert first.fallback.mask.tolist() == [True]
    assert second.fallback.mask.tolist() == [True]
    assert first.ticks_advanced.tolist() == second.ticks_advanced.tolist() == [0]
    assert bridge.engine.runtime.battle.rng.python_state(0) == before
    assert first.fallback.scalar_battles[0].rng.getstate() == source.rng.getstate()
