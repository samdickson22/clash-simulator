from dataclasses import dataclass, field

from ..mechanic_base import BaseMechanic


@dataclass
class Shield(BaseMechanic):
    """Mechanic that provides a shield that absorbs damage before HP"""
    shield_hp: int
    current_shield: int = field(init=False, default=0)
    max_shield: int = field(init=False, default=0)

    def on_attach(self, entity) -> None:
        """Initialize shield state."""
        scaler = getattr(getattr(entity, "card_stats", None), "get_scaled_stat", None)
        self.current_shield = int(scaler(self.shield_hp)) if callable(scaler) else self.shield_hp
        self.max_shield = self.current_shield
        entity._shield_break_count = getattr(entity, "_shield_break_count", 0)

    def modify_incoming_damage(self, entity, amount: float) -> float:
        """Absorb incoming damage with shield HP first."""
        if amount <= 0:
            return 0.0
        if self.current_shield <= 0:
            return amount
        shield_before = self.current_shield
        self.current_shield = max(0.0, self.current_shield - amount)
        if self.current_shield <= 0 < shield_before:
            entity._shield_break_count += 1
        # A shield consumes the entire hit that breaks it. Excess damage from
        # that hit does not spill into the unit's health pool.
        return 0.0

    def on_death(self, entity) -> None:
        """No-op: shield behavior is handled in modify_incoming_damage."""
        return
