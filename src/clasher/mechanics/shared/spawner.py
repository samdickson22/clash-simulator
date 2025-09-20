from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import math
import random

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...battle import BattleState


@dataclass
class PeriodicSpawner(BaseMechanic):
    """Mechanic that periodically spawns units"""
    unit_name: str
    spawn_interval_ms: int
    max_spawns: int = -1  # -1 for unlimited
    spawn_radius_tiles: float = 1.0

    # Internal state
    time_since_spawn_ms: int = field(init=False, default=0)
    spawns_created: int = field(init=False, default=0)

    def on_tick(self, entity, dt_ms: int) -> None:
        """Check if it's time to spawn units"""
        if not hasattr(entity, 'battle_state'):
            return

        self.time_since_spawn_ms += dt_ms

        # Check if we should spawn and haven't reached max
        if (self.time_since_spawn_ms >= self.spawn_interval_ms and
                (self.max_spawns == -1 or self.spawns_created < self.max_spawns)):

            self._spawn_unit(entity)
            self.time_since_spawn_ms = 0
            self.spawns_created += 1

    def _spawn_unit(self, entity) -> None:
        """Spawn a single unit"""
        battle_state = entity.battle_state

        # Try to get spawn stats from card loader
        spawn_stats = battle_state.card_loader.get_card(self.unit_name)

        # If not found, create minimal stats
        if not spawn_stats:
            from ...data import CardStats
            spawn_stats = CardStats(
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

        # Random position around the spawner
        angle = random.random() * 2 * math.pi
        distance = random.random() * self.spawn_radius_tiles
        spawn_x = entity.position.x + distance * math.cos(angle)
        spawn_y = entity.position.y + distance * math.sin(angle)

        # Create and spawn the unit
        from ...arena import Position
        battle_state._spawn_troop(Position(spawn_x, spawn_y), entity.player_id, spawn_stats)