from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ValkyrieSpin(BaseMechanic):
    """Applies Valkyrie's 360-degree spin damage."""
    spin_radius: float = 2.0

    def on_attach(self, entity: 'Entity') -> None:
        configured = getattr(entity.card_stats, "area_damage_radius", None)
        if configured:
            self.spin_radius = float(configured) / 1000.0
