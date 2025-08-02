#!/usr/bin/env python3
"""
Find all cards with summonNumber to identify all swarm cards
"""

import sys
sys.path.append('src')

import json
from clasher.data import CardDataLoader

def find_all_swarm_cards():
    """Find all cards with summonNumber in the JSON data"""
    
    print("=== Finding All Swarm Cards ===")
    
    try:
        # Load raw JSON data
        with open('gamedata.json', 'r') as f:
            data = json.load(f)
        
        # Get all items
        all_items = data.get('items', {}).get('spells', [])
        
        swarm_cards = []
        
        for item in all_items:
            summon_number = item.get('summonNumber')
            if summon_number and summon_number > 1:  # Only cards that spawn multiple units
                card_info = {
                    'name': item.get('name'),
                    'summonNumber': summon_number,
                    'tidType': item.get('tidType'),
                    'card_type': None,
                    'summonCharacterData': item.get('summonCharacterData', {}),
                    'summonCharacterSecondCount': item.get('summonCharacterSecondCount'),
                    'summonCharacterSecondData': item.get('summonCharacterSecondData', {}),
                    'manaCost': item.get('manaCost'),
                    'rarity': item.get('rarity')
                }
                
                # Determine card type
                tid_type = item.get('tidType')
                if tid_type == "TID_CARD_TYPE_CHARACTER":
                    card_info['card_type'] = "Troop"
                elif tid_type == "TID_CARD_TYPE_SPELL":
                    card_info['card_type'] = "Spell"
                elif tid_type == "TID_CARD_TYPE_BUILDING":
                    card_info['card_type'] = "Building"
                
                swarm_cards.append(card_info)
        
        # Sort by card type and name
        swarm_cards.sort(key=lambda x: (x['card_type'] or 'Unknown', x['name']))
        
        print(f"Found {len(swarm_cards)} swarm cards:")
        
        current_type = None
        for card in swarm_cards:
            if card['card_type'] != current_type:
                current_type = card['card_type']
                print(f"\n--- {current_type} Cards ---")
            
            name = card['name']
            count = card['summonNumber']
            second_count = card['summonCharacterSecondCount'] or 0
            cost = card['manaCost']
            rarity = card['rarity']
            
            primary_unit = card['summonCharacterData'].get('name', 'N/A')
            secondary_unit = card['summonCharacterSecondData'].get('name', 'N/A') if second_count > 0 else 'None'
            
            print(f"  {name}: {count} units ({cost} elixir, {rarity})")
            print(f"    Primary: {primary_unit}")
            if second_count > 0:
                print(f"    Secondary: {secondary_unit} (x{second_count})")
        
        return swarm_cards
        
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return []

def test_swarm_cards_in_game():
    """Test which swarm cards are loaded in the game"""
    
    print(f"\n=== Testing Swarm Cards in Game ===")
    
    # Load cards through the game system
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Find cards with summon_count > 1
    swarm_cards_in_game = []
    
    for card_name, card_stats in cards.items():
        summon_count = getattr(card_stats, 'summon_count', None) or 1
        if summon_count > 1:
            second_count = getattr(card_stats, 'summon_character_second_count', None) or 0
            total_units = summon_count + second_count
            
            swarm_cards_in_game.append({
                'name': card_name,
                'card_type': card_stats.card_type,
                'summon_count': summon_count,
                'second_count': second_count,
                'total_units': total_units,
                'mana_cost': card_stats.mana_cost,
                'rarity': card_stats.rarity,
                'has_second_data': bool(getattr(card_stats, 'summon_character_second_data', None)),
                'has_primary_data': bool(getattr(card_stats, 'summon_character_data', None))
            })
    
    # Sort by card type and name
    swarm_cards_in_game.sort(key=lambda x: (x['card_type'] or 'Unknown', x['name']))
    
    print(f"Found {len(swarm_cards_in_game)} swarm cards loaded in game:")
    
    current_type = None
    for card in swarm_cards_in_game:
        if card['card_type'] != current_type:
            current_type = card['card_type']
            print(f"\n--- {current_type} Cards ---")
        
        name = card['name']
        primary_count = card['summon_count']
        second_count = card['second_count']
        total = card['total_units']
        cost = card['mana_cost']
        rarity = card['rarity']
        
        formation_type = "Mixed" if second_count > 0 else "Single"
        has_data = "✅" if card['has_primary_data'] else "❌"
        
        print(f"  {name}: {primary_count}+{second_count}={total} units ({cost} elixir, {rarity}) [{formation_type}] {has_data}")
    
    return swarm_cards_in_game

if __name__ == "__main__":
    json_swarms = find_all_swarm_cards()
    game_swarms = test_swarm_cards_in_game()
    
    # Compare to see if any are missing
    print(f"\n=== Comparison ===")
    json_names = {card['name'] for card in json_swarms}
    game_names = {card['name'] for card in game_swarms}
    
    missing_from_game = json_names - game_names
    if missing_from_game:
        print(f"Missing from game: {missing_from_game}")
    else:
        print("✅ All swarm cards from JSON are loaded in game")