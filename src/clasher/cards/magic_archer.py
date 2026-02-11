from dataclasses import dataclass
from typing import TYPE_CHECKING
import math

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class MagicArcherPierce(BaseMechanic):
    """Applies Magic Archer's piercing arrow behaviour."""
    pierce_range: float = 5.0
    perpendicular_tolerance: float = 0.6
    damage_decay: float = 0.8

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        dx = target.position.x - entity.position.x
        dy = target.position.y - entity.position.y
        length = math.hypot(dx, dy)
        if length == 0:
            return
        ux = dx / length
        uy = dy / length
        origin_x = target.position.x
        origin_y = target.position.y
        damage = entity.damage * self.damage_decay
        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive or other.id == target.id:
                continue
            rel_x = other.position.x - origin_x
            rel_y = other.position.y - origin_y
            proj = rel_x * ux + rel_y * uy
            if proj <= 0 or proj > self.pierce_range:
                continue
            perpendicular = abs(rel_x * uy - rel_y * ux)
            if perpendicular <= self.perpendicular_tolerance:
                other.take_damage(damage)
