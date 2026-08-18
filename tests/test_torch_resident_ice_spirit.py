from __future__ import annotations

from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.torch_sim.resident_ice_spirit import (
    IceSpiritReason,
    TensorIceSpiritState,
    step_ice_spirit_lifecycle_,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    battle._spawn_unit_at_position(
        position,
        player,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    entity = battle.entities[battle.next_entity_id - 1]
    assert isinstance(entity, Troop)
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _battle(distance: float = 1.0) -> tuple[BattleState, Troop, Troop]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    spirit = _spawn(battle, "IceSpirit", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 10.0 + distance))
    spirit.attack_cooldown = 0.0
    target.speed = 0.0
    target.damage = 0.0
    target.attack_cooldown = 10.0
    return battle, spirit, target


def _scalar_special_frame(battle: BattleState) -> None:
    entities = list(battle.entities.values())
    for entity in entities:
        if isinstance(entity, (Troop, Building)):
            entity.update_combat_component(battle.dt, battle)
    for entity in entities:
        if not isinstance(entity, (Troop, Building)) or not entity.is_alive:
            continue
        entity.begin_movement_tick()
        try:
            entity.update_movement_component(battle.dt, battle)
        finally:
            entity.finish_movement_tick(battle)
            entity.quantize_logic_position()


def _slot(runtime: TensorBattleRuntime, row: int, entity_id: int) -> int:
    found = torch.where(runtime.battle.entity_id[row] == entity_id)[0]
    assert found.numel() == 1
    return int(found[0].item())


def test_full_attack_jump_landing_freeze_lifecycle_matches_scalar(
    tensor_device: str,
) -> None:
    source, spirit, target = _battle()
    oracle = source.clone()
    runtime = TensorBattleRuntime.from_battles(
        [source],
        device=tensor_device,
        max_entities=8,
        event_capacity=32,
    )
    state = TensorIceSpiritState.from_battles(runtime, [source])
    spirit_slot = _slot(runtime, 0, spirit.id)
    target_slot = _slot(runtime, 0, target.id)

    for frame in range(3):
        _scalar_special_frame(oracle)
        result = step_ice_spirit_lifecycle_(runtime, state)
        assert result.committed.tolist() == [True]
        oracle_spirit = oracle.entities[spirit.id]
        assert runtime.battle.entity_x_units[0, spirit_slot].item() == round(
            oracle_spirit.position.x * 1_000
        )
        assert runtime.battle.entity_y_units[0, spirit_slot].item() == round(
            oracle_spirit.position.y * 1_000
        )
        assert runtime.battle.entity_hp[0, target_slot].item() == (
            oracle.entities[target.id].hitpoints
        )
        assert runtime.status.stun_timer[0, target_slot].item() == (
            oracle.entities[target.id].stun_timer
        )
        assert state.jump_active[0, spirit_slot].item() is (
            getattr(oracle_spirit, "_ice_spirit_jump_target", None) is not None
        )
        if frame == 0:
            assert result.jumped[0, spirit_slot].item()
            before = oracle_spirit.hitpoints
            oracle_spirit.take_damage(999.0)
            assert oracle_spirit.hitpoints == before
            assert result.immune[0, spirit_slot].item()

    assert not runtime.battle.entity_active[0, spirit_slot].item()
    assert result.self_died[0, spirit_slot].item()
    assert runtime.battle.entity_hp[0, target_slot].item() < target.hitpoints
    assert runtime.status.stun_timer[0, target_slot].item() == pytest.approx(1.1)
    assert state.combat.attack_cooldown[0, target_slot].item() == (
        oracle.entities[target.id].attack_cooldown
    )
    count = int(runtime.events.count[0].item())
    assert runtime.events.opcode[0, :count].tolist() == [
        RuntimeEventOpcode.MOVEMENT,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.STATUS,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
    ]
    assert runtime.events.phase[0, :count].tolist() == [TickPhase.MOVEMENT] * count


def test_lethal_landing_emits_death_and_does_not_freeze_dead_target() -> None:
    source, _, target = _battle(distance=0.2)
    target.hitpoints = 1
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=8, event_capacity=16
    )
    state = TensorIceSpiritState.from_battles(runtime, [source])
    target_slot = _slot(runtime, 0, target.id)

    result = step_ice_spirit_lifecycle_(runtime, state)

    assert result.committed.tolist() == [True]
    assert result.died[0, target_slot].item()
    assert not result.stunned[0, target_slot].item()
    assert runtime.status.stun_timer[0, target_slot].item() == 0.0
    assert runtime.events.opcode[0, : runtime.events.count[0]].tolist() == [
        RuntimeEventOpcode.MOVEMENT,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
    ]


