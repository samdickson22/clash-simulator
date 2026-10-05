"""C56 champion payloads; cast/geometry edge cases await native traces."""

from __future__ import annotations

from ..arena import Position
from ..kinematics import (
    LOGIC_TICK_SECONDS,
    logic_time_milliseconds,
    spawn_path_travel_tick_count,
    tiles_to_logic_units,
)
from ..mechanics.champion.ability import ActiveAbility, ChampionAbilityMechanic
from .miner import UndergroundDeployment


class MightyMinerSwitch(ChampionAbilityMechanic):
    def __init__(self):
        super().__init__(ActiveAbility("Explosive Escape", 1, 13000, 0, []))
        self.pending_ms = None
        self.cast_until_ms = 0
        self.tunnel = UndergroundDeployment()

    def activate_ability(self, entity):
        if not super().activate_ability(entity):
            return False
        now = logic_time_milliseconds(entity.battle_state.time)
        self.pending_ms = now + 500
        self.cast_until_ms = now + 933
        self.ability.activation_time = self.pending_ms
        return True

    def on_object_tick(self, entity, dt_ms):
        super().on_tick(entity, dt_ms)
        if (
            self.pending_ms is None
            or logic_time_milliseconds(entity.battle_state.time) < self.pending_ms
        ):
            return
        self.pending_ms = None
        battle = entity.battle_state
        from ..entities import TimedExplosive

        bomb = TimedExplosive(
            id=battle.next_entity_id,
            position=Position(entity.position.x, entity.position.y),
            player_id=entity.player_id,
            card_stats=entity.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=0,
            range=0,
            sight_range=0,
            explosion_timer=1.0,
            explosion_radius=3.0,
            explosion_damage=entity.card_stats.get_scaled_stat(130),
            knockback_distance=1.8,
        )
        battle.entities[bomb.id] = bomb
        battle.next_entity_id += 1
        destination = Position(
            battle.arena.width - entity.position.x, entity.position.y
        )
        travel = (
            spawn_path_travel_tick_count(
                abs(tiles_to_logic_units(destination.x - entity.position.x)),
                650,
                reached_radius_from_speed=True,
            )
            * LOGIC_TICK_SECONDS
        )
        entity._underground_destination = destination
        entity._underground_travel_duration = travel
        entity.deploy_delay_remaining = travel + 1.0
        entity.placement_delay_total = entity.deploy_delay_remaining
        entity.placement_pending = True
        entity._spawn_hook_pending = True
        entity._spawn_hook_fired = False
        entity._underground_deployment = True
        entity._special_move_active = True
        entity.target_id = None
        entity._movement_target_id = None
        entity._native_ground_route_cells = []
        entity._ground_path_cache_key = None
        entity.reset_attack_windup()
        from ..mechanics.shared.damage_ramp import DamageRamp

        for mechanic in entity.mechanics:
            if isinstance(mechanic, DamageRamp):
                mechanic.on_target_observed(entity, None, 0)
        battle.sync_fast_target_entity(entity)

    def blocks_combat_actions(self, entity):
        return logic_time_milliseconds(entity.battle_state.time) < self.cast_until_ms

    def on_deploy_tick(self, entity, dt_ms):
        self.tunnel.on_deploy_tick(entity, dt_ms)

    def on_spawn(self, entity):
        if getattr(entity, "_underground_deployment", False):
            self.tunnel.on_spawn(entity)
            entity._native_lane_id = entity.battle_state.arena.native_path_id_at(
                entity.position
            )

    def blocks_targeting(self, entity):
        return self.tunnel.blocks_targeting(entity)

    def blocks_ground_collision(self, entity):
        return self.tunnel.blocks_ground_collision(entity)

    def blocks_status_effect(self, entity):
        return self.tunnel.blocks_status_effect(entity)

    def allows_effect(self, entity, source_kind=None, *, affects_hidden=False):
        return self.tunnel.allows_effect(
            entity, source_kind, affects_hidden=affects_hidden
        )

    def take_damage_during_dash(self, entity, damage):
        return self.tunnel.take_damage_during_dash(entity, damage)

    def allows_forced_movement(self, entity, source_kind, movement_kind):
        return self.tunnel.allows_forced_movement(entity, source_kind, movement_kind)

    def on_death(self, entity):
        self.pending_ms = None
        self.ability.is_active = False


