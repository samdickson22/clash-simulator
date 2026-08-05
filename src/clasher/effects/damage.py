from dataclasses import dataclass
from typing import TYPE_CHECKING

from .effect_base import BaseEffect

if TYPE_CHECKING:
    from ..battle import BattleState
    from ..arena import Position


@dataclass
class DirectDamage(BaseEffect):
    """Effect that deals direct damage to entities in radius"""
    damage: float
    radius_tiles: float = 0.0

    def apply(self, context) -> None:
        """Deal damage to all enemies in radius"""
        battle_state = context.battle_state
        target_pos = context.target_position

        targets_hit = 0

        for entity in list(battle_state.entities.values()):
            if entity.player_id == context.caster_id or not entity.is_alive:
                continue

            if (
                entity.intersects_native_area(target_pos, self.radius_tiles)
                and entity.can_receive_area_damage()
            ):
                entity.take_damage(self.damage)
                targets_hit += 1
                context.affected_entities.append(entity)
