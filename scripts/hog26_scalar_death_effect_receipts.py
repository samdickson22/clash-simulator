"""Diagnostic death appearances; internal queues and missing identities stay separate."""

import hashlib
import json
from dataclasses import dataclass
from types import MethodType

from clasher.entities import (
    AreaEffect,
    BuffAreaEffect,
    DeathAreaEffectContainer,
    TimedExplosive,
)
from clasher.mechanics.shared.death_area import DeathAreaEffect, _first_action_spawn
from clasher.mechanics.shared.death_effects import DeathSpawn


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class DeathAppearanceRule:
    entity_type: type
    token: int
    category: str
    payload_digest: str
    mechanic_type: type
    delayed_payload_digest: str | None = None
    source_identity: str = ""

    @classmethod
    def compile(cls, card, source, loader, vocabulary, *, extra_tokens=None):
        if card not in {"Balloon", "BombTower", "SkeletonBarrel", "IceGolem", "Lumberjack"}:
            raise ValueError("death family is not audited")
        if source.card_stats.name != loader.get_card(card).name:
            raise ValueError("source differs from setup card identity")
        mechanic_type = DeathSpawn if card in {"Balloon", "BombTower", "SkeletonBarrel"} else DeathAreaEffect
        mechanics = [m for m in source.mechanics if type(m) is mechanic_type]
        if len(mechanics) != 1:
            raise ValueError("death mechanic topology differs from audited route")
        mechanic = mechanics[0]
        payload = mechanic.unit_data if mechanic_type is DeathSpawn else mechanic.area_data
        serialized = loader.get_card(card)._raw_entry.get("summonCharacterData", {})
        expected_payload = serialized.get(
            "deathSpawnCharacterData" if mechanic_type is DeathSpawn else "deathAreaEffectData"
        )
        if not isinstance(expected_payload, dict) or _digest(payload) != _digest(expected_payload):
            raise ValueError("death mechanic differs from serialized source payload")
        delayed_payload_digest = None
        if mechanic_type is DeathSpawn:
            if mechanic.count != 1 or not payload.get("deathDamage") or payload.get("hitpoints"):
                raise ValueError("death object is not a single timed payload")
            name, namespace, kind = payload.get("name"), "building_body", "death_body"
            entity_type = TimedExplosive
        else:
            nested = _first_action_spawn(payload.get("onStartingActionData"))
            visual = nested["deathAreaEffectData"] if nested else payload
            if nested:
                delayed_payload_digest = _digest(visual)
            name, namespace, kind = visual.get("name"), "area_effect", "area"
            entity_type = BuffAreaEffect if card == "Lumberjack" else AreaEffect
        token = vocabulary.resolve(name, namespace) if name else 0
        # SkeletonContainerNew has no token. Retain an unresolved diagnostic
        # receipt, never substitute its future explosion or spawned Skeletons.
        if extra_tokens is not None:
            if set(extra_tokens) - {"building_body:SkeletonContainerNew"}:
                raise ValueError("extra death identity is not audited")
            for extra_token in extra_tokens.values():
                if (type(extra_token) is not int
                        or extra_token < len(vocabulary.token_names)):
                    raise ValueError("extra death token collides with frozen vocabulary")
            key = f"{namespace}:{name}"
            if token <= 1 and key == "building_body:SkeletonContainerNew":
                token = extra_tokens.get(key, 0)
        if token <= 1:
            token = 0
        return cls(entity_type, token, kind, _digest(payload), mechanic_type,
                   delayed_payload_digest, source.card_stats.name)


@dataclass(frozen=True)
class DeathAppearanceReceipt:
    entity: object
    rule: DeathAppearanceRule
    witnessed_seats: tuple[bool, bool]


