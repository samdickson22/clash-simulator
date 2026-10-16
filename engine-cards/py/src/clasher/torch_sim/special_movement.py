"""Generalized tensor kernels for serialized special movement mechanics.

The factory emits mechanic classes; card identity is not a runtime operation.
This module compiles those classes to stable opcodes and fixed-point parameters,
then supplies CPU/CUDA kernels for their movement and lifecycle transitions.
No kernel branches on a card name.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.kinematics import tiles_to_logic_units

from .movement import integer_sqrt_tensor, normalized_vector_units, trunc_div_tensor


class SpecialMovementOpcode(IntEnum):
    PADDING = 0
    ATTACK_RECOIL = 1
    BANDIT_DASH = 2
    BATTLE_RAM_CHARGE = 3
    FISHERMAN_HOOK = 4
    MEGA_KNIGHT_SLAM = 5
    SPAWN_PUSHBACK = 6
    UNDERGROUND_DEPLOYMENT = 7
    WALL_BREAKERS_DEMOLITION = 8


SPECIAL_OPCODE_BY_CLASS = {
    "AttackRecoil": SpecialMovementOpcode.ATTACK_RECOIL,
    "BanditDash": SpecialMovementOpcode.BANDIT_DASH,
    "BattleRamCharge": SpecialMovementOpcode.BATTLE_RAM_CHARGE,
    "FishermanHook": SpecialMovementOpcode.FISHERMAN_HOOK,
    "MegaKnightSlam": SpecialMovementOpcode.MEGA_KNIGHT_SLAM,
    "SpawnPushback": SpecialMovementOpcode.SPAWN_PUSHBACK,
    "UndergroundDeployment": SpecialMovementOpcode.UNDERGROUND_DEPLOYMENT,
    "WallBreakersDemolition": SpecialMovementOpcode.WALL_BREAKERS_DEMOLITION,
}


class SpecialEventOpcode(IntEnum):
    PHASE_CHANGED = 1
    KNOCKBACK_STARTED = 2
    DAMAGE = 3
    SELF_DEATH = 4
    RIVER_OR_SPECIAL_FINISHED = 5


class DashPhase(IntEnum):
    IDLE = 0
    CHARGING = 1
    TRAVEL = 2


class LeapPhase(IntEnum):
    IDLE = 0
    CHARGING = 1
    AIRBORNE = 2
    LANDING = 3


class HookPhase(IntEnum):
    IDLE = 0
    WINDUP = 1
    FLIGHT = 2
    DRAG = 3


def validate_special_movement_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type not in {"cpu", "cuda"}:
        raise RuntimeError(
            "exact special movement requires CPU/CUDA float64 state; "
            f"device type {result.type!r} is unsupported"
        )
    return result


@dataclass(frozen=True)
class TensorSpecialMovementCatalog:
    device: torch.device
    names: tuple[str, ...]
    name_to_id: dict[str, int]
    opcode: torch.Tensor
    count: torch.Tensor
    distance_units: torch.Tensor
    radius_units: torch.Tensor
    min_range_units: torch.Tensor
    max_range_units: torch.Tensor
    windup_ms: torch.Tensor
    speed_units: torch.Tensor
    secondary_speed_units: torch.Tensor
    tertiary_speed_units: torch.Tensor
    duration_ms: torch.Tensor
    secondary_duration_ms: torch.Tensor
    post_immunity_ms: torch.Tensor
    margin_units: torch.Tensor
    damage: torch.Tensor
    secondary_damage: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    as_attractor: torch.Tensor

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        card_names: Iterable[str],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorSpecialMovementCatalog:
        torch_device = validate_special_movement_device(device)
        definitions = loader.load_card_definitions()
        resolved = tuple(
            sorted({resolve_card_name(name, definitions) for name in card_names})
        )
        missing = [name for name in resolved if name not in definitions]
        if missing:
            raise ValueError(f"missing card definitions: {missing}")
        names = ("", *resolved)
        name_to_id = {name: index for index, name in enumerate(names)}
        selected = {
            name: [
                mechanic
                for mechanic in definitions[name].mechanics
                if type(mechanic).__name__ in SPECIAL_OPCODE_BY_CLASS
            ]
            for name in resolved
        }
        max_operations = max(1, *(len(items) for items in selected.values()))
        shape = (len(names), max_operations)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=torch_device)

        opcode = zeros(torch.int16)
        count = torch.zeros(len(names), dtype=torch.int8, device=torch_device)
        distance = zeros(torch.int64)
        radius = zeros(torch.int64)
        minimum = zeros(torch.int64)
        maximum = zeros(torch.int64)
        windup = zeros(torch.float64)
        speed = zeros(torch.int64)
        secondary_speed = zeros(torch.int64)
        tertiary_speed = zeros(torch.int64)
        duration = zeros(torch.float64)
        secondary_duration = zeros(torch.float64)
        post_immunity = zeros(torch.int64)
        margin = zeros(torch.int64)
        damage = zeros(torch.float64)
        secondary_damage = zeros(torch.float64)
        hits_air = zeros(torch.bool)
        hits_ground = zeros(torch.bool)
        attractor = zeros(torch.bool)

        for card_id, name in enumerate(resolved, start=1):
            card = loader.get_card(name)
            if card is None:
                raise ValueError(f"could not materialize card {name!r}")
            raw = getattr(card, "_raw_entry", {}) or {}
            character = raw.get("summonCharacterData", {}) or {}
            projectile = character.get("projectileSpecialData", {}) or {}
            deploy_projectile = raw.get("projectileData", {}) or {}
            operations = selected[name]
            count[card_id] = len(operations)
            for slot, mechanic in enumerate(operations):
                operation = SpecialMovementOpcode(
                    SPECIAL_OPCODE_BY_CLASS[type(mechanic).__name__]
                )
                opcode[card_id, slot] = int(operation)
                if operation == SpecialMovementOpcode.ATTACK_RECOIL:
                    distance[card_id, slot] = round(
                        float(character.get("attackPushback", 0) or 0)
                    )
                elif operation == SpecialMovementOpcode.BANDIT_DASH:
                    minimum[card_id, slot] = round(
                        float(character.get("dashMinRange", 0) or 0)
                    )
                    maximum[card_id, slot] = round(
                        float(character.get("dashMaxRange", 0) or 0)
                    )
                    windup[card_id, slot] = float(character.get("dashCooldown", 0) or 0)
                    speed[card_id, slot] = round(
                        float(character.get("jumpSpeed", 0) or 0)
                    )
                    damage[card_id, slot] = float(character.get("dashDamage", 0) or 0)
                    post_immunity[card_id, slot] = int(
                        character.get("dashImmuneToDamageTime", 0) or 0
                    )
                elif operation == SpecialMovementOpcode.FISHERMAN_HOOK:
                    minimum[card_id, slot] = round(
                        float(getattr(card, "special_min_range", 0) or 3500)
                    )
                    maximum[card_id, slot] = round(
                        float(getattr(card, "special_range", 0) or 7000)
                    )
                    windup[card_id, slot] = float(
                        getattr(card, "special_load_time", 0) or 1300
                    )
                    speed[card_id, slot] = round(
                        float(projectile.get("speed", 800) or 800)
                    )
                    secondary_speed[card_id, slot] = round(
                        float(projectile.get("dragBackSpeed", 850) or 850)
                    )
                    tertiary_speed[card_id, slot] = round(
                        float(projectile.get("dragSelfSpeed", 450) or 450)
                    )
                    margin[card_id, slot] = round(
                        float(projectile.get("dragMargin", 200) or 200)
                    )
                    attractor[card_id, slot] = bool(
                        projectile.get("dragBackAsAttractor", False)
                    )
                elif operation == SpecialMovementOpcode.MEGA_KNIGHT_SLAM:
                    distance[card_id, slot] = round(
                        float(character.get("dashPushBack", 0) or 0)
                    )
                    radius[card_id, slot] = round(
                        float(
                            character.get(
                                "dashRadius", deploy_projectile.get("radius", 0)
                            )
                            or 0
                        )
                    )
                    minimum[card_id, slot] = round(
                        float(character.get("dashMinRange", 0) or 0)
                    )
                    maximum[card_id, slot] = round(
                        float(character.get("dashMaxRange", 0) or 0)
                    )
                    windup[card_id, slot] = float(character.get("dashCooldown", 0) or 0)
                    speed[card_id, slot] = round(
                        float(character.get("jumpSpeed", 0) or 0)
                    )
                    duration[card_id, slot] = float(
                        character.get("dashConstantTime", 0) or 0
                    )
                    secondary_duration[card_id, slot] = float(
                        character.get("dashLandingTime", 0) or 0
                    )
                    damage[card_id, slot] = float(character.get("dashDamage", 0) or 0)
                    secondary_damage[card_id, slot] = float(
                        deploy_projectile.get("damage", 0) or 0
                    )
                elif operation == SpecialMovementOpcode.SPAWN_PUSHBACK:
                    distance[card_id, slot] = tiles_to_logic_units(
                        float(getattr(mechanic, "distance_tiles"))
                    )
                    radius[card_id, slot] = tiles_to_logic_units(
                        float(getattr(mechanic, "radius_tiles"))
                    )
                    hits_air[card_id, slot] = bool(getattr(mechanic, "hits_air"))
                    hits_ground[card_id, slot] = bool(getattr(mechanic, "hits_ground"))
                elif operation == SpecialMovementOpcode.UNDERGROUND_DEPLOYMENT:
                    speed[card_id, slot] = round(
                        float(character.get("spawnPathfindSpeed", 650) or 650)
                    )
                # BattleRam and Wall Breakers are parameter-free lifecycle ops.

        return cls(
            device=torch_device,
            names=names,
            name_to_id=name_to_id,
            opcode=opcode,
            count=count,
            distance_units=distance,
            radius_units=radius,
            min_range_units=minimum,
            max_range_units=maximum,
            windup_ms=windup,
            speed_units=speed,
            secondary_speed_units=secondary_speed,
            tertiary_speed_units=tertiary_speed,
            duration_ms=duration,
            secondary_duration_ms=secondary_duration,
            post_immunity_ms=post_immunity,
            margin_units=margin,
            damage=damage,
            secondary_damage=secondary_damage,
            hits_air=hits_air,
            hits_ground=hits_ground,
            as_attractor=attractor,
        )


@dataclass(frozen=True)
class TensorSpecialEvents:
    valid: torch.Tensor
    opcode: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor
    amount: torch.Tensor


def stable_special_events(
    valid: torch.Tensor,
    opcode: torch.Tensor,
    source_id: torch.Tensor,
    target_id: torch.Tensor,
    amount: torch.Tensor | None = None,
) -> TensorSpecialEvents:
    """Pack valid pair lanes in stable ``(source ID, target ID, lane)`` order."""

    if valid.shape != opcode.shape or valid.shape != source_id.shape:
        raise ValueError("event tensors must share shape [batch, lane]")
    lanes = valid.shape[1]
    lane_id = torch.arange(lanes, dtype=torch.int64, device=valid.device)[None, :]
    maximum_id = torch.maximum(source_id, target_id).amax().to(torch.int64) + 2
    key = (source_id * maximum_id + target_id) * (lanes + 1) + lane_id
    sentinel = torch.iinfo(torch.int64).max
    order = torch.argsort(torch.where(valid, key, sentinel), dim=1, stable=True)

    def gather(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, order)

    return TensorSpecialEvents(
        valid=gather(valid),
        opcode=gather(opcode),
        source_id=gather(source_id),
        target_id=gather(target_id),
        amount=gather(
            torch.zeros_like(source_id, dtype=torch.float64)
            if amount is None
            else amount
        ),
    )


def vector_towards_units(
    delta_units: torch.Tensor,
    work_units: torch.Tensor,
) -> torch.Tensor:
    remaining = integer_sqrt_tensor(torch.sum(delta_units * delta_units, dim=-1))
    movement = torch.minimum(torch.clamp(work_units.to(torch.int64), min=0), remaining)
    partial = normalized_vector_units(delta_units, movement)
    return torch.where((movement >= remaining).unsqueeze(-1), delta_units, partial)


@dataclass(frozen=True)
class KnockbackInstallResult:
    target_units: torch.Tensor
    velocity_work: torch.Tensor
    started: torch.Tensor


def install_radial_knockback(
    position_units: torch.Tensor,
    origin_units: torch.Tensor,
    distance_units: torch.Tensor,
    *,
    player_id: torch.Tensor,
    eligible: torch.Tensor,
) -> KnockbackInstallResult:
    """Install the native velocity-ramp pushback state without moving it."""

    distance = torch.clamp(distance_units.to(torch.int64), min=0, max=10_000)
    delta = position_units.to(torch.int64) - origin_units.to(torch.int64)
    coincident = torch.all(delta == 0, dim=-1)
    fallback = torch.stack(
        (torch.where(player_id == 0, 1, -1), torch.zeros_like(player_id)), dim=-1
    )
    direction = torch.where(coincident.unsqueeze(-1), fallback, delta)
    displacement = normalized_vector_units(direction, distance)
    started = eligible & (distance > 0)
    target = torch.where(
        started.unsqueeze(-1), position_units + displacement, position_units
    )
    velocity = torch.zeros_like(distance)
    accumulated = torch.zeros_like(distance)
    for _ in range(29):
        advance = started & (accumulated < distance)
        velocity = torch.where(advance, velocity + 25, velocity)
        accumulated = torch.where(advance, accumulated + velocity, accumulated)
    return KnockbackInstallResult(
        target_units=target,
        velocity_work=torch.where(started, velocity, 0),
        started=started,
    )


@dataclass(frozen=True)
class CommitTransitionResult:
    hitpoints: torch.Tensor
    alive: torch.Tensor
    triggered: torch.Tensor
    forced_movement: torch.Tensor
    knockback: KnockbackInstallResult
    events: TensorSpecialEvents


def dispatch_attack_commits(
    opcode: torch.Tensor,
    *,
    source_id: torch.Tensor,
    target_id: torch.Tensor,
    source_position_units: torch.Tensor,
    target_position_units: torch.Tensor,
    source_player: torch.Tensor,
    source_hitpoints: torch.Tensor,
    source_alive: torch.Tensor,
    target_kind: torch.Tensor,
    attack_committed: torch.Tensor,
    attack_hit: torch.Tensor,
    triggered: torch.Tensor,
    recoil_distance_units: torch.Tensor,
) -> CommitTransitionResult:
    recoil = (
        (opcode == int(SpecialMovementOpcode.ATTACK_RECOIL))
        & attack_committed
        & source_alive
    )
    knockback = install_radial_knockback(
        source_position_units,
        target_position_units,
        recoil_distance_units,
        player_id=source_player,
        eligible=recoil,
    )
    ram = (
        (opcode == int(SpecialMovementOpcode.BATTLE_RAM_CHARGE))
        & attack_hit
        & ~triggered
        & (target_kind == 1)
        & source_alive
    )
    wall = (
        (opcode == int(SpecialMovementOpcode.WALL_BREAKERS_DEMOLITION))
        & attack_committed
        & ~triggered
        & source_alive
    )
    self_death = ram | wall
    next_hp = torch.where(
        self_death, torch.zeros_like(source_hitpoints), source_hitpoints
    )
    next_alive = source_alive & ~self_death
    next_triggered = triggered | self_death
    event_valid = knockback.started | self_death
    event_opcode = torch.where(
        self_death,
        int(SpecialEventOpcode.SELF_DEATH),
        int(SpecialEventOpcode.KNOCKBACK_STARTED),
    ).to(torch.int16)
    events = stable_special_events(
        event_valid,
        event_opcode,
        source_id,
        target_id,
    )
    return CommitTransitionResult(
        hitpoints=next_hp,
        alive=next_alive,
        triggered=next_triggered,
        forced_movement=knockback.started,
        knockback=knockback,
        events=events,
    )


@dataclass(frozen=True)
class DashState:
    phase: torch.Tensor
    position_units: torch.Tensor
    origin_units: torch.Tensor
    destination_units: torch.Tensor
    progress_ms: torch.Tensor
    travel_duration_ms: torch.Tensor
    target_id: torch.Tensor
    special_active: torch.Tensor
    special_consumed: torch.Tensor
    invulnerable_until_ms: torch.Tensor


@dataclass(frozen=True)
class DashStepResult:
    state: DashState
    damage_target: torch.Tensor
    damage: torch.Tensor
    finished: torch.Tensor


def step_bandit_dash(
    state: DashState,
    *,
    target_id: torch.Tensor,
    target_position_units: torch.Tensor,
    target_radius_units: torch.Tensor,
    target_in_range: torch.Tensor,
    target_valid: torch.Tensor,
    stunned: torch.Tensor,
    attack_rate: torch.Tensor,
    attack_range_units: torch.Tensor,
    windup_ms: torch.Tensor,
    jump_speed_units: torch.Tensor,
    dash_damage: torch.Tensor,
    post_immunity_ms: torch.Tensor,
    battle_time_ms: torch.Tensor,
    dt_ms: int = 50,
) -> DashStepResult:
    phase = state.phase.clone()
    progress = state.progress_ms.clone()
    position = state.position_units.clone()
    origin = state.origin_units.clone()
    destination = state.destination_units.clone()
    duration = state.travel_duration_ms.clone()
    retained_target = state.target_id.clone()
    special = state.special_active.clone()
    consumed = torch.zeros_like(state.special_consumed)
    immunity = state.invulnerable_until_ms.clone()

    idle = phase == int(DashPhase.IDLE)
    start = idle & target_valid & target_in_range & ~stunned
    phase = torch.where(start, int(DashPhase.CHARGING), phase)
    progress = torch.where(start, torch.zeros_like(progress), progress)
    retained_target = torch.where(start, target_id, retained_target)
    special |= start

    charging = (phase == int(DashPhase.CHARGING)) & ~start
    cancel = charging & (~target_valid | ~target_in_range)
    progress = torch.where(
        charging & ~cancel & ~stunned,
        progress + float(dt_ms) * attack_rate,
        progress,
    )
    launch = charging & ~cancel & ~stunned & (progress + 1e-9 >= windup_ms)
    delta = target_position_units - position
    distance = integer_sqrt_tensor(torch.sum(delta * delta, dim=-1))
    travel = torch.clamp(distance - attack_range_units - target_radius_units, min=0)
    endpoint = position + normalized_vector_units(delta, travel)
    committed = integer_sqrt_tensor(torch.sum((endpoint - position) ** 2, dim=-1))
    launch_duration = torch.clamp(
        committed.to(torch.float64)
        / torch.clamp(jump_speed_units, min=1).to(torch.float64)
        * 50.0,
        min=1.0,
    )
    origin = torch.where(launch.unsqueeze(-1), position, origin)
    destination = torch.where(launch.unsqueeze(-1), endpoint, destination)
    duration = torch.where(launch, launch_duration, duration)
    progress = torch.where(launch, torch.zeros_like(progress), progress)
    phase = torch.where(launch, int(DashPhase.TRAVEL), phase)
    immunity = torch.where(
        launch,
        battle_time_ms.to(torch.float64) + launch_duration,
        immunity,
    )
    phase = torch.where(cancel, int(DashPhase.IDLE), phase)
    progress = torch.where(cancel, torch.zeros_like(progress), progress)
    retained_target = torch.where(cancel, -1, retained_target)
    special &= ~cancel
    consumed |= cancel

    travelling = (phase == int(DashPhase.TRAVEL)) & ~launch
    delta_to_end = destination - position
    remaining = integer_sqrt_tensor(torch.sum(delta_to_end * delta_to_end, dim=-1))
    work = torch.clamp(jump_speed_units, min=0) * int(dt_ms) // 50
    displacement = vector_towards_units(delta_to_end, work)
    position = torch.where(travelling.unsqueeze(-1), position + displacement, position)
    progress = torch.where(travelling, progress + float(dt_ms), progress)
    finished = travelling & (remaining <= work)
    position = torch.where(finished.unsqueeze(-1), destination, position)
    phase = torch.where(finished, int(DashPhase.IDLE), phase)
    progress = torch.where(finished, torch.zeros_like(progress), progress)
    duration = torch.where(finished, torch.zeros_like(duration), duration)
    special &= ~finished
    consumed |= finished
    damage_target = torch.where(finished & target_valid, retained_target, -1)
    retained_target = torch.where(finished, -1, retained_target)
    immunity = torch.where(
        finished,
        battle_time_ms.to(torch.float64) + post_immunity_ms.to(torch.float64),
        immunity,
    )
    return DashStepResult(
        state=DashState(
            phase=phase,
            position_units=position,
            origin_units=origin,
            destination_units=destination,
            progress_ms=progress,
            travel_duration_ms=duration,
            target_id=retained_target,
            special_active=special,
            special_consumed=consumed,
            invulnerable_until_ms=immunity,
        ),
        damage_target=damage_target,
        damage=torch.where(finished & target_valid, dash_damage, 0.0),
        finished=finished,
    )


@dataclass(frozen=True)
class LeapState:
    phase: torch.Tensor
    position_units: torch.Tensor
    origin_units: torch.Tensor
    destination_units: torch.Tensor
    progress_ms: torch.Tensor
    travel_duration_ms: torch.Tensor
    target_id: torch.Tensor
    special_active: torch.Tensor
    special_consumed: torch.Tensor


@dataclass(frozen=True)
class LeapStepResult:
    state: LeapState
    slam: torch.Tensor
    finished: torch.Tensor


def step_mega_knight_leap(
    state: LeapState,
    *,
    target_id: torch.Tensor,
    target_position_units: torch.Tensor,
    target_radius_units: torch.Tensor,
    target_in_range: torch.Tensor,
    target_valid: torch.Tensor,
    stunned: torch.Tensor,
    attack_rate: torch.Tensor,
    attack_range_units: torch.Tensor,
    windup_ms: torch.Tensor,
    airborne_duration_ms: torch.Tensor,
    landing_duration_ms: torch.Tensor,
    dt_ms: int = 50,
) -> LeapStepResult:
    phase = state.phase.clone()
    position = state.position_units.clone()
    origin = state.origin_units.clone()
    destination = state.destination_units.clone()
    progress = state.progress_ms.clone()
    duration = state.travel_duration_ms.clone()
    retained_target = state.target_id.clone()
    special = state.special_active.clone()
    consumed = torch.zeros_like(state.special_consumed)

    start = (phase == int(LeapPhase.IDLE)) & target_valid & target_in_range & ~stunned
    phase = torch.where(start, int(LeapPhase.CHARGING), phase)
    progress = torch.where(start, torch.zeros_like(progress), progress)
    retained_target = torch.where(start, target_id, retained_target)
    special |= start
    charging = (phase == int(LeapPhase.CHARGING)) & ~start
    cancel = charging & (~target_valid | ~target_in_range)
    progress = torch.where(
        charging & ~cancel & ~stunned,
        progress + float(dt_ms) * attack_rate,
        progress,
    )
    launch = charging & ~cancel & ~stunned & (progress + 1e-9 >= windup_ms)
    delta = target_position_units - position
    distance = integer_sqrt_tensor(torch.sum(delta * delta, dim=-1))
    travel = torch.clamp(distance - attack_range_units - target_radius_units, min=0)
    endpoint = position + normalized_vector_units(delta, travel)
    origin = torch.where(launch.unsqueeze(-1), position, origin)
    destination = torch.where(launch.unsqueeze(-1), endpoint, destination)
    duration = torch.where(launch, torch.clamp(airborne_duration_ms, min=1.0), duration)
    progress = torch.where(launch, torch.zeros_like(progress), progress)
    phase = torch.where(launch, int(LeapPhase.AIRBORNE), phase)
    phase = torch.where(cancel, int(LeapPhase.IDLE), phase)
    progress = torch.where(cancel, torch.zeros_like(progress), progress)
    retained_target = torch.where(cancel, -1, retained_target)
    special &= ~cancel
    consumed |= cancel

    airborne = (phase == int(LeapPhase.AIRBORNE)) & ~launch
    next_progress = progress + float(dt_ms)
    elapsed = torch.minimum(torch.round(duration), torch.round(next_progress)).to(
        torch.int64
    )
    rounded_duration = torch.clamp(torch.round(duration).to(torch.int64), min=1)
    interpolated = origin + trunc_div_tensor(
        (destination - origin) * elapsed.unsqueeze(-1),
        rounded_duration.unsqueeze(-1),
    )
    position = torch.where(airborne.unsqueeze(-1), interpolated, position)
    progress = torch.where(airborne, next_progress, progress)
    slam = airborne & (next_progress + 1e-9 >= duration)
    position = torch.where(slam.unsqueeze(-1), destination, position)
    progress = torch.where(slam, torch.zeros_like(progress), progress)
    duration = torch.where(slam, torch.zeros_like(duration), duration)
    enter_landing = slam & (landing_duration_ms > 0)
    finish_air = slam & ~enter_landing
    phase = torch.where(enter_landing, int(LeapPhase.LANDING), phase)
    phase = torch.where(finish_air, int(LeapPhase.IDLE), phase)

    landing = (phase == int(LeapPhase.LANDING)) & ~enter_landing
    progress = torch.where(landing, progress + float(dt_ms), progress)
    finish_landing = landing & (progress + 1e-9 >= landing_duration_ms)
    finished = finish_air | finish_landing
    phase = torch.where(finish_landing, int(LeapPhase.IDLE), phase)
    progress = torch.where(finish_landing, torch.zeros_like(progress), progress)
    retained_target = torch.where(finished, -1, retained_target)
    special &= ~finished
    consumed |= finished
    return LeapStepResult(
        state=LeapState(
            phase=phase,
            position_units=position,
            origin_units=origin,
            destination_units=destination,
            progress_ms=progress,
            travel_duration_ms=duration,
            target_id=retained_target,
            special_active=special,
            special_consumed=consumed,
        ),
        slam=slam,
        finished=finished,
    )


@dataclass(frozen=True)
class HookState:
    phase: torch.Tensor
    source_position_units: torch.Tensor
    target_position_units: torch.Tensor
    hook_position_units: torch.Tensor
    target_id: torch.Tensor
    windup_remaining_ms: torch.Tensor
    target_forced: torch.Tensor
    special_active: torch.Tensor
    special_consumed: torch.Tensor


@dataclass(frozen=True)
class HookStepResult:
    state: HookState
    finished: torch.Tensor


def step_fisherman_hook(
    state: HookState,
    *,
    acquired_target_id: torch.Tensor,
    launch_position_units: torch.Tensor,
    target_valid: torch.Tensor,
    target_in_range: torch.Tensor,
    target_plane_valid: torch.Tensor,
    target_can_forced_move: torch.Tensor,
    target_is_building: torch.Tensor,
    move_allowed: torch.Tensor,
    attack_rate: torch.Tensor,
    windup_ms: torch.Tensor,
    projectile_speed_units: torch.Tensor,
    drag_back_speed_units: torch.Tensor,
    drag_self_speed_units: torch.Tensor,
    drag_margin_units: torch.Tensor,
    source_radius_units: torch.Tensor,
    target_radius_units: torch.Tensor,
    stunned: torch.Tensor,
    dt_ms: int = 50,
) -> HookStepResult:
    phase = state.phase.clone()
    source = state.source_position_units.clone()
    target = state.target_position_units.clone()
    hook = state.hook_position_units.clone()
    retained_target = state.target_id.clone()
    windup = state.windup_remaining_ms.clone()
    forced = state.target_forced.clone()
    special = state.special_active.clone()
    consumed = torch.zeros_like(state.special_consumed)

    cancel = (phase != int(HookPhase.IDLE)) & (~target_valid | stunned)
    start = (phase == int(HookPhase.IDLE)) & target_valid & target_in_range & ~stunned
    phase = torch.where(start, int(HookPhase.WINDUP), phase)
    retained_target = torch.where(start, acquired_target_id, retained_target)
    windup = torch.where(start, windup_ms, windup)
    special |= start

    winding = (phase == int(HookPhase.WINDUP)) & ~start & ~cancel
    cancel |= winding & ~target_in_range
    work = float(dt_ms) * attack_rate
    launch = winding & ~cancel & (work + 1e-9 >= windup)
    windup = torch.where(winding & ~launch & ~cancel, windup - work, windup)
    phase = torch.where(launch, int(HookPhase.FLIGHT), phase)
    hook = torch.where(launch.unsqueeze(-1), launch_position_units, hook)
    windup = torch.where(launch, torch.zeros_like(windup), windup)

    flight = (phase == int(HookPhase.FLIGHT)) & ~launch & ~cancel
    cancel |= flight & ~target_plane_valid
    delta = target - hook
    remaining = integer_sqrt_tensor(torch.sum(delta * delta, dim=-1))
    flight_work = torch.clamp(projectile_speed_units, min=0) * int(dt_ms) // 50
    flight_move = vector_towards_units(delta, flight_work)
    hook = torch.where((flight & ~cancel).unsqueeze(-1), hook + flight_move, hook)
    arrived = flight & ~cancel & (remaining <= flight_work)
    cancel |= arrived & ~target_can_forced_move
    phase = torch.where(arrived & ~cancel, int(HookPhase.DRAG), phase)
    hook = torch.where(arrived.unsqueeze(-1), target, hook)
    forced |= arrived & ~cancel & ~target_is_building

    drag = (phase == int(HookPhase.DRAG)) & ~cancel & ~arrived
    drag_delta = source - target
    distance = integer_sqrt_tensor(torch.sum(drag_delta * drag_delta, dim=-1))
    desired = source_radius_units + target_radius_units + drag_margin_units
    remaining_drag = torch.clamp(distance - desired, min=0)
    pull_self = drag & target_is_building
    drag_speed = torch.where(pull_self, drag_self_speed_units, drag_back_speed_units)
    drag_work = torch.minimum(
        remaining_drag,
        torch.clamp(drag_speed, min=0) * int(dt_ms) // 50,
    )
    target_move = normalized_vector_units(drag_delta, drag_work)
    source_move = normalized_vector_units(-drag_delta, drag_work)
    can_drag = drag & move_allowed & (remaining_drag > 0) & (drag_work > 0)
    target = torch.where(
        (can_drag & ~pull_self).unsqueeze(-1), target + target_move, target
    )
    source = torch.where(
        (can_drag & pull_self).unsqueeze(-1), source + source_move, source
    )
    post_delta = source - target
    post_distance = integer_sqrt_tensor(torch.sum(post_delta * post_delta, dim=-1))
    finish = drag & ((remaining_drag <= 0) | ~move_allowed | (post_distance <= desired))
    cancel |= finish
    phase = torch.where(cancel, int(HookPhase.IDLE), phase)
    retained_target = torch.where(cancel, -1, retained_target)
    windup = torch.where(cancel, torch.zeros_like(windup), windup)
    forced &= ~cancel
    special &= ~cancel
    consumed |= cancel
    hook = torch.where(cancel.unsqueeze(-1), torch.zeros_like(hook), hook)
    return HookStepResult(
        state=HookState(
            phase=phase,
            source_position_units=source,
            target_position_units=target,
            hook_position_units=hook,
            target_id=retained_target,
            windup_remaining_ms=windup,
            target_forced=forced,
            special_active=special,
            special_consumed=consumed,
        ),
        finished=cancel,
    )


@dataclass(frozen=True)
class UndergroundStepResult:
    position_units: torch.Tensor
    underground_active: torch.Tensor
    special_active: torch.Tensor
    reached_destination: torch.Tensor


def step_underground_deployment(
    position_units: torch.Tensor,
    destination_units: torch.Tensor,
    *,
    underground_active: torch.Tensor,
    total_delay_seconds: torch.Tensor,
    remaining_delay_seconds: torch.Tensor,
    travel_duration_seconds: torch.Tensor,
    speed_units: torch.Tensor,
    dt_ms: int = 50,
) -> UndergroundStepResult:
    elapsed = torch.clamp(total_delay_seconds - remaining_delay_seconds, min=0.0)
    frame_seconds = max(0, int(dt_ms)) / 1000.0
    reached = underground_active & (
        (travel_duration_seconds <= 0)
        | (elapsed + frame_seconds >= travel_duration_seconds - 1e-12)
    )
    delta = destination_units - position_units
    work = torch.clamp(speed_units, min=0) * int(dt_ms) // 50
    moved = position_units + vector_towards_units(delta, work)
    position = torch.where(
        reached.unsqueeze(-1),
        destination_units,
        torch.where(underground_active.unsqueeze(-1), moved, position_units),
    )
    # Emergence owns the remaining deploy clock. Travel reaching its endpoint
    # does not itself surface the character.
    surfaced = underground_active & (remaining_delay_seconds <= 0)
    return UndergroundStepResult(
        position_units=position,
        underground_active=underground_active & ~surfaced,
        special_active=underground_active & ~surfaced,
        reached_destination=reached,
    )


@dataclass(frozen=True)
class SpawnPushbackResult:
    affected: torch.Tensor
    knockback: KnockbackInstallResult
    events: TensorSpecialEvents


def dispatch_spawn_pushback(
    opcode: torch.Tensor,
    *,
    source_id: torch.Tensor,
    target_id: torch.Tensor,
    source_owner: torch.Tensor,
    target_owner: torch.Tensor,
    source_position_units: torch.Tensor,
    target_position_units: torch.Tensor,
    target_radius_units: torch.Tensor,
    target_player: torch.Tensor,
    target_alive: torch.Tensor,
    target_is_troop: torch.Tensor,
    target_is_air: torch.Tensor,
    spawned: torch.Tensor,
    distance_units: torch.Tensor,
    radius_units: torch.Tensor,
    hits_air: torch.Tensor,
    hits_ground: torch.Tensor,
) -> SpawnPushbackResult:
    delta = target_position_units - source_position_units
    distance_sq = torch.sum(delta * delta, dim=-1)
    combined = radius_units + target_radius_units
    intersects = distance_sq < combined * combined
    plane = torch.where(target_is_air, hits_air, hits_ground)
    affected = (
        (opcode == int(SpecialMovementOpcode.SPAWN_PUSHBACK))
        & spawned
        & target_alive
        & target_is_troop
        & (source_id != target_id)
        & (source_owner != target_owner)
        & plane
        & intersects
    )
    knockback = install_radial_knockback(
        target_position_units,
        source_position_units,
        distance_units,
        player_id=target_player,
        eligible=affected,
    )
    events = stable_special_events(
        knockback.started,
        torch.full_like(opcode, int(SpecialEventOpcode.KNOCKBACK_STARTED)),
        source_id,
        target_id,
    )
    return SpawnPushbackResult(affected=affected, knockback=knockback, events=events)
