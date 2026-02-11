from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class WallBreakersDemolition(BaseMechanic):
    """Forces wall breakers to explode on contact with buildings, dealing area damage."""
    explosion_radius: float = 2.5
    damage_multiplier: float = 2.5

    def on_attach(self, entity: 'Entity') -> None:
        self._triggered = False
        entity._force_melee_attack = True

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        if self._triggered or not hasattr(entity, 'battle_state'):
            return
        from ..entities import Building
        if isinstance(target, Building):
            self._explode(entity)

    def _explode(self, entity: 'Entity') -> None:
        battle_state = entity.battle_state
        damage = entity.damage * self.damage_multiplier
        for other in battle_state.entities.values():
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            if entity.position.distance_to(other.position) <= self.explosion_radius:
                other.take_damage(damage)
        entity.take_damage(entity.hitpoints)
        self._triggered = True
