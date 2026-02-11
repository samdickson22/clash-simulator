from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..arena import Position
from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class IceSpiritFreeze(BaseMechanic):
    """Freezes nearby enemies when Ice Spirit connects or expires."""
    freeze_radius: float = 2.0
    freeze_duration_ms: int = 1500
    hop_duration_ms: int = 200

    def on_attach(self, entity: 'Entity') -> None:
        entity._force_melee_attack = True
        entity._ice_spirit_detonated = False
        entity._ice_spirit_jump_timer = 0.0
        entity._ice_spirit_jump_target = None

    def on_tick(self, entity: 'Entity', dt_ms: int) -> None:
        target = getattr(entity, '_ice_spirit_jump_target', None)
        if not target:
            return
        entity._ice_spirit_jump_timer += dt_ms
        progress = min(1.0, entity._ice_spirit_jump_timer / self.hop_duration_ms)
        start_x, start_y = getattr(entity, '_ice_spirit_jump_origin', (entity.position.x, entity.position.y))
        target_x, target_y = target
        entity.position.x = start_x + (target_x - start_x) * progress
        entity.position.y = start_y + (target_y - start_y) * progress
        if progress >= 1.0:
            entity._ice_spirit_jump_target = None

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        origin = Position(target.position.x, target.position.y)
        self._freeze(entity, origin)
        entity._ice_spirit_detonated = True
        entity.take_damage(entity.hitpoints)

    def on_death(self, entity: 'Entity') -> None:
        if getattr(entity, '_ice_spirit_detonated', False):
            return
        origin = Position(entity.position.x, entity.position.y)
        self._freeze(entity, origin)

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        entity._ice_spirit_jump_origin = (entity.position.x, entity.position.y)
        entity._ice_spirit_jump_target = (target.position.x, target.position.y)
        entity._ice_spirit_jump_timer = 0.0

    def _freeze(self, entity: 'Entity', origin: Position) -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        for other in battle_state.entities.values():
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            if origin.distance_to(other.position) <= self.freeze_radius:
                other.apply_stun(self.freeze_duration_ms / 1000.0)
