#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop
from clasher.data import CardStats

def test_pathfinding_avoidance():
    """Test that units path around blocked tiles instead of getting stuck"""
    
    print("=== TESTING PATHFINDING AVOIDANCE ===")
    
    battle = BattleState()
    
    # Create a minimal card stats for testing
    card_stats = CardStats(
        name="Knight",
        id=1,
        mana_cost=3,
        rarity="Common",
        hitpoints=1400,
        damage=167,
        speed=60,  # 1 tile per second
        range=1.0,
        sight_range=5.5
    )
    
    # Test case 1: Unit trying to move towards blocked river edge tile
    print("\n--- Test Case 1: Moving towards blocked river edge ---")
    troop1 = Troop(
        id=1,
        position=Position(1.5, 14.0),  # Near blocked tile (0, 14)
        player_id=0,
        card_stats=card_stats,
        hitpoints=1400,
        max_hitpoints=1400,
        damage=167,
        range=1.0,
        sight_range=5.5,
        speed=60,
        is_air_unit=False
    )
    
    print(f"Initial position: ({troop1.position.x:.2f}, {troop1.position.y:.2f})")
    
    # Create a target entity behind the blocked tile to force pathfinding
    target_troop = Troop(
        id=999,
        position=Position(0.0, 13.0),  # On the other side of blocked tile
        player_id=1,  # Enemy
        card_stats=card_stats,
        hitpoints=1400,
        max_hitpoints=1400,
        damage=167,
        range=1.0,
        sight_range=5.5,
        speed=60,
        is_air_unit=False
    )
    
    # Add target to battle state
    battle.entities[999] = target_troop
    
    # Simulate several movement steps
    for step in range(5):
        print(f"\nStep {step + 1}:")
        old_pos = Position(troop1.position.x, troop1.position.y)
        
        # Move towards target (this should trigger avoidance)
        troop1._move_towards_target(target_troop, 1.0, battle)
        
        new_pos = troop1.position
        distance_moved = old_pos.distance_to(new_pos)
        
        print(f"  Position: ({new_pos.x:.2f}, {new_pos.y:.2f})")
        print(f"  Distance moved: {distance_moved:.3f}")
        
        if distance_moved < 0.01:
            print(f"  ❌ Unit is stuck!")
        else:
            print(f"  ✅ Unit is moving (avoiding blocked tiles)")
    
    # Test case 2: Unit trying to move towards blocked fence tile
    print("\n--- Test Case 2: Moving towards blocked fence tile ---")
    troop2 = Troop(
        id=2,
        position=Position(1.0, 0.5),  # Near blocked fence tile (0, 0)
        player_id=0,
        card_stats=card_stats,
        hitpoints=1400,
        max_hitpoints=1400,
        damage=167,
        range=1.0,
        sight_range=5.5,
        speed=60,
        is_air_unit=False
    )
    
    # Create target behind fence
    target_troop2 = Troop(
        id=998,
        position=Position(0.0, 1.5),  # On the other side of fence
        player_id=1,  # Enemy
        card_stats=card_stats,
        hitpoints=1400,
        max_hitpoints=1400,
        damage=167,
        range=1.0,
        sight_range=5.5,
        speed=60,
        is_air_unit=False
    )
    
    battle.entities[998] = target_troop2
    
    print(f"Initial position: ({troop2.position.x:.2f}, {troop2.position.y:.2f})")
    
    # Simulate movement steps
    for step in range(5):
        print(f"\nStep {step + 1}:")
        old_pos = Position(troop2.position.x, troop2.position.y)
        
        # Move towards target
        troop2._move_towards_target(target_troop2, 1.0, battle)
        
        new_pos = troop2.position
        distance_moved = old_pos.distance_to(new_pos)
        
        print(f"  Position: ({new_pos.x:.2f}, {new_pos.y:.2f})")
        print(f"  Distance moved: {distance_moved:.3f}")
        
        if distance_moved < 0.01:
            print(f"  ❌ Unit is stuck!")
        else:
            print(f"  ✅ Unit is moving (avoiding blocked tiles)")

def test_alternative_move_function():
    """Test the _find_alternative_move function directly"""
    
    print("\n=== TESTING ALTERNATIVE MOVE FUNCTION ===")
    
    battle = BattleState()
    
    card_stats = CardStats(
        name="Knight",
        id=1,
        mana_cost=3,
        rarity="Common",
        hitpoints=1400,
        damage=167,
        speed=60,
        range=1.0,
        sight_range=5.5
    )
    
    # Create unit next to a blocked tile
    troop = Troop(
        id=1,
        position=Position(1.0, 14.0),  # Next to blocked tile (0, 14)
        player_id=0,
        card_stats=card_stats,
        hitpoints=1400,
        max_hitpoints=1400,
        damage=167,
        range=1.0,
        sight_range=5.5,
        speed=60,
        is_air_unit=False
    )
    
    # Test different blocked movements
    test_moves = [
        (-1.0, 0.0, "Moving left towards blocked tile (0, 14)"),
        (-0.7, -0.7, "Moving diagonally towards blocked corner"),
        (0.0, -1.0, "Moving up (should be clear)")
    ]
    
    for move_x, move_y, description in test_moves:
        print(f"\n{description}")
        print(f"  Original move: ({move_x:.2f}, {move_y:.2f})")
        
        # Test the alternative move function
        alternative = troop._find_alternative_move(move_x, move_y, battle)
        
        if alternative:
            alt_x, alt_y = alternative
            print(f"  Alternative found: ({alt_x:.2f}, {alt_y:.2f})")
            
            # Verify the alternative is actually walkable
            alt_pos = Position(troop.position.x + alt_x, troop.position.y + alt_y)
            walkable = battle.arena.is_walkable(alt_pos)
            print(f"  Alternative is walkable: {walkable}")
            
            if walkable:
                print(f"  ✅ Valid alternative found")
            else:
                print(f"  ❌ Alternative is not walkable!")
        else:
            print(f"  No alternative found")
            
            # Check if original move was actually blocked
            orig_pos = Position(troop.position.x + move_x, troop.position.y + move_y)
            orig_walkable = battle.arena.is_walkable(orig_pos)
            
            if not orig_walkable:
                print(f"  ❌ Original move was blocked but no alternative found")
            else:
                print(f"  ✅ Original move was clear, no alternative needed")

if __name__ == "__main__":
    test_pathfinding_avoidance()
    test_alternative_move_function()