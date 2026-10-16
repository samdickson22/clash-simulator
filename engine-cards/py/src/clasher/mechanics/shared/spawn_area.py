from dataclasses import dataclass, field

from ..mechanic_base import BaseMechanic
from ...arena import Position
from ...gamedata_normalization import serialized_hit_planes
from ...kinematics import LOGIC_TICK_SECONDS
from .death_area import _serialized_speed_multiplier


@dataclass
class SpawnAreaEffect(BaseMechanic):
    """Create a character's serialized spawn-area object after deployment."""

    area_data: dict
    # Batch C1: a card play area (Electro/Ice Wizard spellAsDeploy) is cast when the card's character is
    # created by a hand play (battle.deploy_card), never again at deploy end, and adds one tick to the
    # character's deploy (RoyaleSim (MIT) state.rs `phase_spawn`). Clone copies cast nothing.
    at_creation: bool = False
    _applied: bool = field(init=False, default=False)

    def on_spawn(self, entity) -> None:
        if self.at_creation:
            self._applied = True
            return
        if self._applied or not hasattr(entity, "battle_state"):
            return
        self._applied = True
        self._create_area(entity)

    def cast_at_creation(self, entity) -> None:
        if self._applied or not hasattr(entity, "battle_state") or entity.is_clone:
            return
        self._applied = True
        entity.deploy_delay_remaining += 0.05
        entity.placement_delay_total += 0.05
        self._create_area(entity)

    def _create_area(self, entity) -> None:
        battle = entity.battle_state
        from ...entities import AreaEffect

        radius = float(self.area_data.get("radius", 0) or 0) / 1000.0
        base_damage = float(self.area_data.get("damage", 0) or 0)
        scaler = getattr(entity.card_stats, "get_scaled_stat", None)
        damage = float(scaler(base_damage) if callable(scaler) else base_damage)
        crown_multiplier = max(
            0.0,
            1.0 + float(self.area_data.get("crownTowerDamagePercent", 0) or 0) / 100.0,
        )
        buff = self.area_data.get("buffData") or {}
        movement_multiplier = _serialized_speed_multiplier(
            buff.get("speedMultiplier")
        )
        attack_multiplier = _serialized_speed_multiplier(
            buff.get("hitSpeedMultiplier")
        )
        spawn_multiplier = _serialized_speed_multiplier(
            buff.get("spawnSpeedMultiplier")
        )
        buff_duration = float(self.area_data.get("buffTime", 0) or 0) / 1000.0
        hits_air, hits_ground = serialized_hit_planes(self.area_data)
        duration = max(
            0.001,
            float(self.area_data.get("lifeDuration", 0) or 0) / 1000.0,
        )
        area = AreaEffect(
            id=battle.next_entity_id,
            position=Position(entity.position.x, entity.position.y),
            player_id=entity.player_id,
            card_stats=entity.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=damage,
            range=radius,
            sight_range=radius,
            duration=duration,
            radius=radius,
            hits_air=hits_air,
            hits_ground=hits_ground,
            affects_hidden=bool(self.area_data.get("affectsHidden", False)),
            crown_tower_damage_multiplier=crown_multiplier,
            damage_tick_interval=LOGIC_TICK_SECONDS,
            initial_damage_delay=0.0,
            max_damage_ticks=1 if damage > 0 else 0,
            damage_on_spawn=damage > 0,
            speed_multiplier=movement_multiplier,
            attack_speed_multiplier=attack_multiplier,
            spawn_speed_multiplier=spawn_multiplier,
            slow_refresh_duration=buff_duration,
            effect_tick_interval=0.0,
            effect_on_spawn_only=True,
        )
        area.spell_name = str(self.area_data.get("name", "") or "spawn-area")
        area.battle_state = battle
        battle.entities[area.id] = area
        battle.next_entity_id += 1
