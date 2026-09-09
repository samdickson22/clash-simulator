"""Diagnostic receipts for three audited scalar rolling/piercing source routes.

Actual births are intercepted; serialized payload metadata never manufactures
an event. A same-frame Wall Breaker projectile can have a birth receipt while
being dead and therefore absent from the subsequent actor observation.
"""

from __future__ import annotations

from dataclasses import dataclass

from clasher.entities import Projectile, RollingProjectile, Troop
from scripts.hog26_scalar_projectile_receipts import (
    ScalarProjectileBirthReceipt,
    ScalarProjectileReceiptRecorder,
    _payload_digest,
)
from scripts.hog26_scalar_public_effect_adapter import ScalarEffectAppearance


@dataclass(frozen=True)
class ScalarLineProjectileDescriptor:
    source_card: str
    token: int
    effect_type: type
    body_sha256: str
    projectile_sha256: str

    @classmethod
    def compile(cls, card_name, loader, vocabulary):
        if card_name not in {"Bowler", "MagicArcher", "Wallbreakers"}:
            raise ValueError("line projectile source is not audited")
        stats = loader.get_card(card_name)
        body = stats._raw_entry.get("summonCharacterData") or {}
        payload = stats.projectile_data or {}
        rolling = bool(
            payload.get("projectileRadius")
            and payload.get("projectileRange")
            and payload.get("pushback")
        )
        if (
            payload.get("spawnProjectileData")
            or payload.get("chainedHitCount", 1) > 1
            or body.get("customFirstProjectileData")
            or int(payload.get("projectileRange", 0)) <= 0
            or rolling != (card_name == "Bowler")
        ):
            raise ValueError("source no longer matches its audited line route")
        if card_name == "Wallbreakers" and (
            payload.get("projectileRange") != 1 or not body.get("kamikaze")
        ):
            raise ValueError("Wall Breaker transient projectile route changed")
        identity = payload.get("name")
        token = vocabulary.resolve(identity, "projectile") if identity else 0
        if token <= 1:
            raise ValueError("line projectile has no serialized actor identity")
        return cls(
            stats.name,
            token,
            RollingProjectile if rolling else Projectile,
            _payload_digest(body),
            _payload_digest(payload),
        )

    def validate_source(self, source):
        if (
            type(source) is not Troop
            or source.card_stats is None
            or source.card_stats.name != self.source_card
            or bool(getattr(source, "_force_melee_attack", False))
            or _payload_digest(
                source.card_stats._raw_entry.get("summonCharacterData") or {}
            )
            != self.body_sha256
            or _payload_digest(source.card_stats.projectile_data)
            != self.projectile_sha256
        ):
            raise ValueError("source differs from its compiled line-projectile route")


class ScalarLineProjectileReceiptRecorder(ScalarProjectileReceiptRecorder):
    """Reuse per-instance installation/restoration; specialize birth validation."""

    def _wrapper(self, source, descriptor, original):
        if not isinstance(descriptor, ScalarLineProjectileDescriptor):
            raise TypeError("line recorder requires a compiled line descriptor")

        def create(bound_source, target, battle_state, *, target_position=None):
            if bound_source is not source or battle_state is not self.battle:
                raise ValueError("line receipt source/battle binding changed")
            descriptor.validate_source(source)
            expected_id = battle_state.next_entity_id
            if expected_id in battle_state.entities:
                raise ValueError("next line projectile identity is already occupied")
            self.calls += 1
            result = original(target, battle_state, target_position=target_position)
            entity = battle_state.entities.get(expected_id)
            if entity is None:
                if battle_state.next_entity_id != expected_id:
                    raise ValueError(
                        "line creation advanced IDs without its own object"
                    )
                self.zero_birth_calls += 1
                return result
            if (
                type(entity) is not descriptor.effect_type
                or entity.source_entity is not source
                or entity.player_id != source.player_id
                or battle_state.next_entity_id <= expected_id
                or (type(entity) is Projectile and not entity.pierces)
            ):
                raise ValueError("birth does not match audited line source/type/owner")
            self.receipts.append(
                ScalarProjectileBirthReceipt(
                    len(self.receipts),
                    source.id,
                    expected_id,
                    ScalarEffectAppearance(
                        entity, descriptor.token, descriptor.effect_type, 1
                    ),
                )
            )
            return result

        create._hog26_receipt_wrapper = True
        return create
