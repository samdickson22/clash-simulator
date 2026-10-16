from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...entities import Entity


@dataclass
class SerializedOnHitBuff(BaseMechanic):
    """Apply a character's serialized BuffOnDamage payload to every hit."""

    duration_ms: int = 0
    movement_multiplier: float = 1.0
    attack_multiplier: float = 1.0
    spawn_multiplier: float = 1.0

    def on_attach(self, entity: "Entity") -> None:
        raw = getattr(entity.card_stats, "_raw_entry", {}) or {}
        character_data = raw.get("summonCharacterData", {}) or {}
        buff_data = character_data.get("buffOnDamageData", {}) or {}
        self.duration_ms = max(
            0,
            int(character_data.get("buffOnDamageTime", self.duration_ms) or 0),
        )
        self.movement_multiplier = self._buff_multiplier(
            buff_data.get("speedMultiplier")
        )
        self.attack_multiplier = self._buff_multiplier(
            buff_data.get("hitSpeedMultiplier")
        )
        self.spawn_multiplier = self._buff_multiplier(
            buff_data.get("spawnSpeedMultiplier")
        )

    @staticmethod
    def _buff_multiplier(percent: object) -> float:
        if percent is None:
            return 1.0
        return max(0.0, 1.0 + float(percent) / 100.0)

    def on_attack_hit(self, entity: "Entity", target: "Entity") -> None:
        self._apply(entity, target)

    def on_secondary_attack_hit(
        self,
        entity: "Entity",
        target: "Entity",
    ) -> None:
        self._apply(entity, target)

    def _apply(self, entity: "Entity", target: "Entity") -> None:
        if self.duration_ms <= 0:
            return
        duration = self.duration_ms / 1000.0
        source_kind = getattr(getattr(entity, "card_stats", None), "name", None)
        if (
            self.movement_multiplier <= 0.0
            and self.attack_multiplier <= 0.0
            and self.spawn_multiplier <= 0.0
        ):
            target.apply_stun(duration, source_kind=source_kind)
            return
        target.apply_slow(
            duration,
            self.movement_multiplier,
            attack_speed_multiplier=self.attack_multiplier,
            spawn_speed_multiplier=self.spawn_multiplier,
            source_kind=source_kind,
        )
