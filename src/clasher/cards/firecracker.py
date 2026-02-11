from dataclasses import dataclass
from typing import TYPE_CHECKING
import math

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class FirecrackerRecoil(BaseMechanic):
    """Moves the Firecracker backwards after each shot to mimic recoil."""
    recoil_distance: float = 1.0
    shard_half_angle: float = 0.45
    shard_hit_width: float = 0.5

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        if target is None:
            return
        dx = entity.position.x - target.position.x
        dy = entity.position.y - target.position.y
        length = math.hypot(dx, dy)
        if length == 0:
            return
        entity.position.x += (dx / length) * self.recoil_distance
        entity.position.y += (dy / length) * self.recoil_distance
        self._apply_shards(entity, target)

    def _apply_shards(self, entity: 'Entity', target: 'Entity') -> None:
        if not hasattr(entity, "battle_state"):
            return
        projectile_data = getattr(entity.card_stats, "projectile_data", {}) or {}
        spawn_projectile = projectile_data.get("spawnProjectileData", {}) or {}
        shard_count = int(spawn_projectile.get("spawnCount", 0) or 0)
        shard_damage = float(spawn_projectile.get("damage", 0) or 0)
        shard_range = float(spawn_projectile.get("projectileRange", 0) or 0) / 1000.0
        if shard_count <= 0 or shard_damage <= 0 or shard_range <= 0:
            return

        dx = target.position.x - entity.position.x
        dy = target.position.y - entity.position.y
        base_len = math.hypot(dx, dy)
        if base_len == 0:
            return
        base_angle = math.atan2(dy, dx)

        for idx in range(shard_count):
            if shard_count == 1:
                shard_angle = base_angle
            else:
                t = idx / (shard_count - 1)
                shard_angle = base_angle - self.shard_half_angle + (2 * self.shard_half_angle * t)
            ux = math.cos(shard_angle)
            uy = math.sin(shard_angle)
            for other in list(entity.battle_state.entities.values()):
                if other.player_id == entity.player_id or not other.is_alive:
                    continue
                rel_x = other.position.x - target.position.x
                rel_y = other.position.y - target.position.y
                along = rel_x * ux + rel_y * uy
                if along < 0 or along > shard_range:
                    continue
                perp = abs(rel_x * uy - rel_y * ux)
                other_radius = getattr(other.card_stats, "collision_radius", 0.5) or 0.5
                if perp <= (self.shard_hit_width + other_radius):
                    other.take_damage(shard_damage)
