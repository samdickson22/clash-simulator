"""Diagnostic receipts from actual queued scalar spell execution."""

from dataclasses import dataclass, fields

from clasher.card_aliases import resolve_card_name
from clasher.dynamic_spells import load_dynamic_spells
from clasher.spells import SPELL_REGISTRY
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
        def cast(battle_state, player_id, target_pos):
            if battle_state is not self.battle:
                return original(battle_state, player_id, target_pos)
            before = set(battle_state.entities)
            result = original(battle_state, player_id, target_pos)
            created = tuple(entity for key, entity in battle_state.entities.items()
                            if key not in before)
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
