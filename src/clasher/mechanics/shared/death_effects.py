from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import math
import random

from ..mechanic_base import BaseMechanic
from ...factory.dynamic_factory import troop_from_values

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

        print(f"[Mechanic] DeathDamage triggered by {getattr(entity.card_stats, 'name', 'Unknown')} at ({entity.position.x:.1f},{entity.position.y:.1f}) radius={self.radius_tiles} dmg={self.damage}")

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
    unit_data: dict | None = None

    def on_death(self, entity) -> None:
        """Spawn units around death position"""
        if not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state

        print(f"[Mechanic] DeathSpawn triggered by {getattr(entity.card_stats, 'name', 'Unknown')} -> {self.count}x {self.unit_name}")

        from ...arena import Position
        from ...entities import TimedExplosive
        from ...factory.dynamic_factory import troop_from_character_data

        # Bomb-style death spawns (e.g., BalloonBomb, BombTowerBomb) become timed explosives.
        if self.unit_data and self.unit_data.get("deathDamage") is not None and not self.unit_data.get("hitpoints"):
            explosion_damage = self.unit_data.get("deathDamage", 0)
            explosion_timer = max(0.1, (self.unit_data.get("deployTime", 1000) or 1000) / 1000.0)
            explosion_radius = max(0.5, (self.unit_data.get("collisionRadius", 1000) or 1000) / 1000.0)
            spawn_data = self.unit_data.get("deathSpawnCharacterData") or {}
            spawn_name = spawn_data.get("name") or self.unit_data.get("deathSpawnCharacter")
            spawn_count = int(self.unit_data.get("deathSpawnCount", 0) or 0)
            for _ in range(self.count):
                explosive = TimedExplosive(
                    id=battle_state.next_entity_id,
                    position=Position(entity.position.x, entity.position.y),
                    player_id=entity.player_id,
                    card_stats=entity.card_stats,
                    hitpoints=1,
                    max_hitpoints=1,
                    damage=0,
                    range=0,
                    sight_range=0,
                    explosion_timer=explosion_timer,
                    explosion_radius=explosion_radius,
                    explosion_damage=explosion_damage,
                    death_spawn_name=spawn_name,
                    death_spawn_count=spawn_count,
                    death_spawn_data=spawn_data or None,
                )
                battle_state.entities[explosive.id] = explosive
                battle_state.next_entity_id += 1
            return

        # Try to get death spawn stats from card loader.
        death_spawn_stats = battle_state.card_loader.get_card(self.unit_name)
        if not death_spawn_stats and self.unit_data:
            death_spawn_stats = troop_from_character_data(
                self.unit_name,
                self.unit_data,
                elixir=0,
                rarity=self.unit_data.get("rarity", "Common"),
            )
        if not death_spawn_stats:
            death_spawn_stats = troop_from_values(
                self.unit_name,
                hitpoints=100,
                damage=25,
                speed_tiles_per_min=60.0,
                range_tiles=1.0,
                sight_range_tiles=5.0,
                hit_speed_ms=1000,
                collision_radius_tiles=0.5,
            )

        # Spawn units in a small radius around the death position
        for _ in range(self.count):
            # Random position around the death location
            angle = random.random() * 2 * math.pi
            distance = random.random() * self.radius_tiles
            spawn_x = entity.position.x + distance * math.cos(angle)
            spawn_y = entity.position.y + distance * math.sin(angle)

            battle_state._spawn_troop(Position(spawn_x, spawn_y), entity.player_id, death_spawn_stats)
