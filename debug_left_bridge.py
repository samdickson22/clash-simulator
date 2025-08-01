#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.arena import Position, TileGrid

def debug_left_bridge():
    """Debug the left bridge walkability and pathfinding"""
    
    print("=== DEBUGGING LEFT BRIDGE ===")
    
    arena = TileGrid()
    
    # Left bridge should span x=2-4, y=15-16
    print("Left bridge tile analysis:")
    
    # Check all tiles around the left bridge area
    for y in range(14, 18):  # y=14-17 (includes river and adjacent land)
        for x in range(1, 6):  # x=1-5 (around bridge area)
            pos = Position(x, y)
            is_blocked = arena.is_blocked_tile(x, y)
            is_walkable = arena.is_walkable(pos)
            
            # Determine what type of tile this is
            tile_type = "UNKNOWN"
            if y < 15:
                tile_type = "LAND"
            elif 15 <= y <= 16:
                if 2 <= x <= 4:
                    tile_type = "BRIDGE"
                else:
                    tile_type = "RIVER"
            else:
                tile_type = "LAND"
            
            print(f"  Tile ({x}, {y}): type={tile_type:>6}, blocked={is_blocked}, walkable={is_walkable}")
            
            # Check for inconsistencies
            if tile_type == "BRIDGE" and (is_blocked or not is_walkable):
                print(f"    ❌ PROBLEM: Bridge tile should be walkable!")
            elif tile_type == "RIVER" and is_walkable:
                print(f"    ❌ PROBLEM: River tile should not be walkable!")
            elif tile_type == "LAND" and is_blocked and (x, y) not in arena.BLOCKED_TILES:
                print(f"    ❌ PROBLEM: Land tile blocked but not in BLOCKED_TILES!")
    
    # Test specific positions that might cause issues
    print(f"\nTesting specific problematic positions:")
    
    problem_positions = [
        Position(4.0, 15.0),  # Rightmost tile of left bridge, bottom
        Position(4.0, 16.0),  # Rightmost tile of left bridge, top
        Position(4.5, 15.5),  # Center-right edge of left bridge
        Position(4.9, 15.5),  # Almost off the bridge
        Position(5.0, 15.5),  # Just off the bridge (should be river)
    ]
    
    for pos in problem_positions:
        is_walkable = arena.is_walkable(pos)
        print(f"  Position ({pos.x}, {pos.y}): walkable={is_walkable}")
        
        # Check what the walkability logic thinks about this position
        if arena.RIVER_Y1 <= pos.y <= arena.RIVER_Y2:
            on_left_bridge = 2.0 <= pos.x < 5.0
            on_right_bridge = 13.0 <= pos.x < 16.0
            should_be_walkable = on_left_bridge or on_right_bridge
            print(f"    River logic: on_left_bridge={on_left_bridge}, should_be_walkable={should_be_walkable}")
            
            if is_walkable != should_be_walkable:
                print(f"    ❌ MISMATCH: is_walkable={is_walkable}, should_be={should_be_walkable}")

def test_bridge_edge_movement():
    """Test movement at the edges of bridges"""
    
    print(f"\n=== TESTING BRIDGE EDGE MOVEMENT ===")
    
    arena = TileGrid()
    
    # Test movement from bridge to river (should be blocked)
    test_cases = [
        {
            "from": Position(4.0, 15.5), 
            "to": Position(5.0, 15.5),
            "description": "Move from rightmost bridge tile to river"
        },
        {
            "from": Position(4.5, 15.5), 
            "to": Position(5.5, 15.5),
            "description": "Move from bridge edge to deep river"
        },
        {
            "from": Position(3.5, 15.5), 
            "to": Position(4.5, 15.5),
            "description": "Move within bridge (should work)"
        },
        {
            "from": Position(2.5, 15.5), 
            "to": Position(1.5, 15.5),
            "description": "Move from bridge to river on left side"
        }
    ]
    
    for test in test_cases:
        from_pos = test["from"]
        to_pos = test["to"]
        desc = test["description"]
        
        print(f"\n{desc}")
        print(f"  From: ({from_pos.x}, {from_pos.y}) - walkable: {arena.is_walkable(from_pos)}")
        print(f"  To: ({to_pos.x}, {to_pos.y}) - walkable: {arena.is_walkable(to_pos)}")
        
        # Calculate movement vector
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        if distance > 0:
            # Simulate small movement steps
            step_size = 0.1  # Small steps
            steps = int(distance / step_size)
            
            print(f"  Testing {steps} small steps:")
            for i in range(1, min(steps + 1, 11)):  # Test up to 10 steps
                progress = (i * step_size) / distance
                if progress > 1.0:
                    progress = 1.0
                
                test_x = from_pos.x + dx * progress
                test_y = from_pos.y + dy * progress
                test_pos = Position(test_x, test_y)
                
                walkable = arena.is_walkable(test_pos)
                print(f"    Step {i}: ({test_x:.2f}, {test_y:.2f}) - walkable: {walkable}")
                
                if not walkable:
                    print(f"      ❌ Movement blocked at step {i}")
                    break

if __name__ == "__main__":
    debug_left_bridge()
    test_bridge_edge_movement()