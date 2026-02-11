from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..arena import Position
from ..effects import ApplyBuff, EffectContext
from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class LumberjackRage(BaseMechanic):
    """Drops a rage aura when the Lumberjack dies."""
    rage_radius: float = 4.0
    speed_multiplier: float = 1.4
    damage_multiplier: float = 1.3
    duration_ms: int = 4000

    def on_death(self, entity: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        context = EffectContext(
            battle_state=battle_state,
            caster_id=entity.player_id,
            target_position=Position(entity.position.x, entity.position.y)
        )
        ApplyBuff(
            duration_seconds=self.duration_ms / 1000.0,
            speed_multiplier=self.speed_multiplier,
            damage_multiplier=self.damage_multiplier,
            radius_tiles=self.rage_radius
        ).apply(context)

