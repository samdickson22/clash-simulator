from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class PrincessLongRange(BaseMechanic):
    """Princess has the longest range of any troop at 9 tiles"""
    range_bonus_tiles: float = 9.0  # 9 tile range
    first_attack_speed_bonus: float = 0.5  # First attack is 50% faster

    def on_attach(self, entity: 'Entity') -> None:
        """Apply range bonus and set up first attack bonus"""
        if hasattr(entity, 'range'):
            entity.range = max(entity.range, self.range_bonus_tiles * 1000)  # Convert to game units

        # Track if this is the first attack
        entity._princess_first_attack = True

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        """Apply first attack speed bonus"""
        if getattr(entity, '_princess_first_attack', True):
            # Reduce attack cooldown for first attack
            if hasattr(entity, 'attack_cooldown'):
                entity.attack_cooldown *= self.first_attack_speed_bonus
            entity._princess_first_attack = False


@dataclass
class PrincessAreaArrows(BaseMechanic):
    """Princess shoots arrows with area damage"""
    arrow_count: int = 5  # Number of arrows per shot
    arrow_spread_radius_tiles: float = 1.5  # Arrow spread radius
    area_damage_radius_tiles: float = 1.0  # Area damage per arrow

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        """Create multiple arrows with area damage"""
        if not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state
        base_damage = entity.damage or 0

        # Create multiple arrow impacts in the target area
        for i in range(self.arrow_count):
            self._create_arrow_impact(entity, target.position, base_damage)

    def _create_arrow_impact(self, shooter: 'Entity', target_pos, damage: float) -> None:
        """Create an arrow impact with area damage"""
        if not hasattr(shooter, 'battle_state'):
            return

        battle_state = shooter.battle_state

        # Calculate random offset for arrow spread
        import math
        import random

        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(0, self.arrow_spread_radius_tiles * 1000)

        offset_x = distance * math.cos(angle)
        offset_y = distance * math.sin(angle)

        impact_pos = target_pos.copy()
        impact_pos.x += offset_x
        impact_pos.y += offset_y

        # Apply area damage around impact point
        area_radius_units = self.area_damage_radius_tiles * 1000
        arrow_damage = damage / self.arrow_count  # Divide damage among arrows

        for target in list(battle_state.entities.values()):
            if (target.player_id == shooter.player_id or
                not target.is_alive):
                continue

            distance_to_impact = impact_pos.distance_to(target.position)
            if distance_to_impact <= area_radius_units:
                target.take_damage(arrow_damage)


@dataclass
class PrincessMultiShot(BaseMechanic):
    """Princess special multi-shot behavior for her first attack"""
    initial_arrow_count: int = 1  # First attack shoots 1 arrow
    subsequent_arrow_count: int = 5  # Subsequent attacks shoot 5 arrows
    is_first_attack: bool = field(init=False, default=True)

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        """Set arrow count based on whether it's the first attack"""
        if self.is_first_attack:
            # Set up for single arrow first attack
            entity._princess_arrow_count = self.initial_arrow_count
            self.is_first_attack = False
        else:
            # Set up for multi-arrow subsequent attacks
            entity._princess_arrow_count = self.subsequent_arrow_count

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        """Override to use dynamic arrow count"""
        arrow_count = getattr(entity, '_princess_arrow_count', self.subsequent_arrow_count)

        # Create the appropriate number of arrows
        for i in range(arrow_count):
            self._create_single_arrow(entity, target, i, arrow_count)

    def _create_single_arrow(self, shooter: 'Entity', target: 'Entity', arrow_index: int, total_arrows: int) -> None:
        """Create a single arrow projectile"""
        if not hasattr(shooter, 'battle_state'):
            return

        from ..entities import Projectile
        from ..arena import Position
        import math

        # Calculate spread target position
        if total_arrows > 1:
            # Create spread for multiple arrows
            spread_angle = (arrow_index - (total_arrows - 1) / 2) * 0.2  # Spread angle in radians
            spread_distance = 500  # Spread distance in game units

            # Calculate spread offset from main target
            target_offset_x = spread_distance * math.sin(spread_angle)
            target_offset_y = spread_distance * math.cos(spread_angle)
        else:
            # Single arrow goes directly to target
            target_offset_x = 0
            target_offset_y = 0

        # Calculate final target position
        target_pos = Position(
            target.position.x + target_offset_x,
            target.position.y + target_offset_y
        )

        # Create arrow projectile with proper damage scaling
        arrow_damage = (shooter.damage or 0) / total_arrows  # Divide damage among arrows

        arrow = Projectile(
            id=shooter.battle_state.next_entity_id,
            position=shooter.position.copy(),
            player_id=shooter.player_id,
            card_stats=None,  # Projectiles don't need card stats
            hitpoints=1,
            max_hitpoints=1,
            damage=arrow_damage,
            range=0,
            sight_range=0,
            target_position=target_pos,
            travel_speed=1200,  # Arrow speed in game units per second
            splash_radius=300,  # Small splash radius for area damage
            source_name="Princess"
        )

        # Set projectile lifetime
        arrow.lifetime_ms = 2000

        # Add to battle state
        shooter.battle_state.add_entity(arrow)
        shooter.battle_state.next_entity_id += 1

