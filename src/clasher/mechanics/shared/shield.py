from dataclasses import dataclass, field

from ..mechanic_base import BaseMechanic


@dataclass
class Shield(BaseMechanic):
    """Mechanic that provides a shield that absorbs damage before HP"""
    shield_hp: int
    current_shield: int = field(init=False, default=0)

    def on_attach(self, entity) -> None:
        """Initialize shield state."""
        self.current_shield = self.shield_hp

    def modify_incoming_damage(self, entity, amount: float) -> float:
        """Absorb incoming damage with shield HP first."""
        if amount <= 0:
            return 0.0
        if self.current_shield <= 0:
            return amount
        absorbed = min(amount, self.current_shield)
        self.current_shield -= absorbed
        return amount - absorbed

    def on_death(self, entity) -> None:
        """No-op: shield behavior is handled in modify_incoming_damage."""
        return
