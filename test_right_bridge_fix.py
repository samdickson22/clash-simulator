#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.arena import Position, TileGrid

def test_right_bridge_walkability():
    """Test that right bridge has the same fix"""
    
    print("=== TESTING RIGHT BRIDGE WALKABILITY ===")
    
    arena = TileGrid()
    
    # Right bridge should span x=13-15, y=15-16
    print("Right bridge fractional position tests:")
    
    test_positions = [
        Position(13.0, 15.5),  # Left edge of right bridge
        Position(13.5, 15.5),  # Within right bridge
        Position(14.0, 15.5),  # Center of right bridge
        Position(14.5, 15.5),  # Within right bridge
        Position(14.9, 15.5),  # Within right bridge (tile 14)
        Position(15.0, 15.5),  # Within right bridge (tile 15)
        Position(15.5, 15.5),  # Within right bridge (tile 15)
        Position(15.9, 15.5),  # Right edge of right bridge (tile 15)
        Position(16.0, 15.5),  # Should be river now (not walkable)
    ]
    
    for pos in test_positions:
        walkable = arena.is_walkable(pos)
        print(f"  Position ({pos.x}, {pos.y}): walkable={walkable}")
        
        # Determine what this should be
        if 13.0 <= pos.x < 16.0 and arena.RIVER_Y1 <= pos.y <= arena.RIVER_Y2:
            expected = True  # Should be bridge
        elif arena.RIVER_Y1 <= pos.y <= arena.RIVER_Y2:
            expected = False  # Should be river
        else:
            expected = True  # Should be land
        
        if walkable == expected:
            print(f"    ✅ Correct")
        else:
            print(f"    ❌ Expected {expected}")
    
    # Test movement across right bridge
    print(f"\nTesting movement across right bridge:")
    
    test_movement = [
        {"from": Position(14.0, 15.5), "to": Position(14.9, 15.5), "desc": "Within right bridge"},
        {"from": Position(14.5, 15.5), "to": Position(15.5, 15.5), "desc": "From bridge to river"},
    ]
    
    for test in test_movement:
        from_pos = test["from"]
        to_pos = test["to"]
        desc = test["desc"]
        
        print(f"\n{desc}:")
        print(f"  From: ({from_pos.x}, {from_pos.y}) - walkable: {arena.is_walkable(from_pos)}")
        print(f"  To: ({to_pos.x}, {to_pos.y}) - walkable: {arena.is_walkable(to_pos)}")
        
        # Test small steps
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        if distance > 0:
            step_size = 0.1
            steps = int(distance / step_size)
            
            blocked_at = None
            for i in range(1, min(steps + 1, 11)):
                progress = (i * step_size) / distance
                if progress > 1.0:
                    progress = 1.0
                
                test_x = from_pos.x + dx * progress
                test_y = from_pos.y + dy * progress
                test_pos = Position(test_x, test_y)
                
                walkable = arena.is_walkable(test_pos)
                if not walkable:
                    blocked_at = i
                    print(f"    Movement blocked at step {i}: ({test_x:.2f}, {test_y:.2f})")
                    break
            
            if blocked_at is None:
                print(f"    ✅ All {min(steps, 10)} steps walkable")

if __name__ == "__main__":
    test_right_bridge_walkability()