def test_primary_death_in_flight_keeps_endpoint_and_freezes_other_target() -> None:
    source, spirit, primary = _battle()
    secondary = _spawn(source, "Knight", 1, Position(9.5, 11.0))
    secondary.speed = 0.0
    secondary.damage = 0.0
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=8, event_capacity=32
    )
    state = TensorIceSpiritState.from_battles(runtime, [source])
    spirit_slot = _slot(runtime, 0, spirit.id)
    primary_slot = _slot(runtime, 0, primary.id)
    secondary_slot = _slot(runtime, 0, secondary.id)

    first = step_ice_spirit_lifecycle_(runtime, state)
    assert first.jumped[0, spirit_slot].item()
    runtime.battle.entity_active[0, primary_slot] = False
    runtime.battle.entity_hp[0, primary_slot] = 0.0
    state.combat.alive[0, primary_slot] = False
    for _ in range(3):
        result = step_ice_spirit_lifecycle_(runtime, state)
        if result.self_died.any():
            break

    assert runtime.battle.entity_y_units[0, spirit_slot].item() == 11_000
    assert result.stunned[0, secondary_slot].item()
    assert runtime.status.stun_timer[0, secondary_slot].item() == pytest.approx(1.1)


def test_clone_fork_and_reset_preserve_independent_retained_lifecycle() -> None:
    left, _, _ = _battle()
    right, _, _ = _battle(distance=0.5)
    runtime = TensorBattleRuntime.from_battles(
        [left, right], max_entities=8, event_capacity=16
    )
    state = TensorIceSpiritState.from_battles(runtime, [left, right])
    cloned = state.clone()
    forked = state.fork([1, 0, 1])
    assert torch.equal(forked.jump_active[0], state.jump_active[1])
    assert forked.combat.hp.data_ptr() != state.combat.hp.data_ptr()
    cloned.jump_active[0, 0] = True
    assert not state.jump_active[0, 0].item()
    state.reset_rows_([0], cloned, [0])
    assert state.jump_active[0, 0].item()


def test_event_capacity_rollback_is_row_local_and_atomic() -> None:
    first, _, first_target = _battle(distance=0.0)
    second, _, second_target = _battle(distance=0.0)
    runtime = TensorBattleRuntime.from_battles(
        [first, second], max_entities=8, event_capacity=5
    )
    state = TensorIceSpiritState.from_battles(runtime, [first, second])
    runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.COMMAND,
        valid=torch.tensor([[True], [False]]),
    )
    before_hp = runtime.battle.entity_hp.clone()

    result = step_ice_spirit_lifecycle_(runtime, state)

    assert result.committed.tolist() == [False, True]
    assert result.reason.tolist() == [IceSpiritReason.EVENT_CAPACITY, 0]
    assert torch.equal(runtime.battle.entity_hp[0], before_hp[0])
    second_slot = _slot(runtime, 1, second_target.id)
    assert runtime.battle.entity_hp[1, second_slot] < before_hp[1, second_slot]
    first_slot = _slot(runtime, 0, first_target.id)
    assert runtime.battle.entity_hp[0, first_slot] == before_hp[0, first_slot]


def test_lethal_serialized_victim_payload_fails_closed_before_commit() -> None:
    source = BattleState(fast_path=False)
    source.entities.clear()
    source.next_entity_id = 1
    spirit = _spawn(source, "IceSpirit", 0, Position(9.0, 10.0))
    victim = _spawn(source, "Golem", 1, Position(9.0, 10.0))
    spirit.attack_cooldown = 0.0
    victim.hitpoints = 1
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=8, event_capacity=16
    )
    state = TensorIceSpiritState.from_battles(runtime, [source])
    before_hp = runtime.battle.entity_hp.clone()

    result = step_ice_spirit_lifecycle_(runtime, state)

    assert result.committed.tolist() == [False]
    assert result.reason.tolist() == [IceSpiritReason.UNSUPPORTED_DEATH_PAYLOAD]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert runtime.events.count.tolist() == [0]
    assert not result.jumped.any().item()
