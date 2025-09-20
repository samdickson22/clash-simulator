from dataclasses import dataclass
from typing import TYPE_CHECKING

from .effect_base import BaseEffect

if TYPE_CHECKING:
    from ...battle import BattleState
    from ...arena import Position


@dataclass
class ApplyStun(BaseEffect):
    """Effect that stuns entities in radius"""
    duration_seconds: float
    radius_tiles: float = 0.0

    def apply(self, context) -> None:
        """Apply stun to enemies in radius"""
        battle_state = context.battle_state
        target_pos = context.target_position

        for entity in battle_state.entities.values():
            if entity.player_id == context.caster_id or not entity.is_alive:
                continue

            distance = entity.position.distance_to(target_pos)
            entity_radius = getattr(entity.card_stats, 'collision_radius', 0.5) or 0.5

            if distance <= (self.radius_tiles + entity_radius):
                entity.apply_stun(self.duration_seconds)
                context.affected_entities.append(entity)


@dataclass
class ApplySlow(BaseEffect):
    """Effect that slows entities in radius"""
    duration_seconds: float
    slow_multiplier: float = 0.5
    radius_tiles: float = 0.0

    def apply(self, context) -> None:
        """Apply slow to enemies in radius"""
        battle_state = context.battle_state
        target_pos = context.target_position

        for entity in battle_state.entities.values():
            if entity.player_id == context.caster_id or not entity.is_alive:
                continue

            distance = entity.position.distance_to(target_pos)
            entity_radius = getattr(entity.card_stats, 'collision_radius', 0.5) or 0.5

            if distance <= (self.radius_tiles + entity_radius):
                entity.apply_slow(self.duration_seconds, self.slow_multiplier)
                context.affected_entities.append(entity)


@dataclass
class ApplyFreeze(BaseEffect):
    """Effect that freezes entities (stops movement and attacks)"""
    duration_seconds: float
    radius_tiles: float = 0.0

    def apply(self, context) -> None:
        """Apply freeze to enemies in radius"""
        battle_state = context.battle_state
        target_pos = context.target_position

        for entity in battle_state.entities.values():
            if entity.player_id == context.caster_id or not entity.is_alive:
                continue

            distance = entity.position.distance_to(target_pos)
            entity_radius = getattr(entity.card_stats, 'collision_radius', 0.5) or 0.5

            if distance <= (self.radius_tiles + entity_radius):
                # Stop movement
                if hasattr(entity, 'speed'):
                    entity.speed = 0

                # Stop attacks by extending attack cooldown
                if hasattr(entity, 'attack_cooldown'):
                    entity.attack_cooldown = max(entity.attack_cooldown, self.duration_seconds)

                context.affected_entities.append(entity)