#!/usr/bin/env python3
"""
Search for Golemite spells in gamedata.json
"""

import json

def main():
    """Search for Golemite spells"""
    with open('gamedata.json', 'r') as f:
        data = json.load(f)
    
    spells = data.get('items', {}).get('spells', [])
    golemite_spells = []
    
    for spell in spells:
        name = spell.get('name', '')
        death_spawn = spell.get('deathSpawnCharacterData', {}).get('name', '') if spell.get('deathSpawnCharacterData') else ''
        
        if 'Golemite' in name or 'Golemite' in death_spawn:
            golemite_spells.append(spell)
    
    print(f"Found {len(golemite_spells)} spells with Golemite:")
    for spell in golemite_spells:
        name = spell.get('name', 'Unknown')
        death_spawn = spell.get('deathSpawnCharacterData', {}).get('name', 'None') if spell.get('deathSpawnCharacterData') else 'None'
        print(f"  {name} - death spawn: {death_spawn}")

if __name__ == "__main__":
    main()
