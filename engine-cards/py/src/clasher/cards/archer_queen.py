from ..mechanics.champion.ability import ChampionAbilityMechanic, ActiveAbility
from ..kinematics import logic_time_milliseconds


class ArcherQueenCloak(ChampionAbilityMechanic):
    """Implements the Archer Queen's Cloak ability with temporary stealth and burst damage."""

    def __init__(
        self,
        attack_speed_multiplier: float = 2.8,
        movement_speed_multiplier: float = 0.75,
        cooldown_ms: int = 17000,
        duration_ms: int = 3500,
        cast_time_ms: int = 933,
        trigger_delay_ms: int = 200,
    ) -> None:
        ability = ActiveAbility(
            name="Cloak",
            elixir_cost=1,
            cooldown_ms=cooldown_ms,
            duration_ms=duration_ms,
            effects=[],
        )
        super().__init__(ability)
        self.attack_speed_multiplier = attack_speed_multiplier
        self.movement_speed_multiplier = movement_speed_multiplier
        self.duration_ms = duration_ms
        self.cast_time_ms = cast_time_ms
        self.trigger_delay_ms = trigger_delay_ms
        self._original_movement_mode_multiplier = None
        self._cloak_pending_until = None
        self._cast_lock_until = None

    def on_attach(self, entity) -> None:
        entity._stealth_until = 0
        raw = getattr(entity.card_stats, "_raw_entry", {}) or {}
        char_data = raw.get("summonCharacterData", {}) or {}
        ability_data = char_data.get("abilityData", {}) or {}
        buff_data = ability_data.get("buffData", {}) or {}
        self.ability.elixir_cost = int(ability_data.get("manaCost", self.ability.elixir_cost))
        self.ability.cooldown_ms = int(ability_data.get("cooldown", self.ability.cooldown_ms))
        self.duration_ms = int(ability_data.get("buffTime", self.duration_ms))
        self.ability.duration_ms = self.duration_ms
        self.cast_time_ms = int(ability_data.get("castTime", self.cast_time_ms))
        self.trigger_delay_ms = int(
            ability_data.get("triggerDelay", self.trigger_delay_ms)
        )
        hit_speed_percent = buff_data.get("hitSpeedMultiplier")
        if hit_speed_percent is not None:
            self.attack_speed_multiplier = float(hit_speed_percent) / 100.0
        speed_percent = buff_data.get("speedMultiplier")
        if speed_percent is not None:
            self.movement_speed_multiplier = max(0.0, 1.0 + float(speed_percent) / 100.0)

    def activate_ability(self, entity) -> bool:
        if super().activate_ability(entity):
            now_ms = logic_time_milliseconds(entity.battle_state.time)
            self._cloak_pending_until = now_ms + self.trigger_delay_ms
            self._cast_lock_until = now_ms + self.cast_time_ms
            # TriggerDelay schedules the buff within the longer casting
            # animation. Buff duration and the later cooldown begin at the
            # trigger, while movement/attacks remain locked for CastTime.
            self.ability.activation_time = self._cloak_pending_until
            return True
        return False

    def on_tick(self, entity, dt_ms: int) -> None:
        super().on_tick(entity, dt_ms)
        if self._cloak_pending_until is not None:
            now_ms = logic_time_milliseconds(entity.battle_state.time)
            if now_ms >= self._cloak_pending_until:
                self._cloak_pending_until = None
                self._apply_cloak(entity)
        if self._cast_lock_until is not None:
            now_ms = logic_time_milliseconds(entity.battle_state.time)
            if now_ms >= self._cast_lock_until:
                self._cast_lock_until = None
        if not self.ability.is_active and self._original_movement_mode_multiplier is not None:
            self._remove_cloak(entity)

    def blocks_combat_actions(self, entity) -> bool:
        return self._cast_lock_until is not None

    def on_death(self, entity) -> None:
        self._cloak_pending_until = None
        self._cast_lock_until = None
        self.ability.is_active = False
        if self._original_movement_mode_multiplier is not None:
            self._remove_cloak(entity)

    def _apply_cloak(self, entity) -> None:
        self._original_movement_mode_multiplier = getattr(
            entity,
            "movement_mode_multiplier",
            1.0,
        )
        entity.attack_mode_multiplier = self.attack_speed_multiplier
        set_movement_mode = getattr(entity, "set_movement_mode_multiplier", None)
        if callable(set_movement_mode):
            set_movement_mode(
                self._original_movement_mode_multiplier
                * self.movement_speed_multiplier
            )
        if hasattr(entity, 'battle_state'):
            now_ms = logic_time_milliseconds(entity.battle_state.time)
        else:
            now_ms = 0
        entity._stealth_until = now_ms + self.duration_ms

    def _remove_cloak(self, entity) -> None:
        if self._original_movement_mode_multiplier is not None:
            entity.set_movement_mode_multiplier(
                self._original_movement_mode_multiplier
            )
        entity.attack_mode_multiplier = 1.0
        entity._stealth_until = 0
        self._original_movement_mode_multiplier = None
