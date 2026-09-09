"""Diagnostic Electro Dragon/Spirit birth provenance, without guessed chain assets.

The ordinary Electro Dragon parent has a serialized projectile appearance.
ChainLightning births retain their serialized family only as private provenance.
A separately declared public_effect:chain_bolt category describes a currently
visible travelling effect, without asserting an asset or source-family identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MethodType

from clasher.cards.electro_dragon import ElectroDragonChainLightning
from clasher.cards.electro_spirit import ElectroSpiritChain
from clasher.entities import ChainLightning, Troop
from scripts.hog26_scalar_projectile_receipts import (
    ScalarProjectileReceiptRecorder,
    _payload_digest,
)
from scripts.hog26_scalar_public_effect_adapter import ScalarEffectAppearance


@dataclass(frozen=True)
class ScalarChainSourceDescriptor:
    source_card: str
    token: int  # Serialized family; not an automatically authorized chain appearance.
    body_sha256: str
    projectile_sha256: str
    mechanic_type: type
    hook_name: str
    ordinary_parent: bool

    @classmethod
    def compile(cls, card_name, loader, vocabulary):
        if card_name not in {"ElectroDragon", "ElectroSpirit"}:
            raise ValueError("chain source is not audited")
        stats = loader.get_card(card_name)
        payload = stats.projectile_data or {}
        body = stats._raw_entry.get("summonCharacterData") or {}
        token = vocabulary.resolve(payload.get("name", ""), "projectile")
        expected_links = 3 if card_name == "ElectroDragon" else 9
        if token <= 1 or payload.get("chainedHitCount") != expected_links:
            raise ValueError("serialized chain family differs from audited route")
        dragon = card_name == "ElectroDragon"
        return cls(
            stats.name,
            token,
            _payload_digest(body),
            _payload_digest(payload),
            ElectroDragonChainLightning if dragon else ElectroSpiritChain,
            "on_attack_hit" if dragon else "_land",
            dragon,
        )

    def validate_source(self, source):
        if (
            type(source) is not Troop
            or source.card_stats is None
            or source.card_stats.name != self.source_card
            or _payload_digest(
                source.card_stats._raw_entry.get("summonCharacterData") or {}
            )
            != self.body_sha256
            or _payload_digest(source.card_stats.projectile_data)
            != self.projectile_sha256
            or bool(getattr(source, "_force_melee_attack", False))
            == self.ordinary_parent
            or sum(type(m) is self.mechanic_type for m in source.mechanics) != 1
        ):
            raise ValueError("source differs from compiled chain route")


@dataclass(frozen=True)
class ScalarChainBirthReceipt:
    ordinal: int
    source_id: int
    chain_id: int
    entity: ChainLightning
    serialized_family_token: int


class ScalarChainReceiptRecorder:
    """Per-instance mechanic hooks; ordinary parent registration only for Dragon."""

    def __init__(self, battle, sources):
        self.battle = battle
        self.sources = tuple(sources)
        self.chain_receipts: list[ScalarChainBirthReceipt] = []
        self.parent_recorder = None
        self._saved = []
        self._entered = False

    @property
    def parent_appearances(self):
        return () if self.parent_recorder is None else self.parent_recorder.appearances

    def chain_appearances(self, *, category_name, category_token, visible_to):
        """Bind visible current chain objects to an explicit outcome category.

        Setup owns the token assignment. Call the public projector with the
        same current ``visible_to(entity, seat)`` predicate; this binding is not
        permission to bypass its seat mask. Dead/hidden objects yield no binding.
        Serialized family tokens and all origin/target/hop payloads are excluded.
        """
        if category_name != "public_effect:chain_bolt":
            raise ValueError("chain appearance requires its explicit public category")
        if type(category_token) is not int or category_token < 494:
            raise ValueError("chain category must use a declared outcome-only token")
        if not callable(visible_to):
            raise TypeError("chain appearance requires explicit current visibility")
        return tuple(
            ScalarEffectAppearance(receipt.entity, category_token, ChainLightning, 2)
            for receipt in self.chain_receipts
            if receipt.entity.is_alive
            and any(bool(visible_to(receipt.entity, seat)) for seat in (0, 1))
        )

    def __enter__(self):
        if self._entered:
            raise RuntimeError("chain recorder cannot be entered twice")
        self._entered = True
        if len({id(source) for source, _ in self.sources}) != len(self.sources):
            raise ValueError("duplicate chain source")
        try:
            for source, descriptor in self.sources:
                descriptor.validate_source(source)
                if (
                    self.battle.entities.get(source.id) is not source
                    or source.battle_state is not self.battle
                ):
                    raise ValueError("chain source is not owned by battle")
                mechanic = next(
                    m for m in source.mechanics if type(m) is descriptor.mechanic_type
                )
                name = descriptor.hook_name
                original = getattr(mechanic, name)
                if getattr(
                    getattr(original, "__func__", None), "_hog26_chain_wrapper", False
                ):
                    raise ValueError("mechanic already has a chain recorder")
                self._saved.append(
                    (
                        mechanic,
                        name,
                        name in mechanic.__dict__,
                        mechanic.__dict__.get(name),
                    )
                )
                setattr(
                    mechanic,
                    name,
                    MethodType(self._wrapper(source, descriptor, original), mechanic),
                )
            parents = [(s, d) for s, d in self.sources if d.ordinary_parent]
            self.parent_recorder = ScalarProjectileReceiptRecorder(self.battle, parents)
            self.parent_recorder.__enter__()
        except BaseException:
            self._restore()
            raise
        return self

    def _wrapper(self, source, descriptor, original):
        def emit(bound_mechanic, entity, target):
            if entity is not source or source.battle_state is not self.battle:
                raise ValueError("chain hook source binding changed")
            descriptor.validate_source(source)
            expected = self.battle.next_entity_id
            if expected in self.battle.entities:
                raise ValueError("next chain identity is occupied")
            result = original(entity, target)
            chain = self.battle.entities.get(expected)
            if (
                type(chain) is not ChainLightning
                or chain.player_id != source.player_id
                or chain.card_stats is not source.card_stats
                or self.battle.next_entity_id <= expected
            ):
                raise ValueError("hook did not emit the expected chain object")
            self.chain_receipts.append(
                ScalarChainBirthReceipt(
                    len(self.chain_receipts),
                    source.id,
                    expected,
                    chain,
                    descriptor.token,
                )
            )
            return result

        emit._hog26_chain_wrapper = True
        return emit

    def _restore(self):
        if self.parent_recorder is not None:
            self.parent_recorder._restore()
        for mechanic, name, existed, previous in reversed(self._saved):
            if existed:
                setattr(mechanic, name, previous)
            else:
                mechanic.__dict__.pop(name, None)
        self._saved.clear()

    def __exit__(self, exc_type, exc_value, traceback):
        self._restore()
        return False
