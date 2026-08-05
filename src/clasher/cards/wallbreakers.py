from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class WallBreakersDemolition(BaseMechanic):
    """Destroys a projectile-backed kamikaze after its payload is committed.

    Wall Breakers serialize their explosion as an ordinary area projectile
    with a one-logic-unit travel range.  Let the shared projectile engine own
    its launch position, radius, hit planes, scaling, and impact snapshot;
    this mechanic supplies only the character's kamikaze lifecycle.
    """

    def on_attach(self, entity: 'Entity') -> None:
        self._triggered = False

    def on_attack_committed(self, entity: 'Entity', target: 'Entity') -> None:
        if self._triggered:
            return
        self._triggered = True
        entity.take_damage(entity.hitpoints)
