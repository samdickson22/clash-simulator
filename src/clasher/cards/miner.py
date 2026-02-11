from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Troop


@dataclass
class MinerTunnel(BaseMechanic):
    """Mechanic for Miner's tunnel ability to deploy anywhere"""
    tunnel_cooldown_ms: int = 1000  # Cooldown after tunneling
    tunnel_duration_ms: int = 500  # Time spent underground
    tunnel_move_speed: float = 120.0  # Speed while tunneling

    # Internal state
    is_tunneling: bool = field(init=False, default=False)
    tunnel_start_time: int = field(init=False, default=0)
    tunnel_target_pos = None
    stored_original_speed: float = field(init=False, default=0)
    has_tunneled_this_deploy: bool = field(init=False, default=False)

    def on_attach(self, entity) -> None:
        """Store original speed"""
        self.stored_original_speed = getattr(entity, 'speed', 60.0)

    def on_spawn(self, entity) -> None:
        """Reset tunnel state on spawn"""
        self.has_tunneled_this_deploy = False
        self.is_tunneling = False

    def on_tick(self, entity, dt_ms: int) -> None:
        """Handle tunneling logic"""
        if not hasattr(entity, 'battle_state'):
            return

        current_time_ms = int(entity.battle_state.time * 1000)

        # Check if we should start tunneling to nearest target
        if (not self.is_tunneling and
                not self.has_tunneled_this_deploy and
                entity.target_id):

            target = entity.battle_state.entities.get(entity.target_id)
            if target:
                distance = entity.position.distance_to(target.position)
                # Start tunneling if target is far away
                if distance > 5.0:  # Tunnel if target is more than 5 tiles away
                    self._start_tunnel(entity, target, current_time_ms)

        # Update tunneling state
        if self.is_tunneling:
            self._update_tunnel(entity, dt_ms, current_time_ms)

    def _start_tunnel(self, entity, target, current_time_ms: int) -> None:
        """Start tunneling towards target"""
        self.is_tunneling = True
        self.tunnel_start_time = current_time_ms
        self.tunnel_target_pos = (target.position.x, target.position.y)

        # Apply tunnel speed
        entity.speed = self.tunnel_move_speed

        # Apply temporary invincibility while tunneling
        # This could be handled by modifying take_damage method

    def _update_tunnel(self, entity, dt_ms: int, current_time_ms: int) -> None:
        """Update tunneling progress"""
        if not self.tunnel_target_pos:
            self._end_tunnel(entity)
            return

        target_x, target_y = self.tunnel_target_pos
        dx = target_x - entity.position.x
        dy = target_y - entity.position.y
        distance = (dx * dx + dy * dy) ** 0.5

        # Check if we've tunneled long enough or reached target
        if (current_time_ms - self.tunnel_start_time >= self.tunnel_duration_ms or
                distance < 1.0):

            # Instantly move to target location
            entity.position.x = target_x
            entity.position.y = target_y
            self._end_tunnel(entity)

    def _end_tunnel(self, entity) -> None:
        """End tunneling and restore normal state"""
        self.is_tunneling = False
        self.has_tunneled_this_deploy = True
        entity.speed = self.stored_original_speed

        # Remove temporary invincibility
        self.tunnel_target_pos = None

        # Apply brief stun to enemies at emergence location (area effect)
        if hasattr(entity, 'battle_state'):
            self._apply_emergence_effect(entity)

    def _apply_emergence_effect(self, entity) -> None:
        """Apply area effect when miner emerges from tunnel"""
        emergence_radius = 2.0  # tiles
        stun_duration = 0.5  # seconds

        for target in list(entity.battle_state.entities.values()):
            if (target.player_id == entity.player_id or
                    not target.is_alive or
                    target == entity):
                continue

            distance = entity.position.distance_to(target.position)
            if distance <= emergence_radius:
                # Apply brief stun and damage
                target.apply_stun(stun_duration)
                target.take_damage(50)  # Emergence damage

    def take_damage_while_tunneling(self, entity, damage: float) -> bool:
        """Check if entity should take damage while tunneling"""
        # Return False if invincible while tunneling, True if damage should be applied
        return not self.is_tunneling