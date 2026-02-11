from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ValkyrieSpin(BaseMechanic):
    """Applies Valkyrie's 360-degree spin damage."""
    spin_radius: float = 1.8

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive or other.id == target.id:
                continue
            if entity.position.distance_to(other.position) <= self.spin_radius:
                other.take_damage(entity.damage)