class GoblinsteinTether(ChampionAbilityMechanic):
    def __init__(self):
        super().__init__(ActiveAbility("Lightning Link", 2, 17000, 4000, []))
        self.monster_id = None
        self.anchor = None
        self.next_hit_ms = None
        self.cast_until_ms = 0

    def on_attach(self, entity):
        # Mixed-swarm construction inserts the matching monster immediately
        # before this doctor. Bind once so later copies cannot steal the link.
        monsters = [
            e
            for e in entity.battle_state.entities.values()
            if e.player_id == entity.player_id
            and e.is_alive
            and e.is_clone == entity.is_clone
            and e.card_stats is not None
            and str(
                (e.card_stats.summon_character_data or {}).get("name", "")
            ).casefold()
            == "goblinstein"
        ]
        if monsters:
            monster = max(monsters, key=lambda e: e.id)
            self.monster_id = monster.id
            self.anchor = Position(monster.position.x, monster.position.y)

    def can_activate_ability(self, entity):
        return self.anchor is not None and super().can_activate_ability(entity)

    def activate_ability(self, entity):
        if not self.can_activate_ability(entity) or not super().activate_ability(
            entity
        ):
            return False
        now = logic_time_milliseconds(entity.battle_state.time)
        self.ability.activation_time = now + 50
        self.next_hit_ms = self.ability.activation_time
        self.cast_until_ms = now + 933
        return True

    def blocks_combat_actions(self, entity):
        return logic_time_milliseconds(entity.battle_state.time) < self.cast_until_ms

    def on_object_tick(self, entity, dt_ms):
        battle = entity.battle_state
        monster = battle.entities.get(self.monster_id)
        if monster is not None:
            self.anchor = Position(monster.position.x, monster.position.y)
        super().on_tick(entity, dt_ms)
        if not self.ability.is_active:
            self.next_hit_ms = None
            return
        now = logic_time_milliseconds(battle.time)
        while self.next_hit_ms is not None and now >= self.next_hit_ms:
            # Damage callbacks can kill the doctor and clear this timer.
            self.next_hit_ms += 500
            self._pulse(entity)

    def _pulse(self, entity):
        # Native TetherWidth is the full strip width. Target hitboxes extend it.
        a, b = entity.position, self.anchor
        dx, dy = b.x - a.x, b.y - a.y
        length_squared = dx * dx + dy * dy
        for target in list(entity.battle_state.entities.values()):
            if (
                target.player_id == entity.player_id
                or not target.is_alive
                or target.entity_kind in {2, 3}
            ):
                continue
            if not target.can_receive_area_damage("GoblinsteinTether"):
                continue
            t = (
                max(
                    0.0,
                    min(
                        1.0,
                        (
                            (target.position.x - a.x) * dx
                            + (target.position.y - a.y) * dy
                        )
                        / length_squared,
                    ),
                )
                if length_squared
                else 0.0
            )
            nearest = Position(a.x + t * dx, a.y + t * dy)
            if (
                target.position.distance_to(nearest)
                <= 1.0 + target.get_collision_radius()
            ):
                crown = getattr(target, "_crown_tower_slot", None) is not None
                # Live runtime-update: 37, not the old APK's 42. Crown base 9.
                damage = entity.card_stats.get_scaled_stat(9 if crown else 37)
                target.take_damage(damage, source_kind="GoblinsteinTether")

    def on_death(self, entity):
        self.ability.is_active = False
        self.next_hit_ms = None
