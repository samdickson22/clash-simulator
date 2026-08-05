from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class InvisibilityWhenNotAttacking(BaseMechanic):
    """Apply serialized inactivity-triggered invisibility."""
    fade_delay_ms: int = 2000
    use_attack_range: bool = False
    time_since_attack_ms: float = 0.0

    def on_attach(self, entity: 'Entity') -> None:
        # Royal Ghost enters the arena invisible; the delay applies only when
        # re-entering stealth after an attack.
        entity._stealth_until = 2**31 - 1
        raw = getattr(entity.card_stats, "_raw_entry", {}) or {}
        char_data = raw.get("summonCharacterData", {}) or {}
        self.fade_delay_ms = int(char_data.get("buffWhenNotAttackingTime", self.fade_delay_ms))
        self.use_attack_range = bool(
            char_data.get("buffWhenNotAttackingUseAttackRange", False)
        )
        self.time_since_attack_ms = float(self.fade_delay_ms)

    def on_object_tick(self, entity: 'Entity', dt_ms: int) -> None:
        if not hasattr(entity, 'battle_state'):
            return
        if self.use_attack_range:
            target = entity.battle_state.entities.get(
                getattr(entity, "target_id", None)
            )
            if (
                target is not None
                and entity._is_valid_target(target)
                and entity.is_within_attack_reach(target)
            ):
                # This serialized mode defines inactivity by combat reach,
                # not by the elapsed time since the last damage frame. A
                # slow or stun can stretch the next swing past the fade delay
                # without making the Ghost leave an ongoing melee.
                self.time_since_attack_ms = 0.0
                return
        self.time_since_attack_ms += max(0.0, float(dt_ms))
        if self.time_since_attack_ms >= self.fade_delay_ms:
            entity._stealth_until = 2**31 - 1

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        self.time_since_attack_ms = 0.0
        entity._stealth_until = 0


RoyalGhostFade = InvisibilityWhenNotAttacking
