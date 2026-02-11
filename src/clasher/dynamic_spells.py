#!/usr/bin/env python3
"""
Dynamic spell type assignment based on JSON data structure
"""

import json
from typing import Dict, Any, Type
from .spells import (
    Spell, DirectDamageSpell, ProjectileSpell, SpawnProjectileSpell, 
    AreaEffectSpell, BuffSpell, CloneSpell, HealSpell, RollingProjectileSpell,
    TornadoSpell, GraveyardSpell, RoyalDeliverySpell
)
from .card_aliases import CARD_NAME_ALIASES


def _percent_to_multiplier(percent: Any, default: float = 1.0) -> float:
    if percent is None:
        return default
    try:
        return max(0.0, 1.0 + (float(percent) / 100.0))
    except (TypeError, ValueError):
        return default

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

    # Explicit special-cases used by sample decks
    if spell_name == "Tornado":
        return TornadoSpell
    if spell_name == "Graveyard":
        return GraveyardSpell
    if spell_name == "RoyalDelivery":
        return RoyalDeliverySpell

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
        return DirectDamageSpell  # Special handling in battle logic
    
    # Default fallback
    return DirectDamageSpell


def create_spell_from_json(spell_data: Dict[str, Any]) -> Spell:
    """Create a spell instance from JSON data."""
    spell_type = determine_spell_type(spell_data)
    name = spell_data.get('name', 'Unknown')
    mana_cost = spell_data.get('manaCost', 1)
    radius = spell_data.get('radius', 0) / 1000.0  # Convert to tiles

    # Explicit card behavior overrides for sample deck spells.
    if name == "Zap":
        area_data = spell_data.get("areaEffectObjectData", {})
        return DirectDamageSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=area_data.get("damage", spell_data.get("damage", 0)),
            stun_duration=area_data.get("buffTime", 500) / 1000.0,
            crown_tower_damage_multiplier=_percent_to_multiplier(area_data.get("crownTowerDamagePercent")),
        )

    if name == "Freeze":
        area_data = spell_data.get("areaEffectObjectData", {})
        return AreaEffectSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=area_data.get("damage", spell_data.get("damage", 0)),
            duration=area_data.get("lifeDuration", 4000) / 1000.0,
            freeze_effect=True,
            hits_air=area_data.get("hitsAir", True),
            hits_ground=area_data.get("hitsGround", True),
            crown_tower_damage_multiplier=_percent_to_multiplier(area_data.get("crownTowerDamagePercent")),
        )

    if name in {"Poison", "Earthquake"}:
        area_data = spell_data.get("areaEffectObjectData", {})
        buff_data = area_data.get("buffData", {})
        speed_multiplier = 1.0 + (buff_data.get("speedMultiplier", 0) / 100.0)
        building_damage_multiplier = 1.0
        if name == "Earthquake":
            building_damage_multiplier = max(
                1.0, float(buff_data.get("buildingDamagePercent", 100)) / 100.0
            )
        return AreaEffectSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=buff_data.get("damagePerSecond", 0),
            duration=area_data.get("lifeDuration", 4000) / 1000.0,
            speed_multiplier=max(0.0, speed_multiplier),
            hits_air=area_data.get("hitsAir", True),
            hits_ground=area_data.get("hitsGround", True),
            crown_tower_damage_multiplier=_percent_to_multiplier(buff_data.get("crownTowerDamagePercent")),
            building_damage_multiplier=building_damage_multiplier,
        )

    if name == "Tornado":
        area_data = spell_data.get("areaEffectObjectData", {})
        buff_data = area_data.get("buffData", {})
        return TornadoSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=0,
            pull_force=3.0,
            damage_per_second=buff_data.get("damagePerSecond", 0),
            duration=area_data.get("lifeDuration", 1050) / 1000.0,
            hits_air=area_data.get("hitsAir", True),
            hits_ground=area_data.get("hitsGround", True),
            crown_tower_damage_multiplier=_percent_to_multiplier(buff_data.get("crownTowerDamagePercent")),
        )

    if name == "Graveyard":
        area_data = spell_data.get("areaEffectObjectData", {})
        spawn_interval_ms = area_data.get("spawnInterval", 500)
        life_duration_ms = area_data.get("lifeDuration", 9000)
        max_skeletons = int(life_duration_ms / max(1, spawn_interval_ms))
        return GraveyardSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=0,
            spawn_interval=spawn_interval_ms / 1000.0,
            max_skeletons=max(1, max_skeletons),
            duration=life_duration_ms / 1000.0,
            skeleton_data=area_data.get("spawnCharacterData"),
        )

    if name == "RoyalDelivery":
        area_data = spell_data.get("areaEffectObjectData", {})
        projectile_data = area_data.get("projectileData", {})
        spawn_character_data = projectile_data.get("spawnCharacterData", {})
        return RoyalDeliverySpell(
            name=name,
            mana_cost=mana_cost,
            radius=projectile_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=projectile_data.get("damage", 0),
            impact_delay=area_data.get("lifeDuration", 2000) / 1000.0,
            travel_speed=projectile_data.get("speed", 5000) / 60.0,
            spawn_count=projectile_data.get("spawnCharacterCount", 1),
            spawn_character=spawn_character_data.get("name", "DeliveryRecruit"),
            spawn_character_data=spawn_character_data,
        )

    if name in {"Snowball", "GiantSnowball"}:
        projectile_data = spell_data.get("projectileData", {})
        target_buff = projectile_data.get("targetBuffData", {})
        return ProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=projectile_data.get("radius", spell_data.get("radius", 0)) / 1000.0,
            damage=projectile_data.get("damage", spell_data.get("damage", 0)),
            travel_speed=projectile_data.get("speed", 500) / 60.0,
            slow_duration=projectile_data.get("buffTime", 0) / 1000.0,
            slow_multiplier=max(0.0, 1.0 + (target_buff.get("speedMultiplier", 0) / 100.0)),
            knockback_distance=projectile_data.get("pushback", 0) / 1000.0,
            crown_tower_damage_multiplier=_percent_to_multiplier(projectile_data.get("crownTowerDamagePercent")),
        )
    
    if spell_type == ProjectileSpell:
        proj_data = spell_data['projectileData']
        return ProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=proj_data.get('radius', 0) / 1000.0,
            damage=proj_data.get('damage', 0),
            travel_speed=proj_data.get('speed', 500) / 60.0,  # Convert to tiles/sec
            knockback_distance=proj_data.get('pushback', 0) / 1000.0,
            crown_tower_damage_multiplier=_percent_to_multiplier(proj_data.get("crownTowerDamagePercent")),
        )
    
    elif spell_type == SpawnProjectileSpell:
        proj_data = spell_data['projectileData']
        return SpawnProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=proj_data.get('radius', 0) / 1000.0,
            damage=proj_data.get('damage', 0),
            travel_speed=proj_data.get('speed', 500) / 60.0,
            spawn_count=proj_data.get('spawnCharacterCount', 1),
            spawn_character=proj_data.get('spawnCharacterData', {}).get('name', 'Unknown'),
            spawn_character_data=proj_data.get('spawnCharacterData', {})
        )
    
    elif spell_type == AreaEffectSpell:
        area_data = spell_data['areaEffectObjectData']
        buff_data = area_data.get("buffData", {})
        speed_multiplier = 1.0 + (buff_data.get("speedMultiplier", 0) / 100.0)
        return AreaEffectSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get('radius', 0) / 1000.0,
            damage=area_data.get('damage', 0),
            duration=area_data.get('lifeDuration', 4000) / 1000.0,  # Convert to seconds
            freeze_effect='buffData' in area_data and buff_data.get('speedMultiplier') == -100,
            speed_multiplier=max(0.0, speed_multiplier),
            hits_air=area_data.get("hitsAir", True),
            hits_ground=area_data.get("hitsGround", True),
            crown_tower_damage_multiplier=_percent_to_multiplier(
                area_data.get("crownTowerDamagePercent", buff_data.get("crownTowerDamagePercent"))
            ),
        )
    
    elif spell_type == DirectDamageSpell:
        # For area effects with short duration, get damage from area data
        if 'areaEffectObjectData' in spell_data:
            area_data = spell_data['areaEffectObjectData']
            damage = area_data.get('damage', 0)
            radius = area_data.get('radius', 0) / 1000.0
        else:
            damage = spell_data.get('damage', 0)
        
        return DirectDamageSpell(
            name=name,
            mana_cost=mana_cost,
            radius=radius,
            damage=damage
        )
    
    elif spell_type == CloneSpell:
        return CloneSpell(
            name=name,
            mana_cost=mana_cost,
            radius=radius,
            damage=0
        )
    
    elif spell_type == RollingProjectileSpell:
        proj_data = spell_data['projectileData']
        spawn_proj_data = proj_data.get('spawnProjectileData', {})
        
        return RollingProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=proj_data.get('radius', 0) / 1000.0,
            damage=spawn_proj_data.get('damage', 0),
            travel_speed=spawn_proj_data.get('speed', 200),  # Already in tiles/min
            projectile_range=spawn_proj_data.get('projectileRange', 10000) / 1000.0,  # Convert to tiles
            spawn_delay=0.65,  # Fixed spawn delay
            spawn_character=spawn_proj_data.get('spawnCharacterData', {}).get('name'),
            spawn_character_data=spawn_proj_data.get('spawnCharacterData', {}),
            radius_y=proj_data.get('radiusY', 600) / 1000.0,  # Convert to tiles
            knockback_distance=spawn_proj_data.get('pushback', 0) / 1000.0
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
            heal_amount=heal_amount
        )
    
    # Default fallback
    return DirectDamageSpell(name=name, mana_cost=mana_cost, radius=radius, damage=0)


def load_dynamic_spells() -> Dict[str, Spell]:
    """Load all spells dynamically from gamedata.json."""
    with open('gamedata.json', 'r') as f:
        data = json.load(f)
    
    # Get actual spells
    all_items = data.get('items', {}).get('spells', [])
    actual_spells = [item for item in all_items if item.get('tidType') == 'TID_CARD_TYPE_SPELL']
    
    spell_registry = {}
    for spell_data in actual_spells:
        spell = create_spell_from_json(spell_data)
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
