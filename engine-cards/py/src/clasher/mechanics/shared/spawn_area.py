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
    _applied: bool = field(init=False, default=False)

    def on_created(self, entity) -> None:
        """A heal area is the unit's OnStartingAction: cast at creation, not by a
        clone (RoyaleSim (MIT) state.rs spawn_now; 16.402 ExecuteIfTrue !is_clone)."""
        if self._applied or not hasattr(entity, "battle_state") or not _is_heal(self.area_data):
            return
        self._applied = True
        if not getattr(entity, "is_clone", False):
            heal_area_pulse(entity, self.area_data)

    def on_spawn(self, entity) -> None:
        if self._applied or not hasattr(entity, "battle_state"):
            return
        self._applied = True
        battle = entity.battle_state
        if heal_area_pulse(entity, self.area_data):
            return
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


def _is_heal(area_data: dict) -> bool:
    buff = area_data.get("buffData") or {}
    return float(buff.get("healPerSecond", 0) or 0) > 0 and not area_data.get("damage")


def heal_area_pulse(entity, area_data: dict) -> bool:
    """Batch B1: a heal-only area (Battle Healer's spawn and on-hit heals).

    Released as the engine's Heal Spirit pulse (scope_spells.HealPulse): one
    snapshot of the owner's troops within the area's radius, each healed
    floor(HealPerSecond x level scale x HitFrequency) every HitFrequency for
    the area's BuffTime. The releasing unit ignores its own heal buff
    (characters IgnoreBuff; RoyaleSim (MIT) card.rs ignore_buffs). Returns
    False for any area that is not a pure heal.
    """
    buff = area_data.get("buffData") or {}
    heal_per_second = float(buff.get("healPerSecond", 0) or 0)
    if heal_per_second <= 0 or area_data.get("damage"):
        return False
    from ...scope_spells import HealPulse
    from ...stat_scaling import scale_stat

    battle = entity.battle_state
    level = int(getattr(entity.card_stats, "level", 11) or 11)
    interval = float(buff.get("hitFrequency", 250) or 250) / 1000.0
    radius = float(area_data.get("radius", 0) or 0) / 1000.0
    duration = float(area_data.get("buffTime", area_data.get("lifeDuration", 1000)) or 1000) / 1000.0
    per_tick = float(int((scale_stat(heal_per_second, level) or 0) * interval + 1e-9))
    pulse = HealPulse(
        id=battle.next_entity_id,
        position=Position(entity.position.x, entity.position.y),
        player_id=entity.player_id, card_stats=None, hitpoints=1, max_hitpoints=1,
        damage=0, range=radius, sight_range=radius, radius=radius, duration=duration,
        heal_per_tick=per_tick, heal_interval=interval, excluded_id=entity.id,
    )
    pulse.spell_name = str(area_data.get("name", "") or "heal-area")
    pulse.battle_state = battle
    battle.entities[pulse.id] = pulse
    battle.next_entity_id += 1
    return True


@dataclass
class AreaEffectOnHit(BaseMechanic):
    """Batch B1: a character's AreaEffectOnHit (Battle Healer's BattleHealerHeal),
    released at the attacker on every committed hit."""

    area_data: dict

    def on_attack_hit(self, entity, target) -> None:
        if hasattr(entity, "battle_state"):
            heal_area_pulse(entity, self.area_data)
