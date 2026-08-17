"""Fail-closed adapters between Python runtime objects and tensor objects.

The tensor object kernel intentionally does not import the Python oracle.  This
module is its boundary: it compiles already-materialized runtime objects into
``TensorObjectCatalog``/``TensorObjectState``, preserves manager IDs and order,
and replays emitted payload events into a Python battle for shadow comparison.

Only object-manager behavior represented by :mod:`clasher.torch_sim.objects`
is admitted.  Every other live feature marks the complete battle unsupported;
``step_object_phase`` will then leave that battle byte-for-byte untouched.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import IntEnum

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import (
    AreaEffect,
    BuffAreaEffect,
    Building,
    DeathAreaEffectContainer,
    Entity,
    Projectile,
    SpawnProjectile,
    TimedExplosive,
    Troop,
)
from clasher.kinematics import (
    LOGIC_TICK_MILLISECONDS,
    logic_units_to_tiles,
    tiles_per_second_to_logic_speed,
    tiles_to_logic_units,
)
from clasher.mechanics.shared.death_area import spawn_death_area_payload

from .objects import (
    ObjectBlueprint,
    ObjectEventOpcode,
    ObjectOpcode,
    ObjectPhaseResult,
    TensorObjectCatalog,
    TensorObjectState,
    UnsupportedObjectFeature,
)


class RuntimePayloadOpcode(IntEnum):
    """Generalized payload identities retained by the boundary catalog."""

    NONE = 0
    SPAWN_CHARACTER = 1
    DEATH_AREA = 2
    EXPLOSION = 3


class RuntimeObjectKind(IntEnum):
    UNKNOWN = 0
    PROJECTILE = 1
    SPAWN_PROJECTILE = 2
    AREA = 3
    DEATH_AREA_CONTAINER = 4
    TIMED_EXPLOSIVE = 5


@dataclass(frozen=True)
class RuntimeObjectFailure:
    """Why one object forces its containing battle to Python fallback."""

    batch_index: int
    object_id: int
    object_type: str
    features: UnsupportedObjectFeature
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeBlueprintMetadata:
    """Boundary-only metadata paired one-to-one with catalog blueprints."""

    kind: RuntimeObjectKind
    object_type: type[Entity] | None
    reasons: tuple[str, ...] = ()


@dataclass
class RuntimeObjectBatch:
    """A tensor object batch plus stable bindings back to Python battles."""

    catalog: TensorObjectCatalog
    state: TensorObjectState
    metadata: tuple[RuntimeBlueprintMetadata, ...]
    failures: tuple[RuntimeObjectFailure, ...]
    _bindings: tuple[dict[int, int], ...]

    @property
    def supported_batches(self) -> torch.Tensor:
        return ~self.state.unsupported_batches()

    def sync_result(
        self,
        battles: Sequence[BattleState],
        result: ObjectPhaseResult,
    ) -> torch.Tensor:
        """Apply supported event streams and state back to Python battles.

        Unsupported batches are not touched.  The returned boolean tensor is
        the exact set of batches synchronized, making mixed production batches
        safe for a caller to route independently to the Python oracle.
        """

        if len(battles) != self.state.batch_size:
            raise ValueError("battle count does not match tensor object batch")
        if result.unsupported_batch.shape != (self.state.batch_size,):
            raise ValueError("object phase result has the wrong batch shape")

        synchronized = ~result.unsupported_batch
        for batch_index, battle in enumerate(battles):
            if not bool(synchronized[batch_index].item()):
                continue
            self._apply_events(batch_index, battle, result)
            self._sync_rows(batch_index, battle)
        return synchronized

    def _apply_events(
        self,
        batch_index: int,
        battle: BattleState,
        result: ObjectPhaseResult,
    ) -> None:
        pending_impacts: list[tuple[Projectile, tuple[Entity, ...]]] = []
        count = int(result.events.count[batch_index].item())
        for event_index in range(count):
            event_opcode = ObjectEventOpcode(
                int(result.events.opcode[batch_index, event_index].item())
            )
            source_id = int(result.events.source_id[batch_index, event_index].item())
            source = battle.entities.get(source_id)
            if source is None:
                raise RuntimeError(
                    f"tensor object event references absent entity {source_id}"
                )

            if event_opcode == ObjectEventOpcode.PROJECTILE_IMPACT:
                if type(source) is Projectile:
                    # Production battle ticks commit every projectile overlap
                    # during the object phase, then resolve all committed
                    # impacts afterward. Retaining that split preserves
                    # reciprocal lethal hits and same-frame area ordering.
                    targets = tuple(source._collect_splash_targets(battle))
                    pending_impacts.append((source, targets))
                elif type(source) is SpawnProjectile:
                    # Character-spawning carriers are currently rejected by
                    # compilation, so this is reachable only for a zero-count
                    # carrier whose impact is an ordinary projectile payload.
                    source._deal_splash_damage(battle)
                else:
                    raise RuntimeError(
                        f"impact event has non-projectile source {type(source).__name__}"
                    )
            elif event_opcode == ObjectEventOpcode.AREA_TICK:
                if type(source) is not AreaEffect:
                    raise RuntimeError(
                        f"area event has non-area source {type(source).__name__}"
                    )
                amount = float(result.events.amount[batch_index, event_index].item())
                source._apply_damage_tick(battle, amount)
            elif event_opcode == ObjectEventOpcode.SPAWN:
                if type(source) is DeathAreaEffectContainer:
                    child = spawn_death_area_payload(
                        battle,
                        player_id=source.player_id,
                        position=Position(source.position.x, source.position.y),
                        card_stats=source.card_stats,
                        area_data=source.area_data,
                    )
                    if child is None:
                        raise RuntimeError(
                            "death-area payload did not create an object"
                        )
                    self._bind_spawned_object(batch_index, child)
                elif type(source) is SpawnProjectile:
                    # Only a zero-count carrier may be supported, and it never
                    # emits SPAWN. Guard this invariant if a catalog is corrupt.
                    raise RuntimeError(
                        "character-spawn event reached the fail-closed adapter"
                    )
                elif type(source) is TimedExplosive:
                    raise RuntimeError(
                        "timed character-spawn event reached the fail-closed adapter"
                    )
            elif event_opcode == ObjectEventOpcode.DEATH:
                if type(source) is TimedExplosive:
                    source._explode(battle)
                if type(source) is not Projectile:
                    source.is_alive = False

        for projectile, targets in pending_impacts:
            projectile._resolve_impact(battle, targets)

    def _bind_spawned_object(self, batch_index: int, child: Entity) -> None:
        matches = torch.nonzero(
            self.state.allocated[batch_index]
            & (self.state.object_id[batch_index] == child.id),
            as_tuple=False,
        ).flatten()
        if matches.numel() != 1:
            raise RuntimeError(
                f"spawned object id {child.id} does not have one tensor slot"
            )
        slot = int(matches[0].item())
        blueprint_id = int(self.state.blueprint_id[batch_index, slot].item())
        expected_type = self.metadata[blueprint_id].object_type
        if expected_type is None or type(child) is not expected_type:
            expected_name = expected_type.__name__ if expected_type else "none"
            raise RuntimeError(
                "spawned object type disagrees with tensor catalog: "
                f"expected {expected_name}, got {type(child).__name__}"
            )
        self._bindings[batch_index][child.id] = blueprint_id

    def _sync_rows(self, batch_index: int, battle: BattleState) -> None:
        for slot in range(self.state.max_objects):
            if not bool(self.state.allocated[batch_index, slot].item()):
                continue
            object_id = int(self.state.object_id[batch_index, slot].item())
            obj = battle.entities.get(object_id)
            if obj is None:
                raise RuntimeError(
                    f"tensor object id {object_id} is absent after event replay"
                )
            blueprint_id = int(self.state.blueprint_id[batch_index, slot].item())
            if self._bindings[batch_index].get(object_id) != blueprint_id:
                raise RuntimeError(
                    f"runtime binding for object {object_id} changed identity"
                )

            obj.position.x = logic_units_to_tiles(
                int(self.state.x_units[batch_index, slot].item())
            )
            obj.position.y = logic_units_to_tiles(
                int(self.state.y_units[batch_index, slot].item())
            )
            obj.is_alive = bool(self.state.active[batch_index, slot].item())
            tensor_age_ms = int(self.state.age_ms[batch_index, slot].item())
            python_age = float(getattr(obj, "time_alive", 0.0) or 0.0)
            prior_age_ms = round(python_age * 1000.0)
            elapsed_frames = max(
                0,
                (tensor_age_ms - prior_age_ms) // LOGIC_TICK_MILLISECONDS,
            )
            age = python_age
            for _ in range(elapsed_frames):
                age += LOGIC_TICK_MILLISECONDS / 1000.0

            if isinstance(obj, Projectile):
                obj.launch_delay = (
                    int(self.state.launch_delay_ms[batch_index, slot].item()) / 1000.0
                )
                if isinstance(obj, SpawnProjectile):
                    obj.time_alive = age
            elif type(obj) is AreaEffect:
                obj.time_alive = age
                new_ticks_applied = max(
                    0,
                    obj.max_damage_ticks
                    - int(self.state.ticks_remaining[batch_index, slot].item()),
                )
                if obj.max_damage_ticks > 0:
                    next_damage_time = obj.next_damage_time
                    if next_damage_time is None:
                        next_damage_time = (
                            obj.initial_damage_delay
                            if obj.initial_damage_delay is not None
                            else (
                                0.0 if obj.damage_on_spawn else obj.damage_tick_interval
                            )
                        )
                    for _ in range(
                        max(0, new_ticks_applied - obj.damage_ticks_applied)
                    ):
                        next_damage_time += obj.damage_tick_interval
                    obj.next_damage_time = next_damage_time
                obj.damage_ticks_applied = new_ticks_applied
            elif type(obj) is DeathAreaEffectContainer:
                obj.time_alive = age
            elif type(obj) is TimedExplosive:
                obj.time_alive = age


@dataclass(frozen=True)
class _CompiledObject:
    blueprint_id: int
    features: UnsupportedObjectFeature
    reasons: tuple[str, ...]


class _CatalogBuilder:
    def __init__(self, battle: BattleState) -> None:
        self.battle = battle
        self.blueprints: list[ObjectBlueprint] = []
        self.metadata: list[RuntimeBlueprintMetadata] = [
            RuntimeBlueprintMetadata(RuntimeObjectKind.UNKNOWN, None)
        ]

    def add(self, obj: Entity) -> _CompiledObject:
        blueprint, kind, features, reasons = self._blueprint(obj)

        if type(obj) is DeathAreaEffectContainer and not features:
            child = self._materialize_death_area_child(obj)
            compiled_child = self.add(child)
            child_index = compiled_child.blueprint_id - 1
            self.blueprints[child_index] = replace(
                self.blueprints[child_index],
                inherit_terminal_position=True,
                inherit_player=True,
            )
            if compiled_child.features:
                features |= UnsupportedObjectFeature.UNKNOWN_OPERATION
                reasons = (*reasons, "terminal death-area child is unsupported")
            blueprint = replace(
                blueprint,
                terminal_blueprint=compiled_child.blueprint_id,
                feature_mask=int(features),
            )

        self.blueprints.append(blueprint)
        self.metadata.append(
            RuntimeBlueprintMetadata(
                kind=kind,
                object_type=type(obj),
                reasons=reasons,
            )
        )
        return _CompiledObject(len(self.blueprints), features, reasons)

    def _materialize_death_area_child(
        self, container: DeathAreaEffectContainer
    ) -> Entity:
        scratch = copy.copy(self.battle)
        scratch.entities = {}
        scratch.next_entity_id = 1
        child = spawn_death_area_payload(
            scratch,
            player_id=container.player_id,
            position=Position(container.position.x, container.position.y),
            card_stats=container.card_stats,
            area_data=container.area_data,
        )
        if not isinstance(child, Entity):
            raise RuntimeError("death-area serialization did not create an entity")
        return child

    def _blueprint(
        self, obj: Entity
    ) -> tuple[
        ObjectBlueprint,
        RuntimeObjectKind,
        UnsupportedObjectFeature,
        tuple[str, ...],
    ]:
        movement_features, movement_reasons = _movement_features(obj)
        if type(obj) is Projectile:
            blueprint, features, reasons = _projectile_blueprint(obj)
            return (
                replace(
                    blueprint,
                    feature_mask=int(features | movement_features),
                ),
                RuntimeObjectKind.PROJECTILE,
                features | movement_features,
                (*reasons, *movement_reasons),
            )
        if type(obj) is SpawnProjectile:
            blueprint, features, reasons = _projectile_blueprint(obj)
            if obj.spawn_count > 0 or obj.spawn_character_data:
                features |= UnsupportedObjectFeature.UNKNOWN_OPERATION
                reasons = (
                    *reasons,
                    "character payload allocation is not represented by TensorObjectState",
                )
            activation_ms, activation_feature = _integer_milliseconds(
                obj.activation_delay
            )
            _, age_feature = _grid_milliseconds(obj.time_alive)
            features |= activation_feature | age_feature | movement_features
            return (
                replace(
                    blueprint,
                    activation_delay_ms=activation_ms,
                    payload_id=int(RuntimePayloadOpcode.SPAWN_CHARACTER),
                    payload_count=max(0, int(obj.spawn_count)),
                    feature_mask=int(features),
                ),
                RuntimeObjectKind.SPAWN_PROJECTILE,
                features,
                (
                    *reasons,
                    *(
                        ("activation delay is off the native grid",)
                        if activation_feature
                        else ()
                    ),
                    *(("elapsed time is off the native grid",) if age_feature else ()),
                    *movement_reasons,
                ),
            )
        if type(obj) is AreaEffect:
            blueprint, features, reasons = _area_blueprint(obj)
            features |= movement_features
            return (
                replace(blueprint, feature_mask=int(features)),
                RuntimeObjectKind.AREA,
                features,
                (*reasons, *movement_reasons),
            )
        if type(obj) is DeathAreaEffectContainer:
            activation_ms, activation_feature = _integer_milliseconds(
                obj.activation_delay
            )
            _, age_feature = _grid_milliseconds(obj.time_alive)
            features = activation_feature | age_feature | movement_features
            reasons = (
                *(
                    ("activation delay is off the native grid",)
                    if activation_feature
                    else ()
                ),
                *(("elapsed time is off the native grid",) if age_feature else ()),
                *movement_reasons,
            )
            return (
                ObjectBlueprint(
                    opcode=ObjectOpcode.TIMED_PAYLOAD,
                    player_id=obj.player_id,
                    x_units=tiles_to_logic_units(obj.position.x),
                    y_units=tiles_to_logic_units(obj.position.y),
                    activation_delay_ms=activation_ms,
                    payload_id=int(RuntimePayloadOpcode.DEATH_AREA),
                    payload_count=1,
                    inherit_terminal_position=True,
                    inherit_player=True,
                    feature_mask=int(features),
                ),
                RuntimeObjectKind.DEATH_AREA_CONTAINER,
                features,
                reasons,
            )
        if type(obj) is TimedExplosive:
            timer_ms, timer_feature = _integer_milliseconds(obj.explosion_timer)
            _, age_feature = _grid_milliseconds(obj.time_alive)
            features = timer_feature | age_feature | movement_features
            reasons = ()
            if obj.knockback_distance > 0:
                features |= UnsupportedObjectFeature.KNOCKBACK
                reasons += ("explosion knockback is not in the event catalog",)
            if obj.death_spawn_name or obj.death_spawn_count > 0:
                features |= UnsupportedObjectFeature.UNKNOWN_OPERATION
                reasons += ("timed character payload allocation is not represented",)
            if timer_feature:
                reasons += ("explosion timer is off the native grid",)
            if age_feature:
                reasons += ("elapsed time is off the native grid",)
            reasons += movement_reasons
            return (
                ObjectBlueprint(
                    opcode=ObjectOpcode.TIMED_PAYLOAD,
                    player_id=obj.player_id,
                    x_units=tiles_to_logic_units(obj.position.x),
                    y_units=tiles_to_logic_units(obj.position.y),
                    activation_delay_ms=timer_ms,
                    amount=float(obj.explosion_damage),
                    payload_id=int(RuntimePayloadOpcode.EXPLOSION),
                    feature_mask=int(features),
                ),
                RuntimeObjectKind.TIMED_EXPLOSIVE,
                features,
                reasons,
            )

        features = UnsupportedObjectFeature.UNKNOWN_OPERATION | movement_features
        reason = (
            "buff areas require a dedicated buff event consumer"
            if isinstance(obj, BuffAreaEffect)
            else f"runtime object type {type(obj).__name__} has no tensor opcode"
        )
        return (
            ObjectBlueprint(
                opcode=0,
                player_id=obj.player_id,
                x_units=tiles_to_logic_units(obj.position.x),
                y_units=tiles_to_logic_units(obj.position.y),
                feature_mask=int(features),
            ),
            RuntimeObjectKind.UNKNOWN,
            features,
            (reason, *movement_reasons),
        )


def _grid_milliseconds(seconds: float) -> tuple[int, UnsupportedObjectFeature]:
    raw = float(seconds) * 1000.0
    milliseconds = round(raw)
    off_grid = (
        abs(raw - milliseconds) > 1e-6 or milliseconds % LOGIC_TICK_MILLISECONDS != 0
    )
    return (
        milliseconds,
        UnsupportedObjectFeature.FRACTIONAL_DELAY
        if off_grid
        else UnsupportedObjectFeature.NONE,
    )


def _integer_milliseconds(seconds: float) -> tuple[int, UnsupportedObjectFeature]:
    raw = float(seconds) * 1000.0
    milliseconds = round(raw)
    return (
        milliseconds,
        UnsupportedObjectFeature.FRACTIONAL_DELAY
        if abs(raw - milliseconds) > 1e-6
        else UnsupportedObjectFeature.NONE,
    )


def _movement_features(
    obj: Entity,
) -> tuple[UnsupportedObjectFeature, tuple[str, ...]]:
    pending = (
        obj._movement_vector_x_units != 0
        or obj._movement_vector_y_units != 0
        or obj._movement_vector_count != 0
        or obj._movement_vector_bypasses_cap
        or abs(obj._pending_movement_x) > 1e-12
        or abs(obj._pending_movement_y) > 1e-12
        or not obj._pending_movement_consumed
    )
    if not pending:
        return UnsupportedObjectFeature.NONE, ()
    return (
        UnsupportedObjectFeature.UNKNOWN_OPERATION,
        ("pending movement accumulator is not represented",),
    )


def _projectile_blueprint(
    projectile: Projectile,
) -> tuple[ObjectBlueprint, UnsupportedObjectFeature, tuple[str, ...]]:
    launch_ms, launch_feature = _grid_milliseconds(projectile.launch_delay)
    features = launch_feature
    reasons: tuple[str, ...] = ()
    if launch_feature:
        reasons += ("launch delay is off the native grid",)
    if projectile.tracks_target and projectile.primary_target is not None:
        features |= UnsupportedObjectFeature.HOMING
        reasons += ("live target tracking is not represented",)
    if (
        projectile._temporary_homing_remaining_ms > 0
        or projectile._temporary_homing_target is not None
    ):
        features |= UnsupportedObjectFeature.HOMING
        reasons += ("temporary homing state is not represented",)
    if projectile.pierces:
        features |= UnsupportedObjectFeature.PIERCING
        reasons += ("piercing collision samples are not represented",)
    if projectile.stun_duration > 0 or (
        projectile.slow_duration > 0 and projectile.slow_multiplier < 1.0
    ):
        features |= UnsupportedObjectFeature.STATUS_APPLICATION
        reasons += ("projectile status payload is not in the event catalog",)
    if projectile.knockback_distance > 0:
        features |= UnsupportedObjectFeature.KNOCKBACK
        reasons += ("projectile knockback is not in the event catalog",)
    if projectile.damage_waves != 1 or projectile.damage_wave_interval > 0:
        features |= UnsupportedObjectFeature.UNKNOWN_OPERATION
        reasons += ("multi-wave impact allocation is not represented",)
    if projectile.spawn_projectile_data:
        features |= UnsupportedObjectFeature.UNKNOWN_OPERATION
        reasons += ("impact child-projectile allocation is not represented",)

    return (
        ObjectBlueprint(
            opcode=ObjectOpcode.PROJECTILE_LAUNCH,
            player_id=projectile.player_id,
            x_units=tiles_to_logic_units(projectile.position.x),
            y_units=tiles_to_logic_units(projectile.position.y),
            target_x_units=tiles_to_logic_units(projectile.target_position.x),
            target_y_units=tiles_to_logic_units(projectile.target_position.y),
            speed_units_per_tick=tiles_per_second_to_logic_speed(
                projectile.travel_speed
            ),
            launch_delay_ms=launch_ms,
            amount=float(projectile.damage),
            feature_mask=int(features),
        ),
        features,
        reasons,
    )


def _area_blueprint(
    area: AreaEffect,
) -> tuple[ObjectBlueprint, UnsupportedObjectFeature, tuple[str, ...]]:
    duration_ms, duration_feature = _integer_milliseconds(area.duration)
    age_ms, age_feature = _grid_milliseconds(area.time_alive)
    features = duration_feature | age_feature
    reasons: tuple[str, ...] = ()
    if duration_feature:
        reasons += ("area duration is off the native grid",)
    if age_feature:
        reasons += ("area elapsed time is off the native grid",)
    if area.freeze_effect or area.attract_percentage > 0:
        features |= UnsupportedObjectFeature.CONTINUOUS_AREA
        reasons += ("freeze/attraction area behavior is not represented",)
    attack_multiplier = (
        area.attack_speed_multiplier
        if area.attack_speed_multiplier is not None
        else area.speed_multiplier
    )
    spawn_multiplier = (
        area.spawn_speed_multiplier
        if area.spawn_speed_multiplier is not None
        else area.speed_multiplier
    )
    if min(area.speed_multiplier, attack_multiplier, spawn_multiplier) < 1.0:
        features |= UnsupportedObjectFeature.STATUS_APPLICATION
        reasons += ("continuous slow application is not represented",)
    if area.target_local_damage or area.periodic_damage_buff_duration > 0:
        features |= UnsupportedObjectFeature.CONTINUOUS_AREA
        reasons += ("target-owned periodic damage is not represented",)

    if area.max_damage_ticks > 0:
        interval_ms, interval_feature = _integer_milliseconds(area.damage_tick_interval)
        initial_delay = (
            area.initial_damage_delay
            if area.initial_damage_delay is not None
            else (0.0 if area.damage_on_spawn else area.damage_tick_interval)
        )
        initial_ms, initial_feature = _integer_milliseconds(initial_delay)
        features |= interval_feature | initial_feature
        if interval_ms < LOGIC_TICK_MILLISECONDS:
            features |= UnsupportedObjectFeature.SUB_TICK_INTERVAL
            reasons += ("area damage interval is below one native frame",)
        if interval_feature:
            reasons += ("area damage interval is off the native grid",)
        if initial_feature:
            reasons += ("area initial deadline is off the native grid",)
        next_tick_ms = (
            round(area.next_damage_time * 1000.0)
            if area.next_damage_time is not None
            else initial_ms
        )
        amount = float(area.damage)
        max_ticks = area.max_damage_ticks
    else:
        interval_ms = LOGIC_TICK_MILLISECONDS
        initial_ms = LOGIC_TICK_MILLISECONDS
        elapsed_ticks = max(0, age_ms // LOGIC_TICK_MILLISECONDS)
        max_ticks = max(
            0,
            (duration_ms + LOGIC_TICK_MILLISECONDS - 1) // LOGIC_TICK_MILLISECONDS,
        )
        next_tick_ms = (elapsed_ticks + 1) * LOGIC_TICK_MILLISECONDS
        amount = float(area.damage) * (LOGIC_TICK_MILLISECONDS / 1000.0)

    blueprint = ObjectBlueprint(
        opcode=ObjectOpcode.PERIODIC_AREA,
        player_id=area.player_id,
        x_units=tiles_to_logic_units(area.position.x),
        y_units=tiles_to_logic_units(area.position.y),
        duration_ms=duration_ms,
        tick_interval_ms=interval_ms,
        initial_tick_ms=initial_ms,
        max_ticks=max_ticks,
        amount=amount,
        feature_mask=int(features),
    )
    # Current clock fields are installed after TensorObjectState.create; keep
    # them in private attributes on the function result tuple instead of
    # widening the immutable kernel blueprint schema.
    blueprint = replace(blueprint, initial_tick_ms=next_tick_ms)
    return blueprint, features, reasons


def runtime_objects_to_tensor(
    battles: Sequence[BattleState],
    *,
    device: str | torch.device = "cpu",
    max_objects: int = 128,
) -> RuntimeObjectBatch:
    """Compile live non-character objects into one fail-closed tensor batch."""

    if not battles:
        raise ValueError("at least one battle is required")

    blueprints: list[ObjectBlueprint] = []
    metadata: list[RuntimeBlueprintMetadata] = [
        RuntimeBlueprintMetadata(RuntimeObjectKind.UNKNOWN, None)
    ]
    batch_blueprint_ids: list[list[int]] = []
    batch_objects: list[list[Entity]] = []
    bindings: list[dict[int, int]] = []
    failures: list[RuntimeObjectFailure] = []

    for batch_index, battle in enumerate(battles):
        objects = sorted(
            (
                entity
                for entity in battle.entities.values()
                if not isinstance(entity, (Troop, Building))
            ),
            key=lambda entity: entity.id,
        )
        builder = _CatalogBuilder(battle)
        object_blueprints: list[int] = []
        object_bindings: dict[int, int] = {}
        for obj in objects:
            compiled = builder.add(obj)
            object_blueprints.append(compiled.blueprint_id)
            object_bindings[obj.id] = compiled.blueprint_id
            if compiled.features:
                failures.append(
                    RuntimeObjectFailure(
                        batch_index=batch_index,
                        object_id=obj.id,
                        object_type=type(obj).__name__,
                        features=compiled.features,
                        reasons=compiled.reasons,
                    )
                )

        # Shift this battle's complete local catalog exactly once.
        offset = len(blueprints)
        shifted = [
            replace(
                blueprint,
                terminal_blueprint=(
                    blueprint.terminal_blueprint + offset
                    if blueprint.terminal_blueprint > 0
                    else 0
                ),
            )
            for blueprint in builder.blueprints
        ]
        blueprints.extend(shifted)
        metadata.extend(builder.metadata[1:])
        shifted_ids = [value + offset for value in object_blueprints]
        batch_blueprint_ids.append(shifted_ids)
        batch_objects.append(objects)
        bindings.append(
            {
                object_id: blueprint_id + offset
                for object_id, blueprint_id in object_bindings.items()
            }
        )

    catalog = TensorObjectCatalog.compile(blueprints, device=device)
    state = TensorObjectState.create(
        catalog,
        batch_blueprint_ids,
        max_objects=max_objects,
    )

    for batch_index, (battle, objects) in enumerate(zip(battles, batch_objects)):
        state.next_object_id[batch_index] = battle.next_entity_id
        for slot, obj in enumerate(objects):
            state.object_id[batch_index, slot] = obj.id
            state.active[batch_index, slot] = obj.is_alive
            age = float(getattr(obj, "time_alive", 0.0) or 0.0)
            state.age_ms[batch_index, slot] = round(age * 1000.0)
            if type(obj) is AreaEffect:
                if obj.max_damage_ticks > 0:
                    next_damage_time = (
                        obj.next_damage_time
                        if obj.next_damage_time is not None
                        else (
                            obj.initial_damage_delay
                            if obj.initial_damage_delay is not None
                            else (
                                0.0 if obj.damage_on_spawn else obj.damage_tick_interval
                            )
                        )
                    )
                    state.next_tick_ms[batch_index, slot] = round(
                        next_damage_time * 1000.0
                    )
                    state.ticks_remaining[batch_index, slot] = max(
                        0,
                        obj.max_damage_ticks - obj.damage_ticks_applied,
                    )
                else:
                    elapsed_ticks = round(age * 1000.0) // LOGIC_TICK_MILLISECONDS
                    state.next_tick_ms[batch_index, slot] = (
                        elapsed_ticks + 1
                    ) * LOGIC_TICK_MILLISECONDS
                    state.ticks_remaining[batch_index, slot] = max(
                        0,
                        (
                            int(state.duration_ms[batch_index, slot].item())
                            + LOGIC_TICK_MILLISECONDS
                            - 1
                        )
                        // LOGIC_TICK_MILLISECONDS
                        - elapsed_ticks,
                    )

    return RuntimeObjectBatch(
        catalog=catalog,
        state=state,
        metadata=tuple(metadata),
        failures=tuple(failures),
        _bindings=tuple(bindings),
    )
