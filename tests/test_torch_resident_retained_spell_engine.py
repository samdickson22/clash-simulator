from __future__ import annotations

import copy
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.resident_engine import TensorResidentEngine


def _battle(spell_name: str) -> tuple[BattleState, Troop]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.0, 10.0), 1, stats)
    assert isinstance(target, Troop)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0
    player = battle.players[0]
    player.hand = [spell_name, "Knight", "Cannon", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 10.0
    return battle, target


def _queue(
    engine: TensorResidentEngine,
    spell_name: str,
    *,
    slot: int = 0,
    sequence: int = 1,
) -> None:
    pending = engine.pending_spells
    pending.active[0, slot] = True
    pending.execute_at[0, slot] = engine.runtime.battle.time[0]
    pending.sequence[0, slot] = sequence
    pending.card_id[0, slot] = engine.runtime.battle.card_to_id[spell_name]
    pending.player_id[0, slot] = 0
    pending.target_x_units[0, slot] = 9_000
    pending.target_y_units[0, slot] = 10_000


def _oracle_object_tick(battle: BattleState) -> None:
    ids = set(battle.entities)
    battle._run_object_phase(battle.dt, ids, ids)
    battle._cleanup_dead_entities()


def _represented(engine: TensorResidentEngine) -> list[tuple[int, str, float, float]]:
    core = engine.runtime.battle
    return sorted(
        (
            int(core.entity_id[0, slot]),
            core.card_names[int(core.entity_card[0, slot])],
            float(core.entity_hp[0, slot]),
            float(core.entity_deploy_delay[0, slot]),
        )
        for slot in range(engine.runtime.max_entities)
        if bool(engine.runtime.entity_pool.active[0, slot])
        and int(core.entity_kind[0, slot]) in {0, 1}
    )


def _oracle_represented(battle: BattleState) -> list[tuple[int, str, float, float]]:
    return sorted(
        (
            entity_id,
            str(entity.card_stats.name),
            float(entity.hitpoints),
            float(entity.deploy_delay_remaining),
        )
        for entity_id, entity in battle.entities.items()
        if getattr(entity, "entity_kind", 4) in {0, 1}
    )


@pytest.mark.parametrize("spell_name", ("Log", "BarbarianBarrel", "RoyalDelivery"))
@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
def test_complete_retained_spell_engine_lifecycle_matches_scalar(
    spell_name: str,
    device: str,
) -> None:
    source, target = _battle(spell_name)
    oracle = copy.deepcopy(source)
    assert SPELL_REGISTRY[spell_name].cast(oracle, 0, Position(9.0, 10.0))
    engine = TensorResidentEngine.from_battles(
        [source],
        device=device,
        max_entities=24,
        max_objects=16,
        event_capacity=512,
    )
    core_card = engine.runtime.battle.card_to_id[spell_name]
    assert engine.spell_ingress.episode_supported_core[core_card]
    _queue(engine, spell_name)

    for _ in range(100):
        _oracle_object_tick(oracle)
        engine.runtime.events.clear()
        result = engine.step()
        assert result.committed.tolist() == [True]
        active = (
            engine.royal_delivery.active.any()
            if spell_name == "RoyalDelivery"
            else engine.rolling_spells.state.active.any()
        )
        if not bool(active):
            break
    else:
        raise AssertionError("retained spell did not finish")

    assert _represented(engine) == _oracle_represented(oracle)
    target_slot = int(
        torch.nonzero(engine.runtime.battle.entity_id[0] == target.id).item()
    )
    assert not engine.runtime.battle.entity_hp_integer_kind[0, target_slot]


def test_mixed_due_commands_follow_sequence_order() -> None:
    battle, _ = _battle("Log")
    player = battle.players[0]
    player.hand = ["Log", "RoyalDelivery", "Knight", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=24, max_objects=16, event_capacity=64
    )
    _queue(engine, "RoyalDelivery", slot=0, sequence=2)
    _queue(engine, "Log", slot=1, sequence=1)

    result = engine.step()

    assert result.committed.tolist() == [True]
    assert result.pending_spells.resolved_count.tolist() == [2]
    assert engine.rolling_spells.state.entity_id[0, 0].item() == 2
    assert engine.royal_delivery.entity_id[0, 0].item() == 3
    assert engine.runtime.events.source_id[0, :2].tolist() == [2, 3]


def test_second_mixed_due_capacity_failure_rolls_back_entire_tick() -> None:
    battle, _ = _battle("Log")
    player = battle.players[0]
    player.hand = ["Log", "RoyalDelivery", "Knight", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=1
    )
    _queue(engine, "Log", slot=0, sequence=1)
    _queue(engine, "RoyalDelivery", slot=1, sequence=2)
    before_time = engine.runtime.battle.time.clone()
    before_ids = engine.runtime.battle.entity_id.clone()

    result = engine.step()

    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.time, before_time)
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert engine.pending_spells.active[0, :2].tolist() == [True, True]
    assert not engine.rolling_spells.state.active.any()
    assert not engine.royal_delivery.active.any()
