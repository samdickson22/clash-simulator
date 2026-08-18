from __future__ import annotations

import random
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _crowded_hogs(owner: int, seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    target_stats = battle.card_loader.get_card("Cannon")
    assert target_stats is not None
    target = battle._spawn_entity(
        Building,
        Position(14.5, 19.0) if owner == 0 else Position(3.5, 13.0),
        1 - owner,
        target_stats,
    )
    target.hitpoints = 10_000
    target.max_hitpoints = 10_000
    target.deploy_delay_remaining = 0.0
    target.placement_delay_total = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0
    player = battle.players[owner]
    player.hand = ["RoyalHogs", "Knight", "Zap", "Fireball"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    battle.overtime_start_time = 4.25
    battle.tiebreaker_time = 4.3
    return battle


def test_mirrored_crowded_hogs_keep_windup_leash_through_tick_67(
    tensor_device: str,
) -> None:
    sources = (
        _crowded_hogs(0, 740_008),
        _crowded_hogs(1, 740_108),
    )
    oracles = [battle.clone() for battle in sources]
    engine = TensorResidentEngine.from_battles(
        [battle.clone() for battle in sources],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=256,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    deploy = 12 * 18 + 14
    result = None
    event_start = engine.runtime.events.count.clone()
    target_hp_before = [10_000.0, 10_000.0]

    for tick in range(68):
        batch_actions: list[tuple[int, int]] = []
        for row, (oracle, owner) in enumerate(zip(oracles, (0, 1), strict=True)):
            target_hp_before[row] = float(oracle.entities[1].hitpoints)
            actions = (
                (deploy, NO_OP_ACTION)
                if tick == 0 and owner == 0
                else (NO_OP_ACTION, deploy)
                if tick == 0
                else (NO_OP_ACTION, NO_OP_ACTION)
            )
            order = [0, 1]
            oracle.rng.shuffle(order)
            for player in order:
                assert action_space.apply_action(oracle, player, actions[player])
            oracle.step_logic_ticks(1)
            batch_actions.append(actions)
        event_start = engine.runtime.events.count.clone()
        result = engine.step(
            torch.tensor(batch_actions, dtype=torch.int64, device=tensor_device)
        )
        assert result.committed.tolist() == [True, True]

    assert result is not None
    core = engine.runtime.battle
    for row, oracle in enumerate(oracles):
        runtime_ids = engine.movement.entity_id[row].tolist()
        for entity_id in (1, 2, 3, 4, 5):
            slot = runtime_ids.index(entity_id)
            expected = oracle.entities[entity_id]
            assert engine.movement.position_units[row, slot].tolist() == [
                round(expected.position.x * 1_000),
                round(expected.position.y * 1_000),
            ]
            assert core.entity_hp[row, slot].item() == expected.hitpoints
            assert engine.combat.attack_cooldown[row, slot].item() == pytest.approx(
                expected.attack_cooldown
            )
            if isinstance(expected, Troop):
                assert engine.movement.facing_units[row, slot].tolist() == list(
                    expected.native_facing_units()
                )
                assert engine.movement.avoidance[row, slot].item() == (
                    expected._native_avoidance
                )
        hog_slot = runtime_ids.index(4)
        assert not result.movement.ordinary_moved[row, hog_slot].item()
        assert result.movement.collision_only_moved[row, hog_slot].item()
        assert engine.runtime.battle.rng.python_state(row) == oracle.rng.getstate()

        event_count = int(engine.runtime.events.count[row].item())
        first_event = int(event_start[row].item())
        damage_events = [
            (
                int(engine.runtime.events.phase[row, event].item()),
                float(engine.runtime.events.amount[row, event].item()),
                int(engine.runtime.events.target_id[row, event].item()),
            )
            for event in range(first_event, event_count)
            if int(engine.runtime.events.opcode[row, event].item())
            == int(RuntimeEventOpcode.DAMAGE)
            and int(engine.runtime.events.phase[row, event].item())
            in {int(TickPhase.COMBAT), int(TickPhase.BUILDING_LIFETIME)}
        ]
        total_loss = target_hp_before[row] - float(oracle.entities[1].hitpoints)
        expected_events = []
        if total_loss > 16.0:
            expected_events.append((int(TickPhase.COMBAT), total_loss - 16.0, 1))
        expected_events.append((int(TickPhase.BUILDING_LIFETIME), 16.0, 1))
        assert damage_events == expected_events

    owner_zero_hog = engine.movement.entity_id[0].tolist().index(4)
    assert engine.movement.position_units[0, owner_zero_hog].tolist() == [
        15_535,
        18_030,
    ]
