#!/usr/bin/env python3

import json

with open('gamedata.json', 'r') as f:
    data = json.load(f)

# Find Knight in the data and show all its attributes
for spell in data['items']['spells']:
    if spell.get('name') == 'Knight':
        print('Knight card-level attributes:')
        for key, value in spell.items():
            if key != 'summonCharacterData':
                print(f'  {key}: {value}')
        
        print('\nKnight summonCharacterData attributes:')
        char_data = spell.get('summonCharacterData', {})
        for key, value in char_data.items():
            print(f'  {key}: {value}')
        break

print("\n" + "="*50)

# Check a few other card types
card_names = ['Fireball', 'Barbarians', 'Princess Tower']
for card_name in card_names:
    for spell in data['items']['spells']:
        if spell.get('name') == card_name:
            print(f'\n{card_name} attributes:')
            for key, value in spell.items():
                if isinstance(value, dict) and len(str(value)) > 100:
                    print(f'  {key}: {{complex object}}')
                else:
                    print(f'  {key}: {value}')
            break