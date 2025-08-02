#!/usr/bin/env python3
"""
Test tower collision detection for troop deployments
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader

def test_tower_collision_detection():
    """Test that troops cannot be deployed on tower tiles"""
    
    print("=== Testing Tower Collision Detection ===")
    
    # Create battle state
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 50.0
    
    # Test regular troop deployment
    card_name = 'Knight'
    if card_name not in cards:
        print(f"❌ {card_name} not found")
        return
    
    battle.players[0].hand = [card_name, 'Fireball', 'Arrows', 'Skeletons']
    
    # Test 1: Try to deploy on Blue King Tower (4x4 area around 9, 2.5)
    print(f"\n--- Test 1: Deploy {card_name} on Blue King Tower ---")
    king_tower_pos = Position(9.0, 2.5)  # Exact center
    success = battle.deploy_card(0, card_name, king_tower_pos)
    
    if success:
        print("❌ Deployment should have failed on king tower")
    else:
        print("✅ Deployment correctly failed on king tower")
    
    # Test 2: Try to deploy on Blue Left Princess Tower (3x3 area around 3.5, 6.5)
    print(f"\n--- Test 2: Deploy {card_name} on Blue Left Princess Tower ---")
    princess_tower_pos = Position(3.5, 6.5)  # Exact center
    success = battle.deploy_card(0, card_name, princess_tower_pos)
    
    if success:
        print("❌ Deployment should have failed on princess tower")
    else:
        print("✅ Deployment correctly failed on princess tower")
    
    # Test 3: Try to deploy near tower edge (should fail)
    print(f"\n--- Test 3: Deploy {card_name} on tower edge ---")
    tower_edge_pos = Position(4.5, 6.5)  # Edge of 3x3 princess tower area
    success = battle.deploy_card(0, card_name, tower_edge_pos)
    
    if success:
        print("❌ Deployment should have failed on tower edge")
    else:
        print("✅ Deployment correctly failed on tower edge")
    
    # Test 4: Deploy just outside tower area (should succeed)
    print(f"\n--- Test 4: Deploy {card_name} just outside tower area ---")
    safe_pos = Position(6.0, 6.5)  # Just outside 3x3 princess tower area
    success = battle.deploy_card(0, card_name, safe_pos)
    
    if success:
        print("✅ Deployment succeeded in safe area")
    else:
        print("❌ Deployment should have succeeded in safe area")
    
    # Test 5: Check blocked ranges for Royal Recruits
    print(f"\n--- Test 5: Check blocked X ranges for Royal Recruits ---")
    
    # Test at different Y coordinates
    test_y_coords = [2.5, 6.5, 8.0, 25.5, 29.5]
    
    for y in test_y_coords:
        blocked_ranges = battle.arena.get_tower_blocked_x_ranges(y, battle)
        print(f"Y={y}: Blocked X ranges: {blocked_ranges}")
    
    # Test 6: Royal Recruits deployment near towers
    print(f"\n--- Test 6: Royal Recruits deployment tests ---")
    
    card_name = 'RoyalRecruits'
    if card_name in cards:
        battle.players[0].hand = [card_name, 'Fireball', 'Arrows', 'Skeletons']
        battle.players[0].elixir = 50.0
        
        # Try to deploy at Y coordinate that intersects with princess towers
        recruit_pos = Position(9.0, 6.5)  # Y=6.5 intersects with princess towers
        success = battle.deploy_card(0, card_name, recruit_pos)
        
        if success:
            print("✅ Royal Recruits deployed successfully with tower avoidance")
            
            # Check where recruits actually spawned
            recruits = []
            for entity in battle.entities.values():
                if (hasattr(entity, 'card_stats') and entity.card_stats and 
                    entity.card_stats.name == card_name and
                    getattr(entity, 'player_id', -1) == 0):
                    recruits.append(entity)
            
            print(f"Royal Recruits positions:")
            for i, recruit in enumerate(recruits):
                pos = recruit.position
                print(f"  Recruit {i+1}: ({pos.x:.2f}, {pos.y:.2f})")
                
                # Check if any recruit is on a tower
                if battle.arena.is_tower_tile(pos, battle):
                    print(f"    ❌ Recruit {i+1} is on a tower!")
                else:
                    print(f"    ✅ Recruit {i+1} is in safe position")
        else:
            print("❌ Royal Recruits deployment failed")
    else:
        print("❌ RoyalRecruits not found in cards")

if __name__ == "__main__":
    test_tower_collision_detection()