#!/usr/bin/env python3
"""
Dynamic spell type assignment based on JSON data structure
"""

import json
from pathlib import Path
from typing import Dict, Any, Type
from .spells import (
    Spell, DirectDamageSpell, ProjectileSpell, SpawnProjectileSpell, 
    AreaEffectSpell, BuffSpell, CloneSpell, HealSpell, RollingProjectileSpell,
    TornadoSpell, GraveyardSpell, RoyalDeliverySpell, SummonedAreaSpell, MirrorSpell, RankedStrikeSpell
)
from .card_aliases import CARD_NAME_ALIASES
from .paths import gamedata_path
from .balance import (
    TOURNAMENT_LEVEL,
    apply_entry_overrides,
    tournament_spell_stat,
)
from .gamedata_normalization import build_object_registry, serialized_hit_planes
from .kinematics import (
    SERVER_ACTION_DELAY_SECONDS,
    logic_speed_to_tiles_per_second,
)
from .logic_math import native_percent_damage
from .stat_scaling import level_multiplier, scale_stat


def _percent_to_multiplier(percent: Any, default: float = 1.0) -> float:
    if percent is None:
        return default
    try:
        return max(0.0, 1.0 + (float(percent) / 100.0))
    except (TypeError, ValueError):
        return default


def _checked_level_override(
    name: str, field: str, raw_value: float, level: int, tournament_raw_value: float
) -> float:
    """Preserve measured overrides; do not extrapolate contradictory raw data."""
    current = tournament_spell_stat(name, field)
    if current is None:
        return raw_value
    if level == TOURNAMENT_LEVEL:
        return float(current)
    if current != tournament_raw_value:
        raise ValueError(
            f"{name} level {level} needs a reconciled {field} override "
            f"(Level 11 raw={tournament_raw_value}, override={current})"
        )
    return raw_value


def _spell_damage(
    name: str, raw_damage: Any, *, level: int = TOURNAMENT_LEVEL
) -> float:
    return _checked_level_override(
        name,
        "damage",
        float(scale_stat(raw_damage or 0, level) or 0),
        level,
        float(scale_stat(raw_damage or 0, TOURNAMENT_LEVEL) or 0),
    )


def _periodic_spell_damage(
    name: str,
    raw_damage_per_second: Any,
    tick_interval: float,
    *,
    level: int = TOURNAMENT_LEVEL,
) -> float:
    """Scale serialized DPS before truncating each periodic hit."""

    def hit(at_level: int) -> float:
        return float(
            int(
                (scale_stat(raw_damage_per_second or 0, at_level) or 0) * tick_interval
                + 1e-9
            )
        )

    return _checked_level_override(
        name, "damage", hit(level), level, hit(TOURNAMENT_LEVEL)
    )


def _completed_periodic_hits(duration: float, tick_interval: float) -> int:
    """Count hit-frequency deadlines completed during an effect's lifetime."""
    if duration <= 0 or tick_interval <= 0:
        return 0
    return max(0, int((duration + 1e-9) / tick_interval))


def _spell_aux_damage(
    name: str,
    field: str,
    fallback: float | None = None,
    *,
    level: int = TOURNAMENT_LEVEL,
) -> float | None:
    current = tournament_spell_stat(name, field)
    if current is not None:
        if level != TOURNAMENT_LEVEL:
            raise ValueError(
                f"{name} level {level} needs a reconciled {field} override"
            )
        return float(current)
    return fallback


def _crown_damage(
    name: str, damage: float, percent: Any, *, level: int = TOURNAMENT_LEVEL
) -> float:
    current = tournament_spell_stat(name, "crown_tower_damage")
    if current is not None and level == TOURNAMENT_LEVEL:
        return float(current)
    return float(native_percent_damage(damage, _percent_to_multiplier(percent)))

