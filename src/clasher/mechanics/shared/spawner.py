from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import math
import random

from ..mechanic_base import BaseMechanic
from ...factory.dynamic_factory import troop_from_character_data, troop_from_values

if TYPE_CHECKING:
    from ...battle import BattleState


@dataclass
class PeriodicSpawner(BaseMechanic):
    """Mechanic that periodically spawns units"""
    unit_name: str
    spawn_interval_ms: int
    count: int = 1
    max_spawns: int = -1  # -1 for unlimited
    spawn_radius_tiles: float = 1.0
    unit_data: dict | None = None

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

            battle_state = entity.battle_state
            if getattr(battle_state, "debug_logs", False):
                print(
                    f"[Mechanic] PeriodicSpawner tick on {getattr(entity.card_stats, 'name', 'Unknown')} "
                    f"interval={self.spawn_interval_ms}ms count={self.count}"
                )
            self._spawn_unit(entity)
            self.time_since_spawn_ms = 0
            self.spawns_created += 1

    def _spawn_unit(self, entity) -> None:
        """Spawn a single unit"""
        battle_state = entity.battle_state

        spawn_stats = None
        if self.unit_data:
            spawn_stats = troop_from_character_data(
                self.unit_name,
                self.unit_data,
                elixir=0,
                rarity=self.unit_data.get("rarity", "Common"),
            )

        # Fall back to canonical card loader entry when raw spawn data is unavailable.
        if not spawn_stats:
            spawn_stats = battle_state.card_loader.get_card(self.unit_name)

        # If not found, create minimal stats
        if not spawn_stats:
            spawn_stats = troop_from_values(
                self.unit_name,
                hitpoints=100,
                damage=25,
                speed_tiles_per_min=60.0,
                range_tiles=1.0,
                sight_range_tiles=5.0,
                hit_speed_ms=1000,
                collision_radius_tiles=0.5,
            )

        from ...arena import Position
        if getattr(battle_state, "debug_logs", False):
            print(
                f"[Mechanic] Spawning {self.count}x {self.unit_name} around "
                f"{getattr(entity.card_stats, 'name', 'Unknown')}"
            )

        spawner_radius = getattr(getattr(entity, "card_stats", None), "collision_radius", 1.0) or 1.0
        unit_radius = getattr(spawn_stats, "collision_radius", 0.5) or 0.5
        min_spawn_distance = max(0.0, float(spawner_radius) + float(unit_radius) + 0.05)
        max_spawn_distance = max(min_spawn_distance, min_spawn_distance + float(self.spawn_radius_tiles))

        # Spawn 'count' units around the spawner
        for _ in range(max(1, self.count)):
            # Random position around the spawner
            angle = random.random() * 2 * math.pi
            distance = random.uniform(min_spawn_distance, max_spawn_distance)
            spawn_x = entity.position.x + distance * math.cos(angle)
            spawn_y = entity.position.y + distance * math.sin(angle)

            # Create and spawn the unit
            battle_state._spawn_troop(Position(spawn_x, spawn_y), entity.player_id, spawn_stats)
