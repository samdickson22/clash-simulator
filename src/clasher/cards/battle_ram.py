from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class BattleRamCharge(BaseMechanic):
    """Applies charge bonus damage when the ram connects with a building."""

    def on_attach(self, entity: 'Entity') -> None:
        self._charge_used = False

    def on_spawn(self, entity: 'Entity') -> None:
        self._charge_used = False

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        if self._charge_used:
            return
        from ..entities import Building
        if isinstance(target, Building):
            bonus = (
                getattr(entity.card_stats, "scaled_damage_special", None)
                or getattr(entity.card_stats, 'damage_special', None)
            )
            if bonus:
                target.take_damage(bonus)
            self._charge_used = True