def _repeated_spawn_action_group(
    area_data: Dict[str, Any],
) -> tuple[Dict[str, Any], list[Dict[str, Any]]] | None:
    """Return a homogeneous native SpawnToLocation action group, if present."""
    action_group = area_data.get("onStartingActionData")
    if (
        not isinstance(action_group, dict)
        or action_group.get("classType") != "ActionGroup"
    ):
        return None
    actions = action_group.get("subActionsData")
    delays = action_group.get("subActionsDelay")
    if (
        not isinstance(actions, list)
        or not actions
        or not isinstance(delays, list)
        or len(actions) != len(delays)
    ):
        return None
    if any(
        not isinstance(action, dict)
        or action.get("classType") != "ActionSpawnToLocation"
        or not action.get("spawnCharacter")
        for action in actions
    ):
        return None
    spawn_characters = {
        str(action["spawnCharacter"])
        for action in actions
    }
    if len(spawn_characters) != 1:
        return None
    return action_group, actions


def determine_spell_type(spell_data: Dict[str, Any]) -> Type[Spell]:
    """
    Dynamically determine spell type based on JSON structure.
    
    Logic:
    1. Has projectileData with spawnCharacterData -> SpawnProjectileSpell
    2. Has projectileData (no spawn) -> ProjectileSpell  
    3. Has areaEffectObjectData with lifeDuration > 1000 -> AreaEffectSpell
    4. Has areaEffectObjectData with lifeDuration <= 1000 -> DirectDamageSpell (instant)
    5. Has summonCharacterData -> varies (could be troop deployment or buff)
    6. Has selfBuffData -> BuffSpell
    7. Special cases (Mirror, Clone actions) -> CloneSpell
    8. Default -> DirectDamageSpell
    """
    
    spell_name = spell_data.get('name', '')

    area_data = spell_data.get("areaEffectObjectData", {})
    if area_data.get("targetSelection") == "highest_hitpoints":
        return RankedStrikeSpell
    area_buff = area_data.get("buffData", {})
    if area_buff.get("attractPercentage") is not None:
        return TornadoSpell
    area_projectile = area_data.get("projectileData", {})
    if (
        area_projectile.get("spawnCharacterData")
        or area_projectile.get("spawnCharacterCount")
    ):
        return RoyalDeliverySpell
    if _repeated_spawn_action_group(area_data) is not None:
        return GraveyardSpell

    carrier = spell_data.get("summonCharacterData") or {}
    if carrier.get("deathAreaEffectData") and not carrier.get("hitpoints"):
        return SummonedAreaSpell

    # Check for projectile spells
    if 'projectileData' in spell_data:
        proj_data = spell_data['projectileData']
        
        # RollingProjectileSpell: has spawnProjectileData (Log, Barbarian Barrel)
        if 'spawnProjectileData' in proj_data:
            return RollingProjectileSpell
        
        # SpawnProjectileSpell: projectile that spawns units
        if ('spawnCharacterCount' in proj_data or 
            'spawnCharacterData' in proj_data):
            return SpawnProjectileSpell
        
        # Regular ProjectileSpell: travels and explodes
        return ProjectileSpell
    
    # Check for area effects
    if 'areaEffectObjectData' in spell_data:
        area_data = spell_data['areaEffectObjectData']
        life_duration = area_data.get('lifeDuration', 0)
        
        # Special clone detection
        if ('onHitActionData' in area_data and 
            area_data['onHitActionData'].get('name') == 'CloneAction'):
            return CloneSpell
        
        # AreaEffectSpell: persistent effects (> 1 second)
        if life_duration > 1000:
            return AreaEffectSpell
        
        # DirectDamageSpell: instant effects (<= 1 second)
        return DirectDamageSpell
    
    # Check for character summoning (like Heal Spirit)
    if 'summonCharacterData' in spell_data:
        char_data = spell_data['summonCharacterData']
        
        # Check if it's a healing spirit
        if ('projectileData' in char_data and 
            'spawnAreaEffectObjectData' in char_data['projectileData']):
            area_effect = char_data['projectileData']['spawnAreaEffectObjectData']
            if ('buffData' in area_effect and 
                'healPerSecond' in area_effect['buffData']):
                return HealSpell
        
        # Default for character summoning
        return DirectDamageSpell
    
    # Check for self buffs
    if 'selfBuffData' in spell_data:
        return BuffSpell
    
    # Special cases by name
    if spell_name in ['Mirror']:
        return MirrorSpell
    
    # Default fallback
    return DirectDamageSpell


