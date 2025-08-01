#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def debug_movement_blocking():
    """Debug why troops get stuck when moving towards bridges"""
    
    print("=== DEBUGGING MOVEMENT BLOCKING ===")
    
    battle = BattleState()
    
    # Test the path from (9.0, 14.0) to (3.5, 16.0)
    from_pos = Position(9.0, 14.0)
    to_pos = Position(3.5, 16.0)
    
    print(f"Testing path from ({from_pos.x}, {from_pos.y}) to ({to_pos.x}, {to_pos.y})")
    print(f"Source walkable: {battle.arena.is_walkable(from_pos)}")
    print(f"Target walkable: {battle.arena.is_walkable(to_pos)}")
    
    # Calculate direction
    dx = to_pos.x - from_pos.x
    dy = to_pos.y - from_pos.y
    distance = (dx * dx + dy * dy) ** 0.5
    
    print(f"Direction: ({dx:.2f}, {dy:.2f}), distance: {distance:.2f}")
    
    # Test intermediate positions along the path
    print(f"\nTesting intermediate positions:")
    
    steps = 20
    for i in range(1, steps + 1):
        progress = i / steps
        test_x = from_pos.x + dx * progress
        test_y = from_pos.y + dy * progress
        test_pos = Position(test_x, test_y)
        
        walkable = battle.arena.is_walkable(test_pos)
        print(f"  Step {i:2d}: ({test_x:4.1f}, {test_y:4.1f}) - walkable: {walkable}")
        
        if not walkable:
            # Analyze why it's not walkable
            in_bounds = battle.arena.is_valid_position(test_pos)
            is_blocked = battle.arena.is_blocked_tile(int(test_x), int(test_y))
            
            if not in_bounds:
                print(f"    → Out of bounds")
            elif is_blocked:
                print(f"    → Blocked tile")
            elif battle.arena.RIVER_Y1 <= test_y <= battle.arena.RIVER_Y2:
                on_left_bridge = 2.0 <= test_x < 5.0
                on_right_bridge = 13.0 <= test_x < 16.0
                print(f"    → River: on_left_bridge={on_left_bridge}, on_right_bridge={on_right_bridge}")
            else:
                print(f"    → Unknown reason")

def test_alternative_paths():
    """Test if alternative paths work better"""
    
    print(f"\n=== TESTING ALTERNATIVE PATHS ===")
    
    battle = BattleState()
    
    # Instead of direct diagonal path, test step-by-step approach
    start_pos = Position(9.0, 14.0)
    bridge_pos = Position(3.5, 16.0)
    
    print(f"Alternative path strategy:")
    print(f"1. Move towards bridge horizontally first")
    print(f"2. Then move vertically to bridge")
    
    # Test horizontal movement first
    intermediate_pos = Position(3.5, 14.0)  # Same X as bridge, but on land
    
    print(f"\nStep 1: Horizontal movement to ({intermediate_pos.x}, {intermediate_pos.y})")
    print(f"  Target walkable: {battle.arena.is_walkable(intermediate_pos)}")
    
    # Test path from start to intermediate
    dx1 = intermediate_pos.x - start_pos.x
    dy1 = intermediate_pos.y - start_pos.y
    distance1 = (dx1 * dx1 + dy1 * dy1) ** 0.5
    
    blocked_step = None
    for i in range(1, 11):
        progress = i / 10
        test_x = start_pos.x + dx1 * progress
        test_y = start_pos.y + dy1 * progress
        test_pos = Position(test_x, test_y)
        
        walkable = battle.arena.is_walkable(test_pos)
        print(f"    Step {i}: ({test_x:4.1f}, {test_y:4.1f}) - walkable: {walkable}")
        
        if not walkable:
            blocked_step = i
            break
    
    if blocked_step:
        print(f"  ❌ Horizontal path blocked at step {blocked_step}")
    else:
        print(f"  ✅ Horizontal path clear")
        
        # Test vertical movement to bridge
        print(f"\nStep 2: Vertical movement to bridge ({bridge_pos.x}, {bridge_pos.y})")
        
        dx2 = bridge_pos.x - intermediate_pos.x
        dy2 = bridge_pos.y - intermediate_pos.y
        
        for i in range(1, 6):
            progress = i / 5
            test_x = intermediate_pos.x + dx2 * progress
            test_y = intermediate_pos.y + dy2 * progress
            test_pos = Position(test_x, test_y)
            
            walkable = battle.arena.is_walkable(test_pos)
            print(f"    Step {i}: ({test_x:4.1f}, {test_y:4.1f}) - walkable: {walkable}")

if __name__ == "__main__":
    debug_movement_blocking()
    test_alternative_paths()