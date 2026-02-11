from ..mechanics.champion.ability import ChampionAbilityMechanic, ActiveAbility


class ArcherQueenCloak(ChampionAbilityMechanic):
    """Implements the Archer Queen's Cloak ability with temporary stealth and burst damage."""

    def __init__(
        self,
        damage_multiplier: float = 1.8,
        speed_multiplier: float = 1.6,
        cooldown_ms: int = 11000,
        duration_ms: int = 3000,
    ) -> None:
        ability = ActiveAbility(
            name="Cloak",
            elixir_cost=1,
            cooldown_ms=cooldown_ms,
            duration_ms=duration_ms,
            effects=[],
        )
        super().__init__(ability)
        self.damage_multiplier = damage_multiplier
        self.speed_multiplier = speed_multiplier
        self.duration_ms = duration_ms
        self._original_damage = None
        self._original_speed = None

    def on_attach(self, entity) -> None:
        entity._stealth_until = 0

    def activate_ability(self, entity) -> bool:
        if super().activate_ability(entity):
            self._apply_cloak(entity)
            return True
        return False

    def on_tick(self, entity, dt_ms: int) -> None:
        super().on_tick(entity, dt_ms)
        if not self.ability.is_active and self.can_activate_ability(entity) and getattr(entity, "target_id", None):
            self.activate_ability(entity)
        if not self.ability.is_active and self._original_damage is not None:
            self._remove_cloak(entity)

    def on_death(self, entity) -> None:
        if self._original_damage is not None:
            self._remove_cloak(entity)

    def _apply_cloak(self, entity) -> None:
        self._original_damage = entity.damage
        self._original_speed = getattr(entity, 'speed', None)
        entity.damage = self._original_damage * self.damage_multiplier
        if self._original_speed is not None:
            entity.speed = self._original_speed * self.speed_multiplier
        if hasattr(entity, 'battle_state'):
            now_ms = int(entity.battle_state.time * 1000)
        else:
            now_ms = 0
        entity._stealth_until = now_ms + self.duration_ms

    def _remove_cloak(self, entity) -> None:
        entity.damage = self._original_damage
        if self._original_speed is not None:
            entity.speed = self._original_speed
        entity._stealth_until = 0
        self._original_damage = None
        self._original_speed = None
