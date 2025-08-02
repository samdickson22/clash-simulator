#!/usr/bin/env python3
"""
Debug specific failing cards in detail
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader
from clasher.entities import Building

def debug_specific_cards():
    """Debug specific cards that are showing 0 units"""
    
    print("=== Debugging Specific Failing Cards ===")
    
    # Create battle state
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 50.0
    
    # Cards showing 0 units in test
    failing_cards = ['Archer', 'Minions', 'SkeletonArmy', 'ThreeMusketeers']
    
    for card_name in failing_cards:
        print(f"\n--- Debugging {card_name} ---")
        
        if card_name not in cards:
            print(f"❌ {card_name} not found")
            continue
        
        card_stats = cards[card_name]
        print(f"Card details:")
        print(f"  Name: {card_stats.name}")
        print(f"  Mana cost: {card_stats.mana_cost}")
        print(f"  Card type: {card_stats.card_type}")
        print(f"  Summon count: {getattr(card_stats, 'summon_count', None)}")
        print(f"  Summon radius: {getattr(card_stats, 'summon_radius', None)}")
        print(f"  Second count: {getattr(card_stats, 'summon_character_second_count', None)}")
        
        # Clear previous units
        battle.entities = {k: v for k, v in battle.entities.items() 
                         if isinstance(v, Building)}
        battle.players[0].elixir = 50.0
        battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
        
        # Count entities before
        entities_before = len(battle.entities)
        print(f"Entities before: {entities_before}")
        
        # Deploy the card
        deploy_pos = Position(9, 8)  # Blue territory
        print(f"Deploying at position: ({deploy_pos.x}, {deploy_pos.y})")
        
        success = battle.deploy_card(0, card_name, deploy_pos)
        print(f"Deployment success: {success}")
        
        # Count entities after
        entities_after = len(battle.entities)
        print(f"Entities after: {entities_after}")
        print(f"New entities: {entities_after - entities_before}")
        
        if success:
            # List all entities and their positions
            print(f"All entities after deployment:")
            for eid, entity in battle.entities.items():
                print(f"  {eid}: {type(entity).__name__} at ({entity.position.x:.2f}, {entity.position.y:.2f}) player={getattr(entity, 'player_id', 'N/A')}")
                if hasattr(entity, 'card_stats') and entity.card_stats:
                    print(f"       Card: {entity.card_stats.name}")
            
            # Check units within range using our test logic
            spawned_units = []
            for entity in battle.entities.values():
                if (hasattr(entity, 'card_stats') and entity.card_stats and 
                    entity.position.distance_to(deploy_pos) <= 4.0 and
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
                        spawned_units.append(entity)
                        distance = entity.position.distance_to(deploy_pos)
                        print(f"    COUNTED: {entity.card_stats.name} at distance {distance:.2f}")
            
            print(f"Units counted by test logic: {len(spawned_units)}")

if __name__ == "__main__":
    debug_specific_cards()