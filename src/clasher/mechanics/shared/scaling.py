from dataclasses import dataclass

from ..mechanic_base import BaseMechanic


@dataclass
class CrownTowerScaling(BaseMechanic):
    """Mechanic that scales damage against crown towers"""
    damage_multiplier: float = 1.0  # Typically 0.4 for most spells
    crown_tower_damage: int | None = None
    stored_original_damage: int = 0

    def on_attach(self, entity) -> None:
        """Store original damage value"""
        self.stored_original_damage = entity.damage

    @staticmethod
    def _is_crown_tower(target) -> bool:
        from ...entities import Building

        return (
            isinstance(target, Building)
            and getattr(getattr(target, "card_stats", None), "name", None)
            in {"Tower", "KingTower", "PrincessTower"}
        )

    def modify_outgoing_damage(self, entity, target, damage: float) -> float:
        if not self._is_crown_tower(target):
            return damage
        if self.crown_tower_damage is not None:
            return float(self.crown_tower_damage)
        return float(int(damage * self.damage_multiplier))

    def projectile_crown_tower_damage(
        self,
        entity,
        damage: float,
    ) -> float | None:
        if self.crown_tower_damage is not None:
            return float(self.crown_tower_damage)
        return float(int(damage * self.damage_multiplier))
