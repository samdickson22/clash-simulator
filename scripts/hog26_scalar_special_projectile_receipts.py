"""Creation receipts for Princess combat shots and Firecracker carrier children.

This binds appearance provenance only. Visibility still belongs to the caller.
No global class, module symbol, entity map, or simulator payload is modified.
"""

from __future__ import annotations

import dis
import hashlib
import json
from dataclasses import dataclass
from types import FunctionType, MethodType

from clasher.entities import Projectile, Troop
from scripts.hog26_scalar_public_effect_adapter import ScalarEffectAppearance


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _with_constructor(method, constructor):
    """Run the unchanged local method code with a scoped constructor receipt.

    Constructor interception happens before insertion/start collision, so a
    child's synchronous lethal callback cannot hide or misidentify its birth.
    The global Projectile class remains untouched, including isinstance checks
    and every method subsequently executed by the created real Projectile.
    """
    local_globals = dict(method.__globals__)
    if local_globals.get("Projectile") is not Projectile:
        raise ValueError("creation method has an unknown Projectile constructor")
    uses = [instruction for instruction in dis.get_instructions(method)
            if instruction.argval == "Projectile"]
    # LOAD_GLOBAL's low argument bit supplies NULL for a direct callable load.
    # A type check, alias, assignment, or additional creation site is unaudited.
    if (len(uses) != 1 or uses[0].opname != "LOAD_GLOBAL"
            or not (uses[0].arg & 1)):
        raise ValueError("Projectile must have one direct constructor site")
    local_globals["Projectile"] = constructor
    local = FunctionType(method.__code__, local_globals, method.__name__,
                         method.__defaults__, method.__closure__)
    local.__kwdefaults__ = method.__kwdefaults__
    return local


def _same_method_contract(current, authority, local):
    return (current is authority and current.__code__ is local.__code__
            and current.__defaults__ is local.__defaults__
            and current.__kwdefaults__ is local.__kwdefaults__
            and current.__closure__ is local.__closure__
            and current.__globals__.get("Projectile") is Projectile)


@dataclass(frozen=True)
class ScalarSpecialProjectileDescriptor:
    source_card: str
    token: int
    child_token: int | None
    body_sha256: str
    payload_sha256: str
    child_sha256: str | None

    @classmethod
    def compile(cls, card_name, loader, vocabulary):
        if card_name not in {"Princess", "Firecracker"}:
            raise ValueError("special projectile source is not audited")
        stats = loader.get_card(card_name)
        body = stats._raw_entry.get("summonCharacterData") or {}
        payload = stats.projectile_data
        child = None
        if card_name == "Princess":
            decoration = body.get("projectileData") or {}
            combat = body.get("customFirstProjectileData") or {}
            if (decoration.get("name") != "PrincessProjectileDeco"
                    or decoration.get("damage") is not None
                    or combat.get("name") != "PrincessProjectile"
                    or combat.get("damage") is None or payload != combat):
                raise ValueError("Princess decoration/combat selection changed")
        else:
            child = payload.get("spawnProjectileData") or {}
            if (payload != body.get("projectileData")
                    or payload.get("name") != "FirecrackerProjectile"
                    or payload.get("damage") is not None
                    or child.get("name") != "FirecrackerExplosion"
                    or child.get("spawnCount") != 5
                    or child.get("projectileRange", 0) <= 0
                    or child.get("damage", 0) <= 0
                    or child.get("spawnProjectileData")):
                raise ValueError("Firecracker carrier/child creation route changed")
        token = vocabulary.resolve(payload["name"], "projectile")
        child_token = vocabulary.resolve(child["name"], "projectile") if child else None
        if token <= 1 or (child_token is not None and child_token <= 1):
            raise ValueError("special projectile appearance has no typed token")
        return cls(stats.name, token, child_token, _digest(body), _digest(payload),
                   _digest(child) if child else None)

    def validate_source(self, source):
        if (type(source) is not Troop or source.card_stats is None
                or source.card_stats.name != self.source_card
                or _digest(source.card_stats.projectile_data) != self.payload_sha256
                or _digest(source.card_stats._raw_entry.get("summonCharacterData") or {}) != self.body_sha256
                or bool(getattr(source, "_force_melee_attack", False))):
            raise ValueError("source differs from special creation authority")


@dataclass(frozen=True)
class ScalarSpecialProjectileReceipt:
    ordinal: int
    source_id: int
    projectile_id: int
    route: str
    appearance: ScalarEffectAppearance


