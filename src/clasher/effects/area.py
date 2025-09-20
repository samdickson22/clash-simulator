from dataclasses import dataclass
from typing import TYPE_CHECKING

from .effect_base import BaseEffect

if TYPE_CHECKING:
    from ...battle import BattleState
    from ...arena import Position


@dataclass
class PeriodicArea(BaseEffect):
    """Effect that creates an area with periodic damage/effects"""
    damage_per_second: float
    duration_seconds: float
    radius_tiles: float
    freeze_effect: bool = False
    pull_force: float = 0.0

    def apply(self, context) -> None:
        """Create area effect entity"""
        from ...entities import AreaEffect

        area_effect = AreaEffect(
            id=context.battle_state.next_entity_id,
            position=Position(context.target_position.x, context.target_position.y),
            player_id=context.caster_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage_per_second,
            range=self.radius_tiles,
            sight_range=self.radius_tiles,
            duration=self.duration_seconds,
            freeze_effect=self.freeze_effect,
            radius=self.radius_tiles
        )

        # Add special properties if needed
        if self.pull_force > 0:
            area_effect.pull_force = self.pull_force
            area_effect.is_tornado = True

        context.battle_state.entities[area_effect.id] = area_effect
        context.battle_state.next_entity_id += 1