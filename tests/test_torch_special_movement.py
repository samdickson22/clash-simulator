from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.factory.mechanic_detector import detect_mechanics_from_data
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.special_movement import (
    DashPhase,
    DashState,
    DashStepResult,
    HookPhase,
    HookState,
    HookStepResult,
    LeapPhase,
    LeapState,
    LeapStepResult,
    SpecialEventOpcode,
    SpecialMovementOpcode,
    TensorSpecialMovementCatalog,
    dispatch_attack_commits,
    dispatch_spawn_pushback,
    stable_special_events,
    step_bandit_dash,
    step_fisherman_hook,
    step_mega_knight_leap,
    step_underground_deployment,
    validate_special_movement_device,
)

DEVICES = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])


def _battle() -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _spawn(
    battle: BattleState,
    name: str,
    player_id: int,
    position: Position,
    *,
    deployed: bool = True,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player_id, stats)
    assert isinstance(entity, Troop)
    if deployed:
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    return entity


def _mechanic(entity: Entity, name: str) -> Any:
    return next(item for item in entity.mechanics if type(item).__name__ == name)


def _operation_slot(
    catalog: TensorSpecialMovementCatalog,
    card_name: str,
    operation: SpecialMovementOpcode,
) -> tuple[int, int]:
    card_id = catalog.name_to_id[card_name]
    slots = torch.nonzero(
        catalog.opcode[card_id] == int(operation), as_tuple=False
    ).flatten()
    assert slots.numel() == 1
    return card_id, int(slots.item())


def _one(value: object, *, dtype: torch.dtype, device: str) -> torch.Tensor:
    return torch.tensor([[value]], dtype=dtype, device=device)


def _one_position(position: Position, device: str) -> torch.Tensor:
    return torch.tensor(
        [[[tiles_to_logic_units(position.x), tiles_to_logic_units(position.y)]]],
        dtype=torch.int64,
        device=device,
    )


def test_catalog_compiles_all_special_classes_and_attached_serialized_parameters() -> (
    None
):
    battle = BattleState()
    names = (
        "Firecracker",
        "Bandit",
        "BattleRam",
        "Fisherman",
        "MegaKnight",
        "Miner",
        "Wallbreakers",
    )
    catalog = TensorSpecialMovementCatalog.compile(battle.card_loader, names)
    actual = {
        SpecialMovementOpcode(int(value))
        for value in catalog.opcode.flatten().tolist()
        if int(value)
    }
    assert actual == set(SpecialMovementOpcode) - {SpecialMovementOpcode.PADDING}

    fire_id, fire_slot = _operation_slot(
        catalog, "Firecracker", SpecialMovementOpcode.ATTACK_RECOIL
    )
    assert catalog.distance_units[fire_id, fire_slot].item() == 1_000
    bandit_id, bandit_slot = _operation_slot(
        catalog, "Bandit", SpecialMovementOpcode.BANDIT_DASH
    )
    assert catalog.min_range_units[bandit_id, bandit_slot].item() == 3_500
    assert catalog.max_range_units[bandit_id, bandit_slot].item() == 6_000
    assert catalog.windup_ms[bandit_id, bandit_slot].item() == 800
    assert catalog.speed_units[bandit_id, bandit_slot].item() == 500
    hook_id, hook_slot = _operation_slot(
        catalog, "Fisherman", SpecialMovementOpcode.FISHERMAN_HOOK
    )
    assert catalog.speed_units[hook_id, hook_slot].item() == 800
    assert catalog.secondary_speed_units[hook_id, hook_slot].item() == 850
    assert catalog.tertiary_speed_units[hook_id, hook_slot].item() == 450
    assert catalog.margin_units[hook_id, hook_slot].item() == 200
    assert catalog.as_attractor[hook_id, hook_slot].item()
    mega_id, mega_slot = _operation_slot(
        catalog, "MegaKnight", SpecialMovementOpcode.MEGA_KNIGHT_SLAM
    )
    assert catalog.duration_ms[mega_id, mega_slot].item() == 800
    assert catalog.secondary_duration_ms[mega_id, mega_slot].item() == 300
    assert catalog.radius_units[mega_id, mega_slot].item() == 2_200
    miner_id, miner_slot = _operation_slot(
        catalog, "Miner", SpecialMovementOpcode.UNDERGROUND_DEPLOYMENT
    )
    assert catalog.speed_units[miner_id, miner_slot].item() == 650


