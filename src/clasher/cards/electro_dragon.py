from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import logic_speed_to_tiles_per_second

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ElectroDragonChainLightning(BaseMechanic):
    """Electro Dragon's bolt chains to additional enemies after each hit."""
    chain_range: float = 4.0
    max_bounces: int = 2
    damage_decay: float = 1.0
    stun_duration_ms: int = 300
    projectile_speed_tiles_per_second: float = logic_speed_to_tiles_per_second(2000.0)

    def on_attach(self, entity: 'Entity') -> None:
        projectile = getattr(entity.card_stats, "projectile_data", {}) or {}
        self.chain_range = float(projectile.get("chainedHitRadius", 4000) or 4000) / 1000.0
        total_targets = int(projectile.get("chainedHitCount", self.max_bounces + 1) or 1)
        self.max_bounces = max(0, total_targets - 1)
        self.stun_duration_ms = int(
            projectile.get("buffTime", self.stun_duration_ms) or self.stun_duration_ms
        )
        self.projectile_speed_tiles_per_second = logic_speed_to_tiles_per_second(
            float(projectile.get("speed", 2000) or 2000)
        )

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        from ..arena import Position
        from ..entities import ChainLightning

        battle_state = entity.battle_state
        chain = ChainLightning(
            id=battle_state.next_entity_id,
            position=Position(target.position.x, target.position.y),
            player_id=entity.player_id,
            card_stats=entity.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=entity.damage * self.damage_decay,
            range=0,
            sight_range=0,
            origin=Position(target.position.x, target.position.y),
            remaining_bounces=self.max_bounces,
            chain_range=self.chain_range,
            travel_speed=self.projectile_speed_tiles_per_second,
            stun_duration=self.stun_duration_ms / 1000.0,
            visited_ids={target.id},
        )
        battle_state.entities[chain.id] = chain
        battle_state.next_entity_id += 1
