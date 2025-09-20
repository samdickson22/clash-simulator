from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Any

if TYPE_CHECKING:
    from ..battle import BattleState
    from ..arena import Position

from .damage import DirectDamage
from .status import ApplyStun, ApplySlow, ApplyFreeze
from .area import PeriodicArea
from .projectile import ProjectileLaunch
from .spawn import SpawnUnits
from .buff import ApplyBuff


@dataclass
class EffectContext:
    battle_state: 'BattleState'
    caster_id: int
    target_position: 'Position'
    affected_entities: List[Any] = field(default_factory=list)

__all__ = [
    'DirectDamage', 'ApplyStun', 'ApplySlow', 'ApplyFreeze',
    'PeriodicArea', 'ProjectileLaunch', 'SpawnUnits', 'ApplyBuff',
    'EffectContext'
]