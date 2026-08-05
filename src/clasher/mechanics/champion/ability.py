from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from ..mechanic_base import BaseMechanic
from ...kinematics import logic_time_milliseconds

if TYPE_CHECKING:
    from ...card_types import Effect
    from ...battle import BattleState


@dataclass
class ActiveAbility:
    """Represents a champion's active ability"""
    name: str
    elixir_cost: int
    cooldown_ms: int
    duration_ms: int
    effects: List['Effect']
    # Champion abilities are available on their first deployment; cooldown is
    # measured from an actual activation, not from match start.
    last_use_time: int = field(init=False, default=-10**12)
    is_active: bool = field(init=False, default=False)
    activation_time: int = field(init=False, default=0)

    def can_activate(self, entity, battle_state: 'BattleState') -> bool:
        """Check if ability can be activated"""
        player = battle_state.players[entity.player_id]
        now_ms = logic_time_milliseconds(battle_state.time)
        # Clash starts a Champion ability's cooldown after its active duration
        # ends.  ``activation_time`` is the effect start (and can therefore be
        # later than the button press for abilities with a cast time).
        never_used = self.last_use_time <= -10**11
        cooldown_ready = never_used or now_ms >= (
            self.activation_time + self.duration_ms + self.cooldown_ms
        )
        is_stunned = getattr(entity, "is_stunned", None)

        return (player.elixir >= self.elixir_cost and
                getattr(entity, "is_alive", True) and
                not (callable(is_stunned) and is_stunned()) and
                not getattr(entity, "placement_pending", False) and
                getattr(entity, "deploy_delay_remaining", 0.0) <= 1e-9 and
                cooldown_ready and
                not self.is_active)

    def activate(self, entity, battle_state: 'BattleState') -> bool:
        """Activate the champion ability"""
        if not self.can_activate(entity, battle_state):
            return False

        player = battle_state.players[entity.player_id]

        # Consume elixir
        player.elixir -= self.elixir_cost

        # Set ability state
        self.last_use_time = logic_time_milliseconds(battle_state.time)
        self.is_active = True
        self.activation_time = logic_time_milliseconds(battle_state.time)

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
            time_active = (
                logic_time_milliseconds(battle_state.time)
                - self.activation_time
            )
            if time_active >= self.duration_ms:
                self.is_active = False
                # Could add duration expiration effects here

    def get_cooldown_remaining(self, battle_state: 'BattleState') -> int:
        """Get remaining cooldown time in milliseconds"""
        if self.last_use_time <= -10**11:
            return 0
        now_ms = logic_time_milliseconds(battle_state.time)
        cooldown_start = self.activation_time + self.duration_ms
        # During the cast/active window the cooldown has not started yet, so
        # the full cooldown remains.  This also keeps the normalized HUD value
        # bounded and meaningful while the ability is active.
        if now_ms < cooldown_start:
            return self.cooldown_ms
        return max(0, self.cooldown_ms - (now_ms - cooldown_start))

    def get_duration_remaining(self, battle_state: 'BattleState') -> int:
        """Get remaining duration time in milliseconds"""
        if not self.is_active:
            return 0
        time_active = (
            logic_time_milliseconds(battle_state.time)
            - self.activation_time
        )
        if time_active < 0:
            return 0
        return max(0, self.duration_ms - time_active)

    def cancel_before_effect(self) -> None:
        """Cancel an interrupted cast without starting its cooldown.

        The activation cost was already committed by ``activate``. A cast
        interrupted before its payload occurs becomes available again but
        does not refund that cost.
        """
        self.is_active = False
        self.activation_time = 0
        self.last_use_time = -10**12

    def reset_cooldown(self) -> None:
        """Make the ability ready after Champion ownership transfers.

        An already-running effect belongs to the troop that cast it and keeps
        its normal duration. Only the cooldown is reset when another copy is
        placed or the current ability owner dies.
        """
        self.last_use_time = -10**12


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
            battle_state = entity.battle_state
            if not battle_state.is_champion_ability_owner(entity):
                return False
            return self.ability.activate(entity, battle_state)
        return False

    def can_activate_ability(self, entity) -> bool:
        """Check if ability can be activated"""
        if hasattr(entity, 'battle_state'):
            battle_state = entity.battle_state
            return (
                battle_state.is_champion_ability_owner(entity)
                and self.ability.can_activate(entity, battle_state)
            )
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
