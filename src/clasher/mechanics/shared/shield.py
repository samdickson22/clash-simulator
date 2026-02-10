from dataclasses import dataclass, field

from ..mechanic_base import BaseMechanic


@dataclass
class Shield(BaseMechanic):
    """Mechanic that provides a shield that absorbs damage before HP"""
    shield_hp: int
    current_shield: int = field(init=False, default=0)

    def on_attach(self, entity) -> None:
        """Initialize shield and hook into damage system"""
        self.current_shield = self.shield_hp
        pass  # print(f"[Mechanic] Shield attached to {getattr(entity.card_stats, 'name', 'Unknown')} hp={self.shield_hp}")

        # Store original take_damage method and replace with shielded version
        entity._original_take_damage = entity.take_damage
        entity.take_damage = lambda amount: self._shielded_take_damage(entity, amount)

    def _shielded_take_damage(self, entity, amount: float) -> None:
        """Handle damage with shield absorption"""
        pass  # print(f"[Mechanic] Shield before={self.current_shield} incoming={amount}")
        if self.current_shield > 0:
            # Calculate how much damage shield can absorb
            absorbed = min(amount, self.current_shield)
            self.current_shield -= absorbed
            remaining = amount - absorbed

            # If shield is broken, deal remaining damage to HP
            if remaining > 0:
                entity._original_take_damage(remaining)
        else:
            # Shield is gone, deal full damage to HP
            entity._original_take_damage(amount)

    def on_death(self, entity) -> None:
        """Clean up shield hook when entity dies"""
        # Restore original take_damage method if it was replaced
        if hasattr(entity, '_original_take_damage'):
            entity.take_damage = entity._original_take_damage
            delattr(entity, '_original_take_damage')