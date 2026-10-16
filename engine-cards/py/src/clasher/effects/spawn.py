from dataclasses import dataclass
import math

from .effect_base import BaseEffect


@dataclass
class SpawnUnits(BaseEffect):
    """Effect that spawns units at target position"""
    unit_name: str
    count: int
    radius_tiles: float = 1.0
    unit_data: dict = None

    def apply(self, context) -> None:
        """Spawn units around target position"""
        from ..arena import Position

        battle_state = context.battle_state

        # Try to get unit stats from card loader
        unit_stats = battle_state.card_loader.get_card(self.unit_name)

        # If not found and unit_data provided, create stats from data
        if not unit_stats and self.unit_data:
            from ..factory.dynamic_factory import troop_from_character_data

            unit_stats = troop_from_character_data(
                self.unit_name,
                self.unit_data,
                elixir=0,
                rarity=self.unit_data.get("rarity", "Common"),
            )

        if not unit_stats:
            raise ValueError(
                f"Missing serialized spawn data for {self.unit_name}"
            )

        # Spawn units in a circle around target position
        for i in range(self.count):
            angle = (2 * math.pi * i) / self.count
            spawn_x = context.target_position.x + self.radius_tiles * math.cos(angle)
            spawn_y = context.target_position.y + self.radius_tiles * math.sin(angle)

            spawn_position = Position(spawn_x, spawn_y)
            battle_state._spawn_troop(spawn_position, context.caster_id, unit_stats)
