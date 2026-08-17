from __future__ import annotations

import random
from collections import deque
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import (
    RESIDENT_PHASE_ORDER,
    TensorResidentEngine,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase

DEPLOY_KNIGHT_FAR_FROM_COMBAT = 1 * 18 + 6


def _set_hand(battle: BattleState, first: str) -> None:
    player = battle.players[0]
    player.hand = [first, "Zap", "Cannon", "Fireball"]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 10.0


def _segment_battle() -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(711_204))
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
    _set_hand(battle, "Knight")
    return battle


def _engine_snapshot(engine: TensorResidentEngine) -> dict[str, torch.Tensor]:
    result: dict[str, torch.Tensor] = {}
    owners = (
        ("battle", engine.runtime.battle),
        ("rng", engine.runtime.battle.rng),
        ("pool", engine.runtime.entity_pool),
        ("runtime_status", engine.runtime.status),
        ("phases", engine.runtime.phases),
        ("events", engine.runtime.events),
        ("combat", engine.combat),
        ("movement", engine.movement),
        ("status", engine.status),
        ("mechanics", engine.mechanics),
        ("objects", engine.objects),
        ("object_state", engine.objects.objects),
    )
    for owner_name, owner in owners:
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if isinstance(value, torch.Tensor):
                result[f"{owner_name}.{descriptor.name}"] = value.clone()
    result["runtime.supported"] = engine.runtime.supported.clone()
    result["runtime.dirty"] = engine.runtime.dirty.clone()
    result["facing_x"] = engine.facing_x_units.clone()
    result["facing_y"] = engine.facing_y_units.clone()
    return result


def test_resident_phase_order_matches_python_battle_manager() -> None:
    assert RESIDENT_PHASE_ORDER == (
        TickPhase.CLOCKS_AND_PLAYERS,
        TickPhase.COMMANDS,
        TickPhase.PROJECTILE_RESERVATIONS,
        TickPhase.COMBAT,
        TickPhase.MOVEMENT,
        TickPhase.COLLISION,
        TickPhase.BUILDING_LIFETIME,
        TickPhase.STATUS,
        TickPhase.OBJECTS,
        TickPhase.CLEANUP_AND_SPAWNS,
        TickPhase.WIN_CONDITIONS,
    )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_enabled_knight_segment_deploys_moves_attacks_and_cleans_death_without_python(
    device: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = _segment_battle()
    oracle = battle.clone()
    trace = (
        (DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION),
        (NO_OP_ACTION, NO_OP_ACTION),
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    for player_actions in trace:
        order = [0, 1]
        oracle.rng.shuffle(order)
        for player in order:
            assert action_space.apply_action(oracle, player, player_actions[player])
        oracle.step_logic_ticks(1)
    assert 1 not in oracle.entities

    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=16,
        max_objects=16,
        event_capacity=512,
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Python callback entered resident supported path")

    monkeypatch.setattr(BattleState, "deploy_card", forbidden)
    monkeypatch.setattr(Troop, "update_combat_component", forbidden)
    monkeypatch.setattr(Troop, "update_movement_component", forbidden)
    monkeypatch.setattr(Troop, "update_buff_component", forbidden)
    monkeypatch.setattr(Troop, "tick_character_object_phase", forbidden)
    monkeypatch.setattr(Entity, "on_spawn", forbidden)
    monkeypatch.setattr(Entity, "on_death", forbidden)

    deployed = False
    moved = False
    attacked = False
    cleaned = False
    for tick, player_actions in enumerate(trace):
        actions = torch.tensor(
            [player_actions],
            dtype=torch.int64,
            device=device,
        )
        result = engine.step(actions)
        assert result.committed.tolist() == [True], (
            tick,
            result.preflight.reasons,
            result.movement.unsupported_reasons,
            result.objects.unsupported_reasons,
        )
        deployed |= 3 in engine.runtime.battle.entity_id[0].tolist()
        moved |= bool(result.movement.ordinary_moved.any().item())
        attacked |= bool(result.combat.attacked.any().item())
        cleaned |= 1 not in engine.runtime.battle.entity_id[0].tolist()
    assert deployed and moved and attacked and cleaned
    assert tick == 1
    runtime_ids = engine.runtime.battle.entity_id[0].tolist()
    assert {entity_id for entity_id in runtime_ids if entity_id} == set(oracle.entities)
    assert engine.runtime.battle.tick.item() == oracle.tick
    assert engine.runtime.battle.time.item() == oracle.time
    assert engine.runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    assert engine.runtime.battle.elixir[0].tolist() == [
        player.elixir for player in oracle.players
    ]
    for entity_id, entity in oracle.entities.items():
        slot = runtime_ids.index(entity_id)
        assert engine.runtime.battle.entity_x_units[0, slot].item() == round(
            entity.position.x * 1_000
        )
        assert engine.runtime.battle.entity_y_units[0, slot].item() == round(
            entity.position.y * 1_000
        )
        assert engine.runtime.battle.entity_hp[0, slot].item() == entity.hitpoints
        assert (
            engine.runtime.battle.entity_deploy_delay[0, slot].item()
            == entity.deploy_delay_remaining
        )
    opcodes = engine.runtime.events.opcode[0, : engine.runtime.events.count[0]].tolist()
    assert RuntimeEventOpcode.SPAWN in opcodes
    assert RuntimeEventOpcode.DAMAGE in opcodes
    assert RuntimeEventOpcode.DEATH in opcodes
    assert engine.runtime.battle.entity_id.device.type == device


def test_action_mechanic_opcode_is_reported_and_rejected_before_mutation() -> None:
    battle = _segment_battle()
    _set_hand(battle, "Golem")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16
    )
    actions = torch.tensor([[DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION]])
    preflight = engine.preflight(actions)
    assert not preflight.supported.item()
    assert preflight.unsupported_mechanic_opcodes[0]
    assert "unsupported mechanic opcodes" in str(preflight.reasons[0])
    before = _engine_snapshot(engine)

    result = engine.step(actions)

    assert not result.committed.item()
    after = _engine_snapshot(engine)
    assert after.keys() == before.keys()
    for name, expected in before.items():
        torch.testing.assert_close(
            after[name], expected, rtol=0, atol=0, equal_nan=True, msg=name
        )


def test_cross_phase_event_overflow_discards_whole_tick_including_rng_and_clock() -> (
    None
):
    battle = BattleState(fast_path=False, rng=random.Random(811_950))
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    for player, y in ((0, 10.0), (1, 10.8)):
        battle._spawn_unit_at_position(
            Position(9.0, y),
            player,
            stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
    battle.entities[1].attack_cooldown = 0.0
    battle.entities[2].hitpoints = 100.0
    battle.entities[2].stun_timer = 100.0
    _set_hand(battle, "Knight")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=1
    )
    before = _engine_snapshot(engine)

    result = engine.step()

    assert not result.committed.item()
    after = _engine_snapshot(engine)
    for name, expected in before.items():
        torch.testing.assert_close(
            after[name], expected, rtol=0, atol=0, equal_nan=True, msg=name
        )
