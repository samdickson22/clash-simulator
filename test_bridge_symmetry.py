#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.arena import TileGrid

def test_bridge_symmetry():
    """Test that left and right bridges are positioned symmetrically"""
    
    print("=== TESTING BRIDGE SYMMETRY ===")
    
    arena = TileGrid()
    
    # Arena is 18 tiles wide (0-17)
    # Center line is at x=9 (middle of 18-tile arena)
    arena_center = 9.0
    
    left_bridge_center = arena.LEFT_BRIDGE.x
    right_bridge_center = arena.RIGHT_BRIDGE.x
    
    print(f"Arena width: 18 tiles (0-17)")
    print(f"Arena center: x={arena_center}")
    print(f"Left bridge center: x={left_bridge_center}")
    print(f"Right bridge center: x={right_bridge_center}")
    
    # Calculate distances from center
    left_distance_from_center = abs(left_bridge_center - arena_center)
    right_distance_from_center = abs(right_bridge_center - arena_center)
    
    print(f"\nDistance from arena center:")
    print(f"Left bridge: {left_distance_from_center} tiles")
    print(f"Right bridge: {right_distance_from_center} tiles")
    
    # Check symmetry
    if abs(left_distance_from_center - right_distance_from_center) < 0.1:
        print(f"✅ Bridges are symmetrically positioned!")
    else:
        print(f"❌ Bridges are NOT symmetrically positioned!")
        print(f"   Difference: {abs(left_distance_from_center - right_distance_from_center)} tiles")
    
    # Test bridge span symmetry
    print(f"\nBridge spans:")
    print(f"Left bridge: x=2-4 (3 tiles wide, center at 3)")
    print(f"Right bridge: x=13-15 (3 tiles wide, center at 14)")
    
    left_span_center = 3.0  # Center of tiles 2,3,4
    right_span_center = 14.0  # Center of tiles 13,14,15
    
    left_span_distance = abs(left_span_center - arena_center)
    right_span_distance = abs(right_span_center - arena_center)
    
    print(f"Left span center distance from arena center: {left_span_distance}")
    print(f"Right span center distance from arena center: {right_span_distance}")
    
    if abs(left_span_distance - right_span_distance) < 0.1:
        print(f"✅ Bridge spans are symmetrically positioned!")
    else:
        print(f"❌ Bridge spans are NOT symmetrically positioned!")
    
    # Visual representation
    print(f"\nVisual representation (X = bridge tiles, . = normal tiles):")
    print("  0123456789012345678")
    print("  ", end="")
    for x in range(18):
        if 2 <= x <= 4 or 13 <= x <= 15:  # Bridge tiles
            print("X", end="")
        elif x == 9:  # Center line
            print("|", end="")
        else:
            print(".", end="")
    print()
    print(f"     ^         ^")
    print(f"  Left(3)   Right(14)")

if __name__ == "__main__":
    test_bridge_symmetry()