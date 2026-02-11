from dataclasses import dataclass
from typing import TYPE_CHECKING, Set

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ElectroSpiritChain(BaseMechanic):
    """Implements Electro Spirit's bouncing zap chain."""
    chain_range: float = 4.0
    max_targets: int = 9
    stun_duration_ms: int = 500
    damage_decay: float = 0.9

    def on_spawn(self, entity: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        visited: Set[int] = set()
        origin = entity.position
        damage = entity.damage
        current_pos = origin
        for _ in range(self.max_targets):
            target = self._find_next_target(battle_state, entity.player_id, visited, current_pos)
            if not target:
                break
            visited.add(target.id)
            target.take_damage(damage)
            target.apply_stun(self.stun_duration_ms / 1000.0)
            current_pos = target.position
            damage *= self.damage_decay

    def _find_next_target(self, battle_state, player_id: int, visited: Set[int], origin) -> 'Entity':
        best = None
        best_distance = self.chain_range + 1.0
        for other in battle_state.entities.values():
            if other.player_id == player_id or not other.is_alive or other.id in visited:
                continue
            distance = origin.distance_to(other.position)
            if distance <= self.chain_range and distance < best_distance:
                best_distance = distance
                best = other
        return best

