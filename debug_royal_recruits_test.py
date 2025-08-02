#!/usr/bin/env python3
"""
Debug Royal Recruits test issue
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader
from clasher.entities import Building

def debug_royal_recruits_test():
    """Debug why Royal Recruits test shows 8 units instead of 6"""
    
    print("=== Debugging Royal Recruits Test Issue ===")
    
    # Create battle state exactly like the main test
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 50.0
    
    card_name = 'RoyalRecruits'
    expected_count = 6
    
    print(f"Testing {card_name} (expecting {expected_count} units)")
    
    # Add card to hand
    battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
    
    # Count entities before (just like main test does it wrong!)
    print(f"Entities before deployment: {len(battle.entities)}")
    for eid, entity in battle.entities.items():
        print(f"  {eid}: {type(entity).__name__} at ({entity.position.x:.2f}, {entity.position.y:.2f})")
    
    # Deploy the card
    deploy_pos = Position(9, 8)  # Blue territory
    success = battle.deploy_card(0, card_name, deploy_pos)
    
    print(f"Deployment success: {success}")
    print(f"Entities after deployment: {len(battle.entities)}")
    
    if success:
        # List all entities
        print(f"All entities after deployment:")
        royal_recruits_entities = []
        for eid, entity in battle.entities.items():
            print(f"  {eid}: {type(entity).__name__} at ({entity.position.x:.2f}, {entity.position.y:.2f}) player={getattr(entity, 'player_id', 'N/A')}")
            if hasattr(entity, 'card_stats') and entity.card_stats:
                print(f"       Card: {entity.card_stats.name}")
                if (entity.card_stats.name == card_name and 
                    getattr(entity, 'player_id', -1) == 0):
                    royal_recruits_entities.append(entity)
        
        print(f"Total Royal Recruits found: {len(royal_recruits_entities)}")
        
        # Apply the exact same filter as main test
        spawned_units = []
        search_radius = 7.0  # Royal Recruits special radius
        
        for entity in battle.entities.values():
            if (hasattr(entity, 'card_stats') and entity.card_stats and 
                entity.position.distance_to(deploy_pos) <= search_radius and
                getattr(entity, 'player_id', -1) == 0):
                # Exclude towers
                pos = entity.position
                is_tower = (
                    (pos.x == 3.5 and pos.y == 2.5) or   # Blue left tower
                    (pos.x == 14.5 and pos.y == 2.5) or  # Blue right tower  
                    (pos.x == 9.0 and pos.y == 2.5) or   # Blue king tower
                    (pos.x == 3.5 and pos.y == 29.5) or  # Red left tower
                    (pos.x == 14.5 and pos.y == 29.5) or # Red right tower
                    (pos.x == 9.0 and pos.y == 29.5)     # Red king tower
                )
                if not is_tower:
                    distance = entity.position.distance_to(deploy_pos)
                    print(f"    COUNTED: {entity.card_stats.name} at distance {distance:.2f}")
                    spawned_units.append(entity)
        
        print(f"Units counted by main test logic: {len(spawned_units)}")
        
        # Check what non-RoyalRecruits entities are being counted
        non_recruits = []
        for unit in spawned_units:
            if unit.card_stats.name != card_name:
                non_recruits.append(unit)
        
        if non_recruits:
            print(f"WARNING: {len(non_recruits)} non-RoyalRecruits units being counted:")
            for unit in non_recruits:
                print(f"  - {unit.card_stats.name} at ({unit.position.x:.2f}, {unit.position.y:.2f})")

if __name__ == "__main__":
    debug_royal_recruits_test()