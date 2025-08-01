#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def test_movement_collision():
    """Test movement collision detection with blocked tiles"""
    
    print("=== TESTING MOVEMENT COLLISION WITH BLOCKED TILES ===")
    
    battle = BattleState()
    arena = battle.arena
    
    # Test movement from various positions towards blocked tiles
    test_cases = [
        # From normal tile to river edge blocked tile
        {
            "from": Position(1.0, 14.0),
            "to": Position(0.0, 14.0),  # Blocked river edge tile
            "description": "Move from (1,14) to blocked river edge (0,14)"
        },
        # From normal tile to fence blocked tile
        {
            "from": Position(1.0, 0.0),
            "to": Position(0.0, 0.0),  # Blocked fence tile
            "description": "Move from (1,0) to blocked fence (0,0)"
        },
        # From normal tile to king area (should be allowed)
        {
            "from": Position(5.0, 0.0),
            "to": Position(6.0, 0.0),  # King area tile
            "description": "Move from (5,0) to king area (6,0)"
        },
        # From king area to fence (should be blocked)
        {
            "from": Position(6.0, 0.0),
            "to": Position(5.0, 0.0),  # Blocked fence tile  
            "description": "Move from king area (6,0) to blocked fence (5,0)"
        }
    ]
    
    for test_case in test_cases:
        from_pos = test_case["from"]
        to_pos = test_case["to"]
        desc = test_case["description"]
        
        print(f"\n{desc}")
        print(f"  From: ({from_pos.x}, {from_pos.y})")
        print(f"  To: ({to_pos.x}, {to_pos.y})")
        
        # Check if destination is blocked
        dest_blocked = arena.is_blocked_tile(int(to_pos.x), int(to_pos.y))
        dest_walkable = arena.is_walkable(to_pos)
        
        print(f"  Destination blocked: {dest_blocked}")
        print(f"  Destination walkable: {dest_walkable}")
        
        # Simulate the movement logic from entities.py
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        if distance > 0:
            # Simulate 1 second movement at 1 tile/second speed
            dt = 1.0
            speed_tiles_per_second = 1.0
            move_distance = speed_tiles_per_second * dt
            
            if move_distance > distance:
                move_distance = distance
            
            move_x = (dx / distance) * move_distance
            move_y = (dy / distance) * move_distance
            
            # Calculate new position
            new_position = Position(from_pos.x + move_x, from_pos.y + move_y)
            
            print(f"  Calculated new position: ({new_position.x:.2f}, {new_position.y:.2f})")
            
            # This is the key check from entities.py line 210:
            # if self.is_air_unit or (battle_state and battle_state.arena.is_walkable(new_position)):
            can_move = arena.is_walkable(new_position)
            print(f"  Can move (walkable check): {can_move}")
            
            if can_move:
                print(f"  ✅ Movement ALLOWED")
            else:
                print(f"  ❌ Movement BLOCKED - unit will be stuck")
                
            # Double-check against expected result
            if dest_blocked and can_move:
                print(f"  🚨 ERROR: Should not be able to move into blocked tile!")
            elif not dest_blocked and not can_move:
                print(f"  🚨 ERROR: Should be able to move into unblocked tile!")
            else:
                print(f"  ✅ CORRECT: Movement result matches tile blocking status")

if __name__ == "__main__":
    test_movement_collision()