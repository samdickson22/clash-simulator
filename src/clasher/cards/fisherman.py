from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Troop


@dataclass
class FishermanHook(BaseMechanic):
    """Mechanic for Fisherman's hook ability that pulls enemies"""
    hook_range: float = 6.0  # Range of hook ability
    hook_pull_distance: float = 3.0  # Distance enemy is pulled
    hook_cooldown_ms: int = 4000  # Cooldown between hook uses
    hook_stun_duration_ms: int = 500  # Stun duration after hook

    # Internal state
    last_hook_time: int = field(init=False, default=0)
    is_hooking: bool = field(init=False, default=False)
    hook_target_id: int = field(init=False, default=0)

    def on_tick(self, entity, dt_ms: int) -> None:
        """Check for hook opportunities"""
        if not hasattr(entity, 'battle_state'):
            return

        current_time_ms = int(entity.battle_state.time * 1000)

        # Check cooldown
        if current_time_ms - self.last_hook_time < self.hook_cooldown_ms:
            return

        # Find nearest enemy within hook range
        nearest_enemy = None
        min_distance = float('inf')

        for target in entity.battle_state.entities.values():
            if (target.player_id == entity.player_id or
                    not target.is_alive or
                    isinstance(target, (entity.__class__.__base__))):  # Skip projectiles/areas
                continue

            distance = entity.position.distance_to(target.position)
            if distance <= self.hook_range and distance < min_distance:
                min_distance = distance
                nearest_enemy = target

        # If we found a target and aren't already hooking, start hooking
        if nearest_enemy and not self.is_hooking:
            self._start_hook(entity, nearest_enemy, current_time_ms)

    def _start_hook(self, entity, target, current_time_ms: int) -> None:
        """Start hooking a target"""
        self.is_hooking = True
        self.hook_target_id = target.id
        self.last_hook_time = current_time_ms

        # Apply hook effects
        self._apply_hook_effects(entity, target)

        # Hook effect is instantaneous for now
        # Could add projectile/hook animation here
        self.is_hooking = False

    def _apply_hook_effects(self, entity, target) -> None:
        """Apply pull and stun effects to hooked target"""
        # Buildings cannot be hooked
        from ...entities import Building
        if target.__class__.__name__ == 'Building':
            return

        # Calculate pull direction (towards fisherman)
        dx = entity.position.x - target.position.x
        dy = entity.position.y - target.position.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance > 0:
            # Normalize and apply pull
            pull_x = (dx / distance) * self.hook_pull_distance
            pull_y = (dy / distance) * self.hook_pull_distance

            # Apply pull movement
            target.position.x += pull_x
            target.position.y += pull_y

            # Apply stun
            target.apply_stun(self.hook_stun_duration_ms / 1000.0)

            # Reset attack cooldown
            target.attack_cooldown = max(target.attack_cooldown, self.hook_stun_duration_ms / 1000.0)

            # Ensure target stays within arena bounds
            target.position.x = max(0.5, min(17.5, target.position.x))
            target.position.y = max(0.5, min(31.5, target.position.y))