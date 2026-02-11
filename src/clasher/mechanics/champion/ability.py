from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...effects import Effect
    from ...battle import BattleState


@dataclass
class ActiveAbility:
    """Represents a champion's active ability"""
    name: str
    elixir_cost: int
    cooldown_ms: int
    duration_ms: int
    effects: List['Effect']
    last_use_time: int = field(init=False, default=0)
    is_active: bool = field(init=False, default=False)
    activation_time: int = field(init=False, default=0)

    def can_activate(self, entity, battle_state: 'BattleState') -> bool:
        """Check if ability can be activated"""
        player = battle_state.players[entity.player_id]
        time_since_use = battle_state.time * 1000 - self.last_use_time

        return (player.elixir >= self.elixir_cost and
                time_since_use >= self.cooldown_ms and
                not self.is_active)

    def activate(self, entity, battle_state: 'BattleState') -> bool:
        """Activate the champion ability"""
        if not self.can_activate(entity, battle_state):
            return False

        player = battle_state.players[entity.player_id]

        # Consume elixir
        player.elixir -= self.elixir_cost

        # Set ability state
        self.last_use_time = int(battle_state.time * 1000)
        self.is_active = True
        self.activation_time = int(battle_state.time * 1000)

        # Apply ability effects
        from ...effects import EffectContext
        from ...arena import Position
        context = EffectContext(
            battle_state=battle_state,
            caster_id=entity.player_id,
            target_position=Position(entity.position.x, entity.position.y)
        )

        for effect in self.effects:
            effect.apply(context)

        return True

    def update(self, entity, dt_ms: int, battle_state: 'BattleState') -> None:
        """Update ability state (handle duration expiration)"""
        if self.is_active:
            time_active = battle_state.time * 1000 - self.activation_time
            if time_active >= self.duration_ms:
                self.is_active = False
                # Could add duration expiration effects here

    def get_cooldown_remaining(self, battle_state: 'BattleState') -> int:
        """Get remaining cooldown time in milliseconds"""
        time_since_use = battle_state.time * 1000 - self.last_use_time
        return max(0, self.cooldown_ms - time_since_use)

    def get_duration_remaining(self, battle_state: 'BattleState') -> int:
        """Get remaining duration time in milliseconds"""
        if not self.is_active:
            return 0
        time_active = battle_state.time * 1000 - self.activation_time
        return max(0, self.duration_ms - time_active)


@dataclass
class ChampionAbilityMechanic(BaseMechanic):
    """Base mechanic for champions with active abilities"""
    ability: ActiveAbility

    def on_tick(self, entity, dt_ms: int) -> None:
        """Update ability state"""
        if hasattr(entity, 'battle_state'):
            self.ability.update(entity, dt_ms, entity.battle_state)

    def activate_ability(self, entity) -> bool:
        """Try to activate the champion's ability"""
        if hasattr(entity, 'battle_state'):
            return self.ability.activate(entity, entity.battle_state)
        return False

    def can_activate_ability(self, entity) -> bool:
        """Check if ability can be activated"""
        if hasattr(entity, 'battle_state'):
            return self.ability.can_activate(entity, entity.battle_state)
        return False

    def get_ability_cooldown(self, entity) -> int:
        """Get remaining cooldown time"""
        if hasattr(entity, 'battle_state'):
            return self.ability.get_cooldown_remaining(entity.battle_state)
        return 0

    def get_ability_duration(self, entity) -> int:
        """Get remaining duration time"""
        if hasattr(entity, 'battle_state'):
            return self.ability.get_duration_remaining(entity.battle_state)
        return 0
