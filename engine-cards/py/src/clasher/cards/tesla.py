from dataclasses import dataclass, field

from ..mechanics.mechanic_base import BaseMechanic


@dataclass
class HideWhenIdle(BaseMechanic):
    """Hide a building when it has had no target for the configured delay."""

    hide_delay_ms: int = 1000
    rise_time_ms: int = 1000
    _phase_ms: float = field(init=False, default=0.0)

    def allows_deployment_combat(self, entity, dt_ms: float) -> bool:
        # Native Tesla acquires and advances its first hit from the object
        # update on the final deployment frame, after projectile impacts.
        return 0 < entity.deploy_delay_remaining <= dt_ms / 1000.0 + 1e-9

    def on_attach(self, entity) -> None:
        raw = getattr(getattr(entity, "card_stats", None), "_raw_entry", {}) or {}
        character = raw.get("summonCharacterData", {}) or {}
        hide_time = character.get("hideTimeMS")
        if hide_time is None:
            hide_time = character.get("hideTimeMs")
        if hide_time is not None:
            self.hide_delay_ms = max(0, int(hide_time))
        up_time = character.get("upTimeMS")
        if up_time is None:
            up_time = character.get("upTimeMs")
        if up_time is not None:
            self.rise_time_ms = max(0, int(up_time))
        # LogicCharacter constructs the hide timer at zero. Deployment frames
        # return before updateHideTimer, so a newly placed Tesla remains on
        # the exposed side of the state boundary until post-deploy idle work
        # reaches HideTimeMs. Only the exact HideTimeMs boundary is hidden;
        # this brief initial transition is therefore targetable/damageable.
        self._phase_ms = 0.0
        entity._hidden_building = False
        entity._special_move_active = False

    def on_object_tick(self, entity, dt_ms: float) -> None:
        # Native character state drives hiding after spells and combat work.
        battle = getattr(entity, "battle_state", None)
        if battle is None:
            return
        # Freeze pauses both halves of Tesla's state machine: an underground
        # Tesla cannot pop up for a nearby enemy, and a visible Tesla cannot
        # complete its retreat while frozen.
        if entity.is_stunned():
            return
        has_target = (
            entity.target_id is not None
            or entity._attack_finish_elapsed_ms > 0
            or entity._attack_finish_tick == battle.tick
        )

        native_tick_work = entity._native_scaled_speed(
            50,
            entity.slow_multiplier,
            entity.movement_speed_buff_multiplier,
        )
        work_ms = max(0.0, float(dt_ms)) * native_tick_work / 50.0
        cycle_ms = self.hide_delay_ms + self.rise_time_ms
        old_phase = self._phase_ms
        next_phase = old_phase + work_ms

        if not has_target:
            # Advancing from the fully-up boundary hides Tesla. If a target
            # leaves during the rise half (> hide boundary), the animation
            # first completes and wraps before the hide half begins again.
            if next_phase >= self.hide_delay_ms and old_phase <= self.hide_delay_ms:
                self._phase_ms = float(self.hide_delay_ms)
            elif cycle_ms > 0:
                self._phase_ms = next_phase % cycle_ms
        else:
            # A target appearing during the hide half reverses that partial
            # animation. From the exact hidden boundary, the clock instead
            # advances through the rise half and wraps to fully up at zero.
            if old_phase < self.hide_delay_ms:
                next_phase = max(0.0, old_phase - work_ms)
            if next_phase > cycle_ms or old_phase == 0:
                self._phase_ms = 0.0
            elif cycle_ms > 0:
                self._phase_ms = next_phase % cycle_ms

        was_hidden = bool(getattr(entity, "_hidden_building", False))
        entity._hidden_building = abs(self._phase_ms - self.hide_delay_ms) <= 1e-9
        entity._special_move_active = entity._hidden_building
        if entity._hidden_building:
            entity.target_id = None
        if entity._hidden_building != was_hidden:
            # Hide/reveal runs in the object component, outside the normal
            # combat/movement cache publication points. Publish the changed
            # targetability immediately so direct component calls and later
            # object-phase consumers observe the same state in scalar and
            # accelerated engines.
            battle.sync_fast_target_entity(entity)

    def allows_effect(
        self,
        entity,
        source_kind: str | None,
        *,
        affects_hidden: bool = False,
    ) -> bool:
        del source_kind
        if not getattr(entity, "_hidden_building", False):
            return True
        return affects_hidden
