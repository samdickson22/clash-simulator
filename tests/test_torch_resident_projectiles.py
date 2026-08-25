from __future__ import annotations

from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, Troop
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase


def _set_noop_hand(battle: BattleState, card_name: str) -> None:
    for player in battle.players:
        player.hand = [card_name, None, None, None]
        player.deck = [card_name]
        player.cycle_queue = deque()
        player.elixir = 10.0


def _projectile_battle(
    card_name: str,
    *,
    source_position: Position | None = None,
    target_position: Position | None = None,
    target_hp: float | None = None,
) -> BattleState:
    source_position = source_position or Position(9, 10)
    target_position = target_position or Position(9, 12)
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card(card_name)
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None
    assert target_stats is not None
    if str(source_stats.card_type).lower() == "building":
        source = battle._spawn_entity(Building, source_position, 0, source_stats)
    else:
        battle._spawn_unit_at_position(
            source_position,
            0,
            source_stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        source = battle.entities[1]
    battle._spawn_unit_at_position(
        target_position,
        1,
        target_stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[2]
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source._spawn_hook_pending = False
    source._spawn_hook_fired = True
    source.target_id = target.id
    source.__dict__["_movement_target_id"] = target.id
    source.attack_cooldown = 0.0
    source.last_attack_time = -10.0
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0
    if target_hp is not None:
        target.hitpoints = target_hp
        target.max_hitpoints = target_hp
    _set_noop_hand(battle, card_name)
    return battle


def _slot_for_id(engine: TensorResidentEngine, entity_id: int) -> int:
    slots = torch.where(engine.runtime.battle.entity_id[0] == entity_id)[0]
    assert slots.numel() == 1
    return int(slots[0].item())


def _fixed_player_order(engine: TensorResidentEngine) -> torch.Tensor:
    return torch.tensor(
        [[0, 1]] * engine.batch_size,
        dtype=torch.int64,
        device=engine.device,
    )


def _assert_state_matches_python(
    oracle: BattleState, engine: TensorResidentEngine
) -> None:
    core = engine.runtime.battle
    tensor_ids = core.entity_id[0, engine.runtime.entity_pool.active[0]].tolist()
    assert sorted(tensor_ids) == sorted(oracle.entities)
    assert engine.runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    for entity_id, entity in oracle.entities.items():
        slot = _slot_for_id(engine, entity_id)
        assert core.entity_player[0, slot].item() == entity.player_id
        assert core.entity_kind[0, slot].item() == entity.entity_kind
        assert core.entity_hp[0, slot].item() == entity.hitpoints
        assert core.entity_x_units[0, slot].item() == round(entity.position.x * 1_000)
        assert core.entity_y_units[0, slot].item() == round(entity.position.y * 1_000)


def _assert_impact_event_order(new_phases: list[int], new_opcodes: list[int]) -> None:
    for index, (phase, opcode) in enumerate(zip(new_phases, new_opcodes, strict=True)):
        if phase != int(TickPhase.OBJECTS) or opcode != int(
            RuntimeEventOpcode.PROJECTILE
        ):
            continue
        assert new_opcodes[index + 1] == int(RuntimeEventOpcode.DAMAGE)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("card_name", "ticks"), (("Archer", 30), ("Cannon", 30), ("Xbow", 30))
)
def test_resident_combat_projectile_full_trace_matches_python(
    card_name: str, ticks: int, device: str
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = _projectile_battle(card_name)
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=24,
        max_objects=24,
        event_capacity=1_024,
    )
    previous_event_count = 0
    for _ in range(ticks):
        oracle.step_logic_ticks(1)
        result = engine.step(player_order=_fixed_player_order(engine))
        assert result.committed.tolist() == [True]
        _assert_state_matches_python(oracle, engine)
        source = oracle.entities[1]
        source_slot = _slot_for_id(engine, 1)
        assert engine.combat.attack_cooldown[0, source_slot].item() == (
            source.attack_cooldown
        )
        assert engine.combat.last_attack_time[0, source_slot].item() == (
            source.last_attack_time
        )
        target_slot = int(engine.combat.target_slot[0, source_slot].item())
        tensor_target = (
            None
            if target_slot < 0
            else int(engine.runtime.battle.entity_id[0, target_slot].item())
        )
        assert tensor_target == source.target_id
        current_event_count = int(engine.runtime.events.count[0].item())
        new_phases = engine.runtime.events.phase[
            0, previous_event_count:current_event_count
        ].tolist()
        new_opcodes = engine.runtime.events.opcode[
            0, previous_event_count:current_event_count
        ].tolist()
        _assert_impact_event_order(new_phases, new_opcodes)
        previous_event_count = current_event_count


def test_projectile_target_death_before_impact_preserves_endpoint_and_identity() -> (
    None
):
    battle = _projectile_battle("Archer", target_position=Position(9, 13))
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16, event_capacity=512
    )
    oracle.step_logic_ticks(1)
    first = engine.step(player_order=_fixed_player_order(engine))
    assert first.committed.tolist() == [True]
    _assert_state_matches_python(oracle, engine)
    assert isinstance(oracle.entities[3], Projectile)

    oracle.entities[2].is_alive = False
    oracle._cleanup_dead_entities()
    target_slot = _slot_for_id(engine, 2)
    engine.runtime.battle.entity_active[0, target_slot] = False
    engine._cleanup(torch.tensor([True]))
    event_start = int(engine.runtime.events.count[0].item())

    for _ in range(10):
        oracle.step_logic_ticks(1)
        result = engine.step(player_order=_fixed_player_order(engine))
        assert result.committed.tolist() == [True]
        _assert_state_matches_python(oracle, engine)
        if 3 not in oracle.entities:
            break
    assert 3 not in oracle.entities
    later_targets = engine.runtime.events.target_id[0, event_start:].tolist()
    later_opcodes = engine.runtime.events.opcode[0, event_start:].tolist()
    assert not any(
        opcode == int(RuntimeEventOpcode.DAMAGE) and target_id == 2
        for opcode, target_id in zip(later_opcodes, later_targets, strict=True)
    )


