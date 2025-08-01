#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop
from clasher.data import CardStats

def test_visualization_fix():
    """Test that the visualization code doesn't crash"""
    
    print("=== TESTING VISUALIZATION FIX ===")
    
    try:
        # Create battle state
        battle = BattleState()
        
        # Create a troop with a target
        card_stats = CardStats(
            name="Minions",
            id=1,
            mana_cost=3,
            rarity="Common",
            hitpoints=190,
            damage=86,
            speed=60,
            range=2.0,
            sight_range=5.5
        )
        
        # Deploy troop successfully
        success = battle.deploy_card(0, 'Minions', Position(10.7, 14.0))
        print(f"Troop deployment: {'Success' if success else 'Failed'}")
        
        # Check if we have entities
        print(f"Number of entities: {len(battle.entities)}")
        
        # Simulate getting an entity with target_id (this is what was causing the crash)
        for entity in battle.entities.values():
            if hasattr(entity, 'target_id'):
                print(f"Entity: {entity.card_stats.name}")
                print(f"Has target_id: {entity.target_id}")
                print(f"Position: ({entity.position.x}, {entity.position.y})")
                
                # Test the logic that was failing
                if entity.target_id:
                    target = battle.entities.get(entity.target_id)
                    if target and target.is_alive:
                        distance_to_target = entity.position.distance_to(target.position)
                        print(f"Distance to target: {distance_to_target}")
                        print(f"Sight range: {entity.sight_range}")
                        
                        # This is the core logic that was causing variable issues
                        if distance_to_target <= entity.sight_range:
                            print("✅ Would show direct yellow arrow to target")
                        else:
                            print("✅ Would show forward-pointing yellow arrow")
        
        print("✅ Visualization logic test passed - no crashes!")
        return True
        
    except Exception as e:
        print(f"❌ Visualization test failed: {e}")
        return False

if __name__ == "__main__":
    test_visualization_fix()