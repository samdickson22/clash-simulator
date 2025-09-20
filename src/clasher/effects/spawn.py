from dataclasses import dataclass
from typing import TYPE_CHECKING
import math
import random

from .effect_base import BaseEffect

if TYPE_CHECKING:
    from ...battle import BattleState
    from ...arena import Position


@dataclass
class SpawnUnits(BaseEffect):
    """Effect that spawns units at target position"""
    unit_name: str
    count: int
    radius_tiles: float = 1.0
    unit_data: dict = None

    def apply(self, context) -> None:
        """Spawn units around target position"""
        battle_state = context.battle_state

        # Try to get unit stats from card loader
        unit_stats = battle_state.card_loader.get_card(self.unit_name)

        # If not found and unit_data provided, create stats from data
        if not unit_stats and self.unit_data:
            from ...data import CardStats
            unit_stats = CardStats(
                name=self.unit_name,
                id=0,
                mana_cost=0,
                rarity="Common",
                hitpoints=self.unit_data.get("hitpoints", 100),
                damage=self.unit_data.get("damage", 10),
                speed=float(self.unit_data.get("speed", 60)),
                range=self.unit_data.get("range", 1000) / 1000.0,
                sight_range=self.unit_data.get("sightRange", 5000) / 1000.0,
                hit_speed=self.unit_data.get("hitSpeed", 1000),
                deploy_time=self.unit_data.get("deployTime", 1000),
                load_time=self.unit_data.get("loadTime", 1000),
                collision_radius=self.unit_data.get("collisionRadius", 500) / 1000.0,
                attacks_ground=self.unit_data.get("attacksGround", True),
                attacks_air=False,
                targets_only_buildings=False,
                target_type=self.unit_data.get("tidTarget")
            )

        if not unit_stats:
            return

        # Spawn units in a circle around target position
        for i in range(self.count):
            angle = (2 * math.pi * i) / self.count
            spawn_x = context.target_position.x + self.radius_tiles * math.cos(angle)
            spawn_y = context.target_position.y + self.radius_tiles * math.sin(angle)

            spawn_position = Position(spawn_x, spawn_y)
            battle_state._spawn_troop(spawn_position, context.caster_id, unit_stats)