def _reservation_battle(target_y: float) -> tuple[BattleState, int]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    archer = battle.card_loader.get_card("Archer")
    knight = battle.card_loader.get_card("Knight")
    assert archer is not None
    assert knight is not None
    battle._spawn_unit_at_position(
        Position(9, 10),
        0,
        archer,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    battle._spawn_unit_at_position(
        Position(9, target_y),
        1,
        knight,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    battle._spawn_unit_at_position(
        Position(9, target_y - 3),
        0,
        archer,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    source, target, observer = (battle.entities[index] for index in (1, 2, 3))
    assert isinstance(source, Troop)
    target.hitpoints = 100.0
    target.max_hitpoints = 100.0
    target.stun_timer = 100.0
    source.target_id = target.id
    source.attack_cooldown = 10.0
    observer.target_id = target.id
    observer.attack_cooldown = 0.0
    observer.last_attack_time = -10.0
    source._create_projectile(target, battle)
    projectile = battle.entities[4]
    assert isinstance(projectile, Projectile)
    duration = projectile._native_pending_damage_duration_ms()
    _set_noop_hand(battle, "Archer")
    return battle, duration


@pytest.mark.parametrize(("target_y", "reserved"), ((17.0, True), (19.0, False)))
def test_pending_projectile_duration_boundary_matches_python(
    target_y: float, reserved: bool
) -> None:
    battle, duration = _reservation_battle(target_y)
    assert (duration <= 600) is reserved
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16, event_capacity=512
    )
    target_slot = _slot_for_id(engine, 2)
    assert engine.pending_projectile_max_duration_ms[0, target_slot].item() == duration

    oracle.step_logic_ticks(1)
    result = engine.step(player_order=_fixed_player_order(engine))

    assert result.committed.tolist() == [True]
    observer_slot = _slot_for_id(engine, 3)
    assert result.combat.attacked[0, observer_slot].item() is (not reserved)
    assert engine.combat.reserved_lethal[0, target_slot].item() is reserved
    _assert_state_matches_python(oracle, engine)


def test_same_frame_launches_do_not_change_reservation_snapshot() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    archer = battle.card_loader.get_card("Archer")
    knight = battle.card_loader.get_card("Knight")
    assert archer is not None
    assert knight is not None
    for x in (8, 10, 9):
        battle._spawn_unit_at_position(
            Position(x, 10),
            0,
            archer,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
    battle._spawn_unit_at_position(
        Position(9, 14),
        1,
        knight,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[4]
    target.hitpoints = 180.0
    target.max_hitpoints = 180.0
    target.stun_timer = 100.0
    for entity_id in (1, 2, 3):
        source = battle.entities[entity_id]
        source.target_id = target.id
        source.last_attack_time = -10.0
        source.attack_cooldown = 0.0 if entity_id < 3 else 0.1
    _set_noop_hand(battle, "Archer")
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=24, max_objects=24, event_capacity=1_024
    )

    oracle.step_logic_ticks(1)
    first = engine.step(player_order=_fixed_player_order(engine))
    assert first.committed.tolist() == [True]
    target_slot = _slot_for_id(engine, 4)
    assert first.combat.attacked[0, :3].tolist() == [True, True, False]
    assert engine.combat.reserved_lethal[0, target_slot].item() is False
    _assert_state_matches_python(oracle, engine)

    oracle.step_logic_ticks(1)
    second = engine.step(player_order=_fixed_player_order(engine))
    assert second.committed.tolist() == [True]
    assert second.combat.attacked[0, 2].item() is False
    assert engine.combat.reserved_lethal[0, target_slot].item() is True
    _assert_state_matches_python(oracle, engine)


def test_pending_duration_resets_when_low_physical_slot_is_reused() -> None:
    battle = _projectile_battle("Archer")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=256
    )
    engine.pending_projectile_max_duration_ms[0, 0] = 1_000
    engine.runtime.battle.entity_id[0, 0] = 99
    engine.runtime.entity_pool.active[0, 0] = True
    engine.runtime.battle.entity_active[0, 0] = True
    engine.runtime.entity_pool.next_entity_id[0] = 100

    engine._refresh_planes()

    assert engine.pending_projectile_max_duration_ms[0, 0].item() == 0


def test_near_target_crown_projectile_with_core_card_zero_fails_closed() -> None:
    battle = BattleState(fast_path=False)
    source = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 0
        and getattr(entity, "_crown_tower_slot", None) != "king"
    )
    knight = battle.card_loader.get_card("Knight")
    assert knight is not None
    battle._spawn_unit_at_position(
        Position(source.position.x, source.position.y + 2),
        1,
        knight,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[battle.next_entity_id - 1]
    target.stun_timer = 100.0
    source.target_id = target.id
    source.attack_cooldown = 0.0
    source.last_attack_time = -10.0
    for entity in battle.entities.values():
        if entity is not source and entity is not target:
            entity.stun_timer = 100.0
    _set_noop_hand(battle, "Knight")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, max_objects=32, event_capacity=1_024
    )
    source_slot = _slot_for_id(engine, source.id)
    engine.runtime.battle.entity_card[0, source_slot] = 0
    before_ids = engine.runtime.battle.entity_id.clone()
    before_time = engine.runtime.battle.time.clone()
    before_events = engine.runtime.events.count.clone()

    preflight = engine.preflight()
    result = engine.step(player_order=_fixed_player_order(engine))

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [
        int(ResidentUnsupportedReason.PROJECTILE_COMBAT)
    ]
    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.battle.time, before_time)
    assert torch.equal(engine.runtime.events.count, before_events)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_mixed_supported_and_unsupported_projectile_rows_are_atomic(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    supported = _projectile_battle("Archer")
    # Magic Archer now has an exact retained piercing owner. Firecracker's
    # recoil/fan-out lifecycle remains intentionally fail-closed here.
    unsupported = _projectile_battle("Firecracker")
    oracle = supported.clone()
    engine = TensorResidentEngine.from_battles(
        [supported, unsupported],
        device=device,
        max_entities=16,
        max_objects=16,
        event_capacity=512,
    )
    before_ids = engine.runtime.battle.entity_id[1].clone()
    before_hp = engine.runtime.battle.entity_hp[1].clone()
    before_time = engine.runtime.battle.time[1].clone()
    before_next = engine.runtime.entity_pool.next_entity_id[1].clone()
    before_events = engine.runtime.events.count[1].clone()

    oracle.step_logic_ticks(1)
    result = engine.step(player_order=_fixed_player_order(engine))

    assert result.committed.tolist() == [True, False]
    row_zero = engine.runtime.battle.entity_id[0].tolist()
    for entity_id, entity in oracle.entities.items():
        slot = row_zero.index(entity_id)
        assert engine.runtime.battle.entity_hp[0, slot].item() == entity.hitpoints
        assert engine.runtime.battle.entity_x_units[0, slot].item() == round(
            entity.position.x * 1_000
        )
        assert engine.runtime.battle.entity_y_units[0, slot].item() == round(
            entity.position.y * 1_000
        )
    assert torch.equal(engine.runtime.battle.entity_id[1], before_ids)
    assert torch.equal(engine.runtime.battle.entity_hp[1], before_hp)
    assert torch.equal(engine.runtime.battle.time[1], before_time)
    assert torch.equal(engine.runtime.entity_pool.next_entity_id[1], before_next)
    assert torch.equal(engine.runtime.events.count[1], before_events)
