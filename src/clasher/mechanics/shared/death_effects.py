from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import math
import random

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...battle import BattleState


@dataclass
class DeathDamage(BaseMechanic):
    """Mechanic that deals area damage when entity dies"""
    radius_tiles: float
    damage: int

    def on_death(self, entity) -> None:
        """Deal area damage at death position"""
        if not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state

        # Deal area damage at death position
        for target in battle_state.entities.values():
            if target.player_id == entity.player_id or not target.is_alive:
                continue

            distance = entity.position.distance_to(target.position)

            # Check if target is within damage radius (accounting for collision radius)
            target_radius = getattr(target.card_stats, 'collision_radius', 0.5) or 0.5
            if distance <= (self.radius_tiles + target_radius):
                target.take_damage(self.damage)


@dataclass
class DeathSpawn(BaseMechanic):
    """Mechanic that spawns units when entity dies"""
    unit_name: str
    count: int
    radius_tiles: float = 0.5

    def on_death(self, entity) -> None:
        """Spawn units around death position"""
        if not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state

        # Try to get death spawn stats from card loader
        death_spawn_stats = battle_state.card_loader.get_card(self.unit_name)

        # If not found, create minimal stats
        if not death_spawn_stats:
            from ...data import CardStats
            death_spawn_stats = CardStats(
                name=self.unit_name,
                id=0,
                mana_cost=0,
                rarity="Common",
                hitpoints=100,
                damage=25,
                speed=60.0,
                range=1.0,
                sight_range=5.0,
                hit_speed=1000,
                load_time=1000,
                deploy_time=1000,
                collision_radius=0.5,
                attacks_ground=True,
                attacks_air=False,
                targets_only_buildings=False,
                target_type="TID_TARGETS_GROUND"
            )

        # Spawn units in a small radius around the death position
        for _ in range(self.count):
            # Random position around the death location
            angle = random.random() * 2 * math.pi
            distance = random.random() * self.radius_tiles
            spawn_x = entity.position.x + distance * math.cos(angle)
            spawn_y = entity.position.y + distance * math.sin(angle)

            # Create and spawn the unit
            from ...arena import Position
            battle_state._spawn_troop(Position(spawn_x, spawn_y), entity.player_id, death_spawn_stats)