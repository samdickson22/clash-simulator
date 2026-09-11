"""Diagnostic receipts from actual queued scalar spell execution."""

import dis
from dataclasses import dataclass, fields
from types import FunctionType

from clasher.card_aliases import resolve_card_name
from clasher.dynamic_spells import load_dynamic_spells
from clasher.entities import (
    AreaEffect,
    Graveyard,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
)
from clasher.spells import (
    SPELL_REGISTRY,
    AreaEffectSpell,
    DirectDamageSpell,
    GraveyardSpell,
    ProjectileSpell,
    RollingProjectileSpell,
    SpawnProjectileSpell,
    TornadoSpell,
)
from scripts.hog26_scalar_public_effect_adapter import (
    ScalarArrowsAppearance,
    ScalarSpellAppearance,
)


@dataclass(frozen=True)
class ScalarSpellBirthReceipt:
    ordinal: int
    appearances: tuple


class ScalarSpellReceiptRecorder:
    """Wrap selected actual spell instances without replacing queue scheduling.

    Registry spell instances are shared, so calls from other battles delegate
    unchanged and produce no receipts. Overlapping instance instrumentation is
    rejected. All instance attributes are restored even on exceptional exit.
    """

    def __init__(self, battle, card_names, loader, vocabulary):
        self.battle = battle
        self.receipts = []
        self._entered = False
        self._saved = []
        self._registrations = []
        definitions = loader.load_card_definitions()
        serialized_spells = load_dynamic_spells(loader.data_file)
        for card_name in card_names:
            name = resolve_card_name(card_name, definitions)
            spell = SPELL_REGISTRY.get(name)
            expected = serialized_spells[name]
            if (spell is None or type(spell) is not type(expected)
                    or any(getattr(spell, f.name) != getattr(expected, f.name)
                           for f in fields(expected))):
                raise ValueError("registered spell differs from serialized factory")
            rule = (ScalarArrowsAppearance.compile(loader, vocabulary) if card_name == "Arrows"
                    else ScalarSpellAppearance.compile(card_name, loader, vocabulary))
            self._registrations.append((spell, rule))
        if len({id(s) for s, _ in self._registrations}) != len(self._registrations):
            raise ValueError("duplicate spell registration")

    @property
    def appearances(self):
        return tuple(a for receipt in self.receipts for a in receipt.appearances)

    def __enter__(self):
        if self._entered:
            raise RuntimeError("spell receipt recorder cannot be entered twice")
        self._entered = True
        try:
            for spell, rule in self._registrations:
                original = spell.cast
                if getattr(original, "_hog26_spell_receipt_wrapper", False):
                    raise ValueError("spell already has a receipt recorder")
                self._saved.append((spell, "cast" in spell.__dict__, spell.__dict__.get("cast")))
                spell.cast = self._wrapper(original, rule)
        except BaseException:
            self._restore()
            raise
        return self

    def _wrapper(self, original, rule):
        spell = getattr(original, "__self__", None)
        routes = {
            DirectDamageSpell: None,
            ProjectileSpell: Projectile,
            AreaEffectSpell: AreaEffect,
            SpawnProjectileSpell: SpawnProjectile,
            RollingProjectileSpell: RollingProjectile,
            TornadoSpell: AreaEffect,
            GraveyardSpell: Graveyard,
        }
        if (type(spell) not in routes
                or getattr(original, "__func__", None) is not type(spell).cast):
            raise ValueError("spell has an unaudited cast override")
        authority = original.__func__
        constructor = routes[type(spell)]
        if constructor is not None:
            name = constructor.__name__
            uses = [i for i in dis.get_instructions(authority) if i.argval == name]
            if (authority.__globals__.get(name) is not constructor
                    or len(uses) != 1 or uses[0].opname != "LOAD_GLOBAL"
                    or not uses[0].arg & 1):
                raise ValueError("spell primary constructor route changed")

        def cast(battle_state, player_id, target_pos):
            if battle_state is not self.battle:
                return original(battle_state, player_id, target_pos)
            if type(spell).cast is not authority:
                raise ValueError("spell cast authority changed")
            created = []

            def construct(**kwargs):
                expected_id = battle_state.next_entity_id
                if (kwargs.get("id") != expected_id or expected_id in battle_state.entities
                        or kwargs.get("player_id") != player_id):
                    raise ValueError("spell primary birth lost allocator or owner provenance")
                entity = constructor(**kwargs)
                created.append(entity)
                return entity

            # Only the audited cast's direct constructor load is intercepted.
            # Damage callbacks execute their original globals, so their children
            # retain independent ownership even when born during this cast.
            local_globals = dict(authority.__globals__)
            if constructor is not None:
                if local_globals.get(name) is not constructor:
                    raise ValueError("spell primary constructor authority changed")
                local_globals[name] = construct
            local = FunctionType(authority.__code__, local_globals, authority.__name__,
                                 authority.__defaults__, authority.__closure__)
            local.__kwdefaults__ = authority.__kwdefaults__
            result = local(spell, battle_state, player_id, target_pos)
            if any(battle_state.entities.get(e.id) is not e for e in created):
                raise ValueError("spell primary birth was not inserted by its creator")
            if not result and getattr(rule, "entity_type", object) is not None:
                raise ValueError("registered queued spell cast failed")
            appearances = rule.bind_cast(created)
            self.receipts.append(ScalarSpellBirthReceipt(len(self.receipts), appearances))
            return result
        cast._hog26_spell_receipt_wrapper = True
        return cast

    def _restore(self):
        for spell, had_previous, previous in reversed(self._saved):
            if had_previous:
                spell.cast = previous
            else:
                del spell.cast
        self._saved.clear()

    def __exit__(self, exc_type, exc_value, traceback):
        self._restore()
        return False
