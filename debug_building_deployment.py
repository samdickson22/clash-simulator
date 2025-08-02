#!/usr/bin/env python3
"""
Debug building deployment issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.data import CardDataLoader
from src.clasher.battle import BattleState
from src.clasher.arena import Position

def main():
    """Debug building deployment"""
    print("Debugging Building Deployment")
    print("=" * 40)
    
    # Load all cards
    loader = CardDataLoader()
    cards = loader.load_cards()
    
    # Get building cards
    building_cards = {name: stats for name, stats in cards.items() 
                     if stats.card_type == "Building"}
    
    print(f"Found {len(building_cards)} building cards:")
    for name in building_cards:
        print(f"  - {name}")
    
    print(f"\\nTesting building deployment...")
    
    # Test a few buildings
    test_buildings = ["Cannon", "GoblinHut", "Elixir Collector"]
    
    for building_name in test_buildings:
        print(f"\\n{'='*50}")
        print(f"Testing: {building_name}")
        print(f"{'='*50}")
        
        try:
            battle = BattleState()
            battle.players[0].hand = [building_name]
            battle.players[0].elixir = 10.0
            
            # Try different positions
            test_positions = [
                Position(5.0, 10.0),  # Player side
                Position(9.0, 15.0),  # Center
                Position(5.0, 8.0),   # Closer to player
            ]
            
            for pos in test_positions:
                print(f"\\nTrying position: ({pos.x}, {pos.y})")
                
                # Reset battle for each position test
                battle = BattleState()
                battle.players[0].hand = [building_name]
                battle.players[0].elixir = 10.0
                
                success = battle.deploy_card(0, building_name, pos)
                print(f"  Deploy result: {success}")
                
                if success:
                    # Find the entity
                    entity = None
                    for ent in battle.entities.values():
                        if ent.card_stats.name == building_name and ent.player_id == 0:
                            entity = ent
                            break
                    
                    if entity:
                        print(f"  ✅ Entity created!")
                        print(f"     - HP: {entity.hitpoints}")
                        print(f"     - Position: ({entity.position.x:.1f}, {entity.position.y:.1f})")
                        break
                else:
                    print(f"  ❌ Failed to deploy")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
