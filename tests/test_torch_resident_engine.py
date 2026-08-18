from __future__ import annotations

import inspect
import random
from collections import deque
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
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
    player.deck = [card for card in player.hand if card is not None]
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
    attacker._movement_target_id = 1  # type: ignore[attr-defined]
    attacker.attack_cooldown = 0.0
    _set_hand(battle, "Knight")
    return battle


def _crowded_battles(count: int = 4) -> list[BattleState]:
    battles: list[BattleState] = []
    for row in range(count):
        battle = _segment_battle()
        battle.rng = random.Random(733_000 + row)
        stats = battle.card_loader.get_card("Knight")
        assert stats is not None
        for spectator in range(6):
            battle._spawn_unit_at_position(
                Position(1.0 + spectator * 0.6, 4.0 + (spectator % 2)),
                0,
                stats,
                deploy_delay_override=0.0,
                snap_to_valid=False,
            )
            entity = battle.entities[battle.next_entity_id - 1]
            entity.stun_timer = 100.0
            entity.attack_cooldown = 10.0
        battles.append(battle)
    return battles


def _cross_river_battle(
    *,
    source_player: int,
    bridge_x: float,
) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(744_100))
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    source_y, target_y = (14.25, 18.75) if source_player == 0 else (17.75, 13.25)
    battle._spawn_unit_at_position(
        Position(bridge_x, source_y),
        source_player,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    battle._spawn_unit_at_position(
        Position(bridge_x, target_y),
        1 - source_player,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    source = battle.entities[1]
    target = battle.entities[2]
    source.target_id = target.id
    # Force resident combat to establish the movement lock and compile its
    # route instead of inheriting a boundary-compiled retained route.
    source._movement_target_id = None  # type: ignore[attr-defined]
    source.attack_cooldown = 10.0
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0
    _set_hand(battle, "Knight")
    return battle


def _active_river_battle(owner: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(744_900 + owner))
    battle.entities.clear()
    battle.next_entity_id = 1
    hog_stats = battle.card_loader.get_card("HogRider")
    target_stats = battle.card_loader.get_card("Cannon")
    assert hog_stats is not None and target_stats is not None
    source_y, landing_y, target_y = (
        (14.75, 14.85, 18.0) if owner == 0 else (17.25, 17.15, 14.0)
    )
    battle._spawn_unit_at_position(
        Position(9.25, source_y),
        owner,
        hog_stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    battle._spawn_entity(
        Building,
        Position(9.25, target_y),
        1 - owner,
        target_stats,
    )
    source = battle.entities[1]
    target = battle.entities[2]
    assert isinstance(source, Troop)
    source.target_id = target.id
    source._movement_target_id = target.id
    source.attack_cooldown = 0.5
    source._river_jump_origin = Position(9.25, source_y)
    source._river_jump_target = Position(9.25, landing_y)
    source._river_jump_elapsed = 0.0
    source._river_jump_duration = 0.05
    source._river_jump_active = True
    source._special_move_active = True
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0
    _set_hand(battle, "HogRider")
    return battle


def _oracle_trace(battles: list[BattleState]) -> None:
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    trace = (
        (DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION),
        (NO_OP_ACTION, NO_OP_ACTION),
    )
    for player_actions in trace:
        for battle in battles:
            order = [0, 1]
            battle.rng.shuffle(order)
            for player in order:
                assert action_space.apply_action(battle, player, player_actions[player])
            battle.step_logic_ticks(1)


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


def test_standard_crown_only_tick_preserves_synthesized_combat_traits() -> None:
    battle = BattleState(fast_path=False, rng=random.Random(912_044))
    oracle = battle.clone()
    order = [0, 1]
    oracle.rng.shuffle(order)
    oracle.step_logic_ticks(1)
    engine = TensorResidentEngine.from_battles([battle])

    result = engine.step()

    assert result.committed.tolist() == [True]
    assert engine.runtime.battle.tick.item() == oracle.tick
    assert engine.runtime.battle.time.item() == oracle.time
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    assert engine.runtime.battle.elixir[0].tolist() == [
        player.elixir for player in oracle.players
    ]
    runtime_ids = engine.runtime.battle.entity_id[0].tolist()
    assert {entity_id for entity_id in runtime_ids if entity_id} == set(oracle.entities)
    for entity_id, entity in oracle.entities.items():
        slot = runtime_ids.index(entity_id)
        assert engine.runtime.battle.entity_hp[0, slot].item() == entity.hitpoints
        assert (
            engine.runtime.battle.entity_last_attack_time[0, slot].item()
            == entity.last_attack_time
        )
        assert engine.combat.range_units[0, slot].item() == round(entity.range * 1_000)
        assert engine.combat.hit_speed_ms[0, slot].item() == int(
            getattr(entity.card_stats, "hit_speed", 0) or 0
        )


def test_supported_preflight_and_route_compilation_have_no_host_row_extraction() -> (
    None
):
    for method in (
        TensorResidentEngine.preflight,
        TensorResidentEngine._compile_straight_ground_routes_,
    ):
        source = inspect.getsource(method)
        assert ".item(" not in source
        assert ".tolist(" not in source


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
            result.preflight.reason_code.tolist(),
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


def test_represented_action_mechanic_opcode_deploys_and_initializes_owners() -> None:
    battle = _segment_battle()
    _set_hand(battle, "Golem")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16
    )
    actions = torch.tensor([[DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION]])
    preflight = engine.preflight(actions)
    assert preflight.supported.item()
    assert preflight.mechanic_opcode_present[0].any()

    result = engine.step(actions)

    assert result.committed.item()
    death_owner = engine.mechanic_deployment.catalog.owner_index("death_payload")
    terminal_owner = engine.mechanic_deployment.catalog.owner_index("terminal")
    assert engine.mechanic_deployment.state.owner_entity_id[death_owner].any()
    assert engine.mechanic_deployment.state.owner_entity_id[terminal_owner].any()


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_crowded_batched_rows_match_oracle_exactly(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    sources = _crowded_battles()
    oracle = [battle.clone() for battle in sources]
    _oracle_trace(oracle)
    engine = TensorResidentEngine.from_battles(
        [battle.clone() for battle in sources],
        device=device,
        max_entities=24,
        max_objects=24,
        event_capacity=128,
    )
    trace = (
        (DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION),
        (NO_OP_ACTION, NO_OP_ACTION),
    )
    for player_actions in trace:
        actions = torch.tensor(
            [player_actions for _ in sources],
            dtype=torch.int64,
            device=device,
        )
        result = engine.step(actions)
        assert result.committed.all()

    for row, expected in enumerate(oracle):
        runtime_ids = engine.runtime.battle.entity_id[row].tolist()
        assert {entity_id for entity_id in runtime_ids if entity_id} == set(
            expected.entities
        )
        assert engine.runtime.battle.tick[row].item() == expected.tick
        assert engine.runtime.battle.time[row].item() == expected.time
        assert engine.runtime.battle.rng.python_state(row) == expected.rng.getstate()
        assert engine.runtime.entity_pool.next_entity_id[row].item() == (
            expected.next_entity_id
        )
        assert engine.runtime.battle.elixir[row].tolist() == [
            player.elixir for player in expected.players
        ]
        for entity_id, entity in expected.entities.items():
            slot = runtime_ids.index(entity_id)
            assert engine.runtime.battle.entity_x_units[row, slot].item() == round(
                entity.position.x * 1_000
            )
            assert engine.runtime.battle.entity_y_units[row, slot].item() == round(
                entity.position.y * 1_000
            )
            assert engine.runtime.battle.entity_hp[row, slot].item() == entity.hitpoints
            assert (
                engine.runtime.battle.entity_deploy_delay[row, slot].item()
                == entity.deploy_delay_remaining
            )
            assert engine.combat.attack_cooldown[row, slot].item() == (
                entity.attack_cooldown
            )
        opcodes = engine.runtime.events.opcode[
            row, : engine.runtime.events.count[row]
        ].tolist()
        assert opcodes == [
            RuntimeEventOpcode.SPAWN,
            RuntimeEventOpcode.DAMAGE,
            RuntimeEventOpcode.DEATH,
        ]


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_exact_cross_river_both_bridge_lanes_and_owners_match_oracle(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    cases = [
        _cross_river_battle(source_player=player, bridge_x=bridge_x)
        for player in (0, 1)
        for bridge_x in (3.5, 14.5)
    ]
    oracle = [battle.clone() for battle in cases]
    for battle in oracle:
        order = [0, 1]
        battle.rng.shuffle(order)
        battle.step_logic_ticks(1)
    engine = TensorResidentEngine.from_battles(
        [battle.clone() for battle in cases],
        device=device,
        max_entities=8,
        max_objects=8,
    )

    result = engine.step()

    assert result.committed.all()
    assert engine.path_cache.valid.any()
    for row, expected in enumerate(oracle):
        runtime_ids = engine.runtime.battle.entity_id[row].tolist()
        source_slot = runtime_ids.index(1)
        expected_source = expected.entities[1]
        assert engine.runtime.battle.entity_x_units[row, source_slot].item() == round(
            expected_source.position.x * 1_000
        )
        assert engine.runtime.battle.entity_y_units[row, source_slot].item() == round(
            expected_source.position.y * 1_000
        )
        expected_route = tuple(
            getattr(expected_source, "_native_ground_route_cells", [])
        )
        route_count = int(engine.movement.route_count[row, source_slot].item())
        actual_route = tuple(
            tuple(value)
            for value in engine.movement.route_cells[
                row, source_slot, :route_count
            ].tolist()
        )
        assert actual_route == expected_route
        assert engine.movement.ground_path_backwards[row, source_slot].item() is (
            expected_source._ground_path_backwards
        )
        assert engine.movement.lane_id[row, source_slot].item() == (
            expected_source._native_lane_id
        )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_river_active_and_landing_consume_frames_preserve_combat_clock(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    sources = [_active_river_battle(owner) for owner in (0, 1)]
    oracle = [battle.clone() for battle in sources]
    engine = TensorResidentEngine.from_battles(
        [battle.clone() for battle in sources],
        device=device,
        max_entities=8,
        max_objects=8,
        event_capacity=64,
    )
    actions = torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64, device=device)

    for _ in range(2):
        for battle in oracle:
            order = [0, 1]
            battle.rng.shuffle(order)
            battle.step_logic_ticks(1)
        result = engine.step(actions)
        assert result.committed.tolist() == [True, True]
        for row, expected in enumerate(oracle):
            source = expected.entities[1]
            slot = engine.movement.entity_id[row].tolist().index(1)
            assert engine.combat.attack_cooldown[row, slot].item() == (
                source.attack_cooldown
            )
            assert engine.movement.position_units[row, slot].tolist() == [
                round(source.position.x * 1_000),
                round(source.position.y * 1_000),
            ]
            assert engine.movement.river_jump_active[row, slot].item() is bool(
                getattr(source, "_river_jump_active", False)
            )
            assert engine.movement.special_move_consumed_tick[row, slot].item() is bool(
                getattr(source, "_special_move_consumed_tick", False)
            )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_combat_block_preserves_observed_facing_but_suppresses_movement_intent(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = _segment_battle()
    engine = TensorResidentEngine.from_battles(
        [battle], device=device, max_entities=8, max_objects=8
    )
    source_slot = engine.combat.entity_id[0].tolist().index(2)
    target_slot = engine.combat.entity_id[0].tolist().index(1)
    engine.dispatcher.dash.phase[0, source_slot] = 1
    cooldown_before = engine.combat.attack_cooldown[0, source_slot].clone()

    engine._combat_phase(torch.ones(1, dtype=torch.bool, device=device))

    assert engine.facing_x_units[0, source_slot].item() == (
        engine.combat.x_units[0, target_slot].item()
        - engine.combat.x_units[0, source_slot].item()
    )
    assert engine.facing_y_units[0, source_slot].item() == (
        engine.combat.y_units[0, target_slot].item()
        - engine.combat.y_units[0, source_slot].item()
    )
    assert engine.movement.target_slot[0, source_slot].item() == -1
    assert torch.equal(engine.combat.attack_cooldown[0, source_slot], cooldown_before)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_character_deploy_zero_crossing_snaps_exactly_before_completion(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = BattleState(fast_path=False, rng=random.Random(745_100))
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Xbow")
    assert stats is not None
    building = battle._spawn_entity(Building, Position(9.0, 10.0), 0, stats)
    building.deploy_delay_remaining = 0.05 + 5e-17
    building.placement_pending = True
    building._spawn_hook_pending = True
    building._spawn_hook_fired = False
    expected = battle.clone()
    expected_building = expected.entities[1]
    assert isinstance(expected_building, Building)
    expected_building.tick_character_object_phase(0.05)
    engine = TensorResidentEngine.from_battles(
        [battle], device=device, max_entities=8, max_objects=8
    )

    completed = engine._character_object_phase(
        torch.ones(1, dtype=torch.bool, device=device)
    )

    assert completed[0, 0].item()
    assert engine.runtime.battle.entity_deploy_delay[0, 0].item() == 0.0
    assert engine.runtime.battle.entity_deploy_delay[0, 0].item() == (
        expected_building.deploy_delay_remaining
    )
    assert not engine.runtime.battle.entity_placement_pending[0, 0].item()
    assert not engine.runtime.battle.entity_spawn_hook_pending[0, 0].item()
    assert engine.runtime.battle.entity_spawn_hook_fired[0, 0].item()


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_raw_target_id_survives_cleanup_then_rejects_reused_physical_slot(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = _segment_battle()
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle], device=device, max_entities=8, max_objects=8
    )
    no_op = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=device)

    for _ in range(3):
        order = [0, 1]
        oracle.rng.shuffle(order)
        oracle.step_logic_ticks(1)
        first = engine.step(no_op)
        assert first.committed.tolist() == [True]
        if 1 not in oracle.entities:
            break
    assert 1 not in oracle.entities
    source_slot = engine.runtime.battle.entity_id[0].tolist().index(2)
    assert oracle.entities[2].target_id == 1
    assert engine.combat_target_entity_id[0, source_slot].item() == 1

    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = (DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION)
    order = [0, 1]
    oracle.rng.shuffle(order)
    for player in order:
        assert action_space.apply_action(oracle, player, actions[player])
    oracle.step_logic_ticks(1)
    second = engine.step(torch.tensor([actions], dtype=torch.int64, device=device))

    assert second.committed.tolist() == [True]
    assert engine.runtime.battle.entity_id[0, 0].item() == 3
    source_slot = engine.runtime.battle.entity_id[0].tolist().index(2)
    assert oracle.entities[2].target_id is None
    assert engine.combat_target_entity_id[0, source_slot].item() == -1
    assert engine.combat_target_entity_id[0, source_slot].item() != 3


def test_death_then_lowest_slot_reuse_routes_new_high_id_exactly() -> None:
    battle = _segment_battle()
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(
        Position(6.5, 6.0),
        1,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    distant_target = battle.entities[3]
    distant_target.stun_timer = 100.0
    distant_target.attack_cooldown = 10.0
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles([battle], max_entities=8, max_objects=8)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    trace = [
        (NO_OP_ACTION, NO_OP_ACTION),
        (NO_OP_ACTION, NO_OP_ACTION),
        (DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION),
        *[(NO_OP_ACTION, NO_OP_ACTION) for _ in range(22)],
    ]

    saw_reused_slot_movement = False
    for actions in trace:
        order = [0, 1]
        oracle.rng.shuffle(order)
        for player in order:
            assert action_space.apply_action(oracle, player, actions[player])
        oracle.step_logic_ticks(1)
        result = engine.step(torch.tensor([actions]))
        assert result.committed.tolist() == [True]
        if engine.runtime.battle.entity_id[0, 0].item() == 4:
            saw_reused_slot_movement |= bool(
                result.movement.ordinary_moved[0, 0].item()
            )

    assert 1 not in oracle.entities
    assert engine.runtime.battle.entity_id[0, 0].item() == 4
    assert saw_reused_slot_movement
    runtime_ids = engine.runtime.battle.entity_id[0].tolist()
    assert {entity_id for entity_id in runtime_ids if entity_id} == set(oracle.entities)
    for entity_id, entity in oracle.entities.items():
        slot = runtime_ids.index(entity_id)
        assert engine.runtime.battle.entity_x_units[0, slot].item() == round(
            entity.position.x * 1_000
        )
        assert engine.runtime.battle.entity_y_units[0, slot].item() == round(
            entity.position.y * 1_000
        )
    assert not torch.all(
        engine.runtime.battle.entity_id[0, :-1]
        <= engine.runtime.battle.entity_id[0, 1:]
    )


def test_speculative_clone_shares_immutable_path_cache() -> None:
    engine = TensorResidentEngine.from_battles([_segment_battle()], max_entities=8)
    cloned = engine.clone()

    assert cloned.path_cache is engine.path_cache


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


def test_two_direct_attackers_emit_separate_source_attributed_events() -> None:
    battle = _segment_battle()
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(
        Position(14.5, 12.9),
        0,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    second = battle.entities[3]
    second.target_id = 1
    second._movement_target_id = 1  # type: ignore[attr-defined]
    second.attack_cooldown = 0.0
    battle.entities[2].position = Position(14.5, 12.9)
    battle.entities[1].hitpoints = 1_000.0
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=16
    )
    result = engine.step()

    assert result.committed.tolist() == [True]
    count = int(engine.runtime.events.count[0].item())
    damage = engine.runtime.events.opcode[0, :count] == RuntimeEventOpcode.DAMAGE
    assert engine.runtime.events.source_id[0, :count][damage].tolist() == [2, 3]
    assert engine.runtime.events.target_id[0, :count][damage].tolist() == [1, 1]
    assert engine.runtime.events.x_units[0, :count][damage].tolist() == [14_500, 14_500]
    assert engine.runtime.events.y_units[0, :count][damage].tolist() == [14_500, 14_500]
    knight = engine.runtime.battle.card_to_id["Knight"]
    assert engine.runtime.events.payload[0, :count][damage].tolist() == [
        knight,
        knight,
    ]


def test_direct_area_events_keep_primary_before_lower_id_secondary() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    stats.area_damage_radius = 1_000
    for position in (Position(15.0, 14.5), Position(14.5, 14.5)):
        battle._spawn_unit_at_position(
            position,
            1,
            stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        target = battle.entities[battle.next_entity_id - 1]
        target.stun_timer = 100.0
        target.attack_cooldown = 10.0
        target.hitpoints = 1_000.0
    battle._spawn_unit_at_position(
        Position(14.5, 12.9),
        0,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    attacker = battle.entities[3]
    attacker.target_id = 2
    attacker._movement_target_id = 2  # type: ignore[attr-defined]
    attacker.attack_cooldown = 0.0
    _set_hand(battle, "Knight")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=8, event_capacity=16
    )
    engine.area_radius_units.fill_(1_000)

    result = engine.step()

    assert result.committed.tolist() == [True]
    count = int(engine.runtime.events.count[0].item())
    damage = engine.runtime.events.opcode[0, :count] == RuntimeEventOpcode.DAMAGE
    assert engine.runtime.events.source_id[0, :count][damage].tolist() == [3, 3]
    assert engine.runtime.events.target_id[0, :count][damage].tolist() == [2, 1]