@pytest.mark.parametrize("device", DEVICES)
def test_recoil_knockback_install_matches_python_mechanic(device: str) -> None:
    battle = _battle()
    source = _spawn(battle, "Firecracker", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(12.0, 14.0))
    oracle = deepcopy(battle)
    oracle_source = oracle.entities[source.id]
    oracle_target = oracle.entities[target.id]
    getattr(_mechanic(oracle_source, "AttackRecoil"), "on_attack_committed")(
        oracle_source, oracle_target
    )
    catalog = TensorSpecialMovementCatalog.compile(
        battle.card_loader, ["Firecracker"], device=device
    )
    card_id, slot = _operation_slot(
        catalog, "Firecracker", SpecialMovementOpcode.ATTACK_RECOIL
    )

    result = dispatch_attack_commits(
        _one(
            int(SpecialMovementOpcode.ATTACK_RECOIL), dtype=torch.int64, device=device
        ),
        source_id=_one(source.id, dtype=torch.int64, device=device),
        target_id=_one(target.id, dtype=torch.int64, device=device),
        source_position_units=_one_position(source.position, device),
        target_position_units=_one_position(target.position, device),
        source_player=_one(source.player_id, dtype=torch.int64, device=device),
        source_hitpoints=_one(source.hitpoints, dtype=torch.float64, device=device),
        source_alive=_one(True, dtype=torch.bool, device=device),
        target_kind=_one(target.entity_kind, dtype=torch.int64, device=device),
        attack_committed=_one(True, dtype=torch.bool, device=device),
        attack_hit=_one(False, dtype=torch.bool, device=device),
        triggered=_one(False, dtype=torch.bool, device=device),
        recoil_distance_units=catalog.distance_units[card_id, slot].reshape(1, 1),
    )

    oracle_knockback = getattr(oracle_source, "_knockback_target")
    assert oracle_knockback is not None
    assert result.knockback.target_units.cpu().tolist() == [
        [
            [
                tiles_to_logic_units(oracle_knockback.x),
                tiles_to_logic_units(oracle_knockback.y),
            ]
        ]
    ]
    assert result.knockback.velocity_work.item() == getattr(
        oracle_source, "_knockback_velocity_work"
    )
    assert result.forced_movement.item() == oracle_source.forced_movement_active
    assert result.events.opcode[0, 0].item() == int(
        SpecialEventOpcode.KNOCKBACK_STARTED
    )