def create_spell_from_json(
    spell_data: Dict[str, Any],
    object_registry: Dict[str, Dict[str, Any]] | None = None,
    *, level: int = TOURNAMENT_LEVEL,
) -> Spell:
    """Create an independent spell at the requested level.

    Non-tournament construction rejects stale raw damage overrides and spell
    types whose level inheritance is not implemented yet.
    """
    level_multiplier(level)  # Validate even spells without damage.
    if level != TOURNAMENT_LEVEL:
        baseline = create_spell_from_json(spell_data, object_registry)
        crown = getattr(baseline, "crown_tower_damage", None)
        multiplier = getattr(baseline, "crown_tower_damage_multiplier", None)
        base_damage = getattr(baseline, "damage_per_hit", baseline.damage)
        if (
            crown is not None
            and multiplier is not None
            and crown != native_percent_damage(base_damage, multiplier)
        ):
            raise ValueError(f"{baseline.name} level {level} needs a reconciled crown damage override")
        if isinstance(baseline, (CloneSpell, HealSpell)) or baseline.name == "Mirror":
            raise ValueError(f"{baseline.name} level {level} inheritance is not implemented")

    spell_type = determine_spell_type(spell_data)
    name = spell_data.get('name', 'Unknown')
    mana_cost = spell_data.get('manaCost', 1)
    radius = spell_data.get('radius', 0) / 1000.0  # Convert to tiles
    # `spellAsDeploy` also marks center-targeted effects such as Tornado, so
    # it is not a placement-zone flag.  Territory follows payload mechanics:
    # lane rollers and delayed friendly-side deliveries use troop territory.
    requires_territory = spell_type in {RollingProjectileSpell, RoyalDeliverySpell}

    if spell_type == RankedStrikeSpell:
        area = spell_data["areaEffectObjectData"]
        projectile = area["projectileData"]
        damage = _spell_damage(name, projectile.get("damage", 0), level=level)
        hits_air, hits_ground = serialized_hit_planes(area)
        return RankedStrikeSpell(
            name=name, mana_cost=mana_cost, level=level, damage=damage,
            radius=float(area.get("radius", 0)) / 1000,
            max_targets=int(area["maxTargets"]),
            duration=float(area.get("lifeDuration", 0)) / 1000,
            strike_interval=max(0.05, float(area.get("hitSpeed", 0)) / 1000),
            stun_duration=float(projectile.get("buffTime", 0)) / 1000,
            crown_tower_damage=_crown_damage(name, damage, projectile.get("crownTowerDamagePercent"), level=level),
            crown_tower_damage_multiplier=_percent_to_multiplier(projectile.get("crownTowerDamagePercent")),
            hits_air=hits_air, hits_ground=hits_ground,
        )

    if spell_type == MirrorSpell:
        return MirrorSpell(name=name, mana_cost=mana_cost, level=level)

    if spell_type == SummonedAreaSpell:
        return SummonedAreaSpell(
            name=name, mana_cost=mana_cost, radius=radius, level=level,
            character_data=spell_data["summonCharacterData"],
        )

    area_payload = spell_data.get("areaEffectObjectData", {})
    periodic_buff = area_payload.get("buffData", {})
    if (
        spell_type != TornadoSpell
        and periodic_buff.get("damagePerSecond") is not None
    ):
        area_data = area_payload
        hits_air, hits_ground = serialized_hit_planes(area_data)
        buff_data = periodic_buff
        speed_multiplier = 1.0 + (buff_data.get("speedMultiplier", 0) / 100.0)
        effect_tick_interval = (
            float(area_data.get("hitSpeed", 50) or 50) / 1000.0
        )
        building_damage_multiplier = max(
            0.0,
            float(buff_data.get("buildingDamagePercent", 100) or 100)
            / 100.0,
        )
        tick_interval = float(buff_data.get("hitFrequency", 1000) or 1000) / 1000.0
        duration = area_data.get("lifeDuration", 4000) / 1000.0
        hit_tick_from_source = bool(
            buff_data.get("hitTickFromSource", False)
        )
        damage = _periodic_spell_damage(
            name,
            buff_data.get("damagePerSecond", 0),
            tick_interval,
            level=level,
        )
        return AreaEffectSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=damage,
            requires_territory=requires_territory,
            duration=duration,
            speed_multiplier=max(0.0, speed_multiplier),
            hits_air=hits_air,
            hits_ground=hits_ground,
            affects_hidden=bool(area_data.get("affectsHidden", False)),
            crown_tower_damage_multiplier=_percent_to_multiplier(buff_data.get("crownTowerDamagePercent")),
            building_damage_multiplier=building_damage_multiplier,
            crown_tower_damage=_crown_damage(name, damage, buff_data.get("crownTowerDamagePercent"), level=level),
            building_damage=_spell_aux_damage(
                name,
                "building_damage",
                float(
                    native_percent_damage(
                        damage,
                        building_damage_multiplier,
                    )
                ),
                level=level,
            ),
            damage_tick_interval=tick_interval,
            max_damage_ticks=(
                _completed_periodic_hits(duration, tick_interval)
                if hit_tick_from_source
                else 0
            ),
            damage_on_spawn=False,
            slows_attack_speed=False,
            slows_spawn_speed=False,
            slow_refresh_duration=(
                float(area_data.get("buffTime", 250) or 250) / 1000.0
            ),
            effect_tick_interval=effect_tick_interval,
            cap_buff_time_to_effect=bool(
                area_data.get("capBuffTimeToAreaEffectTime", False)
            ),
            target_local_damage=not hit_tick_from_source,
            periodic_damage_buff_duration=(
                float(area_data.get("buffTime", 0) or 0) / 1000.0
            ),
            level=level,
        )

    if spell_type == TornadoSpell:
        area_data = spell_data.get("areaEffectObjectData", {})
        hits_air, hits_ground = serialized_hit_planes(area_data)
        buff_data = area_data.get("buffData", {})
        tick_interval = float(buff_data.get("hitFrequency", 550) or 550) / 1000.0
        effect_tick_interval = (
            float(area_data.get("hitSpeed", 50) or 50) / 1000.0
        )
        duration = area_data.get("lifeDuration", 1050) / 1000.0
        damage = _periodic_spell_damage(
            name,
            buff_data.get("damagePerSecond", 0),
            tick_interval,
            level=level,
        )
        return TornadoSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=0,
            requires_territory=requires_territory,
            attract_percentage=float(
                buff_data.get("attractPercentage", 0) or 0
            ),
            push_speed_factor=float(
                buff_data.get("pushSpeedFactor", 0) or 0
            ),
            damage_per_hit=damage,
            duration=duration,
            hits_air=hits_air,
            hits_ground=hits_ground,
            affects_hidden=bool(area_data.get("affectsHidden", False)),
            crown_tower_damage_multiplier=_percent_to_multiplier(buff_data.get("crownTowerDamagePercent")),
            crown_tower_damage=_crown_damage(name, damage, buff_data.get("crownTowerDamagePercent"), level=level),
            damage_tick_interval=tick_interval,
            initial_damage_delay=tick_interval + effect_tick_interval,
            max_damage_ticks=_completed_periodic_hits(duration, tick_interval),
            effect_tick_interval=effect_tick_interval,
            buff_duration=(
                float(area_data.get("buffTime", 500) or 500) / 1000.0
            ),
            controlled_by_parent=bool(
                buff_data.get("controlledByParent", False)
            ),
            level=level,
        )

    if spell_type == GraveyardSpell:
        area_data = spell_data.get("areaEffectObjectData", {})
        action_group_result = _repeated_spawn_action_group(area_data)
        if action_group_result is None:
            raise ValueError(
                f"{name} is missing its repeated SpawnToLocation action group"
            )
        action_group, spawn_actions = action_group_result
        spawn_deadlines = tuple(
            max(
                0.0,
                (
                    int(delay_ms)
                    - round(SERVER_ACTION_DELAY_SECONDS * 1000.0)
                )
                / 1000.0,
            )
            for delay_ms in action_group["subActionsDelay"]
        )
        spawn_offsets = tuple(
            (
                float(action.get("xOffset", 0) or 0) / 1000.0,
                float(action.get("yOffset", 0) or 0) / 1000.0,
            )
            for action in spawn_actions
        )
        spawn_character = str(spawn_actions[0]["spawnCharacter"])
        spawn_deploy_delay = (
            float(spawn_actions[0].get("deployTime", 0) or 0) / 1000.0
        )
        mirror_pattern_x_at_center = all(
            bool(action.get("mirrorXAtArenaCenter", False))
            for action in spawn_actions
        )
        orient_pattern_y_by_player = all(
            bool(action.get("orientYByTeam", False))
            for action in spawn_actions
        )
        life_duration_ms = area_data.get("lifeDuration", 9000)
        return GraveyardSpell(
            name=name,
            mana_cost=mana_cost,
            radius=float(area_data.get("radius", 4000) or 4000) / 1000.0,
            damage=0,
            requires_territory=requires_territory,
            spawn_interval=(
                spawn_deadlines[1] - spawn_deadlines[0]
                if len(spawn_deadlines) > 1
                else 0.5
            ),
            initial_spawn_delay=spawn_deadlines[0],
            spawn_deadlines=spawn_deadlines,
            max_skeletons=len(spawn_deadlines),
            duration=life_duration_ms / 1000.0,
            spawn_offsets=spawn_offsets,
            mirror_pattern_x_at_center=mirror_pattern_x_at_center,
            orient_pattern_y_by_player=orient_pattern_y_by_player,
            spawn_deploy_delay_override=spawn_deploy_delay,
            spawn_character=spawn_character,
            skeleton_data=(
                spawn_actions[0].get("spawnCharacterData")
                or (object_registry or {}).get(spawn_character)
            ),
            level=level,
        )

    if spell_type == RoyalDeliverySpell:
        area_data = spell_data.get("areaEffectObjectData", {})
        projectile_data = area_data.get("projectileData", {})
        spawn_character_data = projectile_data.get("spawnCharacterData", {})
        damage = _spell_damage(name, projectile_data.get("damage", 0), level=level)
        return RoyalDeliverySpell(
            name=name,
            mana_cost=mana_cost,
            radius=projectile_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=damage,
            requires_territory=requires_territory,
            impact_delay=area_data.get(
                "spawnInitialDelay",
                area_data.get("lifeDuration", 2000),
            ) / 1000.0,
            # Royal Delivery serializes the Recruit's post-impact action
            # window on the enclosing area object rather than on the nested
            # character.  Honor that payload timing without changing how
            # ordinary troop or barrel spawns interpret deployTime.
            spawn_deploy_delay=area_data.get("spawnTime", 250) / 1000.0,
            travel_speed=logic_speed_to_tiles_per_second(
                projectile_data.get("speed", 5000)
            ),
            spawn_count=projectile_data.get("spawnCharacterCount", 1),
            spawn_character=spawn_character_data.get("name", "DeliveryRecruit"),
            spawn_character_data=spawn_character_data,
            ignore_buildings=bool(area_data.get("ignoreBuildings", False)),
            level=level,
        )

    if spell_type == ProjectileSpell:
        proj_data = spell_data['projectileData']
        target_buff = proj_data.get("targetBuffData", {})
        damage = _spell_damage(name, proj_data.get('damage', 0), level=level)
        projectile_count = int(spell_data.get("multipleProjectiles", 1) or 1)
        return ProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=proj_data.get('radius', 0) / 1000.0,
            damage=damage,
            requires_territory=requires_territory,
            travel_speed=logic_speed_to_tiles_per_second(
                proj_data.get('speed', 500)
            ),
            knockback_distance=proj_data.get('pushback', 0) / 1000.0,
            slow_duration=float(proj_data.get("buffTime", 0) or 0) / 1000.0,
            slow_multiplier=max(
                0.0,
                1.0
                + float(target_buff.get("speedMultiplier", 0) or 0)
                / 100.0,
            ),
            crown_tower_damage_multiplier=_percent_to_multiplier(proj_data.get("crownTowerDamagePercent")),
            crown_tower_damage=_crown_damage(name, damage, proj_data.get("crownTowerDamagePercent"), level=level),
            damage_waves=int(spell_data.get("projectileWaves", 1) or 1),
            damage_wave_interval=float(spell_data.get("projectileWaveInterval", 0) or 0) / 1000.0,
            multiple_projectiles=projectile_count,
            spread_radius=float(spell_data.get("radius", 0) or 0) / 1000.0,
            projectile_pattern=(
                "grouped_ring"
                if projectile_count > 1
                else "native_radial"
            ),
            level=level,
        )
    
    elif spell_type == SpawnProjectileSpell:
        proj_data = spell_data['projectileData']
        damage = _spell_damage(name, proj_data.get('damage', 0), level=level)
        return SpawnProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=proj_data.get('radius', 0) / 1000.0,
            damage=damage,
            requires_territory=requires_territory,
            travel_speed=logic_speed_to_tiles_per_second(
                proj_data.get('speed', 500)
            ),
            spawn_count=proj_data.get('spawnCharacterCount', 1),
            spawn_character=proj_data.get('spawnCharacterData', {}).get('name', 'Unknown'),
            spawn_character_data=proj_data.get('spawnCharacterData', {}),
            spawn_const_priority=bool(
                proj_data.get("spawnConstPriority", False)
            ),
            spawn_deploy_delay=(
                float(proj_data["spawnCharacterDeployTime"]) / 1000.0
                if proj_data.get("spawnCharacterDeployTime") is not None
                else None
            ),
            level=level,
        )
    
    elif spell_type == AreaEffectSpell:
        area_data = spell_data['areaEffectObjectData']
        hits_air, hits_ground = serialized_hit_planes(area_data)
        buff_data = area_data.get("buffData", {})
        speed_multiplier = 1.0 + (buff_data.get("speedMultiplier", 0) / 100.0)
        effect_tick_interval = (
            float(area_data.get("hitSpeed", 50) or 50) / 1000.0
        )
        damage = _spell_damage(name, area_data.get('damage', 0), level=level)
        return AreaEffectSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get('radius', 0) / 1000.0,
            damage=damage,
            requires_territory=requires_territory,
            duration=area_data.get('lifeDuration', 4000) / 1000.0,  # Convert to seconds
            freeze_effect='buffData' in area_data and buff_data.get('speedMultiplier') == -100,
            speed_multiplier=max(0.0, speed_multiplier),
            hits_air=hits_air,
            hits_ground=hits_ground,
            affects_hidden=bool(area_data.get("affectsHidden", False)),
            crown_tower_damage_multiplier=_percent_to_multiplier(
                area_data.get("crownTowerDamagePercent", buff_data.get("crownTowerDamagePercent"))
            ),
            crown_tower_damage=_crown_damage(
                name,
                damage,
                area_data.get("crownTowerDamagePercent", buff_data.get("crownTowerDamagePercent")),
                level=level,
            ),
            max_damage_ticks=1 if damage > 0 else 0,
            damage_on_spawn=damage > 0,
            effect_tick_interval=effect_tick_interval,
            cap_buff_time_to_effect=bool(
                area_data.get("capBuffTimeToAreaEffectTime", False)
            ),
            level=level,
        )
    
    elif spell_type == DirectDamageSpell:
        # For area effects with short duration, get damage from area data
        if 'areaEffectObjectData' in spell_data:
            area_data = spell_data['areaEffectObjectData']
            buff_data = area_data.get("buffData", {})
            hits_air, hits_ground = serialized_hit_planes(area_data)
            damage = _spell_damage(name, area_data.get('damage', 0), level=level)
            radius = area_data.get('radius', 0) / 1000.0
            buff_duration = float(area_data.get("buffTime", 0) or 0) / 1000.0
            speed_percent = float(buff_data.get("speedMultiplier", 0) or 0)
            freezes_actions = (
                speed_percent <= -100
                and float(buff_data.get("hitSpeedMultiplier", 0) or 0) <= -100
                and float(buff_data.get("spawnSpeedMultiplier", 0) or 0) <= -100
            )
        else:
            area_data = {}
            hits_air, hits_ground = True, True
            buff_duration = 0.0
            speed_percent = 0.0
            freezes_actions = False
            damage = _spell_damage(name, spell_data.get('damage', 0), level=level)
        
        return DirectDamageSpell(
            name=name,
            mana_cost=mana_cost,
            radius=radius,
            damage=damage,
            requires_territory=requires_territory,
            stun_duration=buff_duration if freezes_actions else 0.0,
            slow_duration=buff_duration if speed_percent < 0 and not freezes_actions else 0.0,
            slow_multiplier=max(0.0, 1.0 + speed_percent / 100.0),
            hits_air=hits_air,
            hits_ground=hits_ground,
            affects_hidden=bool(area_data.get("affectsHidden", False)),
            crown_tower_damage_multiplier=_percent_to_multiplier(
                area_data.get("crownTowerDamagePercent")
            ),
            crown_tower_damage=_crown_damage(
                name,
                damage,
                area_data.get("crownTowerDamagePercent"),
                level=level,
            ),
            level=level,
        )
    
    elif spell_type == CloneSpell:
        return CloneSpell(
            name=name,
            mana_cost=mana_cost,
            radius=radius,
            damage=0,
            requires_territory=requires_territory,
            level=level,
        )
    
    elif spell_type == RollingProjectileSpell:
        proj_data = spell_data['projectileData']
        spawn_proj_data = proj_data.get('spawnProjectileData', {})
        
        damage = _spell_damage(name, spawn_proj_data.get('damage', 0), level=level)
        return RollingProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=spawn_proj_data.get(
                "projectileRadius",
                proj_data.get("radius", 0),
            ) / 1000.0,
            damage=damage,
            requires_territory=requires_territory,
            casting_speed=logic_speed_to_tiles_per_second(
                proj_data.get('speed', 360)
            ),
            casting_min_distance=proj_data.get('minDistance', 0) / 1000.0,
            travel_speed=spawn_proj_data.get('speed', 200),
            projectile_range=spawn_proj_data.get('projectileRange', 10000) / 1000.0,  # Convert to tiles
            spawn_character=spawn_proj_data.get('spawnCharacterData', {}).get('name'),
            spawn_character_data=spawn_proj_data.get('spawnCharacterData', {}),
            spawn_deploy_delay=(
                float(spawn_proj_data["spawnCharacterDeployTime"]) / 1000.0
                if spawn_proj_data.get("spawnCharacterDeployTime") is not None
                else None
            ),
            radius_y=spawn_proj_data.get(
                "projectileRadiusY",
                proj_data.get("radiusY", 600),
            ) / 1000.0,
            knockback_distance=spawn_proj_data.get('pushback', 0) / 1000.0,
            knockback_ignores_mass=bool(
                spawn_proj_data.get("pushbackAll", False)
            ),
            crown_tower_damage_multiplier=_percent_to_multiplier(spawn_proj_data.get("crownTowerDamagePercent")),
            crown_tower_damage=_crown_damage(name, damage, spawn_proj_data.get("crownTowerDamagePercent"), level=level),
            level=level,
        )
    
    elif spell_type == HealSpell:
        # Extract heal amount from the character data
        char_data = spell_data['summonCharacterData']
        proj_data = char_data.get('projectileData', {})
        area_data = proj_data.get('spawnAreaEffectObjectData', {})
        buff_data = area_data.get('buffData', {})
        heal_amount = buff_data.get('healPerSecond', 100) * 4  # Approximate total heal
        
        return HealSpell(
            name=name,
            mana_cost=mana_cost,
            radius=proj_data.get('radius', 0) / 1000.0,
            damage=0,
            heal_amount=heal_amount,
            level=level,
        )
    
    # Default fallback
    return DirectDamageSpell(
        name=name,
        mana_cost=mana_cost,
        radius=radius,
        damage=0,
        requires_territory=requires_territory,
        level=level,
    )


def load_dynamic_spells(data_file: str | Path | None = None) -> Dict[str, Spell]:
    """Load all spells dynamically from gamedata.json."""
    data_path = gamedata_path(data_file, must_exist=True)
    with data_path.open('r') as f:
        data = json.load(f)
    
    # Get actual spells
    all_items = data.get('items', {}).get('spells', [])
    actual_spells = [item for item in all_items if item.get('tidType') == 'TID_CARD_TYPE_SPELL']
    object_registry = build_object_registry(data)
    
    spell_registry = {}
    for spell_data in actual_spells:
        spell_data = apply_entry_overrides(spell_data, object_registry)
        spell = create_spell_from_json(spell_data, object_registry)
        spell_registry[spell.name] = spell

    # Add alias spell names used by sample deck lists.
    for alias, target in CARD_NAME_ALIASES.items():
        if alias in spell_registry:
            continue
        if target in spell_registry:
            spell_registry[alias] = spell_registry[target]
    
    return spell_registry


if __name__ == "__main__":
    # Test the dynamic loading
    spells = load_dynamic_spells()
    
    print(f"Loaded {len(spells)} spells dynamically:")
    for name, spell in spells.items():
        print(f"  {name}: {type(spell).__name__}")
