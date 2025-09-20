from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Troop


@dataclass
class BanditDash(BaseMechanic):
    """Mechanic for Bandit's dash attack with invincibility frames"""
    dash_distance: float = 4.0  # Distance to dash
    dash_speed_multiplier: float = 2.0  # Speed during dash
    invincibility_duration_ms: int = 500  # Invincibility frames after dash
    dash_cooldown_ms: int = 3000  # Cooldown between dashes

    # Internal state
    is_dashing: bool = field(init=False, default=False)
    dash_start_pos = None
    dash_target_pos = None
    last_dash_time: int = field(init=False, default=0)
    invincibility_end_time: int = field(init=False, default=0)
    stored_original_speed: float = field(init=False, default=0)

    def on_attach(self, entity) -> None:
        """Store original speed"""
        self.stored_original_speed = getattr(entity, 'speed', 60.0)

    def on_tick(self, entity, dt_ms: int) -> None:
        """Handle dash logic and invincibility"""
        current_time_ms = 0
        if hasattr(entity, 'battle_state') and hasattr(entity.battle_state, 'time'):
            current_time_ms = int(entity.battle_state.time * 1000)

        # Check invincibility expiration
        if current_time_ms > self.invincibility_end_time:
            # Remove invincibility (could be indicated by visual effect)
            pass

        # Check if we should initiate dash
        if (not self.is_dashing and
                entity.target_id and
                current_time_ms - self.last_dash_time >= self.dash_cooldown_ms):

            # Check if target is in range for dash
            target = entity.battle_state.entities.get(entity.target_id) if hasattr(entity, 'battle_state') else None
            if target and entity.can_attack_target(target):
                # Don't dash if already in attack range
                distance = entity.position.distance_to(target.position)
                if distance > entity.range * 1.5:  # Dash if target is far
                    self._start_dash(entity, target)

        # Update dash movement
        if self.is_dashing:
            self._update_dash(entity, dt_ms)

    def _start_dash(self, entity, target) -> None:
        """Initiate dash towards target"""
        self.is_dashing = True
        self.dash_start_pos = (entity.position.x, entity.position.y)

        # Calculate dash target position (closer to target)
        dx = target.position.x - entity.position.x
        dy = target.position.y - entity.position.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance > 0:
            # Move dash_distance towards target, but don't overshoot
            dash_ratio = min(self.dash_distance / distance, 1.0)
            target_x = entity.position.x + dx * dash_ratio
            target_y = entity.position.y + dy * dash_ratio
            self.dash_target_pos = (target_x, target_y)
        else:
            self.dash_target_pos = (entity.position.x, entity.position.y)

        # Apply speed boost
        entity.speed = self.stored_original_speed * self.dash_speed_multiplier

        # Set invincibility
        current_time_ms = int(entity.battle_state.time * 1000)
        self.invincibility_end_time = current_time_ms + self.invincibility_duration_ms

        # Record dash time
        self.last_dash_time = current_time_ms

    def _update_dash(self, entity, dt_ms: int) -> None:
        """Update dash movement"""
        if not self.dash_target_pos:
            self.is_dashing = False
            return

        target_x, target_y = self.dash_target_pos
        dx = target_x - entity.position.x
        dy = target_y - entity.position.y
        remaining_distance = (dx * dx + dy * dy) ** 0.5

        if remaining_distance < 0.1:  # Reached target
            entity.position.x = target_x
            entity.position.y = target_y
            self.is_dashing = False
            entity.speed = self.stored_original_speed  # Restore normal speed
        else:
            # Continue dashing
            # Movement will be handled by normal Troop.update with boosted speed
            pass

    def take_damage_during_dash(self, entity, damage: float) -> bool:
        """Check if entity should take damage during dash"""
        current_time_ms = 0
        if hasattr(entity, 'battle_state') and hasattr(entity.battle_state, 'time'):
            current_time_ms = int(entity.battle_state.time * 1000)

        # Return True if damage should be applied, False if invincible
        return current_time_ms > self.invincibility_end_time