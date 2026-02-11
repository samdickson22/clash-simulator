from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class RoyalGhostFade(BaseMechanic):
    """Handles Royal Ghost's invisibility when no enemies are nearby."""
    fade_radius: float = 4.5
    grace_period_ms: int = 600

    def on_attach(self, entity: 'Entity') -> None:
        entity._stealth_until = 0

    def on_tick(self, entity: 'Entity', dt_ms: int) -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        now_ms = int(battle_state.time * 1000)
        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            if entity.position.distance_to(other.position) <= self.fade_radius:
                entity._stealth_until = 0
                return
        entity._stealth_until = now_ms + self.grace_period_ms
