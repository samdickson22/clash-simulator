from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Troop


@dataclass
class SparkyChargeUp(BaseMechanic):
    """Mechanic for Sparky's charge-up attack with stun reset"""
    charge_time_ms: int = 5000  # Time to fully charge
    charged_damage_multiplier: float = 3.0  # Damage multiplier when charged
    reset_on_stun: bool = True

    # Internal state
    charge_time: int = field(init=False, default=0)
    is_charging: bool = field(init=False, default=False)
    has_charged: bool = field(init=False, default=False)
    stored_original_damage: int = field(init=False, default=0)

    def on_attach(self, entity) -> None:
        """Store original damage value"""
        self.stored_original_damage = entity.damage

    def on_tick(self, entity, dt_ms: int) -> None:
        """Update charge state when targeting"""
        # Only charge when we have a target
        if entity.target_id and not self.has_charged:
            self.charge_time += dt_ms
            self.is_charging = True

            # Visual effect could be added here
        elif not entity.target_id:
            # Lose charge over time when no target
            self.charge_time = max(0, self.charge_time - dt_ms // 2)
            if self.charge_time == 0:
                self.is_charging = False

    def on_attack_start(self, entity, target) -> None:
        """Apply charged damage if fully charged"""
        if self.is_charging and self.charge_time >= self.charge_time_ms:
            # Apply charged damage
            entity.damage = int(self.stored_original_damage * self.charged_damage_multiplier)
            self.has_charged = True
            self.charge_time = 0
            self.is_charging = False
        else:
            # Normal damage
            entity.damage = self.stored_original_damage

    def on_death(self, entity) -> None:
        """Reset charge state on death"""
        self.charge_time = 0
        self.is_charging = False
        self.has_charged = False
        entity.damage = self.stored_original_damage

    def handle_stun(self, entity) -> None:
        """Handle stun reset (called from external stun logic)"""
        if self.reset_on_stun and self.is_charging:
            self.charge_time = 0
            self.is_charging = False