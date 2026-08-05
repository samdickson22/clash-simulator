from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import (
    logic_speed_to_tiles_per_second,
    logic_units_to_tiles,
    speed_work_for_duration,
    tiles_to_logic_units,
    vector_towards_logic_units,
)

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ElectroSpiritChain(BaseMechanic):
    """Implements Electro Spirit's bouncing zap chain."""
    chain_range: float = 4.0
    max_targets: int = 9
    stun_duration_ms: int = 500
    damage_decay: float = 1.0
    jump_duration_ms: int = 200
    jump_speed_logic_units_per_tick: int = 1000
    projectile_speed_tiles_per_second: float = logic_speed_to_tiles_per_second(2000.0)
    chain_interval_seconds: float = 0.25

    def on_attach(self, entity: 'Entity') -> None:
        # The spirit itself is the projectile: it jumps, connects, chains, and
        # disappears.  Its projectileData describes the chain payload, not a
        # separately fired basic projectile.
        entity._force_melee_attack = True
        entity._electro_spirit_jump_target_id = None
        entity._electro_spirit_jump_elapsed = 0.0
        entity._electro_spirit_jump_destination = None
        projectile = getattr(entity.card_stats, "projectile_data", {}) or {}
        self.chain_range = float(projectile.get("chainedHitRadius", 4000) or 4000) / 1000.0
        self.max_targets = int(projectile.get("chainedHitCount", self.max_targets))
        self.stun_duration_ms = int(projectile.get("buffTime", self.stun_duration_ms))
        projectile_speed = int(projectile.get("speed", 1000) or 1000)
        self.jump_speed_logic_units_per_tick = projectile_speed
        self.projectile_speed_tiles_per_second = logic_speed_to_tiles_per_second(
            projectile_speed
        )

    def on_attack_start(self, entity: 'Entity', target: 'Entity') -> None:
        entity._electro_spirit_jump_target_id = target.id
        entity._electro_spirit_jump_origin = (entity.position.x, entity.position.y)
        entity._electro_spirit_jump_destination = (target.position.x, target.position.y)
        entity._electro_spirit_jump_elapsed = 0.0
        entity._special_move_active = True
        entity._special_move_consumed_tick = True

    def on_movement_tick(self, entity: 'Entity', dt_ms: int) -> None:
        """Advance the committed jump in component type 1."""
        if not getattr(entity, "_special_move_active", False):
            return
        battle_state = entity.battle_state
        target = battle_state.entities.get(entity._electro_spirit_jump_target_id)
        entity._electro_spirit_jump_elapsed += dt_ms
        if target is not None:
            destination_x, destination_y = target.position.x, target.position.y
            entity._electro_spirit_jump_destination = (destination_x, destination_y)
        else:
            destination_x, destination_y = getattr(
                entity,
                '_electro_spirit_jump_destination',
                (entity.position.x, entity.position.y),
            )
        dx_units = tiles_to_logic_units(destination_x - entity.position.x)
        dy_units = tiles_to_logic_units(destination_y - entity.position.y)
        remaining_units = math.isqrt(
            dx_units * dx_units + dy_units * dy_units
        )
        travel_units = speed_work_for_duration(
            self.jump_speed_logic_units_per_tick,
            dt_ms / 1000.0,
        )
        move_x_units, move_y_units = vector_towards_logic_units(
            dx_units,
            dy_units,
            travel_units,
        )
        entity.position.x = logic_units_to_tiles(
            tiles_to_logic_units(entity.position.x) + move_x_units
        )
        entity.position.y = logic_units_to_tiles(
            tiles_to_logic_units(entity.position.y) + move_y_units
        )
        if remaining_units > travel_units:
            return
        entity._special_move_active = False
        entity._special_move_consumed_tick = True
        entity._electro_spirit_jump_destination = None
        if target is not None and target.is_alive:
            target.take_damage(entity.damage)
            # Contact commits the entire chain.  The first hit is allowed to
            # kill its victim (and synchronously create any death spawns)
            # before the remaining links choose their targets.
            self._land(entity, target)
        entity.take_damage(entity.hitpoints)

    def _land(self, entity: 'Entity', target: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        if target.is_alive:
            target.apply_stun(self.stun_duration_ms / 1000.0)
        from ..arena import Position
        from ..entities import ChainLightning

        chain = ChainLightning(
            id=battle_state.next_entity_id,
            position=Position(target.position.x, target.position.y),
            player_id=entity.player_id,
            card_stats=entity.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=entity.damage,
            range=0,
            sight_range=0,
            origin=Position(target.position.x, target.position.y),
            remaining_bounces=max(0, self.max_targets - 1),
            chain_range=self.chain_range,
            travel_speed=self.projectile_speed_tiles_per_second,
            fixed_hop_duration=self.chain_interval_seconds,
            stun_duration=self.stun_duration_ms / 1000.0,
            visited_ids={target.id},
        )
        battle_state.entities[chain.id] = chain
        battle_state.next_entity_id += 1

    def modify_incoming_damage(self, entity: 'Entity', amount: float) -> float:
        return 0.0 if getattr(entity, "_special_move_active", False) else amount

    def allows_effect(
        self,
        entity: 'Entity',
        source_kind: str | None,
        *,
        affects_hidden: bool = False,
    ) -> bool:
        """Treat the committed self-projectile as absent from effect queries."""
        del source_kind, affects_hidden
        return not getattr(entity, "_special_move_active", False)

    def blocks_status_effect(self, entity: 'Entity') -> bool:
        return bool(getattr(entity, "_special_move_active", False))

    def blocks_targeting(self, entity: 'Entity') -> bool:
        return bool(getattr(entity, "_special_move_active", False))

    def blocks_ground_collision(self, entity: 'Entity') -> bool:
        return getattr(entity, "_electro_spirit_jump_target_id", None) is not None