class ScalarDeathEffectRecorder:
    """Per-mechanic and per-container wrapping of actual scalar lifecycle calls."""

    def __init__(self, battle, sources, *, witnessed_visible_to):
        self.battle = battle
        self.sources = tuple(sources)
        self.witnessed_visible_to = witnessed_visible_to
        self.receipts = []
        self.internal_containers = []
        self._saved = []
        self._entered = False

    @property
    def registered_internal_containers(self):
        """Exact observed scheduler references, not a class-wide exclusion.

        This says nothing about an unmodeled pre-buff bottle animation.
        """
        return tuple(self.internal_containers)

    def _wrap(self, obj, name, wrapper):
        original = getattr(obj, name)
        if getattr(getattr(original, "__func__", original), "_death_receipt_wrapper", False):
            raise ValueError("death lifecycle already instrumented")
        self._saved.append((obj, name, name in vars(obj), vars(obj).get(name)))
        wrapper._death_receipt_wrapper = True
        setattr(obj, name, MethodType(wrapper, obj))

    def __enter__(self):
        if self._entered:
            raise RuntimeError("death recorder cannot be entered twice")
        self._entered = True
        try:
            for source, rule in self.sources:
                if self.battle.entities.get(source.id) is not source:
                    raise ValueError("death source is not owned by battle")
                mechanic = next(m for m in source.mechanics if type(m) is rule.mechanic_type)
                payload = mechanic.unit_data if type(mechanic) is DeathSpawn else mechanic.area_data
                if _digest(payload) != rule.payload_digest:
                    raise ValueError("death serialized payload changed")
                self._wrap(mechanic, "on_death", self._death_wrapper(source, mechanic.on_death, rule))
        except BaseException:
            self._restore()
            raise
        return self

    def _death_wrapper(self, source, original, rule):
        def death(mechanic, entity):
            if entity is not source or entity.battle_state is not self.battle:
                raise ValueError("death source binding changed")
            if getattr(source.card_stats, "name", None) != rule.source_identity:
                raise ValueError("death source identity changed before emission")
            payload = mechanic.unit_data if type(mechanic) is DeathSpawn else mechanic.area_data
            if type(mechanic) is DeathSpawn and (
                mechanic.count != 1 or mechanic.unit_name != payload.get("name")
            ):
                raise ValueError("death creation topology changed before emission")
            if type(mechanic) is not rule.mechanic_type or _digest(payload) != rule.payload_digest:
                raise ValueError("death serialized payload changed before emission")
            witness = tuple(bool(self.witnessed_visible_to(source, seat)) for seat in (0, 1))
            before = set(self.battle.entities)
            result = original(entity)
            born = [e for key, e in self.battle.entities.items() if key not in before]
            if len(born) != 1:
                raise ValueError("death receipt has unresolved creation topology")
            self._register(born[0], rule, witness)
            return result
        return death

    def _register(self, entity, rule, witness):
        if type(entity) is DeathAreaEffectContainer:
            if (rule.delayed_payload_digest is None
                    or _digest(entity.area_data) != rule.delayed_payload_digest):
                raise ValueError("death container payload differs from compiled authority")
            self.internal_containers.append(entity)
            original = entity.update
            def update(container, dt, battle):
                if battle is not self.battle:
                    raise ValueError("death container battle changed")
                if _digest(container.area_data) != rule.delayed_payload_digest:
                    raise ValueError("death container payload changed before emission")
                before = set(battle.entities)
                result = original(dt, battle)
                born = [e for key, e in battle.entities.items() if key not in before]
                if born:
                    if len(born) != 1:
                        raise ValueError("death container created unresolved objects")
                    self._register(born[0], rule, witness)
                return result
            self._wrap(entity, "update", update)
        elif type(entity) is rule.entity_type:
            self.receipts.append(DeathAppearanceReceipt(entity, rule, witness))
        else:
            raise ValueError("death object differs from compiled lifecycle")

    def _restore(self):
        for obj, name, existed, previous in reversed(self._saved):
            if existed:
                setattr(obj, name, previous)
            else:
                vars(obj).pop(name, None)
        self._saved.clear()

    def __exit__(self, *exc):
        self._restore()
        return False


def project_current_death_appearances(receipts, *, visible_to):
    """Current appearance records per seat; no combat or future metadata.

    Category death_body means the serialized bomb body, not an area explosion.
    Both witnessed source visibility and explicit current visibility are needed.
    Internal death containers are never represented by these receipts.
    """
    seats = ([], [])
    for receipt in receipts:
        entity = receipt.entity
        if not entity.is_alive:
            continue
        for seat in (0, 1):
            if not receipt.witnessed_seats[seat] or not visible_to(entity, seat):
                continue
            if receipt.rule.token <= 1:
                raise ValueError("current death appearance has no frozen vocabulary identity")
            x, y = entity.position.x / 18, entity.position.y / 32
            if seat == 1:
                x, y = 1 - x, 1 - y
            seats[seat].append((receipt.rule.token, receipt.rule.category, x, y,
                                entity.player_id == seat))
    return tuple(tuple(rows) for rows in seats)
