from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class PrincessLongRange(BaseMechanic):
    """Keep Princess range at its live nine-tile value.

    Combat positions are expressed in tiles throughout the simulator.  Her
    area damage is already represented by the attack projectile and must not
    be duplicated by a second card-specific damage hook.
    """

    range_tiles: float = 9.0

    def on_attach(self, entity: "Entity") -> None:
        entity.range = max(entity.range, self.range_tiles)