@pytest.mark.parametrize(
    ("card_name", "operation", "attack_committed", "attack_hit", "building"),
    [
        (
            "BattleRam",
            SpecialMovementOpcode.BATTLE_RAM_CHARGE,
            False,
            True,
            True,
        ),
        (
            "Wallbreakers",
            SpecialMovementOpcode.WALL_BREAKERS_DEMOLITION,
            True,
            False,
            False,
        ),
    ],
)
def test_kamikaze_lifecycle_opcodes_match_python_once(
    card_name: str,
    operation: SpecialMovementOpcode,
    attack_committed: bool,
    attack_hit: bool,
    building: bool,
) -> None:
    battle = _battle()
    source = _spawn(battle, card_name, 0, Position(9.0, 10.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    target = (
        battle._spawn_entity(
            Building,
            Position(9.0, 11.0),
            1,
            cannon_stats,
        )
        if building
        else _spawn(battle, "Knight", 1, Position(9.0, 11.0))
    )
    oracle = deepcopy(battle)
    oracle_source = oracle.entities[source.id]
    oracle_target = oracle.entities[target.id]
    mechanic = _mechanic(
        oracle_source,
        "BattleRamCharge" if building else "WallBreakersDemolition",
    )
    method = "on_attack_hit" if attack_hit else "on_attack_committed"
    getattr(mechanic, method)(oracle_source, oracle_target)

    result = dispatch_attack_commits(
        torch.tensor([[int(operation)]]),
        source_id=torch.tensor([[source.id]]),
        target_id=torch.tensor([[target.id]]),
        source_position_units=_one_position(source.position, "cpu"),
        target_position_units=_one_position(target.position, "cpu"),
        source_player=torch.tensor([[source.player_id]]),
        source_hitpoints=torch.tensor([[source.hitpoints]], dtype=torch.float64),
        source_alive=torch.tensor([[True]]),
        target_kind=torch.tensor([[target.entity_kind]]),
        attack_committed=torch.tensor([[attack_committed]]),
        attack_hit=torch.tensor([[attack_hit]]),
        triggered=torch.tensor([[False]]),
        recoil_distance_units=torch.zeros((1, 1), dtype=torch.int64),
    )
    assert result.alive.item() == oracle_source.is_alive
    assert result.hitpoints.item() == oracle_source.hitpoints
    assert result.triggered.item()
    assert result.events.opcode[0, 0].item() == int(SpecialEventOpcode.SELF_DEATH)


def _dash_state(entity: Troop, device: str) -> DashState:
    phase = (
        DashPhase.TRAVEL
        if getattr(entity, "_bandit_dashing", False)
        else DashPhase.CHARGING
        if getattr(entity, "_bandit_charging", False)
        else DashPhase.IDLE
    )
    origin = getattr(entity, "_bandit_dash_origin", None) or (
        entity.position.x,
        entity.position.y,
    )
    destination = getattr(entity, "_bandit_dash_target", None) or origin
    return DashState(
        phase=torch.tensor([[int(phase)]], device=device),
        position_units=_one_position(entity.position, device),
        origin_units=torch.tensor(
            [[[tiles_to_logic_units(origin[0]), tiles_to_logic_units(origin[1])]]],
            device=device,
        ),
        destination_units=torch.tensor(
            [
                [
                    [
                        tiles_to_logic_units(destination[0]),
                        tiles_to_logic_units(destination[1]),
                    ]
                ]
            ],
            device=device,
        ),
        progress_ms=torch.tensor(
            [[float(getattr(entity, "_bandit_dash_timer", 0.0))]],
            dtype=torch.float64,
            device=device,
        ),
        travel_duration_ms=torch.tensor(
            [[float(getattr(entity, "_bandit_dash_travel_duration_ms", 0.0))]],
            dtype=torch.float64,
            device=device,
        ),
        target_id=torch.tensor(
            [[int(getattr(entity, "_bandit_dash_target_id", -1) or -1)]],
            device=device,
        ),
        special_active=torch.tensor(
            [[bool(getattr(entity, "_special_move_active", False))]],
            device=device,
        ),
        special_consumed=torch.tensor([[False]], device=device),
        invulnerable_until_ms=torch.tensor(
            [[float(getattr(entity, "_bandit_invulnerable_until", 0.0))]],
            dtype=torch.float64,
            device=device,
        ),
    )


def _step_bandit_tensor(
    state: DashState,
    bandit: Troop,
    target: Troop,
    mechanic: object,
    dt_ms: int,
) -> DashStepResult:
    device = state.phase.device
    return step_bandit_dash(
        state,
        target_id=torch.tensor([[target.id]], device=device),
        target_position_units=_one_position(target.position, str(device)),
        target_radius_units=torch.tensor(
            [[tiles_to_logic_units(target.get_collision_radius())]], device=device
        ),
        target_in_range=torch.tensor(
            [[getattr(mechanic, "_target_edge_distance")(bandit, target) is not None]],
            device=device,
        ),
        target_valid=torch.tensor([[target.is_alive]], device=device),
        stunned=torch.tensor([[bandit.is_stunned()]], device=device),
        attack_rate=torch.tensor(
            [[bandit.get_attack_rate_multiplier()]], dtype=torch.float64, device=device
        ),
        attack_range_units=torch.tensor(
            [[tiles_to_logic_units(bandit.range)]], device=device
        ),
        windup_ms=torch.tensor(
            [[float(getattr(mechanic, "dash_duration_ms"))]],
            dtype=torch.float64,
            device=device,
        ),
        jump_speed_units=torch.tensor(
            [[round(getattr(mechanic, "jump_speed"))]], device=device
        ),
        dash_damage=torch.tensor(
            [[float(getattr(mechanic, "dash_damage"))]],
            dtype=torch.float64,
            device=device,
        ),
        post_immunity_ms=torch.tensor(
            [[int(getattr(mechanic, "post_dash_immunity_ms"))]], device=device
        ),
        battle_time_ms=torch.tensor(
            [[round(getattr(bandit, "battle_state").time * 1000)]], device=device
        ),
        dt_ms=dt_ms,
    )


@pytest.mark.parametrize("device", DEVICES)
def test_bandit_charge_launch_travel_and_landing_match_python(device: str) -> None:
    battle = _battle()
    bandit = _spawn(battle, "Bandit", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(12.0, 14.0))
    bandit.target_id = target.id
    mechanic = _mechanic(bandit, "BanditDash")
    state = _dash_state(bandit, device)

    getattr(mechanic, "on_tick")(bandit, 50)
    tensor = _step_bandit_tensor(state, bandit, target, mechanic, 50)
    state = tensor.state
    assert state.phase.item() == int(DashPhase.CHARGING)
    getattr(mechanic, "on_tick")(bandit, 800)
    tensor = _step_bandit_tensor(state, bandit, target, mechanic, 800)
    state = tensor.state
    assert state.phase.item() == int(DashPhase.TRAVEL)
    assert state.destination_units[0, 0].cpu().tolist() == [
        tiles_to_logic_units(value) for value in getattr(bandit, "_bandit_dash_target")
    ]
    assert state.travel_duration_ms.item() == getattr(
        bandit, "_bandit_dash_travel_duration_ms"
    )

    for _ in range(30):
        getattr(mechanic, "on_movement_tick")(bandit, 50)
        tensor = _step_bandit_tensor(state, bandit, target, mechanic, 50)
        state = tensor.state
        assert state.position_units[0, 0].cpu().tolist() == [
            tiles_to_logic_units(bandit.position.x),
            tiles_to_logic_units(bandit.position.y),
        ]
        if not getattr(bandit, "_bandit_dashing"):
            assert tensor.finished.item()
            break
    else:
        pytest.fail("Bandit dash did not finish")


def _leap_state(entity: Troop, device: str) -> LeapState:
    raw_phase = getattr(entity, "_mk_leap_phase", None)
    phase = {
        None: LeapPhase.IDLE,
        "charging": LeapPhase.CHARGING,
        "airborne": LeapPhase.AIRBORNE,
        "landing": LeapPhase.LANDING,
    }[raw_phase]
    origin = getattr(entity, "_mk_leap_origin", None) or (
        entity.position.x,
        entity.position.y,
    )
    destination = getattr(entity, "_mk_leap_target", None) or origin
    return LeapState(
        phase=torch.tensor([[int(phase)]], device=device),
        position_units=_one_position(entity.position, device),
        origin_units=torch.tensor(
            [[[tiles_to_logic_units(origin[0]), tiles_to_logic_units(origin[1])]]],
            device=device,
        ),
        destination_units=torch.tensor(
            [
                [
                    [
                        tiles_to_logic_units(destination[0]),
                        tiles_to_logic_units(destination[1]),
                    ]
                ]
            ],
            device=device,
        ),
        progress_ms=torch.tensor(
            [[float(getattr(entity, "_mk_leap_progress", 0.0))]],
            dtype=torch.float64,
            device=device,
        ),
        travel_duration_ms=torch.tensor(
            [[float(getattr(entity, "_mk_leap_travel_duration_ms", 0.0))]],
            dtype=torch.float64,
            device=device,
        ),
        target_id=torch.tensor(
            [[int(getattr(entity, "_mk_leap_target_id", -1) or -1)]], device=device
        ),
        special_active=torch.tensor(
            [[bool(getattr(entity, "_special_move_active", False))]], device=device
        ),
        special_consumed=torch.tensor([[False]], device=device),
    )


def _step_leap_tensor(
    state: LeapState,
    mega: Troop,
    target: Troop,
    mechanic: object,
    dt_ms: int,
) -> LeapStepResult:
    device = state.phase.device
    return step_mega_knight_leap(
        state,
        target_id=torch.tensor([[target.id]], device=device),
        target_position_units=_one_position(target.position, str(device)),
        target_radius_units=torch.tensor(
            [[tiles_to_logic_units(target.get_collision_radius())]], device=device
        ),
        target_in_range=torch.tensor(
            [[getattr(mechanic, "_target_edge_distance")(mega, target) is not None]],
            device=device,
        ),
        target_valid=torch.tensor([[target.is_alive]], device=device),
        stunned=torch.tensor([[mega.is_stunned()]], device=device),
        attack_rate=torch.tensor(
            [[mega.get_attack_rate_multiplier()]], dtype=torch.float64, device=device
        ),
        attack_range_units=torch.tensor(
            [[tiles_to_logic_units(mega.range)]], device=device
        ),
        windup_ms=torch.tensor(
            [[float(getattr(mechanic, "leap_duration_ms"))]],
            dtype=torch.float64,
            device=device,
        ),
        airborne_duration_ms=torch.tensor(
            [[float(getattr(mechanic, "airborne_duration_ms"))]],
            dtype=torch.float64,
            device=device,
        ),
        landing_duration_ms=torch.tensor(
            [[float(getattr(mechanic, "landing_duration_ms"))]],
            dtype=torch.float64,
            device=device,
        ),
        dt_ms=dt_ms,
    )


@pytest.mark.parametrize("device", DEVICES)
def test_mega_knight_charge_fixed_airborne_and_landing_match_python(
    device: str,
) -> None:
    battle = _battle()
    mega = _spawn(battle, "MegaKnight", 0, Position(3.5, 10.0))
    target = _spawn(battle, "Knight", 1, Position(3.5, 15.0))
    mega.target_id = target.id
    mechanic = _mechanic(mega, "MegaKnightSlam")
    state = _leap_state(mega, device)

    getattr(mechanic, "on_tick")(mega, 50)
    state = _step_leap_tensor(state, mega, target, mechanic, 50).state
    getattr(mechanic, "on_tick")(mega, 900)
    state = _step_leap_tensor(state, mega, target, mechanic, 900).state
    assert state.phase.item() == int(LeapPhase.AIRBORNE)
    assert state.destination_units[0, 0].cpu().tolist() == [
        tiles_to_logic_units(value) for value in getattr(mega, "_mk_leap_target")
    ]

    saw_slam = False
    for _ in range(24):
        getattr(mechanic, "on_movement_tick")(mega, 50)
        tensor = _step_leap_tensor(state, mega, target, mechanic, 50)
        state = tensor.state
        assert state.position_units[0, 0].cpu().tolist() == [
            tiles_to_logic_units(mega.position.x),
            tiles_to_logic_units(mega.position.y),
        ]
        saw_slam |= bool(tensor.slam.item())
        expected_phase = {
            None: LeapPhase.IDLE,
            "charging": LeapPhase.CHARGING,
            "airborne": LeapPhase.AIRBORNE,
            "landing": LeapPhase.LANDING,
        }[getattr(mega, "_mk_leap_phase")]
        assert state.phase.item() == int(expected_phase)
        if expected_phase == LeapPhase.IDLE:
            break
    assert saw_slam
    assert state.phase.item() == int(LeapPhase.IDLE)


def _hook_state(
    source: Troop,
    target: Troop,
    mechanic: object,
    device: str,
) -> HookState:
    phase = HookPhase(
        {"idle": 0, "windup": 1, "flight": 2, "drag": 3}[getattr(mechanic, "state")]
    )
    hook = getattr(mechanic, "hook_position")
    return HookState(
        phase=torch.tensor([[int(phase)]], device=device),
        source_position_units=_one_position(source.position, device),
        target_position_units=_one_position(target.position, device),
        hook_position_units=(
            torch.zeros((1, 1, 2), dtype=torch.int64, device=device)
            if hook is None
            else _one_position(hook, device)
        ),
        target_id=torch.tensor(
            [[int(getattr(mechanic, "hook_target_id") or -1)]], device=device
        ),
        windup_remaining_ms=torch.tensor(
            [[float(getattr(mechanic, "windup_remaining_ms"))]],
            dtype=torch.float64,
            device=device,
        ),
        target_forced=torch.tensor([[target.forced_movement_active]], device=device),
        special_active=torch.tensor(
            [[bool(getattr(source, "_special_move_active", False))]], device=device
        ),
        special_consumed=torch.tensor([[False]], device=device),
    )


def _step_hook_tensor(
    state: HookState,
    source: Troop,
    target: Troop,
    mechanic: object,
    dt_ms: int,
) -> HookStepResult:
    device = state.phase.device
    launch, _, _ = source._projectile_launch_geometry(target)
    return step_fisherman_hook(
        state,
        acquired_target_id=torch.tensor([[target.id]], device=device),
        launch_position_units=_one_position(launch, str(device)),
        target_valid=torch.tensor([[target.is_alive]], device=device),
        target_in_range=torch.tensor(
            [[getattr(mechanic, "_is_hook_target_in_range")(source, target)]],
            device=device,
        ),
        target_plane_valid=torch.tensor(
            [[source.can_affect_target_plane(target)]], device=device
        ),
        target_can_forced_move=torch.tensor(
            [[target.can_receive_forced_movement("Fisherman", "hook")]],
            device=device,
        ),
        target_is_building=torch.tensor([[False]], device=device),
        move_allowed=torch.tensor([[True]], device=device),
        attack_rate=torch.tensor(
            [[source.get_attack_rate_multiplier()]], dtype=torch.float64, device=device
        ),
        windup_ms=torch.tensor(
            [[float(getattr(mechanic, "hook_windup_ms"))]],
            dtype=torch.float64,
            device=device,
        ),
        projectile_speed_units=torch.tensor([[800]], device=device),
        drag_back_speed_units=torch.tensor([[850]], device=device),
        drag_self_speed_units=torch.tensor([[450]], device=device),
        drag_margin_units=torch.tensor(
            [[tiles_to_logic_units(getattr(mechanic, "drag_margin"))]], device=device
        ),
        source_radius_units=torch.tensor(
            [[tiles_to_logic_units(source.get_collision_radius())]], device=device
        ),
        target_radius_units=torch.tensor(
            [[tiles_to_logic_units(target.get_collision_radius())]], device=device
        ),
        stunned=torch.tensor([[source.is_stunned()]], device=device),
        dt_ms=dt_ms,
    )


@pytest.mark.parametrize("device", DEVICES)
def test_fisherman_windup_flight_and_victim_drag_match_python(device: str) -> None:
    battle = _battle()
    fisherman = _spawn(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 16.0))
    mechanic = _mechanic(fisherman, "FishermanHook")
    state = _hook_state(fisherman, target, mechanic, device)

    getattr(mechanic, "on_tick")(fisherman, 50)
    state = _step_hook_tensor(state, fisherman, target, mechanic, 50).state
    getattr(mechanic, "on_tick")(fisherman, 1300)
    state = _step_hook_tensor(state, fisherman, target, mechanic, 1300).state
    assert state.phase.item() == int(HookPhase.FLIGHT)

    for _ in range(40):
        getattr(mechanic, "on_object_tick")(fisherman, 50)
        tensor = _step_hook_tensor(state, fisherman, target, mechanic, 50)
        state = tensor.state
        assert state.source_position_units[0, 0].cpu().tolist() == [
            tiles_to_logic_units(fisherman.position.x),
            tiles_to_logic_units(fisherman.position.y),
        ]
        assert state.target_position_units[0, 0].cpu().tolist() == [
            tiles_to_logic_units(target.position.x),
            tiles_to_logic_units(target.position.y),
        ]
        expected_phase = HookPhase(
            {"idle": 0, "windup": 1, "flight": 2, "drag": 3}[getattr(mechanic, "state")]
        )
        assert state.phase.item() == int(expected_phase)
        if expected_phase == HookPhase.IDLE:
            break
    assert state.phase.item() == int(HookPhase.IDLE)


@pytest.mark.parametrize("device", DEVICES)
def test_underground_transport_frames_match_miner_mechanic(device: str) -> None:
    battle = _battle()
    miner = _spawn(battle, "Miner", 0, Position(12.0, 20.0), deployed=False)
    mechanic = _mechanic(miner, "UndergroundDeployment")
    position = _one_position(miner.position, device)
    destination = _one_position(getattr(miner, "_underground_destination"), device)
    active = torch.tensor(
        [[bool(getattr(miner, "_underground_deployment"))]], device=device
    )
    total = torch.tensor(
        [[miner.placement_delay_total]], dtype=torch.float64, device=device
    )
    travel = torch.tensor(
        [[float(getattr(miner, "_underground_travel_duration"))]],
        dtype=torch.float64,
        device=device,
    )
    speed = torch.tensor(
        [[round(getattr(mechanic, "travel_speed_logic_units_per_tick"))]],
        device=device,
    )

    for _ in range(80):
        remaining = torch.tensor(
            [[miner.deploy_delay_remaining]], dtype=torch.float64, device=device
        )
        getattr(mechanic, "on_deploy_tick")(miner, 50)
        result = step_underground_deployment(
            position,
            destination,
            underground_active=active,
            total_delay_seconds=total,
            remaining_delay_seconds=remaining,
            travel_duration_seconds=travel,
            speed_units=speed,
        )
        position = result.position_units
        assert position[0, 0].cpu().tolist() == [
            tiles_to_logic_units(miner.position.x),
            tiles_to_logic_units(miner.position.y),
        ]
        miner.deploy_delay_remaining = max(0.0, miner.deploy_delay_remaining - 0.05)
        if result.reached_destination.item():
            break
    assert result.reached_destination.item()


@pytest.mark.parametrize("device", DEVICES)
def test_spawn_pushback_pair_kernel_matches_synthetic_scalar_and_stable_events(
    device: str,
) -> None:
    mechanic = next(
        item
        for item in detect_mechanics_from_data(
            {
                "name": "SyntheticSpawner",
                "summonCharacterData": {
                    "spawnPushback": 750,
                    "spawnPushbackRadius": 1000,
                    "attacksGround": True,
                    "attacksAir": False,
                },
            }
        )
        if type(item).__name__ == "SpawnPushback"
    )
    battle = _battle()
    source = _spawn(battle, "Knight", 0, Position(9.0, 12.0))
    targets = [
        _spawn(battle, "Knight", 1, Position(10.4, 12.0)),
        _spawn(battle, "Giant", 1, Position(7.3, 12.0)),
        _spawn(battle, "BabyDragon", 1, Position(9.0, 10.6)),
    ]
    oracle = deepcopy(battle)
    oracle_source = oracle.entities[source.id]
    getattr(mechanic, "on_spawn")(oracle_source)
    lanes = [2, 0, 1]
    lane_targets = [targets[index] for index in lanes]
    result = dispatch_spawn_pushback(
        torch.full((1, 3), int(SpecialMovementOpcode.SPAWN_PUSHBACK), device=device),
        source_id=torch.full((1, 3), source.id, device=device),
        target_id=torch.tensor([[item.id for item in lane_targets]], device=device),
        source_owner=torch.zeros((1, 3), dtype=torch.int64, device=device),
        target_owner=torch.ones((1, 3), dtype=torch.int64, device=device),
        source_position_units=torch.tensor(
            [
                [
                    [
                        tiles_to_logic_units(source.position.x),
                        tiles_to_logic_units(source.position.y),
                    ]
                    for _ in lane_targets
                ]
            ],
            device=device,
        ),
        target_position_units=torch.tensor(
            [
                [
                    [
                        tiles_to_logic_units(item.position.x),
                        tiles_to_logic_units(item.position.y),
                    ]
                    for item in lane_targets
                ]
            ],
            device=device,
        ),
        target_radius_units=torch.tensor(
            [
                [
                    tiles_to_logic_units(item.get_collision_radius())
                    for item in lane_targets
                ]
            ],
            device=device,
        ),
        target_player=torch.ones((1, 3), dtype=torch.int64, device=device),
        target_alive=torch.ones((1, 3), dtype=torch.bool, device=device),
        target_is_troop=torch.ones((1, 3), dtype=torch.bool, device=device),
        target_is_air=torch.tensor(
            [[item.is_air_unit for item in lane_targets]], device=device
        ),
        spawned=torch.ones((1, 3), dtype=torch.bool, device=device),
        distance_units=torch.full((1, 3), 750, device=device),
        radius_units=torch.full((1, 3), 1000, device=device),
        hits_air=torch.zeros((1, 3), dtype=torch.bool, device=device),
        hits_ground=torch.ones((1, 3), dtype=torch.bool, device=device),
    )
    for lane, target in enumerate(lane_targets):
        oracle_target = oracle.entities[target.id]
        expected = getattr(oracle_target, "_knockback_target")
        if expected is None:
            assert not result.affected[0, lane].item()
        else:
            assert result.knockback.target_units[0, lane].cpu().tolist() == [
                tiles_to_logic_units(expected.x),
                tiles_to_logic_units(expected.y),
            ]
    valid_ids = result.events.target_id[0][result.events.valid[0]].cpu().tolist()
    assert valid_ids == sorted(valid_ids)


def test_stable_event_packing_is_source_then_target_then_lane() -> None:
    valid = torch.tensor([[True, True, True, False]])
    source = torch.tensor([[9, 3, 3, 1]])
    target = torch.tensor([[2, 8, 4, 0]])
    events = stable_special_events(
        valid,
        torch.ones_like(source),
        source,
        target,
    )
    assert events.source_id[0, :3].tolist() == [3, 3, 9]
    assert events.target_id[0, :3].tolist() == [4, 8, 2]


def test_mps_fails_closed_before_float_state_allocation() -> None:
    with pytest.raises(RuntimeError, match="CPU/CUDA"):
        validate_special_movement_device("mps")
