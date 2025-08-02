#!/usr/bin/env python3
"""
Dynamic spell type assignment based on JSON data structure
"""

import json
from typing import Dict, Any, Type
from .spells import (
    Spell, DirectDamageSpell, ProjectileSpell, SpawnProjectileSpell, 
    AreaEffectSpell, BuffSpell, CloneSpell, HealSpell, RollingProjectileSpell
)

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
    spell_name = spell_data.get('name', '')
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
    
    if spell_type == ProjectileSpell:
        proj_data = spell_data['projectileData']
        return ProjectileSpell(
            name=name,
            mana_cost=mana_cost,
            radius=proj_data.get('radius', 0) / 1000.0,
            damage=proj_data.get('damage', 0),
            travel_speed=proj_data.get('speed', 500) / 60.0  # Convert to tiles/sec
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
        return AreaEffectSpell(
            name=name,
            mana_cost=mana_cost,
            radius=area_data.get('radius', 0) / 1000.0,
            damage=area_data.get('damage', 0),
            duration=area_data.get('lifeDuration', 4000) / 1000.0,  # Convert to seconds
            freeze_effect='buffData' in area_data and 'speedMultiplier' in area_data.get('buffData', {})
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
            radius_y=proj_data.get('radiusY', 600) / 1000.0  # Convert to tiles
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
    
    return spell_registry


if __name__ == "__main__":
    # Test the dynamic loading
    spells = load_dynamic_spells()
    
    print(f"Loaded {len(spells)} spells dynamically:")
    for name, spell in spells.items():
        print(f"  {name}: {type(spell).__name__}")