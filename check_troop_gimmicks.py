#!/usr/bin/env python3
"""
Script to examine troop gimmicks from gamedata.json without overflowing context window
"""

import json
from typing import Dict, Any, List

def find_charging_troops(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find all troops with charging mechanics"""
    charging_troops = []
    
    spells = data.get("items", {}).get("spells", [])
    
    for spell in spells:
        char_data = spell.get("summonCharacterData", {})
        if char_data:
            # Check for charging mechanics
            charge_range = char_data.get("chargeRange")
            charge_speed_multiplier = char_data.get("chargeSpeedMultiplier")
            damage_special = char_data.get("damageSpecial")
            
            if charge_range or charge_speed_multiplier or damage_special:
                troop_info = {
                    "name": spell.get("name"),
                    "chargeRange": charge_range,
                    "chargeSpeedMultiplier": charge_speed_multiplier,
                    "damageSpecial": damage_special,
                    "normal_damage": char_data.get("damage"),
                    "speed": char_data.get("speed"),
                    "range": char_data.get("range")
                }
                charging_troops.append(troop_info)
    
    return charging_troops

def find_death_spawn_troops(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find all troops with death spawn mechanics"""
    death_spawn_troops = []
    
    spells = data.get("items", {}).get("spells", [])
    
    for spell in spells:
        char_data = spell.get("summonCharacterData", {})
        if char_data:
            death_spawn_data = char_data.get("deathSpawnCharacterData")
            death_spawn_count = char_data.get("deathSpawnCount")
            
            if death_spawn_data or death_spawn_count:
                troop_info = {
                    "name": spell.get("name"),
                    "deathSpawnCharacterData": death_spawn_data.get("name") if death_spawn_data else None,
                    "deathSpawnCount": death_spawn_count,
                    "kamikaze": char_data.get("kamikaze", False)
                }
                death_spawn_troops.append(troop_info)
    
    return death_spawn_troops

def find_buff_troops(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find all troops with buff mechanics"""
    buff_troops = []
    
    spells = data.get("items", {}).get("spells", [])
    
    for spell in spells:
        char_data = spell.get("summonCharacterData", {})
        if char_data:
            # Check for various buff-related fields
            buff_data = char_data.get("buffData")
            hit_speed_multiplier = char_data.get("hitSpeedMultiplier")
            speed_multiplier = char_data.get("speedMultiplier")
            spawn_speed_multiplier = char_data.get("spawnSpeedMultiplier")
            
            if buff_data or hit_speed_multiplier or speed_multiplier or spawn_speed_multiplier:
                troop_info = {
                    "name": spell.get("name"),
                    "buffData": buff_data.get("name") if buff_data else None,
                    "hitSpeedMultiplier": hit_speed_multiplier,
                    "speedMultiplier": speed_multiplier,
                    "spawnSpeedMultiplier": spawn_speed_multiplier
                }
                buff_troops.append(troop_info)
    
    return buff_troops

def find_special_timing_troops(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find all troops with special timing mechanics"""
    special_timing_troops = []
    
    spells = data.get("items", {}).get("spells", [])
    
    for spell in spells:
        char_data = spell.get("summonCharacterData", {})
        if char_data:
            special_load_time = char_data.get("specialLoadTime")
            special_range = char_data.get("specialRange")
            special_min_range = char_data.get("specialMinRange")
            
            if special_load_time or special_range or special_min_range:
                troop_info = {
                    "name": spell.get("name"),
                    "specialLoadTime": special_load_time,
                    "specialRange": special_range,
                    "specialMinRange": special_min_range,
                    "normalLoadTime": char_data.get("loadTime"),
                    "normalRange": char_data.get("range")
                }
                special_timing_troops.append(troop_info)
    
    return special_timing_troops

def main():
    """Examine troop gimmicks in gamedata.json"""
    try:
        with open("gamedata.json", "r") as f:
            data = json.load(f)
        
        print("=== CHARGING TROOPS ===")
        charging_troops = find_charging_troops(data)
        for troop in charging_troops:
            print(f"Troop: {troop['name']}")
            if troop['chargeRange']:
                print(f"  chargeRange: {troop['chargeRange']}")
            if troop['chargeSpeedMultiplier']:
                print(f"  chargeSpeedMultiplier: {troop['chargeSpeedMultiplier']}")
            if troop['damageSpecial']:
                print(f"  damageSpecial: {troop['damageSpecial']}")
            if troop['normal_damage']:
                print(f"  normal_damage: {troop['normal_damage']}")
            if troop['speed']:
                print(f"  speed: {troop['speed']}")
            print()
        
        print(f"Total charging troops: {len(charging_troops)}")
        
        print("\n=== DEATH SPAWN TROOPS ===")
        death_spawn_troops = find_death_spawn_troops(data)
        for troop in death_spawn_troops:
            print(f"Troop: {troop['name']}")
            if troop['deathSpawnCharacterData']:
                print(f"  deathSpawnCharacter: {troop['deathSpawnCharacterData']}")
            if troop['deathSpawnCount']:
                print(f"  deathSpawnCount: {troop['deathSpawnCount']}")
            if troop['kamikaze']:
                print(f"  kamikaze: {troop['kamikaze']}")
            print()
        
        print(f"Total death spawn troops: {len(death_spawn_troops)}")
        
        print("\n=== BUFF TROOPS ===")
        buff_troops = find_buff_troops(data)
        for troop in buff_troops:
            print(f"Troop: {troop['name']}")
            if troop['buffData']:
                print(f"  buffData: {troop['buffData']}")
            if troop['hitSpeedMultiplier']:
                print(f"  hitSpeedMultiplier: {troop['hitSpeedMultiplier']}")
            if troop['speedMultiplier']:
                print(f"  speedMultiplier: {troop['speedMultiplier']}")
            if troop['spawnSpeedMultiplier']:
                print(f"  spawnSpeedMultiplier: {troop['spawnSpeedMultiplier']}")
            print()
        
        print(f"Total buff troops: {len(buff_troops)}")
        
        print("\n=== SPECIAL TIMING TROOPS ===")
        special_timing_troops = find_special_timing_troops(data)
        for troop in special_timing_troops:
            print(f"Troop: {troop['name']}")
            if troop['specialLoadTime']:
                print(f"  specialLoadTime: {troop['specialLoadTime']}")
            if troop['specialRange']:
                print(f"  specialRange: {troop['specialRange']}")
            if troop['specialMinRange']:
                print(f"  specialMinRange: {troop['specialMinRange']}")
            print()
        
        print(f"Total special timing troops: {len(special_timing_troops)}")
        
    except FileNotFoundError:
        print("gamedata.json file not found")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
