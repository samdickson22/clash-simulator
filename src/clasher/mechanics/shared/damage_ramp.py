from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...entities import Entity


@dataclass
class DamageRamp(BaseMechanic):
    """Mechanic that increases damage over time when attacking the same target"""
    stages: list[tuple[int, int]]  # [(time_ms, damage)]
    per_target: bool = True  # If True, ramps separately per target
    target_timers: dict = field(default_factory=dict)
    stored_original_damage: int = 0

    def on_attach(self, entity) -> None:
        """Store original damage value"""
        self.stored_original_damage = entity.damage

    def on_tick(self, entity, dt_ms: int) -> None:
        """Track time on current target"""
        if not self.per_target:
            return

        # Track time on current target
        if entity.target_id:
            self.target_timers[entity.target_id] = \
                self.target_timers.get(entity.target_id, 0) + dt_ms

    def on_attack_start(self, entity, target) -> None:
        """Apply ramped damage based on time on target"""
        if self.per_target:
            time_on_target = self.target_timers.get(target.id, 0)
        else:
            # Global timer - track time since first target engagement
            if not hasattr(self, 'global_timer'):
                self.global_timer = 0
            time_on_target = self.global_timer

        damage = self._get_damage_for_time(time_on_target)
        entity.damage = damage

    def on_attack_hit(self, entity, target) -> None:
        """Update global timer if not per-target"""
        if not self.per_target and hasattr(self, 'global_timer'):
            # Approximate time since last attack (using hit speed)
            hit_speed_ms = entity.card_stats.hit_speed or 1000
            self.global_timer += hit_speed_ms

    def _get_damage_for_time(self, time_ms: int) -> int:
        """Get damage value for given time on target"""
        for stage_time, stage_damage in reversed(self.stages):
            if time_ms >= stage_time:
                return stage_damage

        # Default to first stage damage
        return self.stages[0][1] if self.stages else self.stored_original_damage