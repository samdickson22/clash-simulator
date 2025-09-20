from dataclasses import dataclass

from ..mechanic_base import BaseMechanic


@dataclass
class KnockbackOnHit(BaseMechanic):
    """Mechanic that knocks back targets on attack hit"""
    knockback_distance: float = 1.0  # tiles
    knockback_chance: float = 1.0

    def on_attack_hit(self, entity, target) -> None:
        """Apply knockback effect to target"""
        import random

        if random.random() <= self.knockback_chance:
            # Buildings cannot be knocked back
            from ...entities import Building
            if isinstance(target, Building):
                return

            # Calculate knockback direction (away from attacker)
            dx = target.position.x - entity.position.x
            dy = target.position.y - entity.position.y
            distance = (dx * dx + dy * dy) ** 0.5

            if distance > 0:
                # Normalize and apply knockback
                knockback_x = (dx / distance) * self.knockback_distance
                knockback_y = (dy / distance) * self.knockback_distance

                # Apply knockback movement
                target.position.x += knockback_x
                target.position.y += knockback_y

                # Brief stun effect
                target.attack_cooldown = max(target.attack_cooldown, 0.5)

                # Ensure target stays within arena bounds
                target.position.x = max(0.5, min(17.5, target.position.x))
                target.position.y = max(0.5, min(31.5, target.position.y))