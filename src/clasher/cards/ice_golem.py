from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class IceGolemChill(BaseMechanic):
    """Applies the Ice Golem's slowing death nova."""
    slow_radius: float = 2.5
    slow_multiplier: float = 0.4
    slow_duration_ms: int = 2000
    damage_scale: float = 1.0

    def on_death(self, entity: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        damage = entity.damage * self.damage_scale
        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            if entity.position.distance_to(other.position) <= self.slow_radius:
                other.take_damage(damage)
                other.apply_slow(self.slow_duration_ms / 1000.0, self.slow_multiplier)

