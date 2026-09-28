"""Diagnostic birth receipts for setup-audited ordinary scalar projectiles.

Registration establishes creation provenance, never visibility. Unknown child
objects and tower projectiles remain unbound. No global class is patched.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MethodType

from clasher.entities import Building, Projectile, Troop
from clasher.factory.dynamic_factory import troop_from_character_data
from scripts.hog26_scalar_public_effect_adapter import ScalarEffectAppearance


def _payload_digest(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


_COMMON_ROOTS = frozenset(
    {
        "Musketeer",
        "ArcherQueen",
        "Cannon",
        "Archers",
        "BabyDragon",
        "DartGoblin",
        "BombTower",
        "Bomber",
        "IceWizard",
        "LavaHound",
        "MegaMinion",
        "Minions",
        "SpearGoblins",
        "Witch",
        "Xbow",
    }
)
_EXTRA_SPAWN_ROUTES = (
    ("LavaHound", ("summonCharacterData", "deathSpawnCharacterData")),
    ("GoblinGang", ("summonCharacterSecondData",)),
    ("IceWizard", ("areaEffectObjectData", "onStartingActionData", "spawnDataData")),
)


@dataclass(frozen=True)
class ScalarOrdinaryProjectileDescriptor:
    source_card: str
    source_type: type
    token: int
    projectile_payload_sha256: str
    source_body_sha256: str
    source_authority: str

    @classmethod
    def compile(cls, card_name, loader, vocabulary):
        if card_name not in _COMMON_ROOTS:
            raise ValueError("ordinary appearance source is not audited")
        stats = loader.get_card(card_name)
        source_type = (
            Building if card_name in {"Cannon", "BombTower", "Xbow"} else Troop
        )
        return cls._from_stats(stats, source_type, vocabulary, f"card:{card_name}")

    @classmethod
    def compile_spawn_body(cls, parent_card, path, loader, vocabulary):
        """Compile a named serialized body path, never a runtime name guess.

        The caller must bind the actual source receipt created from this body.
        Root troop bodies are supported in addition to the explicit secondary,
        death-spawn and spawn-action routes audited in the training graph.
        """
        path = tuple(path)
        ordinary_root_body = (
            parent_card in _COMMON_ROOTS
            and parent_card not in {"Cannon", "BombTower", "Xbow"}
            and path == ("summonCharacterData",)
        )
        if not ordinary_root_body and (parent_card, path) not in _EXTRA_SPAWN_ROUTES:
            raise ValueError("serialized spawn-body route is not audited")
        body = loader.get_card(parent_card)._raw_entry
        for key in path:
            if not isinstance(body, dict) or not isinstance(body.get(key), dict):
                raise TypeError("serialized spawn-body authority is missing")
            body = body[key]
        if body.get("source") != "characters" or not isinstance(body.get("name"), str):
            raise ValueError("spawn body is not a serialized ordinary character")
        stats = troop_from_character_data(body["name"], body)
        return cls._from_stats(
            stats, Troop, vocabulary, "spawn:" + parent_card + "/" + "/".join(path)
        )

    @classmethod
    def _from_stats(cls, stats, source_type, vocabulary, authority):
        payload = stats.projectile_data
        body = stats._raw_entry.get("summonCharacterData") or {}
        if not isinstance(payload, dict) or not payload.get("name"):
            raise ValueError("source has no serialized projectile identity")
        if (
            payload.get("spawnProjectileData")
            or payload.get("projectileRange")
            or payload.get("chainedHitCount", 1) > 1
            or body.get("customFirstProjectileData")
            or body.get("kamikaze")
        ):
            raise ValueError("source is no longer a single ordinary projectile route")
        token = vocabulary.resolve(payload["name"], "projectile")
        if token <= 1:
            raise ValueError("serialized projectile identity has no actor token")
        return cls(
            stats.name,
            source_type,
            token,
            _payload_digest(payload),
            _payload_digest(body),
            authority,
        )

    def validate_source(self, source):
        """Validate a setup binding; labels never select appearance at emission."""
        if (
            type(source) is not self.source_type
            or source.card_stats is None
            or source.card_stats.name != self.source_card
            or _payload_digest(source.card_stats.projectile_data)
            != self.projectile_payload_sha256
            or _payload_digest(
                source.card_stats._raw_entry.get("summonCharacterData") or {}
            )
            != self.source_body_sha256
            or bool(getattr(source, "_force_melee_attack", False))
        ):
            raise ValueError(
                "source differs from compiled ordinary projectile descriptor"
            )


@dataclass(frozen=True)
class ScalarProjectileBirthReceipt:
    ordinal: int
    source_id: int
    projectile_id: int
    appearance: ScalarEffectAppearance


class ScalarProjectileReceiptRecorder:
    """Narrow per-instance interception, restored on normal/error context exit.

    Bind each source to a setup-compiled descriptor before running its combat
    component. The pre-call next entity ID identifies its own projectile even
    when synchronous start-collision callbacks create additional child objects.
    Such child objects receive no inherited appearance binding.
    """

    def __init__(self, battle, sources):
        self.battle = battle
        self.sources = tuple(sources)
        self.receipts: list[ScalarProjectileBirthReceipt] = []
        self.calls = 0
        self.zero_birth_calls = 0
        self._saved = []
        self._entered = False

    @property
    def appearances(self):
        return tuple(receipt.appearance for receipt in self.receipts)

    def __enter__(self):
        if self._entered:
            raise RuntimeError("receipt recorder cannot be entered twice")
        self._entered = True
        if len({id(source) for source, _ in self.sources}) != len(self.sources):
            raise ValueError("duplicate source registration")
        try:
            for source, descriptor in self.sources:
                descriptor.validate_source(source)
                if (
                    self.battle.entities.get(source.id) is not source
                    or source.battle_state is not self.battle
                ):
                    raise ValueError("source is not owned by this battle")
                previous = source.__dict__.get("_create_projectile")
                had_previous = "_create_projectile" in source.__dict__
                original = source._create_projectile
                if getattr(
                    getattr(original, "__func__", None), "_hog26_receipt_wrapper", False
                ):
                    raise ValueError("source already has a receipt recorder")
                wrapper = self._wrapper(source, descriptor, original)
                self._saved.append((source, had_previous, previous))
                source._create_projectile = MethodType(wrapper, source)
        except BaseException:
            self._restore()
            raise
        return self

    def _wrapper(self, source, descriptor, original):
        def create(bound_source, target, battle_state, *, target_position=None):
            if bound_source is not source or battle_state is not self.battle:
                raise ValueError("receipt source/battle binding changed")
            descriptor.validate_source(source)
            expected_id = battle_state.next_entity_id
            if expected_id in battle_state.entities:
                raise ValueError("next projectile identity is already occupied")
            self.calls += 1
            result = original(target, battle_state, target_position=target_position)
            entity = battle_state.entities.get(expected_id)
            if entity is None:
                if battle_state.next_entity_id != expected_id:
                    raise ValueError(
                        "creation advanced IDs without expected projectile"
                    )
                self.zero_birth_calls += 1
                return result
            if (
                type(entity) is not Projectile
                or entity.source_entity is not source
                or entity.player_id != source.player_id
                or battle_state.next_entity_id <= expected_id
            ):
                raise ValueError(
                    "birth does not match the audited ordinary creation route"
                )
            self.receipts.append(
                ScalarProjectileBirthReceipt(
                    len(self.receipts),
                    source.id,
                    expected_id,
                    ScalarEffectAppearance(entity, descriptor.token),
                )
            )
            return result

        create._hog26_receipt_wrapper = True
        return create

    def _restore(self):
        for source, had_previous, previous in reversed(self._saved):
            if had_previous:
                source._create_projectile = previous
            else:
                source.__dict__.pop("_create_projectile", None)
        self._saved.clear()

    def __exit__(self, exc_type, exc_value, traceback):
        self._restore()
        return False
