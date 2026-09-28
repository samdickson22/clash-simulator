"""Royal Delivery scheduler/recruit receipts; no modeled visible flight."""

from dataclasses import dataclass, fields
from types import MethodType

from clasher.dynamic_spells import load_dynamic_spells
from clasher.entities import SpawnProjectile, Troop
from clasher.spells import SPELL_REGISTRY, RoyalDeliverySpell
from scripts.hog26_scalar_projectile_receipts import _payload_digest


@dataclass(frozen=True)
class RoyalDeliveryRecruitReceipt:
    entity: Troop
    token: int


class ScalarRoyalDeliveryRecorder:
    """Observe actual cast/spawn hooks without replacing queue or impact order.

    Scalar RoyalDelivery creates a stationary target-position SpawnProjectile,
    waits activation_delay, then impacts and spawns a recruit in one update.
    It does not model a visible falling trajectory. Registered scheduler objects
    may be excluded by exact reference only; this is incomplete visual coverage.
    """

    def __init__(self, battle, loader, vocabulary):
        self.battle = battle
        self.spell = SPELL_REGISTRY["RoyalDelivery"]
        self.expected = load_dynamic_spells(loader.data_file)["RoyalDelivery"]
        if type(self.expected) is not RoyalDeliverySpell:
            raise ValueError("RoyalDelivery factory lifecycle changed")
        raw = loader.get_card("RoyalDelivery")._raw_entry
        payload = raw["areaEffectObjectData"]["projectileData"]["spawnCharacterData"]
        self.body_identity = payload["name"]
        self.body_payload_digest = _payload_digest(payload)
        self.body_token = vocabulary.resolve(self.body_identity, "troop_body")
        if self.body_token <= 1:
            raise ValueError("RoyalDelivery recruit lacks typed current body identity")
        self.recruits = []
        self._containers = []
        self._saved = []
        self._entered = False

    @property
    def registered_internal_containers(self):
        return tuple(self._containers)

    @property
    def appearances(self):
        """There is no scalar visible-flight appearance receipt."""
        return ()

    def _validate_spell(self):
        if (type(self.spell) is not type(self.expected)
                or any(getattr(self.spell, f.name) != getattr(self.expected, f.name)
                       for f in fields(self.expected))):
            raise ValueError("RoyalDelivery serialized spell authority changed")

    def _patch(self, obj, name, function, *, method=True):
        original = getattr(obj, name)
        if getattr(getattr(original, "__func__", original), "_royal_delivery_receipt", False):
            raise ValueError("RoyalDelivery hook already instrumented")
        self._saved.append((obj, name, name in vars(obj), vars(obj).get(name)))
        function._royal_delivery_receipt = True
        setattr(obj, name, MethodType(function, obj) if method else function)

    def __enter__(self):
        if self._entered:
            raise RuntimeError("RoyalDelivery recorder cannot be entered twice")
        self._entered = True
        try:
            self._validate_spell()
            original = self.spell.cast
            def cast(battle, owner, position):
                if battle is not self.battle:
                    return original(battle, owner, position)
                self._validate_spell()
                before = set(battle.entities)
                result = original(battle, owner, position)
                born = [e for key, e in battle.entities.items() if key not in before]
                if len(born) != 1 or type(born[0]) is not SpawnProjectile:
                    raise ValueError("RoyalDelivery cast creation topology changed")
                self._register(born[0])
                return result
            self._patch(self.spell, "cast", cast, method=False)
        except BaseException:
            self._restore()
            raise
        return self

    def _validate_container(self, entity):
        if (type(entity) is not SpawnProjectile
                or _payload_digest(entity.spawn_character_data) != self.body_payload_digest
                or entity.spawn_character != self.body_identity or entity.spawn_count != 1
                or entity.position.x != entity.target_position.x
                or entity.position.y != entity.target_position.y
                or entity.activation_delay != self.expected.impact_delay):
            raise ValueError("RoyalDelivery stationary scheduler authority changed")

    def _register(self, container):
        self._validate_container(container)
        self._containers.append(container)
        original_update, original_spawn = container.update, container._spawn_units
        def update(entity, dt, battle):
            if battle is not self.battle:
                raise ValueError("RoyalDelivery scheduler battle changed")
            self._validate_container(entity)
            return original_update(dt, battle)
        def spawn(entity, battle):
            if battle is not self.battle:
                raise ValueError("RoyalDelivery recruit battle changed")
            self._validate_container(entity)
            before = set(battle.entities)
            result = original_spawn(battle)
            born = [e for key, e in battle.entities.items() if key not in before]
            if (len(born) != 1 or type(born[0]) is not Troop
                    or born[0].card_stats.name != self.body_identity):
                raise ValueError("RoyalDelivery recruit creation topology changed")
            self.recruits.append(RoyalDeliveryRecruitReceipt(born[0], self.body_token))
            return result
        self._patch(container, "update", update)
        self._patch(container, "_spawn_units", spawn)

    def current_recruit_rows(self, *, visible_to):
        """Only already-born currently visible recruit identities/positions/owners."""
        return tuple(tuple((r.token, r.entity.position.x, r.entity.position.y, r.entity.player_id)
                           for r in self.recruits if r.entity.is_alive and visible_to(r.entity, seat))
                     for seat in (0, 1))

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
