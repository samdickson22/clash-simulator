from __future__ import annotations

import copy
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import RollingProjectile, Troop
from clasher.spells import SPELL_REGISTRY, RollingProjectileSpell
from clasher.torch_sim.resident_pending_spells import TensorResidentPendingSpells
from clasher.torch_sim.resident_rolling_spell import (
    TensorResidentRollingSpells,
    TensorRollingDueHandoff,
    TensorRollingProjectileState,
    TensorRollingSpellCatalog,
    TensorRollingTargets,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)

SPELLS = ("Log", "BarbarianBarrel")


def _battle(spell_name: str) -> tuple[BattleState, Troop]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    player = battle.players[0]
    player.hand = [spell_name, "Knight", "Cannon", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    player.cycle_queue = deque()
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.0, 12.0), 1, stats)
    assert isinstance(target, Troop)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    return battle, target


def _stack(
    battle: BattleState,
    *,
    device: str,
    event_capacity: int = 256,
) -> tuple[
    TensorBattleRuntime,
    TensorResidentPendingSpells,
    TensorResidentRollingSpells,
]:
    runtime = TensorBattleRuntime.from_battles(
        [battle], device=device, max_entities=16, event_capacity=event_capacity
    )
    catalog = TensorRollingSpellCatalog.compile(runtime, battle)
    targets = TensorRollingTargets.from_battles(runtime, [battle], catalog)
    state = TensorRollingProjectileState.empty(
        1, 4, runtime.max_entities, device=device
    )
    pending = TensorResidentPendingSpells.from_battles(
        runtime, [battle], runtime.catalog
    )
    return runtime, pending, TensorResidentRollingSpells(catalog, state, targets)


def _queue_due(
    runtime: TensorBattleRuntime,
    pending: TensorResidentPendingSpells,
    rolling: TensorResidentRollingSpells,
    spell_name: str,
) -> TensorRollingDueHandoff:
    core = next(
        index
        for index, name in enumerate(runtime.battle.card_names)
        if name == spell_name
        or (
            isinstance(SPELL_REGISTRY.get(name), RollingProjectileSpell)
            and SPELL_REGISTRY[name].name == SPELL_REGISTRY[spell_name].name
        )
    )
    pending.active[0, 0] = True
    pending.execute_at[0, 0] = runtime.battle.time[0]
    pending.sequence[0, 0] = 1
    pending.card_id[0, 0] = core
    pending.player_id[0, 0] = 0
    pending.target_x_units[0, 0] = 9_000
    pending.target_y_units[0, 0] = 8_000
    return TensorRollingDueHandoff.from_pending(runtime, pending, rolling.catalog)


@pytest.mark.parametrize("spell_name", SPELLS)
@pytest.mark.parametrize(
    "device",
    [
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ],
)
def test_full_rolling_spell_lifecycle_matches_scalar(
    spell_name: str,
    device: str,
) -> None:
    source, target = _battle(spell_name)
    oracle = copy.deepcopy(source)
    spell = SPELL_REGISTRY[spell_name]
    assert isinstance(spell, RollingProjectileSpell)
    assert spell.cast(oracle, 0, Position(9.0, 8.0))
    runtime, pending, rolling = _stack(source, device=device)
    handoff = _queue_due(runtime, pending, rolling, spell_name)
    spell_id = runtime.battle.card_to_id[spell_name]
    runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.COMMAND,
        valid=torch.ones((1, 1), dtype=torch.bool, device=runtime.device),
        x_units=9_000,
        y_units=8_000,
        payload=spell_id,
    )

    committed = rolling.consume_due_(runtime, pending, handoff)
    assert committed.tolist() == [True]
    assert not pending.active.any()
    assert rolling.state.active.sum().item() == 1
    roller_id = int(rolling.state.entity_id[0, 0].item())
    roller_slot = int(torch.nonzero(runtime.battle.entity_id[0] == roller_id).item())
    assert runtime.battle.entity_kind[0, roller_slot].item() == 2
    assert runtime.battle.entity_card[0, roller_slot].item() == 0
    assert runtime.battle.entity_hp[0, roller_slot].item() == 1.0
    assert runtime.battle.entity_hp_integer_kind[0, roller_slot].item()
    assert rolling.state.card_id[0, 0].item() == spell_id
    assert runtime.events.count.item() == 2
    assert runtime.events.phase[0, :2].tolist() == [
        TickPhase.COMMANDS,
        TickPhase.COMMANDS,
    ]
    assert runtime.events.opcode[0, :2].tolist() == [
        RuntimeEventOpcode.COMMAND,
        RuntimeEventOpcode.SPAWN,
    ]
    assert runtime.events.source_id[0, :2].tolist() == [0, 0]
    assert runtime.events.target_id[0, :2].tolist() == [0, roller_id]
    assert runtime.events.payload[0, :2].tolist() == [spell_id, spell_id]
    oracle_roller = next(
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, RollingProjectile)
    )
    assert rolling.state.spawn_delay_ms[0, 0].item() == pytest.approx(
        oracle_roller.spawn_delay * 1_000
    )

    terminal_result = None
    knockback_seen = False
    for _ in range(100):
        oracle_rollers = [
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, RollingProjectile)
        ]
        if not oracle_rollers:
            break
        oracle_rollers[0].update(0.05, oracle)
        oracle._cleanup_dead_entities()
        runtime.events.clear()
        result = rolling.step_(runtime)
        assert result.committed.tolist() == [True]
        knockback_seen = knockback_seen or bool(result.knockback.valid.any())
        if not rolling.state.active.any():
            terminal_result = result
    assert terminal_result is not None
    target_slot = int(torch.nonzero(runtime.battle.entity_id[0] == target.id).item())
    assert runtime.battle.entity_hp[0, target_slot].item() == (
        oracle.entities[target.id].hitpoints
    )
    tensor_children = [
        int(entity_id)
        for entity_id in runtime.battle.entity_id[0].tolist()
        if entity_id > target.id
    ]
    oracle_children = [
        entity_id
        for entity_id, entity in oracle.entities.items()
        if not isinstance(entity, RollingProjectile) and entity_id > target.id
    ]
    assert tensor_children == oracle_children
    if oracle_children:
        child_slot = int(
            torch.nonzero(runtime.battle.entity_id[0] == oracle_children[0]).item()
        )
        oracle_child = oracle.entities[oracle_children[0]]
        assert runtime.battle.entity_y_units[0, child_slot].item() == round(
            oracle_child.position.y * 1_000
        )
        assert runtime.battle.entity_deploy_delay[0, child_slot].item() == (
            oracle_child.deploy_delay_remaining
        )
    if spell.knockback_distance > 0:
        assert knockback_seen


