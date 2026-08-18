from __future__ import annotations

import copy
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import TargetType, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.diagnostics import first_divergence
from clasher.torch_sim.oracle_event_capture import PythonOracleEventCapture
from clasher.torch_sim.resident_differential import (
    _oracle_events,
    _oracle_snapshot,
    _resident_events,
    _resident_snapshot,
)
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace
from clasher.torch_sim.runtime_state import TickPhase

AREA_SPELLS = ("Freeze", "Earthquake", "Poison", "Graveyard", "Tornado")


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _battle(spell_name: str, *, target_hp: int = 10_000) -> BattleState:
    battle = BattleState(fast_path=False)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = Troop(
        id=1,
        position=(
            Position(14.5, 30.0) if spell_name == "Graveyard" else Position(9.5, 14.5)
        ),
        player_id=1,
        card_stats=stats,
        hitpoints=target_hp,
        max_hitpoints=target_hp,
        damage=0,
        range=0,
        sight_range=0,
        speed=0,
        target_type=TargetType.BOTH,
    )
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    target.battle_state = battle  # type: ignore[attr-defined]
    battle.entities = {1: target}
    battle.next_entity_id = 2
    battle.players[0].hand = [spell_name, "Knight", None, None]
    battle.players[0].deck = [spell_name, "Knight"]
    battle.players[0].cycle_queue = deque()
    battle.players[0].elixir = 10.0
    return battle


def test_complete_area_spell_engine_lifetimes_are_exact(
    tensor_device: str,
) -> None:
    seeds = [_battle(name) for name in AREA_SPELLS]
    oracle = [copy.deepcopy(battle) for battle in seeds]
    engine = TensorResidentEngine.from_battles(
        seeds,
        device=tensor_device,
        max_entities=16,
        max_objects=8,
        event_capacity=512,
    )
    workspace = TensorResidentWorkspace(engine)
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    actions = torch.tensor([[action, NO_OP_ACTION]] * len(seeds), device=engine.device)
    order = torch.tensor([[0, 1]] * len(seeds), device=engine.device)

    for tick in range(205):
        event_start = engine.runtime.events.count.clone()
        captured_events = []
        for battle, name in zip(oracle, AREA_SPELLS, strict=True):
            with PythonOracleEventCapture(battle) as capture:
                if tick == 0:
                    assert capture.deploy_card(0, name, Position(9.5, 14.5))
                capture.step_logic_ticks(1)
                captured_events.append(tuple(capture.events))
        result = workspace.step(
            actions if tick == 0 else None,
            player_order=order,
        )
        assert result.committed.tolist() == [True] * len(seeds)

        # Commands resolved at t=1.0 did not exist during that elapsed frame.
        if tick == 19:
            assert engine.continuous_areas.age_ms.max().item() == 0
            assert engine.graveyards.age_ms.max().item() == 0
            assert engine.tornadoes.age_ms.max().item() == 0

        for row, (battle, name) in enumerate(zip(oracle, AREA_SPELLS, strict=True)):
            divergence = first_divergence(
                _oracle_snapshot(battle),
                _resident_snapshot(engine, row),
                path=f"rows[{row}]",
            )
            assert divergence is None, f"tick={tick} card={name}: {divergence}"
            assert engine.runtime.battle.rng.python_state(row) == battle.rng.getstate()
            actual_events = _resident_events(engine, row, int(event_start[row].item()))
            expected_events = _oracle_events(captured_events[row], engine)
            assert actual_events == expected_events, (
                f"tick={tick} card={name}: expected={expected_events} "
                f"actual={actual_events}"
            )

    assert not engine.continuous_areas.active.any()
    assert not engine.graveyards.active.any()
    assert not engine.tornadoes.active.any()


def test_clone_and_workspace_own_area_state_without_aliasing() -> None:
    engine = TensorResidentEngine.from_battles(
        [_battle("Poison")], max_entities=16, max_objects=8
    )
    cloned = engine.clone()
    workspace = TensorResidentWorkspace(engine)
    assert cloned.continuous_effect_deadline_seconds.data_ptr() == (
        engine.continuous_effect_deadline_seconds.data_ptr()
    )
    assert workspace.scratch.continuous_effect_deadline_seconds.data_ptr() == (
        engine.continuous_effect_deadline_seconds.data_ptr()
    )
    for name in ("continuous_areas", "graveyards", "tornadoes"):
        committed = getattr(engine, name)
        clone_owner = getattr(cloned, name)
        scratch = getattr(workspace.scratch, name)
        assert clone_owner.catalog is committed.catalog
        assert scratch.catalog is committed.catalog
        assert clone_owner.active.data_ptr() != committed.active.data_ptr()
        assert scratch.active.data_ptr() != committed.active.data_ptr()
    engine.continuous_areas.age_ms.fill_(700)
    workspace.refresh()
    assert torch.equal(
        workspace.scratch.continuous_areas.age_ms,
        engine.continuous_areas.age_ms,
    )


def test_mixed_area_due_resolution_rolls_back_the_entire_row() -> None:
    battle = _battle("Freeze")
    battle.players[1].hand = ["Tornado", "Knight", None, None]
    battle.players[1].deck = ["Tornado", "Knight"]
    battle.players[1].cycle_queue = deque()
    battle.players[1].elixir = 10.0
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=8, event_capacity=128
    )
    workspace = TensorResidentWorkspace(engine)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [
                action_space.encode_action(0, 9, 14, 0),
                action_space.encode_action(0, 9, 14, 1),
            ]
        ]
    )
    order = torch.tensor([[0, 1]])
    assert workspace.step(actions, player_order=order).committed.tolist() == [True]
    for _ in range(18):
        assert workspace.step(player_order=order).committed.tolist() == [True]
    before = engine.clone()

    failed = workspace.step(player_order=order)

    assert failed.committed.tolist() == [False]
    assert (
        workspace.scratch.runtime.phases.supported[0, TickPhase.OBJECTS].item() is False
    )
    assert torch.equal(engine.runtime.battle.tick, before.runtime.battle.tick)
    assert torch.equal(engine.runtime.battle.time, before.runtime.battle.time)
    assert torch.equal(
        engine.runtime.entity_pool.next_entity_id,
        before.runtime.entity_pool.next_entity_id,
    )
    assert torch.equal(engine.runtime.events.count, before.runtime.events.count)
    assert engine.runtime.battle.rng.python_state(0) == (
        before.runtime.battle.rng.python_state(0)
    )
    assert torch.equal(engine.pending_spells.active, before.pending_spells.active)
    assert not engine.continuous_areas.active.any()
    assert not engine.tornadoes.active.any()
