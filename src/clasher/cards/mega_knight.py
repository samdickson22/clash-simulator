from dataclasses import dataclass
from typing import TYPE_CHECKING
import math

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class MegaKnightSlam(BaseMechanic):
    """Applies Mega Knight's spawn slam and ground shockwaves."""
    spawn_radius: float = 2.5
    spawn_damage_multiplier: float = 2.0
    slam_radius: float = 1.5
    stun_duration_ms: int = 300
    jump_height: float = 2.0
    leap_duration_ms: int = 600

    def on_spawn(self, entity: 'Entity') -> None:
        self._slam(entity, self.spawn_radius, entity.damage * self.spawn_damage_multiplier)

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        entity._mk_leap_progress = 0.0
        entity._mk_leap_origin = (entity.position.x, entity.position.y)
        entity._mk_leap_target = (target.position.x, target.position.y)

    def on_tick(self, entity: 'Entity', dt_ms: int) -> None:
        if not hasattr(entity, '_mk_leap_target') or entity._mk_leap_target is None:
            return
        entity._mk_leap_progress += dt_ms
        progress = min(1.0, entity._mk_leap_progress / self.leap_duration_ms)
        start_x, start_y = entity._mk_leap_origin
        target_x, target_y = entity._mk_leap_target
        entity.position.x = start_x + (target_x - start_x) * progress
        entity.position.y = start_y + (target_y - start_y) * progress
        if progress >= 1.0:
            entity._mk_leap_target = None

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        entity._mk_leap_target = None
        self._slam(entity, self.slam_radius, entity.damage)

    def _slam(self, entity: 'Entity', radius: float, damage: float) -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            if entity.position.distance_to(other.position) <= radius:
                other.take_damage(damage)
                other.apply_stun(self.stun_duration_ms / 1000.0)
