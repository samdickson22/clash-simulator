from dataclasses import dataclass, field

from ..mechanic_base import BaseMechanic
from ...balance import LOGIC_CHARACTER_CONTINUOUS_DAMAGE_ATTACK_CLOSER


@dataclass
class DamageRamp(BaseMechanic):
    """Mechanic that increases damage over time when attacking the same target"""
    # LOGIC_CHARACTER_CONTINUOUS_DAMAGE_ATTACK_CLOSER. Native subtracts this
    # only from a moving character's attack range while it approaches a new
    # continuous-damage lock; connected beams and buildings use full range.
    stages: list[tuple[int, int]]  # [(time_ms, damage)]
    per_target: bool = True  # Retained for API compatibility
    target_timers: dict = field(default_factory=dict)  # legacy field
    stored_original_damage: int = 0
    _current_target_id: int | None = field(init=False, default=None)
    _current_target_ms: float = field(init=False, default=0.0)

    def on_attach(self, entity) -> None:
        """Store original damage value"""
        self.stored_original_damage = entity.damage
        scaler = getattr(getattr(entity, "card_stats", None), "get_scaled_stat", None)
        if self.stages and callable(scaler):
            # Each stage is a distinct serialized damage stat. Scaling later
            # stages through the already-truncated first stage compounds its
            # rounding error (especially for Inferno's large final stage).
            self.stages = [
                (time_ms, int(scaler(damage)))
                for time_ms, damage in self.stages
            ]

    def on_target_observed(self, entity, target_entity, dt_ms: int) -> None:
        """Track beam lock time; reset ramp when target changes or lock breaks."""
        current_target = getattr(target_entity, "id", None)
        beam_connected = bool(
            current_target is not None
            and target_entity is not None
            and not entity.is_stunned()
            and entity.can_attack_target(
                target_entity,
                is_current_target=True,
            )
            and entity.is_within_attack_engagement_reach(target_entity)
            and target_entity.can_receive_effect(
                getattr(getattr(entity, "card_stats", None), "name", None)
            )
        )
        if not beam_connected:
            self._current_target_id = None
            self._current_target_ms = 0.0
            entity.damage = self._get_damage_for_time(0)
            return
        if self._current_target_id != current_target:
            self._current_target_id = current_target
            self._current_target_ms = 0.0
            entity.damage = self._get_damage_for_time(0)
        # Native updateHitTimer advances on the acquisition frame before
        # variable damage is chosen for a hit that becomes ready this frame.
        get_attack_rate = getattr(entity, "get_attack_rate_multiplier", None)
        attack_rate = (
            float(get_attack_rate())
            if callable(get_attack_rate)
            else 1.0
        )
        self._current_target_ms += dt_ms * max(0.0, attack_rate)

    def allows_target(self, entity, target) -> bool:
        """Reject recipients that cannot accept the continuous channel.

        Damage immunity does not generally make a character untargetable.
        Continuous-damage weapons are different: their connected channel
        drops and the attacker is free to acquire another target while the
        recipient rejects the beam.
        """
        source_kind = getattr(
            getattr(entity, "card_stats", None),
            "name",
            None,
        )
        return target.can_receive_effect(source_kind)

    def attack_approach_range_reduction(self, entity, target_entity) -> float:
        """Make only mobile, not-yet-connected channels approach closer."""
        if (
            getattr(entity, "entity_kind", 4) != 0
            or self._current_target_id == getattr(target_entity, "id", None)
        ):
            return 0.0
        return LOGIC_CHARACTER_CONTINUOUS_DAMAGE_ATTACK_CLOSER / 1000.0

    def on_attack_start(self, entity, target) -> None:
        """Apply ramped damage based on current lock time."""
        if self._current_target_id != getattr(target, "id", None):
            self._current_target_id = getattr(target, "id", None)
            self._current_target_ms = 0.0
        damage = self._get_damage_for_time(self._current_target_ms)
        entity.damage = damage

    def on_shield_lost(self, entity, shielded_entity) -> None:
        """Reset a connected beam when its retained target loses a shield."""
        if (
            getattr(entity, "target_id", None)
            == getattr(shielded_entity, "id", None)
            and self._current_target_id
            == getattr(shielded_entity, "id", None)
        ):
            self._current_target_ms = 0.0
            entity.damage = self._get_damage_for_time(0)

    def handle_stun(self, entity) -> None:
        """Stuns interrupt an Inferno beam and reset its damage stage."""
        self._reset_lock(entity)

    def on_knockback(self, entity) -> None:
        """Physical displacement breaks an Inferno beam just like a stun."""
        self._reset_lock(entity)

    def on_forced_movement(
        self,
        entity,
        source_kind: str | None,
        movement_kind: str,
    ) -> None:
        """Non-knockback displacement also breaks the connected beam."""
        if movement_kind != "knockback":
            self._reset_lock(entity)

    def _reset_lock(self, entity) -> None:
        self._current_target_id = None
        self._current_target_ms = 0.0
        entity.target_id = None
        entity.damage = self._get_damage_for_time(0)

    def _get_damage_for_time(self, time_ms: float) -> int:
        """Get damage value for given time on target"""
        for stage_time, stage_damage in reversed(self.stages):
            if time_ms >= stage_time:
                return stage_damage

        # Default to first stage damage
        return self.stages[0][1] if self.stages else self.stored_original_damage
