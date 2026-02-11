from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class BombTowerDeathBomb(BaseMechanic):
    """Bomb Tower drops a bomb on death that explodes after delay"""
    explosion_radius_tiles: float = 3.0  # 3 tile radius
    explosion_delay_ms: int = 3000  # 3 second delay
    damage_scale: float = 1.0  # Damage scale for death bomb

    def on_death(self, entity: 'Entity') -> None:
        """Spawn bomb on death"""
        if not hasattr(entity, 'battle_state'):
            return

        battle_state = entity.battle_state

        # Create death bomb entity
        bomb_entity = self._create_death_bomb(entity)
        if bomb_entity:
            battle_state.add_entity(bomb_entity)

    def _create_death_bomb(self, parent_entity: 'Entity') -> 'Entity':
        """Create the death bomb entity"""
        if not hasattr(parent_entity, 'battle_state'):
            return None

        # Import here to avoid circular imports
        from ..entities import Projectile
        from ..arena import Position
        from ..card_types import CardStatsCompat
        from ..factory.card_factory import create_card_definition

        # Create a simple entity for the death bomb
        class DeathBomb(Projectile):
            def __init__(self, position, player_id, damage, lifetime_ms):
                # Create minimal card definition for the bomb
                card_def = create_card_definition(
                    name="DeathBomb",
                    kind="troop",
                    rarity="Common",
                    elixir=0,
                    raw={"damage": damage}
                )
                card_stats = CardStatsCompat(card_def)

                super().__init__(
                    id=-1,  # Temporary ID
                    position=position,
                    player_id=player_id,
                    card_stats=card_stats,
                    hitpoints=1,
                    max_hitpoints=1,
                    damage=damage,
                    range=0,
                    sight_range=0
                )
                self.lifetime_ms = lifetime_ms
                self.creation_time = 0
                self.explosion_damage = damage

            def update(self, dt: float, battle_state: 'BattleState') -> None:
                """Update bomb - explode after delay"""
                if not self.is_alive:
                    return

                self.creation_time += dt
                if self.creation_time * 1000 >= self.lifetime_ms:
                    self._explode_bomb(battle_state)
                    self.is_alive = False

            def _explode_bomb(self, battle_state: 'BattleState') -> None:
                """Handle explosion"""
                explosion_radius_units = 3.0 * 1000  # 3 tiles in game units

                for target in list(battle_state.entities.values()):
                    if (target.player_id == self.player_id or
                        not target.is_alive or
                        target == self):
                        continue

                    distance = self.position.distance_to(target.position)
                    if distance <= explosion_radius_units:
                        target.take_damage(self.explosion_damage)

        # Create death bomb
        bomb = DeathBomb(
            position=parent_entity.position.copy(),
            player_id=parent_entity.player_id,
            damage=(parent_entity.damage or 0) * self.damage_scale,
            lifetime_ms=self.explosion_delay_ms
        )

        return bomb

    

@dataclass
class BombTowerBomb(BaseMechanic):
    """Controls the bomb projectile behavior for Bomb Tower"""
    bomb_lifetime_ms: int = 2000  # Bomb lifetime before exploding
    explosion_radius_tiles: float = 2.0  # Individual bomb explosion radius

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        """Override attack to create special bomb projectile"""
        # This would be called when Bomb Tower attacks
        # The bomb should not pathfind like a normal projectile
        pass

    def create_bomb_projectile(self, tower: 'Entity', target_pos, damage: float) -> 'Entity':
        """Create a bomb projectile that explodes on impact or timeout"""
        from ..entities import Projectile

        bomb = Projectile(
            position=tower.position.copy(),
            owner_id=tower.player_id,
            damage=damage,
            speed=500,  # Bomb projectile speed
            lifetime_ms=self.bomb_lifetime_ms,
            projectile_type="bomb_tower_bomb"
        )

        # Set target position (bomb should go to target area, not chase)
        bomb.target_position = target_pos

        return bomb