#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.arena import Position, TileGrid

def debug_right_bridge_issue():
    """Debug why right bridge positions are unexpectedly walkable"""
    
    print("=== DEBUGGING RIGHT BRIDGE ISSUE ===")
    
    arena = TileGrid()
    
    # Test positions that should be river (not walkable)
    problem_positions = [
        Position(15.0, 15.5),
        Position(15.5, 15.5),
        Position(16.0, 15.5),
    ]
    
    for pos in problem_positions:
        print(f"\nPosition ({pos.x}, {pos.y}):")
        
        # Check if it's in bounds
        in_bounds = arena.is_valid_position(pos)
        print(f"  In bounds: {in_bounds}")
        
        # Check if it's a blocked tile
        tile_pos = (int(pos.x), int(pos.y))
        is_blocked_tile = arena.is_blocked_tile(int(pos.x), int(pos.y))
        print(f"  Blocked tile: {is_blocked_tile}")
        
        # Check river logic
        in_river_y = arena.RIVER_Y1 <= pos.y <= arena.RIVER_Y2
        print(f"  In river Y range ({arena.RIVER_Y1}-{arena.RIVER_Y2}): {in_river_y}")
        
        if in_river_y:
            on_left_bridge = 2.0 <= pos.x < 5.0
            on_right_bridge = 13.0 <= pos.x < 16.0
            print(f"  On left bridge (2.0 <= x < 5.0): {on_left_bridge}")
            print(f"  On right bridge (13.0 <= x < 16.0): {on_right_bridge}")
            print(f"  Should be walkable (on any bridge): {on_left_bridge or on_right_bridge}")
        
        # Final walkability
        walkable = arena.is_walkable(pos)
        print(f"  Actually walkable: {walkable}")
        
        # Check what the logic path is
        if not in_bounds:
            print(f"  → Blocked: Out of bounds")
        elif is_blocked_tile:
            print(f"  → Blocked: Blocked tile")
        elif in_river_y:
            if on_left_bridge or on_right_bridge:
                print(f"  → Walkable: On bridge")
            else:
                print(f"  → Blocked: In river, not on bridge")
        else:
            print(f"  → Walkable: On land")

if __name__ == "__main__":
    debug_right_bridge_issue()