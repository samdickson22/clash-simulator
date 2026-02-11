from dataclasses import dataclass
from typing import TYPE_CHECKING, Set

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ElectroDragonChainLightning(BaseMechanic):
    """Electro Dragon's bolt chains to additional enemies after each hit."""
    chain_range: float = 4.5
    max_bounces: int = 2
    damage_decay: float = 0.7
    stun_duration_ms: int = 300

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        visited: Set[int] = {target.id}
        previous = target
        damage = entity.damage * self.damage_decay
        bounces = 0
        while bounces < self.max_bounces and damage > 0:
            candidate = self._find_next_target(battle_state, entity.player_id, visited, previous.position)
            if not candidate:
                break
            visited.add(candidate.id)
            candidate.take_damage(damage)
            candidate.apply_stun(self.stun_duration_ms / 1000.0)
            previous = candidate
            damage *= self.damage_decay
            bounces += 1
        else:
            # Apply the first bounce effects if at least one candidate exists
            pass

    def _find_next_target(self, battle_state, player_id: int, visited: Set[int], origin) -> 'Entity':
        best = None
        best_distance = self.chain_range + 1.0
        for other in list(battle_state.entities.values()):
            if other.player_id == player_id or not other.is_alive or other.id in visited:
                continue
            distance = origin.distance_to(other.position)
            if distance <= self.chain_range and distance < best_distance:
                best_distance = distance
                best = other
        return best