def test_hit_group_prevents_second_damage_and_public_events_are_stable() -> None:
    battle, target = _battle("Log")
    runtime, pending, rolling = _stack(battle, device="cpu")
    rolling.consume_due_(runtime, pending, _queue_due(runtime, pending, rolling, "Log"))
    damage_events = 0
    for _ in range(100):
        runtime.events.clear()
        rolling.step_(runtime)
        damage_events += int(
            (
                runtime.events.opcode[0, : runtime.events.count[0]]
                == RuntimeEventOpcode.DAMAGE
            )
            .sum()
            .item()
        )
        if not rolling.state.active.any():
            break
    assert damage_events == 1
    slot = int(torch.nonzero(runtime.battle.entity_id[0] == target.id).item())
    assert runtime.battle.entity_hp[0, slot].item() == target.hitpoints - 268


def test_due_capacity_failure_is_atomic() -> None:
    battle, _ = _battle("Log")
    runtime, pending, rolling = _stack(battle, device="cpu", event_capacity=1)
    runtime.events.count[0] = 1
    before = runtime.battle.entity_id.clone()
    handoff = _queue_due(runtime, pending, rolling, "Log")

    committed = rolling.consume_due_(runtime, pending, handoff)

    assert committed.tolist() == [False]
    assert torch.equal(runtime.battle.entity_id, before)
    assert pending.active[0, 0]
    assert not rolling.state.active.any()


def test_inflight_event_capacity_failure_rolls_back_hit_and_roller_state() -> None:
    battle, target = _battle("Log")
    runtime, pending, rolling = _stack(battle, device="cpu", event_capacity=2)
    rolling.consume_due_(runtime, pending, _queue_due(runtime, pending, rolling, "Log"))
    runtime.events.clear()

    for _ in range(100):
        before_hp = runtime.battle.entity_hp.clone()
        before_state = rolling.state.clone()
        runtime.events.count[0] = runtime.events.capacity
        result = rolling.step_(runtime)
        if result.hit.any():
            assert result.committed.tolist() == [False]
            slot = int(torch.nonzero(runtime.battle.entity_id[0] == target.id).item())
            assert runtime.battle.entity_hp[0, slot] == before_hp[0, slot]
            for name in vars(before_state):
                assert torch.equal(
                    getattr(rolling.state, name), getattr(before_state, name)
                ), name
            break
        runtime.events.clear()
    else:
        raise AssertionError("roller never reached the target")


def test_roller_state_clone_fork_and_reset_are_independent() -> None:
    state = TensorRollingProjectileState.empty(2, 3, 5, device="cpu")
    state.active[0, 1] = True
    state.entity_id[0, 1] = 7
    clone = state.clone()
    fork = state.fork([0, 0])
    assert clone.entity_id.data_ptr() != state.entity_id.data_ptr()
    assert fork.entity_id[:, 1].tolist() == [7, 7]
    clone.reset_(clone.active)
    assert state.active[0, 1]
    assert not clone.active.any()
