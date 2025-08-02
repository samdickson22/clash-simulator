#!/usr/bin/env python3
"""
Debug Royal Recruits counting issue in the main test
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader
from clasher.entities import Building

def debug_royal_recruits_count():
    """Debug why Royal Recruits shows 4 units instead of 6 in main test"""
    
    print("=== Debugging Royal Recruits Count Issue ===")
    
    # Create battle state  
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 50.0
    
    card_name = 'RoyalRecruits'
    battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
    
    # Clear previous entities
    battle.entities = {k: v for k, v in battle.entities.items() if isinstance(v, Building)}
    
    deploy_pos = Position(9, 8)  # Same as main test
    print(f"Deploy position: ({deploy_pos.x}, {deploy_pos.y})")
    
    success = battle.deploy_card(0, card_name, deploy_pos)
    print(f"Deployment success: {success}")
    
    if success:
        # Count all Royal Recruits entities
        all_recruits = []
        for entity in battle.entities.values():
            if (hasattr(entity, 'card_stats') and entity.card_stats and 
                entity.card_stats.name == card_name and
                getattr(entity, 'player_id', -1) == 0):
                all_recruits.append(entity)
        
        print(f"Total Royal Recruits spawned: {len(all_recruits)}")
        
        # Check which ones are within 4.0 tile radius (main test filter)
        within_radius = []
        for entity in all_recruits:
            distance = entity.position.distance_to(deploy_pos)
            print(f"  Unit at ({entity.position.x:.2f}, {entity.position.y:.2f}): distance = {distance:.2f}")
            if distance <= 4.0:
                within_radius.append(entity)
        
        print(f"Units within 4.0 tile radius: {len(within_radius)}")
        print(f"This explains why main test counted {len(within_radius)} instead of {len(all_recruits)}")
        
        # Suggest solution
        print(f"\nSolution: Royal Recruits spawn in a line up to 12.5 tiles wide")
        print(f"Need to either:")
        print(f"1. Increase radius filter to 7+ tiles for Royal Recruits")
        print(f"2. Use different counting logic for special formations")

if __name__ == "__main__":
    debug_royal_recruits_count()