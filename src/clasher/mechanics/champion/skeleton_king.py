from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .ability import ChampionAbilityMechanic, ActiveAbility
from ...effects import SpawnUnits

if TYPE_CHECKING:
    from ...battle import BattleState


@dataclass
class SkeletonKingSoulCollector(ChampionAbilityMechanic):
    """Skeleton King's soul collection mechanic and summon skeletons ability"""
    soul_collection_radius: float = 5.0  # Radius for soul collection
    souls_per_activation: int = 20  # Souls needed for ability
    max_souls: int = 30  # Maximum souls that can be stored

    # Internal state
    souls_collected: int = field(init=False, default=0)

    def __post_init__(self):
        """Initialize the Skeleton King's ability"""
        ability = ActiveAbility(
            name="Summon Skeletons",
            elixir_cost=3,
            cooldown_ms=15000,  # 15 seconds
            duration_ms=1000,  # Instant effect
            effects=[
                SpawnUnits(
                    unit_name="Skeleton",
                    count=15,  # Spawn 15 skeletons
                    radius_tiles=2.0
                )
            ]
        )
        super().__init__(ability)

    def on_tick(self, entity, dt_ms: int) -> None:
        """Check for nearby deaths and collect souls"""
        super().on_tick(entity, dt_ms)

        if not hasattr(entity, 'battle_state'):
            return

        # Check for nearby deaths and collect souls
        for other in entity.battle_state.entities.values():
            if (other.player_id == entity.player_id or  # Don't collect from allies
                    other.is_alive or  # Only collect from dead entities
                    other == entity):  # Don't collect from self
                continue

            distance = entity.position.distance_to(other.position)
            if distance <= self.soul_collection_radius:
                # Collect soul
                self.souls_collected = min(self.souls_collected + 1, self.max_souls)

                # Visual effect could be added here

        # Update ability availability based on souls
        self._update_ability_availability(entity)

    def _update_ability_availability(self, entity) -> None:
        """Update ability availability based on soul count"""
        # Modify ability cost or cooldown based on souls
        if self.souls_collected >= self.souls_per_activation:
            # Ability is ready - could reduce cooldown or cost
            self.ability.elixir_cost = max(1, 3 - (self.souls_collected // 10))
        else:
            # Need more souls
            self.ability.elixir_cost = 3

    def activate_ability(self, entity) -> bool:
        """Override to handle soul consumption"""
        if self.souls_collected < self.souls_per_activation:
            return False  # Not enough souls

        # Activate the ability
        if super().activate_ability(entity):
            # Consume souls
            self.souls_collected = max(0, self.souls_collected - self.souls_per_activation)
            return True

        return False

    def on_death(self, entity) -> None:
        """Handle soul drop on death"""
        super().on_death(entity)

        # Drop some souls as skeletons when killed
        if self.souls_collected > 0:
            souls_to_drop = min(self.souls_collected // 2, 10)  # Drop up to 10 skeletons
            if souls_to_drop > 0 and hasattr(entity, 'battle_state'):
                self._drop_souls_as_skeletons(entity, souls_to_drop)

    def _drop_souls_as_skeletons(self, entity, count: int) -> None:
        """Spawn skeleton minions from dropped souls"""
        battle_state = entity.battle_state

        # Get skeleton stats
        skeleton_stats = battle_state.card_loader.get_card("Skeleton")
        if not skeleton_stats:
            return

        import math
        import random
        from ...arena import Position

        # Spawn skeletons in a circle around death position
        for i in range(count):
            angle = (2 * math.pi * i) / count
            spawn_x = entity.position.x + 1.5 * math.cos(angle)
            spawn_y = entity.position.y + 1.5 * math.sin(angle)

            spawn_position = Position(spawn_x, spawn_y)
            battle_state._spawn_troop(spawn_position, entity.player_id, skeleton_stats)

    def get_soul_count(self) -> int:
        """Get current soul count"""
        return self.souls_collected

    def get_souls_needed_for_ability(self) -> int:
        """Get number of souls needed for next ability use"""
        return max(0, self.souls_per_activation - self.souls_collected)