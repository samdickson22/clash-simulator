from dataclasses import dataclass

from .effect_base import BaseEffect


@dataclass
class ApplyStun(BaseEffect):
    """Effect that stuns entities in radius"""
    duration_seconds: float
    radius_tiles: float = 0.0

    def apply(self, context) -> None:
        """Apply stun to enemies in radius"""
        battle_state = context.battle_state
        target_pos = context.target_position

        for entity in list(battle_state.entities.values()):
            if entity.player_id == context.caster_id or not entity.is_alive:
                continue

            if entity.intersects_native_area(target_pos, self.radius_tiles):
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

        for entity in list(battle_state.entities.values()):
            if entity.player_id == context.caster_id or not entity.is_alive:
                continue

            if entity.intersects_native_area(target_pos, self.radius_tiles):
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

        for entity in list(battle_state.entities.values()):
            if entity.player_id == context.caster_id or not entity.is_alive:
                continue

            if entity.intersects_native_area(target_pos, self.radius_tiles):
                # Stop movement
                if hasattr(entity, 'speed'):
                    entity.speed = 0

                # Stop attacks by extending attack cooldown
                if hasattr(entity, 'attack_cooldown'):
                    entity.attack_cooldown = max(entity.attack_cooldown, self.duration_seconds)

                context.affected_entities.append(entity)
