from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...entities import Entity


@dataclass
class FreezeDebuff(BaseMechanic):
    """Mechanic that applies a slow debuff to nearby enemies"""
    radius_tiles: float
    slow_multiplier: float = 0.5
    aura_effect: bool = True  # If True, applies continuously while alive

    def on_tick(self, entity, dt_ms: int) -> None:
        """Apply slow to enemies within radius"""
        if not self.aura_effect or not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state

        for target in list(battle_state.entities.values()):
            if target.player_id == entity.player_id or not target.is_alive:
                continue

            distance = entity.position.distance_to(target.position)
            if distance <= self.radius_tiles:
                # Apply slow effect
                target.apply_slow(dt_ms / 1000.0, self.slow_multiplier)


@dataclass
class Stun(BaseMechanic):
    """Mechanic that can stun targets on attack"""
    stun_duration_ms: int
    stun_chance: float = 1.0  # 1.0 = always stun

    def on_attack_hit(self, entity, target) -> None:
        """Apply stun to target if chance succeeds"""
        import random

        if random.random() <= self.stun_chance:
            target.apply_stun(self.stun_duration_ms / 1000.0)
