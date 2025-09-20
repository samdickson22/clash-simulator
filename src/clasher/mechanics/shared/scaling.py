from dataclasses import dataclass

from ..mechanic_base import BaseMechanic


@dataclass
class CrownTowerScaling(BaseMechanic):
    """Mechanic that scales damage against crown towers"""
    damage_multiplier: float = 1.0  # Typically 0.4 for most spells
    stored_original_damage: int = 0

    def on_attach(self, entity) -> None:
        """Store original damage value"""
        self.stored_original_damage = entity.damage

    def on_attack_start(self, entity, target) -> None:
        """Apply crown tower scaling if attacking a tower"""
        # Check if target is a crown tower (king tower or princess tower)
        from ...entities import Building
        if isinstance(target, Building):
            # Check if this is one of the main towers by position
            is_crown_tower = False

            # You could add more sophisticated tower detection here
            # For now, we'll assume buildings are towers if they're not regular defenses
            if hasattr(target.card_stats, 'name'):
                tower_names = ['Tower', 'KingTower', 'PrincessTower']
                for tower_name in tower_names:
                    if tower_name in target.card_stats.name:
                        is_crown_tower = True
                        break

            if is_crown_tower:
                entity.damage = int(self.stored_original_damage * self.damage_multiplier)
            else:
                entity.damage = self.stored_original_damage
        else:
            entity.damage = self.stored_original_damage