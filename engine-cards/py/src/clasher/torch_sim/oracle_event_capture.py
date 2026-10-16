"""Verifier-only capture of events at the Python oracle's actual call sites.

Unlike an end-state delta reconstruction, this adapter observes allocation,
damage, death, and status calls while the scalar simulator executes them.  It
temporarily installs an observable entity dictionary and scoped method wrappers
and restores every production object on exit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from enum import IntEnum
from types import MethodType
from typing import Any, TypeVar
from unittest.mock import patch

from typing_extensions import Self

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.cards.miner import UndergroundDeployment
from clasher.entities import (
    AreaEffect,
    Building,
    Entity,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
    TimedExplosive,
    Troop,
)
from clasher.spells import SPELL_REGISTRY

from .runtime_state import RuntimeEventOpcode, TickPhase

_T = TypeVar("_T")


class OraclePayloadKind(IntEnum):
    """Data-bearing scalar operation that produced an event."""

    NONE = 0
    COMMAND_DEPLOYMENT = 1
    COMBAT_PROJECTILE = 2
    SPELL_EXECUTION = 3
    SPELL_PROJECTILE = 4
    SPELL_AREA = 5
    OBJECT_PROJECTILE = 6
    OBJECT_CHARACTER = 7
    DAMAGE = 8
    DEATH = 9
    STUN = 10
    SLOW = 11
    PROJECTILE_IMPACT = 12
    UNDERGROUND_MOVEMENT = 13


@dataclass(frozen=True)
class OracleEventRecord:
    tick: int
    phase: int
    opcode: int
    sequence: int
    source_id: int
    target_id: int
    x_units: int
    y_units: int
    amount: object
    amount_kind: str
    payload_kind: int
    payload: object
    payload_scalar_kind: str


def _logic_units(value: float) -> int:
    return round(float(value) * 1_000)


class _CaptureEntityDict(dict[int, Entity]):
    def __init__(
        self, source: dict[int, Entity], capture: PythonOracleEventCapture
    ) -> None:
        super().__init__(source)
        self.capture = capture

    def __setitem__(self, key: int, value: Entity) -> None:
        created = key not in self
        super().__setitem__(key, value)
        if created:
            self.capture._capture_allocation(value)


class PythonOracleEventCapture:
    """Capture exact scalar events without changing simulator source/state."""

    def __init__(self, battle: BattleState) -> None:
        self.battle = battle
        self.events: list[OracleEventRecord] = []
        self._phase = TickPhase.COMMANDS
        self._source_id = 0
        self._source_payload: object = None
        self._stack: ExitStack | None = None
        self._original_entities: dict[int, Entity] | None = None
        self._spell_cast_state: list[tuple[Any, bool, object | None]] = []

    def __enter__(self) -> Self:
        if self._stack is not None:
            raise RuntimeError("oracle event capture is already active")
        self._original_entities = self.battle.entities
        self.battle.entities = _CaptureEntityDict(self.battle.entities, self)
        stack = ExitStack()
        self._stack = stack
        self._install_phase_wrappers(stack)
        self._install_payload_wrappers(stack)
        self._install_spell_wrappers()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            self._restore_spell_wrappers()
            if self._stack is not None:
                self._stack.close()
        finally:
            if self._original_entities is not None:
                self._original_entities.clear()
                self._original_entities.update(self.battle.entities)
                self.battle.entities = self._original_entities
            self._original_entities = None
            self._stack = None

    @contextmanager
    def _scope(
        self,
        *,
        phase: TickPhase | None = None,
        source_id: int | None = None,
        source_payload: object = None,
    ) -> Iterator[None]:
        previous = (self._phase, self._source_id, self._source_payload)
        if phase is not None:
            self._phase = phase
        if source_id is not None:
            self._source_id = int(source_id)
        if source_payload is not None:
            self._source_payload = source_payload
        try:
            yield
        finally:
            self._phase, self._source_id, self._source_payload = previous

    def command(self, operation: Callable[[], _T]) -> _T:
        """Run one scalar command while preserving its allocation identity."""

        with self._scope(phase=TickPhase.COMMANDS):
            return operation()

    def deploy_card(self, player_id: int, card_name: str, position: Position) -> bool:
        return self.command(
            lambda: self.battle.deploy_card(player_id, card_name, position)
        )

    def step_logic_ticks(self, ticks: int = 1) -> tuple[OracleEventRecord, ...]:
        start = len(self.events)
        self.battle.step_logic_ticks(ticks)
        return tuple(self.events[start:])

    def _record(
        self,
        opcode: RuntimeEventOpcode,
        *,
        source_id: int = 0,
        target_id: int = 0,
        x_units: int = 0,
        y_units: int = 0,
        amount: object = 0,
        payload_kind: OraclePayloadKind = OraclePayloadKind.NONE,
        payload: object = None,
    ) -> None:
        self.events.append(
            OracleEventRecord(
                tick=int(self.battle.tick),
                phase=int(self._phase),
                opcode=int(opcode),
                sequence=len(self.events),
                source_id=int(source_id),
                target_id=int(target_id),
                x_units=int(x_units),
                y_units=int(y_units),
                amount=amount,
                amount_kind=type(amount).__name__,
                payload_kind=int(payload_kind),
                payload=payload,
                payload_scalar_kind=type(payload).__name__,
            )
        )

    def _capture_allocation(self, entity: Entity) -> None:
        x = _logic_units(entity.position.x)
        y = _logic_units(entity.position.y)
        payload = self._source_payload
        if payload is None:
            payload = getattr(getattr(entity, "card_stats", None), "name", None)
            if payload is None:
                payload = getattr(entity, "spell_name", None)
        if self._phase == TickPhase.COMMANDS and isinstance(entity, (Troop, Building)):
            self._record(
                RuntimeEventOpcode.SPAWN,
                source_id=entity.id,
                x_units=x,
                y_units=y,
                payload_kind=OraclePayloadKind.COMMAND_DEPLOYMENT,
                payload=payload,
            )
            if getattr(entity, "_underground_deployment", False):
                with self._scope(phase=TickPhase.MOVEMENT, source_id=entity.id):
                    self._record(
                        RuntimeEventOpcode.MOVEMENT,
                        source_id=entity.id,
                        x_units=x,
                        y_units=y,
                        payload_kind=OraclePayloadKind.UNDERGROUND_MOVEMENT,
                        payload=payload,
                    )
            return
        if isinstance(entity, AreaEffect):
            kind = OraclePayloadKind.SPELL_AREA
            opcode = RuntimeEventOpcode.AREA
        elif isinstance(entity, Projectile):
            opcode = RuntimeEventOpcode.PROJECTILE
            if self._phase == TickPhase.COMBAT:
                kind = OraclePayloadKind.COMBAT_PROJECTILE
            elif self._phase == TickPhase.COMMANDS:
                kind = OraclePayloadKind.SPELL_PROJECTILE
            else:
                kind = OraclePayloadKind.OBJECT_PROJECTILE
        else:
            kind = OraclePayloadKind.OBJECT_CHARACTER
            opcode = RuntimeEventOpcode.SPAWN
        self._record(
            opcode,
            source_id=self._source_id,
            target_id=entity.id,
            x_units=x,
            y_units=y,
            payload_kind=kind,
            payload=payload,
        )

    def _install_phase_wrappers(self, stack: ExitStack) -> None:
        capture = self

        def wrap_phase(cls: type[Any], name: str, phase: TickPhase) -> None:
            original = getattr(cls, name)

            def wrapped(instance: Any, *args: object, **kwargs: object) -> object:
                if (
                    instance is capture.battle
                    or getattr(instance, "battle_state", None) is capture.battle
                ):
                    source = instance.id if isinstance(instance, Entity) else None
                    with capture._scope(phase=phase, source_id=source):
                        return original(instance, *args, **kwargs)
                return original(instance, *args, **kwargs)

            stack.enter_context(patch.object(cls, name, wrapped))

        wrap_phase(BattleState, "_resolve_pending_spell_casts", TickPhase.COMMANDS)
        wrap_phase(Troop, "update_combat_component", TickPhase.COMBAT)
        wrap_phase(Building, "update_combat_component", TickPhase.COMBAT)
        original_lifetime = Building.update_hitpoint_component

        def building_lifetime(building: Building, dt: float) -> None:
            if getattr(building, "battle_state", None) is not capture.battle:
                original_lifetime(building, dt)
                return
            before_hp = building.hitpoints
            before_alive = building.is_alive
            with capture._scope(
                phase=TickPhase.BUILDING_LIFETIME,
                source_id=0,
            ):
                original_lifetime(building, dt)
                if building.hitpoints < before_hp:
                    capture._record(
                        RuntimeEventOpcode.DAMAGE,
                        target_id=building.id,
                        x_units=_logic_units(building.position.x),
                        y_units=_logic_units(building.position.y),
                        amount=before_hp - building.hitpoints,
                        payload_kind=OraclePayloadKind.DAMAGE,
                    )
                if before_alive and not building.is_alive:
                    capture._record(
                        RuntimeEventOpcode.DEATH,
                        target_id=building.id,
                        x_units=_logic_units(building.position.x),
                        y_units=_logic_units(building.position.y),
                        payload_kind=OraclePayloadKind.DEATH,
                    )

        stack.enter_context(
            patch.object(Building, "update_hitpoint_component", building_lifetime)
        )
        wrap_phase(Entity, "update_status_effects", TickPhase.STATUS)
        wrap_phase(BattleState, "_run_object_phase", TickPhase.OBJECTS)
        wrap_phase(BattleState, "_cleanup_dead_entities", TickPhase.CLEANUP_AND_SPAWNS)

    def _install_payload_wrappers(self, stack: ExitStack) -> None:
        capture = self
        original_underground_tick = UndergroundDeployment.on_deploy_tick

        def underground_tick(
            mechanic: UndergroundDeployment,
            entity: Entity,
            dt_ms: int,
        ) -> None:
            destination = getattr(entity, "_underground_destination", None)
            before = (_logic_units(entity.position.x), _logic_units(entity.position.y))
            original_underground_tick(mechanic, entity, dt_ms)
            if (
                getattr(entity, "battle_state", None) is capture.battle
                and destination is not None
                and before != (_logic_units(destination.x), _logic_units(destination.y))
                and (_logic_units(entity.position.x), _logic_units(entity.position.y))
                == (_logic_units(destination.x), _logic_units(destination.y))
            ):
                payload = getattr(getattr(entity, "card_stats", None), "name", None)
                with capture._scope(
                    phase=TickPhase.MOVEMENT,
                    source_id=entity.id,
                    source_payload=payload,
                ):
                    capture._record(
                        RuntimeEventOpcode.MOVEMENT,
                        source_id=entity.id,
                        x_units=_logic_units(entity.position.x),
                        y_units=_logic_units(entity.position.y),
                        payload_kind=OraclePayloadKind.UNDERGROUND_MOVEMENT,
                        payload=payload,
                    )

        stack.enter_context(
            patch.object(UndergroundDeployment, "on_deploy_tick", underground_tick)
        )
        original_damage = Entity.take_damage
        original_damage_any: Any = original_damage

        def take_damage(entity: Entity, *args: object, **kwargs: object) -> None:
            before_hp = entity.hitpoints
            before_alive = entity.is_alive
            original_damage_any(entity, *args, **kwargs)
            if getattr(entity, "battle_state", None) is not capture.battle:
                return
            if entity.hitpoints < before_hp:
                amount = before_hp - entity.hitpoints
                capture._record(
                    RuntimeEventOpcode.DAMAGE,
                    source_id=capture._source_id,
                    target_id=entity.id,
                    x_units=_logic_units(entity.position.x),
                    y_units=_logic_units(entity.position.y),
                    amount=amount,
                    payload_kind=OraclePayloadKind.DAMAGE,
                    payload=capture._source_payload,
                )
            if before_alive and not entity.is_alive:
                capture._record(
                    RuntimeEventOpcode.DEATH,
                    source_id=capture._source_id,
                    target_id=entity.id,
                    x_units=_logic_units(entity.position.x),
                    y_units=_logic_units(entity.position.y),
                    payload_kind=OraclePayloadKind.DEATH,
                    payload=capture._source_payload,
                )

        stack.enter_context(patch.object(Entity, "take_damage", take_damage))

        for method_name, payload_kind in (
            ("apply_stun", OraclePayloadKind.STUN),
            ("apply_slow", OraclePayloadKind.SLOW),
        ):
            original = getattr(Entity, method_name)

            def status(
                entity: Entity,
                *args: object,
                _original: Callable[..., None] = original,
                _kind: OraclePayloadKind = payload_kind,
                **kwargs: object,
            ) -> None:
                before = (
                    entity.stun_timer
                    if _kind == OraclePayloadKind.STUN
                    else tuple(entity._slow_effects)
                )
                _original(entity, *args, **kwargs)
                after = (
                    entity.stun_timer
                    if _kind == OraclePayloadKind.STUN
                    else tuple(entity._slow_effects)
                )
                if (
                    getattr(entity, "battle_state", None) is capture.battle
                    and after != before
                ):
                    amount = (
                        args[0] if args and isinstance(args[0], (int, float)) else 0
                    )
                    capture._record(
                        RuntimeEventOpcode.STATUS,
                        source_id=capture._source_id,
                        target_id=entity.id,
                        x_units=_logic_units(entity.position.x),
                        y_units=_logic_units(entity.position.y),
                        amount=amount,
                        payload_kind=_kind,
                        payload=capture._source_payload,
                    )

            stack.enter_context(patch.object(Entity, method_name, status))

        def wrap_source(cls: type[Any], method_name: str) -> None:
            original = getattr(cls, method_name)

            def sourced(entity: Entity, *args: object, **kwargs: object) -> object:
                if getattr(entity, "battle_state", None) is capture.battle or (
                    args and args[-1] is capture.battle
                ):
                    payload = getattr(
                        getattr(entity, "card_stats", None), "name", None
                    ) or getattr(entity, "spell_name", None)
                    with capture._scope(source_id=entity.id, source_payload=payload):
                        return original(entity, *args, **kwargs)
                return original(entity, *args, **kwargs)

            stack.enter_context(patch.object(cls, method_name, sourced))

        wrap_source(Entity, "_resolve_attack_damage")
        wrap_source(Projectile, "_damage_target")

        def wrap_impact(method_name: str) -> None:
            original = getattr(Projectile, method_name)

            def impact(
                projectile: Projectile, *args: object, **kwargs: object
            ) -> object:
                battle = next(
                    (value for value in args if isinstance(value, BattleState)),
                    None,
                )
                if battle is not capture.battle:
                    return original(projectile, *args, **kwargs)
                payload = getattr(
                    getattr(projectile, "card_stats", None), "name", None
                ) or getattr(projectile, "spell_name", None)
                target_id = 0
                if method_name == "_resolve_impact" and len(args) >= 2:
                    candidates = args[1]
                    if isinstance(candidates, (list, tuple)) and candidates:
                        target_id = int(candidates[0].id)
                with capture._scope(
                    phase=TickPhase.OBJECTS,
                    source_id=projectile.id,
                    source_payload=payload,
                ):
                    capture._record(
                        RuntimeEventOpcode.PROJECTILE,
                        source_id=projectile.id,
                        target_id=target_id,
                        x_units=_logic_units(projectile.target_position.x),
                        y_units=_logic_units(projectile.target_position.y),
                        payload_kind=OraclePayloadKind.PROJECTILE_IMPACT,
                        payload=payload,
                    )
                    return original(projectile, *args, **kwargs)

            stack.enter_context(patch.object(Projectile, method_name, impact))

        wrap_impact("_resolve_impact")
        wrap_impact("_deal_splash_damage")
        for cls in (
            Projectile,
            SpawnProjectile,
            RollingProjectile,
            AreaEffect,
            TimedExplosive,
        ):
            wrap_source(cls, "update")

    def _install_spell_wrappers(self) -> None:
        seen: set[int] = set()
        for spell in SPELL_REGISTRY.values():
            if id(spell) in seen:
                continue
            seen.add(id(spell))
            had_own = "cast" in vars(spell)
            own_value = vars(spell).get("cast")
            bound = spell.cast

            def spell_cast(
                _spell: object,
                battle: BattleState,
                player_id: int,
                target: Position,
                *,
                _bound: Callable[[BattleState, int, Position], bool] = bound,
                _capture: PythonOracleEventCapture = self,
            ) -> bool:
                if battle is not _capture.battle:
                    return _bound(battle, player_id, target)
                name = getattr(_spell, "name", type(_spell).__name__)
                with _capture._scope(
                    phase=TickPhase.COMMANDS,
                    source_id=0,
                    source_payload=name,
                ):
                    _capture._record(
                        RuntimeEventOpcode.COMMAND,
                        x_units=_logic_units(target.x),
                        y_units=_logic_units(target.y),
                        payload_kind=OraclePayloadKind.SPELL_EXECUTION,
                        payload=name,
                    )
                    return _bound(battle, player_id, target)

            self._spell_cast_state.append((spell, had_own, own_value))
            vars(spell)["cast"] = MethodType(spell_cast, spell)

    def _restore_spell_wrappers(self) -> None:
        for spell, had_own, own_value in reversed(self._spell_cast_state):
            if had_own:
                vars(spell)["cast"] = own_value
            else:
                vars(spell).pop("cast", None)
        self._spell_cast_state.clear()


__all__ = [
    "OracleEventRecord",
    "OraclePayloadKind",
    "PythonOracleEventCapture",
]
