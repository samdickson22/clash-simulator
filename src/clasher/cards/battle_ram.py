from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class BattleRamCharge(BaseMechanic):
    """Breaks the ram and releases its riders when it connects."""

    def on_attach(self, entity: 'Entity') -> None:
        self._charge_used = False

    def on_spawn(self, entity: 'Entity') -> None:
        self._charge_used = False

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        if self._charge_used:
            return
        from ..entities import Building
        if isinstance(target, Building):
            self._charge_used = True
            entity.take_damage(entity.hitpoints)
