from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Troop


@dataclass
class HogRiderJump(BaseMechanic):
    """Mechanic that allows Hog Rider to jump over rivers"""
    jump_cooldown_ms: int = 2000  # Cooldown between jumps
    jump_distance: float = 2.0  # Distance jumped in tiles
    jump_height: float = 1.0  # Visual jump height

    # Internal state
    last_jump_time: int = 0
    is_jumping: bool = False
    jump_start_pos = None
    jump_target_pos = None

    def on_tick(self, entity, dt_ms: int) -> None:
        """Handle jumping logic"""
        from ..entities import Troop  # Local import to avoid circular dependency at module load

        if not isinstance(entity, Troop):
            return

        # Check if we're approaching the river (y=16)
        current_y = entity.position.y
        river_y = 16.0

        # Check if we need to jump over river
        if (not self.is_jumping and
                ((entity.player_id == 0 and current_y < river_y and current_y > 14.0) or  # Blue approaching from north
                 (entity.player_id == 1 and current_y > river_y and current_y < 18.0))):  # Red approaching from south

            # Check jump cooldown
            current_time = getattr(entity, 'battle_state', None)
            if current_time and hasattr(current_time, 'time'):
                time_ms = int(current_time.time * 1000)
                if time_ms - self.last_jump_time >= self.jump_cooldown_ms:

                    # Start jump
                    self._start_jump(entity)

        # Handle jump animation
        if self.is_jumping:
            self._update_jump(entity, dt_ms)

    def _start_jump(self, entity) -> None:
        """Initiate jump over river"""
        self.is_jumping = True
        self.jump_start_pos = (entity.position.x, entity.position.y)

        # Calculate jump target (other side of river)
        if entity.player_id == 0:  # Blue jumping to red side
            target_y = 18.0
        else:  # Red jumping to blue side
            target_y = 14.0

        self.jump_target_pos = (entity.position.x, target_y)

        # Record jump time
        if hasattr(entity, 'battle_state') and hasattr(entity.battle_state, 'time'):
            self.last_jump_time = int(entity.battle_state.time * 1000)

    def _update_jump(self, entity, dt_ms: int) -> None:
        """Update jump progress"""
        if not self.jump_target_pos:
            return

        # Simple instant jump for now
        # Could add smooth interpolation animation here
        entity.position.x = self.jump_target_pos[0]
        entity.position.y = self.jump_target_pos[1]
        self.is_jumping = False

        # Clear any pathfinding blockers
        if hasattr(entity, '_pathfind_target'):
            entity._pathfind_target = None
