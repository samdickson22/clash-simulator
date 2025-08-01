#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.arena import Position, TileGrid

def test_bridge_positions():
    """Test that bridge positions are correct after the fix"""
    
    print("=== TESTING BRIDGE POSITIONS ===")
    
    arena = TileGrid()
    
    # Test left bridge (should be unchanged at x=2-4, y=15-16)
    print("\nLeft Bridge (x=2-4, y=15-16):")
    left_bridge_tiles = [
        (2, 15), (3, 15), (4, 15),
        (2, 16), (3, 16), (4, 16)
    ]
    
    for x, y in left_bridge_tiles:
        walkable = arena.is_walkable(Position(x, y))
        print(f"  Tile ({x}, {y}): walkable={walkable}")
        if not walkable:
            print(f"    ❌ Left bridge tile should be walkable!")
    
    # Test right bridge (should now be at x=13-15, y=15-16)  
    print("\nRight Bridge (x=13-15, y=15-16):")
    right_bridge_tiles = [
        (13, 15), (14, 15), (15, 15),
        (13, 16), (14, 16), (15, 16)
    ]
    
    for x, y in right_bridge_tiles:
        walkable = arena.is_walkable(Position(x, y))
        print(f"  Tile ({x}, {y}): walkable={walkable}")
        if not walkable:
            print(f"    ❌ Right bridge tile should be walkable!")
    
    # Test old right bridge position (x=14-16 should no longer be bridge)
    print("\nOld right bridge area (x=16, y=15-16) should NOT be walkable:")
    old_right_bridge_tiles = [(16, 15), (16, 16)]
    
    for x, y in old_right_bridge_tiles:
        walkable = arena.is_walkable(Position(x, y))
        print(f"  Tile ({x}, {y}): walkable={walkable}")
        if walkable:
            print(f"    ❌ Old right bridge area should not be walkable (river)!")
        else:
            print(f"    ✅ Correctly not walkable (river)")
    
    # Test bridge center positions
    print(f"\nBridge centers:")
    print(f"  Left bridge center: {arena.LEFT_BRIDGE}")
    print(f"  Right bridge center: {arena.RIGHT_BRIDGE}")
    
    # Verify bridge centers are walkable
    left_walkable = arena.is_walkable(arena.LEFT_BRIDGE)
    right_walkable = arena.is_walkable(arena.RIGHT_BRIDGE)
    
    print(f"  Left bridge center walkable: {left_walkable}")
    print(f"  Right bridge center walkable: {right_walkable}")
    
    if not left_walkable:
        print(f"    ❌ Left bridge center should be walkable!")
    if not right_walkable:
        print(f"    ❌ Right bridge center should be walkable!")
    
    if left_walkable and right_walkable:
        print(f"    ✅ Both bridge centers are walkable")

if __name__ == "__main__":
    test_bridge_positions()