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
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase

DUE_SPELLS = (
    "Arrows",
    "BarbarianBarrel",
    "Earthquake",
    "Fireball",
    "Freeze",
    "GiantSnowball",
    "GoblinBarrel",
    "Graveyard",
    "Log",
    "Poison",
    "Rocket",
    "RoyalDelivery",
    "Tornado",
    "Zap",
)


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
    row: int = 0,
    slot: int = 0,
    sequence: int = 1,
    execute_at: float | None = None,
    x_units: int = 9_000,
    y_units: int = 10_000,
) -> None:
    pending = engine.pending_spells
    pending.active[row, slot] = True
    pending.execute_at[row, slot] = (
        engine.runtime.battle.time[row] if execute_at is None else execute_at
    )
    pending.sequence[row, slot] = sequence
    pending.card_id[row, slot] = engine.runtime.battle.card_to_id[spell_name]
    pending.player_id[row, slot] = 0
    pending.target_x_units[row, slot] = x_units
    pending.target_y_units[row, slot] = y_units


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
    command = engine.runtime.events.opcode[0] == int(RuntimeEventOpcode.COMMAND)
    assert engine.runtime.events.payload[0, command].tolist() == [
        engine.runtime.battle.card_to_id["Log"],
        engine.runtime.battle.card_to_id["RoyalDelivery"],
    ]
    owner_event = (
        torch.arange(engine.runtime.events.capacity) < engine.runtime.events.count[0]
    ) & ~command
    assert engine.runtime.events.target_id[0, owner_event].tolist() == [2, 3]


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
def test_mixed_owner_due_commands_use_global_deadline_sequence_order(
    device: str,
) -> None:
    battle, _ = _battle("Log")
    player = battle.players[0]
    player.hand = ["Log", "RoyalDelivery", "Knight", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=24,
        max_objects=16,
        event_capacity=128,
    )
    _queue(
        engine,
        "Log",
        slot=0,
        sequence=10,
        execute_at=0.04,
        x_units=1_000,
        y_units=2_000,
    )
    _queue(
        engine,
        "RoyalDelivery",
        slot=1,
        sequence=20,
        execute_at=0.02,
        x_units=3_000,
        y_units=4_000,
    )
    _queue(
        engine,
        "Log",
        slot=2,
        sequence=5,
        execute_at=0.02,
        x_units=5_000,
        y_units=6_000,
    )
    _queue(
        engine,
        "RoyalDelivery",
        slot=3,
        sequence=1,
        execute_at=0.04,
        x_units=7_000,
        y_units=8_000,
    )

    result = engine.step()

    assert result.committed.tolist() == [True]
    assert result.pending_spells.resolved_count.tolist() == [4]
    count = int(engine.runtime.events.count[0])
    command = engine.runtime.events.opcode[0, :count] == int(RuntimeEventOpcode.COMMAND)
    assert command.sum().item() == 4
    assert (
        engine.runtime.events.phase[0, :count][command].tolist()
        == [int(TickPhase.COMMANDS)] * 4
    )
    assert engine.runtime.events.source_id[0, :count][command].tolist() == [0] * 4
    assert engine.runtime.events.target_id[0, :count][command].tolist() == [0] * 4
    assert engine.runtime.events.payload[0, :count][command].tolist() == [
        engine.runtime.battle.card_to_id["Log"],
        engine.runtime.battle.card_to_id["RoyalDelivery"],
        engine.runtime.battle.card_to_id["RoyalDelivery"],
        engine.runtime.battle.card_to_id["Log"],
    ]
    assert torch.stack(
        (
            engine.runtime.events.x_units[0, :count][command],
            engine.runtime.events.y_units[0, :count][command],
        ),
        dim=1,
    ).tolist() == [
        [5_000, 6_000],
        [3_000, 4_000],
        [7_000, 8_000],
        [1_000, 2_000],
    ]


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
def test_every_due_spell_emits_one_exact_command_before_owner(device: str) -> None:
    battles = [_battle(spell)[0] for spell in DUE_SPELLS]
    engine = TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=64,
        max_objects=64,
        event_capacity=512,
    )
    for row, spell in enumerate(DUE_SPELLS):
        _queue(
            engine,
            spell,
            row=row,
            sequence=row + 1,
            x_units=9_000 + row,
            y_units=10_000 + row,
        )

    result = engine.step()

    assert result.committed.tolist() == [True] * len(DUE_SPELLS)
    for row, spell in enumerate(DUE_SPELLS):
        count = int(engine.runtime.events.count[row])
        command = engine.runtime.events.opcode[row, :count] == int(
            RuntimeEventOpcode.COMMAND
        )
        assert command.sum().item() == 1
        command_slot = int(torch.nonzero(command, as_tuple=False)[0, 0])
        assert command_slot == 0
        assert engine.runtime.events.phase[row, command_slot].item() == int(
            TickPhase.COMMANDS
        )
        assert engine.runtime.events.source_id[row, command_slot].item() == 0
        assert engine.runtime.events.target_id[row, command_slot].item() == 0
        assert engine.runtime.events.x_units[row, command_slot].item() == 9_000 + row
        assert engine.runtime.events.y_units[row, command_slot].item() == 10_000 + row
        assert (
            engine.runtime.events.payload[row, command_slot].item()
            == (engine.runtime.battle.card_to_id[spell])
        )


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
def test_due_command_capacity_failure_is_selectively_atomic(device: str) -> None:
    log, _ = _battle("Log")
    delivery, _ = _battle("RoyalDelivery")
    engine = TensorResidentEngine.from_battles(
        [log, delivery],
        device=device,
        max_entities=16,
        max_objects=8,
        event_capacity=8,
    )
    _queue(engine, "Log", row=0, sequence=1)
    _queue(engine, "RoyalDelivery", row=1, sequence=1)
    engine.runtime.events.count[0] = engine.runtime.events.capacity
    before_time = engine.runtime.battle.time.clone()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_pending = engine.pending_spells.active.clone()

    result = engine.step()

    assert result.committed.tolist() == [False, True]
    assert engine.runtime.battle.time[0].item() == before_time[0].item()
    assert torch.equal(engine.runtime.battle.entity_id[0], before_ids[0])
    assert engine.pending_spells.active[0].tolist() == before_pending[0].tolist()
    assert not engine.rolling_spells.state.active[0].any()
    assert engine.runtime.events.count[0].item() == engine.runtime.events.capacity
    assert not engine.pending_spells.active[1].any()
    row_one_count = int(engine.runtime.events.count[1])
    row_one_command = engine.runtime.events.opcode[1, :row_one_count] == int(
        RuntimeEventOpcode.COMMAND
    )
    assert row_one_command.sum().item() == 1
    assert engine.runtime.events.payload[1, :row_one_count][
        row_one_command
    ].tolist() == [engine.runtime.battle.card_to_id["RoyalDelivery"]]


def test_second_mixed_due_capacity_failure_rolls_back_entire_tick() -> None:
    battle, _ = _battle("Log")
    player = battle.players[0]
    player.hand = ["Log", "RoyalDelivery", "Knight", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=2
    )
    _queue(engine, "Log", slot=0, sequence=1)
    _queue(engine, "RoyalDelivery", slot=1, sequence=2)
    before_time = engine.runtime.battle.time.clone()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_events = engine.runtime.events.count.clone()

    result = engine.step()

    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.time, before_time)
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.events.count, before_events)
    assert engine.pending_spells.active[0, :2].tolist() == [True, True]
    assert not engine.rolling_spells.state.active.any()
    assert not engine.royal_delivery.active.any()
