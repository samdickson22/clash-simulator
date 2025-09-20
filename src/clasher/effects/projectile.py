from dataclasses import dataclass
from typing import TYPE_CHECKING

from .effect_base import BaseEffect

if TYPE_CHECKING:
    from ...battle import BattleState
    from ...arena import Position


@dataclass
class ProjectileLaunch(BaseEffect):
    """Effect that launches a projectile towards target"""
    damage: float
    travel_speed: float  # tiles per second
    splash_radius_tiles: float = 0.0

    def apply(self, context) -> None:
        """Launch projectile from caster position towards target"""
        from ...entities import Projectile

        # Find launch position (caster's nearest tower or king tower)
        launch_pos = self._get_launch_position(context.battle_state, context.caster_id)

        projectile = Projectile(
            id=context.battle_state.next_entity_id,
            position=launch_pos,
            player_id=context.caster_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage,
            range=0,
            sight_range=0,
            target_position=Position(context.target_position.x, context.target_position.y),
            travel_speed=self.travel_speed,
            splash_radius=self.splash_radius_tiles,
            source_name="Projectile"
        )

        context.battle_state.entities[projectile.id] = projectile
        context.battle_state.next_entity_id += 1

    def _get_launch_position(self, battle_state: 'BattleState', player_id: int) -> 'Position':
        """Get launch position for projectile"""
        from ...arena import Position

        if player_id == 0:
            tower_pos = battle_state.arena.BLUE_KING_TOWER
            return Position(tower_pos.x, tower_pos.y)
        else:
            tower_pos = battle_state.arena.RED_KING_TOWER
            return Position(tower_pos.x, tower_pos.y)