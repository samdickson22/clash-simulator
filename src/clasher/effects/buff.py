from dataclasses import dataclass
from typing import TYPE_CHECKING

from .effect_base import BaseEffect

if TYPE_CHECKING:
    from ...battle import BattleState
    from ...arena import Position


@dataclass
class ApplyBuff(BaseEffect):
    """Effect that applies buffs to friendly units in radius"""
    duration_seconds: float
    speed_multiplier: float = 1.5
    damage_multiplier: float = 1.4
    radius_tiles: float = 0.0

    def apply(self, context) -> None:
        """Apply buffs to friendly units in radius"""
        battle_state = context.battle_state
        target_pos = context.target_position

        targets_hit = 0

        for entity in battle_state.entities.values():
            if entity.player_id != context.caster_id or not entity.is_alive:
                continue

            distance = entity.position.distance_to(target_pos)
            if distance <= self.radius_tiles:
                # Store original values for restoration
                if not hasattr(entity, '_original_speed'):
                    entity._original_speed = getattr(entity, 'speed', 0)
                if not hasattr(entity, '_original_damage'):
                    entity._original_damage = entity.damage

                # Apply buff effects
                if hasattr(entity, 'speed'):
                    entity.speed *= self.speed_multiplier
                entity.damage *= self.damage_multiplier
                entity.attack_speed_buff_multiplier = max(
                    getattr(entity, "attack_speed_buff_multiplier", 1.0),
                    self.speed_multiplier,
                )

                # Store buff info for duration tracking
                entity._buff_end_time = battle_state.time + self.duration_seconds
                entity._buff_active = True

                targets_hit += 1
                context.affected_entities.append(entity)