class ScalarSpecialProjectileReceiptRecorder:
    """Per-instance creation hooks, restored after normal and exceptional exit.

    Keep the context open through carrier impact. Newly deployed source bodies
    can be explicitly registered with bind_source; unknown bodies and unrelated
    callback births never inherit appearance. Already-created unbound carriers
    are deliberately not adopted by inspecting their runtime names or payload.
    """

    def __init__(self, battle, sources=()):
        self.battle = battle
        self.sources = tuple(sources)
        self.receipts = []
        self._saved = []
        self._bound_sources = set()
        self._entered = False
        self._active = False

    @property
    def appearances(self):
        return tuple(receipt.appearance for receipt in self.receipts)

    def _install(self, entity, name, wrapper):
        self._saved.append((entity, name, name in entity.__dict__, entity.__dict__.get(name)))
        wrapper._hog26_receipt_wrapper = True
        setattr(entity, name, MethodType(wrapper, entity))

    def __enter__(self):
        if self._entered:
            raise RuntimeError("special recorder cannot be entered twice")
        self._entered = self._active = True
        try:
            for source, descriptor in self.sources:
                self.bind_source(source, descriptor)
        except BaseException:
            self._restore()
            raise
        return self

    def bind_source(self, source, descriptor):
        if not self._active:
            raise RuntimeError("source registration requires an active context")
        descriptor.validate_source(source)
        if (self.battle.entities.get(source.id) is not source
                or source.battle_state is not self.battle):
            raise ValueError("source is not owned by this battle")
        if id(source) in self._bound_sources:
            raise ValueError("duplicate special source registration")
        original = source._create_projectile
        if getattr(original, "__func__", None) is not Troop._create_projectile:
            raise ValueError("source already has a hook or an unaudited creation override")

        def construct(**kwargs):
            if (kwargs.get("source_entity") is not source
                    or kwargs.get("player_id") != source.player_id):
                raise ValueError("special parent constructor lost source provenance")
            entity = self._record_constructor(kwargs, source.id, descriptor.token, "attack")
            if descriptor.child_token is not None:
                self._bind_children(entity, source, descriptor)
            return entity

        local = _with_constructor(Troop._create_projectile, construct)
        authority = original.__func__

        def create(bound, target, battle_state, *, target_position=None):
            if bound is not source or battle_state is not self.battle:
                raise ValueError("special creation binding changed")
            if not _same_method_contract(Troop._create_projectile, authority, local):
                raise ValueError("special source constructor authority changed")
            descriptor.validate_source(source)
            start = len(self.receipts)
            result = local(bound, target, battle_state, target_position=target_position)
            self._validate_insertions(start)
            return result

        self._install(source, "_create_projectile", create)
        self._bound_sources.add(id(source))

    def _record_constructor(self, kwargs, source_id, token, route):
        if not self._active:
            raise RuntimeError("creation receipt outside active context")
        expected = self.battle.next_entity_id
        if kwargs.get("id") != expected or expected in self.battle.entities:
            raise ValueError("creation identity differs from allocator boundary")
        entity = Projectile(**kwargs)
        self.receipts.append(ScalarSpecialProjectileReceipt(
            len(self.receipts), source_id, entity.id, route, ScalarEffectAppearance(entity, token)))
        return entity

    def _bind_children(self, parent, source, descriptor):
        original = parent._spawn_impact_projectiles
        if getattr(original, "__func__", None) is not Projectile._spawn_impact_projectiles:
            raise ValueError("parent has an unaudited child creation override")

        def construct(**kwargs):
            if (kwargs.get("card_stats") is not parent.card_stats
                    or kwargs.get("player_id") != parent.player_id):
                raise ValueError("special child constructor lost parent provenance")
            return self._record_constructor(kwargs, parent.id, descriptor.child_token, "impact_child")

        local = _with_constructor(Projectile._spawn_impact_projectiles, construct)
        authority = original.__func__

        def spawn(bound, battle_state):
            if (bound is not parent or battle_state is not self.battle
                    or self.battle.entities.get(parent.id) is not parent
                    or parent.source_entity is not source
                    or _digest(parent.spawn_projectile_data) != descriptor.child_sha256):
                raise ValueError("Firecracker child creation binding changed")
            if not _same_method_contract(Projectile._spawn_impact_projectiles, authority, local):
                raise ValueError("special child constructor authority changed")
            start = len(self.receipts)
            result = local(bound, battle_state)
            self._validate_insertions(start)
            return result

        self._install(parent, "_spawn_impact_projectiles", spawn)

    def _validate_insertions(self, start):
        for receipt in self.receipts[start:]:
            if self.battle.entities.get(receipt.projectile_id) is not receipt.appearance.entity:
                raise ValueError("constructed projectile was not inserted by audited creator")

    def _restore(self):
        for entity, name, had_previous, previous in reversed(self._saved):
            if had_previous:
                setattr(entity, name, previous)
            else:
                entity.__dict__.pop(name, None)
        self._saved.clear()
        self._active = False

    def __exit__(self, exc_type, exc_value, traceback):
        self._restore()
        return False
