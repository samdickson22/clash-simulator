from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...entities import Entity


@dataclass
class DamageRamp(BaseMechanic):
    """Mechanic that increases damage over time when attacking the same target"""
    stages: list[tuple[int, int]]  # [(time_ms, damage)]
    per_target: bool = True  # Retained for API compatibility
    target_timers: dict = field(default_factory=dict)  # legacy field
    stored_original_damage: int = 0
    _current_target_id: int | None = field(init=False, default=None)
    _current_target_ms: int = field(init=False, default=0)

    def on_attach(self, entity) -> None:
        """Store original damage value"""
        self.stored_original_damage = entity.damage

    def on_tick(self, entity, dt_ms: int) -> None:
        """Track beam lock time; reset ramp when target changes or lock breaks."""
        current_target = getattr(entity, "target_id", None)
        if not current_target:
            self._current_target_id = None
            self._current_target_ms = 0
            return
        if self._current_target_id != current_target:
            self._current_target_id = current_target
            self._current_target_ms = 0
            return
        self._current_target_ms += dt_ms

    def on_attack_start(self, entity, target) -> None:
        """Apply ramped damage based on current lock time."""
        if self._current_target_id != getattr(target, "id", None):
            self._current_target_id = getattr(target, "id", None)
            self._current_target_ms = 0
        damage = self._get_damage_for_time(self._current_target_ms)
        entity.damage = damage

    def _get_damage_for_time(self, time_ms: int) -> int:
        """Get damage value for given time on target"""
        for stage_time, stage_damage in reversed(self.stages):
            if time_ms >= stage_time:
                return stage_damage

        # Default to first stage damage
        return self.stages[0][1] if self.stages else self.stored_original_damage
